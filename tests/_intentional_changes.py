"""Persisted entries that the Gate 4 'equals origin/main' comparisons skip ON PURPOSE, each with the decision that changed it.

The 701de71 fixture is not edited (no silent refresh). A key listed here is excluded from those comparisons and is instead pinned by its own test
(tests/test_hb010_separation.py), so the exclusion cannot widen without a visible edit of this file."""
INTENTIONAL = {
    "HB-010|Separation": "Phase 1 task P1-12 (owner decision 2026-11-09): Missing -> Estimated first-pass purity, product flow and held recovery",
    "EU-CHP|Dispatch": "Phase 1 task P1-05(a): one H2 LHV (10.8) -> total_syngas_kw and wgs_psa_claim_kw +0.0745 %; pinned by tests/test_p1_05a_h2_lhv.py",
    "SA-006|Reading": "Phase 1 task P1-05(a): the syngas LHV reading +0.0745 %; pinned by tests/test_p1_05a_h2_lhv.py",
}
