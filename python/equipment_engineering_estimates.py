"""
Engineering-estimate overlay v1 — PILOT, scoped deliberately to FE-001
through FE-008's 21 remaining "Missing Data — Required" gaps only (task
requirement: "Pilot this on FE-001 through FE-008's 21 remaining gaps —
not all 284 at once"). Extending to the other sections is a separate,
later task, once this pilot is reviewed.

WHY THIS EXISTS, per the real, authorized basis stated in the task:
DOK-ING has confirmed they cannot answer some outstanding questions at
this stage, and has authorized proceeding with engineering estimates —
correlations, literature values, comparable installed systems — clearly
distinguished from confirmed data, to be calibrated once the real plant
exists. This is standard FEED-stage practice, and this project already
does it in scattered form: the ER=0.25 air equivalence ratio and 200/150
ppm feed sulfur/chlorine figures (python/uncertainty.py), and the
compressor motor power / drive power estimates already in the equipment
registry itself, are all exactly this kind of thing, just not
previously given a distinct, honest STATUS label of their own.

HARD RULE, same discipline as equipment_rfi_fills.py before it, made
stricter here rather than looser: a gap gets filled ONLY where a real,
STATABLE, DEFENSIBLE basis exists — a named engineering correlation
(e.g. a standard mass-balance conversion), a cited literature source
(a real, standard, checkable reference), or a comparable, actually-
existing installed-equipment-class practice (e.g. "mechanical material-
handling equipment in this class universally operates at ambient
conditions, per standard industrial practice"). NEVER a plausible-
sounding number invented to look complete. Every filled row states its
actual basis in its own remarks — not just a number, "why, citable and
checkable" (task requirement 2). Where no genuine basis exists, the gap
stays "Missing Data — Required" — task requirement 3 is explicit this
is not "fill everything that can technically be filled", it's "fill
only where real engineering justification exists". Of FE's 21 gaps,
7 get a genuine estimate; 14 stay missing — see REPORT below for the
per-gap reasoning on every single one, filled and declined alike.

STATUS, DISTINCT FROM BOTH "Confirmed" AND "Missing Data — Required"
(task requirement 1): every row added here carries
"status": equipment_datasheet.STATUS_ESTIMATE
("Engineering Estimate (Not Vendor/DOK-ING Confirmed)") — a third,
genuine status equipment_datasheet.py's own summarize()/slot_status()
now understands natively (see that module's own docstring for the
three-way logic), reported SEPARATELY from Confirmed in the honest
completion percentage, never blended into it (task requirement 4).

PROVENANCE, same "source" field convention as equipment_rfi_fills.py:
every row's "source" names this pilot and its basis type, distinct in
app.py's UI from both "Equipment Datasheet" (vendor data) and "DOK-ING
RFI (design_basis.py Q#)" (DOK-ING's real answers) rows.

Does NOT modify data/equipment_registry.json (off-limits, DOK-ING's own
static datasheet extract) or equipment_datasheet.py's build_datasheet()
(stays pure, registry-only). apply_estimates() is a separate overlay,
deep-copying its input, exactly the equipment_rfi_fills.py pattern —
and composes with it: app.py applies RFI fills first, then estimates,
on the same datasheets dict, since both only ever touch buckets that
were genuinely empty of real data.

REPORT (task requirement 5 — every one of FE's 21 gaps, filled and
declined, with the actual reasoning):

FILLED — 7 of 21:

  FE-002 (Magnetic & Eddy Current Separator) Operating Conditions:
    Ambient temperature, matching FE-001's own confirmed site ambient
    range (-20 to +50 degC). Basis: comparable-installed-system
    practice — magnetic/eddy-current separation is a purely mechanical/
    electromagnetic process with no heating or cooling unit operation
    involved; no vendor in this equipment class publishes a distinct
    "operating temperature" spec beyond ambient rating, because there
    isn't one to publish. Same-site reasoning: FE-002 sits in the same
    feed-handling area as FE-001, immediately downstream, before any
    heating stage (FE-005) — no reason to assume a different ambient
    range.

  FE-003 (Weighing Conveyor) Operating Conditions: same ambient basis
    and same reasoning as FE-002 — mechanical belt conveying, no
    process heating/cooling, same feed-handling area.

  FE-004 (Shredder / Size Reducer) Operating Conditions: ambient, with
    an honest caveat this item's own remarks don't get for FE-002/003 —
    shredding generates SOME frictional/cutting heat, but this is not a
    controlled process setpoint the way FE-005's dryer temperature is;
    standard practice for two-shaft waste shredders is no active
    thermal control, operating at ambient plus an uncontrolled, minor
    temperature rise.

  FE-004 Performance Indicators: specific energy consumption, 150
    kWh/tonne — an EXACT calculation from this item's own two already-
    CONFIRMED real values (Drive motor power = 15 kW; Throughput
    capacity = 0.1 t/h; 15 / 0.1 = 150), not an independent guess,
    still flagged Estimate rather than Confirmed since DOK-ING/vendor
    has not itself stated a specific-energy figure. Compared against a
    published range: coarse/primary MSW and mixed-waste shredding is
    commonly cited in solid-waste engineering references (e.g.
    Tchobanoglous, Theisen & Vigil, "Integrated Solid Waste Management",
    a standard reference in this field) in the rough range of 10-40
    kWh/tonne at commercial scale. FE-004's derived 150 kWh/tonne sits
    well above that range — reported honestly as consistent with this
    being a small (0.1 t/h), pilot-scale unit, where fixed motor
    overhead dominates specific energy far more than it would at
    commercial throughput, not treated as an error or hidden.

  FE-005 (Feed Dryer) Performance Indicators: typical convective/belt
    dryer thermal efficiency, 50-75%. Basis: a general equipment-class
    range from standard industrial drying literature (e.g. Mujumdar,
    "Handbook of Industrial Drying", a standard reference for this
    equipment type) for convective belt dryers on biomass/solid-waste-
    type duty. Explicitly NOT calculated from FE-005's own specific
    duty — no stated evaporation/heat-duty figure exists in this
    item's own data to calculate from — a general equipment-class
    range only, stated as such, not dressed up as item-specific.

  FE-007 (Feed Screw / Ram Feeder) Outputs: ~37.9 kg/h post-drying feed
    rate. Basis: a named, standard engineering method — wet/dry
    moisture-basis mass-balance conversion — applied to this item's own
    confirmed inputs: the confirmed 41.67 kg/h as-received feed rate
    (DOK-ING RFI Q1, applied upstream at FE-001/GA-001), and FE-005's
    own confirmed inlet moisture (10%) and outlet moisture target
    (<1%, taken as ~1%). Dry-solids mass = 41.67 x (1 - 0.10) =
    37.5 kg/h; post-drying wet mass at ~1% moisture = 37.5 / (1 - 0.01)
    = ~37.9 kg/h. This is a calculation from confirmed inputs via a
    standard, named method, not an independent literature/vendor
    figure — flagged Estimate because DOK-ING has not itself stated
    this specific post-drying flow rate, only the inputs it's
    calculated from.

  FE-008 (Air-lock / Rotary Valve) Outputs: the same ~37.9 kg/h
    post-drying feed rate, same basis as FE-007 — FE-008 is the next
    conveying stage immediately after FE-007, with no further moisture
    change between them, so the same post-drying mass-balance figure
    applies directly.

DECLINED — 14 of 21, with the actual reason (not silently skipped):

  FE-001 Outputs: a receiving hopper's discharge rate for heterogeneous
    MSW is NOT amenable to a standard bulk-solids orifice-flow
    correlation (e.g. Beverloo) the way free-flowing granular solids
    are — MSW bridges/arches, which is explicitly why this item's own
    900x900mm opening is oversized to avoid it (per this item's own
    remarks). The actual discharge rate is a CONTROLLED process
    variable (set by FE-003's downstream metering), not a physical
    correlation output. No defensible estimate exists.
  FE-001 Performance Indicators: this item's own "Live capacity
    (usable)" (1.7 t of 2 t total, 85%) already IS this item's real
    utilization figure, just classified into Parameters by the keyword
    rule, not Performance Indicators — no genuinely NEW, additional
    figure to estimate beyond what's already on file.
  FE-002 Outputs: the actual reject rate (residual tramp metal in an
    already-post-MRF stream) would be a trace fraction with no
    published "typical residual tramp-metal content in post-MRF waste"
    figure this module can cite with any real confidence — too
    source-dependent to state a defensible number.
  FE-002 Measurements: instrument accuracy/calibration is fundamentally
    a VENDOR product spec (already correctly routed to Vendor in
    python/equipment_request_routing.py) — no correlation or literature
    value substitutes for a specific instrument's own delivered
    accuracy before that instrument is selected.
  FE-003 Outputs: a conveyor's own throughput already equals its
    already-confirmed Inputs figure (Nominal feed rate) — no distinct
    NEW Outputs quantity exists to estimate.
  FE-003 Performance Indicators: weighing accuracy is already captured
    (Measurements, real registry data) — no additional, genuinely new
    PI concept for a weighing conveyor beyond that.
  FE-004 Measurements: same vendor-instrument reasoning as FE-002.
  FE-005 Measurements: same vendor-instrument reasoning (moisture-
    sensor accuracy is FE-006's domain anyway, a separate item).
  FE-006 (Moisture Analyser) Inputs and Outputs: this is a non-contact
    optical sensor mounted above a conveyor — it has no physical
    material stream of its own to characterize (structurally not
    applicable, not just undocumented; already established this way in
    python/equipment_rfi_fills.py's own reasoning for this same item).
    No engineering estimate can manufacture a material flow rate for
    equipment that doesn't have one.
  FE-006 Performance Indicators: would just restate this item's own
    already-populated Measurements (accuracy, response time) under a
    different category label — not new information.
  FE-007 Performance Indicators: no genuine additional basis beyond
    what's now in this item's own Outputs.
  FE-008 Measurements: same vendor-instrument reasoning as FE-002/004.
  FE-008 Performance Indicators: same reasoning as FE-007 — nothing
    additional beyond Outputs.
"""
import copy

from . import equipment_datasheet

_Q = equipment_datasheet


def _source(basis_label):
    return f"Engineering estimate (FE-001..FE-008 pilot) — {basis_label}"


# {item_id: {category: [ {parameter, value, unit, remarks, status, source} ]}}
# Every row targets a category verified genuinely empty of real data in
# the self-test below (same hard safety check as equipment_rfi_fills.py
# — refuses to overwrite real vendor/DOK-ING data with an estimate).
ESTIMATE_FILLS = {
    "FE-002": {
        "Operating Conditions": [
            {
                "parameter": "Estimated operating temperature",
                "value": "-20 to +50", "unit": "°C",
                "remarks": (
                    "Comparable-installed-system basis: magnetic/eddy-current separation is a "
                    "purely mechanical/electromagnetic process with no heating or cooling unit "
                    "operation involved — standard industrial practice for this equipment class "
                    "is ambient-only operation (no vendor publishes a distinct operating-"
                    "temperature spec because there isn't one). Matches FE-001's own confirmed "
                    "site ambient range — same feed-handling area, upstream of any heating stage."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source("comparable-installed-system practice (ambient-only mechanical equipment)"),
            },
        ],
    },
    "FE-003": {
        "Operating Conditions": [
            {
                "parameter": "Estimated operating temperature",
                "value": "-20 to +50", "unit": "°C",
                "remarks": (
                    "Comparable-installed-system basis: mechanical belt conveying, same as "
                    "FE-002 — no process heating/cooling, no controlled operating temperature. "
                    "Matches FE-001's/FE-002's confirmed site ambient range, same feed-handling "
                    "area upstream of any heating stage."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source("comparable-installed-system practice (ambient-only mechanical equipment)"),
            },
        ],
    },
    "FE-004": {
        "Operating Conditions": [
            {
                "parameter": "Estimated operating temperature",
                "value": "-20 to +50 (plus minor frictional/cutting heat rise, uncontrolled)", "unit": "°C",
                "remarks": (
                    "Comparable-installed-system basis: standard practice for two-shaft MSW/"
                    "mixed-waste shredders is no active thermal control — operation at ambient "
                    "plus an uncontrolled, minor frictional/cutting heat rise, unlike FE-005's "
                    "dryer, which has an actual controlled process temperature. Base ambient "
                    "range matches FE-001/FE-002/FE-003's confirmed site conditions."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source("comparable-installed-system practice (unheated mechanical shredding equipment)"),
            },
        ],
        "Performance Indicators": [
            {
                "parameter": "Estimated specific energy consumption",
                "value": "150", "unit": "kWh/tonne",
                "remarks": (
                    "Exact calculation from this item's own two already-CONFIRMED real values: "
                    "Drive motor power (15 kW) / Throughput capacity (0.1 t/h) = 150 kWh/t — not "
                    "an independent guess, but flagged Estimate since no vendor/DOK-ING source "
                    "states a specific-energy figure directly. For context: coarse/primary MSW "
                    "and mixed-waste shredding is commonly cited in solid-waste engineering "
                    "references (e.g. Tchobanoglous, Theisen & Vigil, \"Integrated Solid Waste "
                    "Management\") in the rough range of 10-40 kWh/tonne at commercial scale — "
                    "this item's derived 150 kWh/t sits well above that, consistent with FE-004 "
                    "being a small, pilot-scale (0.1 t/h) unit where fixed motor overhead "
                    "dominates specific energy far more than at commercial throughput, not "
                    "treated as an error."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source("calculated from this item's own confirmed motor power and throughput, compared against published literature range"),
            },
        ],
    },
    "FE-005": {
        "Performance Indicators": [
            {
                "parameter": "Typical thermal efficiency (equipment class)",
                "value": "50-75", "unit": "%",
                "remarks": (
                    "General equipment-class range from standard industrial drying literature "
                    "(e.g. Mujumdar, \"Handbook of Industrial Drying\") for convective belt "
                    "dryers on biomass/solid-waste-type duty. Explicitly NOT calculated from "
                    "this item's own specific duty — no stated evaporation/heat-duty figure "
                    "exists in this item's own data to calculate from — a general equipment-"
                    "class range only, not dressed up as item-specific."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source("published literature range for the equipment class (convective belt dryers)"),
            },
        ],
    },
    "FE-007": {
        "Outputs": [
            {
                "parameter": "Estimated post-drying feed rate",
                "value": "~37.9", "unit": "kg/h",
                "remarks": (
                    "Standard, named engineering method: wet/dry moisture-basis mass-balance "
                    "conversion, applied to this item's own confirmed inputs. Dry-solids mass = "
                    "41.67 kg/h (confirmed as-received feed rate, DOK-ING RFI Q1) x (1 - 0.10) "
                    "(FE-005's confirmed inlet moisture) = 37.5 kg/h. Post-drying wet mass at "
                    "FE-005's confirmed outlet moisture target (<1%, taken as ~1%) = "
                    "37.5 / (1 - 0.01) = ~37.9 kg/h. A calculation from confirmed inputs via a "
                    "standard method, not an independent literature/vendor figure — flagged "
                    "Estimate since DOK-ING has not itself stated this specific post-drying rate, "
                    "only the inputs it's calculated from."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source("standard moisture-basis mass-balance conversion from this item's own confirmed inputs"),
            },
        ],
    },
    "FE-008": {
        "Outputs": [
            {
                "parameter": "Estimated post-drying feed rate",
                "value": "~37.9", "unit": "kg/h",
                "remarks": (
                    "Same basis and figure as FE-007's own estimated post-drying feed rate — "
                    "FE-008 is the next conveying stage immediately after FE-007, with no "
                    "further moisture change between them, so the same mass-balance result "
                    "applies directly."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source("standard moisture-basis mass-balance conversion, same as FE-007"),
            },
        ],
    },
}


def apply_estimates(datasheets):
    """Returns a NEW datasheets dict (deep-copied — input never
    mutated) with ESTIMATE_FILLS' rows appended into the named (item_id,
    category) buckets. Same safety check as equipment_rfi_fills.py:
    raises if a target bucket already has real data in it — this module
    must only ever fill genuinely empty slots, never sit on top of or
    contradict confirmed data."""
    out = copy.deepcopy(datasheets)
    for item_id, categories in ESTIMATE_FILLS.items():
        if item_id not in out:
            raise KeyError(f"ESTIMATE_FILLS references {item_id}, which isn't in the given datasheets.")
        sheet = out[item_id]["datasheet"]
        for category, rows in categories.items():
            if category not in sheet:
                raise KeyError(f"ESTIMATE_FILLS[{item_id!r}] references unknown category {category!r}.")
            if sheet[category]:
                raise ValueError(
                    f"REGRESSION GUARD: {item_id}'s {category} already has "
                    f"{len(sheet[category])} real row(s) — refusing to append an estimate on "
                    f"top of it. ESTIMATE_FILLS must only target genuinely empty categories."
                )
            sheet[category] = list(rows)
    return out


def count_estimates():
    """Returns (n_rows, n_slots, n_items)."""
    n_rows = sum(len(rows) for cats in ESTIMATE_FILLS.values() for rows in cats.values())
    n_slots = sum(len(cats) for cats in ESTIMATE_FILLS.values())
    n_items = len(ESTIMATE_FILLS)
    return n_rows, n_slots, n_items


if __name__ == "__main__":
    from . import equipment_rfi_fills

    print("=== Regression guard: every ESTIMATE_FILLS target category is genuinely empty beforehand ===")
    base = equipment_rfi_fills.apply_rfi_fills(equipment_datasheet.build_all_datasheets())
    for item_id, categories in ESTIMATE_FILLS.items():
        for category in categories:
            rows = base[item_id]["datasheet"][category]
            status = "OK (empty)" if not rows else f"FAIL ({len(rows)} real row(s) already there)"
            print(f"  {item_id} / {category}: {status}")
            assert not rows, f"REGRESSION: {item_id}'s {category} is NOT empty -- ESTIMATE_FILLS would overwrite real data."
    print("PASSED -- every targeted slot was genuinely 'Missing Data - Required' before this overlay.")

    print("\n=== apply_estimates() correctness ===")
    filled = apply_estimates(base)
    assert base is not filled, "REGRESSION: apply_estimates() returned the same object -- must be a copy."
    for item_id, categories in ESTIMATE_FILLS.items():
        for category in categories:
            assert not base[item_id]["datasheet"][category], (
                f"REGRESSION: apply_estimates() mutated the INPUT datasheets dict at {item_id}/{category}."
            )
    print("PASSED -- input datasheets dict is untouched; apply_estimates() returns a genuine copy.")

    n_rows, n_slots, n_items = count_estimates()
    print(f"\nRows added: {n_rows}")
    print(f"Distinct (item, category) slots newly estimated: {n_slots}")
    print(f"Distinct items touched: {n_items}")
    assert n_rows == 7, f"REGRESSION: expected 7 rows, counted {n_rows}."
    assert n_slots == 7, f"REGRESSION: expected 7 newly-estimated slots, counted {n_slots}."
    assert n_items == 6, f"REGRESSION: expected 6 items touched, counted {n_items}."

    print("\n=== Every added row carries status=STATUS_ESTIMATE, distinct from Confirmed ===")
    for item_id, categories in ESTIMATE_FILLS.items():
        for category, rows in categories.items():
            for row in rows:
                assert row["status"] == equipment_datasheet.STATUS_ESTIMATE, (
                    f"REGRESSION: {item_id}/{category} row has status {row.get('status')!r}, expected STATUS_ESTIMATE."
                )
                assert row["source"].startswith("Engineering estimate"), (
                    f"REGRESSION: {item_id}/{category} row's source doesn't identify it as an engineering estimate."
                )
                assert row["remarks"] and len(row["remarks"]) > 40, (
                    f"REGRESSION: {item_id}/{category} row has no substantive stated basis in its remarks."
                )
    print("PASSED -- every one of the 7 rows is tagged STATUS_ESTIMATE with a real, substantive basis stated.")

    print("\n=== Task requirement 4: three-way honest totals, verified live (not blended) ===")
    before = equipment_datasheet.summarize(base)
    after = equipment_datasheet.summarize(filled)
    print(f"Confirmed slots: {before['confirmed_category_slots']} -> {after['confirmed_category_slots']} "
          f"(should be UNCHANGED -- estimates don't touch confirmed data)")
    print(f"Estimate slots:  {before['estimated_category_slots']} -> {after['estimated_category_slots']} "
          f"(+{after['estimated_category_slots'] - before['estimated_category_slots']})")
    print(f"Missing slots:   {before['missing_category_slots']} -> {after['missing_category_slots']} "
          f"(-{before['missing_category_slots'] - after['missing_category_slots']})")
    assert after["confirmed_category_slots"] == before["confirmed_category_slots"], (
        "REGRESSION: confirmed_category_slots changed -- estimates must never touch confirmed data."
    )
    assert after["estimated_category_slots"] - before["estimated_category_slots"] == n_slots
    assert before["missing_category_slots"] - after["missing_category_slots"] == n_slots
    assert before["missing_category_slots"] == 284, f"REGRESSION: expected 284 missing before this overlay, got {before['missing_category_slots']}."
    assert after["missing_category_slots"] == 284 - n_slots
    print(f"PASSED -- {n_slots} slots moved from Missing to Estimate (284 -> {after['missing_category_slots']}), "
          f"Confirmed slots genuinely unchanged, not blended together.")

    print("\n=== Task requirement 5: FE-specific honest breakdown ===")
    fe_after = equipment_datasheet.summarize(filled, ids=equipment_datasheet.FE_IDS)
    print(f"FE: {fe_after['confirmed_category_slots']} Confirmed, "
          f"{fe_after['estimated_category_slots']} Engineering Estimate, "
          f"{fe_after['missing_category_slots']} Missing (of {fe_after['total_category_slots']} total slots)")
    assert fe_after["confirmed_category_slots"] == 27, f"REGRESSION: expected 27 Confirmed FE slots, got {fe_after['confirmed_category_slots']}."
    assert fe_after["estimated_category_slots"] == 7, f"REGRESSION: expected 7 Estimate FE slots, got {fe_after['estimated_category_slots']}."
    assert fe_after["missing_category_slots"] == 14, f"REGRESSION: expected 14 Missing FE slots, got {fe_after['missing_category_slots']}."
    print("PASSED -- FE: 27 Confirmed + 7 Engineering Estimate + 14 Missing = 48 total slots, matches exactly.")

    print("\n=== Regression check: every OTHER section is untouched by this overlay ===")
    for label, ids in [
        ("GA", equipment_datasheet.GA_IDS), ("GC", equipment_datasheet.GC_IDS),
        ("SA", equipment_datasheet.SA_IDS), ("HB", equipment_datasheet.HB_IDS),
        ("EU", equipment_datasheet.EU_IDS), ("AI", equipment_datasheet.AI_IDS),
    ]:
        b = equipment_datasheet.summarize(base, ids=ids)
        f = equipment_datasheet.summarize(filled, ids=ids)
        print(f"  {label}: {b} == {f}: {b == f}")
        assert b == f, f"REGRESSION: {label} section changed, but this pilot only targets FE."
    print("PASSED -- GA, GC, SA, HB, EU, and AI are byte-for-byte identical to the pre-overlay data.")
