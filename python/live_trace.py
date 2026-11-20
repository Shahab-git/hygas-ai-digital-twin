"""P2-2: a per-cycle trace of the model, for the Summary tab's charts. CLASS: simulated output of the
unchanged quasi-steady engine (no plant data, nothing validated).

`run_trace(n)` runs the engine for n cycles from a cold start and records, after each cycle, a few values
read from the published snapshot (the same KPI function the Digital Twin tab uses). What the charts show
is the engine's own start-up behaviour: the lagged couplings converging (about five cycles) and the
hydrogen inventory filling. Cycle numbers are model cycles, not seconds: the engine has no time-domain
dynamics (see CLAUDE.md, known limitations).

Numeric check (comment, project convention): the last point of each series equals the same value read from
a plain build_live_snapshot(n) (asserted in tests/test_a3_live_trace.py).
"""
from . import fe_feed_handling as fe
from . import plant_status as ps
from . import tab1_integration as t1

SERIES = (
    ("h2_kg_h", "Hydrogen production (kg/h)", "total_h2_production"),
    ("syngas_nm3_h", "Clean syngas (Nm3/h)", "total_syngas_production"),
    ("storage_kg", "Hydrogen storage level (kg)", "h2_storage_level"),
    ("grid_kw", "Electrical consumption (kW)", "total_electrical_consumption"),
)
COOLING_LABEL = "Cooling demand EU-008 (kW)"


def _val(kpi):
    v = kpi.get("value") if kpi.get("status") != "Missing" else None
    return None if v is None else float(v)


def _feed_step_override(nominal, at_cycle, new_value):
    """Override for FE-001's delivery rate: `nominal` before cycle `at_cycle`, `new_value` from it on. The engine calls
    the function once per cycle, so a closure counter is the cycle index (Assumed what-if input, as in ui_transient_sim)."""
    count = {"n": 0}

    def fn(get_input):
        count["n"] += 1
        v = new_value if count["n"] >= at_cycle else nominal
        return {"value": v, "status": ps.STATUS_ASSUMED, "inputs": [], "validation_basis": ps.VALIDATION_NA,
                "confidence_note": "What-if feed step for the Summary trace (Assumed)."}
    return fn


def row_from_snapshot(cycle, snap):
    """One trace row (cycle, the SERIES values, cooling_kw, feed_kg_h) read from a published snapshot. Shared with python/live_runner.py (P4-1)."""
    k = t1.compute_tab1_kpis(snap)
    row = {"cycle": cycle}
    for name, _label, kpi in SERIES:
        row[name] = _val(k[kpi])
    sup = snap.get(("EU-008", "CoolingSupply"))
    row["cooling_kw"] = None if not sup or sup.get("status") == "Missing" else float(sup["value"]["demand_kw"])
    fe_in = snap.get(("FE-001-INPUT", "msw_delivery_rate_kg_h"))
    row["feed_kg_h"] = None if not fe_in or fe_in.get("status") == "Missing" else float(fe_in["value"])
    return row


def run_trace(n_cycles=20, feed_step=None):
    """feed_step: optional (at_cycle, kg_h) -- the as-received feed rate changes at that cycle (a what-if)."""
    rows = []
    overrides = None
    if feed_step is not None:
        overrides = {("FE-001-INPUT", "msw_delivery_rate_kg_h"):
                     _feed_step_override(fe.FE001_DEFAULT_DELIVERY_RATE_KG_H, feed_step[0], feed_step[1])}

    t1.build_live_snapshot(n_cycles, overrides=overrides, on_cycle=lambda i, snap: rows.append(row_from_snapshot(i, snap)))
    return rows
