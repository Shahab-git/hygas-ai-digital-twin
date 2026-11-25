"""Simulation tab, part 1: a device picker over the 91 registry items, on the LIVE engine.

CLASS: simulated what-if on the unchanged quasi-steady engine (python/tab1_integration.py). Nothing here is
plant data and nothing is validated. Every scenario input is an ASSUMED what-if value.

What it does: pick any registry item (FE, GA, GC, SA, HB, EU, AI). It shows the item's live engine keys
(value, unit, evidence status). For an item that has live keys, the user can change a few upstream scenario
inputs (feed rate, air equivalence ratio, steam-to-feed ratio, carbon conversion, tail-gas mode) and see
that item's values against the baseline. An item without any live key is marked "no model".

What it does NOT do: write to the plant state, any database or any file; read the plant heat report;
offer a gasifier-temperature input (over 850-950 degC it moves hydrogen by 0.08 %, see CLAUDE.md, so a
slider would suggest an effect the model does not have). The baseline and the scenario each run
N_CYCLES cycles from a cold start; the engine converges in about five cycles after a step.

Numeric check (comment, project convention): with every input at its default the scenario table shows a
delta of exactly 0 for every key (tests/test_ui_simulation_tab.py).
"""
import json
import os

import pandas as pd
import streamlit as st

from . import fe_feed_handling as fe
from . import plant_status as ps
from . import tab1_integration as t1

N_CYCLES = 12
_REG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "equipment_registry.json")
_MAX_ROWS = 60

# scenario inputs: key -> (label, min, max, default, step). Ranges are tab limits, not validated ranges.
SCENARIO_INPUTS = {
    ("FE-001-INPUT", "msw_delivery_rate_kg_h"): ("As-received feed (kg/h)", 10.0, 60.0, fe.FE001_DEFAULT_DELIVERY_RATE_KG_H, 0.5),
    ("GA-001-INPUT", "equivalence_ratio"): ("Air equivalence ratio ER", 0.15, 0.40, 0.25, 0.01),
    ("GA-001-INPUT", "steam_to_feed_ratio"): ("Steam-to-feed ratio", 0.2, 0.8, 0.4, 0.05),
    ("GA-001-INPUT", "carbon_conversion_efficiency"): ("Carbon conversion", 0.80, 0.98, 0.9, 0.01),
}
TAIL_GAS_KEY = ("GA-001-INPUT", "tail_gas_mode")
TAIL_GAS_DEFAULT = "heat_only"


def registry_items():
    """[(id, name, category)] of every registry item, in file order."""
    with open(_REG_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return [(d["id"], d["name"], d.get("category", "")) for d in data]


def _override(value, note):
    def fn(get_input):
        return {"value": value, "status": ps.STATUS_ASSUMED, "inputs": [], "validation_basis": ps.VALIDATION_NA,
                "confidence_note": note}
    return fn


def build_overrides(values, tail_gas_mode):
    """Overrides only for inputs that differ from the default, so the default scenario is the baseline exactly."""
    out = {}
    for key, (label, _lo, _hi, default, _st) in SCENARIO_INPUTS.items():
        v = values.get(key, default)
        if abs(float(v) - float(default)) > 1e-12:
            out[key] = _override(float(v), f"What-if value from the Simulation tab ({label}); Assumed.")
    if tail_gas_mode != TAIL_GAS_DEFAULT:
        out[TAIL_GAS_KEY] = _override(tail_gas_mode, "What-if tail-gas mode from the Simulation tab; Assumed.")
    return out


def _reduce(snap, ids):
    """Keep only the keys of registry items (and their -INPUT keys); drop everything else."""
    red = {}
    for (eid, cat), rec in snap.items():
        base = eid[:-6] if eid.endswith("-INPUT") else eid
        if base in ids:
            red[(eid, cat)] = {"value": rec.get("value"), "unit": rec.get("unit"), "status": rec.get("status"),
                               "note": rec.get("confidence_note") or rec.get("missing_reason") or ""}
    return red


def run_snapshot(overrides_spec, ids):
    snap, _state, _eng = t1.build_live_snapshot(N_CYCLES, overrides=overrides_spec or None)
    return _reduce(snap, ids)


@st.cache_data(show_spinner=False)
def baseline(ids_tuple):
    return run_snapshot({}, set(ids_tuple))


def flatten(value, prefix=""):
    """{label: float} for a scalar or a dict of numbers (two levels). Booleans and text are skipped."""
    out = {}
    if isinstance(value, bool) or value is None:
        return out
    if isinstance(value, (int, float)):
        out[prefix or "value"] = float(value)
    elif isinstance(value, dict):
        for k, v in value.items():
            out.update(flatten(v, f"{prefix}.{k}" if prefix else str(k)) if not isinstance(v, dict) or prefix.count(".") < 1 else {})
    return out


def item_keys(snap, item_id):
    return sorted(k for k in snap if k[0] == item_id or k[0] == item_id + "-INPUT")


def item_table(base, scen, item_id):
    """Rows for one item. scen may be None (no scenario run yet)."""
    rows = []
    for key in item_keys(base, item_id):
        b = base[key]
        s = scen.get(key) if scen else None
        bf = flatten(b["value"])
        sf = flatten(s["value"]) if s else {}
        if bf:
            for label, bv in bf.items():
                sv = sf.get(label)
                rows.append({"key": key[1] if label == "value" else f"{key[1]}.{label}", "unit": b["unit"], "status": b["status"],
                             "baseline": bv, "scenario": sv, "delta": None if sv is None else sv - bv})
        else:
            txt = "n/a" if b["value"] is None else str(b["value"])[:80]
            stxt = None if not s else ("n/a" if s["value"] is None else str(s["value"])[:80])
            rows.append({"key": key[1], "unit": b["unit"], "status": b["status"], "baseline": txt, "scenario": stxt, "delta": None})
    return rows[:_MAX_ROWS]


def render():
    st.subheader("Device picker (live engine)")
    st.caption("SIMULATED what-if on the unchanged quasi-steady engine; every input below is Assumed and nothing is validated against "
               f"plant data. Each run is {N_CYCLES} cycles from a cold start (the engine converges in about five cycles after a step). "
               "Nothing is written to the plant state or any database.")
    items = registry_items()
    ids = tuple(i for i, _n, _c in items)
    labels = {i: f"{i} · {n}" for i, n, _c in items}
    cat = {i: c for i, _n, c in items}
    pick = st.selectbox("Equipment item (all registry items)", ids, format_func=lambda i: labels[i], key="_sim_dev_pick")
    try:
        base = baseline(ids)
    except Exception as exc:
        st.warning(f"Baseline run unavailable: {type(exc).__name__}")
        return
    keys = item_keys(base, pick)
    st.markdown(f"**{labels[pick]}** · {cat[pick]}")
    if not keys:
        st.info("No model: this item has no live engine key, so it cannot be simulated. Its registry data is shown in the equipment tabs.")
        return
    counts = {}
    for k in keys:
        counts[base[k]["status"]] = counts.get(base[k]["status"], 0) + 1
    st.caption("Evidence status of this item's live keys: " + ", ".join(f"{n} {s}" for s, n in sorted(counts.items())) + ".")

    st.markdown("**Scenario inputs (Assumed what-ifs)**")
    cols = st.columns(len(SCENARIO_INPUTS) + 1)
    values = {}
    for col, (key, (label, lo, hi, default, step)) in zip(cols, SCENARIO_INPUTS.items()):
        values[key] = col.slider(label, lo, hi, float(default), step, key=f"_sim_dev_{key[1]}")
    tail = cols[-1].radio("Tail-gas mode", ["heat_only", "regasify"], key="_sim_dev_tail")
    st.caption("No gasifier-temperature input: over 850-950 degC the model's hydrogen changes by 0.08 %, so a slider would suggest an "
               "effect the model does not have.")
    if st.button("Run scenario", key="_sim_dev_run"):
        with st.spinner("Running the engine..."):
            try:
                st.session_state["_sim_dev_scen"] = {
                    "inputs": (tuple(sorted(values.items())), tail),
                    "snap": run_snapshot(build_overrides(values, tail), set(ids))}
            except Exception as exc:
                st.warning(f"Scenario run failed: {type(exc).__name__}")
    saved = st.session_state.get("_sim_dev_scen")
    scen = saved["snap"] if saved else None
    if saved:
        st.caption("Scenario shown is the last run; press Run scenario again after changing the inputs.")
    rows = item_table(base, scen, pick)
    df = pd.DataFrame(rows)
    for c in ("baseline", "scenario", "delta"):
        df[c] = df[c].map(lambda v: "" if v is None else (f"{v:.4g}" if isinstance(v, float) else str(v)))
    st.dataframe(df, use_container_width=True, hide_index=True)
    if scen is None:
        st.caption("Baseline only. Press Run scenario to compare.")
