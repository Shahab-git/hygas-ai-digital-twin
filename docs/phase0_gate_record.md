# Phase 0 gate record

**Status: Phase 0 is closed WITH EXCEPTIONS by the owner's decision of 2026-11-09 (G5-03, section 3c). Phase 1 is authorised ONLY for the four tasks named in section 3d (G5-04) and the five named in section 3e.** The approval says the baseline and its limits are documented; it does not say the model is validated, calibrated or correct. The Gate 5 criteria (G5-01 to G5-15) were adopted as working proposals; the owner accepted each disposition recorded below, and G5-09 is an exception, not a pass.

Record date: 2026-11-06; sections 2a, 3a, 3b, 3c and 4 updated 2026-11-09 (G5-01, G5-02, G5-03, G5-09). Repository state described: `main` at `e7f25b2` (merge of PR #38) for the 9 Nov updates; section 1 lists merges up to PR #32. This file records decisions and facts; it makes none. Where a statement rests only on the owner's word, it says so. Where the repo cannot show something, it says NOT VERIFIED.

## 1. What has been merged since the 3 Nov Phase 0 report

| PR | Merge commit | What | Test run on the PR |
|---|---|---|---|
| #25 | `5dfe3bc` | (in the 3 Nov report) | green, 3.11 and 3.12 |
| #26 | `2a7b372` | (in the 3 Nov report) | green, 3.11 and 3.12 |
| #27 | `1d2ae64` | A1: gasifying-agent switch (default `air`), read-only display, study document section | green, 3.11 and 3.12 |
| #28 | `6b010de` | P0-FB1: feed-rate bases documented, known feed-basis limitations characterized by tests | green, 3.11 and 3.12 |
| #29 | `8bc0728` | G5-02: date and commit labels in `docs/balance_audit_baseline.json` (numbers unchanged) | per owner report; CI result not recorded here |
| #30 | `dfdfe8d` | P0-FB2 step 1: circularity default and app input use the dry solids feed (37.503 kg/h) | green, 3.11 and 3.12 |
| #31 | `d8af8f3` | P0-FB2 step 2: GA-006/007/008/010 datasheet fills, provenance worksheet cells and overlay | CI result not recorded here (owner merged) |
| #32 | `244eb39` | G5-07: read-only reproduction script `scripts/run_disagreement_report.py` and pinned tests | CI result not recorded here (owner merged) |

The Tests workflow runs on `pull_request` and `workflow_dispatch` only. Merge commits on `main` have no Tests run. This is a known gap, put on hold by the owner (see section 3).

## 2. Gates 1 to 4 (restated on current code in the G5-02 reconciliation, 6 Nov)

| Gate | Recorded decision | Evidence on current code | Limitation stated |
|---|---|---|---|
| 1 Design-basis ledger | PASS (3 Nov) | coverage test passes on 3.11 and 3.12 | proves coverage of a scanned set, not that the scan set is complete |
| 2 Closure baselines | PASS (3 Nov) | regenerated audit equals the committed baseline at 1e-9; date/commit labels corrected by PR #29 | a measurement record, not a regression gate; 9 of 21 closure rows close by construction |
| 3 Maturity classes and readiness gates | PASS (3 Nov) | tests pass on both Pythons | gates fail by design; no module has plant-data evidence |
| 4 Test safeguards preserved | PASS (3 Nov), restated | persisted snapshots compared with fixture `tests/fixtures/snapshot_origin_main_701de71.json.gz` at 1e-12 relative; 123 keys now | scope restated 3 Nov; see owner notes below |

### 2a. Evidence on the commit `365f8b5` (merge of PR #37), 2026-11-09 (G5-02 refresh)

Gates 1-4 were re-checked on `365f8b5`, the tip of `main` when this section was written. Later commits in this series change documentation only. This is evidence of what ran, not a new decision.

| Check | Result | Where it ran |
|---|---|---|
| Full test suite, Python 3.11 | 910 passed, 6 skipped, 1 failed | scratch clone (cloud container), 9 Nov |
| Full test suite, Python 3.12 | 910 passed, 6 skipped, 1 failed | scratch clone (cloud container), 9 Nov |
| The one failure | `test_plant_heat_integration.py::test_nothing_reads_the_key_and_no_model_depends_on_it`: file-listing order in the container; the same test passes on the owner's machine and in the PR CI runs (container artefact, on hold, see section 3) | |
| Full test suite, Python 3.14.0, owner's machine | 913 passed, 0 failed, 4 skipped (last docs PR before this one, reported by the owner) | owner's machine |
| The 6 skips | 2 openpyxl not installed in the container (`test_apply_provenance.py:270`, `test_provenance_overlay.py:133`); 2 wording / heat-integration range guards; 2 "already merged" guards (`test_closure_scenarios.py:148`, `test_maturity_registry.py:128`). The owner's machine skips 4 (it has openpyxl) | |
| Gate 1: ledger coverage and pinned counts | included in the full run above, passed on both | |
| Gate 2: balance-audit baseline regenerated | 1,285 numeric and text entries of the original baseline compared with the committed file: the only differences are the date and the commit label (numbers equal at 1e-9). The scenario baseline is checked by `test_the_scenario_baseline_matches_a_fresh_run`, passed in the full run | scratch clone |
| Gate 3: maturity and readiness tests | passed in the full run on both | |
| Gate 4: persisted snapshot comparisons | passed in the full run on both; 123 persisted keys; fixture `tests/fixtures/snapshot_origin_main_701de71.json.gz` at 1e-12 relative | |
| Tests workflow results (GitHub Actions) | green on 3.11 and 3.12 for PRs #25-#28 and #30 as reported earlier; **not recorded here for PRs #29, #31-#37**: the owner merged them and reported no failure, but this record cannot show the runs (NOT VERIFIED from the repo) | |

Limits: no Tests run exists on merge commits of `main` (on hold); the container runs and the owner's run are not a substitute for a CI run on `365f8b5`.

Gate 4 notes accepted by the owner: two persisted keys were added by A1 (`GA-001-INPUT|gasifying_agent`, `GA-001|AgentConsistency`); some tests were edited for them; A1 was done early. P0-FB2 (narrow, steps 1 and 2): static modules, the app and the datasheet fills use the dry feed; **no persisted number changed**; two feed-basis limitation tests were converted or replaced by correctness tests, one new correctness test was added.

## 3. Owner decisions recorded (as stated by the owner in review)

| Topic | Decision |
|---|---|
| Gate 4 note (extra keys, test edits, A1 early) | accepted as a note |
| A3D phrase pairs | approved |
| The 12 CI skips (8 history-dependent, 2 merge-state, 2 openpyxl) | accepted |
| CI on `main` merges; the container `os.walk` ordering failure | on hold, no change |
| Stale baseline records | corrected (PR #29) |
| Issue 8 | recorded as a limit |
| G5-14 disposition | A1 authorised retroactively; A4.1 held |
| G5-06 feed basis | correct now, narrow scope (done: PRs #30, #31); the full correction (cycle-1 fallback, constant name) is not authorised |
| G5-07 | list in `docs/cross_module_disagreements.md`; dispositions accepted 6 Nov: defer all 19 rows pending DOK-ING (row 9 decision still open, rows 14 and 18 accepted) |
| G5-08 | dispositions accepted 6 Nov: see `docs/phase0_open_items.md` |
| G5-13 | boundary accepted as final 6 Nov (wording in `docs/phase0_open_items.md`, to be confirmed in review) |
| G5-05 | wording residue accepted 6 Nov; rewording listed as Phase 1 work |
| G5-15 and three amendments; G5-13 boundary draft | accepted as proposals, not as approved criteria |
| G5-10 benchmark screen | proposed dispositions accepted (numbers unchanged, evidence made visible); screen added to the repo as a screen, not as validation |
| G5-12 wording scan | fix points 1, 2, 3, 5 (wording only, no number changes); point 4 (the word 'Confirmed' in app.py code comments for HB-006 55 % and 10 % inlet moisture) recorded as a known limitation |

### 3a. G5-01: owner review of the four reports (recorded 2026-11-09, on `main` at `e7f25b2`)

The owner reviewed the four reports: A3 (`docs/design_basis_ledger.md`), A5 (`docs/balance_closure_audit.md`, section 9 and the audit it extends), A10 (`docs/maturity_and_readiness_gates.md`) and W1 (the wording-pass record in the ledger document, section "Confirmed mentions in the engine modules"). The owner worked from one-paragraph summaries prepared by Claude from those documents; Claude did not re-run the underlying scripts for this review. This entry records the owner's statement; the repo cannot show the review itself (NOT VERIFIED from the repo).

Findings:

1. The A10 table of wording still "needing rewording, not changed" (section 9 of that document) predates PR #35 (G5-12). It is not the current residue; the residue list is in `docs/phase0_open_items.md`.
2. The A5 audit's section 8 says its CI results were not verified. The current commit is covered only by the indirect CI record (section 3b), not by a run on `main`.
3. The A5 audit's standard enthalpies and LHV correlations are cited from memory, not fetched. A test pins the derived LHVs to the repo's own table within 0.3 %.
4. Not claimed: none of the four reports validates the model. 9 of the 21 closure rows close by construction (ENFORCED), and no module has plant-data evidence.

### 3b. G5-09: CI evidence on the closing commit (owner decision, 2026-11-09)

The owner chose an **indirect record** instead of a manual `workflow_dispatch` run on `main`. This is an accepted exception, not a pass. The hold on CI for `main` merges and on workflow changes stays.

| Evidence | What it shows | Limit |
|---|---|---|
| Tests workflow, 3.11 and 3.12 | green on PRs #25, #26, #27, #28 and #30 (as reported earlier) | not recorded here for PRs #29 and #31-#38: the owner merged them and reported no failure, but the repo cannot show the runs (NOT VERIFIED) |
| Container runs on `365f8b5` (section 2a) | 910 passed, 6 skipped, 1 failed on 3.11 and on 3.12; the one failure is the known file-listing-order artefact | not a CI run; not on the final commit |
| Owner's machine, Python 3.14 | 913 passed, 0 failed, 4 skipped on the last docs PR before PR #38 | not a CI run; 3.14 is not a CI version |
| Merge commits on `main` | no Tests run exists (the workflow runs on `pull_request` and `workflow_dispatch` only) | the gap itself |

Update 2026-11-10: the owner read the Actions history; the result is in section 3k. It narrows the "NOT VERIFIED" limit in the first row, it does not remove it.

Update 2026-11-11 (owner instruction, "yes please", to prepare the change): the one workflow change authorised so far. In `.github/workflows/tests.yml` `timeout-minutes` goes from 15 to 25 and nothing else in the file changes. Evidence (read from the Actions API, run 43029155542 on the P1-06c branch): the Python 3.11 job was cancelled at 15 min 17 s inside "Run tests" while 3.12 passed in 10 min 52 s, and the last twelve Tests runs took 7 to 14 minutes per job, so the limit sat on the edge. No test failed. This lifts the hold on workflow changes for this one change only; the other holds of section 7 (merge-commit runs on `main`, any other workflow edit) are unchanged.

### 3c. G5-03: Phase 0 approved with exceptions (owner decision, 2026-11-09)

The owner approved Phase 0 as closed with the exceptions below, in chat on 2026-11-09, after the merge of PR #39 (`8e0f268`). The decision is on `main` at `8e0f268`; the commit that records it changes documentation only. This entry records the owner's statement; the repo cannot show the decision itself (NOT VERIFIED from the repo).

What the approval means: the baseline and its limits are documented. It does **not** say the model is validated, calibrated or correct, it changes no number, and it does **not** authorise Phase 1 (G5-04). Any later change to the model needs its own authorisation.

Exceptions carried into Phase 1:

1. The 19 cross-module disagreement rows (`docs/cross_module_disagreements.md`), deferred pending DOK-ING. Row 9 (the tail-gas default) is still an open owner decision.
2. The DOK-ING-dependent items in `docs/dok_ing_dependent_items.md`, including those no RFI #2 question asks.
3. The wording residue in code comments and docstrings (G5-05; G5-12 point 4, see `docs/phase0_open_items.md`).
4. No Tests run on merge commits of `main` (G5-09; the indirect record in section 3b stands in for it).
5. The full feed-basis correction (cycle-1 fallback, `DEFAULT_DRY_FEED_KG_H`), not authorised.

### 3d. G5-04: Phase 1 authorisation (owner instruction, 2026-11-09)

On 2026-11-09 the owner wrote in chat "please start phase 1", after reading the draft Phase 1 task list (kept outside the repo). The instruction did not name tasks. **It is read as authorising the four tasks that the draft recommended starting with, in this order:** P1-01 (operating-point study, read-only; "aligned with about 50 kg/day" read as a scenario study that changes no default), P1-02 (wording residue), P1-03 (declare the two undeclared reads) and P1-07 (second request to DOK-ING for the items no RFI #2 question asks). None of the four changes a persisted number. This reading is Claude's; the owner is asked to confirm or correct it when reviewing this change. This entry records the owner's statement; the repo cannot show it (NOT VERIFIED from the repo).

Not authorised: every other Phase 1 task (P1-04, P1-05, P1-06, P1-08 to P1-10 of the draft), applying any provisional-answer-sheet value, changing a default, and CI or workflow changes. The Phase 1 rules (one task per PR; a before / after table and a Gate 4 scope statement for any change that can move a number; nothing tuned; Assumed labels) apply to each task.

### 3e. Phase 1 extension: literature-informed values (owner instruction, 2026-11-09)

After the P1-07 draft, the owner wrote in chat that DOK-ING's answers may take long, that the project should proceed with the closest realistic values from other projects and reliable figures instead of leaving parameters empty, and that DOK-ING's data will replace them when available; and then, offered a list of five items, "all of 1-5 in this order". **Read as authorising five further tasks, one PR each, in this order:** P1-11 (heat-recovery fractions), P1-12 (HB-010 membrane selectivity and HB-014/016 carrier kinetics), P1-13 (FE-003 minimum and maximum feed rate), P1-14 (HB-007 liquid-carrier split as an explicit scenario parameter, not one chosen number), P1-15 (EU-008 and HB-003 published as `Estimated` ratings next to the registry figures, registry rows untouched). The owner's statement is recorded here; the repo cannot show it (NOT VERIFIED from the repo).

Conditions that apply to all five (stated by Claude when the list was offered; the owner proceeded on them): every value taken from literature or another plant is labelled `Assumed` (literature-informed) with its source and range; none becomes Confirmed or "validated" without a DOK-ING source line; a source that cannot be found is recorded as not found, and the value is not invented; the Phase 1 rules (before / after table and Gate 4 scope statement for any change that can move a number; nothing tuned) apply. Not authorised by this entry: the larger drivers (gasifying agent, feed composition, tail-gas default), which stay scenario work until the owner decides separately, and every item listed in section 7.

### 3f. Task P1-04 (owner instruction, 2026-11-09)

After the five tasks of section 3e were merged, the owner was offered the list of tasks that do not wait for DOK-ING and wrote "start please". **Read as authorising P1-04 only** (the first item of the recommendation made in the same reply: the two safety items of G5-08, no number changes). P1-05 (number-changing fixes) and P1-06 (tail-gas default decision) still need the owner's own authorisation. This reading is Claude's; the owner is asked to confirm or correct it.

### 3g. Task P1-05 parts (a) and (b) (owner instruction, 2026-11-10)

The owner answered "yes please" to the reply that proposed starting P1-05 with parts (a) and (b), after the measured effect of each had been stated in chat. **Read as authorising P1-05(a) (one hydrogen LHV) and P1-05(b) (water molar mass from the atomic masses), as two PRs, (a) first.** P1-05(c) (feed-basis correction) and P1-05(d) (carbon-black alignment) and P1-06 stay unauthorised. Claude's choice inside (a): the single value is 10.8 MJ/Nm3 (EU-006's stated basis, +0.1 % above 241.826 kJ/mol / 0.022414 = 10.789), because it moves the fewest persisted entries (2 of 124, +0.0745 %); 10.783 would have moved 6, by up to 0.38 %. The owner is asked to confirm or correct that choice.

### 3h. Task P1-05(d) (owner instruction, 2026-11-10)

The owner answered "yes please: I'd take (d) before (c). It is the smaller of the two" to the reply that listed (c) and (d) as the remaining P1-05 parts. **Read as authorising P1-05(d) only**: the carbon black in the Circularity section of the app, `circularity.py` and the static GA-008 / GA-010 equipment fills is the engine's derived value (`(GA-001, CarbonAccounting)`, 2.013 kg/h at the default), no longer the legacy 5 % rule (1.875 kg/h on the same 37.503 kg/h dry feed). P1-05(c), P1-06 and everything else stay unauthorised.

Gate 4 scope: **no engine entry changes** (no model, constant or persisted key is touched; the four persisted-snapshot fixtures compare unchanged). What moves is static: `circularity_summary()` carbon black 1.875 -> 2.013 kg/h, its revenue 0.750 -> 0.805 EUR/h, the diversion fraction 15.00 -> 15.37 %; the GA-008 fill "~1.875" -> "~2.013" and the GA-010 fill ">=1.78" -> ">=1.91" kg/h (with their remarks); two cells of the provenance worksheet (the fill values; no origin answer touched) and the overlay's hash and timestamp; the app's Circularity captions. Ash is untouched. The Tab 4 cards already showed the engine value.

How: a pinned fraction `circularity.ENGINE_CARBON_BLACK_FRACTION_OF_DRY_FEED` (0.0536807889, the converged engine value / dry feed at the default feed and tail-gas mode) because a static module cannot import the live engine; `tests/test_p1_05d_carbon_black.py` fails if it drifts from the engine. Simplifications, stated in the code: it is the default-mode value (`heat_only`, other conversions or splits give other values), and scaling it linearly with an entered feed is approximate (the engine gives 2.416 kg/h at +30 % feed against 2.617 linear). The legacy rule stays in `gasifier_mass_balance.py` and as the engine's cross-check (`carbon_black_rule_kg_h` is kept in the summary). Not changed: the feed-basis question of the static default 41.67 (that is P1-05(c)).

### 3i. Task P1-05(c) (owner instruction, 2026-11-10)

The owner answered the reply that listed P1-05(c) as the larger remaining part with "do this: P1-05(c), the full feed-basis correction ... I need your explicit go-ahead, and I'd state the measured effect first". **Read as authorising P1-05(c) only.** P1-06 and everything else stay unauthorised.

Change: `gasifier_mass_balance.DEFAULT_DRY_FEED_KG_H` is now the dry solids, 41.67 x (1 - 0.10) = 37.503 kg/h (it held the as-received 41.67); the as-received rate has its own name `DEFAULT_AS_RECEIVED_FEED_KG_H`, and the 10 % moisture is `DEFAULT_INLET_MOISTURE_FRACTION` (a static copy of `fe_feed_handling.FE005_INLET_MOISTURE_FRACTION`, equality pinned). GA-001's cycle-1 fallback and the default of `byproduct_mass_flows()` follow the constant. Nothing else in the engine is touched.

Measured effect (against the tip of the P1-05(d) branch, be7a92a): **converged GA-001 outputs do not move** (30 cycles: zero GA-001 entries differ). Cycle 1: GA-001 dry gas flow 87.4 -> 78.7 Nm3/h (-10 %), 34 entries move. The default 5-cycle run: 50 entries move (the GA-001 dry flow 102.73 -> 102.71), mainly through lagged and accumulating states (e.g. the PEM fuel-cell fuel use and the H2 budget go 0 -> 8.7 and 6.8 kW); the 20-cycle runs move 16 (default) and 13 (heat_only) entries, the 30-cycle default run 8 (HB-013 storage, HB-018 dispensing, EU-CHP dispatch, EU-008 cooling supply and mirrors). The default five-cycle storage state no longer sits on the empty-tank clamp (0.133 kg of H2 created by the clamp before, 0 now; test_balance_audit.py edited). Static: `byproduct_mass_flows()` default 4.167 / 2.0835 -> 3.7503 / 1.87515 kg/h.

Gate 4 scope: 51 persisted keys can differ from the pre-change snapshot in the five runs pinned by `tests/test_p1_05c_feed_basis.py`; 46 were already excluded by earlier decisions and five are added to `tests/_intentional_changes.py` (`P1_05C_KEYS`). The pin test compares against a new committed fixture of the pre-change snapshot (`tests/fixtures/snapshot_origin_main_be7a92a.json.gz`: default 1/5/20/30 and heat_only 20 cycles) and proves attribution: with the constant put back to 41.67 the snapshot equals the fixture in every entry. Not changed: P1-06 (the tail-gas default), the feed composition and ash fraction, and the data-replacement plumbing.

### 3j. Task P1-06 (owner decision, 2026-11-10)

The owner asked for P1-06 and, when asked which default to use, chose `heat_only`. **Read as authorising P1-06 only: the default of `GA-001-INPUT tail_gas_mode` becomes `heat_only`.** Nothing was tuned; no other default, equation or registry value changes.

Measured effect (against origin/main after P1-05(c)): headline hydrogen 78.0 -> 55.7 kg/day (3.251 -> 2.323 kg/h; still +11 % over DOK-ING's about 50 and +25 % over the registry's 44.4); 49 to 50 of the 124 persisted entries move in the default 5-, 20- and 30-cycle runs and 5 on cycle 1. The new default snapshot equals the previous explicit `heat_only` snapshot in every entry except the switch's own note. The plant heat deficit is the documented -18 kW; the energy balance does not close. Because the tail gas is no longer recycled the engine's carbon black is exactly 4.5 % of the dry feed, so the static pinned fraction of P1-05(d) follows (`circularity.ENGINE_CARBON_BLACK_FRACTION_OF_DRY_FEED` 0.0537 -> 0.045): carbon black 2.013 -> 1.688 kg/h, its revenue 0.805 -> 0.675 EUR/h, diversion 15.37 -> 14.5 %, GA-008 fill ~2.013 -> ~1.688, GA-010 fill >=1.91 -> >=1.60 kg/h (two cells of the provenance worksheet and the overlay hash regenerated; no origin answer touched).

Gate 4 scope: the existing test modules were written and measured on `regasify`, so `tests/conftest.py` restores that default for them (module scope; a module sets `REAL_TAIL_GAS_DEFAULT = True` to opt out). `tests/test_p1_06_tail_gas_default.py` and `tests/test_p1_05d_carbon_black.py` run on the real default. The new test compares against a committed pre-flip fixture (`tests/fixtures/snapshot_origin_main_8282f4a.json.gz`) and proves attribution: with the old default put back the snapshot equals the fixture in every entry. The switch's own entry (its note) is added to `tests/_intentional_changes.py`. This means the older Gate 4 comparisons exercise the `regasify` path under the name "default"; the real default is covered by the new test and by the explicit `heat_only` runs those modules already contained.

Deliberate test edits: `test_feed_basis.py` (static values compared with a `heat_only` snapshot), `test_transient_tab.py` (under `heat_only` there is no recycle delay, so all three scenarios show the overlap caption; the non-vacuity check allows that), `test_design_basis_ledger.py` (the committed ledger files are generated on the real default), `test_p1_05b`/`05c` (the switch entry is skipped), `test_p1_05d` (new numbers).

### 3k. CI history of the Tests workflow (owner reading of the Actions page, 2026-11-10)

Source: the owner opened the repository's Actions page, selected the Tests workflow, searched `is:failure` and sent screenshots; the repo cannot show these runs (NOT VERIFIED from the repo). The numbers below are the owner's readings, recorded as stated.

| Item | Reading |
|---|---|
| Failed Tests runs, whole history | 4: run #52 (PR #49, P1-15), run #23 (PR #21, ledger fixes A3/A3b/A3c), runs #3 and #4 (PR #2, Dynamics layer and Transient What-If tab) |
| PRs #29 and #31-#54 | no failed Tests run other than PR #49's; PR #54 shown green on 3.11 and 3.12 (run #57, 15 m 1 s) |
| PR #49, run #52 | failed after 52 s with the annotation "Internal server error" and no test job started (a GitHub infrastructure error, not a test result); re-run on 2026-11-10: success on 3.11 (7 m 49 s) and 3.12 (8 m 45 s), total 8 m 52 s |
| PRs #21 and #2 | outside the range; their failed runs are listed only for completeness, their later results were not read |

Limits: the `is:failure` filter shows no cancelled runs and says nothing about a PR that never ran the workflow; a missing failure is not a recorded success for each PR. The "Continuous Simulation Cycle" workflow was not read. No Tests run exists on a merge commit of `main` (section 3b); that gap and the hold on CI changes are unchanged. PR #55 (P1-06) was not read.

### 3l. Task P1-06b: the real tail-gas default is the test default (owner instruction, 2026-11-11)

The owner asked for all work that does not wait for DOK-ING; this is the first item, **read as authorising P1-06b only** (tests only; no model code, no persisted number, no registry value changes). The blind spot named in section 3j is narrowed: `tests/conftest.py` used to restore the old `regasify` default for every module except two. It now does so only for modules that declare `LEGACY_REGASIFY_DEFAULT = True`; every other module runs on the real default (`heat_only`).

Measurement before the change (container, Python 3.13, fixture switched off, nothing else changed): 43 failures in 12 modules, 941 passed, 4 skipped; one of the 43 is the known container-only file-listing-order failure. The 12 modules declare the marker, each with its reason on the same line: `test_gasifying_agent` (12 failures), `test_p1_05c_feed_basis` (8), `test_balance_audit` (5), `test_plant_heat_integration` (4, one the known one), `test_disagreement_rows` (3), `test_tail_gas_mode`, `test_p1_05b_water_molar_mass`, `test_p1_05a_h2_lhv`, `test_feed_basis` (2 each), `test_operating_point_study`, `test_lohc_split_scenarios`, `test_closure_scenarios` (1 each). So the suite exercises the real default everywhere else, and these 12 modules remain on `regasify` by declaration: converting them means re-measuring their pins or fixtures on `heat_only` and is not done here. The `REAL_TAIL_GAS_DEFAULT` marker of P1-06 is removed (it is the default behaviour now). One assertion changed: `test_tail_gas_mode` no longer pins `TAIL_GAS_MODE_DEFAULT == "regasify"` (in that module it is the patched value; the real default is pinned by `test_p1_06_tail_gas_default.py`).

### 3m. Task P1-06c: `test_balance_audit` and `test_plant_heat_integration` on the real default (owner instruction, 2026-11-11)

Second item of the owner's "all work that does not wait for DOK-ING"; **read as authorising this conversion only** (tests and this record; no model code, no persisted number). The two modules no longer declare `LEGACY_REGASIFY_DEFAULT`; 10 modules still do (section 3l minus these two). Where a test is about the recycle it now says `regasify` explicitly through the engine override; the others run on `heat_only`.

- `test_balance_audit.py`: a new fixture `snaps_regasify` (override `tail_gas_mode = regasify`) serves the recycle tests (`a_wrong_recycle_is_not_silently_absorbed`, `active_recycle_without_the_previous_cycle_cannot_be_evaluated`) and the pre-P1-06 carbon-identity and storage-clamp tests, whose assertions are unchanged. Two tests are new on the real default: the carbon identity closes with no recycle term (`unconverted_from_recycle_kg_h == 0`, carbon black 4.5 % of the dry feed, 0.1875 kg/h below the old 5 % rule), and the storage clamp. **Finding, not a fix:** on the real default the default five-cycle state empties the H2 tank (outflow 3.42 kg against 0.54 kg stored plus 2.33 kg inflow), so the lower clamp creates 0.5601 kg of H2 and the audit's verdict is "does not close"; the 20-cycle state is unaffected. Before P1-05(c) the old default also sat on the clamp (0.133 kg), so this is a property of the 5-cycle start-up state, not of the tail-gas change alone.
- `test_plant_heat_integration.py`: the `runs` fixture gains an explicit `regasify` run next to `default` (real default) and `heat_only`. The fixture comparisons now map `regasify` to the pre-P1-06 `default|20` entries (the check that the regasify path is unchanged is therefore real, not the default path under another name), the mode-labelled assertions use the explicit mode, and the level-mismatch test is measured on `regasify` because under `heat_only` the counted flue gas lifts the matched heat to 47.6 kW (its "< 20 kW" claim is about `regasify`).

### 3n. Task P1-06d: `test_disagreement_rows` on the real default (owner instruction, 2026-11-11)

Third item of "all work that does not wait for DOK-ING"; **read as authorising this conversion only** (a test, this record and a dated note in `docs/cross_module_disagreements.md`; no model code, no persisted number). The module no longer declares `LEGACY_REGASIFY_DEFAULT` (9 modules still do). Its three figure tests run for both modes: the real default (`heat_only`, new numbers) and an explicit `regasify` run that keeps the 2026-11-06 numbers unchanged. Measured on the real default, 30 cycles: syngas H2 24.79 vol% (27.45 on `regasify`), N2 39.24 (39.64), flow 78.79 Nm3/h (102.75), PSA feed H2 36.1 (38.1), hydrogen 55.7 kg/day (78.0), PSA recovery 77.0 % (78.8), EU-008 demand 39.98 kW (51.99), HB-003 hot / cold 5.73 / 8.45 kW (7.38 / 10.72), carbon black 1.688 kg/h (2.013). The G5-07 dispositions (defer all pending DOK-ING) are unchanged: every difference with the registry remains. The G5-07 file itself keeps its `regasify` figures as dated records and carries an update note with the `heat_only` ones.

### 3o. Task P1-06e: `test_closure_scenarios` and `test_operating_point_study` on the real default (owner instruction, 2026-11-11)

Fourth item of "all work that does not wait for DOK-ING"; **read as authorising this conversion only** (two tests and this record; no model code, no persisted number, the committed baseline `docs/balance_audit_baseline.json` is untouched). The two modules no longer declare `LEGACY_REGASIFY_DEFAULT` (7 modules still do). No test function was removed or renamed; one parametrisation case was added.

- `test_closure_scenarios.py`: the module's "S0 current" case is now the real default (`| heat_only`), compared with the committed baseline entry of that name (the baseline already holds all 30 cases in both modes, so the drift test now checks the real default against it); the `regasify` S0 case is built explicitly and checked against its own baseline entry as before. The "every persisted entry equals the pre-change fixture" test runs three cases: explicit `regasify` against the fixture's `default|20` entries (the check that the regasify path is unchanged is real), explicit `heat_only`, and the real default against `heat_only|20`.
- `test_operating_point_study.py`: the starting point of `test_default_point_reproduces_the_engine_default_and_overrides_do_not_leak` is now `heat_only` (55.7 kg/day, the engine default); the 78.0 kg/day `regasify` case of `docs/tail_gas_heat.md` is run explicitly and still pinned; the "overrides do not leak" check is unchanged in kind (a plain default run after the study cases is still the default one).

### 3p. Task P1-06f: `test_tail_gas_mode`, `test_p1_05a_h2_lhv` and `test_lohc_split_scenarios` on the real default; one script fixed (owner instruction, 2026-11-11)

Fifth item of "all work that does not wait for DOK-ING"; **read as authorising this conversion only**. The three modules no longer declare `LEGACY_REGASIFY_DEFAULT` (4 modules still do: `test_gasifying_agent`, `test_p1_05c_feed_basis`, `test_p1_05b_water_molar_mass`, `test_feed_basis`). No model code and no persisted number change; **one script changes**, see the first bullet.

- **Script found mislabelled by the conversion (fixed):** `scripts/run_lohc_split_scenarios.py::live_psa_h2_kg_h` ran the label `regasify` with NO override, because `regasify` was the engine default when it was written. Since P1-06 it therefore ran `heat_only` under the `regasify` label (the "regasify" row of the study would have shown 2.32 kg/h instead of 3.25). It now always sets the mode explicitly; `docs/lohc_split_scenarios.md` (3.251 kg/h `regasify`, 2.323 `heat_only`) is reproduced again and was never wrong. A search of `scripts/`, `python/` and `app.py` for the same pattern (a mode label that means "no override") found no other instance.
- `test_tail_gas_mode.py`: two new explicit `regasify` runs (5 and 30 cycles) make the comparison with the pre-change fixture real (its entries are the `regasify` default of that time); the real-default runs stay. `test_default_is_regasify_and_...` is split into `test_default_is_heat_only_and_...` (value, note "since P1-06", no recycle) and `test_regasify_recycles_and_...` (no test removed; one renamed and one added).
- `test_p1_05a_h2_lhv.py`: its snapshot is built with `regasify` explicitly, because it is compared with the 701de71 fixture's `default|20` entries; the pins are unchanged.
- `test_lohc_split_scenarios.py`: the 78.0 kg/day `regasify` hydrogen is pinned as before and the 55.7 kg/day `heat_only` one is added.

### 3q. Task P1-06g: `test_p1_05b_water_molar_mass`, `test_p1_05c_feed_basis` and `test_feed_basis` on the real default (owner instruction, 2026-11-11)

Sixth item of "all work that does not wait for DOK-ING"; **read as authorising this conversion only** (three tests and this record; no model code, no script, no persisted number, no fixture). The three modules no longer declare `LEGACY_REGASIFY_DEFAULT`; **one module still does: `test_gasifying_agent`**. No test function is removed or renamed; one is added and one is parametrised (36 to 38 test cases).

- `test_p1_05b_water_molar_mass.py` and `test_p1_05c_feed_basis.py`: their runs labelled "default" are compared with pre-change fixtures whose "default" entries are the `regasify` default of that time. The label now selects `regasify` explicitly through the engine override (one line each); pins, moved-entry counts and tolerances are unchanged. Their `heat_only` runs already covered the mode that is now the real default.
- `test_feed_basis.py`: the module's snapshots are the real default. The derived-carbon-black recomputation runs for both modes (`heat_only`: no recycle term; `regasify`: the original case). The three-carbon-black known-limitation test is kept on explicit `regasify` (5 % rule on the live feed < derived < 5 % rule on 41.67) and a new test pins the real default, where the ordering differs: derived (exactly 4.5 % of the dry feed, 1.688 kg/h) < 1.875 < 2.0835.

## 4. Gate 5 criteria: status as of this record

| ID | Criterion | Status |
|---|---|---|
| G5-01 | Owner review of A3/A5/A10/W1 recorded | recorded 9 Nov (section 3a) |
| G5-02 | Gates 1-4 restated on the closing commit | refreshed 9 Nov on `365f8b5` (section 2a). Commits after it (`#38`, `#39` and the G5-03 record) change documentation only; the only later run is the owner's full suite on the PR #39 branch (`fd9ba34`): 913 passed, 0 failed, 4 skipped on Python 3.14 (owner's report). A CI run on the closing commit is not recorded (G5-09) |
| G5-03 | "Phase 0 approved" decision recorded | recorded 9 Nov: approved with exceptions (section 3c) |
| G5-04 | Phase 1 authorisation is a separate act | given 9 Nov for four named tasks only (section 3d); everything else in Phase 1 stays unauthorised |
| G5-05 | No assumption presented as confirmed or validated | residue list in `docs/phase0_open_items.md`; owner accepted it 6 Nov |
| G5-06 | Feed-basis disposition | decided and implemented (narrow); documented limits remain |
| G5-07 | Cross-module disagreements listed with dispositions | list in repo; reproduction script merged (PR #32); all rows deferred pending DOK-ING (owner, 6 Nov) |
| G5-08 | Open items each have a disposition | dispositions recorded (owner, 6 Nov) |
| G5-09 | CI green on the closing commit | **accepted as an exception, not a pass**: indirect record (owner, 9 Nov; section 3b). No Tests run exists on a merge commit of `main` |
| G5-10 | Benchmark screen reviewed | screen in `docs/benchmark_msw_gasification.md`; owner dispositions recorded (section 6 of that file); deeper source reading still open |
| G5-11 | DOK-ING-dependent items listed; RFI #2 status recorded | list in `docs/dok_ing_dependent_items.md` (headline values mapped to RFI #2 questions; items no question asks listed as a gap); RFI #2 status in section 5 |
| G5-12 | No external validation claimed | refreshed 6 Nov: no validation claim found; 4 wording points fixed in code text, 1 recorded as a limitation |
| G5-13 | Phase 0 / Phase 1 boundary written down | accepted as final (owner, 6 Nov); wording in `docs/phase0_open_items.md` |
| G5-14 | Disposition of A1 and A4.1 | recorded (section 3) |
| G5-15 | In-repo gate record | this document, once accepted |

Task P1-15 (authorised in section 3e): `("HB-003","DutyEstimate")` is published as Estimated next to the registry 5 kW; EU-008 already published its Estimated recommendation beside the registry 20 kW, so it needed no code change. Persisted keys 123 to 124; no old entry moved; the registry is untouched.

## 5. RFI #2 status

- DOK-ING's first RFI (17 questions) was answered earlier (`data/dokink_rfi_answers.md`).
- RFI #2 full list: `docs/rfi2_dokink.md`, 24 questions in sections A-G. It was **not sent** in this form.
- A **short form** (10 points: gasifying agent, oxygen supply, carrier loop, air and steam flows, feed wet/dry basis, external energy, PSA recovery, carbon black and char, ash and tar, preheat temperatures) was sent by the owner to DOK-ING on **2026-11-06**. This is the owner's statement; the repo cannot show it (NOT VERIFIED from the repo).
- **No reply has been received.** A provisional answer sheet (literature and other-plant experience) exists outside the repo. No value from it is applied to the model; applying values is Phase 1.

## 6. Waiting on DOK-ING

G5-07 dispositions (rows 1-4 share one cause, the gasifying agent); the feed wet/dry basis (G5-06); the cooling tower rating (EU-008); the HB-003 duty; the primary air flow; the PSA recovery; the tail-gas use. Until answers arrive these stay Assumed or Unverified (registry).

## 7. Not authorised

Phase 1 except the four tasks of section 3d, the five of section 3e, P1-04 of section 3f, P1-05(a)/(b) of section 3g and P1-05(d) of section 3h P1-05(c) of section 3i and P1-06 of section 3j and P1-06b of section 3l and P1-06c of section 3m and P1-06d of section 3n and P1-06e of section 3o and P1-06f of section 3p and P1-06g of section 3q; P0-T1; CI or workflow changes; A4.2 to A4.4 (A4.1 is held); applying any answer-sheet value to the model.

## 8. Where the measured limits are

`CLAUDE.md` section "Known limitations"; `docs/balance_closure_audit.md`; `docs/tail_gas_heat.md`; `docs/carbon_bookkeeping.md`; `docs/gasifying_agent_study.md`; `docs/master_open_questions.md`; `docs/design_basis_ledger.md`. No plant data exists; nothing in the model is calibrated or validated against DOK-ING or any plant.
