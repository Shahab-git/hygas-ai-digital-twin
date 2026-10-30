# Tail gas as heat: a switch and a read-only energy key

> Update 2026-10-30: the carbon residuals quoted below (+0.138 / -0.1875 kg/h) are from before the carbon-bookkeeping change; carbon now closes to numerical precision in both modes (`docs/carbon_bookkeeping.md`). Nothing gas-side in this document changed.

Written 2026-10-30 on `origin/main` 71e92cc (branch `tail-gas-heat`). The twin makes 78.0 kg/day of hydrogen against DOK-ING's "about 50 kg/day" (RFI #6, plastic waste) and the registry's
44.4 kg/day. The biggest identified driver is that the PSA tail gas is re-gasified and re-shifted in GA-001 while the registry says it returns "as supplemental fuel", i.e. heat. The owner decided to treat the
tail gas as heat (option A), **behind a switch that defaults to today's behaviour**.

**The switch is OFF by default. The hourly runtime, the app, the what-if tab and every persisted value still show today's behaviour until the owner flips the default.** Nothing was tuned: ER, carbon conversion, PSA
recovery, the steam ratio and every other Assumed default are unchanged. Offline throughout: in-memory fake store, no database, no network, the real `secrets.toml` never read, `HYGAS_ALLOW_DB_WRITES` unset.

## 1. Read first (item A)

### 1.1 How the tail gas enters GA-001 today

| point | file:line | what it does |
|---|---|---|
| lagged read | `python/ga001_gasifier_model.py:1148-1149` | `GA-001 Outputs` is registered with `lagged_depends_on=[("HB-009","TailGas"), ("FE-005","MoistureBalance")]`: it reads the PREVIOUS cycle's tail gas (a 1 h lag, the circular GA-001 -> GC -> HB -> HB-009 -> GA-001 loop) |
| species taken | `ga001_gasifier_model.py:654-657` (`_RECYCLE_SPECIES_ATOMS`) | **H2, CO and CH4 only**. CO2 and N2 are deliberately excluded (:632-653: folding them in diverged), and water is not part of the tail gas |
| conversion | `ga001_gasifier_model.py:660-694` (`_recycle_atom_moles`) | each species' Nm3/h -> mol/h -> **C, H, O, N atoms** added to the fuel atoms (:770-783), then x, y, z are re-derived from the totals |
| atoms or energy | same | **atoms only.** The recycle is counted as feed atoms; its chemical energy is not a term anywhere in the engine (the audit computes it) |
| other consumers of `("HB-009","TailGas")` | `hb_wgs_psa_storage_chain.py:456` (HB-012 reads the product flow); `eu_utilities_chp.py:472` (EU-007 flare: inert CO2 + N2 vented; `combustible_nm3_h` is hard-coded to 0 because the recycle is assumed to claim 100 %, :482-484); `dynamics.py:174, 404-410` (replaces the tail-gas read by a delayed one); `app.py:7784, 8229` (display) | **no burner, boiler or CHP receives any tail gas**; CHP gets no syngas at all (`WGS_PSA_SYNGAS_CLAIM_FRACTION = 1.0`) |

Registry wording (`data/equipment_registry.json`; field names and values as in the file; GA-001 has no tail-gas field):

- HB-007, field "Tail gas disposition": value "Recycled to GA-001 gasifier via HB-009 (PSA Tail Gas Handler) as supplemental fuel"; remarks "Matches the design intent already established for HB-009 — closes a small efficiency loop rather than venting".
- HB-009, field "Tail gas disposition": value "Recycled to GA-001 gasifier as supplemental fuel"; remarks "Matches HB-007's established disposition exactly".
- HB-007, field "Tail gas LHV": value "~8 MJ/Nm³"; remarks "Still meaningful fuel value from unrecovered H2 and CH4 — lower than SA-006's 9.8 MJ/Nm3, but substantial enough to justify recycling".
- HB-009, field "Tail gas compressor (if recycled)": value "0.5 kW".
- HB-007, "Tail gas flow rate" 29.4 Nm3/h, "Tail gas composition" "~H2 25%, CO2 55%, CH4 10%, CO+N2 10%".

### 1.2 Tail-gas energy, converged default state

84.3 Nm3/h: H2 9.73, CO 4.385, CH4 1.691, CO2 27.74, N2 40.73 Nm3/h (mol %: 11.55 / 5.20 / 2.01 / 32.91 / 48.33). Lower heating value from the closure audit's named constants: **61.35 kW** (H2 29.16 kW = 47.5 %, CO 15.38 kW = 25.1 %, CH4
16.81 kW = 27.4 %) = 2.62 MJ/Nm3. **The 61 kW figure is confirmed.** The registry's "~8 MJ/Nm3 at 29.4 Nm3/h" is about 65 kW, so the energy is close even though flow, composition and LHV per Nm3 differ (the live gas is 2.4x the registry flow and
much more diluted with N2).

### 1.3 Heat demands that need a source (reusing `python/balance_audit.py`)

| demand | kW | basis |
|---|---|---|
| raise gasifier steam (15.0 kg/h, 25 -> 350 degC) | 13.0 | `DH_VAP` 44.004 kJ/mol + mean cp x 325 K; GA-004 350 degC (registry) |
| raise WGS steam (70.9 kg/h, HB-005) | 61.4 | same constants |
| preheat air to 200 degC (GA-004 registry, Assumed) | 3.4 | repo mean cp |
| evaporate feed moisture (3.79 kg/h, 100 degC dryer) | 2.7 | `DH_VAP` + cp |
| **total (regasify state)** | **80.6** | Estimated |
| implied gasifier duty at feed LHV 15 / 17.5 / 20 MJ/kg | +22.8 / -3.3 / -29.3 | `Calculated, not part of the engine` |

### 1.4 What would change if GA-001 stopped receiving recycle atoms

Measured by running both modes (30 cycles): **43 of the 118 entries get a different value.** Equipment affected: GA-001 (Outputs, inputs) and everything downstream of its gas: GC-001/003/004/007/008/009/013/015, HB-001/003/004/005/006/009/010/012/013/018, WGS,
EU-007/008/009/010/EU-CHP, SA-001..006/010, AI-007/AI-011, and Tab 1. Plant Overview KPIs (converged): total syngas 102.75 -> 78.79 Nm3/h; **H2 production 3.251 -> 2.323 kg/h**; H2 recovery 0.788 -> 0.770; H2 storage level 4.715 -> 1.545 kg;
electrical consumption 15.85 -> 13.27 kW; H2 yield 0.0867 -> 0.0619 kg/kg; overall efficiency, major losses and the SCADA snapshot change; **unchanged**: plant status, feedstock input, H2 purity (Missing), electrical and thermal production
totals as reported, equipment availability. SA-006 LHV 6.26 -> 6.10 MJ/Nm3; EU-009 net -0.85 -> +1.73 kW; AI-004's EU-009 state stays FAULT.

Dynamics and what-if tab (run in-process with the default temporarily set to `heat_only`, file untouched; feed +10 % at 10 min, dt 60 s): the baseline H2 is 2.3228 kg/h instead of 3.2510, and the **recycle delay `tau_rec` has no effect at all**
(`tau_rec` is not even listed as used; the maximum difference between default `tau_rec` and 0 is 0.00000 kg/h, against 0.00161 kg/h in `regasify`). So in `heat_only` the what-if tab's recycle-delay slider would do nothing.

### 1.5 Registration, and the design (item B in three lines)

The coupling is registered as `lagged_depends_on` on `GA-001 Outputs` (:1149). The switch is implemented **without changing the engine API, `SharedPlantState` or any existing dependency list** (the lagged HB-009 edge stays):

1. The switch is a new leaf engine input `("GA-001-INPUT","tail_gas_mode")` (`ga001_gasifier_model.py:1545-1580`, registered at :1145), status Assumed, default `"regasify"`; `GA-001 Outputs` also depends on it (it is deliberately not in the published `inputs` list, so no existing entry changes).
2. In `heat_only`, `_recycle_atom_moles` is handed a Missing-shaped HB-009 entry (`_tail_gas_entry`, :1574), i.e. zero recycle atoms (:673; line-neutral, so the closure audit's file:line references stay valid); an invalid mode raises `ValueError`.
3. A new leaf, report-only entry `("GA-001","EnergyBalance")` (`python/ga001_energy_balance.py`, registered from `register_ga001`, so the hourly runtime and the app pick it up with no change to `run_continuous_cycle.py`) publishes the energy terms in both modes.

Risks (all verified or stated): (i) three existing tests pin the entry count (116 -> 118) and one derives "would persist only N" from it; only those pins changed (section 3). (ii) In `heat_only`, EU-007 and the CHP model still assume the tail
combustibles are recycled (EU-007 reports 0 combustible; CHP gets no syngas): the 12.5 Nm3/h of H2/CO/CH4 are reported as heat only by the new key. Not changed (rule 3). (iii) The closure audit needed a convention for the burned tail gas (complete
combustion, no burner exists) to keep the loop and plant balances closing. (iv) `tau_rec` becomes inert. (v) The persisted key count rises 118 -> 120 (new keys are fine for the 90 % shrink guard; no key is lost).

## 2. The two modes and the energy key (item B)

- `regasify` (default): today's behaviour. HB-009's H2/CO/CH4 re-enter GA-001's atom balance one cycle late.
- `heat_only`: GA-001 receives zero recycle atoms; HB-009 and every other model are untouched and still run. The tail gas is a heat source only in `(GA-001, EnergyBalance)`.

`(GA-001, EnergyBalance)` (`python/ga001_energy_balance.py`; a leaf, nothing depends on it, nothing feeds back): for each feed-LHV case (DOK-ING 15 / 17.5 / 20 MJ/kg and the composition estimate 15.75): feed chemical energy
(feed sensible heat **Missing**, not zero), product-gas chemical and sensible energy, the implied gasifier duty (`Calculated, not part of the engine`), steam raising, air preheat and feed drying (Estimated, `balance_audit.heat_demands`), the tail gas's
chemical energy as available and as used heat, and `net_heat_kw = tail-gas heat used - gasifier duty - (steam + air + drying)` (+ surplus / - deficit; `net_heat_kw_if_tail_gas_were_heat` lets one snapshot show both modes). Constants are the closure audit's
(standard enthalpies of formation, the repo's mean cp, GA-004 registry temperatures). Assumed inputs are listed with ranges (feed temperature 25-100 degC, recycle temperature 25-65 degC, solids cp 0.8-1.4 kJ/kg.K). Missing and listed: tar, heat loss, feed
and recycle sensible heat, burner/boiler efficiency (the tail-gas heat is the gross LHV), and where the demanded heat is actually sourced. No boiler model and no heat-integration logic were added.

## 3. Tests and guards (item D)

`tests/test_tail_gas_mode.py`: 17 tests, about 11 s. (a) The default snapshot equals origin/main 71e92cc for all 116 existing entries (five-cycle and converged), against a gzip fixture made from the unmodified code
(`tests/fixtures/snapshot_origin_main_71e92cc.json.gz`): exact for structure, strings and integers and 1e-12 relative for floats, so another platform's libm cannot fail it; byte-identity was verified locally by diffing the serialised snapshots of
origin/main and of the new default (empty diff). (b) `heat_only` gives zero recycle atoms and H, O, N close below 1e-12. (c) The key exists in both modes and equals the closure-audit functions. (d) No key of main is lost; exactly two are added.
(e) An invalid mode raises `ValueError`. (f) Zero database calls, no client import. Mutation check: 11 of 11 mutants caught (switch inverted, recycle only partly zeroed, a Missing term set to zero, the key mutating shared model state, a persisted key dropped,
invalid mode silently defaulted, net-heat sign flipped, the switch leaking into the published inputs, the default flipped, tail heat counted in the wrong mode, the key not registered).

**Existing tests changed (the only edits):** `tests/test_dynamics.py` (two `== 116` pins -> `== 118`), `tests/test_snapshot_deterministic.py` (`== 116` -> `== 118`), `tests/test_store_read_guard.py::test_6` ("would persist only 80" -> `{stored - 38}`, derived from the stored count). All three are entry-count pins
that must follow the two new keys; none was weakened. Dynamics, what-if tab and closure-audit tests otherwise pass unchanged.

## 4. What the numbers do and do not show

- With the switch on, the twin's hydrogen falls from 78.0 to **55.7 kg/day** (-22.3 kg/day, about the +22 estimated earlier): +11.5 % against DOK-ING's 50 and +25.4 % against the registry's 44.4. **It still overshoots at the default ER 0.25.**
- Of that overshoot, nothing here says which Assumed value is wrong. ER 0.30 gives 50.5 kg/day and 0.40 gives 39.7; carbon conversion 0.85 gives 51.4; PSA recovery fixed at 75 % gives 54.3. These are one-at-a-time sensitivities, not a calibration, and no default was chosen from them.
- The comparison baselines differ: DOK-ING's 50 kg/day is for plastic waste (gross or net unstated); the model is MSW at 100 % availability with a 100 %-H2 product and no losses.
- Energy: in `heat_only` the tail gas supplies 49.0 kW of the 66.7 kW heat demand; the **net deficit is -18.3 kW at 17.5 MJ/kg** (-44.4 to +7.7 across 15-20 MJ/kg). In `regasify` the same demand is 80.6 kW with no heat source: -77.3 kW. The sign of the `heat_only` balance is not fixed by the data: the feed LHV uncertainty (+/-26 kW) is as large as the deficit.
- The closure audit in `heat_only`: H, O, N still close to 1e-16 (GA-001, loop, plant N); the carbon residual changes sign (-0.1875 kg/h: 10 % of the feed carbon is below the 5 % carbon-black stream when no recycle carbon is added); the plant energy residual grows to +65 kW (43 %) because the burned tail gas (49 kW) is
  heat the engine has no term to report. Reported, not fixed.
- What it does not show: that the tail gas should be burned (that is the owner's interpretation of "supplemental fuel"; the registry could also mean fuel to the gasifier), that the heat can actually be used at the temperatures needed, or any plant-measured yield.

## 5. Open decisions

1. **Flip the default to `heat_only`?** The effect is section 1.4: 43 entries change, Plant Overview H2 production 3.25 -> 2.32 kg/h, syngas 102.8 -> 78.8 Nm3/h, storage, electrical consumption, yield and efficiency change, EU-007 and the CHP model keep their recycle assumption, and the what-if tab's `tau_rec` slider becomes inert. Flipping is a one-line change of `TAIL_GAS_MODE_DEFAULT`
   (`ga001_gasifier_model.py:1541`); the persisted state would shift on the next run.
2. **ER.** The sweep (section 4 of the tables below) shows the overshoot depends on ER more than on anything else; the decision needs DOK-ING's actual air or oxygen supply, not this comparison.
3. **A boiler or heat-integration model?** The net deficit (-18 kW at the midpoint, -44 to +8 kW over the LHV range) and the unsourced 61-80 kW of steam raising say that without one the plant energy balance cannot close; the first step would be to route the tail-gas heat and the quench heat to the steam demand as a report, before any control logic.
4. **PSA recovery and conversion.** Fixing recovery at the registry's 75 % lowers hydrogen by 1.4 kg/day only; conversion 0.85-0.98 moves it from 51.4 to 62.7 kg/day. Neither alone closes the gap, and both are Assumed.

## Appendix: measured tables (generated by `scripts/run_h2_yield_comparison.py`)

### 1. Hydrogen product

Key and definition: `("HB-012","Compressor").h2_kg_h` = PSA product after recovery; compression is a pass-through (same mass), purity taken as 100 %; x 24 h. Registry design target 44.4 kg/day (HB-007/HB-012 20.6 Nm3/h = 1.85 kg/h); DOK-ING "about 50 kg/day from 1 tpd" (RFI #6).

| mode | state | H2 kg/h | H2 kg/day | vs registry 44.4 | vs DOK-ING 50 | PSA recovery (model) |
|---|---|---|---|---|---|---|
| regasify | converged (30) | 3.2510 | 78.0 | +75.7 % | +56.0 % | 78.8 % |
| regasify | five-cycle | 3.2502 | 78.0 | +75.7 % | +56.0 % | 78.8 % |
| heat_only | converged (30) | 2.3228 | 55.7 | +25.6 % | +11.5 % | 77.0 % |
| heat_only | five-cycle | 2.3228 | 55.7 | +25.6 % | +11.5 % | 77.0 % |

Caveats that belong next to these numbers: DOK-ING's ~50 kg/day is for **plastic waste** (RFI #6), gross or net not stated, availability and start-up not stated; ours is MSW at 100 % availability and steady state, with no leaks, purges or losses and a 100 %-H2 product. The registry's 44.4 kg/day is a design calculation on a stale gas basis (50 Nm3/h x 55 % H2 x 75 % recovery), not a measurement.

### 2. The energy key (GA-001, EnergyBalance), converged

**regasify** -- tail gas 84.3 Nm3/h, 2.62 MJ/Nm3, 61.3 kW (H2 48 %, CO 25 %, CH4 27 %); used as heat: False.

| kW | DOK-ING low (15.00 MJ/kg) | DOK-ING midpoint (17.50 MJ/kg) | DOK-ING high (20.00 MJ/kg) | model composition (15.75 MJ/kg) |
|---|---|---|---|---|
| steam raising (gasifier + WGS) | 74.4 | 74.4 | 74.4 | 74.4 |
| air preheat | 3.4 | 3.4 | 3.4 | 3.4 |
| feed drying | 2.7 | 2.7 | 2.7 | 2.7 |
| **heat demand total** | 80.6 | 80.6 | 80.6 | 80.6 |
| implied gasifier duty (+ must add heat) | +22.8 | -3.3 | -29.3 | +14.9 |
| tail-gas heat used | 0.0 | 0.0 | 0.0 | 0.0 |
| **net heat (+ surplus / - deficit)** | -103.3 | -77.3 | -51.3 | -95.5 |
| net if the tail gas were heat | -42.0 | -16.0 | +10.1 | -34.1 |

**heat_only** -- tail gas 67.0 Nm3/h, 2.64 MJ/Nm3, 49.0 kW (H2 47 %, CO 24 %, CH4 29 %); used as heat: True.

| kW | DOK-ING low (15.00 MJ/kg) | DOK-ING midpoint (17.50 MJ/kg) | DOK-ING high (20.00 MJ/kg) | model composition (15.75 MJ/kg) |
|---|---|---|---|---|
| steam raising (gasifier + WGS) | 61.4 | 61.4 | 61.4 | 61.4 |
| air preheat | 2.6 | 2.6 | 2.6 | 2.6 |
| feed drying | 2.7 | 2.7 | 2.7 | 2.7 |
| **heat demand total** | 66.7 | 66.7 | 66.7 | 66.7 |
| implied gasifier duty (+ must add heat) | +26.7 | +0.6 | -25.4 | +18.8 |
| tail-gas heat used | 49.0 | 49.0 | 49.0 | 49.0 |
| **net heat (+ surplus / - deficit)** | -44.4 | -18.3 | +7.7 | -36.5 |
| net if the tail gas were heat | -44.4 | -18.3 | +7.7 | -36.5 |

Missing (listed, not zero): tar chemical and sensible energy (GA-001 tar is Missing); heat loss through the 150 mm refractory and shell (no loss model); feed and recycle sensible heat (temperatures not stated; see ASSUMED_INPUTS ranges); burner / boiler efficiency and flue-gas losses for the tail-gas heat (no boiler in the engine): the tail-gas heat below is the gross LHV; where the demanded heat is actually sourced (boiler fuel, heat recovery): not modelled.

### 3. Closure audit residuals (python/balance_audit.py), both modes

| mode | state | GA-001 H,O,N max |rel| | loop H,O,N max |rel| | plant N |rel| | GA-001 carbon residual kg/h | plant mass residual kg/h | plant energy residual kW (mid LHV) |
|---|---|---|---|---|---|---|---|
| regasify | converged | 3.7e-16 | 1.6e-16 | 1.3e-16 | +0.1380 | +0.1484 | +23.7 (+16.5 %) |
| regasify | five-cycle | 1.9e-16 | 3.8e-16 | 3.8e-16 | +0.1377 | +0.1481 | +23.7 (+16.5 %) |
| heat_only | converged | 2.4e-16 | 1.8e-16 | 0.0e+00 | -0.1875 | -0.1765 | +65.0 (+43.1 %) |
| heat_only | five-cycle | 2.4e-16 | 1.8e-16 | 0.0e+00 | -0.1875 | -0.1765 | +65.0 (+43.1 %) |

In `heat_only` the audit treats the tail combustibles as burned (complete combustion, a convention: the engine has no burner), so the loop and plant H, O, N still close. Plant H and O keep the 1e-4 electrolyser-water residual found in the closure audit. Carbon and energy are reported, not fixed: the carbon residual changes sign without the recycle (0.1 x feed carbon is below the 5 % carbon-black stream). The `heat_only` plant energy residual is larger (about +65 kW against +24 kW) because the tail gas now burns inside the plant (about 49 kW) and the engine has no burner or boiler term to report that heat: it is the same finding, not a new error.

### 4. ER sweep in heat_only (converged)

| ER | H2 kg/day | vs DOK-ING 50 | vs registry 44.4 | net heat kW (17.5 MJ/kg) | net heat range 15 .. 20 MJ/kg |
|---|---|---|---|---|---|
| 0.2 | 60.9 | +21.9 % | +37.2 % | -27.2 | -53.2 .. -1.1 |
| 0.25 | 55.7 | +11.5 % | +25.6 % | -18.3 | -44.4 .. +7.7 |
| 0.3 | 50.5 | +0.9 % | +13.6 % | -9.2 | -35.3 .. +16.8 |
| 0.4 | 39.7 | -20.6 % | -10.6 % | +9.7 | -16.4 .. +35.7 |

At the default ER 0.25 in `heat_only` the twin gives 55.7 kg/day, +11.5 % against DOK-ING's about 50 and +25.6 % against the registry's 44.4: it **still overshoots**. ER is not chosen or changed from this.

### 5. One-at-a-time sensitivity in heat_only (converged)

| case | H2 kg/day | vs DOK-ING 50 | vs registry 44.4 | PSA recovery used | net heat kW (17.5 MJ/kg) |
|---|---|---|---|---|---|
| default (heat_only) | 55.7 | +11.5 % | +25.6 % | 77.0 % | -18.3 |
| carbon conversion 0.85 | 51.4 | +2.8 % | +15.7 % | 77.2 % | -14.3 |
| carbon conversion 0.98 | 62.7 | +25.4 % | +41.3 % | 76.6 % | -25.1 |
| PSA recovery fixed at 75 % (registry) | 54.3 | +8.6 % | +22.3 % | 75.0 % | -16.4 |

Feed LHV changes the heat balance only (hydrogen is independent of it): net heat in `heat_only` = -44.4 kW at 15.00 MJ/kg, -18.3 kW at 17.50 MJ/kg, +7.7 kW at 20.00 MJ/kg, -36.5 kW at 15.75 MJ/kg.

