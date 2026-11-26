"""P2-1: data for the "Summary" tab (partner front page). CLASS: presentation of model results.

Every number is READ from a plant-state snapshot (the same dict the other tabs use); nothing here is a
typed result. The one reference figure that is not read from the snapshot, DOK-ING's stated ~50 kg/day of
hydrogen from 1 tpd of standard high-calorific plastic, is quoted from data/dokink_rfi_answers.md, answer 6
(it is for plastic waste, not for this model's MSW feed), and is labelled as such.

Numeric check (comment, as the project convention asks): daily H2 = HB-012 h2_kg_h x 24, a unit conversion
of a published value; test_summary_tab.py asserts it against the snapshot.
"""
from . import tab1_integration as t1

DOKING_H2_KG_DAY_PLASTIC = 50.0   # RFI #1/#6, plastic feed, not this model's MSW feed
STATUSES = ("Measured", "Calculated", "Estimated", "Assumed", "Missing")

OPEN_ITEMS = (
    "Syngas composition at the reactor exit, whether the char share (40 to 50% of the feed) includes ash, and the feed LHV (15-20 MJ/kg)",
    "Wet or dry basis of the 1 tonne/day feed rate",
    "Rate constants for the LOHC reactors (HB-014, HB-016)",
)
NO_MEASUREMENTS_ITEM = "Plant measurements: none exist yet, so every value is a model result"


def _num(entry):
    return entry["value"] if entry and entry.get("status") != "Missing" else None


def summary_data(snapshot):
    """Pure function of a snapshot. Returns plain data for the page; no Streamlit calls."""
    kpis = t1.compute_tab1_kpis(snapshot)
    counts = {s: 0 for s in STATUSES}
    for e in snapshot.values():
        counts[e.get("status")] = counts.get(e.get("status"), 0) + 1
    h2_kg_h = _num(kpis["total_h2_production"])
    comp = _num(kpis["syngas_composition"])
    supply = snapshot.get(("EU-008", "CoolingSupply"))
    est = snapshot.get(("EU-008", "RecommendedCapacityEstimate"))
    cooling = None
    if supply and supply.get("status") != "Missing" and est and est.get("status") != "Missing":
        cooling = {"demand_kw": float(supply["value"]["demand_kw"]),
                   "rating_kw": float(est["value"]["actual_dokking_value_kw"])}
    return {
        "total": len(snapshot), "counts": counts,
        "overall_status": _num(kpis["overall_plant_status"]),
        "feed_kg_h": _num(kpis["total_feedstock_input"]),
        "h2_kg_h": None if h2_kg_h is None else float(h2_kg_h),
        "h2_kg_day": None if h2_kg_h is None else float(h2_kg_h) * 24.0,
        "h2_reference_kg_day": DOKING_H2_KG_DAY_PLASTIC,
        "syngas_nm3_h": _num(kpis["total_syngas_production"]),
        "syngas_h2_mol_pct": None if comp is None else comp.get("H2_mol_pct_dry"),
        "psa_recovery": _num(kpis["h2_recovery"]),
        "cooling": cooling,
        "open_items": OPEN_ITEMS + ((NO_MEASUREMENTS_ITEM,) if counts["Measured"] == 0 else ()),
    }
