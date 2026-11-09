# Phase 0 gate record

**Status: Phase 0 is closed WITH EXCEPTIONS by the owner's decision of 2026-11-09 (G5-03, section 3c). Phase 1 is NOT authorised (G5-04).** The approval says the baseline and its limits are documented; it does not say the model is validated, calibrated or correct. The Gate 5 criteria (G5-01 to G5-15) were adopted as working proposals; the owner accepted each disposition recorded below, and G5-09 is an exception, not a pass.

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

### 3c. G5-03: Phase 0 approved with exceptions (owner decision, 2026-11-09)

The owner approved Phase 0 as closed with the exceptions below, in chat on 2026-11-09, after the merge of PR #39 (`8e0f268`). The decision is on `main` at `8e0f268`; the commit that records it changes documentation only. This entry records the owner's statement; the repo cannot show the decision itself (NOT VERIFIED from the repo).

What the approval means: the baseline and its limits are documented. It does **not** say the model is validated, calibrated or correct, it changes no number, and it does **not** authorise Phase 1 (G5-04). Any later change to the model needs its own authorisation.

Exceptions carried into Phase 1:

1. The 19 cross-module disagreement rows (`docs/cross_module_disagreements.md`), deferred pending DOK-ING. Row 9 (the tail-gas default) is still an open owner decision.
2. The DOK-ING-dependent items in `docs/dok_ing_dependent_items.md`, including those no RFI #2 question asks.
3. The wording residue in code comments and docstrings (G5-05; G5-12 point 4, see `docs/phase0_open_items.md`).
4. No Tests run on merge commits of `main` (G5-09; the indirect record in section 3b stands in for it).
5. The full feed-basis correction (cycle-1 fallback, `DEFAULT_DRY_FEED_KG_H`), not authorised.

## 4. Gate 5 criteria: status as of this record

| ID | Criterion | Status |
|---|---|---|
| G5-01 | Owner review of A3/A5/A10/W1 recorded | recorded 9 Nov (section 3a) |
| G5-02 | Gates 1-4 restated on the closing commit | refreshed 9 Nov on `365f8b5` (section 2a). Commits after it (`#38`, `#39` and the G5-03 record) change documentation only; the only later run is the owner's full suite on the PR #39 branch (`fd9ba34`): 913 passed, 0 failed, 4 skipped on Python 3.14 (owner's report). A CI run on the closing commit is not recorded (G5-09) |
| G5-03 | "Phase 0 approved" decision recorded | recorded 9 Nov: approved with exceptions (section 3c) |
| G5-04 | Phase 1 authorisation is a separate act | not given |
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

## 5. RFI #2 status

- DOK-ING's first RFI (17 questions) was answered earlier (`data/dokink_rfi_answers.md`).
- RFI #2 full list: `docs/rfi2_dokink.md`, 24 questions in sections A-G. It was **not sent** in this form.
- A **short form** (10 points: gasifying agent, oxygen supply, carrier loop, air and steam flows, feed wet/dry basis, external energy, PSA recovery, carbon black and char, ash and tar, preheat temperatures) was sent by the owner to DOK-ING on **2026-11-06**. This is the owner's statement; the repo cannot show it (NOT VERIFIED from the repo).
- **No reply has been received.** A provisional answer sheet (literature and other-plant experience) exists outside the repo. No value from it is applied to the model; applying values is Phase 1.

## 6. Waiting on DOK-ING

G5-07 dispositions (rows 1-4 share one cause, the gasifying agent); the feed wet/dry basis (G5-06); the cooling tower rating (EU-008); the HB-003 duty; the primary air flow; the PSA recovery; the tail-gas use. Until answers arrive these stay Assumed or Unverified (registry).

## 7. Not authorised

Phase 1; P0-T1; CI or workflow changes; A4.2 to A4.4 (A4.1 is held); the full feed-basis correction; applying any answer-sheet value to the model.

## 8. Where the measured limits are

`CLAUDE.md` section "Known limitations"; `docs/balance_closure_audit.md`; `docs/tail_gas_heat.md`; `docs/carbon_bookkeeping.md`; `docs/gasifying_agent_study.md`; `docs/master_open_questions.md`; `docs/design_basis_ledger.md`. No plant data exists; nothing in the model is calibrated or validated against DOK-ING or any plant.
