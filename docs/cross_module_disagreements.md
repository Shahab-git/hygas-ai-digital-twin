# Cross-module disagreements (G5-07)

Date: 2026-11-06. Figures measured on `origin/main` at `d8af8f3` (after P0-FB2 step 2). **This is a list of differences the repo measures; it changes no value.** Dispositions are in section 4.

> **Update 2026-11-11 (P1-06 / P1-06d): the engine default is now `heat_only`.** The figures in this file were measured on `regasify` (the default until P1-06) and stay as dated records; nothing below was re-measured. The same rows on the real default, 30 cycles, pinned in `tests/test_disagreement_rows.py` next to the `regasify` ones: syngas H2 / CO / CO2 / CH4 / N2 24.79 / 22.06 / 12.11 / 1.80 / 39.24 vol% (row 1); flow 78.79 Nm3/h dry (3); PSA feed H2 36.1 vol% (4); hydrogen 55.7 kg/day (7); PSA recovery 77.0 % (8); EU-008 demand 39.98 kW (10); HB-003 hot / cold side 5.73 / 8.45 kW (11); GC-009 96.67 % (12, unchanged); carbon black derived 1.688 kg/h (13). Every disagreement with the registry remains (the nitrogen is still about four times the registry's 10 %); the dispositions of section 4 are unchanged, and row 9 (the tail-gas default) was decided by the owner in P1-06.

## How to read this

- A "disagreement" is a place where two parts of the repo (model vs registry, model vs DOK-ING statement, module vs module) give different numbers for the same thing, and the repo already measures it.
- Numbers are the engine at 30 cycles, default settings (`regasify`, ER 0.25, 950 degC), run offline against the in-memory fake store (0 database calls).
- **Reproduced by** says how the number was obtained. "Repo script" means a script in the repo. "ad hoc snapshot" rows (1, 3, 4, 7 partly, 8, 10, 11, 12, 13) are now reproduced and pinned by `python scripts/run_disagreement_report.py` and `tests/test_disagreement_rows.py` (PR #32). Rows 2, 5, 6, 9 and 14-19 rest on the repo scripts and documents named in their row.
- "Proposed" was the reviewer's suggestion; the owner's dispositions are in section 4. Allowed dispositions: **fix**, **defer**, **accept**.

## 1. The list

### A. Model against registry or DOK-ING statements

| # | Disagreement | Number A | Number B | Reproduced by | Documented in | Needs DOK-ING? | Proposed |
|---|---|---|---|---|---|---|---|
| 1 | Syngas composition, live GA-001 (dry) vs registry "Expected" SA-001..005 | H2 27.45 / CO 21.46 / CO2 9.80 / CH4 1.65 / N2 39.64 vol% | 32-33 / 28 / 22 / 8 / 10 vol% (differences -16 %, -23 %, -55 %, -79 %, +296 %) | ad hoc snapshot; `GA-001 AgentConsistency` key reports the N2 line | `master_open_questions.md` item 5; `gasifying_agent_study.md`; CLAUDE.md | Yes (agent, air, composition) | defer |
| 2 | Syngas LHV vs registry SA-006 | -36 % (CLAUDE.md figure; not re-measured here) | 9.8 MJ/Nm3 | not re-run | CLAUDE.md, "Known limitations" | Yes (same cause as 1) | defer, with 1 |
| 3 | Syngas flow vs registry HB-007 / SA-010 / design point | 102.75 Nm3/h dry (125.9 wet) | 50 Nm3/h | ad hoc snapshot | CLAUDE.md; `master_open_questions.md` item 5 | Yes | defer, with 1 |
| 4 | PSA feed H2 vs registry HB-006 | 38.1 vol% (`HB-006 PSA` y_H2 0.381) | 55 vol% | ad hoc snapshot; also printed by `hb_wgs_psa_storage_chain.py` | `master_open_questions.md` item 5 (update 2026-09-08) | Yes | defer, with 1 |
| 5 | Gasifying agent: registry says steam-blown chemical looping; model runs air at ER 0.25 | air, N2 99.3 % from air | Fe2O3/Fe3O4 steam-blown (registry, unverified) | repo script `scripts/run_agent_comparison.py` | `gasifying_agent_study.md`; RFI #2 point 1 | **Yes (root cause of 1-4)** | defer until DOK-ING answers |
| 6 | Primary air flow, GA-001 model vs GA-003 | 38.79 Nm3/h at ER 0.25 (37.5 kg/h feed) | 60 Nm3/h (GA-003, remark says "not DOK-ING-confirmed") | repo self-test `python -m python.ga001_gasifier_model` | `master_open_questions.md` item 6 | Yes | defer |
| 7 | Hydrogen output vs DOK-ING and registry | 78.0 kg/day (`HB-012` h2_kg_h 3.251 x 24); 55.7 with `heat_only` | about 50 (DOK-ING, plastic waste); 44.4 (registry) | repo script `scripts/run_h2_yield_comparison.py` | `tail_gas_heat.md` | Partly (basis of the 50, tail-gas use) | defer; the model is not tuned |
| 8 | PSA recovery, model vs registry | 78.8 % (default); 77.0 % in `heat_only` | 75 % (HB-007) | ad hoc snapshot; repo script above | `tail_gas_heat.md` | Yes (RFI #2 point 7) | defer |
| 9 | Tail-gas use: model re-gasifies it; registry says it returns as supplemental fuel | `regasify` (default) | `heat_only` mode exists, not default | repo script above | `tail_gas_heat.md` | Yes | owner decision on the default |
| 10 | EU-008 cooling tower rating vs this model's own demand | 20 kW (registry, scoped to EU-004 jacket only) | 52.0 kW live demand (utilisation 2.60); 55-60 kW baseline estimate with 15 % margin | ad hoc snapshot (`EU-008 CoolingSupply`, `RecommendedCapacityEstimate`) | CLAUDE.md; `master_open_questions.md` item 1 | Yes (first on the list for DOK-ING) | defer; already flagged |
| 11 | HB-003 heat duty: three figures | 5 kW (registry) vs live 7.38 kW hot side, 10.72 kW cold side | the repo's own self-test prints 6.360 / 9.436 kW, but it runs ONE cycle from a cold start (`_run_full_chain(0.25, n_cycles=1)`); the same chain gives 7.193 / 10.457 kW at 2 cycles and 7.375 / 10.715 kW at 5 | ad hoc snapshot; repo self-test `python -m python.hb_wgs_psa_storage_chain` | `master_open_questions.md` item 7 (now labelled as the 1-cycle figures) | Yes | defer; **see note 1** |
| 12 | GC-009 HCl removal vs its own target | 96.67 % computed from its inlet/outlet figures | ">97 %" stated | ad hoc snapshot (`GC-009 HCl`); repo self-test | `master_open_questions.md` item 8 | Yes (minor) | accept or ask; small |

### B. Module against module inside the model

| # | Disagreement | Number A | Number B | Reproduced by | Documented in | Proposed |
|---|---|---|---|---|---|---|
| 13 | Carbon black: three definitions | 1.875 kg/h (5 % rule on dry feed: app cards, circularity, GA-008 datasheet) | 2.013 kg/h (engine, derived from unconverted carbon, `GA-001 CarbonAccounting`); 2.0835 kg/h (`byproduct_mass_flows()` default, no longer used by app or datasheets) | ad hoc snapshot; `tests/test_feed_basis.py` pins 1.875 and 2.0835 | `carbon_bookkeeping.md`; CLAUDE.md | defer; align the app cards to the engine value is a separate owner decision |
| 14 | Feed basis on cycle 1 only: GA-001 gets 41.67 as if dry (+11.1 %) | 41.67 kg/h | 37.503 kg/h from cycle 2 | pinned by `test_known_limitation_*` in `tests/test_feed_basis.py` | CLAUDE.md feed-rate bases; P0-FB2 | accept as documented (narrow scope chosen 6 Nov) |
| 15 | Plant energy does not close | +23.7 kW (16.5 % of input, `regasify`); +65.0 kW (43.1 %, `heat_only`); -73 to +107 kW across scenarios (CLAUDE.md) | 0 | repo script `scripts/run_balance_audit.py` (re-run today: +23.65 kW, -2.4 to +49.7 over 15-20 MJ/kg) | `balance_closure_audit.md` | defer; omitted terms are Missing, not zero |
| 16 | Omitted heat: ~76.7 kW of heat rejection with no sink, ~80.6 kW of steam/drying duty with no source | 76.69 kW / 80.56 kW | engine has neither | repo script `scripts/run_balance_audit.py` | `balance_closure_audit.md`; `plant_heat_integration.md` | defer |
| 17 | Heat deficit with no burner or boiler | 52 kW (`regasify`), 13 kW (`heat_only`) | none modelled | repo script `scripts/run_heat_integration_report.py` | `plant_heat_integration.md` | defer; needs DOK-ING stack and steam data |
| 18 | Published-stream mass residual | 4.56 % on published streams (closes to 0.001 % only with ash and unconverted carbon added) | 0 | repo script `scripts/run_balance_audit.py` | CLAUDE.md; `balance_closure_audit.md` | accept (explained) |
| 19 | Efficiency reported ignores electricity | 52.0-69.4 % (feed only) | 47.0-60.7 % with 22.1 kW electricity | repo script `scripts/run_balance_audit.py` | `balance_closure_audit.md` section C3 | defer; label rather than change |

## 2. Notes

1. **Row 11 shows an internal inconsistency, not only a model-vs-registry gap.** The live engine reports 7.376 / 10.717 kW, while the repo's self-test, and `master_open_questions.md` item 7 which quotes it, show 6.360 / 9.436 kW. **Cause traced 9 Nov:** the self-test runs one cycle from a cold start (cycle-1 feed fallback of 41.67 kg/h, tail-gas recycle not yet established), the live figures are the converged 30-cycle state. Measured offline with the fake store: 1 cycle 6.360 / 9.436 kW, 2 cycles 7.193 / 10.457, 5 cycles 7.375 / 10.715, 30 cycles 7.376 / 10.717. No model, test or script output was changed; `master_open_questions.md` item 7 now says which state each figure belongs to (owner-authorised documentation fix, 9 Nov).
2. Rows 1-4 share one root cause (row 5: the gasifying agent and air). I list them separately because each is a separate number a reviewer can find, but a single DOK-ING answer would close all four.
3. Row 6's 38.79 Nm3/h is at 37.5 kg/h, the original design point. At 37.503 it is effectively the same. I did not recompute it at the cycle-1 41.67 figure.
4. Row 2 and the "-73 to +107 kW" range in row 15 are taken from CLAUDE.md and the closure audit; I did not re-measure them today.
5. Several tolerances are not set (for example `GA-001 AgentConsistency` has no tolerance, so it gives no verdict). The list reports differences, not pass or fail.

## 3. Not on the list (separate items, G5-08)

H2 LHV 10.8 vs 10.783 MJ/Nm3 and water molar mass 18.015 vs 18.016 (rounding-level), two undeclared reads, three unused constants, and the hardening items. These are code hygiene, not disagreements between modules.

## 4. Owner dispositions (2026-11-06)

The owner accepted the proposed dispositions (Phase 0 closing request, item 2): **defer all 19 rows pending DOK-ING's reply to RFI #2**, with these specific readings of the "Proposed" column:

| Rows | Disposition |
|---|---|
| 1, 2, 3, 4 | defer (one cause: the gasifying agent; RFI #2 point 1) |
| 5, 6, 7, 8 | defer (RFI #2 points 1, 4, 7, and tail-gas use) |
| 9 (tail-gas default) | **decision still open**; to be taken once DOK-ING answers on tail-gas use; no default changes before then |
| 10, 11 | defer (DOK-ING to confirm cooling duty and HB-003 duty); row 11's document figures (6.36 / 9.44 kW) were the 1-cycle self-test values, now labelled as such in `master_open_questions.md` item 7 (9 Nov); the disposition (defer) is unchanged |
| 12 | defer (small; ask DOK-ING at the next request) |
| 13 | defer (aligning the app cards to the engine's derived carbon black is a separate decision) |
| 14 | **accept** as documented (cycle-1 feed basis; narrow scope chosen for P0-FB2) |
| 15, 16, 17, 19 | defer (the omitted energy terms are Missing, not zero; need DOK-ING stack and steam data) |
| 18 | **accept** (explained: closes only when ash and unconverted carbon are added) |

No fix is made in Phase 0. Nothing in this list is a validation, and no value here is calibrated.

## 5. Reproduce

`python scripts/run_disagreement_report.py` prints the rows covered by the pinned figures. The other rows: `python scripts/run_balance_audit.py`, `python scripts/run_h2_yield_comparison.py`, `python scripts/run_heat_integration_report.py`, `python scripts/run_agent_comparison.py`, `python -m python.ga001_gasifier_model`, `python -m python.hb_wgs_psa_storage_chain`. All are offline and make no database calls.
