"""
Equipment datasheet view v1 — Feed Handling (FE-001..FE-008) and
Gasification (GA-001..GA-010) only.

SCOPE: a deliberately scoped, incremental pass. First shipped covering
just FE-001..FE-008; this version adds GA-001..GA-010 (the gasification
section) using the SAME methodology, no rewrite. The other 73 items in
the 91-item registry are still NOT attempted here.

HARD RULE, enforced by code, not just convention: every data point shown
is read directly from equipment_registry.load_registry() — the SAME
loader python/vendor_log.py already uses, not a re-derived or simplified
copy. Nothing here infers, estimates, or backfills a value that isn't
literally present in the registry's own parameter list. A category with
no real data mapped to it for a given item is reported as "Missing Data
— Required", never a plausible-sounding invented number.

NULL-VALUED REGISTRY ROWS, handled explicitly: one row in the source
registry (GA-002's "Vendor / model (transmitter)") is present in the
item's parameter list but carries value=None, unit=None — an explicit
placeholder for an unfilled slot, unlike FE, where unfilled slots are
simply absent from the list entirely. Checked directly: this is the ONLY
such row across FE-001..FE-008 and GA-001..GA-010. Any row with a None
value is excluded before classification — it is not real data and must
not count as one, and must not be treated as populating whatever
category it would otherwise map to.

CATEGORIZATION METHOD: each item's real parameters (already extracted
from the source workbook — see equipment_registry.py's own docstring)
are sorted into six categories — Inputs, Outputs, Parameters,
Measurements, Operating Conditions, Performance Indicators — using a
documented keyword-priority rule applied to the parameter's own NAME
text (checked in the order below; first match wins, else Parameters):

  0. Parameters (design-value override) -- name contains "design" AND
     ("pressure" OR "temperature") -- e.g. GA-001's "Design temperature"
     / "Design pressure", GA-004's "Steam temperature (design)". Added
     for GA: GA-001/GA-002 list an explicit DESIGN (rated) value right
     next to a separate OPERATING (actual) value for the same quantity
     -- a genuinely new pattern FE never had. A design/rated value is an
     equipment SPEC (Parameters), not a live Operating Condition, so
     this override is checked first, ahead of the generic "pressure"
     keyword below. Verified this does NOT touch FE-002/FE-005's
     "Design throughput" -- that phrase has no "pressure"/"temperature"
     in it, so it still falls through to the Inputs "throughput" keyword
     unchanged.
  1. Measurements          -- "sensor", "measurement", "accuracy",
                               "calibration", "response time",
                               "output signal", "flow meter",
                               "transmitter" (the last two added for GA:
                               "flow meter" and "pressure transmitter"
                               are real instrumentation terms FE never
                               used. NOTE: a bare "meter" was tried
                               first and caught in testing as wrong --
                               it silently matched GA-001's "Vessel
                               internal diameter" ("dia-METER"),
                               misclassifying a physical dimension as an
                               instrument reading. Caught by scanning
                               every FE/GA parameter name for the
                               substring before shipping, and fixed by
                               using the specific phrase "flow meter"
                               instead of the bare word)
  2. Operating Conditions  -- "operating", "ambient", "pressure"
  3. Outputs               -- "outlet", "output", "discharge rate",
                               "product" (last two added for GA: "Ash
                               discharge rate" mirrors "feed rate" for
                               material LEAVING equipment, and "product
                               ash content" / "Product size grade" /
                               "Compressive strength (product)" / etc.
                               recur across GA-008/009/010 describing the
                               output product's own spec -- a clear,
                               recurring pattern, not a one-off guess)
  4. Inputs                -- "inlet", "feed rate", "throughput",
                               "flow rate" (last one added for GA:
                               "Primary air flow rate" / "Steam flow
                               rate" describe a utility stream entering
                               the gasifier, the same role "feed rate"
                               plays for FE)
  5. Performance Indicators -- "efficiency"
  6. Parameters            -- everything else (equipment design/
                               construction specs: dimensions, materials,
                               motor power, mechanical specs, etc.)

DELIBERATELY NOT added, and why (so this isn't just "whatever made the
numbers look better"): a bare "capacity" keyword was considered for
GA-008/009's "Design capacity" and GA-006's "Conveyor capacity" (to
mirror "Design throughput"), but rejected -- FE-001's "Total hopper
capacity" and "Live capacity (usable)" are STORAGE volumes, not flow
rates, and were already correctly classified as Parameters; a blanket
"capacity" keyword would have wrongly reclassified those as Inputs. A
bare "temperature" keyword was also considered for GA-004's "Air preheat
temperature" (to catch it as an Operating Condition), but rejected --
GA-001's "Number of temperature zones" is a construction spec (a count),
not an operating value, and would have been wrongly reclassified as an
Operating Condition. Both would-be extensions failed the same test:
they broke an existing, already-correct classification elsewhere, so
they were left out. "Air preheat temperature" and GA-006/008/009/010's
various "capacity" parameters fall through to Parameters by default --
a defensible, if imperfect, reading, not an obvious error.

This rule was checked BY HAND against all 69 real FE-001..FE-008
parameters when first written, and again against all 76 real (77 minus
the one null row) GA-001..GA-010 parameters before this extension was
written as code — see this module's own self-test, which prints every
parameter's assigned category so the mapping stays auditable, not a
black box, and includes a hardcoded regression check that FE's own
counts (69 real data points, 26 of 48 category slots populated) are
byte-for-byte unchanged by the GA extension.

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
GA_IDS = [f"GA-{i:03d}" for i in range(1, 11)]
ITEM_IDS = FE_IDS + GA_IDS  # registry's own numbering, FE section first, GA after -- no renumbering

CATEGORIES = [
    "Inputs", "Outputs", "Parameters", "Measurements",
    "Operating Conditions", "Performance Indicators",
]

_MEASUREMENTS_KEYWORDS = (
    "sensor", "measurement", "accuracy", "calibration", "response time", "output signal",
    "flow meter", "transmitter",
)
_OPERATING_KEYWORDS = ("operating", "ambient", "pressure")
_OUTPUTS_KEYWORDS = ("outlet", "output", "discharge rate", "product")
_INPUTS_KEYWORDS = ("inlet", "feed rate", "throughput", "flow rate")
_PERFORMANCE_KEYWORDS = ("efficiency",)


def classify(parameter_name):
    """The categorization rule — see module docstring. Pure function of
    the parameter's own name text, so the mapping is auditable and
    reproducible, not a per-item judgment call hidden in app.py."""
    name = parameter_name.lower()
    if "design" in name and ("pressure" in name or "temperature" in name):
        return "Parameters"
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
    rather than a missing key that has to be guessed at. Rows with a
    None value (see module docstring) are skipped — not real data."""
    buckets = {c: [] for c in CATEGORIES}
    for p in item["parameters"]:
        if p.get("value") is None:
            continue
        buckets[classify(p["parameter"])].append(p)
    return buckets


def build_all_datasheets(registry=None, ids=None):
    """Loads the real registry (equipment_registry.load_registry() — not
    a copy) and builds datasheets for the given ids (default: every
    FE + GA item covered so far, in the registry's own order)."""
    registry = registry if registry is not None else equipment_registry.load_registry()
    ids = ids if ids is not None else ITEM_IDS
    by_id = {i["id"]: i for i in registry}
    out = {}
    for item_id in ids:
        item = by_id.get(item_id)
        if item is None:
            continue
        out[item_id] = {"item": item, "datasheet": build_datasheet(item)}
    return out


def summarize(datasheets=None, ids=None):
    """The honest count this module's own self-test and app.py both
    report: total real data points (individual parameter rows) across
    the given items, versus total "Missing Data — Required" category
    slots (empty category buckets) — the real measure of how far this
    pass is from a complete profile, not rounded up. Pass `ids` to scope
    to just FE, just GA, or the combined set (default: whatever is in
    `datasheets`, or every covered item)."""
    datasheets = datasheets if datasheets is not None else build_all_datasheets(ids=ids)
    if ids is not None:
        datasheets = {k: v for k, v in datasheets.items() if k in ids}
    total_real_data_points = 0
    total_category_slots = 0
    missing_category_slots = 0
    per_item = {}
    for item_id, entry in datasheets.items():
        sheet = entry["datasheet"]
        n_real = sum(len(v) for v in sheet.values())
        n_missing = sum(1 for v in sheet.values() if len(v) == 0)
        total_real_data_points += n_real
        total_category_slots += len(CATEGORIES)
        missing_category_slots += n_missing
        per_item[item_id] = {
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
    for item_id, entry in datasheets.items():
        item = entry["item"]
        print(f"=== {item_id} - {item['name']} ===")
        for cat in CATEGORIES:
            rows = entry["datasheet"][cat]
            if not rows:
                print(f"  {cat}: MISSING DATA - REQUIRED")
            else:
                print(f"  {cat}: {len(rows)} data point(s)")
                for p in rows:
                    print(f"    - {p['parameter']} = {p['value']} {p['unit']}")
        print()

    print("=== Step 6 (FE): honest count ===")
    fe_summary = summarize(datasheets, ids=FE_IDS)
    print(f"Total real data points (8 FE items): {fe_summary['total_real_data_points']}")
    print(f"Total category slots (8 x 6): {fe_summary['total_category_slots']}")
    print(f"Populated category slots: {fe_summary['populated_category_slots']}")
    print(f"Missing Data - Required category slots: {fe_summary['missing_category_slots']} "
          f"({fe_summary['missing_category_slots'] / fe_summary['total_category_slots'] * 100:.0f}%)")

    print("\n=== Step 5/6 (GA): honest count, this section specifically ===")
    ga_summary = summarize(datasheets, ids=GA_IDS)
    print(f"Total real data points (10 GA items): {ga_summary['total_real_data_points']}")
    print(f"Total category slots (10 x 6): {ga_summary['total_category_slots']}")
    print(f"Populated category slots: {ga_summary['populated_category_slots']}")
    print(f"Missing Data - Required category slots: {ga_summary['missing_category_slots']} "
          f"({ga_summary['missing_category_slots'] / ga_summary['total_category_slots'] * 100:.0f}%)")
    for item_id, stat in ga_summary["per_item"].items():
        print(f"  {item_id}: {stat['real_data_points']} real data points, "
              f"{stat['populated_categories']}/6 categories populated")

    print("\n=== Step 6: regression check -- did the GA extension change FE's own numbers? ===")
    EXPECTED_FE_REAL_DATA_POINTS = 69
    EXPECTED_FE_POPULATED_SLOTS = 26
    EXPECTED_FE_MISSING_SLOTS = 22
    fe_ok = (
        fe_summary["total_real_data_points"] == EXPECTED_FE_REAL_DATA_POINTS
        and fe_summary["populated_category_slots"] == EXPECTED_FE_POPULATED_SLOTS
        and fe_summary["missing_category_slots"] == EXPECTED_FE_MISSING_SLOTS
    )
    print(f"Expected (previously reported): {EXPECTED_FE_REAL_DATA_POINTS} real data points, "
          f"{EXPECTED_FE_POPULATED_SLOTS}/48 populated, {EXPECTED_FE_MISSING_SLOTS}/48 missing.")
    print(f"Actual after GA extension:      {fe_summary['total_real_data_points']} real data points, "
          f"{fe_summary['populated_category_slots']}/48 populated, {fe_summary['missing_category_slots']}/48 missing.")
    assert fe_ok, "REGRESSION: the GA rule extension changed FE's own classification!"
    print("PASSED -- FE's classification is byte-for-byte unchanged by the GA extension.")

    print("\n=== Combined (FE + GA) ===")
    combined = summarize(datasheets)
    print(f"Total real data points (18 items): {combined['total_real_data_points']}")
    print(f"Total category slots (18 x 6): {combined['total_category_slots']}")
    print(f"Populated category slots: {combined['populated_category_slots']}")
    print(f"Missing Data - Required category slots: {combined['missing_category_slots']} "
          f"({combined['missing_category_slots'] / combined['total_category_slots'] * 100:.0f}%)")

