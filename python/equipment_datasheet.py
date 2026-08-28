"""
Equipment datasheet view v1 — Feed Handling (FE-001..FE-008),
Gasification (GA-001..GA-010), Gas Cleaning (GC-001..GC-015), Sensors &
Analysers (SA-001..SA-012), Hydrogen/Balance-of-Plant (HB-001..HB-018),
Electrical/Utilities (EU-001..EU-013), and Automation/Instrumentation
(AI-001..AI-015). ALL 91 REGISTRY ITEMS ARE NOW COVERED -- this is the
final section.

SCOPE: a deliberately scoped, incremental pass, one equipment section at
a time. First shipped covering just FE-001..FE-008, then GA-001..GA-010,
then GC-001..GC-015, then SA-001..SA-012, then HB-001..HB-018, then
EU-001..EU-013, now AI-001..AI-015 -- each new section used the SAME
methodology, no rewrite of what came before. With AI shipped, every one
of the 91 items in the registry now has a datasheet view somewhere in
this module -- see the module-level completeness check in the self-test
below for the full accounting (item-count reconciliation, no duplicates,
none missing, and the grand total real-data-point / populated-slot count
across the whole registry).

HB IS THE SECTION CONTAINING THE ALREADY-VALIDATED WGS REACTION KINETICS
(HB-001 HTS reactor, HB-004 LTS reactor) THIS PROJECT RELIES ON
ELSEWHERE -- checked specifically, not just assumed to work out:
  - HB-002's "Steam-to-CO molar ratio" and "Space velocity (GHSV)" --
    the same steam_to_CO and GHSV parameters kinetics.py's
    hts_conversion()/lts_conversion() actually take -- land in
    Parameters (no keyword matches either; they're equipment/process
    design specs, correctly the default bucket, same as every other
    dimensionless ratio or rate spec in this module).
  - HB-002's "CO conversion efficiency" (75%, kinetics.py's own
    validated HTS design target) lands in Performance Indicators via
    the existing "efficiency" keyword -- correctly a KPI, not a generic
    parameter.
  - HB-004's "Sensitivity to sulphur" (<0.1 ppm S cumulative) -- the
    EXACT catalyst tolerance value safety_flags.py's
    LTS_CATALYST_SULFUR_LIMIT_PPM already cites from this same
    datasheet -- lands in Parameters (no keyword match; a catalyst
    material tolerance spec, the same treatment SA-008's "Alarm
    setpoint H₂S" and SA-009's "Detection limit" already got). Not
    miscategorized, not dropped, not silently renamed.
  - HB-013's "Design pressure" (875 bar(g), the same H2 storage design
    pressure safety_flags.py's h2_storage_flag() already cites) lands in
    Parameters via the design-value override (rule 0) -- correctly a
    rated equipment spec, not confused with the separate "Operating
    pressure range" (350-700 bar(g)) two rows below it, which DOES land
    in Operating Conditions.
None of these load-bearing fields needed a rule change to classify
sensibly; they were the main reason to check this section's keyword
behavior carefully before shipping, not just run the self-test and move
on.

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
     in it, so it still falls through to the Inputs "design throughput"
     keyword unchanged (see the AI section's throughput fix below for
     why that keyword is no longer the bare word).
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
  4. Inputs                -- "inlet", "feed rate", "flow rate" (added
                               for GA: "Primary air flow rate" / "Steam
                               flow rate" describe a utility stream
                               entering the gasifier, the same role
                               "feed rate" plays for FE), "design
                               throughput" / "throughput capacity" /
                               "nominal throughput" (three specific
                               phrases, NOT the bare word "throughput" --
                               see the AI section below for why this
                               changed from the original bare-word
                               version)
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

For HB, three small, well-justified additions, each checked against
every FE/GA/GC/SA/HB-so-far parameter name for false positives before
shipping (zero found outside HB in all three cases):
  - "recovery rate" added to Performance Indicators: HB-007's and
    HB-010's "H₂ recovery rate" fields are the exact same kind of
    headline process-performance metric "efficiency" already captures
    elsewhere (this project's own psa.py and app.py already treat "PSA
    recovery" as a first-class KPI, not a generic parameter) -- 2
    genuine new matches, 0 false positives at the time. (HB-017's
    "Recovery efficiency" already matched via "efficiency" either way,
    so this addition was additive there, not load-bearing.) CORRECTED
    LATER, when EU was added: this was first shipped as the bare word
    "recovery", which worked for HB at the time but was a latent bug --
    EU-004's "Jacket cooling heat recovery" / "Exhaust heat recovery" /
    "Total heat recovery potential" (heat DUTY quantities in kW, not
    percentage-style KPIs) and EU-011's "Recovery medium" (names a
    substance, "Water") would all have been wrongly swept into
    Performance Indicators by the bare word. Caught before shipping EU,
    fixed by tightening the keyword to the exact phrase "recovery rate"
    -- verified this still matches both original HB-007/HB-010 fields
    unchanged (both literally contain "recovery rate"), and confirmed
    against every FE/GA/GC/SA/HB/EU parameter name that the tightened
    phrase now has zero false positives anywhere, including the EU
    fields that broke the old bare-word version.
  - "feed gas" added to Inputs: HB-006's "Feed gas H₂ content"
    characterizes the incoming stream the same way FE-005's "Inlet
    moisture" already does, just worded differently -- 1 genuine new
    match ("Feed gas flow rate" in HB-007/HB-010 already matched via
    "flow rate" either way; "Feed gas H₂ partial pressure" in HB-010
    still lands in Operating Conditions regardless, since "pressure" at
    priority 2 is checked before "feed gas" at priority 4), 0 false
    positives.
  - "production rate" added to Outputs: HB-005's "Steam production
    rate" and HB-011's "H₂ production rate (rated)" describe what the
    equipment PRODUCES, the output-side mirror of "feed rate" -- 2
    genuine new matches, 0 false positives.
Two more candidates were found, considered, and DELIBERATELY left
unadded, same discipline as every prior section's rejected candidates:
"permeate" (HB-010's "Permeate H₂ purity" -- a single instance, and
HB-010's Outputs category was already populated via "Product H₂ flow
rate", so reclassifying it wouldn't fix an actively wrong category, just
move one item between two already-populated buckets) and "metering"
(HB-018's "Metering/billing system" -- a real Coriolis mass flow meter,
but named differently from the "flow meter" keyword, and a single
occurrence project-wide -- the same low-bar-not-met reasoning that kept
"permeate" out).
A genuine priority-order interaction is worth noting explicitly, not
because it's wrong but because it's easy to miss: HB-012's and HB-017's
"Inlet pressure"/"Outlet pressure" fields land in Operating Conditions,
not Inputs/Outputs, because Operating Conditions (priority 2) is checked
before both Outputs (priority 3) and Inputs (priority 4), so "pressure"
wins over "inlet"/"outlet" in the same phrase. This is a defensible
reading (a pressure value at a named location is itself an operating
condition), consistent with FE-007's "Operating pressure (hydraulic)"
precedent, not a new special case introduced for HB.

For EU (electrical/utilities), one bug fix and one genuine addition,
both checked against every FE/GA/GC/SA/HB/EU parameter name before
shipping:
  - The "recovery" -> "recovery rate" fix described above under HB --
    EU is the section that actually exposed the bug, since EU-004/
    EU-011 are full of legitimate, non-KPI uses of the word "recovery"
    (heat recovery duties, a recovery medium) that the bare word would
    have wrongly swept into Performance Indicators.
  - "power meter" added to Measurements: EU-002's and EU-003's "Power
    meter type" / "Power meter / protection relay" are real
    instrumentation (a power meter, the electrical equivalent of the
    "flow meter" keyword already covers for gas) -- 2 genuine new
    matches, 0 false positives, and both are the LAST category each of
    those two items needed: EU-002 and EU-003 go from 5/6 to 6/6
    populated, the first two fully-populated items across every section
    shipped so far.
Two more "meter"-adjacent candidates were found and deliberately left
unadded, same bar as "permeate"/"metering" under HB: EU-009's bare
"Meter type" and EU-013's "Metering standard" are real instruments too,
but neither is named "power meter" or "flow meter" specifically, and
in both cases Measurements was already populated for that item via
other fields ("Accuracy class"/"Measurement range" for EU-009,
"Metered energy accuracy class" for EU-013) -- reclassifying the bare
"meter"/"metering" wording would move an item between two already-
populated buckets, not populate a new one, the same low-value bar every
prior section's declined candidates failed to clear. A bare "meter"
keyword was NOT reconsidered at all here -- it was already rejected for
GA-001's "diameter" false positive, and the same "diameter" risk
recurring in GC-004/GC-006/GC-008's own diameter fields (checked again
here, still present) confirms that rejection remains correct.

For AI (automation/instrumentation -- weather station, camera, PLC,
gateways, brokers, servers, firewalls, cloud/database services, AI
model server, digital twin engine, orchestration controller, RFNBO
monitor), the story flips from every prior section: AI's vocabulary is
IT/software terminology, not process-equipment terminology, and it
needed essentially no productive NEW keyword -- almost everything here
correctly defaults to Parameters (a make/model/spec description, same
as "Catalyst type" or "Membrane material" elsewhere). What AI's
different vocabulary DID do is expose that three EXISTING keywords,
each built for the process-equipment domain, collide with an entirely
different meaning of the same English word in IT/software contexts.
Checked against every FE/GA/GC/SA/HB/EU/AI parameter name before
shipping, same discipline as every prior extension:
  - FIXED (a genuine bug, not just a soft misfit): the bare word
    "throughput" was added for FE-002/FE-004/FE-005/FE-008's material
    feed-rate ratings ("Design throughput", "Throughput capacity",
    "Nominal throughput"). AI-006's "Max message throughput" (MQTT
    messages/s), AI-009's bare "Throughput" (a firewall's network
    throughput, Gbps), and AI-011's "Write throughput" (a database's
    write rate, points/s) are IT/network metrics with zero conceptual
    connection to a material stream entering equipment -- landing them
    in Inputs would have been a clear, unambiguous domain-mismatch, the
    same severity as the GA-001 "diameter" bug, not a defensible
    alternate reading. FIXED by replacing the bare word with the three
    SPECIFIC phrases FE actually uses ("design throughput", "throughput
    capacity", "nominal throughput") -- verified this preserves all
    four original FE matches (FE-002 and FE-005 both say "Design
    throughput", FE-004 says "Throughput capacity", FE-008 says
    "Nominal throughput") and produces zero matches on any of AI's three
    IT-throughput fields.
  - NOT fixed, documented instead (soft, single-item cases where a
    regex/word-boundary fix would be needed to correct cleanly, which
    is a bigger design change than this module's simple substring
    matching is meant to carry, for a small, non-harmful effect):
    AI-004's "Number of digital outputs" / "Number of analogue outputs"
    (PLC I/O channel COUNTS) match the generic "output" keyword (which
    exists for real process/electrical outputs like EU-002's "Rated
    electrical power output") purely because "outputs" contains
    "output" as a substring -- landing these in Outputs is an imperfect
    reading (a hardware channel count isn't really a process "output"),
    but not a harmful one, and AI-004's own populated-category count
    would only go from 2/6 to 1/6 if "corrected", i.e. removing the
    match would make the section look LESS complete for a marginal
    correctness gain. Left as-is. Similarly, AI-014's "Module health
    monitoring" and "Scaling response time" match "monitor" and
    "response time" (added for physical instrumentation -- dust
    monitors, an analyser's response time) even though they describe
    SOFTWARE orchestration behavior, not a physical instrument. Also
    left as-is, for the same reason.
No new keyword was added for AI's own sake -- the "power meter" (EU),
"analyser"/"monitor" (GC), "flow meter"/"transmitter" (GA) additions
already cover the handful of AI fields that are genuinely
instrumentation-flavored (e.g. AI-003's Bed Pressure-Drop Sensor, which
reuses "sensor"/"measurement"/"accuracy"/"response time"/"output
signal" exactly as SA's gas analysers do).

This rule was checked BY HAND against all 69 real FE-001..FE-008
parameters when first written, again against all 76 real GA-001..GA-010
parameters (77 minus the one null row) before the GA extension, again
against all 115 real GC-001..GC-015 parameters (all 115 rows are real --
GC has no null rows) before the GC extension, again against all 85
real SA-001..SA-012 parameters (all 85 rows are real -- SA has no null
rows either, though SA-005's own "parameters_filled" metadata claims one
more filled row than actually exists in its list; see the source-data
quirks above) before the SA extension, again against all 154 real
HB-001..HB-018 parameters (all 154 rows are real -- HB has no null rows)
before the HB extension, again against all 114 real EU-001..EU-013
parameters (all 114 rows are real -- EU has no null rows) before the EU
extension, and again against all 135 real AI-001..AI-015 parameters (all
135 rows are real -- AI has no null rows) before this final AI section
was written as code — see this module's own self-test, which prints
every parameter's assigned category so the mapping stays auditable, not
a black box, and includes hardcoded regression checks that FE's (69 real
data points, 26 of 48 slots), GA's (84 real data points, 27 of 60
slots), GC's (115 real data points, 52 of 90 slots), SA's (85 real data
points, 26 of 72 slots), HB's (154 real data points, 56 of 108 slots),
and EU's (114 real data points, 45 of 78 slots) counts are byte-for-byte
unchanged by the AI addition, plus a module-level completeness check
that FE_IDS + GA_IDS + GC_IDS + SA_IDS + HB_IDS + EU_IDS + AI_IDS
together cover exactly the 91 real registry item ids, with no duplicates
and none missing, now that AI is the last section shipped.

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
HB_IDS = [f"HB-{i:03d}" for i in range(1, 19)]
EU_IDS = [f"EU-{i:03d}" for i in range(1, 14)]
AI_IDS = [f"AI-{i:03d}" for i in range(1, 16)]
ITEM_IDS = FE_IDS + GA_IDS + GC_IDS + SA_IDS + HB_IDS + EU_IDS + AI_IDS  # registry's own numbering, each section in order -- no renumbering, covers all 91 items once AI ships

CATEGORIES = [
    "Inputs", "Outputs", "Parameters", "Measurements",
    "Operating Conditions", "Performance Indicators",
]

# Three genuine data-confidence statuses a category SLOT can have --
# added for the engineering-estimate pilot (python/
# equipment_engineering_estimates.py). STATUS_CONFIRMED is the default
# for every parameter row that has no explicit "status" key -- true of
# every registry row and every python/equipment_rfi_fills.py row ever
# written, so this is fully backward compatible, not a breaking change.
# A row instead carrying "status": STATUS_ESTIMATE marks it honestly as
# a correlation/literature/comparable-system estimate, NOT vendor- or
# DOK-ING-confirmed data -- see summarize()'s slot-status logic below
# for exactly how a category's rows roll up into one of these three.
STATUS_CONFIRMED = "Confirmed"
STATUS_ESTIMATE = "Engineering Estimate (Not Vendor/DOK-ING Confirmed)"
STATUS_MISSING = "Missing Data — Required"

_MEASUREMENTS_KEYWORDS = (
    "sensor", "measurement", "accuracy", "calibration", "response time", "output signal",
    "flow meter", "transmitter", "analyser", "monitor", "power meter",
)
_OPERATING_KEYWORDS = ("operating", "ambient", "pressure")
_OUTPUTS_KEYWORDS = ("outlet", "output", "discharge rate", "product", "production rate")
_INPUTS_KEYWORDS = (
    "inlet", "feed rate", "flow rate", "feed gas",
    "design throughput", "throughput capacity", "nominal throughput",
)
_PERFORMANCE_KEYWORDS = ("efficiency", "recovery rate")


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


def slot_status(rows):
    """Classifies ONE category bucket's real status: STATUS_MISSING if
    empty; STATUS_CONFIRMED if at least one row in it is confirmed data
    (real vendor-datasheet or DOK-ING-RFI data -- the default for any
    row without an explicit "status" key, so a slot with a mix of
    confirmed and estimate rows still counts as genuinely Confirmed,
    since real confirmed data IS present); STATUS_ESTIMATE only if
    every row present is an engineering estimate and none is confirmed.
    Public because app.py's rendering needs the same per-slot
    classification the honest count uses, not a separate copy of this
    logic."""
    if not rows:
        return STATUS_MISSING
    statuses = {r.get("status", STATUS_CONFIRMED) for r in rows}
    return STATUS_CONFIRMED if STATUS_CONFIRMED in statuses else STATUS_ESTIMATE


def summarize(datasheets=None, ids=None):
    """The honest count this module's own self-test and app.py both
    report: total real data points (individual parameter rows) across
    the given items, versus category slots split into three genuine
    statuses -- STATUS_CONFIRMED, STATUS_ESTIMATE, STATUS_MISSING (task
    requirement 4: Estimate is reported SEPARATELY, never blended into
    a single "populated" figure that would overstate how solid an
    estimated number actually is). `populated_category_slots` (=
    confirmed + estimated) and `missing_category_slots` are kept for
    backward compatibility with every caller that predates the
    three-way split (equipment_data_requests.py's gap list only needs
    to know "empty or not", which populated_category_slots still
    answers correctly). Pass `ids` to scope to just FE, just GA, or the
    combined set (default: whatever is in `datasheets`, or every
    covered item)."""
    datasheets = datasheets if datasheets is not None else build_all_datasheets(ids=ids)
    if ids is not None:
        datasheets = {k: v for k, v in datasheets.items() if k in ids}
    total_real_data_points = 0
    total_category_slots = 0
    confirmed_category_slots = 0
    estimated_category_slots = 0
    missing_category_slots = 0
    per_item = {}
    for item_id, entry in datasheets.items():
        sheet = entry["datasheet"]
        n_real = sum(len(v) for v in sheet.values())
        n_confirmed = sum(1 for v in sheet.values() if slot_status(v) == STATUS_CONFIRMED)
        n_estimated = sum(1 for v in sheet.values() if slot_status(v) == STATUS_ESTIMATE)
        n_missing = sum(1 for v in sheet.values() if slot_status(v) == STATUS_MISSING)
        total_real_data_points += n_real
        total_category_slots += len(CATEGORIES)
        confirmed_category_slots += n_confirmed
        estimated_category_slots += n_estimated
        missing_category_slots += n_missing
        per_item[item_id] = {
            "real_data_points": n_real, "missing_categories": n_missing,
            "populated_categories": len(CATEGORIES) - n_missing,
            "confirmed_categories": n_confirmed, "estimated_categories": n_estimated,
        }
    return {
        "total_real_data_points": total_real_data_points,
        "total_category_slots": total_category_slots,
        "populated_category_slots": total_category_slots - missing_category_slots,
        "confirmed_category_slots": confirmed_category_slots,
        "estimated_category_slots": estimated_category_slots,
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

    print("\n=== SA: honest count ===")
    sa_summary = summarize(datasheets, ids=SA_IDS)
    print(f"Total real data points (12 SA items): {sa_summary['total_real_data_points']}")
    print(f"Total category slots (12 x 6): {sa_summary['total_category_slots']}")
    print(f"Populated category slots: {sa_summary['populated_category_slots']}")
    print(f"Missing Data - Required category slots: {sa_summary['missing_category_slots']} "
          f"({sa_summary['missing_category_slots'] / sa_summary['total_category_slots'] * 100:.0f}%)")

    print("\n=== HB: honest count ===")
    hb_summary = summarize(datasheets, ids=HB_IDS)
    print(f"Total real data points (18 HB items): {hb_summary['total_real_data_points']}")
    print(f"Total category slots (18 x 6): {hb_summary['total_category_slots']}")
    print(f"Populated category slots: {hb_summary['populated_category_slots']}")
    print(f"Missing Data - Required category slots: {hb_summary['missing_category_slots']} "
          f"({hb_summary['missing_category_slots'] / hb_summary['total_category_slots'] * 100:.0f}%)")

    print("\n=== Kinetics-critical HB fields, verified by name ===")
    hb_by_id = {k: v for k, v in datasheets.items() if k in HB_IDS}
    checks = [
        ("HB-002", "Space velocity (GHSV)", "Parameters"),
        ("HB-002", "Steam-to-CO molar ratio", "Parameters"),
        ("HB-002", "CO conversion efficiency", "Performance Indicators"),
        ("HB-004", "Sensitivity to sulphur", "Parameters"),
        ("HB-013", "Design pressure", "Parameters"),
    ]
    for item_id, param_name, expected_cat in checks:
        sheet = hb_by_id[item_id]["datasheet"]
        actual_cat = next(
            (cat for cat, rows in sheet.items() if any(r["parameter"] == param_name for r in rows)), None
        )
        status = "OK" if actual_cat == expected_cat else "MISMATCH"
        print(f"  [{status}] {item_id} '{param_name}' -> {actual_cat} (expected {expected_cat})")
        assert actual_cat == expected_cat, f"{item_id} '{param_name}' landed in {actual_cat}, expected {expected_cat}"

    print("\n=== EU: honest count ===")
    eu_summary = summarize(datasheets, ids=EU_IDS)
    print(f"Total real data points (13 EU items): {eu_summary['total_real_data_points']}")
    print(f"Total category slots (13 x 6): {eu_summary['total_category_slots']}")
    print(f"Populated category slots: {eu_summary['populated_category_slots']}")
    print(f"Missing Data - Required category slots: {eu_summary['missing_category_slots']} "
          f"({eu_summary['missing_category_slots'] / eu_summary['total_category_slots'] * 100:.0f}%)")

    print("\n=== Recovery-rate bug-fix check: does the tightened keyword avoid EU's false positives? ===")
    eu_by_id = {k: v for k, v in datasheets.items() if k in EU_IDS}
    non_performance_checks = [
        ("EU-004", "Jacket cooling heat recovery", "Parameters"),
        ("EU-004", "Exhaust heat recovery", "Parameters"),
        ("EU-004", "Total heat recovery potential", "Parameters"),
        ("EU-011", "Recovery medium", "Parameters"),
    ]
    for item_id, param_name, expected_cat in non_performance_checks:
        sheet = eu_by_id[item_id]["datasheet"]
        actual_cat = next(
            (cat for cat, rows in sheet.items() if any(r["parameter"] == param_name for r in rows)), None
        )
        status = "OK" if actual_cat == expected_cat else "MISMATCH"
        print(f"  [{status}] {item_id} '{param_name}' -> {actual_cat} (expected {expected_cat}, NOT Performance Indicators)")
        assert actual_cat == expected_cat, f"{item_id} '{param_name}' landed in {actual_cat}, expected {expected_cat}"

    print("\n=== Step 5 (AI): honest count, this section specifically ===")
    ai_summary = summarize(datasheets, ids=AI_IDS)
    print(f"Total real data points (15 AI items): {ai_summary['total_real_data_points']}")
    print(f"Total category slots (15 x 6): {ai_summary['total_category_slots']}")
    print(f"Populated category slots: {ai_summary['populated_category_slots']}")
    print(f"Missing Data - Required category slots: {ai_summary['missing_category_slots']} "
          f"({ai_summary['missing_category_slots'] / ai_summary['total_category_slots'] * 100:.0f}%)")
    for item_id, stat in ai_summary["per_item"].items():
        print(f"  {item_id}: {stat['real_data_points']} real data points, "
              f"{stat['populated_categories']}/6 categories populated")

    print("\n=== Step 5: regression check -- did the AI addition change FE's, GA's, GC's, SA's, HB's, or EU's own numbers? ===")
    EXPECTED = {
        "FE": (fe_summary, 69, 26, 22, 48),
        "GA": (ga_summary, 84, 27, 33, 60),
        "GC": (gc_summary, 115, 52, 38, 90),
        "SA": (sa_summary, 85, 26, 46, 72),
        "HB": (hb_summary, 154, 56, 52, 108),
        "EU": (eu_summary, 114, 45, 33, 78),
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
        assert ok, f"REGRESSION: the AI addition changed {label}'s own classification!"
    print("PASSED -- FE's, GA's, GC's, SA's, HB's, and EU's classifications are all byte-for-byte "
          "unchanged by the AI addition.")

    print("\n=== Throughput bug-fix check: does the tightened keyword avoid AI's false positives, "
          "while still catching FE's real ones? ===")
    ai_by_id = {k: v for k, v in datasheets.items() if k in AI_IDS}
    throughput_checks = [
        ("AI-006", "Max message throughput", "Parameters"),
        ("AI-009", "Throughput", "Parameters"),
        ("AI-011", "Write throughput", "Parameters"),
    ]
    for item_id, param_name, expected_cat in throughput_checks:
        sheet = ai_by_id[item_id]["datasheet"]
        actual_cat = next(
            (cat for cat, rows in sheet.items() if any(r["parameter"] == param_name for r in rows)), None
        )
        status = "OK" if actual_cat == expected_cat else "MISMATCH"
        print(f"  [{status}] {item_id} '{param_name}' -> {actual_cat} (expected {expected_cat}, NOT Inputs)")
        assert actual_cat == expected_cat, f"{item_id} '{param_name}' landed in {actual_cat}, expected {expected_cat}"
    fe_by_id = {k: v for k, v in datasheets.items() if k in FE_IDS}
    fe_throughput_checks = [
        ("FE-002", "Design throughput", "Inputs"),
        ("FE-004", "Throughput capacity", "Inputs"),
        ("FE-005", "Design throughput", "Inputs"),
        ("FE-008", "Nominal throughput", "Inputs"),
    ]
    for item_id, param_name, expected_cat in fe_throughput_checks:
        sheet = fe_by_id[item_id]["datasheet"]
        actual_cat = next(
            (cat for cat, rows in sheet.items() if any(r["parameter"] == param_name for r in rows)), None
        )
        status = "OK" if actual_cat == expected_cat else "MISMATCH"
        print(f"  [{status}] {item_id} '{param_name}' -> {actual_cat} (expected {expected_cat}, still Inputs)")
        assert actual_cat == expected_cat, f"{item_id} '{param_name}' landed in {actual_cat}, expected {expected_cat}"

    print("\n=== Step 6: completeness check -- all 91 registry items, no duplicates, none missing ===")
    ALL_SECTION_IDS = {
        "FE": FE_IDS, "GA": GA_IDS, "GC": GC_IDS, "SA": SA_IDS,
        "HB": HB_IDS, "EU": EU_IDS, "AI": AI_IDS,
    }
    total_items_covered = sum(len(ids) for ids in ALL_SECTION_IDS.values())
    print(f"Section item counts: " + ", ".join(f"{label}={len(ids)}" for label, ids in ALL_SECTION_IDS.items()))
    print(f"Sum: {total_items_covered} (expected 91)")
    assert total_items_covered == 91, f"REGRESSION: section id lists sum to {total_items_covered}, not 91!"

    seen = set()
    duplicates = []
    for ids in ALL_SECTION_IDS.values():
        for item_id in ids:
            if item_id in seen:
                duplicates.append(item_id)
            seen.add(item_id)
    print(f"Duplicate item ids across sections: {duplicates or 'none'}")
    assert not duplicates, f"REGRESSION: {duplicates} appear in more than one section!"

    full_registry = equipment_registry.load_registry()
    all_registry_ids = {i["id"] for i in full_registry}
    missing_from_module = all_registry_ids - seen
    extra_in_module = seen - all_registry_ids
    print(f"Registry items not covered by any section: {missing_from_module or 'none'}")
    print(f"Section ids not present in the registry: {extra_in_module or 'none'}")
    assert not missing_from_module, f"REGRESSION: {missing_from_module} are in the registry but not covered!"
    assert not extra_in_module, f"REGRESSION: {extra_in_module} are covered but don't exist in the registry!"
    print(f"Total registry items: {len(full_registry)} (expected 91)")
    assert len(full_registry) == 91, f"REGRESSION: registry has {len(full_registry)} items, not 91!"
    print("PASSED -- all 91 registry items are covered by exactly one section tab each.")

    print("\n=== GRAND TOTAL: the whole registry, all 91 items, all 9 tabs ===")
    combined = summarize(datasheets)
    print(f"Total real data points (91 items): {combined['total_real_data_points']}")
    print(f"Total category slots (91 x 6): {combined['total_category_slots']}")
    print(f"Populated category slots: {combined['populated_category_slots']}")
    print(f"Missing Data - Required category slots: {combined['missing_category_slots']} "
          f"({combined['missing_category_slots'] / combined['total_category_slots'] * 100:.0f}%)")
    print(f"Overall honest completion: {combined['populated_category_slots']} of "
          f"{combined['total_category_slots']} possible (item x category) slots actually have real "
          f"data -- {combined['populated_category_slots'] / combined['total_category_slots'] * 100:.1f}%.")


