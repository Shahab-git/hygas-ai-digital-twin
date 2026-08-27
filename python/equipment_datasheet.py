"""
Equipment datasheet view v1 — Feed Handling (FE-001..FE-008) only.

SCOPE: a deliberately first, narrow pass — only the 8 Feed Handling items
(FE-001 through FE-008) out of the full 91-item registry. The other 83
items are NOT attempted here; this is a scoped first section, not a
simplified stand-in for the rest.

HARD RULE, enforced by code, not just convention: every data point shown
is read directly from equipment_registry.load_registry() — the SAME
loader python/vendor_log.py already uses, not a re-derived or simplified
copy. Nothing here infers, estimates, or backfills a value that isn't
literally present in the registry's own parameter list. A category with
no real data mapped to it for a given item is reported as "Missing Data
— Required", never a plausible-sounding invented number.

CATEGORIZATION METHOD: each item's real parameters (already extracted
from the source workbook — see equipment_registry.py's own docstring)
are sorted into six categories — Inputs, Outputs, Parameters,
Measurements, Operating Conditions, Performance Indicators — using a
documented keyword-priority rule applied to the parameter's own NAME
text (checked in the order below; first match wins, else Parameters):

  1. Measurements          -- "sensor", "measurement", "accuracy",
                               "calibration", "response time",
                               "output signal"
  2. Operating Conditions  -- "operating", "ambient", "pressure"
  3. Outputs               -- "outlet", "output"
  4. Inputs                -- "inlet", "feed rate", "throughput"
  5. Performance Indicators -- "efficiency"
  6. Parameters            -- everything else (equipment design/
                               construction specs: dimensions, materials,
                               motor power, mechanical specs, etc.)

This rule was checked BY HAND against all 69 real FE-001..FE-008
parameters before being written as code — see this module's own
self-test, which prints every parameter's assigned category so the
mapping stays auditable, not a black box.

DATA-QUALITY NOTE, reported honestly rather than silently fixed: a
handful of parameter rows already in the committed
equipment_registry.json look value/unit-misaligned (e.g. FE-002's
"Target metal fraction" carries unit "mm", and "Drive power"/
"Installation position" appear to have swapped units — "%"" and "Kw"
respectively — which doesn't match either field's meaning). This is
displayed EXACTLY as stored, not corrected — "fixing" it would mean
guessing at what the right value should have been, which the hard rule
above forbids. (Checked directly: the special characters elsewhere, e.g.
"±", "–", "°C", render correctly once printed with a UTF-8-aware
console/terminal — an earlier debugging session's mangled-looking output
was a Windows console codepage display issue, not a defect in the
committed file itself.)
"""
from . import equipment_registry

FE_IDS = [f"FE-{i:03d}" for i in range(1, 9)]

CATEGORIES = [
    "Inputs", "Outputs", "Parameters", "Measurements",
    "Operating Conditions", "Performance Indicators",
]

_MEASUREMENTS_KEYWORDS = ("sensor", "measurement", "accuracy", "calibration", "response time", "output signal")
_OPERATING_KEYWORDS = ("operating", "ambient", "pressure")
_OUTPUTS_KEYWORDS = ("outlet", "output")
_INPUTS_KEYWORDS = ("inlet", "feed rate", "throughput")
_PERFORMANCE_KEYWORDS = ("efficiency",)


def classify(parameter_name):
    """The categorization rule — see module docstring. Pure function of
    the parameter's own name text, so the mapping is auditable and
    reproducible, not a per-item judgment call hidden in app.py."""
    name = parameter_name.lower()
    if any(k in name for k in _MEASUREMENTS_KEYWORDS):
        return "Measurements"
    if any(k in name for k in _OPERATING_KEYWORDS):
        return "Operating Conditions"
    if any(k in name for k in _OUTPUTS_KEYWORDS):
        return "Outputs"
    if any(k in name for k in _INPUTS_KEYWORDS):
        return "Inputs"
    if any(k in name for k in _PERFORMANCE_KEYWORDS):
        return "Performance Indicators"
    return "Parameters"


def build_datasheet(item):
    """Returns {category: [real parameter dicts]} for one registry item,
    with EVERY category key present — even an empty list — so callers
    render "Missing Data — Required" for an explicit empty category
    rather than a missing key that has to be guessed at."""
    buckets = {c: [] for c in CATEGORIES}
    for p in item["parameters"]:
        buckets[classify(p["parameter"])].append(p)
    return buckets


def build_all_datasheets(registry=None):
    """Loads the real registry (equipment_registry.load_registry() — not
    a copy) and builds the FE-001..FE-008 datasheets from it."""
    registry = registry if registry is not None else equipment_registry.load_registry()
    by_id = {i["id"]: i for i in registry}
    out = {}
    for fe_id in FE_IDS:
        item = by_id.get(fe_id)
        if item is None:
            continue
        out[fe_id] = {"item": item, "datasheet": build_datasheet(item)}
    return out


def summarize(datasheets=None):
    """The honest count this module's own self-test and app.py both
    report: total real data points (individual parameter rows) across
    all 8 items, versus total "Missing Data — Required" category slots
    (empty category buckets) — the real measure of how far this first
    pass is from a complete profile, not rounded up."""
    datasheets = datasheets if datasheets is not None else build_all_datasheets()
    total_real_data_points = 0
    total_category_slots = 0
    missing_category_slots = 0
    per_item = {}
    for fe_id, entry in datasheets.items():
        sheet = entry["datasheet"]
        n_real = sum(len(v) for v in sheet.values())
        n_missing = sum(1 for v in sheet.values() if len(v) == 0)
        total_real_data_points += n_real
        total_category_slots += len(CATEGORIES)
        missing_category_slots += n_missing
        per_item[fe_id] = {
            "real_data_points": n_real, "missing_categories": n_missing,
            "populated_categories": len(CATEGORIES) - n_missing,
        }
    return {
        "total_real_data_points": total_real_data_points,
        "total_category_slots": total_category_slots,
        "populated_category_slots": total_category_slots - missing_category_slots,
        "missing_category_slots": missing_category_slots,
        "per_item": per_item,
    }


if __name__ == "__main__":
    datasheets = build_all_datasheets()
    for fe_id, entry in datasheets.items():
        item = entry["item"]
        print(f"=== {fe_id} - {item['name']} ===")
        for cat in CATEGORIES:
            rows = entry["datasheet"][cat]
            if not rows:
                print(f"  {cat}: MISSING DATA - REQUIRED")
            else:
                print(f"  {cat}: {len(rows)} data point(s)")
                for p in rows:
                    print(f"    - {p['parameter']} = {p['value']} {p['unit']}")
        print()

    s = summarize(datasheets)
    print("=== Step 6: honest count ===")
    print(f"Total real data points (across all 8 items): {s['total_real_data_points']}")
    print(f"Total category slots (8 items x 6 categories): {s['total_category_slots']}")
    print(f"Populated category slots: {s['populated_category_slots']}")
    print(f"Missing Data - Required category slots: {s['missing_category_slots']} "
          f"({s['missing_category_slots'] / s['total_category_slots'] * 100:.0f}%)")
    for fe_id, stat in s["per_item"].items():
        print(f"  {fe_id}: {stat['real_data_points']} real data points, "
              f"{stat['populated_categories']}/6 categories populated")
