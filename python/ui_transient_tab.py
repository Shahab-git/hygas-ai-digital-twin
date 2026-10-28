"""
"Transient What-If" tab (Tab 11) -- ONE entry point: render().

A throw-away simulation of how the plant would respond to a step in the feed rate, ER or the gasifier
temperature setpoint, using the dynamics layer (python/dynamics.py) with ASSUMED time constants.

NOT the live plant. This tab never reads or writes the plant state published by the hourly runtime,
opens no database client and makes no network call. Every run happens in a short-lived child process
with its own engine and its own state (python/ui_transient_sim.py explains why a child process).
The only things it keeps are in this viewer's session (the last result) and in st.cache_data (results
keyed on all parameters).

Everything dynamic is ASSUMED, a what-if, not validated against plant data. Quantities that are not valid
in a transient (HB-013, HB-018, EU-010 and what depends on them) are listed in a box and NEVER plotted:
the worker does not even send them (ui_transient_sim.NOT_VALID_SERIES).
"""
import html
import json

import altair as alt
import pandas as pd
import streamlit as st

from . import dynamics as dy
from . import ui_transient_sim as sim

_K = "wi_"       # session-state prefix of this tab
_TAU_STEP = {"T_gasifier": 5.0, "tau_conv": 30.0, "tau_gas": 1.0, "tau_rec": 5.0, "EU008_cooling_water": 1.0}
_TAG = {"Assumed": ("#FEF3C7", "#B45309"), "Missing": ("#F3F4F6", "#6B7280"), "Calculated": ("#DBEAFE", "#1D4ED8")}


def _pretty(text):
    for a, b in (("CO2", "CO₂"), ("CH4", "CH₄"), ("H2", "H₂"), ("N2", "N₂"), ("Nm3", "Nm³")):
        text = text.replace(a, b)
    return text


def _tag(status):
    bg, fg = _TAG[status]
    return (f'<span style="display:inline-block;padding:2px 10px;border-radius:12px;font-size:0.72rem;font-weight:600;'
            f'margin-right:6px;white-space:nowrap;background:{bg};color:{fg};">{status}</span>')


def _banner():
    # the same alert styling as the KNOWN SHORTFALL banners of Tabs 5 and 7
    st.markdown(
        '<div style="background:#FEF2F2;border:2px solid #B91C1C;border-radius:8px;padding:8px 14px;margin:8px 0;">'
        f'<span style="color:#B91C1C;font-weight:800;font-size:0.85rem;">⚠️ {html.escape(sim.BANNER_TEXT)}</span></div>',
        unsafe_allow_html=True)


def _not_valid_box():
    items = "".join(f'<li><b>{html.escape(eq)}</b> — {html.escape(what)}. <i>{html.escape(why)}.</i></li>' for eq, what, why in sim.NOT_VALID_ITEMS)
    st.markdown(
        '<div style="background:#FEF2F2;border:2px solid #B91C1C;border-radius:8px;padding:10px 16px;margin:8px 0;">'
        '<span style="color:#B91C1C;font-weight:800;font-size:0.9rem;">⛔ Not valid in transients — not plotted, not exported</span> '
        f'{_tag("Missing")}<br/><span style="font-size:0.85rem;color:#111827;">The dispensing demand is <b>Missing</b> and the hydrogen stock is '
        f'drained and refilled in a few steps, so these are not results:</span><ul style="font-size:0.85rem;color:#111827;margin:4px 0 0 0;">'
        f'{items}</ul></div>', unsafe_allow_html=True)


# ----------------------------------------------------------------------------------------------------------- state
def _defaults():
    d = {_K + "scenario": sim.DEFAULTS["scenario"], _K + "feed_pct": sim.DEFAULTS["feed_pct"], _K + "er_new": sim.DEFAULTS["er_new"],
         _K + "T_new": sim.DEFAULTS["T_new"], _K + "step_min": sim.DEFAULTS["step_min"],
         _K + "duration_min": sim.DEFAULTS["duration_min"], _K + "dt_s": sim.DEFAULTS["dt_s"]}
    d.update({_K + "tau_" + n: t for n, t in sim.default_taus().items()})
    return d


def _reset_to_defaults():
    for key, value in _defaults().items():
        st.session_state[key] = value


def _on_scenario_change():
    """A new step type brings its own default dt, duration and step time (sim.SCENARIO_DEFAULTS, the reason is shown next to the controls)."""
    chosen = sim.SCENARIO_DEFAULTS[st.session_state[_K + "scenario"]]
    st.session_state[_K + "dt_s"] = chosen["dt_s"]
    st.session_state[_K + "duration_min"] = chosen["duration_min"]
    st.session_state[_K + "step_min"] = chosen["step_min"]


def _clamp_time_controls():
    """Keeps the duration and the step time inside what the caps allow at the chosen dt (before the widgets are drawn). Returns a notice or None."""
    s = st.session_state
    duration, clamped = sim.clamp_duration_min(s[_K + "duration_min"], s[_K + "dt_s"])
    notice = None
    if clamped:
        notice = (f"The duration was reduced from {s[_K + 'duration_min']} to {duration} min: at dt = {s[_K + 'dt_s']} s the caps "
                  f"({sim.MAX_STEPS} steps, {sim.MAX_DURATION_S // 3600} h) allow at most {duration} min.")
        s[_K + "duration_min"] = duration
    if s[_K + "step_min"] > duration - 1:
        s[_K + "step_min"] = max(1, duration - 1)
    return notice


def _current_params():
    s = st.session_state
    return sim.normalise_params({
        "scenario": s[_K + "scenario"], "feed_pct": s[_K + "feed_pct"], "er_new": s[_K + "er_new"], "T_new": s[_K + "T_new"],
        "step_min": s[_K + "step_min"], "duration_min": s[_K + "duration_min"], "dt_s": s[_K + "dt_s"],
        "taus": {n: s[_K + "tau_" + n] for n in dy.TAU_SPECS}})


@st.cache_data(show_spinner=False, max_entries=8, ttl=3600)
def _cached_run(params_json):
    """Keyed on ALL parameters. Exceptions are not cached by Streamlit, so a failed or busy run is retried on the next press."""
    return sim.run_in_child(json.loads(params_json))


# -------------------------------------------------------------------------------------------------------- controls
def _controls():
    s = st.session_state
    notice = _clamp_time_controls()
    st.markdown("##### 1 · The disturbance")
    st.radio("Step type", sim.SCENARIOS, key=_K + "scenario", format_func=lambda k: sim.SCENARIO_LABELS[k], horizontal=True,
             on_change=_on_scenario_change)
    c1, c2, c3 = st.columns(3)
    with c1:
        if s[_K + "scenario"] == "feed":
            st.number_input("Feed-rate change [%]", min_value=sim.FEED_PCT_RANGE[0], max_value=sim.FEED_PCT_RANGE[1], step=5.0,
                            key=_K + "feed_pct", help=f"Relative to the {sim.FEED_BASE_KG_H:g} kg/h (as received) base feed. "
                            "A limit of this tab, not a validated operating range.")
        elif s[_K + "scenario"] == "er":
            st.slider("New ER (air / equivalence ratio)", sim.ER_RANGE[0], sim.ER_RANGE[1], step=0.0025, format="%.4f", key=_K + "er_new",
                      help=f"Starts at {sim.ER_BASE:g}. The slider spans the declared Assumed range of air_equivalence_ratio "
                      "(python/uncertainty.py).")
        else:
            st.number_input("New gasifier T setpoint [°C]", min_value=sim.T_RANGE[0], max_value=sim.T_RANGE[1], step=5.0, key=_K + "T_new",
                            help=f"Starts at {sim.T_BASE:g} °C (Confirmed registry value). Limits of this tab: below the Confirmed 1050 °C "
                            "design temperature; not a validated operating range.")
    top_min = sim.max_duration_s(s[_K + "dt_s"]) // 60
    with c2:
        st.number_input("Step time [min]", min_value=1, max_value=max(1, int(s[_K + "duration_min"]) - 1), step=1, key=_K + "step_min")
    with c3:
        st.number_input("Total duration [min]", min_value=sim.MIN_DURATION_S // 60, max_value=top_min, step=5 if top_min <= 60 else 10,
                        key=_K + "duration_min", help=f"Hard caps: at most {sim.MAX_DURATION_S // 3600} h and {sim.MAX_STEPS} steps per run.")
    st.radio("Time step dt", sim.DT_CHOICES_S, key=_K + "dt_s", format_func=lambda d: f"{d} s", horizontal=True,
             help="Each step runs the full steady-state engine once (~0.1 s). A smaller dt resolves faster lags but allows a shorter run "
                  "(240 steps at most).")
    chosen = sim.SCENARIO_DEFAULTS[s[_K + "scenario"]]
    st.caption(f"At dt = {s[_K + 'dt_s']} s the longest run is **{top_min} min** ({sim.MAX_STEPS} steps; hard cap {sim.MAX_DURATION_S // 3600} h). "
               f"Defaults for this step type are dt = {chosen['dt_s']} s and {chosen['duration_min']} min: {chosen['why']}.")
    if notice:
        st.warning(notice)

    st.markdown("##### 2 · Time constants " + _tag("Assumed"), unsafe_allow_html=True)
    st.caption("All five are **Assumed** — placeholders from the registry geometry and engineering judgement, not measured. Each slider is limited "
               "to its declared range; hover the slider for the reasoning, and read the question that would replace it.")
    for name, spec in dy.TAU_SPECS.items():
        lo, hi = spec.range_s
        left, right = st.columns([3, 2])
        with left:
            st.markdown(f"**{name}** {_tag('Assumed')} <span style='font-size:0.8rem;color:#4B5563;'>{html.escape(spec.what)}</span>",
                        unsafe_allow_html=True)
            st.slider(name, float(lo), float(hi), step=_TAU_STEP[name], format="%g s", key=_K + "tau_" + name, label_visibility="collapsed",
                      help=f"{spec.reasoning}\n\nQuestion for DOK-ING: {spec.question_for_doking}")
        with right:
            st.caption(f"Range {lo:g}–{hi:g} s · default {spec.default_s:g} s. **Ask DOK-ING:** {spec.question_for_doking}")


def _resolution_messages(params):
    errors = sim.validate_params(params)
    _blocked, warned = sim.check_resolution(params["taus"], params["dt_s"])
    if warned:
        st.warning("Poorly resolved at dt = %d s (time constant shorter than 2·dt): %s. Results for these lags are coarse; a smaller dt "
                   "resolves them better." % (params["dt_s"], ", ".join(f"{n} = {t:g} s" for n, t in warned)))
    for message in errors:
        st.error(message)
    return errors


# --------------------------------------------------------------------------------------------------------- results
def _fmt(value, digits=4):
    return "—" if value is None else f"{value:.{digits}g}" if abs(value) >= 1e5 or (value != 0 and abs(value) < 1e-3) else f"{value:.{digits}f}"


def _response_frame(payload):
    rows = []
    for r in payload["response"]:
        if not r["meaningful"]:
            t63 = t95 = "n/a (change < 0.01 %)"
            peak = "—"
        else:
            t63 = (sim.UNRESOLVED_LABEL if r["t63_unresolved"] else f"{r['t63']:.0f}") if r["t63"] is not None else "not reached in this run"
            t95 = (sim.UNRESOLVED_LABEL if r["t95_unresolved"] else f"{r['t95']:.0f}") if r["t95"] is not None else "not reached in this run"
            peak = f"{r['peak_pct']:.0f}"
        rows.append({"Quantity": _pretty(r["label"]), "Unit": _pretty(r["unit"]), "Before step": _fmt(r["before"]), "End of run": _fmt(r["end_of_run"]),
                     "Final steady state": _fmt(r["final"]), "Change": _fmt(r["change"]) if r["meaningful"] else "≈ 0", "t63 [s]": t63, "t95 [s]": t95,
                     "Peak [% of change]": peak})
    return pd.DataFrame(rows)


def _long_frames(payload):
    step_min = payload["params"]["step_s"] / 60.0
    absolute, normalised = [], []
    for r in payload["response"]:
        label = f"{_pretty(r['label'])} [{_pretty(r['unit'])}]"
        for row in payload["series"]:
            minute = row["t_s"] / 60.0
            absolute.append({"quantity": label, "minute": minute, "value": row[r["key"]], "old_steady": r["before"], "new_steady": r["final"],
                             "step_min": step_min})
            if r["meaningful"]:
                normalised.append({"quantity": _pretty(r["label"]), "minute": minute, "pct": (row[r["key"]] - r["before"]) / r["change"] * 100.0})
    return pd.DataFrame(absolute), pd.DataFrame(normalised), step_min


def _absolute_chart(df, labels):
    x = alt.X("minute:Q", title="time [min]")
    line = alt.Chart().mark_line(color="#1D4ED8").encode(x=x, y=alt.Y("value:Q", title=None, scale=alt.Scale(zero=False), axis=alt.Axis(format=".6~g")))
    old = alt.Chart().mark_rule(color="#6B7280", strokeDash=[4, 3]).encode(y="old_steady:Q")
    new = alt.Chart().mark_rule(color="#B91C1C", strokeDash=[4, 3]).encode(y="new_steady:Q")
    step = alt.Chart().mark_rule(color="#111827", strokeWidth=1).encode(x="step_min:Q")
    layered = alt.layer(line, old, new, step, data=df).properties(width=230, height=120)
    return layered.facet(facet=alt.Facet("quantity:N", sort=labels, title=None), columns=3).resolve_scale(y="independent")


def _normalised_chart(df, step_min):
    lines = alt.Chart(df).mark_line().encode(x=alt.X("minute:Q", title="time [min]"), y=alt.Y("pct:Q", title="% of the change to the new steady state"),
                                               color=alt.Color("quantity:N", title=None), tooltip=["quantity:N", "minute:Q", alt.Tooltip("pct:Q", format=".1f")])
    guides = alt.Chart(pd.DataFrame({"pct": [0.0, 63.2, 95.0, 100.0]})).mark_rule(color="#9CA3AF", strokeDash=[3, 3]).encode(y="pct:Q")
    step = alt.Chart(pd.DataFrame({"minute": [step_min]})).mark_rule(color="#111827").encode(x="minute:Q")
    return (guides + step + lines).properties(height=320)


def _render_results(payload):
    p = payload["params"]
    stale = payload["params"] != _current_params()
    st.markdown("### Results " + _tag("Assumed"), unsafe_allow_html=True)
    st.caption(f"{payload['status']} · {payload['magnitude']} at t = {p['step_s'] / 60:g} min · {p['duration_s'] / 60:g} min at dt = {p['dt_s']} s "
               f"({payload['n_steps']} steps after {payload['warmup_cycles']} warm-up cycles) · run time {payload['run_seconds']:.1f} s. "
               f"Final steady state = the steady-state engine at the final inputs ({payload['steady_status']}), independent of the transient.")
    if stale:
        st.info("The inputs above have changed since this result. Press **Run what-if simulation** to update it.")

    dt = p["dt_s"]
    st.caption(f"Sampling interval dt = {dt} s. A response time shorter than 2·dt = {2 * dt} s lies inside one or two samples and is shown as "
               f"“{sim.UNRESOLVED_LABEL}”; choose a smaller dt to resolve it.")
    st.markdown("**Response times** — seconds after the step to reach 63.2 % and 95 % of the change to the new steady state "
                "(first crossing, linearly interpolated: the same definitions as `scripts/run_transient_demo.py`). A response that overshoots "
                "crosses 95 % before it has settled — read the peak column.")
    st.dataframe(_response_frame(payload), hide_index=True, use_container_width=True)

    absolute, normalised, step_min = _long_frames(payload)
    labels = list(dict.fromkeys(absolute["quantity"]))
    st.markdown("**Absolute values** — blue: what-if response · grey dashed: old steady state · red dashed: new steady state · black: the step")
    st.altair_chart(_absolute_chart(absolute, labels))
    st.markdown("**Normalised** — 0 % = old steady state, 100 % = new steady state (quantities whose change is below 0.01 % are left out)")
    if normalised.empty:
        st.caption("No quantity changes by more than 0.01 % in this run.")
    else:
        st.altair_chart(_normalised_chart(normalised, step_min), use_container_width=True)

    st.download_button("Download the series (CSV, with the banner and the Assumed time constants as header rows)", sim.build_csv(payload),
                       file_name="whatif_series.csv", mime="text/csv", key=_K + "dl_series")
    st.download_button("Download the response-time table (CSV)", sim.build_response_csv(payload), file_name="whatif_response_times.csv",
                       mime="text/csv", key=_K + "dl_response")


def _render_findings(payload):
    st.markdown("### What this tab shows")
    for title, text in (sim.findings(payload) if payload else sim.FINDINGS_STATIC):
        st.markdown(f"**{title}** {text}")
    st.markdown("### Assumed parameters and the question each becomes for DOK-ING")
    values = {a["name"]: a["value_s"] for a in payload["assumptions"]} if payload else {}
    frame = pd.DataFrame([{"Time constant": n, "Status": s.status, "Value [s]": values.get(n, s.default_s),
                           "Declared range [s]": f"{s.range_s[0]:g}–{s.range_s[1]:g}", "Question for DOK-ING": s.question_for_doking}
                          for n, s in dy.TAU_SPECS.items()])
    st.dataframe(frame, hide_index=True, use_container_width=True)
    with st.expander("Reasoning behind each Assumed value"):
        for n, s in dy.TAU_SPECS.items():
            st.markdown(f"**{n}** ({s.status}) — {s.what}. {s.reasoning}")
    with st.expander("Limits of this model"):
        for line in dy.LIMITS:
            st.markdown(f"- {line}")


# ----------------------------------------------------------------------------------------------------------- entry
def render():
    _banner()
    st.header("Transient What-If")
    st.caption("How would the plant respond if the feed rate, the air (ER) or the gasifier temperature setpoint were stepped? A throw-away "
               "simulation on top of the steady-state engine; it runs only when you press the button.")
    for key, value in _defaults().items():
        st.session_state.setdefault(key, value)
    _controls()
    params = _current_params()
    errors = _resolution_messages(params)
    steps = params["duration_s"] // params["dt_s"] if params["dt_s"] in sim.DT_CHOICES_S else 0
    st.caption(f"The step is applied at {params['step_s']} s and the run lasts {params['duration_s']} s: {steps} steps at dt = {params['dt_s']} s "
               f"(cap {sim.MAX_STEPS} steps / {sim.MAX_DURATION_S // 3600} h). Expect roughly {0.12 * steps + 6:.0f} s on a fast machine, "
               "longer on shared hosting.")

    left, right, _ = st.columns([2, 1, 3])
    run = left.button("Run what-if simulation", type="primary", disabled=bool(errors), key=_K + "run")
    right.button("Reset to defaults", on_click=_reset_to_defaults, key=_K + "reset")

    if run and not errors:
        try:
            with st.spinner(f"Running {steps} engine steps in an isolated worker … (about {0.12 * steps + 6:.0f} s)"):
                st.session_state[_K + "payload"] = _cached_run(json.dumps(params, sort_keys=True))
            st.session_state.pop(_K + "error", None)
        except sim.WhatIfError as exc:
            st.session_state[_K + "error"] = str(exc)
        except Exception as exc:       # a failed run is a message, never a traceback
            st.session_state[_K + "error"] = f"The simulation could not be run ({type(exc).__name__})."
    if st.session_state.get(_K + "error"):
        st.error(st.session_state[_K + "error"])

    st.divider()
    _not_valid_box()
    payload = st.session_state.get(_K + "payload")
    if payload:
        _render_results(payload)
    else:
        st.info("No result yet — choose a disturbance and press **Run what-if simulation**.")
    st.divider()
    _render_findings(payload)
