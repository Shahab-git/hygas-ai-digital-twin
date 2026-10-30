# Mass and energy closure audit (step 1 of the validation plan)

Measured 2026-10-29 on `origin/main` c9d1847 (branch `balance-audit`). **Nothing was fixed, plugged or tuned**: no model equation, Confirmed
value, `SharedPlantState`, engine API, `run_continuous_cycle.py`, dynamics layer or workflow file changed. A residual here is a finding.
Offline throughout: the engine runs in-process against `tests/_fakes.py`, no database, no network, the real `secrets.toml` is never read,
`HYGAS_ALLOW_DB_WRITES` stays unset (the run made 0 database calls).

Reproduce: `python scripts/run_balance_audit.py` (about 1 minute; writes `outputs/balance/balance_audit.md` and `.csv`, git-ignored) and
`python scripts/run_balance_audit.py --write-baseline` (rewrites `docs/balance_audit_baseline.json`). Code: `python/balance_audit.py`
(pure functions), `python/balance_audit_inventory.py` (stream inventory; every `file:line` is checked by a test), `tests/test_balance_audit.py`.

## 1. Headline

- **H, O and N close to numerical precision** (relative residual below 5e-16) across GA-001 and across the whole gasification loop with the
  tail-gas recycle inside it, at the default inputs, at both ends of the ER range and for feed -30 % / +30 %, converged or not.
- **Carbon does not close.** The residual is +0.138 kg/h (0.69 % of the carbon entering GA-001, 0.82 % of the carbon entering the plant). It is
  exactly `(1 - 0.90) x (C_feed + C_recycle) - carbon_black`: the model sends 90 % of the carbon (recycled CO and CH4 carbon included) to the
  gas, the other 10 % has no stream, and the carbon-black stream is an independent 5 % of dry feed. Two Assumed constants that were never tied
  together.
- **Whole-plant total mass closes to 0.077 % of inflow, but that figure is flattering**: air (66 kg/h) and steam (86 kg/h) are 78 % of the 194 kg/h inflow. The
  residual of 0.148 kg/h is explained to 1e-14 kg/h (carbon 0.138, electrolyser water 0.013, water molar-mass basis -0.003).
- **GA-001 computes no heat duty** (temperature enters only the water-gas-shift constant). The duty the gasifier would need to reach 950 degC is
  **+22.8 kW (feed LHV 15 MJ/kg), -3.3 kW (17.5), -29.3 kW (20)**: it is close to thermoneutral and its sign flips inside DOK-ING's own Confirmed
  LHV range. Every 1 MJ/kg of feed LHV moves it by 10.4 kW, as much as the whole ER range (0.2125-0.2875) does (+4.9 to -11.3 kW at 17.5).
- **Whole-plant energy does not close, and cannot be closed with the terms the engine has.** At the midpoint LHV the balance says 64.9 kW must
  leave as heat; the engine reports 41.3 kW. The residual is **+23.7 kW = 16.5 % of the energy input** (-2.4 to +49.7 kW across 15-20 MJ/kg). The
  engine omits about 77 kW of heat rejection (WGS knock-out condensation 43.9, quench latent 20.8, electrolyser 5.8, shredder 6.3) and has **no
  term for the energy that raises about 81 kW of steam, air preheat and drying heat**. Both cannot be true without a heat input the engine lacks.
- **The "H2 conversion 52-69 %" is arithmetically right and incomplete**: H2 LHV (108.3 kW) over feed LHV only. With the 22.1 kW of electricity
  the plant uses it is 47-61 %; steam raising is not counted at all.

## 2. One-page summary (converged default state, 40 cycles; the five-cycle state differs by less than 0.5 % of each number)

| balance | residual | % of inflow | closed? | cause |
|---|---|---|---|---|
| GA-001 H, O, N (recycle = external feed) | < 1e-14 kg/h | < 4e-14 % | **Y, numerical precision** | closed by construction (`solve_product_gas`) |
| GA-001 ash | 0 | 0 | Y, by construction | the same 10 % constant on both sides (gasifier_mass_balance.py:61) |
| GA-001 carbon | +0.1380 kg/h | 0.686 % of C in | **N** | 0.90 conversion on feed + recycle carbon vs independent 5 % carbon black (ga001:303, gasifier_mass_balance.py:62) |
| GA-001 total mass | +0.1380 kg/h | 0.109 % | N (just above 0.1 %) | the carbon residual; tar, S, Cl, Ar Missing |
| loop H, O, N (recycle inside) | < 2e-14 kg/h | < 4e-14 % | **Y, numerical precision** | the one-cycle recycle lag is carried as an explicit inventory term |
| loop carbon | +0.1380 kg/h | 0.818 % of C in | **N** | same carbon identity |
| loop total mass | +0.1351 kg/h | 0.071 % | Y, stated tolerance (< 0.1 %) | carbon (0.138) and water basis (-0.003) |
| plant H | +1.485e-3 kg/h | 0.012 % | Y, stated tolerance | electrolyser water 1 L/Nm3 vs 0.80 stoichiometric (hb_remaining_chain.py:170) |
| plant O | +0.01179 kg/h | 0.011 % | Y, stated tolerance | same |
| plant N | -6e-15 kg/h | 1e-14 % | **Y, numerical precision** | - |
| plant total mass | +0.1484 kg/h | 0.077 % | Y, stated tolerance (incomplete: 6 Missing terms) | carbon 0.1380 + electrolyser 0.0133 + water basis -0.0029 |
| HB-013 H2 inventory (default 5-cycle state) | +0.133 kg created | 4.1 % of the cycle's inflow | **N** | clamp at 0 kg with lagged outflow (hb_wgs_psa_storage_chain.py:537); 0 in the converged state |
| GA-001 energy (implied heat duty) | +22.8 / -3.3 / -29.3 kW | +14.6 / -1.8 / -14.1 % of feed | cannot be evaluated | no duty in the engine; LHV uncertainty (+/-26 kW) dominates; tar, heat loss Missing |
| whole-plant energy | +23.7 kW (-2.4 .. +49.7) | 16.5 % (-2.0 .. 29.4) of input | **N** and incomplete | omitted heat rejection (77 kW) and no energy source for steam raising (81 kW demand) |

Verdict scale: closes to numerical precision (< 1e-6 relative) / closes to a stated tolerance (< 0.1 % of inflow, an audit choice, not a project
specification) / does not close / cannot be evaluated (a Missing term blocks the calculation).

## 3. How it was measured

- **States.** Cycle 1 (no recycle; GA-001 still uses the 41.67 kg/h placeholder), the engine's default five-cycle state, and a converged state
  (40 cycles; the tail-gas recycle contracts about 5x per cycle and is below 1e-9 by cycle 20). All through
  `tab1_integration.build_live_snapshot(n_cycles=N, overrides=...)`.
- **The recycle is lagged**, so a single snapshot does not contain the tail gas GA-001 used. The audit therefore takes the previous cycle's
  snapshot (`build_live_snapshot(n_cycles=N-1)`). Without it, and with the recycle active, the C/H/O rows are reported `cannot be evaluated`
  (never computed with the recycle set to zero). An independent check backs the carbon GA-001 must have seen out of its own published gas; it
  agrees with feed + recycle read from the previous cycle to 1e-16.
- **Control volumes.** (a) GA-001 alone, the recycle an external feed; (b) the gasification loop (GA-001, gas cleaning, WGS, PSA, HB-009), the
  recycle inside, so it is neither input nor output and only its one-cycle inventory in transit appears; (c) the whole plant, wet MSW in,
  H2 to storage out.
- **Inputs are independent of the model being checked**: feed atoms are re-derived from the mass fractions, air from the model's own formula
  on the recycle-augmented fuel, the gas from the published `GA-001 Outputs`, ash and carbon black from `gasifier_mass_balance`. Moles are
  primary; mass uses one atomic-mass table, except where the engine publishes kg (then as published).
- **Energy basis.** Lower heating value plus sensible heat above 25 degC with water vapour at 25 degC as zero (liquid water is -44.004 kJ/mol).
  Constants (named, standard): enthalpies of formation H2O(g) -241.826, H2O(l) -285.830, CO -110.525, CO2 -393.509, CH4 -74.873 kJ/mol
  (NIST-JANAF / CRC); derived LHV H2 241.826, CO 282.984, CH4 802.288, C 393.509 kJ/mol, which agree with the repo's own MJ/Nm3 table
  (eu_utilities_chp.py:165) to within 0.3 %. Heat capacities are the repo's (gc_gas_cleaning_chain.py:106, hb_wgs_psa_storage_chain.py:94).
  Registry temperatures: air 200 degC, steam 350 degC (GA-004), dryer 100 degC (FE-005), carbon black 180 degC (GA-008). Feed LHV is evaluated at
  DOK-ING's Confirmed 15 and 20 MJ/kg dry, the midpoint 17.5 (Assumed point), and 15.75 from the model composition (Estimated: midpoint of Dulong
  14.85 and Channiwala-Parikh 16.66). Solids cp 1.0 kJ/kg.K (range 0.8-1.4) is **Assumed**; there is none in the repo.
- **Status tags.** Calculated (read from the snapshot or derived by an identity), Estimated (correlations, mean cp), Assumed (compositions,
  ratios, temperatures not stated), Missing (listed, never zero). Measured does not occur: the snapshot has none.

## 4. Findings

### 4.1 Mass

**M1. Carbon (explained).** C in the gas is 0.90 of the total carbon (ga001_gasifier_model.py:303), applied after the recycled CO and CH4 carbon
is added to the fuel (:770-778), so 0.326 kg/h of recycled carbon is also cut by 10 %: gas-phase carbon cannot become solid carbon. Unconverted carbon
is `0.045 F + 0.1 C_recycle` = 2.013 kg/h; the carbon-black stream is `0.05 F` = 1.875 kg/h; the difference is +0.138. Without recycle (cycle 1, F = 41.67) the sign flips
(-0.208 kg/h, -1.11 %). A conversion of 0.889 would make the feed-only numbers agree: inside the stated 0.85-0.98 range, so neither constant is wrong on its own.
`explain_carbon_residual` reproduces the identity to 5e-15 kg/h.

**M2. `verify_atom_balance` tests H and O only** (ga001_gasifier_model.py:350: `ok` uses `h_check` and `o_check`). The carbon check is returned
in `detail` and never compared; nitrogen is not tested. The model's own guard therefore could not have seen M1.

**M3. Electrolyser water.** HB-011 draws 1 L water per Nm3 H2 (hb_remaining_chain.py:170,307); 2 H2O -> 2 H2 + O2 needs 0.804. The excess
(0.737 mol/h = 0.0133 kg/h) has no stream and the O2 is not published. This is all of the plant H and O residual (checked to 1e-13).

**M4. Water molar mass.** The engine converts water with 18.015 (ga001_gasifier_model.py:165); the atomic masses defined four lines above give
18.016. Wherever a water mass is the engine's published kg, the total differs from the mole-based mass by 5.5e-5: -0.0029 kg/h of the plant total.

**M5. H2 storage creates hydrogen.** HB-013 clamps the level to [0, 50] kg (hb_wgs_psa_storage_chain.py:537) while HB-018 dispenses
`min(72 kg/h, previous level)` and EU-006 draws lagged. The coupled lags oscillate; at the default five-cycle state the level would go to -0.133 kg and
is held at 0 (4.1 % of that cycle's inflow). In the converged state at 40 cycles the clamp is inactive. Storage is outside the plant balance (the boundary is H2 into storage); this is a separate check.

**M6. Cycle-1 bootstrap.** On cycle 1 GA-001 reads no FE-005 and uses the 41.67 kg/h WET figure as dry feed (ga001_gasifier_model.py:418-435), with no
residual moisture; it is replaced by 37.503 kg/h from cycle 2. Known and documented in the code; recorded here because it is the only state
where the carbon residual is negative.

**M7. FE-003 clipping.** A feed delivery above 50 kg/h is clipped and the surplus goes nowhere (fe_feed_handling.py:221-224). At +30 % the plant
accepts 50 kg/h (+20 %); 4.17 kg/h is reported separately as `clipped_surplus_kg_h`, outside the balance.

**M8. Masses that appear or leave with no stream** (live values, see appendix A3): WGS unreacted steam 56.7 kg/h (no condensate stream, unit or heat
rejection); quench-loop blowdowns 50 + 77 kg/h with no make-up; sulfur 0.029 kg/h and chlorine 0.024 kg/h removed by GC-008/GC-009 though the feed has none;
tar 0.046 kg/h removed by GC-006/GC-007 though GA-001 tar is Missing; fly ash 0.206 kg/h (GC-003's fixed 2 g/Nm3) not subtracted from the 10 % bottom ash;
HB-010's fixed 50 Nm3/h not deducted from the PSA feed.

**M9. Operation dependence (B3).** The H, O and N residuals stay below 5e-16 relative at ER 0.2125, 0.25, 0.2875 and feed -30 / +30 %. The carbon residual scales with
feed and ER (+0.097 kg/h at -30 %, +0.166 at +30 %, +0.131 / +0.145 kg/h at ER 0.2125 / 0.2875) and stays 0.65-0.72 % of carbon. A direct override of GA-001's dry feed
(+/-30 %) breaks the FE-005 -> GA-001 link by construction and shows up as a +/-11 kg/h plant residual; that is the sensitivity case, not a model fault.

### 4.2 Energy

**E1. GA-001 has no heat duty.** Searching its outputs and code: temperature is the registry value at ga001_gasifier_model.py:230, read at :746, passed at :787 (`T_C + 273.15`) and used
only in `_wgs_keq` (:314). The implied duty (section 2) is computed by the audit from the enthalpies above and marked `Calculated, not part of the engine`.
At the published composition the adiabatic temperature is 523 / 1011 / 1499 degC for 15 / 17.5 / 20 MJ/kg. Cold-gas efficiency is 0.82 / 0.73 / 0.66 including
the recycle, 0.75 / 0.64 / 0.56 net of it. Tar, heat loss through the 150 mm refractory, and feed / recycle temperatures are Missing.

**E2. Plant energy.** Midpoint LHV, kW: in 143.2 (feed 182.3, electricity 22.1, make-up and moisture water as liquid -61.2); known out 78.3 (H2 108.3,
carbon black 17.1, liquid condensate and knock-out water -49.3, small terms); the 64.9 kW difference must leave as heat. The engine reports 41.3 kW (GC-004 sensible
32.6 + compressor 8.7). EU-008's 52.0 kW demand additionally counts HB-003's 10.7 kW cold-side duty, which is heat recovered into feedwater, not rejected.
The heat the engine omits (Calculated / Estimated): condensing and cooling the unreacted WGS steam 43.9, the quench vapour and condensation that GC-004's own docstring says it
leaves out 20.8, electrolyser losses 5.8, shredder 6.3 = 76.7 kW. That exceeds the residual by 53 kW, which is only consistent with a heat input of that size that no engine term
supplies; the unsourced internal heat demand is 81 kW (raise WGS steam 61.4, gasifier steam 13.0, preheat air 3.4, dry feed 2.7), against the 10.7 kW the engine routes to feedwater.

**E3. Electricity.** EU-009 sums HB-012 8.7 + HB-011 6.0 + GC-013 fan 0.4 + EU-008 fan 0.75 = 15.8 kW. FE-004's 6.25 kW is computed by the engine and not included.
Registry nameplates in no sum: FE-003 0.37, FE-005 5, FE-007 5.5, FE-008 0.75, GA-005 1.1, GA-006 0.55, HB-009 blower 0.5 kW (13.8 kW rated, utilisation not stated). The fan is
hydraulic power only.

**E4. Electrolyser specific energy.** `HB011_SEC_RATED_KWH_PER_NM3 = 55` (hb_remaining_chain.py:169). The LHV of H2 is 3.0 kWh/Nm3, so 55 kWh/Nm3 is a 5.5 % efficient
electrolyser (88.7 kWh/Nm3 at the 60 % load used, 3.4 %). 55 kWh/kg is typical of PEM, so the registry unit is probably per kg. The engine turns 6.0 kW into 0.068 Nm3/h
(0.2 kW of H2). This also drives 5.8 kW of unrejected heat. Not fixed here.

**E5. Efficiencies.** `overall_efficiency` = 100 x H2 LHV(HB-012, 10.8 MJ/Nm3) / (FE-005 dry feed x 15..20 MJ/kg) = 52.0-69.4 %: re-derived exactly, and the
balance gives 52.0-69.3 % (H2 LHV differs 0.10 % between the EU-006 10.8 MJ/Nm3 and the derived 10.789). It leaves out electricity (47.0-60.7 % with it) and steam raising.
`h2_yield_per_feed_mass` = 0.0867 kg/kg dry is 55 % of the stoichiometric maximum 0.156 (complete steam reforming of the feed carbon). `major_losses` lists
`cooling_tower_heat_rejected_kw`, which already contains the quench and compressor entries, so summing the list double-counts.

### 4.3 Feedstock

The default composition is dry ash-free C/H/O/N = 0.50 / 0.06 / 0.43 / 0.01 (`_input_feedstock_composition`), **Assumed** / Literature, not DOK-ING data. The cross-check
passes all three tests (verbatim in the appendix). Two caveats the check does not show: it compares the ash-free 50 % carbon with the floor ">45 %", while on a dry-with-ash basis
carbon is exactly 45.0 % (at the floor, not above it; DOK-ING gave no basis); and it does not test LHV at all. The composition's own LHV estimate is 14.85-16.66 MJ/kg, at or just below the bottom of DOK-ING's 15-20.

## 5. What is Missing, and the DOK-ING question each becomes

| Missing term | affects | DOK-ING data that would supply it |
|---|---|---|
| Full ultimate and proximate analysis of the feed (C, H, O, N, S, Cl, ash, moisture basis) and the dry LHV as a point | feed energy +/-26 kW; every element row; S, Cl | One representative batch analysis, dry and as received, with the basis stated |
| Tar yield and heating value at 950 degC, ER 0.25 | C, H, O rows; energy | Measured tar loading (g/Nm3) at the GA-001 outlet and its heating value |
| Where the unconverted carbon goes (bed drain, cyclone catch, carbon black, fly ash) and each stream's carbon content | carbon row (+0.138 kg/h) | Mass flow and carbon content of GA-005, GA-006, GA-008 and cyclone catch at nominal load |
| Gasifier heat loss, feed and recycle temperatures, air preheat source | gasifier duty | Shell / refractory loss at 950 degC, feed temperature after the dryer, how the air is preheated |
| Steam: source and energy for 15 kg/h gasifier steam and 70.9 kg/h WGS steam; boiler fuel; feedwater make-up | plant energy (81 kW demand) | The steam raising and heat integration scheme (what feeds the boiler, trim fuel, heat recovered from where) |
| Destination, temperature and heat rejection of the WGS knock-out water; LTS outlet temperature | mass 56.7 kg/h, energy 43.9 kW | Condensate handling downstream of the shift reactors |
| Quench / scrubber water loops: make-up, blowdown destination, cooling-tower evaporation; GC-004 duty including latent heat | utility water, 20.8 kW | Water balance of GC-004..GC-009 and EU-008 at nominal load, measured cooling-water flow and temperature rise |
| Electrical utilisation of every motor and the PSA / valve / instrument-air loads | electricity 15.8 kW + 6.3 + up to 13.8 | Measured or rated duty cycle per drive |
| PSA product purity, recovery, tail-gas composition and temperature | H2 product 100 % assumption; vent heat | Commissioning data of HB-006..HB-009 |
| Fly ash / dust carry-over from GA-001 | ash row | Dust loading at the cyclone inlet, ash split between bed drain and fly ash |
| Electrolyser specific energy unit (kWh/Nm3 or kWh/kg), O2 vent, water consumption | 5.8 kW, 0.013 kg/h | Datasheet of HB-011 |
| Whether HB-010 (50 Nm3/h) and the LOHC branch take gas from the main flow | mass | Process flow diagram of the H2 section |
| Hydrogen dispensing demand profile | storage clamp | The expected FCEV fill schedule (HB-018) |
| Measured H2 production (kg/day) and any plant energy or mass meter data | whole validation | Any commissioning or pilot data (step 2 of the validation plan) |

## 6. Needs your decision

1. **Carbon bookkeeping.** Which Assumed constant governs: carbon conversion 0.90, or the 5 % carbon black (derived from GA-008's 1.88 kg/h at the old 37.5 kg/h)? And should the
   recycled CO / CH4 carbon be subject to the solid-carbon conversion at all? Both are structure decisions, not plugs; this audit does not make them.
2. **Electrolyser unit** (E4): ask DOK-ING, or keep the 55 kWh/Nm3 reading.
3. **Feed LHV.** The +/-26 kW LHV uncertainty swamps everything else in the energy balance; pin it (DOK-ING analysis) before building on the gasifier energy results.
4. Whether the H2 storage / dispensing lag oscillation (M5) is wanted for the hourly runtime, or only for the what-if tab.

## 7. Recommended next step and its cost

The task that was planned (energy balance and gasifier temperature) is justified, and this audit says how to stage it. Cost figures are engineering estimates (Estimated), not measured.

1. **Pin the feed first (no code, days of waiting).** The point LHV and a real ultimate analysis, because ER and temperature results cannot be read through +/-26 kW of feed energy. Ask the questions in section 5, rows 1-4.
2. **Add the gasifier energy balance as a separate, read-only engine key** (about 1 day with tests): publish exactly the implied duty `gasifier_energy` computes, tar and heat loss as Missing, with no feedback into GA-001. It makes the missing duty visible in Tab 1 without changing any number.
3. **Then couple temperature** (about 3-5 days and DOK-ING data): temperature-dependent carbon conversion and tar, closed against that duty, so the gasifier's thermal lag in `dynamics.py` stops being decorative.
4. **Steam raising and heat integration** (about 2 days, separate from 3): give HB-005 / GA-004 steam and the dryer an energy source and route the omitted rejections (43.9 + 20.8 kW) to EU-008 or to heat recovery; until then the plant energy balance cannot close.
5. **Optional, before 2 (half a day):** the carbon bookkeeping decision above plus extending `verify_atom_balance` to test carbon and nitrogen.

## 8. Not verified

- Python 3.11 and 3.12: the new code uses no syntax newer than 3.11 (checked with `ast.parse(..., feature_version=(3, 11))`), but only the local interpreter ran it; CI results need a push.
- The Cloud and the browser look: not relevant to this task.
- The standard enthalpies and the two LHV correlations are cited from memory of NIST-JANAF / CRC and Dulong / Channiwala-Parikh; they were not fetched. The test pins the derived LHVs against the repo's own table (0.3 %).
- Solids cp (1.0 kJ/kg.K), the 25 degC temperature of the feed and the recycle gas, the 220 degC entry of the knock-out water and the 40 degC knock-out / vent temperatures are Assumed; a +/-15 degC change in the knock-out or vent temperature moves the result by about 1 kW and 0.4 kW, and +/-20 degC at the knock-out entry by 0.7 kW.
- Tar, heat loss, S and Cl, argon are Missing, so every "closes" above is closure of the modelled terms only.

## Appendix: measured tables

Generated by `scripts/run_balance_audit.py` at the commit named in `docs/balance_audit_baseline.json`; regenerating on the same code gives the same numbers.

### A. Inventory

#### A1. GA-001 streams

| stream | dir | what the model uses | status | file:line | closed by construction? |
|---|---|---|---|---|---|
| dry feed rate | in | GA-001-INPUT dry_feed_rate_kg_h = FE-005 dry solids (37.503 kg/h at 41.67 wet); on cycle 1 the 41.67 kg/h placeholder (a WET figure used as dry) | Calculated (cycle 1: Assumed) | ga001_gasifier_model.py:384 | input |
| feed C/H/O/N (dry, ash-free: 0.50/0.06/0.43/0.01) | in | literature stand-in (Tchobanoglous et al.), cross-checked against DOK-ING floors only | Assumed | ga001_gasifier_model.py:193 | input |
| feed ash (10 % of dry feed) | in | ASH_FRACTION, GA-005 registry 'Ash discharge rate 10 % of feed' | Confirmed registry value (tag Assumed in the engine) | gasifier_mass_balance.py:61 | not used by the gas closure; carried by the byproduct module only |
| feed S, Cl, trace | in | no S/Cl in the composition; GC-008/GC-009 inlets are fixed 200 / 150 ppm | Missing | gc_gas_cleaning_chain.py:413 | no |
| residual moisture in the dry feed | in | FE-005 residual_water_kg_h (0.379 kg/h), read one cycle late, added to the steam pool | Calculated | ga001_gasifier_model.py:697 | Y (H, O) |
| gasifying air | in | not a stream: O2 = ER x (1 + x/4 - y/2) per mol C, N2 = O2 x 0.79/0.21 (no argon); ER 0.25 | Assumed (ER) | ga001_gasifier_model.py:301 | Y (O, N) |
| gasifier steam | in | steam_to_feed_ratio 0.4 kg/kg dry feed = 15.0 kg/h; GA-003 registry 15 kg/h at 37.5 kg/h | Assumed | ga001_gasifier_model.py:752 | Y (H, O) |
| oxygen-carrier (Fe2O3/Fe3O4) oxygen | in | NOT in the model: the circulation estimate is standalone and 'does NOT feed back into ga001_model()' | Missing (as a stream) | ga001_gasifier_model.py:962 | n/a |
| bed material / carrier inventory, make-up, attrition | in/out | not modelled | Missing | ga001_gasifier_model.py:962 | n/a |
| tail-gas recycle (HB-009 H2, CO, CH4) | in | previous cycle's tail gas atoms added to the fuel atoms; CO2 and N2 deliberately not recycled | Calculated | ga001_gasifier_model.py:660 | Y (H, O); C only at the 0.90 conversion |
| product gas, dry flow + composition (H2, CO, CO2, CH4, N2) | out | dry_flow_nm3_h and mol % from the WGS-equilibrium closure | Calculated | ga001_gasifier_model.py:793 | Y (H, O, N) |
| product gas, water | out | wet_flow_nm3_h and H2O_mol_pct_wet | Calculated | ga001_gasifier_model.py:795 | Y (H, O) |
| unconverted carbon / char | out | NOT a stream: (1 - 0.90) x total C simply does not appear in the gas (also applied to the recycled CO and CH4 carbon) | Assumed (0.90) | ga001_gasifier_model.py:303 | no stream |
| ash | out | 10 % of dry feed from the byproduct module, independent of the gas closure | Assumed | gasifier_mass_balance.py:65 | by an independent constant |
| carbon black | out | 5 % of dry feed from the byproduct module, independent of the 0.90 carbon conversion | Assumed | gasifier_mass_balance.py:62 | N (not tied to the gas closure) |
| tar | out | permanently Missing | Missing | ga001_gasifier_model.py:842 | N |
| fly ash / dust leaving with the gas | out | GC-001 Dust Missing; GC-003 inlet fixed 2 g/Nm3 | Missing | gc_gas_cleaning_chain.py:132 | N |

- solve_product_gas conserves H, O and N exactly by construction (ga001_gasifier_model.py:299-330). Carbon is conserved only on the gas side: 0.90 of the carbon (including the recycled carbon) goes to CO + CO2 + CH4 and the other 10 % has no stream.
- verify_atom_balance (ga001_gasifier_model.py:333) tests H and O only: `ok` uses h_check and o_check; the carbon check is returned in `detail` but never compared, and nitrogen is not tested at all.

#### A2. Every other unit

| unit | streams in | streams out | conserved? | file:line | note |
|---|---|---|---|---|---|
| FE-001 receiving hopper | MSW delivery 41.67 kg/h (Assumed) | same rate; hopper level | Y (pass-through) | fe_feed_handling.py:135 |  |
| FE-002 magnet / eddy current | FE-001 flow | same flow; tramp-metal reject Missing | partly | fe_feed_handling.py:194 | reject taken as negligible, not subtracted |
| FE-003 weighing conveyor | FE-002 flow | flow clipped to 29-50 kg/h | partly (N when clipped) | fe_feed_handling.py:215 | surplus mass above 50 kg/h goes nowhere |
| FE-004 shredder | FE-003 flow | same flow; 150 kWh/t electricity | Y (mass); electricity computed | fe_feed_handling.py:243 | power not summed in EU-009 |
| FE-005 dryer | wet feed (10 % water) | dry solids + 1 % residual water to GA-001; evaporated water 3.79 kg/h | Y (mass, explicit) | fe_feed_handling.py:275 | no dryer heat duty; evaporated water has no destination |
| FE-006 / FE-007 / FE-008 | FE-005 outlet | pass-through 37.88 kg/h | Y (pass-through) | fe_feed_handling.py:331 | GA-001 takes the dry mass and the water separately |
| GA-001 gasifier | see A1 | see A1 | H, O, N Y; C partly; ash by constant; energy N | ga001_gasifier_model.py:718 | no heat duty computed |
| GC-001 / GC-003 cyclones | GA-001 gas | same gas (copied) | Y (copy) | gc_gas_cleaning_chain.py:152 | dust: GC-001 Missing, GC-003 fixed 2 g/Nm3 and 95 % |
| GC-004 quench | GA-001 wet gas | dry gas + condensate (wet - dry) | Y (water, by construction) | gc_gas_cleaning_chain.py:256 | duty = sensible heat of the dry gas only |
| GC-005 quench water | - | blowdown 0.05 m3/h (fixed) | N | gc_gas_cleaning_chain.py:312 | no make-up stream, no circulation balance |
| GC-006 / GC-007 tar removal | tar 500 mg/Nm3 (fixed) | tar 50 mg/Nm3; blowdown | N | gc_gas_cleaning_chain.py:364 | not tied to GA-001 tar (Missing); removed tar goes nowhere |
| GC-008 H2S / GC-009 HCl scrubbers | 200 ppm / 150 ppm (fixed) | 1 ppm / 5 ppm; blowdowns | N | gc_gas_cleaning_chain.py:413 | S and Cl appear from nowhere |
| GC-010 bag filter / GC-012 carbon filter | fixed dust, H2S | fixed efficiencies | N | gc_gas_cleaning_chain.py:508 |  |
| GC-013 fan / GC-014 blower | gas | same gas; hydraulic power | Y (copy); power from dP | gc_gas_cleaning_chain.py:574 | dP and power are design values |
| GC-015 condensate tank | GC-004 condensate + blowdowns | total m3/h | N (a sum) | gc_gas_cleaning_chain.py:713 | adds process condensate to utility blowdowns |
| HB-001 / HB-004 WGS (HTS, LTS) | GC-013 gas + steam 4 x CO | CO -> CO2 + H2; unreacted steam | explicit (C and O, 1e-9) | hb_wgs_psa_storage_chain.py:275 | unreacted steam has no destination |
| HB-005 steam generator | CO mol/h x 4 | steam 70.9 kg/h | Y | hb_wgs_psa_storage_chain.py:177 | no fuel / heat input to raise it |
| HB-003 heat exchanger | gas 400 -> 220 degC; water 20 -> 150 degC | duties 7.4 / 10.7 kW | N (two-sided duties differ) | hb_wgs_psa_storage_chain.py:208 | reported, not forced equal |
| HB-006 / HB-009 PSA + tail gas | WGS gas | H2 product (taken as 100 % H2) + tail gas | Y (species split) | hb_wgs_psa_storage_chain.py:380 | purity 99.97 % not modelled |
| HB-010 membrane | constant 50 Nm3/h | separation Missing | N | hb_remaining_chain.py:339 | flow is a design constant, not taken from the PSA/WGS flow |
| HB-011 electrolyser | 10 kW x 0.6 availability; water 1 L/Nm3 | H2 0.068 Nm3/h | partly | hb_remaining_chain.py:279 | O2 not published; excess water; SEC 88.7 kWh/Nm3 |
| HB-012 compressor | PSA H2 | same H2; polytropic power | Y (pass-through) | hb_wgs_psa_storage_chain.py:452 | n = 1.3 Assumed |
| HB-013 H2 storage | PSA + electrolyser H2 | lagged dispensing + fuel cell; level | N when clamped | hb_wgs_psa_storage_chain.py:487 | clamp to [0, 50] kg creates / destroys H2 |
| HB-014..017 LOHC | - | - | Missing | hb_remaining_chain.py:605 | mass balances Missing |
| HB-018 dispensing | HB-013 level (lagged) | min(72 kg/h, level) | partly | hb_remaining_chain.py:981 | lagged, so it oscillates against HB-013 |
| EU-CHP dispatch / EU-002..006 | syngas budget (0 after WGS/PSA claim), H2 budget | electrical, thermal kW | partly (energy split explicit) | eu_utilities_chp.py:299 | CHP receives no syngas by design |
| EU-007 flare | tail gas CO2 + N2 | vented | Y | eu_utilities_chp.py:464 | 98 % destruction applies to 0 combustible |
| EU-008 cooling tower | GC-004 + HB-003 cold side + HB-012 | demand 52 kW | N (a sum, not a balance) | eu_utilities_chp.py:510 | HB-003 cold side is recovered, not rejected |
| EU-009 electrical metering | HB-012 + HB-011 + GC-013 fan + EU-008 fan | consumption kW | N (a sum) | eu_utilities_chp.py:733 | omits FE-004 and all other nameplate loads |
| EU-010 UPS | EU-009 net | state of charge | explicit (Coulomb counting) | eu_utilities_chp.py:775 |  |
| EU-011..013 heat recovery | EU-005 exhaust, EU-004 | kWth | Y (sums) | eu_utilities_chp.py:813 | zero while the CHP units idle |
| oxygen carrier (chemical looping) | - | - | n/a (standalone estimate) | ga001_gasifier_model.py:962 | no stream enters or leaves the balance |

#### A3. Mass or energy that appears or disappears without a stream (live values, converged state)

| item | value | unit | status | file:line | effect |
|---|---|---|---|---|---|
| ash leaving as bottom ash (10 % of dry feed) | 3.7503 | kg/h | Assumed | gasifier_mass_balance.py:61 | carries no C/H/O/N; closed by an independent constant |
| fly ash implied by GC-003's fixed 2 g/Nm3 inlet | 0.2055 | kg/h | Assumed | gc_gas_cleaning_chain.py:206 | not subtracted from the 10 % bottom ash |
| carbon black (5 % of dry feed) | 1.8752 | kg/h | Assumed | gasifier_mass_balance.py:62 | not tied to the unconverted carbon |
| tar mass removed by GC-006/GC-007 (500 -> 50 mg/Nm3) | 0.0462 | kg/h | Assumed | gc_gas_cleaning_chain.py:364 | tar that GA-001 does not produce (Missing) is removed here |
| H2S entering GC-008 (200 ppm of the dry gas), as sulfur | 0.0294 | kg S/h | Assumed | gc_gas_cleaning_chain.py:413 | no sulfur in the feed composition: S appears from nowhere |
| HCl entering GC-009 (150 ppm of the dry gas), as chlorine | 0.0244 | kg Cl/h | Assumed | gc_gas_cleaning_chain.py:463 | no chlorine in the feed composition |
| quench-loop blowdown GC-005 (fixed 0.05 m3/h) | 50.0000 | kg/h | Assumed | gc_gas_cleaning_chain.py:312 | leaves with no make-up stream |
| GC-007/008/009 blowdowns (scaled to gas flow) | 77.0646 | kg/h | Assumed | gc_gas_cleaning_chain.py:389 | no make-up stream |
| WGS unreacted steam knocked out | 56.6966 | kg/h | Calculated | hb_wgs_psa_storage_chain.py:270 | no condensate stream, no unit, no heat rejection |
| WGS steam raised (HB-005) | 70.8966 | kg/h | Calculated | hb_wgs_psa_storage_chain.py:189 | feedwater source and boiler energy not modelled |
| gasifier steam (GA-003 / GA-004) | 15.0012 | kg/h | Assumed | ga001_gasifier_model.py:752 | source and energy of this steam not modelled |
| dryer vapour (FE-005) | 3.7882 | kg/h | Calculated | fe_feed_handling.py:291 | no destination, no heat duty |
| tail-gas CO2 + N2 vented | 105.3691 | kg/h | Calculated | eu_utilities_chp.py:485 | a real exit stream (EU-007) |
| HB-013 clamp at 0 kg (storage would go negative) | - | kg per cycle | Calculated | hb_wgs_psa_storage_chain.py:537 | creates H2; see storage_inventory_check |
| HB-010 membrane feed (constant, not taken from the plant flow) | 50.0000 | Nm3/h | Assumed | hb_remaining_chain.py:182 | not deducted from the PSA/WGS gas |
| FE-004 shredder electricity not in EU-009 | 6.2505 | kW | Calculated | fe_feed_handling.py:243 | electrical load missing from the plant sum |
| registry nameplate loads in no sum (FE-003 .37, FE-005 5, FE-007 5.5, FE-008 .75, GA-005 1.1, GA-006 .55, HB-009 .5) | 13.7700 | kW rated | Confirmed nameplate | equipment_registry.json | utilisation not stated |
| EU-008 'cooling demand' counts HB-003 cold side as a cooling load | 10.7168 | kW | Calculated | eu_utilities_chp.py:520 | heat that is recovered to the feedwater, not rejected |
| GC-004 duty omits condensation latent heat | - | kW | Calculated | gc_gas_cleaning_chain.py:282 | see plant_energy candidates |

Hard-coded efficiencies, losses and constants:

| what | value | file:line | effect |
|---|---|---|---|
| carbon conversion efficiency | 0.90 (range 0.85-0.98), Assumed | ga001_gasifier_model.py:217 | sets the unconverted carbon; independent of temperature |
| CH4 carbon fraction | 0.05, Assumed | ga001_gasifier_model.py:224 | CH4 is not an equilibrium result |
| ash fraction | 0.10 of dry feed, Confirmed registry value | gasifier_mass_balance.py:61 | a constant, not tied to the composition |
| carbon-black fraction | 0.05 of dry feed | gasifier_mass_balance.py:62 | not tied to the 0.90 conversion |
| gasifier operating temperature | 950 degC, registry value | ga001_gasifier_model.py:230 | enters only the WGS Keq |
| steam-to-CO ratio in the WGS | 4.0 mol/mol | hb_wgs_psa_storage_chain.py:98 | sets the steam raised and the water knocked out |
| quench inlet / outlet temperature | 860 / 65 degC | gc_gas_cleaning_chain.py:295 | duty excludes latent heat |
| mean heat capacities | H2 29.3, CO 30.5, CO2 46.5, CH4 55.0, N2 30.6, H2O 37.5 J/mol.K | gc_gas_cleaning_chain.py:106 | one mean over 300-1200 K for every temperature |
| compressor polytropic exponent | 1.3, Assumed | hb_wgs_psa_storage_chain.py:122 | sets 8.7 kW |
| PSA product purity | 100 % H2 (design target 99.97 %) | hb_wgs_psa_storage_chain.py:384 | impurities ignored |
| electrolyser SEC and balance of plant | 55 kWh/Nm3 H2 rated, BoP 8 % | hb_remaining_chain.py:169 | LHV of H2 is 3.0 kWh/Nm3: this is 5.5 % efficient (unit suspect) |
| flare destruction efficiency | 0.98 | eu_utilities_chp.py:177 | applied to zero combustible |
| UPS round-trip efficiency | 0.94 | eu_utilities_chp.py:207 | charge side only |
| WGS/PSA claim on syngas | 1.0 | eu_utilities_chp.py:231 | CHP fuel budget is 0 |
| gas-train fan power | hydraulic power only (efficiency not applied) | gc_gas_cleaning_chain.py:594 | lower bound of electrical load |
| heat loss from any vessel or pipe | none anywhere | ga001_gasifier_model.py:718 | no heat-loss term exists in the repo |

#### A4. Feedstock composition

Default composition (`_input_feedstock_composition`, ga001_gasifier_model.py:549): dry ash-free mass fractions C/H/O/N = {'C': 0.5, 'H': 0.06, 'O': 0.43, 'N': 0.01} -- status **Assumed**, validation basis `Literature` (literature stand-in, not DOK-ING data).

`feedstock_composition_dokink_cross_check()` output, verbatim:

```json
{
 "carbon": {
  "value_pct": 50.0,
  "constraint": ">45%",
  "pass": true
 },
 "hydrogen": {
  "value_pct": 6.0,
  "constraint": ">5%",
  "pass": true
 },
 "ash": {
  "value_pct": 10.0,
  "constraint": "[5-15]%",
  "pass": true
 },
 "all_pass": true
}
```

`design_basis.get_feedstock_composition_ranges()` (DOK-ING Confirmed, RFI #2), verbatim:

```json
{
 "moisture_pct": [
  5.0,
  15.0
 ],
 "ash_pct": [
  5.0,
  15.0
 ],
 "volatile_matter_pct_min": 65.0,
 "carbon_pct_min": 45.0,
 "hydrogen_pct_min": 5.0,
 "lhv_mj_per_kg": [
  15.0,
  20.0
 ],
 "basis_note": "DOK-ING's own answer states LHV explicitly as dry basis; moisture/ash/VM are conventional proximate-analysis percentages (typically as-received for moisture, dry basis for ash/VM); carbon/hydrogen are given as bare percentage floors with no basis stated and no oxygen/nitrogen figures at all -- NOT a complete proximate/ultimate analysis, a real, stated limitation, not resolved here."
}
```

Agreement with DOK-ING's stated figures:

| DOK-ING stated | this model | agrees? | comment |
|---|---|---|---|
| moisture about 10 % (5-15 %) | FE-005 inlet 10 %, outlet 1 % | yes | moisture is not part of the composition; handled by FE-005 |
| ash about 10 % dry (5-15 %) | 10.0 % of dry feed | yes | Confirmed registry constant (GA-005) |
| carbon at least 45 % | 45.0 % of the dry feed incl. ash (50 % of the ash-free fuel) | marginal | the cross-check compares the ASH-FREE 50 % with the floor; on a dry-with-ash basis C is exactly 45.0 %, at the floor, not above it. DOK-ING gave no basis |
| hydrogen at least 5 % | 5.4 % of the dry feed incl. ash (6 % ash-free) | yes | passes on both bases |
| dry LHV 15-20 MJ/kg | 14.85-16.66 MJ/kg (Dulong / Channiwala-Parikh from this composition, Estimated) | borderline | the Dulong estimate sits just below 15; the cross-check function does not test LHV at all |
| oxygen, nitrogen | O 43 %, N 1 % of the ash-free fuel | cannot be checked | DOK-ING gave neither |

LHV estimate detail:
```json
{
 "dry_wt_pct": {
  "C": 45.0,
  "H": 5.4,
  "O": 38.7,
  "N": 0.9000000000000001,
  "ash": 10.0
 },
 "HHV_channiwala_parikh_MJ_kg": 17.84615,
 "HHV_dulong_MJ_kg": 16.0351875,
 "LHV_channiwala_parikh_MJ_kg": 16.659031265611993,
 "LHV_dulong_MJ_kg": 14.84806876561199,
 "range_MJ_kg": [
  14.84806876561199,
  16.659031265611993
 ],
 "status": "Estimated"
}
```

### B. Mass balances

Verdicts: closes to numerical precision (< 1e-6 relative) / closes to a stated tolerance (< 0.1 % of inflow) / does not close / cannot be evaluated (Missing term). A row flagged with Missing terms is INCOMPLETE even when the modelled terms close: the listed terms are never treated as zero.

#### B1/B2. Default inputs, converged (40 cycles)

| control volume | quantity | in kg/h | out kg/h | residual kg/h | % of inflow | verdict | Missing terms listed |
|---|---|---|---|---|---|---|---|
| GA-001 (recycle = external feed) | C | 20.1319 | 19.9939 | +1.3804e-01 | +0.6857 | does not close | tar |
| GA-001 (recycle = external feed) | H | 4.9256 | 4.9256 | +1.8335e-15 | +3.722e-14 | closes to numerical precision (< 1e-6 relative) | tar |
| GA-001 (recycle = external feed) | O | 46.6595 | 46.6595 | +7.2760e-15 | +1.559e-14 | closes to numerical precision (< 1e-6 relative) | tar |
| GA-001 (recycle = external feed) | N | 50.9101 | 50.9101 | -6.3696e-15 | -1.251e-14 | closes to numerical precision (< 1e-6 relative) | - |
| GA-001 (recycle = external feed) | ash | 3.7503 | 3.7503 | +0.0000e+00 | +0 | closes to numerical precision (< 1e-6 relative) | - |
| GA-001 (recycle = external feed) | mass | 126.3774 | 126.2393 | +1.3804e-01 | +0.1092 | does not close | tar; sulfur, chlorine, argon and trace species |
| gasification loop (recycle INSIDE) | C | 16.8764 | 16.7383 | +1.3804e-01 | +0.818 | does not close | tar; PSA product impurities (purity 99.97 % taken as 100 %) |
| gasification loop (recycle INSIDE) | H | 11.6801 | 11.6801 | +1.8335e-15 | +1.57e-14 | closes to numerical precision (< 1e-6 relative) | tar; PSA product impurities (purity 99.97 % taken as 100 %) |
| gasification loop (recycle INSIDE) | O | 106.4962 | 106.4962 | +1.4552e-14 | +1.366e-14 | closes to numerical precision (< 1e-6 relative) | tar; PSA product impurities (purity 99.97 % taken as 100 %) |
| gasification loop (recycle INSIDE) | N | 50.9101 | 50.9101 | -6.3696e-15 | -1.251e-14 | closes to numerical precision (< 1e-6 relative) | PSA product impurities (purity 99.97 % taken as 100 %) |
| gasification loop (recycle INSIDE) | ash | 3.7503 | 3.7503 | +0.0000e+00 | +0 | closes to numerical precision (< 1e-6 relative) | - |
| gasification loop (recycle INSIDE) | mass | 189.7091 | 189.5740 | +1.3514e-01 | +0.07124 | closes to a stated tolerance (< 0.1 % of inflow) | tar; dust / fly ash, S and Cl species, argon; quench / scrubber / cooling-tower water loops (make-up, blowdown, evaporation); PSA product impurities (purity 99.97 % taken as 100 %); FE-002 tramp metal reject; membrane (HB-010) and LOHC (HB-014..017) branches |
| whole plant (wet MSW in, H2 out) | C | 16.8764 | 16.7383 | +1.3804e-01 | +0.818 | does not close | tar; PSA product impurities (purity 99.97 % taken as 100 %) |
| whole plant (wet MSW in, H2 out) | H | 12.1116 | 12.1101 | +1.4851e-03 | +0.01226 | closes to a stated tolerance (< 0.1 % of inflow) | tar; PSA product impurities (purity 99.97 % taken as 100 %) |
| whole plant (wet MSW in, H2 out) | O | 109.9208 | 109.9090 | +1.1786e-02 | +0.01072 | closes to a stated tolerance (< 0.1 % of inflow) | tar; PSA product impurities (purity 99.97 % taken as 100 %) |
| whole plant (wet MSW in, H2 out) | N | 50.9101 | 50.9101 | -6.3696e-15 | -1.251e-14 | closes to numerical precision (< 1e-6 relative) | PSA product impurities (purity 99.97 % taken as 100 %) |
| whole plant (wet MSW in, H2 out) | ash | 3.7503 | 3.7503 | +0.0000e+00 | +0 | closes to numerical precision (< 1e-6 relative) | - |
| whole plant (wet MSW in, H2 out) | mass | 193.5649 | 193.4165 | +1.4839e-01 | +0.07666 | closes to a stated tolerance (< 0.1 % of inflow) | tar; dust / fly ash, S and Cl species, argon; quench / scrubber / cooling-tower water loops (make-up, blowdown, evaporation); PSA product impurities (purity 99.97 % taken as 100 %); FE-002 tramp metal reject; membrane (HB-010) and LOHC (HB-014..017) branches |

Carbon detail (GA-001): total C 20.1319 kg/h; in the gas 18.1187; not in the gas 2.0132 (= (1-0.90) x total C, of which 0.3256 is recycled CO/CH4 carbon); carbon-black stream 1.8751; **unassigned carbon +0.1380 kg/h**. Recycle cross-check (carbon implied by the published gas vs feed + recycle read): relative difference -1.36e-16.
HB-013 storage this cycle: level 0.0000 -> 1.7988 kg, inflow 3.2571, outflow 1.4583; expected without the clamp +1.7988; **H2 created (+) / destroyed (-) by the clamp: +0.0000 kg** (0.00 % of the cycle's inflow) -- closes to numerical precision (< 1e-6 relative). FE-003 clipped surplus: 0.000 kg/h.

#### B1/B2. Default inputs, default five-cycle state

| control volume | quantity | in kg/h | out kg/h | residual kg/h | % of inflow | verdict | Missing terms listed |
|---|---|---|---|---|---|---|---|
| GA-001 (recycle = external feed) | C | 20.1286 | 19.9909 | +1.3771e-01 | +0.6842 | does not close | tar |
| GA-001 (recycle = external feed) | H | 4.9245 | 4.9245 | +9.1677e-16 | +1.862e-14 | closes to numerical precision (< 1e-6 relative) | tar |
| GA-001 (recycle = external feed) | O | 46.6526 | 46.6526 | +7.2760e-15 | +1.56e-14 | closes to numerical precision (< 1e-6 relative) | tar |
| GA-001 (recycle = external feed) | N | 50.8986 | 50.8986 | -6.3696e-15 | -1.251e-14 | closes to numerical precision (< 1e-6 relative) | - |
| GA-001 (recycle = external feed) | ash | 3.7503 | 3.7503 | +0.0000e+00 | +0 | closes to numerical precision (< 1e-6 relative) | - |
| GA-001 (recycle = external feed) | mass | 126.3546 | 126.2169 | +1.3771e-01 | +0.109 | does not close | tar; sulfur, chlorine, argon and trace species |
| gasification loop (recycle INSIDE) | C | 16.8764 | 16.7386 | +1.3771e-01 | +0.816 | does not close | tar; PSA product impurities (purity 99.97 % taken as 100 %) |
| gasification loop (recycle INSIDE) | H | 11.6785 | 11.6785 | +1.8335e-15 | +1.57e-14 | closes to numerical precision (< 1e-6 relative) | tar; PSA product impurities (purity 99.97 % taken as 100 %) |
| gasification loop (recycle INSIDE) | O | 106.4801 | 106.4801 | +0.0000e+00 | +0 | closes to numerical precision (< 1e-6 relative) | tar; PSA product impurities (purity 99.97 % taken as 100 %) |
| gasification loop (recycle INSIDE) | N | 50.8986 | 50.8986 | -1.9109e-14 | -3.754e-14 | closes to numerical precision (< 1e-6 relative) | PSA product impurities (purity 99.97 % taken as 100 %) |
| gasification loop (recycle INSIDE) | ash | 3.7503 | 3.7503 | +0.0000e+00 | +0 | closes to numerical precision (< 1e-6 relative) | - |
| gasification loop (recycle INSIDE) | mass | 189.6798 | 189.5450 | +1.3481e-01 | +0.07107 | closes to a stated tolerance (< 0.1 % of inflow) | tar; dust / fly ash, S and Cl species, argon; quench / scrubber / cooling-tower water loops (make-up, blowdown, evaporation); PSA product impurities (purity 99.97 % taken as 100 %); FE-002 tramp metal reject; membrane (HB-010) and LOHC (HB-014..017) branches |
| whole plant (wet MSW in, H2 out) | C | 16.8764 | 16.7386 | +1.3771e-01 | +0.816 | does not close | tar; PSA product impurities (purity 99.97 % taken as 100 %) |
| whole plant (wet MSW in, H2 out) | H | 12.1100 | 12.1085 | +1.4851e-03 | +0.01226 | closes to a stated tolerance (< 0.1 % of inflow) | tar; PSA product impurities (purity 99.97 % taken as 100 %) |
| whole plant (wet MSW in, H2 out) | O | 109.9046 | 109.8928 | +1.1786e-02 | +0.01072 | closes to a stated tolerance (< 0.1 % of inflow) | tar; PSA product impurities (purity 99.97 % taken as 100 %) |
| whole plant (wet MSW in, H2 out) | N | 50.8986 | 50.8986 | -1.9109e-14 | -3.754e-14 | closes to numerical precision (< 1e-6 relative) | PSA product impurities (purity 99.97 % taken as 100 %) |
| whole plant (wet MSW in, H2 out) | ash | 3.7503 | 3.7503 | +0.0000e+00 | +0 | closes to numerical precision (< 1e-6 relative) | - |
| whole plant (wet MSW in, H2 out) | mass | 193.5356 | 193.3876 | +1.4806e-01 | +0.0765 | closes to a stated tolerance (< 0.1 % of inflow) | tar; dust / fly ash, S and Cl species, argon; quench / scrubber / cooling-tower water loops (make-up, blowdown, evaporation); PSA product impurities (purity 99.97 % taken as 100 %); FE-002 tramp metal reject; membrane (HB-010) and LOHC (HB-014..017) branches |

Carbon detail (GA-001): total C 20.1286 kg/h; in the gas 18.1158; not in the gas 2.0129 (= (1-0.90) x total C, of which 0.3252 is recycled CO/CH4 carbon); carbon-black stream 1.8751; **unassigned carbon +0.1377 kg/h**. Recycle cross-check (carbon implied by the published gas vs feed + recycle read): relative difference 0.00e+00.
HB-013 storage this cycle: level 2.1090 -> 0.0000 kg, inflow 3.2562, outflow 5.4980; expected without the clamp -0.1327; **H2 created (+) / destroyed (-) by the clamp: +0.1327 kg** (4.08 % of the cycle's inflow) -- does not close. FE-003 clipped surplus: 0.000 kg/h.

#### Terms of the converged default balances

**GA-001 (recycle external):**

| dir | term | status | mass kg/h | source |
|---|---|---|---|---|
| in | dry feed (C,H,O,N + ash) | Assumed | 37.50300 | GA-001-INPUT dry_feed_rate_kg_h (Calculated, FE-005) x feedstock_composition (Assumed, ga001:193-196); ash 10 % (gasifier_mass_balance.py:61, GA-005) |
| in | residual moisture in dry feed | Calculated | 0.37884 | FE-005 MoistureBalance.residual_water_kg_h (fe_feed_handling.py:290), folded in at ga001:761-763 |
| in | air O2 | Calculated | 15.35613 | ER x stoichiometric O2 on the recycle-augmented fuel (ga001:299-300, :776-778); ER Assumed 0.25 |
| in | air N2 | Calculated | 50.57254 | O2 x 0.79/0.21 (ga001:301); argon and CO2 in air ignored by the model |
| in | gasifier steam | Assumed | 15.00203 | steam_to_feed_ratio 0.4 kg/kg (Assumed, ga001:458-480) x dry feed; GA-003 registry 15 kg/h |
| in | tail-gas recycle (HB-009) | Calculated | 7.56482 | previous cycle's HB-009 tail gas (H2, CO, CH4; CO2 and N2 are not recycled, ga001_gasifier_model.py:654-657) |
| out | product gas (wet) | Calculated | 120.61388 | GA-001 Outputs dry_flow_nm3_h x mol% and (wet - dry) water (ga001:793-803) |
| out | ash | Assumed | 3.75030 | ASH_FRACTION x dry feed, gasifier_mass_balance.py:65-71 (GA-005 'Ash discharge rate 10 % of feed') |
| out | carbon black (taken as pure C) | Assumed | 1.87515 | CARBON_BLACK_FRACTION 5 % x dry feed (gasifier_mass_balance.py:62, derived from GA-008 1.88 kg/h / 37.5 kg/h); pure carbon is an audit assumption (GA-008 'product ash < 1 wt%') |
| out | tar | Missing | MISSING | GA-001 'Tar content' is permanently Missing (ga001_gasifier_model.py:842-857) |
| out | sulfur, chlorine, argon and trace species | Missing | MISSING | no S/Cl/Ar in the feed composition (ga001:193-196); GC-008/GC-009 inlets are fixed ppm (Assumed), not tied to the feed |

**Whole plant:**

| dir | term | status | mass kg/h | source |
|---|---|---|---|---|
| in | MSW dry solids (FE-005 outlet) | Assumed | 37.50300 | FE-003 confirmed wet feed x (1 - 10 % moisture) (fe_feed_handling.py:288); composition Assumed (ga001:193-196) |
| in | MSW moisture (10 % of wet feed) | Calculated | 4.16700 | FE-003 wet feed - FE-005 dry solids (fe_feed_handling.py:288); 10 % is FE-005's design inlet moisture |
| out | dryer vapour (FE-005) | Calculated | 3.78818 | FE-005 water_evaporated_kg_h (fe_feed_handling.py:291) |
| in | air O2 | Calculated | 15.35613 | ER x stoichiometric O2 on the recycle-augmented fuel (ga001:299-300, :776-778); ER Assumed 0.25 |
| in | air N2 | Calculated | 50.57254 | O2 x 0.79/0.21 (ga001:301); argon and CO2 in air ignored by the model |
| in | gasifier steam | Assumed | 15.00203 | steam_to_feed_ratio 0.4 kg/kg (Assumed, ga001:458-480) x dry feed; GA-003 registry 15 kg/h |
| in | WGS steam (HB-005) | Calculated | 70.89656 | HB-005 Steam.steam_kg_h = 4 x CO mol/h (hb_wgs_psa_storage_chain.py:187-189) |
| in | electrolyser feed water (HB-011) | Calculated | 0.06762 | HB-011 water_l_h (hb_remaining_chain.py:307), 1 kg/L assumed |
| out | electrolyser H2 (HB-011) | Calculated | 0.00608 | HB-011 h2_kg_h |
| out | electrolyser O2 (stoichiometric, not published) | Calculated | 0.04827 | audit: 2 H2O -> 2 H2 + O2; the engine publishes no O2 stream |
| out | ash | Assumed | 3.75030 | ASH_FRACTION x dry feed, gasifier_mass_balance.py:65-71 (GA-005 'Ash discharge rate 10 % of feed') |
| out | carbon black (taken as pure C) | Assumed | 1.87515 | CARBON_BLACK_FRACTION 5 % x dry feed (gasifier_mass_balance.py:62, derived from GA-008 1.88 kg/h / 37.5 kg/h); pure carbon is an audit assumption (GA-008 'product ash < 1 wt%') |
| out | quench condensate (GC-004) | Calculated | 18.62577 | GC-004 'Condensed water' m3/h x 1000 kg/m3 (gc_gas_cleaning_chain.py:265-268) |
| out | WGS unreacted steam (knocked out, no equipment) | Calculated | 56.69972 | WGS Composition.H2O x GC-013 dry flow (hb_wgs_psa_storage_chain.py:262-270) |
| out | tail-gas CO2 + N2 to flare/vent (HB-009 -> EU-007) | Calculated | 105.37202 | HB-009 TailGas.species_nm3_h; EU-007 inert_in (eu_utilities_chp.py:485) |
| out | H2 product to storage (HB-012) | Calculated | 3.25102 | HB-012 h2_kg_h (hb_wgs_psa_storage_chain.py:467); PSA product taken as 100 % H2 (HB-009 docstring) |
| out | recycle inventory in transit (lag) | Calculated | 0.00000 | HB-009 tail gas this cycle - tail gas GA-001 read (lagged, ga001:660-694); zero when the loop has converged |
| out | tar | Missing | MISSING | GA-001 'Tar content' Missing (ga001_gasifier_model.py:842-857) |
| out | dust / fly ash, S and Cl species, argon | Missing | MISSING | GC-001 Dust Missing; GC-003 2 g/Nm3 and GC-008/009 ppm are fixed registry values, not tied to the feed |
| out | quench / scrubber / cooling-tower water loops (make-up, blowdown, evaporation) | Missing | MISSING | GC-005/007/008/009 blowdowns (Assumed m3/h) have no make-up stream; EU-008 evaporation not modelled |
| out | PSA product impurities (purity 99.97 % taken as 100 %) | Missing | MISSING | HB-006 purity is a design target only (tab1_integration.py:159-165) |
| out | FE-002 tramp metal reject | Missing | MISSING | FE-002 TrampMetalReject Missing (fe_feed_handling.py:194) |
| out | membrane (HB-010) and LOHC (HB-014..017) branches | Missing | MISSING | HB-010 separation, HB-014/016/017 mass balances and HB-015 inventory are Missing |

#### B3. Does the residual depend on operation? (converged state, then five-cycle state)

| case | cycles | GA-001 C residual kg/h (% of C in) | GA H rel | GA O rel | GA N rel | loop mass residual kg/h | plant mass residual kg/h (%) | H2 created by storage clamp kg |
|---|---|---|---|---|---|---|---|---|
| default | 40 | +0.1380 (+0.69 %) | 3.7e-16 | 1.6e-16 | -1.3e-16 | +0.1351 | +0.1484 (+0.077 %) | +0.000 |
| default | 5 | +0.1377 (+0.68 %) | 1.9e-16 | 1.6e-16 | -1.3e-16 | +0.1348 | +0.1481 (+0.077 %) | +0.133 |
| ER 0.2125 | 40 | +0.1305 (+0.65 %) | -1.8e-16 | -1.6e-16 | -1.5e-16 | +0.1273 | +0.1405 (+0.075 %) | +0.000 |
| ER 0.2125 | 5 | +0.1301 (+0.65 %) | 0.0e+00 | 1.6e-16 | -2.9e-16 | +0.1269 | +0.1402 (+0.075 %) | +0.025 |
| ER 0.2875 | 40 | +0.1450 (+0.72 %) | 1.9e-16 | 0.0e+00 | 0.0e+00 | +0.1424 | +0.1556 (+0.078 %) | +0.000 |
| ER 0.2875 | 5 | +0.1447 (+0.72 %) | 1.9e-16 | 0.0e+00 | -4.4e-16 | +0.1421 | +0.1553 (+0.078 %) | +0.232 |
| feed -30 % at FE-001 | 40 | +0.0966 (+0.69 %) | -1.3e-16 | 0.0e+00 | 1.8e-16 | +0.0946 | +0.1079 (+0.080 %) | +0.000 |
| feed -30 % at FE-001 | 5 | +0.0972 (+0.69 %) | 1.3e-16 | 1.1e-16 | -1.8e-16 | +0.0951 | +0.1084 (+0.080 %) | +0.754 |
| feed +30 % at FE-001 (FE-003 clips to 50 kg/h = +20 %) | 40 | +0.1656 (+0.69 %) | 1.6e-16 | 2.6e-16 | 0.0e+00 | +0.1622 | +0.1754 (+0.076 %) | +0.000 |
| feed +30 % at FE-001 (FE-003 clips to 50 kg/h = +20 %) | 5 | +0.1647 (+0.68 %) | 1.6e-16 | 0.0e+00 | 2.1e-16 | +0.1613 | +0.1745 (+0.075 %) | +0.000 |
| dry feed -30 % at GA-001 | 40 | +0.0967 (+0.69 %) | 1.3e-16 | -2.2e-16 | -1.8e-16 | +0.0947 | +11.3588 (+7.678 %) | +0.000 |
| dry feed -30 % at GA-001 | 5 | +0.0963 (+0.68 %) | 0.0e+00 | 1.1e-16 | -1.8e-16 | +0.0943 | +11.3584 (+7.680 %) | +0.125 |
| dry feed +30 % at GA-001 | 40 | +0.1794 (+0.69 %) | 1.4e-16 | -1.2e-16 | 1.9e-16 | +0.1756 | -11.0620 (-4.625 %) | +0.000 |
| dry feed +30 % at GA-001 | 5 | +0.1786 (+0.68 %) | 2.9e-16 | 0.0e+00 | -3.9e-16 | +0.1749 | -11.0628 (-4.626 %) | +0.000 |

### C. Energy balances (kW; converged default state)

Basis: lower heating value + sensible heat above 25 degC, water VAPOUR at 25 degC = 0 (so liquid water is -44.0 kJ/mol). Constants: standard enthalpies of formation H2O(g) -241.826, H2O(l) -285.830, CO -110.525, CO2 -393.509, CH4 -74.873 kJ/mol (NIST-JANAF/CRC); the repo's own mean cp (gc_gas_cleaning_chain.py:106) and liquid-water cp (hb_wgs_psa_storage_chain.py:94). Feed LHV is evaluated at DOK-ING's Confirmed 15-20 MJ/kg dry (ends and midpoint) and at the model composition's own correlation estimate.

#### C2. GA-001 energy (GA-001 computes NO heat duty: temperature enters only the WGS Keq, ga001_gasifier_model.py:314,230)

| term | dir | DOK-ING low kW | DOK-ING midpoint kW | DOK-ING high kW | model composition kW |
|---|---|---|---|---|---|
| dry feed chemical energy (dry mass x LHV) | in | 156.262 | 182.306 | 208.350 | 164.113 |
| residual moisture (liquid water, 25 degC) | in | -0.257 | -0.257 | -0.257 | -0.257 |
| air sensible heat (preheated to 200 degC) | in | 3.399 | 3.399 | 3.399 | 3.399 |
| gasifier steam sensible heat (350 degC vapour) | in | 2.819 | 2.819 | 2.819 | 2.819 |
| tail-gas recycle chemical energy (H2, CO, CH4) | in | 61.348 | 61.348 | 61.348 | 61.348 |
| product gas chemical energy (H2, CO, CH4) | out | 178.685 | 178.685 | 178.685 | 178.685 |
| product gas sensible heat (at operating temperature, wet) | out | 47.869 | 47.869 | 47.869 | 47.869 |
| carbon not in the gas: chemical energy (graphite LHV) | out | 18.321 | 18.321 | 18.321 | 18.321 |
| char + ash sensible heat at bed temperature | out | 1.481 | 1.481 | 1.481 | 1.481 |
| **sum in** |  | 223.572 | 249.615 | 275.659 | 231.422 |
| **sum out** |  | 246.356 | 246.356 | 246.356 | 246.356 |
| **implied heat duty (+ = gasifier must ADD heat)** -- Calculated, not part of the engine |  | +22.78 | -3.26 | -29.30 | +14.93 |
| implied duty, % of feed energy |  | +14.6 | -1.8 | -14.1 | +9.1 |
| adiabatic temperature at the published composition, degC |  | 523 | 1011 | 1499 | 670 |
| cold-gas efficiency incl. recycle |  | 0.821 | 0.733 | 0.663 | 0.793 |
| cold-gas efficiency net of recycle |  | 0.751 | 0.644 | 0.563 | 0.715 |

Missing terms (listed, not zero): tar chemical and sensible energy (GA-001 tar Missing); heat loss through the 150 mm refractory and shell (no loss model; GA-001 registry gives geometry only); feed and recycle sensible heat (feed/recycle temperatures not stated).

#### C1. Whole-plant energy (boundary crossings; internal heat recovery cancels)

| term | dir | DOK-ING low kW | DOK-ING midpoint kW | DOK-ING high kW | model composition kW |
|---|---|---|---|---|---|
| dry feed chemical energy (dry mass x LHV) | in | 156.262 | 182.306 | 208.350 | 164.113 |
| feed moisture (liquid water, 25 degC) | in | -2.827 | -2.827 | -2.827 | -2.827 |
| make-up water for gasifier steam (liquid, 25 degC) | in | -10.178 | -10.178 | -10.178 | -10.178 |
| make-up water for WGS steam (liquid, 25 degC) | in | -48.104 | -48.104 | -48.104 | -48.104 |
| electrolyser feed water (liquid, 25 degC) | in | -0.046 | -0.046 | -0.046 | -0.046 |
| electricity consumed, as summed by EU-009 | in | 15.846 | 15.846 | 15.846 | 15.846 |
| shredder FE-004 electricity (computed by the engine, NOT in EU-009) | in | 6.250 | 6.250 | 6.250 | 6.250 |
| PSA hydrogen product, LHV | out | 108.325 | 108.325 | 108.325 | 108.325 |
| electrolyser hydrogen, LHV | out | 0.203 | 0.203 | 0.203 | 0.203 |
| carbon black, chemical energy (taken as pure carbon) | out | 17.065 | 17.065 | 17.065 | 17.065 |
| carbon black, sensible heat at 180 degC | out | 0.081 | 0.081 | 0.081 | 0.081 |
| model-implied carbon beyond the carbon-black stream (chemical) | out | 1.256 | 1.256 | 1.256 | 1.256 |
| vent gas CO2 + N2 sensible heat | out | 0.471 | 0.471 | 0.471 | 0.471 |
| quench condensate (liquid, 65 degC) | out | -11.771 | -11.771 | -11.771 | -11.771 |
| WGS knocked-out water (liquid) | out | -37.480 | -37.480 | -37.480 | -37.480 |
| dryer vapour (100 degC) | out | 0.164 | 0.164 | 0.164 | 0.164 |
| **sum in** |  | 117.203 | 143.247 | 169.291 | 125.053 |
| **known energy out (non-heat)** |  | 78.314 | 78.314 | 78.314 | 78.314 |
| **heat the balance says must be rejected** (in - known out) |  | 38.89 | 64.93 | 90.98 | 46.74 |
| heat rejection the engine reports (GC-004 sensible + HB-012 power) |  | 41.28 | 41.28 | 41.28 | 41.28 |
| **closure residual = balance - engine, kW** |  | -2.39 | +23.66 | +49.70 | +5.46 |
| closure residual, % of energy input |  | -2.0 | +16.5 | +29.4 | +4.4 |

Heat rejection the engine omits (computed from the same constants, Calculated / Estimated; midpoint LHV):

| item | kW | status | basis |
|---|---|---|---|
| WGS knock-out: cool and condense the unreacted steam (from 220 degC, Assumed) | 43.87 | Estimated | n_H2O x [cp_vap (220-25) + DH_VAP - cp_liq (T-25)]; no unit in the engine rejects this heat |
| quench: water vapour sensible + condensation (not in GC-004 duty) | 20.76 | Calculated | n_H2O x [cp_vap (860-25) + DH_VAP - cp_liq (65-25)]; GC-004 docstring says it is omitted |
| electrolyser: electricity not converted to hydrogen LHV | 5.80 | Calculated | HB-011 power_kw - H2 LHV; no heat-rejection stream exists |
| shredder FE-004 electricity becomes heat | 6.25 | Calculated | FE-004 power_kw; not in EU-009 nor EU-008 |
| **sum of the omitted rejections** | 76.69 |  |  |

The omitted rejections (76.7 kW) exceed the closure residual (+23.7 kW) by 53.0 kW: they can only all be real if a heat INPUT of that size exists that the engine has no term for. The steam and drying duties below are the candidate:

| internal heat demand with no source in the engine | kW | status | basis |
|---|---|---|---|
| raise gasifier steam: liquid 25 degC -> vapour 350 degC | 13.00 | Estimated | DH_VAP + mean cp x (350-25); source of this heat is not in the engine |
| raise WGS steam: liquid 25 degC -> vapour 350 degC | 61.43 | Estimated | HB-005 conditions 350 degC / 5 bar(g); the engine counts only HB-003's 20->150 degC sensible duty |
| preheat air to 200 degC | 3.40 | Estimated | GA-004 'recovered process heat' |
| evaporate feed moisture in the dryer | 2.73 | Estimated | FE-005 heat source 'recovered process heat ... electric/gas trim backup' |
| **sum** | 80.56 |  | the engine routes only HB-003's 10.7 kW to feedwater |

Missing plant-energy terms (listed, not zero): heat loss from vessels and piping (no model); tar and dust energy (Missing); ash sensible heat (discharge temperature not stated); nameplate loads outside EU-009 and FE-004: FE-003 0.37, FE-005 5, FE-007 5.5, FE-008 0.75, GA-005 1.1, GA-006 0.55, HB-009 blower 0.5 kW (utilisation not stated); boiler / trim fuel for steam raising and drying (not modelled); make-up water and cooling-tower evaporation energy.

#### C3. Efficiencies as reported vs as the balance implies

| quantity | twin reports | re-derived from its formula | balance-implied | formula / comment |
|---|---|---|---|---|
| H2 conversion efficiency (Integrated Plant Status) | 52.0-69.4 % | 52.0-69.4 % | 52.0-69.3 % (feed only) | 100 x H2 LHV (HB-012 h2_kg_h at 10.8 MJ/Nm3) / (FE-005 dry feed x 15..20 MJ/kg); feed energy is the ONLY denominator term (tab1_integration.py:213-233) |
| same, with the electricity the plant uses in the denominator | not reported | - | 47.0-60.7 % (22.1 kW) | the reported figure ignores electricity (and steam raising) |
| H2 LHV used (kW) | 108.435 (10.8 MJ/Nm3, EU-006) | - | 108.325 (241.826 kJ/mol) | difference +0.10 % |
| H2 yield per kg dry feed | 0.0867 | - | 55.5 % of the stoichiometric maximum 0.1563 | HB-012 h2_kg_h / FE-005 dry_solids_kg_h (tab1_integration.py:266); maximum: feed C x (2 + H/C/2 - O/C) mol H2 (complete steam reforming to CO2, unlimited steam), x 2.016 g/mol; N and ash ignored |
| cold-gas efficiency (GA-001) | not reported | - | 17.5 MJ/kg: 0.82, 0.73, 0.66, 0.79 (incl. recycle) | gas LHV (H2+CO+CH4) / (feed LHV + recycle LHV); net of recycle: (gas LHV - recycle LHV) / feed LHV |

major_losses as the twin lists them (tab1_integration.py:271-289): {"quench_sensible_heat_rejected_kw": 32.579, "cooling_tower_heat_rejected_kw": 51.992, "h2_compressor_shaft_power_kw": 8.696, "gas_train_fan_power_kw": 0.4}. Its `cooling_tower_heat_rejected_kw` already contains the quench sensible duty and the compressor power, so the list double-counts if added.

