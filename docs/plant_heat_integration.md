# Plant heat integration, stage 1: where does the heat come from and where does the deficit go?

Written 2026-11-02 on `origin/main` f628406 (branch `heat-integration`). **Read-only.** The new key `("PLANT", "HeatIntegration")` is an inventory: it adds no boiler, burner, exchanger or stack, changes no temperature,
conversion, flow, composition or hydrogen, and nothing reads it. Every default, Confirmed value, registry value, engine equation and hourly-runtime file is unchanged. The only edit outside the new files is one
registration line in `python/ga001_gasifier_model.py` (next to `ga001_carbon_accounting.register(engine)`), and the pinned key counts in six existing tests (120 -> 121, section 8).
Offline throughout: in-memory fake store, no database, no network, the real `secrets.toml` never read, `HYGAS_ALLOW_DB_WRITES` unset.

Files: `python/plant_heat_integration.py` (pure functions + `register`), `scripts/run_heat_integration_report.py` (writes `outputs/heat/heat_integration.md` + `.csv`, git-ignored),
`tests/test_plant_heat_integration.py` (23 tests, about 7 s), `tests/fixtures/snapshot_origin_main_f628406.json.gz` (the unmodified origin/main snapshots the "nothing else moved" test compares against).

## 1. Read first: what heat quantities exist today (item A)

The engine has **no boiler, burner, stack or heat-recovery model** (searched: `boiler`, `burner`, `stack` in `python/*.py` hit only comments and audit conventions: `balance_audit.py:430, 460-465, 709, 795`).
Heat appears in three places only:

| quantity | where | value (default feed) | status | who owns the number |
|---|---|---|---|---|
| WGS steam raise 20 -> 150 degC (HB-003) | `hb_wgs_psa_storage_chain.py` (HB-003 hot 400 -> 220 degC, cold 20 -> 150 degC, "Design heat duty" 5 kW) | the engine counts only this sensible duty | registry row resolved to **Unverified (registry)** | project-own registry text, no DOK-ING origin recorded in `data/registry_status_overlay.json` |
| Heat demands of GA-004 steam, WGS steam, air preheat, FE-005 dryer | `balance_audit.heat_demands` (`balance_audit.py:691-703`), `ga001_energy_balance.py:86` | 13.0 + 61.4 + 3.4 + 2.7 = 80.6 kW (regasify), 66.7 kW (heat_only) | Estimated | project-own calculation from registry temperatures |
| Implied gasifier heat duty | `balance_audit.gasifier_energy` (`balance_audit.py:640`) | LHV dependent: +22.8 / -3.3 / -29.3 kW (regasify) and +26.7 / +0.6 / -25.4 kW (heat_only) at LHV 15 / 17.5 / 20 (negative = surplus the gasifier would have to shed) | Estimated / Assumed | project-own; DOK-ING's feed LHV range 15 .. 20 MJ/kg is the input |

Registry temperatures that fix the levels (committed overlay, resolved with `equipment_datasheet.resolve_datasheets`): GA-004 air preheat 200 degC, GA-004 steam 350 degC / 5 bar(g), FE-005 operating 100 degC, GA-008 operating 180 degC,
GC-004 inlet 860 / outlet 65 degC, HB-001 inlet 350 degC, HB-004 inlet 220 degC, HB-005 steam 45 kg/h at 350 degC: **all resolve to "Unverified (registry)"**. None resolves to DOK-ING-confirmed; the only non-registry label is GA-001 operating
temperature 950 degC = Assumed. Note the comment at `balance_audit.py:90` still says "Confirmed static design value" for the 200 degC air preheat; the overlay does not support that wording (reported, not edited: out of scope).
The registry says the tail gas returns "as supplemental fuel" (HB-007, HB-009) and that GA-004 air preheat and FE-005 are "recovered process heat"; none of that is modelled as heat flow, which is the gap this key makes visible.

Five-line design: (1) sinks = the four EnergyBalance demands (taken from `ga001_energy_balance.energy_balance`, recomputed inside the key so EnergyBalance stays a leaf) + the one extra sink the published state supports (WGS feed reheat, clean gas
SA-011 40 degC -> 350 degC); (2) sources = product-gas sensible heat, WGS reaction heat (HTS, LTS), ash and carbon-black heat (low grade), flue gas from burning the tail gas; the tail-gas chemical energy is shown but counted only through the flue gas;
(3) each source is released over a temperature interval and may serve a need only at a level at least `delta_t_min_k` below it (greedy, hottest need first, coldest qualifying supply first); (4) the unmet need is the supplementary fuel (kW, and as kg/day of
hydrogen at 33.32 kWh/kg) and recovered heat that cannot serve what is unmet is reported as the temperature-level mismatch; (5) unknown terms are Missing, never zero.
Risks: recovery fractions are Assumed; steam bands use steam-table values at 6 bar abs; the flue-gas temperature of a burner that does not exist is Assumed; the gas-cooler outlet temperature is 65 degC today because GC-004 is a water-spray quench.

## 2. What is a source and what is a sink

Sinks (kW, level): raise gasifier steam to 350 degC (split into liquid heating 18.4 %, evaporation 68.5 %, superheat 13.1 %, Estimated), raise WGS steam (same split), preheat air to 200 degC, dry the feed at 100 degC,
WGS feed reheat to 350 degC (when the clean gas arrives colder), and, per LHV case, the implied gasifier heat duty at the gasifier temperature when it is positive.
Sources: product gas from gasifier temperature down to the cooler outlet (Calculated, mean cp `balance_audit.CP_J_MOLK`), WGS reaction heat (`DH_WGS_KJ_MOL` = -41.158 kJ/mol from standard enthalpies of formation, released at 350 / 220 degC),
ash and carbon-black sensible heat (Assumed solids cp 1.0 kJ/kg.K, range 0.8 .. 1.4, `balance_audit.SOLIDS_CP_KJ_KGK`), flue gas (adiabatic flame about 1050 degC to the stack temperature, Assumed lambda and stack), and a negative gasifier duty as a surplus at the gasifier temperature.
`regasify` (default): the tail gas is gasifier feed, so the flue-gas source is shown but **not counted**. `heat_only`: counted.

## 3. Constants and their statuses

| constant | value | range | status |
|---|---|---|---|
| recovery_gas_cooler | 0.7 | 0.5 .. 0.9 | Assumed |
| recovery_wgs | 0.7 | 0.5 .. 0.9 | Assumed |
| recovery_ash (also carbon black) | 0.5 | 0.25 .. 0.75 | Assumed |
| recovery_flue | 0.8 | 0.6 .. 0.9 | Assumed |
| delta_t_min_k | 20 K | 10 .. 40 | Assumed |
| excess_air_ratio | 1.2 | 1.1 .. 1.5 | Assumed |
| stack_temperature_c | 180 degC | 120 .. 250 | Assumed |
| ash_discharge_temperature_c | 150 degC | 100 .. 300 | Assumed (GA-006 registry "Char temperature at inlet" 150 is Unverified (registry)) |
| carbon_black_final_c | 60 degC | 25 .. 100 | Assumed |
| gas_cooler_outlet_c | 65 degC | 65 .. 300 | Assumed (65 is the GC-004 quench outlet, `gc_gas_cleaning_chain.py:295`) |
| solids cp | 1.0 kJ/kg.K | 0.8 .. 1.4 | Assumed |
| steam band split at 6 bar abs | T_sat 158.83 degC, h_fg 2085.8 kJ/kg | - | Estimated (steam tables) |
| WGS reaction enthalpy | -41.158 kJ/mol | - | Calculated |
| H2 LHV | 33.32 kWh/kg | - | Calculated (`balance_audit.LHV_KJ_MOL`, `hb_wgs_psa_storage_chain.M_H2`) |

Nothing was tuned: the values are module defaults, and sensitivities (section 5) move one at a time across the stated range.

## 4. The numbers (default feed, converged, `outputs/heat/heat_integration.md` sections 1-5)

Unmet = supplementary fuel at 100 % burner efficiency (no efficiency is modelled), not applied anywhere.

| case | tail_gas_mode | feed LHV MJ/kg | demand kW | recovered kW | net, energy basis kW | unmet kW | = H2 kg/day | level mismatch kW |
|---|---|---|---|---|---|---|---|---|
| default feed | regasify | 15.0 | 116.0 | 38.8 | -77.2 | 77.2 | 55.6 | 0.0 |
| default feed | regasify | 17.5 | 93.3 | 41.1 | -52.2 | 52.2 | 37.6 | 0.0 |
| default feed | regasify | 20.0 | 93.3 | 59.3 | -33.9 | 33.9 | 24.4 | 0.0 |
| default feed | heat_only | 15.0 | 103.3 | 64.0 | -39.3 | 39.3 | 28.3 | 0.0 |
| default feed | heat_only | 17.5 | 77.2 | 64.0 | -13.2 | 13.2 | 9.5 | 0.0 |
| default feed | heat_only | 20.0 | 76.6 | 81.8 | +5.2 | 0.0 | 0.0 | - |
| cotton | regasify / heat_only | 14.3 | 111.6 / 99.4 | 37.8 / 61.9 | -73.8 / -37.5 | 73.8 / 37.5 | 53.1 / 27.0 | 0.0 |
| polyethylene | regasify / heat_only | 35.9 | 243.7 / 221.3 | 74.7 / 125.8 | -169.0 / -95.6 | 169.0 / 95.6 | 121.7 / 68.8 | 0.0 |
| S2 oxygen-blown | regasify / heat_only | 17.5 | 84.0 / 71.0 | 41.0 / 69.4 | -43.0 / -1.6 | 43.0 / 1.6 | 31.0 / 1.2 | 0.0 |
| S4a steam only (allothermal) | regasify / heat_only | 17.5 | 158.5 / 129.6 | 31.6 / 69.8 | -126.9 / -59.7 | 126.9 / 59.7 | 91.4 / 43.0 | 0.0 |

(Five-cycle and 30-cycle states agree to the printed digits.) Missing in S2: the heat or electricity of the air-separation unit; S4a: the allothermal heat supply is the implied-duty sink.

## 5. Sensitivities (one at a time, unmet kW at midpoint LHV, default feed)

| constant | regasify low / high | heat_only low / high |
|---|---|---|
| recovery_gas_cooler 0.5 / 0.9 | +9.8 / -9.8 | +7.2 / -7.2 |
| recovery_wgs 0.5 / 0.9 | +1.8 / -1.8 | +1.4 / -1.4 |
| recovery_ash 0.25 / 0.75 | +0.2 / -0.2 | +0.2 / -0.2 |
| recovery_flue 0.6 / 0.9 | 0 (not counted) | +8.3 / -4.2 |
| stack_temperature_c 120 / 250 | 0 | -2.3 / +2.7 |
| gas_cooler_outlet_c 65 / 300 (high) | +8.5 | +6.7 |
| delta_t_min_k 10 / 40, excess_air 1.1 / 1.5, ash and carbon-black temperatures | under 0.7 | under 0.7 |

Bound (not a tuning): with **every** recovery fraction at the top of its range and the stack at 120 degC, midpoint-LHV unmet is 40.3 kW (regasify) and 0 kW (heat_only; 15.8 kW on the model-composition case, 23.6 kW at DOK-ING's low LHV).

## 6. What the numbers do and do not show

Do show: with the tail gas treated as gasifier feed (today's default) the recoverable heat covers 33 % (LHV 15), 44 % (17.5) and 64 % (20) of the demand, and no one-at-a-time or combined change within the stated ranges closes it
(best case 16.9 kW unmet at LHV 20). Treating the tail gas as heat (`heat_only`) raises the recoverable heat by about 55 % at the midpoint (41.1 -> 64.0 kW) and brings the midpoint to 13 kW unmet (9.5 kg/day of hydrogen-equivalent); it closes at LHV 20 or with high recovery.
Caution on the LHV 20 closure: 17.8 of its 81.8 kW recovered is the implied gasifier surplus (25.4 kW x 0.7), which exists only because the feed LHV of 20 MJ/kg puts more energy into the gas than the engine's temperature accounts for; it is a consequence of the LHV assumption, not independent heat.
The binding constraint is **energy, not temperature level**: the level mismatch is 0.0 kW in every default case, so the deficit is not a matter of the heat being too cold. The largest single lever is how much of the product-gas sensible heat
a real cooler recovers, followed by the flue-gas recovery (heat_only only) and the gas-cooler outlet temperature.
Do not show: a plant design. There is no burner efficiency (the supplementary fuel is gross), no ASU heat for S2, no losses (radiation, ducts), no start-up heat, no tar energy (tar is Missing), no condensation latent heat of the raw gas, no pumping or fan power
(`missing_terms` in the key lists them). The recovery fractions are Assumed and the heat-exchanger network is not designed: the matching only checks that a supply is hot enough. The numbers are a bound on the size of the problem, not a prediction.

## 7. What DOK-ING data would turn each Assumed constant into something Confirmed

| constant | datum that would settle it |
|---|---|
| recovery_flue, stack_temperature_c, excess_air_ratio | the stack / flue arrangement: is there a burner for the tail gas, a boiler or economiser behind it, what is the stack temperature and the excess air |
| recovery_gas_cooler, gas_cooler_outlet_c | the gas-cooler duty and outlet temperature: is the GC-004 water-spray quench the only cooling, or is there a dry waste-heat cooler upstream of it |
| recovery_wgs | whether the WGS reaction heat is used (HB-003 duty, steam generation) and at what level |
| the steam sink | what fuel the steam generator burns today and whether it is the tail gas |
| WGS feed reheat | PSA / WGS preheat arrangement (how the clean gas gets from 40 to 350 degC) |
| ash and carbon-black recovery | whether the GA-005 / GA-008 heat is used at all (small: 0.2 kW sensitivity) |

## 8. Persisted key count and the existing tests touched

`("PLANT", "HeatIntegration")` is one more persisted key (120 -> 121). It is registered through `register_ga001`, so the dynamics engine registers it too. The runtime's 90 % shrink guard
(`scripts/run_continuous_cycle.py` `check_shrink`) accepts the new set (tested). Existing tests edited deliberately, each only for the new key: `test_tail_gas_mode.py` and `test_carbon_bookkeeping.py` (`NEW_KEYS`),
and the pinned `120` -> `121` in `test_snapshot_deterministic.py`, `test_dynamics.py` (two places), `test_apply_provenance.py`, `test_apply_wording.py`. No assertion was weakened; the origin/main fixture comparison still covers every old entry.

## 9. Stage 2 (not built)

A `heat_integration_mode` switch (default = today) would be the natural form, as `tail_gas_mode` was. It would add a burner / boiler and let the supplementary fuel be a real stream, which changes every Plant Overview total that touches
hydrogen, fuel, flue gas and water: net H2 export (the hydrogen-equivalent column above is the size of the effect if hydrogen were the fuel), CO2 to the stack, the EU-007 flare's hard-coded `combustible_nm3_h = 0`, the plant mass balance (combustion air, flue gas) and
every energy-efficiency KPI. None of that is done here.
