# Phase 0 gate record

**Status: Phase 0 is NOT closed. Gate 5 has NOT passed.** None of the proposed Gate 5 criteria (G5-01 to G5-15) is formally approved as a criterion; the owner accepted G5-15, three amendments and a draft of the G5-13 boundary as proposals only.

Record date: 2026-11-06. Repository state described: `main` at `244eb39` (merge of PR #32). This file records decisions and facts; it makes none. Where a statement rests only on the owner's word, it says so. Where the repo cannot show something, it says NOT VERIFIED.

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
| G5-07 | list drafted; dispositions **on hold until DOK-ING replies** |
| G5-15 and three amendments; G5-13 boundary draft | accepted as proposals, not as approved criteria |
| G5-10 benchmark screen | proposed dispositions accepted (numbers unchanged, evidence made visible); screen added to the repo as a screen, not as validation |
| G5-12 wording scan | fix points 1, 2, 3, 5 (wording only, no number changes); point 4 (the word 'Confirmed' in app.py code comments for HB-006 55 % and 10 % inlet moisture) recorded as a known limitation |

## 4. Gate 5 criteria: status as of this record

| ID | Criterion | Status |
|---|---|---|
| G5-01 | Owner review of A3/A5/A10/W1 recorded | pending |
| G5-02 | Gates 1-4 restated on the closing commit | restated 6 Nov on `6b010de`; needs refresh on the closing commit |
| G5-03 | "Phase 0 approved" decision recorded | pending |
| G5-04 | Phase 1 authorisation is a separate act | not given |
| G5-05 | No assumption presented as confirmed or validated | partly met; residue list pending |
| G5-06 | Feed-basis disposition | decided and implemented (narrow); documented limits remain |
| G5-07 | Cross-module disagreements listed with dispositions | 19-row list drafted; reproduction script merged (PR #32); dispositions on hold |
| G5-08 | Open items each have a disposition | pending |
| G5-09 | CI green on the closing commit | partly met; manual run on `main` not done |
| G5-10 | Benchmark screen reviewed | screen in `docs/benchmark_msw_gasification.md`; owner dispositions recorded (section 6 of that file); deeper source reading still open |
| G5-11 | DOK-ING-dependent items listed; RFI #2 status recorded | RFI #2 status below; list pending |
| G5-12 | No external validation claimed | refreshed 6 Nov: no validation claim found; 4 wording points fixed in code text, 1 recorded as a limitation |
| G5-13 | Phase 0 / Phase 1 boundary written down | draft accepted as a proposal |
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
