"""Simulation tab: the curated series of each plant section (Feed handling, Gasification, ...), read from a published snapshot.

CLASS: read-only reader of the unchanged quasi-steady engine's snapshot. SIMULATED values, Assumed inputs, nothing validated against plant
data. It adds no model, writes nothing and never reads the plant heat report or any PLANT key.

SECTIONS maps a section name to (prefixes of its registry ids, series). A series is (label, item id, category key, path inside the value
or None for a scalar, unit). `extract(snap, section)` returns {label: float or None}; None means the key is absent or Missing this cycle.

Numeric check (comment, project convention): every series resolves to a float in a plain build_live_snapshot(3) and the value equals the
snapshot's own entry (tests/test_sim_sections.py).
"""

SECTIONS = {
    "Feed Handling": (("FE",), (
        ("Hopper level (t)", "FE-001", "Inventory", "level_t", "t"),
        ("As-received feed (kg/h)", "FE-003", "Weighing", "confirmed_wet_feed_kg_h", "kg/h"),
        ("Shredder power (kW)", "FE-004", "ShredderPower", "power_kw", "kW"),
        ("Dry solids after dryer (kg/h)", "FE-005", "MoistureBalance", "dry_solids_kg_h", "kg/h"),
        ("Feed into gasifier (kg/h)", "FE-008", "Airlock", "feed_rate_kg_h", "kg/h"),
    )),
    "Gasification": (("GA",), (
        ("Dry syngas (Nm3/h)", "GA-001", "Outputs", "dry_flow_nm3_h", "Nm3/h"),
        ("H2 (mol% dry)", "GA-001", "Outputs", "H2_mol_pct_dry", "%"),
        ("CO (mol% dry)", "GA-001", "Outputs", "CO_mol_pct_dry", "%"),
        ("N2 (mol% dry)", "GA-001", "Outputs", "N2_mol_pct_dry", "%"),
        ("Carbon black (kg/h)", "GA-001", "CarbonAccounting", "carbon_black_kg_h", "kg/h"),
    )),
    "Gas Cleaning": (("GC",), (
        ("Quench cooling duty (kW)", "GC-004", "Cooling duty", None, "kW"),
        ("Clean syngas (Nm3/h)", "GC-013", "Gas", "dry_flow_nm3_h", "Nm3/h"),
        ("H2 after cleaning (mol% dry)", "GC-013", "Gas", "H2_mol_pct_dry", "%"),
        ("Fan hydraulic power (W)", "GC-013", "Fan power", "hydraulic_power_w", "W"),
        ("Condensate (m3/h)", "GC-015", "Condensate", "condensed_process_water_m3_h", "m3/h"),
    )),
    "Sensors & Analysers": (("SA",), (
        ("SA-001 reading (vol%)", "SA-001", "Reading", None, "vol%"),
        ("SA-002 reading (vol%)", "SA-002", "Reading", None, "vol%"),
        ("SA-003 reading (vol%)", "SA-003", "Reading", None, "vol%"),
        ("SA-005 N2 reading (vol%)", "SA-005", "Reading", None, "vol%"),
        ("SA-010 flow (Nm3/h)", "SA-010", "Reading", None, "Nm3/h"),
    )),
    "Hydrogen & BoP": (("HB",), (
        ("HTS CO conversion", "HB-001", "HTS", "X_hts", "fraction"),
        ("LTS relative conversion", "HB-004", "LTS", "X_lts_relative", "fraction"),
        ("PSA recovery", "HB-006", "PSA", "recovery", "fraction"),
        ("H2 to compressor (kg/h)", "HB-012", "Compressor", "h2_kg_h", "kg/h"),
        ("Compressor power (kW)", "HB-012", "Compressor", "power_kW", "kW"),
        ("H2 storage level (kg)", "HB-013", "Storage", "level_kg", "kg"),
    )),
    "Electrical & Utilities": (("EU",), (
        ("Cooling demand EU-008 (kW)", "EU-008", "CoolingSupply", "demand_kw", "kW"),
        ("Grid generation (kW)", "EU-009", "GridBalance", "generation_kw", "kW"),
        ("Grid consumption (kW)", "EU-009", "GridBalance", "consumption_kw", "kW"),
        ("UPS state of charge", "EU-010", "UPS", "soc_fraction", "fraction"),
        ("Fuel cell load (fraction)", "EU-006", "FuelCell", "load_factor", "fraction"),
    )),
    "Automation & AI": (("AI",), (
        ("Bed pressure drop (mbar)", "AI-003", "BedPressureDrop", None, "mbar"),
        ("Renewable availability (assumed)", "AI-001", "RenewableAvailability", "availability_fraction", "fraction"),
        ("Active modules", "AI-014", "OrchestrationState", "active_modules", "count"),
        ("Logged dry syngas (Nm3/h)", "AI-011", "LoggingStatus", "summary.ga_dry_flow_nm3_h", "Nm3/h"),
    )),
}


def _dig(value, path):
    cur = value
    for part in (path.split(".") if path else []):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def extract(snap, section):
    out = {}
    for label, item, cat, path, _unit in SECTIONS[section][1]:
        rec = snap.get((item, cat))
        v = None
        if rec and rec.get("status") != "Missing":
            v = _dig(rec.get("value"), path)
        out[label] = None if v is None or isinstance(v, bool) else float(v)
    return out


def extract_all(snap):
    return {s: extract(snap, s) for s in SECTIONS}


def units(section):
    return {label: unit for label, _i, _c, _p, unit in SECTIONS[section][1]}
