"""Persisted entries that the Gate 4 'equals origin/main' comparisons skip ON PURPOSE, each with the decision that changed it.

The 701de71 fixture is not edited (no silent refresh). A key listed here is excluded from those comparisons and is instead pinned by its own test
(tests/test_hb010_separation.py), so the exclusion cannot widen without a visible edit of this file."""
INTENTIONAL = {
    "HB-010|Separation": "Phase 1 task P1-12 (owner decision 2026-11-09): Missing -> Estimated first-pass purity, product flow and held recovery",
    "EU-CHP|Dispatch": "Phase 1 task P1-05(a): one H2 LHV (10.8) -> total_syngas_kw and wgs_psa_claim_kw +0.0745 %; pinned by tests/test_p1_05a_h2_lhv.py",
    "SA-006|Reading": "Phase 1 task P1-05(a): the syngas LHV reading +0.0745 %; pinned by tests/test_p1_05a_h2_lhv.py",
}

# Phase 1 task P1-05(b): the water molar mass is computed from the atomic masses (18.016, was the literal 18.015, 5.5e-5 lower). Every persisted entry below that carries a number derived
# from a water mass or mole count moves by at most 7e-5 relative (3.5e-4 in the heat_only energy report); pinned key by key, and attributed by re-running with M_H2O = 18.015, by
# tests/test_p1_05b_water_molar_mass.py.
P1_05B_KEYS = (
    "AI-004|EU-009-State-IfResized",           # value unchanged; its confidence_note quotes a moved number
    "AI-007|ScadaSnapshot",
    "AI-011|LoggingStatus",
    "EU-007|Flare",
    "EU-008|ConsumerAdequacy",
    "EU-008|CoolingSupply",
    "EU-008|RecommendedCapacityEstimate",
    "EU-009|GridBalance",
    "EU-010|UPS",
    "GA-001|CarbonAccounting",
    "GA-001|EnergyBalance",
    "GA-001|Outputs",
    "GC-001|Gas",
    "GC-003|Gas",
    "GC-004|Condensed water",
    "GC-004|Cooling duty",
    "GC-004|Gas",
    "GC-007|Blowdown",
    "GC-008|Blowdown",
    "GC-009|Blowdown",
    "GC-013|Fan power",
    "GC-013|Gas",
    "GC-015|Condensate",
    "GC-015|OperatingConditions",
    "HB-001|HTS",
    "HB-003|HeatExchanger",
    "HB-004|LTS",
    "HB-005|Steam",
    "HB-006|PSA",
    "HB-009|TailGas",
    "HB-010|Feed",
    "HB-010|SelectivityEstimate",
    "HB-012|Compressor",
    "HB-013|Storage",
    "HB-018|Dispensing",
    "PLANT|HeatIntegration",
    "SA-001|Reading",
    "SA-002|Reading",
    "SA-003|Reading",
    "SA-004|Reading",
    "SA-005|Reading",
    "SA-010|Reading",
    "WGS|Composition",
)
for _k in P1_05B_KEYS:
    INTENTIONAL[_k] = "Phase 1 task P1-05(b): water molar mass 18.016 (was 18.015); pinned by tests/test_p1_05b_water_molar_mass.py"

# Phase 1 task P1-05(c): the cycle-1 fallback of GA-001's dry feed is the DRY solids (37.503), not the as-received 41.67. Converged GA-001 outputs are unchanged; the start-up transient and
# everything that accumulates from it moves. Five keys not already excluded above are added here; the other keys that move are already excluded by an earlier decision and are pinned
# one by one, together with these, against the committed pre-change snapshot tests/fixtures/snapshot_origin_main_be7a92a.json.gz by tests/test_p1_05c_feed_basis.py.
P1_05C_KEYS = (
    "EU-006|FuelCell",
    "GA-001-INPUT|dry_feed_rate_kg_h",           # the confidence note quotes the constant
    "GA-001|AgentConsistency",
    "GA-001|OxygenCarrierCirculationEstimate",
    "HB-003|DutyEstimate",
)
for _k in P1_05C_KEYS:
    INTENTIONAL[_k] = "Phase 1 task P1-05(c): cycle-1 dry feed 37.503 (was 41.67 as-received); pinned by tests/test_p1_05c_feed_basis.py"
