"""Persisted entries that the Gate 4 'equals origin/main' comparisons skip ON PURPOSE, each with the decision that changed it.

The 701de71 fixture is not edited (no silent refresh). A key listed here is excluded from those comparisons and is instead pinned by its own test
(tests/test_hb010_separation.py), so the exclusion cannot widen without a visible edit of this file."""
INTENTIONAL = {
    "HB-010|Separation": "Phase 1 task P1-12 (owner decision 2026-11-09): Missing -> Estimated first-pass purity, product flow and held recovery",
}
