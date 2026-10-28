"""
Streamlit-free core of the "Transient What-If" tab (python/ui_transient_tab.py).

WHAT THIS IS: input validation, the hard caps, the isolated simulation run, the response-time
table and the CSV text -- everything the tab needs that is not drawing.

WHAT THIS IS NOT: it never reads or writes the plant state, never opens a database client and never
makes a network call. The simulation is python/dynamics.run_transient(), which builds its OWN
throw-away SharedPlantState and engine for every run.

WHY A CHILD PROCESS: run_transient() has to move two module-level globals while it runs
(cycle_clock's elapsed-hours override and eu_utilities_chp.EU008_DAMPING). The Streamlit server runs
every viewer's script in the same process, and app.py's own cached engine runs (Tab 1 and others) read
those same globals -- a what-if run in the server process could therefore leak a 30 s clock into
another viewer's cached numbers for up to the cache TTL (300 s). The run is done in a short-lived
child process instead (python -m python.ui_transient_sim): the server process's globals are never
touched, the child gets an environment without credentials (child_env), refuses database clients and
network connections (_install_guards), and is killed after WORKER_TIMEOUT_S.

Everything dynamic is ASSUMED (time constants in dynamics.TAU_SPECS), a what-if, not validated against plant data.
"""
import csv
import io
import json
import math
import os
import subprocess
import sys
import threading
import time

from . import dynamics as dy
from . import fe_feed_handling as fe
from . import ga001_gasifier_model as ga001
from . import plant_status as ps
from . import uncertainty

BANNER_TEXT = ("WHAT-IF SIMULATION. Not the live plant. Time constants are Assumed and not validated against plant data. "
               "This tab does not read or change the plant state published by the hourly runtime.")

# ---- hard limits (Streamlit Community Cloud has little CPU/memory: one engine cycle costs ~0.1 s on the development machine)
DT_CHOICES_S = (10, 15, 30, 60, 120)
MAX_STEPS = 240                 # sub-steps (= engine cycles) per run; 240 x ~0.1 s ~ 25 s locally
MAX_DURATION_S = 4 * 3600
MIN_DURATION_S = 600
UNRESOLVED_LABEL = "not resolved (< 2 steps)"      # shown instead of a t63 / t95 shorter than 2 x dt


def max_duration_s(dt_s):
    """The longest run the caps allow at this dt: 240 steps, and never more than 4 h (10 s -> 2400 s, 15 s -> 3600 s, 30 s -> 7200 s)."""
    return min(MAX_DURATION_S, MAX_STEPS * int(dt_s))


def clamp_duration_min(duration_min, dt_s):
    """(duration in minutes limited to what the caps allow at this dt, True if it had to be reduced). Never below the minimum run."""
    top = max_duration_s(dt_s) // 60
    value = max(MIN_DURATION_S // 60, min(int(duration_min), top))
    return value, value < int(duration_min)
WORKER_TIMEOUT_S = 300          # the child is killed after this
RESULT_MARKER = "@@WHATIF_RESULT@@"

SCENARIOS = ("feed", "er", "T")
SCENARIO_LABELS = {"feed": "Feed-rate step", "er": "ER step (air / equivalence ratio)", "T": "Gasifier T-setpoint step"}

# ---- input limits. ER: the project's own declared Assumed bounds. Feed and T: LIMITS OF THIS TAB, not validated operating ranges.
FEED_PCT_RANGE = (-30.0, 30.0)
# FIXED limits of this tab -- deliberately NOT read from uncertainty.bounds(): that function returns the DOK-ING-confirmed range once
# confirmation_loop.sync_confirmed_from_db() has replayed a database row into memory (app.py runs it before Tab 11 is built), which would silently
# narrow the slider to the confirmed band (e.g. 0.245-0.255) and make it depend on a database row. Basis: the default Assumed band of
# air_equivalence_ratio in python/uncertainty.py, point 0.25 +/- 15 % (UNCERTAINTY_FRACTION), copied here as constants. Tab limits, not a validated range.
ER_BASE = 0.25                  # the engine's base ER (uncertainty.ASSUMPTIONS point; pinned to it by a test)
ER_RANGE = (0.2125, 0.2875)     # 0.25 x (1 - 0.15), 0.25 x (1 + 0.15)
LIMITS_NOTE = "tab limits, not validated ranges"
ENVELOPE_QUESTION = ("What is the real operating envelope for feed rate, air ratio (ER) and gasifier temperature? The input limits of this tab "
                     "are not validated ranges.")


def air_ratio_status():
    """(confirmed?, text) for the air ratio, read from the IN-MEMORY uncertainty.ASSUMPTIONS only. In the app that state was already replayed from
    the confirmation table by Tab 1's existing sync; this function itself makes no database call and the limits above never depend on it."""
    if uncertainty.is_confirmed("air_equivalence_ratio"):
        lo, hi = uncertainty.bounds("air_equivalence_ratio")
        return True, f"Air ratio status: confirmation recorded, point {uncertainty.ASSUMPTIONS['air_equivalence_ratio']['point']:g}, range {lo:g}-{hi:g}"
    return False, "Air ratio status: Assumed, not confirmed"
T_RANGE = (850.0, 1000.0)       # 1000 < the Confirmed 1050 degC design temperature; 850 = low end of docs/dynamics_v0.md section 7
T_BASE = float(ga001.GA001_OPERATING_TEMPERATURE_C)                                # 950, Confirmed registry value
FEED_BASE_KG_H = float(fe.FE001_DEFAULT_DELIVERY_RATE_KG_H)

# Defaults per step type (dt, duration, step time) with the reason shown next to the controls. Measured on the development machine with the Assumed
# defaults (see docs/dynamics_v0.md, "Using the what-if tab"): the GA-001 flow reaches 63 % of an ER step in about 20 s (the recycle loop makes the
# steady-state target jump first), so only dt = 10 s samples it twice; the EU-008 demand reaches 63 % of a T step in about 54 s, which needs dt <= 15 s.
SCENARIO_DEFAULTS = {
    "feed": {"dt_s": 30, "duration_min": 120, "step_min": 10,
             "why": "the slowest lag, tau_conv = 1200 s, dominates, so dt = 30 s resolves it; 2 h shows the settling"},
    "er": {"dt_s": 10, "duration_min": 30, "step_min": 5,
           "why": "an ER step passes through tau_gas (30 s) only and the GA-001 flow reaches 63 % in about 20 s, so only dt = 10 s samples that "
                  "twice; the gas, recycle and EU-008 demand responses are over within about 10 min, so 30 min (180 steps) is enough"},
    "T": {"dt_s": 15, "duration_min": 30, "step_min": 5,
          "why": "the EU-008 demand reaches 63 % of a T step in about 54 s, which needs dt <= 15 s to be sampled twice; the responses are over "
                 "within about 8 min, so 30 min (120 steps) is enough"},
}
DEFAULTS = {
    "feed": {"dt_s": 30, "duration_min": 120, "step_min": 10,
             "why": "the slowest lag, tau_conv = 1200 s, dominates, so dt = 30 s resolves it; 2 h shows the settling"},
    "er": {"dt_s": 15, "duration_min": 30, "step_min": 5,
           "why": "an ER step only passes through tau_gas (30 s), which needs dt <= 15 s to be sampled twice per time constant; the gas, recycle "
                  "and EU-008 demand responses are over within about 10 min, so 30 min (120 steps) is enough"},
    "T": {"dt_s": 30, "duration_min": 60, "step_min": 5,
          "why": "T_gasifier = 120 s and the outputs move only weakly, so dt = 30 s resolves it; the responses are over within about 15 min"},
}
DEFAULTS = {"scenario": "feed", "feed_pct": 10.0, "er_new": ER_RANGE[1], "T_new": 920.0,
            "step_min": 10, "duration_min": 120, "dt_s": 30}

# ---- what is plotted (and the only things that ever leave the worker)
PLOT_QUANTITIES = (
    ("ga001_dry_flow_nm3_h", "GA-001 dry gas flow", "Nm3/h"),
    ("H2_pct_dry", "H2 fraction (dry)", "mol %"),
    ("CO_pct_dry", "CO fraction (dry)", "mol %"),
    ("CO2_pct_dry", "CO2 fraction (dry)", "mol %"),
    ("CH4_pct_dry", "CH4 fraction (dry)", "mol %"),
    ("N2_pct_dry", "N2 fraction (dry)", "mol %"),
    ("lhv_mj_nm3", "Syngas LHV", "MJ/Nm3"),
    ("h2_production_kg_h", "H2 production", "kg/h"),
    ("eu008_demand_kw", "EU-008 cooling demand", "kW"),
    ("eu008_supply_temp_c", "EU-008 supply temperature", "degC"),
    ("T_gasifier_C", "Gasifier temperature (T_gasifier)", "degC"),
)
TRACE_COLUMNS = ("t_s", "T_setpoint_C", "feed_kg_h", "ER", "ga001_dry_flow_target_nm3_h")
SERIES_COLUMNS = TRACE_COLUMNS + tuple(q[0] for q in PLOT_QUANTITIES)

# ---- NOT valid in a transient: never plotted, never exported. (series name in the dynamics layer, equipment, reason)
NOT_VALID_SERIES = ("hb013_storage_kg", "hb013_inflow_kg_h", "hb013_outflow_kg_h", "eu010_soc_kwh", "ai004_eu009_state")
NOT_VALID_ITEMS = (
    ("HB-013", "hydrogen storage level, inflow and outflow",
     "the stock is drained and refilled in a few steps by HB-018 and EU-006 (see HB-018); it chatters with no disturbance at all"),
    ("HB-018", "hydrogen dispensing",
     "the real dispensing demand is Missing; the model dispenses the whole previous-cycle stock every step "
     "(hb_remaining_chain.py:986-989, rated 72 kg/h), so the draw only reflects the step size"),
    ("EU-010", "UPS state of charge",
     "it integrates the EU-009 grid balance, which includes the EU-006 fuel-cell output sized from the HB-013 stock"),
    ("Derived from them", "EU-006 fuel-cell output, EU-009 grid balance, AI-004 EU-009-State and HB-013-State",
     "they inherit the HB-013 / EU-006 stock-per-step behaviour; AI-004's first-cycle state STARTING is meaningless in a transient"),
)

# ---- the three findings (text); numbers are added from the run by findings()
FINDINGS_STATIC = (
    ("Recycle loop shapes the response.",
     "GA-001 reads the PSA tail gas that HB-009 recycles to it. Here that read is a transport delay (tau_rec, Assumed) instead of the "
     "engine's one-cycle lag. After a step, GA-001's steady-state target first jumps and then relaxes as the recycle follows, so the "
     "lagged flow can overshoot its final value; a feed step is slowed by one more per-cycle lag (FE-005 to GA-001), one sub-step long."),
    ("Hydrogen storage and dispensing are not valid in a transient.",
     "HB-018 dispenses the whole previous-cycle stock each step and EU-006 sizes its hydrogen draw as stored energy divided by dt, so "
     "HB-013's level swings even with no disturbance, and EU-010 and the AI-004 states inherit that. The real dispensing profile is "
     "Missing. These quantities are therefore not shown as results; the algebraic outputs (flow, composition, LHV, H2 production, EU-008) "
     "do not depend on them. Cause and trials: docs/dynamics_v0.md section 4."),
    ("Gasifier temperature barely moves the outputs.",
     "GA-001 uses temperature only in the water-gas-shift equilibrium constant (no energy balance, carbon conversion fixed at 0.90, tar "
     "Missing). The thermal lag T_gasifier is therefore nearly decorative until the model has a temperature-dependent conversion."),
)

# ---- what the lags are asked of DOK-ING is in dynamics.TAU_SPECS (value, range, reasoning, question) -- single source


class WhatIfError(Exception):
    """A run that failed or was refused; the message is meant for the user (one or two sentences, no traceback)."""


class WhatIfBusy(WhatIfError):
    """Another what-if run is in progress in this server process."""


# =============================================================================================== parameters / validation
def tau_ranges():
    return {name: tuple(spec.range_s) for name, spec in dy.TAU_SPECS.items()}


def default_taus():
    return {name: float(spec.default_s) for name, spec in dy.TAU_SPECS.items()}


def snap_to_dt(seconds, dt_s):
    """Nearest multiple of dt (at least dt): the step must fall on a sub-step boundary so the 'before' row exists."""
    return int(max(1, round(float(seconds) / dt_s)) * dt_s)


def check_resolution(taus, dt_s):
    """(blocked, warned): lists of (name, tau_s). BLOCKED = tau < dt: the lag completes inside one sub-step, so its response is a single
    sample and t63 / t95 cannot be read (measured: tau = dt/2 gave a 24 % dt-spread of t95, tau = dt gave 0.3 %, tests/test_dynamics.py).
    WARNED = tau < 2 dt: poorly resolved (the project's convergence tests need tau >= 2 dt). Blocking at tau < 2 dt would leave no
    runnable combination at the Assumed defaults (tau_gas = 30 s)."""
    blocked = [(n, t) for n, t in taus.items() if t < dt_s]
    warned = [(n, t) for n, t in taus.items() if dt_s <= t < 2 * dt_s]
    return blocked, warned


def normalise_params(raw):
    """Fills defaults, snaps the step time to a sub-step boundary and returns plain numbers. Does not validate."""
    p = dict(DEFAULTS)
    p.update({k: v for k, v in (raw or {}).items() if k != "taus"})
    taus = default_taus()
    taus.update({k: float(v) for k, v in ((raw or {}).get("taus") or {}).items()})
    dt_s = int(p["dt_s"])
    duration_s = int(round(float(p["duration_min"]) * 60))
    step_s = int(round(float(p["step_min"]) * 60))
    if dt_s in DT_CHOICES_S:
        step_s = snap_to_dt(step_s, dt_s)
        duration_s = snap_to_dt(duration_s, dt_s)
    return {"scenario": p["scenario"], "feed_pct": float(p["feed_pct"]), "er_new": float(p["er_new"]), "T_new": float(p["T_new"]),
            "step_s": step_s, "duration_s": duration_s, "dt_s": dt_s, "taus": taus}


def validate_params(p):
    """List of user-facing error strings (empty = runnable). Enforced again inside the worker: the browser is not trusted."""
    errors = []
    if p.get("scenario") not in SCENARIOS:
        errors.append(f"Unknown scenario {p.get('scenario')!r}.")
    elif p["scenario"] == "feed" and not FEED_PCT_RANGE[0] <= p["feed_pct"] <= FEED_PCT_RANGE[1]:
        errors.append(f"Feed change must be within {FEED_PCT_RANGE[0]:g} to {FEED_PCT_RANGE[1]:g} % ({LIMITS_NOTE}).")
    elif p["scenario"] == "er" and not ER_RANGE[0] <= p["er_new"] <= ER_RANGE[1]:
        errors.append(f"New ER must be within the limits of this tab, {ER_RANGE[0]:.4g} to {ER_RANGE[1]:.4g} ({LIMITS_NOTE}).")
    elif p["scenario"] == "T" and not T_RANGE[0] <= p["T_new"] <= T_RANGE[1]:
        errors.append(f"New T setpoint must be within {T_RANGE[0]:g} to {T_RANGE[1]:g} degC ({LIMITS_NOTE}).")

    ranges = tau_ranges()
    if set(p.get("taus", {})) != set(ranges):
        errors.append("The five time constants must all be given: " + ", ".join(sorted(ranges)) + ".")
    for name, (lo, hi) in ranges.items():
        value = p.get("taus", {}).get(name)
        if value is None or not (isinstance(value, (int, float)) and math.isfinite(value)) or not lo <= value <= hi:
            errors.append(f"{name} = {value} s is outside its declared range {lo:g} to {hi:g} s.")

    dt_s = p.get("dt_s")
    if dt_s not in DT_CHOICES_S:
        errors.append(f"dt must be one of {', '.join(str(d) for d in DT_CHOICES_S)} s.")
        return errors
    duration_s, step_s = p["duration_s"], p["step_s"]
    if duration_s > MAX_DURATION_S:
        errors.append(f"Cap hit: the duration is limited to {MAX_DURATION_S // 3600} h ({MAX_DURATION_S // 60} min) to protect the server's CPU.")
    if duration_s < MIN_DURATION_S:
        errors.append(f"The duration must be at least {MIN_DURATION_S // 60} min.")
    n_steps = duration_s // dt_s
    if n_steps > MAX_STEPS:
        errors.append(f"Cap hit: at most {MAX_STEPS} steps per run (duration / dt = {n_steps}). At dt = {dt_s} s that is "
                      f"{MAX_STEPS * dt_s // 60} min; shorten the run or choose a larger dt.")
    if step_s < dt_s or step_s > duration_s - dt_s:
        errors.append(f"The step time must be between {dt_s} s and {duration_s - dt_s} s (one sub-step before the end).")
    if not isinstance(p.get("taus"), dict):
        return errors
    blocked, _warned = check_resolution({k: v for k, v in p["taus"].items() if isinstance(v, (int, float))}, dt_s)
    for name, value in blocked:
        errors.append(f"{name} = {value:g} s is shorter than dt = {dt_s} s: its response would fit inside one step and cannot be "
                      f"resolved. Choose a smaller dt or raise {name}.")
    return errors


def build_scenario(p):
    """(scenario list for dynamics.run_transient, final steady-state inputs, magnitude text)."""
    t = float(p["step_s"])
    if p["scenario"] == "feed":
        return [{"t_s": t, "feed_rel": p["feed_pct"] / 100.0}], {"feed_kg_h": FEED_BASE_KG_H * (1.0 + p["feed_pct"] / 100.0)}, \
            f"feed rate {p['feed_pct']:+g} % (from {FEED_BASE_KG_H:g} kg/h as received)"
    if p["scenario"] == "er":
        return [{"t_s": t, "ER": p["er_new"]}], {"ER": p["er_new"]}, f"ER {ER_BASE:g} -> {p['er_new']:g}"
    return [{"t_s": t, "T_setpoint_C": p["T_new"]}], {"T_setpoint_C": p["T_new"]}, f"T setpoint {T_BASE:g} -> {p['T_new']:g} degC"


# ======================================================================================================= metrics
def time_to_fraction(series, column, x0, x_final, fraction, t_step):
    """Seconds after the step until `column` has covered `fraction` of (x_final - x0); linearly interpolated.
    None if never reached or the change is zero.  Identical to scripts/run_transient_demo.py (pinned by a test)."""
    if x_final == x0:
        return None
    previous = None
    for row in series:
        if row["t_s"] < t_step:
            continue
        f = (row[column] - x0) / (x_final - x0)
        if f >= fraction:
            if previous is None:
                return row["t_s"] - t_step
            (t_a, f_a) = previous
            return t_a + (fraction - f_a) / (f - f_a) * (row["t_s"] - t_a) - t_step
        previous = (row["t_s"], f)
    return None


def steady_state(inputs):
    """The steady-state engine at `inputs` (converged: 30 hourly cycles), independent of the transient layer -- the same definition
    as scripts/run_transient_demo.py. Returns ({column: value}, status of the GA-001 entry)."""
    from . import tab1_integration

    def override(value):
        return lambda get_input: {"value": value, "status": ps.STATUS_ASSUMED, "validation_basis": ps.VALIDATION_NA,
                                  "confidence_note": "what-if tab steady-state reference input"}

    overrides = {}
    if "feed_kg_h" in inputs:
        overrides[("FE-001-INPUT", "msw_delivery_rate_kg_h")] = override(inputs["feed_kg_h"])
    if "ER" in inputs:
        overrides[("GA-001-INPUT", "equivalence_ratio")] = override(inputs["ER"])
    if "T_setpoint_C" in inputs:
        overrides[("GA-001-INPUT", "operating_temperature_C")] = override(inputs["T_setpoint_C"])
    snap, _state, _engine = tab1_integration.build_live_snapshot(n_cycles=30, overrides=overrides or None)
    out = snap[("GA-001", "Outputs")]["value"]
    values = {"ga001_dry_flow_nm3_h": out["dry_flow_nm3_h"], "H2_pct_dry": out["H2_mol_pct_dry"], "CO_pct_dry": out["CO_mol_pct_dry"],
              "CO2_pct_dry": out["CO2_mol_pct_dry"], "CH4_pct_dry": out["CH4_mol_pct_dry"], "N2_pct_dry": out["N2_mol_pct_dry"],
              "lhv_mj_nm3": snap[("SA-006", "Reading")]["value"],
              "h2_production_kg_h": snap[("HB-012", "Compressor")]["value"]["h2_kg_h"],
              "eu008_demand_kw": snap[("EU-008", "CoolingSupply")]["value"]["demand_kw"],
              "eu008_supply_temp_c": snap[("EU-008", "CoolingSupply")]["value"]["supply_temp_c"],
              "T_gasifier_C": inputs.get("T_setpoint_C", T_BASE)}
    return {k: float(v) for k, v in values.items()}, snap[("GA-001", "Outputs")]["status"]


def response_table(series, step_s, steady_final, dt_s):
    """One row per plotted quantity. before = value at the end of the sub-step before the step acts (row at t = step), final = the
    independent steady-state engine at the final inputs, t63 / t95 = seconds after the step (demo definitions: fraction 0.632 / 0.95).
    A change smaller than 0.01 % of the starting value is flagged not meaningful (as in the demo's results page). A t63 / t95 shorter than
    2 x dt is flagged unresolved: it lies within one or two samples, so it is an interpolation, not a measurement of the response. The
    numbers stay in the payload; the display and the CSV show UNRESOLVED_LABEL instead."""
    before_row = next(r for r in series if r["t_s"] == step_s)
    last = series[-1]
    rows = []
    for key, label, unit in PLOT_QUANTITIES:
        x0, xf, x_end = before_row[key], steady_final[key], last[key]
        change = xf - x0
        meaningful = abs(change) > 1e-4 * abs(x0) if x0 else abs(change) > 1e-12
        entry = {"key": key, "label": label, "unit": unit, "before": x0, "end_of_run": x_end, "final": xf, "change": change,
                 "meaningful": bool(meaningful), "t63": None, "t95": None, "peak_pct": None, "end_pct": None,
                 "t63_unresolved": False, "t95_unresolved": False}
        if meaningful:
            entry["t63"] = time_to_fraction(series, key, x0, xf, 0.632, step_s)
            entry["t95"] = time_to_fraction(series, key, x0, xf, 0.95, step_s)
            entry["t63_unresolved"] = entry["t63"] is not None and entry["t63"] < 2 * dt_s
            entry["t95_unresolved"] = entry["t95"] is not None and entry["t95"] < 2 * dt_s
            fractions = [(r[key] - x0) / change * 100.0 for r in series if r["t_s"] >= step_s]
            entry["peak_pct"] = max(fractions)
            entry["end_pct"] = (x_end - x0) / change * 100.0
        rows.append(entry)
    return rows


def findings(payload):
    """The three findings: static text plus, where this run allows it, numbers computed from THIS run (never typed in)."""
    series, step_s = payload["series"], payload["params"]["step_s"]
    after = [r for r in series if r["t_s"] >= step_s]
    texts = [list(f) for f in FINDINGS_STATIC]
    flow = next(r for r in payload["response"] if r["key"] == "ga001_dry_flow_nm3_h")
    if flow["meaningful"]:
        change = flow["change"]
        peak_flow = max((r["ga001_dry_flow_nm3_h"] - flow["before"]) / change * 100.0 for r in after)
        peak_target = max((r["ga001_dry_flow_target_nm3_h"] - flow["before"]) / change * 100.0 for r in after)
        texts[0][1] += (f" In this run the lagged GA-001 flow peaks at {peak_flow:.0f} % of its final change and the steady-state "
                        f"target at {peak_target:.0f} %.")
    h2 = next(r for r in payload["response"] if r["key"] == "h2_production_kg_h")
    if payload["params"]["scenario"] == "T":
        texts[2][1] += (f" In this run a setpoint change of {payload['params']['T_new'] - T_BASE:+g} degC changes the dry flow by "
                        f"{100.0 * flow['change'] / flow['before']:+.2f} % and H2 production by {100.0 * h2['change'] / h2['before']:+.3f} %.")
    else:
        texts[2][1] += " Run the T-setpoint scenario to see the size of the effect."
    return [tuple(t) for t in texts]


# ====================================================================================================== the run itself
def simulate(params):
    """Runs the transient and builds the payload. Used by the worker process and directly by tests (it must be database- and
    network-free; nothing here touches the server's plant state). `params` must already be normalised."""
    errors = validate_params(params)
    if errors:
        raise WhatIfError(" ".join(errors))
    started = time.perf_counter()
    scenario, final_inputs, magnitude = build_scenario(params)
    result = dy.run_transient(scenario, dt_s=float(params["dt_s"]), duration_s=float(params["duration_s"]), taus=params["taus"])
    result.verify_honesty()
    steady_final, steady_status = steady_state(final_inputs)
    series = [{k: row[k] for k in SERIES_COLUMNS} for row in result.series]       # the NOT_VALID_SERIES never leave this function
    payload = {
        "params": params, "magnitude": magnitude, "series": series,
        "units": {k: result.units.get(k, "") for k in SERIES_COLUMNS},
        "response": response_table(series, params["step_s"], steady_final, params["dt_s"]),
        "steady_final": steady_final, "steady_status": steady_status,
        "assumptions": result.assumptions, "status": result.status, "limits": list(result.limits),
        "used_taus": list(result.used_taus), "banner": BANNER_TEXT,
        "run_seconds": time.perf_counter() - started, "n_steps": result.meta["n_steps"], "warmup_cycles": result.meta["warmup_cycles"],
        "not_valid_dropped": list(NOT_VALID_SERIES),
    }
    return payload


def _install_guards():
    """Child process only: any database client or network connection attempted by the simulation fails loudly."""
    import socket

    from . import confirmation_loop, vendor_log

    def no_database(*_args, **_kwargs):
        raise RuntimeError("the what-if worker is database-free; a database access was attempted")

    def no_network(*_args, **_kwargs):
        raise RuntimeError("the what-if worker is network-free; a connection was attempted")

    vendor_log._get_client = no_database
    confirmation_loop._get_client = no_database
    socket.socket.connect = no_network
    socket.create_connection = no_network
    if vendor_log.db_writes_allowed():
        raise RuntimeError("HYGAS_ALLOW_DB_WRITES is set; the what-if worker never writes")


_SECRET_MARKERS = ("SUPABASE", "SECRET", "TOKEN", "PASSWORD", "PASSWD", "CREDENTIAL", "KEY", "AUTH", "PRIVATE", "HYGAS")


def child_env(environ):
    """The worker's environment: the parent's, minus anything that looks like a credential, with database writes forced off."""
    env = {k: v for k, v in environ.items() if not any(m in k.upper() for m in _SECRET_MARKERS)}
    env["HYGAS_ALLOW_DB_WRITES"] = "0"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


_RUN_LOCK = threading.Lock()
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def run_in_child(params):
    """Validate, run the worker process and return its payload. One run at a time per server process (WhatIfBusy otherwise).
    Raises WhatIfError with a short user-facing message on any failure -- never a traceback."""
    errors = validate_params(params)
    if errors:
        raise WhatIfError(" ".join(errors))
    if not _RUN_LOCK.acquire(blocking=False):
        raise WhatIfBusy("Another what-if run is in progress on this server. Wait for it to finish and press Run again.")
    try:
        try:
            proc = subprocess.run([sys.executable, "-m", "python.ui_transient_sim"], input=json.dumps(params), capture_output=True,
                                  text=True, timeout=WORKER_TIMEOUT_S, cwd=ROOT, env=child_env(os.environ))
        except subprocess.TimeoutExpired:
            raise WhatIfError(f"The simulation took longer than {WORKER_TIMEOUT_S} s and was stopped. Use a larger dt or a shorter run.") from None
        except OSError as exc:
            raise WhatIfError(f"The simulation process could not be started ({type(exc).__name__}).") from None
    finally:
        _RUN_LOCK.release()
    line = next((ln for ln in reversed(proc.stdout.splitlines()) if ln.startswith(RESULT_MARKER)), None)
    if proc.returncode != 0 or line is None:
        tail = (proc.stderr.strip().splitlines() or ["no error text"])[-1][:200]
        raise WhatIfError(f"The simulation failed (exit code {proc.returncode}): {tail}")
    try:
        return json.loads(line[len(RESULT_MARKER):])
    except ValueError:
        raise WhatIfError("The simulation returned an unreadable result.") from None


def worker_main():
    _install_guards()
    params = json.loads(sys.stdin.read())
    payload = simulate(params)
    sys.stdout.write(RESULT_MARKER + json.dumps(payload) + "\n")
    sys.stdout.flush()


# ================================================================================================================ CSV
def build_csv(payload):
    """The series as CSV text with the banner, the run and the Assumed time constants as '#' header rows
    (pandas.read_csv(..., comment='#') skips them)."""
    out = io.StringIO()
    p = payload["params"]
    out.write(f"# {payload['banner']}\n# {payload['status']}\n")
    out.write(f"# run: {payload['magnitude']}; step at {p['step_s']} s; duration {p['duration_s']} s; dt {p['dt_s']} s; "
              f"{payload['n_steps']} steps after {payload['warmup_cycles']} warm-up cycles\n")
    out.write("# Assumed time constants (name, value_s, range_s, status, question for DOK-ING):\n")
    for a in payload["assumptions"]:
        out.write(f"#   {a['name']}, {a['value_s']:g}, {a['range_s'][0]:g}-{a['range_s'][1]:g}, {a['status']}, {a['question_for_doking']}\n")
    out.write("# Not included on purpose (not valid in transients): " + ", ".join(payload["not_valid_dropped"]) + "\n")
    out.write("# units: " + "; ".join(f"{k} [{u}]" for k, u in payload["units"].items()) + "\n")
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(SERIES_COLUMNS)
    for row in payload["series"]:
        writer.writerow([row[c] for c in SERIES_COLUMNS])
    return out.getvalue()


def build_response_csv(payload):
    out = io.StringIO()
    out.write(f"# {payload['banner']}\n# {payload['status']}\n# {payload['magnitude']}; t63 / t95 in seconds after the step "
              f"(fractions 0.632 / 0.95 of the change to the independent steady-state engine at the final inputs; first crossing)\n"
              f"# sampling interval dt = {payload['params']['dt_s']} s; a time shorter than 2 x dt = {2 * payload['params']['dt_s']} s is shown as "
              f"'{UNRESOLVED_LABEL}'\n")
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["quantity", "unit", "before_step", "end_of_run", "final_steady_state", "change", "t63_s", "t95_s", "peak_pct_of_change",
                     "meaningful_change"])
    for r in payload["response"]:
        writer.writerow([r["label"], r["unit"], r["before"], r["end_of_run"], r["final"], r["change"],
                         UNRESOLVED_LABEL if r["t63_unresolved"] else r["t63"], UNRESOLVED_LABEL if r["t95_unresolved"] else r["t95"],
                         r["peak_pct"], r["meaningful"]])
    return out.getvalue()


if __name__ == "__main__":
    worker_main()
