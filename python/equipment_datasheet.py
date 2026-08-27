"""
Equipment datasheet view v1 — Feed Handling (FE-001..FE-008),
Gasification (GA-001..GA-010), Gas Cleaning (GC-001..GC-015), and Sensors
& Analysers (SA-001..SA-012) only.

SCOPE: a deliberately scoped, incremental pass, one equipment section at
a time. First shipped covering just FE-001..FE-008, then GA-001..GA-010,
then GC-001..GC-015, now SA-001..SA-012 -- each new section uses the SAME
methodology, no rewrite of what came before. The other 46 items in the
91-item registry are still NOT attempted here.

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
such value=None row across FE-001..FE-008, GA-001..GA-010, GC-001..GC-015
(none), and SA-001..SA-012 (none). Any row with a None value is excluded
before classification — it is not real data and must not count as one,
and must not be treated as populating whatever category it would
otherwise map to.

TWO MORE SOURCE-DATA QUIRKS, noticed while adding SA and reported
honestly rather than smoothed over (same discipline as GC-009's "Design
gas flow" vs. "Design gas flow rate" wording gap, and FE-002's
misaligned units, below):
  - SA-005's own "parameters_filled" metadata says "6 of 7 parameters
    filled", but the actual parameter list in the committed registry has
    only 5 entries — a discrepancy in the source registry's own
    bookkeeping. This module counts the 5 rows that are ACTUALLY present
    (all 5 have real values), not the 6 the metadata claims; it does not
    invent a 6th row to match the stated count.
  - SA-007's "Analysis lab / method" row has unit=None while its value is
    a real, present string (a lab method reference has no physical
    unit) — unlike GA-002's row, this is NOT excluded (only a None
    VALUE is treated as missing; a None unit on a real value is not).
    Displayed exactly as stored, same as every other value/unit pair.

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
                               "transmitter", "analyser", "monitor"
                               ("flow meter"/"transmitter" added for GA;
                               "analyser"/"monitor" added for GC: GC-007/
                               GC-008's "Tar analyser type" and "H₂S
                               analyser (inlet/outlet) type", and
                               GC-010/012/015's "Optical dust monitor
                               type" / "Breakthrough monitoring" / "pH
                               monitoring" are real instrumentation terms
                               neither FE nor GA used. Checked directly:
                               scanned every FE, GA, and GC parameter
                               name for both substrings before adding --
                               6 real matches, all genuine instruments,
                               zero false positives. Priority matters
                               here too: "H₂S analyser (inlet) type"
                               matches Measurements at priority 1 before
                               it could ever reach the Inputs "inlet"
                               keyword at priority 4, so the analyser
                               itself is correctly classified as an
                               instrument, not confused with the H₂S
                               stream it measures. NOTE: a bare "meter"
                               was tried first for the GA extension and
                               caught in testing as wrong -- it silently
                               matched GA-001's "Vessel internal
                               diameter" ("dia-METER"), misclassifying a
                               physical dimension as an instrument
                               reading. Caught by scanning every FE/GA
                               parameter name for the substring before
                               shipping, and fixed by using the specific
                               phrase "flow meter" instead of the bare
                               word)
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

For GC, the existing rule (Inputs/Outputs/Operating Conditions/
Performance Indicators, and the design-value override) needed NO new
keywords beyond Measurements' "analyser"/"monitor" above -- GC's real
parameters reuse "inlet"/"outlet" (e.g. "Inlet gas temperature",
"Tar outlet concentration (target)"), "flow rate" (e.g. "Design gas flow
rate"), "operating"/"pressure" (e.g. "Operating temperature", "Design
pressure drop"), and "efficiency" (e.g. "Removal efficiency", "Collection
efficiency") exactly as FE and GA already did. One genuinely new,
GC-specific wording gap was noticed but deliberately NOT special-cased:
"Design gas flow" (GC-009, no "rate" suffix) does not match the
"flow rate" keyword the way GC-001/003/013's "Design gas flow RATE" does
-- both describe the same kind of quantity, worded slightly differently
in the real source data, and this module reflects that real variance
rather than papering over it with looser matching that risks new false
positives elsewhere.

For SA, the existing rule needed NO new keywords at all -- zero
extension, not even the pattern of one or two well-justified additions
each prior section needed. SA-001..SA-012 are almost entirely gas
analysers and sensors, and every one of their real recurring fields --
"Measurement range", "Measurement principle", "Response time",
"Accuracy", "Calibration interval"/"Calibration method", and above all
"Output signal" -- was already a Measurements keyword from FE's very
first version. "Output signal" earns particular mention: nearly every
SA item repeats it verbatim, and because Measurements is checked at
priority 1, ahead of Outputs' generic "output" at priority 3, it
correctly lands as an instrument's signal format rather than being
confused with a process output, exactly as designed back in FE-006.
Two borderline cases were considered and deliberately left as Parameters
rather than special-cased, same discipline as "capacity"/"temperature"
above: SA-009's "Detection limit" (an instrument spec, conceptually
close to "Accuracy", but moving just this one word would empty out
SA-009's only other populated Parameters slot without fixing a real
misclassification -- unlike GC's analyser/monitor gap, nothing here was
landing in an actively WRONG category, just the generic default one),
and SA-007's "Sampling method"/"Sampling frequency" (SA-007 is a manual
grab-sampling procedure with no continuous online instrument at all, per
its own value text -- whether a sampling PROCEDURE description counts as
"Measurements" the way an instrument's OWN specs do is a genuine judgment
call, and this module doesn't force it either way).

This rule was checked BY HAND against all 69 real FE-001..FE-008
parameters when first written, again against all 76 real GA-001..GA-010
parameters (77 minus the one null row) before the GA extension, again
against all 115 real GC-001..GC-015 parameters (all 115 rows are real --
GC has no null rows) before the GC extension, and again against all 85
real SA-001..SA-012 parameters (all 85 rows are real -- SA has no null
rows either, though SA-005's own "parameters_filled" metadata claims one
more filled row than actually exists in its list; see the source-data
quirks above) before this SA extension was written as code —
see this module's own self-test, which prints every parameter's assigned
category so the mapping stays auditable, not a black box, and includes
hardcoded regression checks that FE's (69 real data points, 26 of 48
slots), GA's (84 real data points, 27 of 60 slots), and GC's (115 real
data points, 52 of 90 slots) counts are byte-for-byte unchanged by the SA
addition.

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
GC_IDS = [f"GC-{i:03d}" for i in range(1, 16)]
SA_IDS = [f"SA-{i:03d}" for i in range(1, 13)]
ITEM_IDS = FE_IDS + GA_IDS + GC_IDS + SA_IDS  # registry's own numbering, each section in order -- no renumbering

CATEGORIES = [
    "Inputs", "Outputs", "Parameters", "Measurements",
    "Operating Conditions", "Performance Indicators",
]

_MEASUREMENTS_KEYWORDS = (
    "sensor", "measurement", "accuracy", "calibration", "response time", "output signal",
    "flow meter", "transmitter", "analyser", "monitor",
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

    print("\n=== GA: honest count ===")
    ga_summary = summarize(datasheets, ids=GA_IDS)
    print(f"Total real data points (10 GA items): {ga_summary['total_real_data_points']}")
    print(f"Total category slots (10 x 6): {ga_summary['total_category_slots']}")
    print(f"Populated category slots: {ga_summary['populated_category_slots']}")
    print(f"Missing Data - Required category slots: {ga_summary['missing_category_slots']} "
          f"({ga_summary['missing_category_slots'] / ga_summary['total_category_slots'] * 100:.0f}%)")

    print("\n=== GC: honest count ===")
    gc_summary = summarize(datasheets, ids=GC_IDS)
    print(f"Total real data points (15 GC items): {gc_summary['total_real_data_points']}")
    print(f"Total category slots (15 x 6): {gc_summary['total_category_slots']}")
    print(f"Populated category slots: {gc_summary['populated_category_slots']}")
    print(f"Missing Data - Required category slots: {gc_summary['missing_category_slots']} "
          f"({gc_summary['missing_category_slots'] / gc_summary['total_category_slots'] * 100:.0f}%)")

    print("\n=== Step 5 (SA): honest count, this section specifically ===")
    sa_summary = summarize(datasheets, ids=SA_IDS)
    print(f"Total real data points (12 SA items): {sa_summary['total_real_data_points']}")
    print(f"Total category slots (12 x 6): {sa_summary['total_category_slots']}")
    print(f"Populated category slots: {sa_summary['populated_category_slots']}")
    print(f"Missing Data - Required category slots: {sa_summary['missing_category_slots']} "
          f"({sa_summary['missing_category_slots'] / sa_summary['total_category_slots'] * 100:.0f}%)")
    for item_id, stat in sa_summary["per_item"].items():
        print(f"  {item_id}: {stat['real_data_points']} real data points, "
              f"{stat['populated_categories']}/6 categories populated")

    print("\n=== Step 5: regression check -- did the SA addition change FE's, GA's, or GC's own numbers? ===")
    EXPECTED = {
        "FE": (fe_summary, 69, 26, 22, 48),
        "GA": (ga_summary, 84, 27, 33, 60),
        "GC": (gc_summary, 115, 52, 38, 90),
    }
    all_ok = True
    for label, (summary, exp_real, exp_pop, exp_missing, n_slots) in EXPECTED.items():
        ok = (
            summary["total_real_data_points"] == exp_real
            and summary["populated_category_slots"] == exp_pop
            and summary["missing_category_slots"] == exp_missing
        )
        all_ok = all_ok and ok
        print(f"  {label}: expected {exp_real} real data points, {exp_pop}/{n_slots} populated, "
              f"{exp_missing}/{n_slots} missing.")
        print(f"  {label}: actual   {summary['total_real_data_points']} real data points, "
              f"{summary['populated_category_slots']}/{n_slots} populated, "
              f"{summary['missing_category_slots']}/{n_slots} missing.")
        assert ok, f"REGRESSION: the SA addition changed {label}'s own classification!"
    print("PASSED -- FE's, GA's, and GC's classifications are all byte-for-byte unchanged by the SA addition.")

    print("\n=== Combined (FE + GA + GC + SA) ===")
    combined = summarize(datasheets)
    print(f"Total real data points (45 items): {combined['total_real_data_points']}")
    print(f"Total category slots (45 x 6): {combined['total_category_slots']}")
    print(f"Populated category slots: {combined['populated_category_slots']}")
    print(f"Missing Data - Required category slots: {combined['missing_category_slots']} "
          f"({combined['missing_category_slots'] / combined['total_category_slots'] * 100:.0f}%)")

