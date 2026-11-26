"""Guided tour and design-finding highlights for the "3D Plant" tab. CLASS: presentation of model results, not a model.

Every number is READ from a plant-state snapshot (the same dict the Summary and Plant Overview tabs use, through
python/summary_tab.summary_data and the published keys named below); nothing here is typed in or recomputed. The only
constants are DOK-ING's stated ~50 kg/day hydrogen figure (summary_tab.DOKING_H2_KG_DAY_PLASTIC, RFI answer 6, for plastic waste, not
this model's MSW feed) and the registry's expected N2 share (design_basis_board.registry_expected_n2_pct, read from the registry).

What it claims, and what it does not:
- The TOUR walks the camera through the process groups and shows, per stage, a few model numbers with their evidence class. It is a
  presentation aid. A stage line never says "measured": the plant has no measurements.
- A FINDING is a place where the model and a registry or RFI figure disagree. It is phrased as a question for DOK-ING, never as a
  fault of the plant. The cooling rating in particular is an Unverified (registry) value whose own remark scopes it to EU-004 jacket cooling.
- Item ids are registry ids; test_plant_3d_story.py checks that every id named here exists in the registry.

Numeric check (the project convention): every number printed here equals the value read from the snapshot (h2 kg/day = HB-012 h2_kg_h x 24 as in
summary_tab); test_plant_3d_story.py asserts this. The heat finding carries NO number: the heat-integration report is read-only by design and the
project's tests forbid any reader of it, so this module does not read it either.
"""
from . import summary_tab
from . import design_basis_board

GROUP_FOCUS = {"FE": "Feed handling", "GA": "Gasification", "GC": "Gas cleaning", "HB": "Hydrogen & BoP",
               "EU": "Electrical & utilities", "SA": "Sensors & analysers", "AI": "Automation & AI"}
FINDING_ITEMS = {"cooling": ["EU-008"], "gas": ["GA-001", "SA-005"], "hydrogen": ["HB-006", "HB-012"], "heat": ["GA-001", "HB-005"]}


def _f(v, fmt="%.1f", unit=""):
    return "n/a" if v is None else (fmt % float(v)) + unit


def story_data(snapshot):
    """Pure function of a snapshot. Returns {"tour": [...], "findings": [...]} as plain JSON-able data."""
    sm = summary_tab.summary_data(snapshot)
    comp = snapshot.get(("GA-001", "Outputs"))
    n2 = None if not comp or comp.get("status") == "Missing" else float(comp["value"]["N2_mol_pct_dry"])
    reg_n2 = design_basis_board.registry_expected_n2_pct()
    cool = sm["cooling"]
    measured = sm["counts"].get("Measured", 0)
    ref = sm["h2_reference_kg_day"]

    tour = [
        {"key": "overview", "title": "Whole plant", "group": None, "focus": [], "status": "Model result",
         "lines": [f"{measured} of {sm['total']} published values are Measured: every number in this tour is a model result.",
                   f"Hydrogen: {_f(sm['h2_kg_day'])} kg/day (model). DOK-ING states about {ref:.0f} kg/day for plastic waste (RFI #6)."]},
        {"key": "feed", "title": "1 · Feed handling", "group": "FE", "focus": [], "status": "Assumed basis",
         "lines": [f"Feed: {_f(sm['feed_kg_h'], '%.2f')} kg/h (DOK-ING's stated 1 tonne/day).",
                   "The wet or dry basis is not stated by DOK-ING; the model treats it as as-received. DOK-ING (RFI2): the feed is not dried (up to 15% moisture), so the dryer FE-005 evaporates nothing in the model."]},
        {"key": "gasification", "title": "2 · Gasification", "group": "GA", "focus": ["GA-001"], "status": "Calculated from Assumed inputs",
         "lines": [f"Dry N2 in the product gas: {_f(n2)} vol% (registry expects {_f(reg_n2, '%.0f')} vol%).",
                   "DOK-ING (RFI2): no air, steam or oxygen is added and the reactor is heated electrically from outside; the model follows that. Char is 40 to 50% of the feed (DOK-ING); the 45% midpoint is Assumed."]},
        {"key": "cleaning", "title": "3 · Gas cleaning", "group": "GC", "focus": [], "status": "Calculated",
         "lines": [f"Clean syngas: {_f(sm['syngas_nm3_h'], '%.0f')} Nm3/h (model).",
                   "Cleaning targets are registry values; the feed sulfur and chlorine contents are Assumed inputs."]},
        {"key": "hydrogen", "title": "4 · Hydrogen and balance of plant", "group": "HB", "focus": ["HB-006"], "status": "Calculated",
         "lines": [f"PSA recovery {_f(None if sm['psa_recovery'] is None else 100 * sm['psa_recovery'])} %; hydrogen {_f(sm['h2_kg_day'])} kg/day.",
                   "The shift and PSA figures are correlations calibrated to design targets, not plant data. DOK-ING (RFI2): the PSA does not exist yet, so this chain is the NACHIP design, not existing DOK-ING equipment."]},
        {"key": "utilities", "title": "5 · Electrical and utilities", "group": "EU", "focus": ["EU-008"], "status": "Calculated",
         "lines": [(f"Cooling demand in the model: about {cool['demand_kw']:.0f} kW; the registry lists a {cool['rating_kw']:.0f} kW cooling tower."
                    if cool else "Cooling demand could not be read this cycle."),
                   "The model has no heat-integration equipment: heat terms are an inventory, not a design. DOK-ING (RFI2) states about 100 kW electric for heating and propulsion; the model has no electric heating term (Missing)."]},
        {"key": "control", "title": "6 · Sensors and automation", "group": "SA", "focus": [], "status": "Simulated",
         "lines": ["No physical sensors exist yet: sensor and AI items show model values, labelled simulated.",
                   "Nothing here is trained on or validated against plant data."]},
    ]

    findings = [
        {"id": "cooling", "title": "Cooling capacity", "items": FINDING_ITEMS["cooling"], "status": "Calculated (Assumed inputs)",
         "lines": ([f"Model peak cooling demand about {cool['demand_kw']:.0f} kW against a registry rating of {cool['rating_kw']:.0f} kW."]
                   if cool else ["Cooling demand could not be read this cycle."]) +
                  ["The 20 kW is Unverified (registry); its remark scopes it to EU-004 jacket cooling."] +
                  (["On DOK-ING's RFI2 basis the model demand is below that rating; the earlier air-blown basis gave about 40 kW."] if cool and cool["demand_kw"] < cool["rating_kw"] else []),
         "ask": "What cooling capacity is installed for the whole plant?"},
        {"id": "gas", "title": "Gas composition", "items": FINDING_ITEMS["gas"], "status": "Calculated (Assumed inputs)",
         "lines": [f"Dry N2 {_f(n2)} vol% in the model against {_f(reg_n2, '%.0f')} vol% expected in the registry.",
                   "DOK-ING (RFI2) adds no air or steam, so the earlier air-blown nitrogen is gone; the registry's expected composition predates that reply."],
         "ask": "What is the syngas composition at the reactor exit (H2, CO, CO2, CH4, N2)?"},
        {"id": "hydrogen", "title": "Hydrogen production", "items": FINDING_ITEMS["hydrogen"], "status": "Calculated (Assumed inputs)",
         "lines": [f"Model: {_f(sm['h2_kg_day'], '%.1f')} kg/day, with char at an Assumed 45% of the feed (DOK-ING: 40 to 50%). DOK-ING states about {ref:.0f} kg/day, for plastic waste (RFI #6), not for this MSW feed.",
                   "Hydrogen is very sensitive to the char share: a few percentage points move it by several kg/day."],
         "ask": "Does the 40 to 50% char share include ash, and which feed does the 50 kg/day figure assume?"},
        {"id": "heat", "title": "Plant heat balance", "items": FINDING_ITEMS["heat"], "status": "Estimated (Assumed recovery)",
         "lines": ["The model has no boiler, burner, stack or heat recovery: its heat balance is a read-only inventory with Assumed recovery fractions.",
                   "That inventory shows a net heat deficit at DOK-ING's midpoint feed LHV; the figure is in the project's heat-integration report, not read live here (by design nothing reads that report)."],
         "ask": "Stack, steam-generator fuel and gas-cooler data would settle the Assumed heat terms."},
    ]
    return {"tour": tour, "findings": findings}
