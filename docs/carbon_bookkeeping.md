# Carbon bookkeeping: one governing value and a complete atom-balance guard

Written 2026-10-30 on `origin/main` 198bfcb (branch `carbon-bookkeeping`). Source: the closure audit (`docs/balance_closure_audit.md`). H, O and N already closed to numerical precision; carbon did not
(+0.138 kg/h at the default) because two Assumed constants disagreed, and `verify_atom_balance` checked only H and O. Owner decision: the carbon conversion governs, the carbon black is derived from the unconverted carbon,
the GA-008 datasheet figure becomes a cross-check, and the guard covers C and N.

**No gas-side result changed.** The 118 entries of `main` are bit-identical in both `tail_gas_mode` values: 1888 entries compared over 16 runs (default, heat_only, ER 0.2125 / 0.2875, feed -30 / +30 %, conversion 0.85 / 0.98, each
at 5 and 30 cycles), 0 differ, 0 removed, 2 added. Product-gas flow and composition, LHV, hydrogen, PSA, storage, EU, SA, the energy key and the dynamics results are untouched. No default (conversion 0.90, ash 10 %, the 5 % constant, ER, ...) was changed,
nothing was tuned, the registry file, `SharedPlantState`, the engine API, `run_continuous_cycle.py`, the dynamics layer, the what-if tab, the workflows and `requirements.txt` are untouched. Offline throughout.

## 1. The old and the new accounting

| | before | now |
|---|---|---|
| carbon that reaches the gas | `conversion` (0.90, Assumed, range 0.85-0.98) x all fuel carbon, recycled CO/CH4 carbon included (`ga001_gasifier_model.py:303`, per mol of the combined fuel carbon) | unchanged |
| unconverted carbon | implicit: `0.1 x (C_feed + C_recycle)` has no stream, and is published nowhere | `(1 - conversion) x (C_feed + C_recycle)` = 2.013 kg/h at the default (1.688 from the feed + 0.326 from the recycle), published in `("GA-001","CarbonAccounting")`; one function, `ga001.unconverted_carbon_fraction`, defines it for both the key and the guard |
| carbon black | independent: 5 % of dry feed (`gasifier_mass_balance.py:62`, derived from GA-008's 1.88 kg/h at the old 37.5 kg/h design point) = 1.875 kg/h | **derived**: unconverted carbon x the split = 2.013 kg/h |
| the governing parameter | two (conversion and the 5 % constant) | **one**: `carbon_conversion_efficiency`, plus the Assumed split `("GA-001-INPUT","unconverted_carbon_to_carbon_black")` = 1.0 (range 0.5-1.0) |
| the 5 % constant and GA-008's figure | inputs | a **cross-check** (`datasheet_cross_check` in the key): ratio derived / datasheet, the GA-008 3 kg/h capacity check; it feeds nothing |
| `verify_atom_balance` | H and O (the carbon check was computed and never compared; nitrogen not tested) | C (gas carbon equals the conversion, and gas carbon + unconverted fraction is the 1 mol fed), H, O and N; same tolerance 1e-8; still returns `(ok, detail)` and is called only by the GA-001 self-test and the closure audit (not by the hourly runtime or the UI) |

The split: the Assumed share of the unconverted carbon that leaves as carbon black. Below 1 the rest is published as `remainder_kg_h` with `remainder_destination_status = Missing`, and the closure audit counts it as a labelled
"destination Missing" term, so the carbon still closes by construction. Unknown is not zero: the true split between carbon black, bed-drain carry-over, cyclone catch and fly ash is `Missing`.

## 2. Result: carbon closes everywhere (closure audit, before and after)

| case | cycles | GA-001 carbon before, kg/h (% of C in) | GA-001 carbon after | loop carbon before (%) | loop carbon after | GA-001 total mass before (%) | GA-001 total mass after |
|---|---|---|---|---|---|---|---|
| default | 30 | +0.1380 (+0.69 %) | +0e+00 | +0.1380 (+0.82 %) | +0e+00 | +0.1380 (+0.109 %) | +1e-14 |
| default | 5 | +0.1377 (+0.68 %) | +0e+00 | +0.1377 (+0.82 %) | +0e+00 | +0.1377 (+0.109 %) | +0e+00 |
| heat_only | 30 | -0.1875 (-1.11 %) | +0e+00 | -0.1875 (-1.11 %) | +0e+00 | -0.1875 (-0.182 %) | +3e-14 |
| heat_only | 5 | -0.1875 (-1.11 %) | +0e+00 | -0.1875 (-1.11 %) | +0e+00 | -0.1875 (-0.182 %) | +3e-14 |
| ER 0.2125 | 30 | +0.1305 (+0.65 %) | +0e+00 | +0.1305 (+0.77 %) | -3e-15 | +0.1305 (+0.112 %) | -1e-14 |
| ER 0.2125 | 5 | +0.1301 (+0.65 %) | +0e+00 | +0.1301 (+0.77 %) | -3e-15 | +0.1301 (+0.111 %) | +0e+00 |
| ER 0.2875 | 30 | +0.1450 (+0.72 %) | +3e-15 | +0.1450 (+0.86 %) | +5e-15 | +0.1450 (+0.107 %) | +3e-14 |
| ER 0.2875 | 5 | +0.1447 (+0.72 %) | -3e-15 | +0.1447 (+0.86 %) | -3e-15 | +0.1447 (+0.107 %) | +0e+00 |
| feed -30 % (FE-001) | 30 | +0.0966 (+0.69 %) | +0e+00 | +0.0966 (+0.82 %) | +1e-15 | +0.0966 (+0.109 %) | +1e-14 |
| feed -30 % (FE-001) | 5 | +0.0972 (+0.69 %) | +0e+00 | +0.0972 (+0.82 %) | -1e-15 | +0.0972 (+0.110 %) | +0e+00 |
| feed +30 % (FE-001) | 30 | +0.1656 (+0.69 %) | -5e-15 | +0.1656 (+0.82 %) | -3e-15 | +0.1656 (+0.109 %) | +3e-14 |
| feed +30 % (FE-001) | 5 | +0.1647 (+0.68 %) | +0e+00 | +0.1647 (+0.81 %) | +5e-15 | +0.1647 (+0.109 %) | +3e-14 |
| conversion 0.85 | 30 | +1.1184 (+5.60 %) | +0e+00 | +1.1184 (+6.63 %) | +3e-15 | +1.1184 (+0.897 %) | +0e+00 |
| conversion 0.85 | 5 | +1.1180 (+5.60 %) | -3e-15 | +1.1180 (+6.62 %) | -3e-15 | +1.1180 (+0.896 %) | +3e-14 |
| conversion 0.98 | 30 | -1.4669 (-7.19 %) | +3e-15 | -1.4669 (-8.69 %) | -3e-15 | -1.4669 (-1.137 %) | +3e-14 |
| conversion 0.98 | 5 | -1.4670 (-7.19 %) | +3e-15 | -1.4670 (-8.69 %) | +3e-15 | -1.4670 (-1.137 %) | +0e+00 |

Worst remaining carbon residual: 5.5e-15 kg/h (rounding). Verdict in every row: `closes to numerical precision`. H, O and N stay below 5e-16 relative. The old residual scaled with the conversion (+1.12 kg/h at 0.85, -1.47 kg/h at 0.98) because the 5 % constant
was never tied to it; the derived flow follows the conversion by construction.

## 3. Cross-check against the datasheet (converged, kg/h)

| case | unconverted | carbon black (split 1) | remainder | datasheet rule (5 %) | derived / datasheet | GA-008 capacity 3 kg/h |
|---|---|---|---|---|---|---|
| default | 2.013 | 2.013 | 0.000 | 1.875 | 1.074 | not exceeded |
| heat_only | 1.688 | 1.688 | 0.000 | 1.875 | 0.900 | not exceeded |
| ER 0.2125 / 0.2875 | 2.006 / 2.020 | same | 0 | 1.875 | 1.070 / 1.077 | not exceeded |
| feed -30 % / +30 % | 1.409 / 2.416 | same | 0 | 1.313 / 2.250 | 1.074 | not exceeded |
| conversion 0.85 | 2.994 | 2.994 | 0.000 | 1.875 | 1.596 | not exceeded (**99.8 % of capacity**) |
| conversion 0.98 | 0.408 | 0.408 | 0.000 | 1.875 | 0.218 | not exceeded |
| split 0.5 (check) | 2.013 | 1.007 | 1.007 | 1.875 | 0.537 | not exceeded |

Status line at the default: "derived 2.013 kg/h against datasheet rule 1.875 kg/h (5 % of 37.50 kg/h dry feed; GA-008's 1.88 kg/h at the old 37.5 kg/h design point scales to 1.880); GA-008 capacity 3.0 kg/h not exceeded".
GA-008's 3 kg/h capacity holds in every case; at the bottom of the conversion range (0.85) the unit would be at 99.8 % with nothing to spare, and a feed increase on top would exceed it. The registry was not changed. GA-009 (ash, 5 kg/h) is unaffected (ash is untouched).

## 4. What changed, and what did not (A1 of the task)

No engine entry published carbon black or ash before this task, so **no existing entry changed**: only two keys were added, `("GA-001-INPUT","unconverted_carbon_to_carbon_black")` and `("GA-001","CarbonAccounting")` (persisted keys 120 -> 122; no key is lost, growth does not trip the 90 % shrink guard).
Places that still compute the carbon black from the 5 % rule, on demand and outside the engine: `gasifier_mass_balance.byproduct_mass_flows` (`gasifier_mass_balance.py:65`), the app cards (`app.py` GA-008 / GA-010 / "Carbon black recovery (derived)" cards, `app.py:4802, 5069, 5355`), `circularity.py:42` and the static equipment fills in `equipment_engineering_estimates.py:1617`. They show 1.875 kg/h
while the engine publishes 2.013 kg/h. Changing them is a UI / static-tool change, out of scope here (one line in `CLAUDE.md` Known limitations).

## 5. Still `Missing` or out of scope

The split of the unconverted carbon (carbon black / bed-drain carry-over / cyclone catch / fly ash); the carbon content of the carbon black (taken as pure carbon; GA-008 states product ash < 1 wt %); the fly-ash / bottom-ash split of the 10 % ash (ash is untouched);
tar; the water, sulphur and chlorine sinks; the cycle-1 bootstrap (GA-001 uses the 41.67 kg/h wet figure as dry feed on cycle 1; unchanged); the HB-013 storage clamp; the water molar-mass constant (18.015 vs 18.016, now the only reason the loop total mass is not zero: about -2e-3 to -4e-3 kg/h).

## 6. Tests and guards

New: `tests/test_carbon_bookkeeping.py` (see the test file's docstring). Existing tests changed deliberately, each because it pinned the entry count or the old residual: `tests/test_dynamics.py` (two `== 118` -> `== 120`), `tests/test_snapshot_deterministic.py` (`== 118` -> `== 120`),
`tests/test_tail_gas_mode.py` (its list of new keys now has the two added here, and one test was renamed from "...exactly_two_are_added" to "...exactly_the_new_keys_are_added"), `tests/test_balance_audit.py` (the cycle-1 assertion `measured < 0` encoded the old -0.208 kg/h residual; it now asserts the carbon closes and that the
5 % cross-check keeps its sign flip). `tests/test_store_read_guard.py` needed no change this time.

## 7. Open decisions

1. **Is `0.1 x C_recycle` defensible?** The conversion is applied to the recycled CO and CH4 carbon because `solve_product_gas` works per mol of the combined fuel carbon. Carbon that is already in the gas phase cannot become solid carbon, so in `regasify` mode 0.326 kg/h of the 2.013 kg/h "unconverted carbon" (16 %) is an artefact of that structure, and the carbon black derived from it inherits it.
   In `heat_only` the term is zero. I recommend revisiting it when the tail-gas question is settled; it was not changed here (it would change a gas-side result).
2. **The split parameter**: 1.0 means all unconverted carbon is carbon black. DOK-ING data on bed-drain carry-over, cyclone catch and fly ash would replace it; until then the range is 0.5-1.0 (Assumed).
3. **The cycle-1 bootstrap** (the 41.67 kg/h wet figure used as dry feed) is untouched: it only affects cycle 1 and is unchanged by this task.
