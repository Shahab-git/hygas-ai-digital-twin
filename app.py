"""
HYGAS-AI — Live Digital Twin Status Dashboard

Deploy at share.streamlit.io by pointing it at this repo. Uses the
verified Python physics modules in /python — the same models that were
cross-checked against the MATLAB/Simulink blocks during development.
"""
import altair as alt
import pandas as pd
import streamlit as st
from python import kinetics, psa, chp, dispatch_ga, copilot, equipment_registry, vendor_log, uncertainty, optimizer

st.set_page_config(page_title="HYGAS-AI Digital Twin", layout="wide")

# Apply any pending "jump sliders to these values" request from the
# Optimizer section (Section 6) *before* the slider widgets below are
# instantiated — Streamlit forbids writing to a widget's session_state
# key after that widget has already rendered in the same script run, so
# the actual jump has to happen up here, one rerun after the button click.
if "_pending_slider_jump" in st.session_state:
    for _k, _v in st.session_state.pop("_pending_slider_jump").items():
        st.session_state[_k] = _v

st.title("HYGAS-AI — Digital Twin Status")
st.caption("Physics-informed, agent-driven digital twin for RFNBO-compliant green hydrogen from waste")

st.divider()

# ---------------------------------------------------------------------
# Section 1 — WGS reaction kinetics (live, interactive)
# ---------------------------------------------------------------------
st.header("Water-Gas Shift Reaction Kinetics")
col1, col2 = st.columns(2)

with col1:
    st.subheader("HTS stage (Fe-Cr catalyst)")
    T_hts_C = st.slider("HTS temperature (°C)", 300, 400, 350, key="hts_t")
    ghsv_hts = st.slider("HTS space velocity (GHSV, 1/h)", 1000, 4000, 2000, key="hts_ghsv")
    X_hts = kinetics.hts_conversion(T_K=T_hts_C + 273.15, GHSV=ghsv_hts)
    st.metric("HTS conversion", f"{X_hts*100:.1f}%", help="Design target: 75.0%")

with col2:
    st.subheader("LTS stage (Cu/ZnO/Al2O3 catalyst)")
    T_lts_C = st.slider("LTS temperature (°C)", 180, 260, 220, key="lts_t")
    ghsv_lts = st.slider("LTS space velocity (GHSV, 1/h)", 1000, 4000, 2000, key="lts_ghsv")
    y_co_after_hts = 0.28 * (1 - X_hts)
    X_lts = kinetics.lts_conversion(T_K=T_lts_C + 273.15, GHSV=ghsv_lts, y_CO_in=y_co_after_hts)
    st.metric("LTS relative conversion", f"{X_lts*100:.1f}%", help="Design target: 40.0%")

overall = 1 - (1 - X_hts) * (1 - X_lts)
st.metric("Overall WGS conversion", f"{overall*100:.1f}%", help="Design target: 85.0%")

st.session_state["hts"] = {"X": X_hts, "T_C": T_hts_C, "GHSV": ghsv_hts}
st.session_state["lts"] = {"X": X_lts, "T_C": T_lts_C, "GHSV": ghsv_lts, "y_CO_in": y_co_after_hts}
st.session_state["overall"] = overall

st.divider()

# ---------------------------------------------------------------------
# Section 2 — PSA recovery (live, interactive)
# ---------------------------------------------------------------------
st.header("PSA Hydrogen Recovery")
col3, col4 = st.columns(2)
with col3:
    p_high = st.slider("Adsorption pressure (bar, absolute)", 4.0, 14.0, 8.0, key="p_high")
    p_low = st.slider("Purge pressure (bar, absolute)", 0.5, 3.0, 1.0, key="p_low")
with col4:
    y_co2 = st.slider("Feed CO2 fraction", 0.20, 0.45, 0.35, key="y_co2")

recovery = psa.psa_recovery(y_CO2=y_co2, P_high_bar_a=p_high, P_low_bar_a=p_low)
st.metric("PSA recovery", f"{recovery*100:.1f}%", help="Design target: 75.0%")

st.session_state["psa"] = {"recovery": recovery, "p_high": p_high, "p_low": p_low, "y_co2": y_co2}

st.divider()

# ---------------------------------------------------------------------
# Section 3 — CHP dispatch optimisation (on demand, since GA takes a
# few seconds — not something to re-run on every slider movement)
# ---------------------------------------------------------------------
st.header("CHP Dispatch Optimisation")
col5, col6 = st.columns(2)
with col5:
    syngas_budget = st.number_input("Syngas fuel budget (kW)", 20, 100, 60)
with col6:
    h2_budget = st.number_input("Hydrogen fuel budget (kW)", 5, 30, 15)

if st.button("Run dispatch optimisation (genetic algorithm)"):
    with st.spinner("Running genetic algorithm (150 generations)..."):
        dispatch = dispatch_ga.run_dispatch_ga(syngas_budget, h2_budget)
    st.session_state["dispatch"] = {"result": dispatch, "syngas_budget": syngas_budget, "h2_budget": h2_budget}

if "dispatch" in st.session_state:
    cols = st.columns(4)
    for i, (name, load) in enumerate(st.session_state["dispatch"]["result"].items()):
        eta = chp.chp_efficiency(load, name)
        with cols[i]:
            st.metric(name, f"{load*100:.1f}% load", f"{eta*100:.1f}% efficiency")

st.divider()

# ---------------------------------------------------------------------
# Section 4 — Validated milestones reference table
# ---------------------------------------------------------------------
st.header("Validated Milestones")
st.caption("All confirmed running live in the MATLAB/Simulink model, not just calculated")

st.table({
    "Subsystem": ["Gasifier", "Gas Cleaning", "WGS HTS", "Interstage HX",
                  "WGS LTS", "WGS Overall", "PSA Recovery"],
    "Design Target": ["46.9 kg/h", "~45.9 kg/h", "75.0%", "~4.1 kW",
                       "40.0%", "85.0%", "75.0%"],
    "Simulink Result": ["46.88 kg/h", "45.94 kg/h", "75.0%", "4.134 kW",
                         "40.0%", "85.0%", "75.0%"],
})

st.divider()

# ---------------------------------------------------------------------
# Section 5 — Monte Carlo uncertainty analysis over the six unconfirmed
# design assumptions (see python/uncertainty.py for the full reasoning)
# ---------------------------------------------------------------------
st.header("Uncertainty Analysis")
st.warning(
    "This reflects uncertainty in **unconfirmed design assumptions** — steam-to-feed "
    "ratio, air equivalence ratio, feed sulfur/chlorine, and the WGS/PSA target "
    "calibrations themselves — **not measurement noise or numerical/model error.** "
    "kinetics.py and psa.py's own math is deterministic and already validated exactly "
    "against their design targets; what's uncertain is whether the *inputs* to that "
    "math are correct, since DOK-ING hasn't confirmed them yet.",
    icon="⚠️",
)

with st.expander("Assumption ranges used (point value ± 15% — our own assumed default, not DOK-ING-sourced)"):
    st.table({
        "Assumption": [cfg["label"] for cfg in uncertainty.ASSUMPTIONS.values()],
        "Point value": [cfg["point"] for cfg in uncertainty.ASSUMPTIONS.values()],
        "±15% range": [
            f"{cfg['point']*0.85:.3g} – {cfg['point']*1.15:.3g}" for cfg in uncertainty.ASSUMPTIONS.values()
        ],
        "Propagated into kinetics/psa?": [
            "Yes" if cfg["wired_in"] else "No — no poisoning/corrosion model exists yet"
            for cfg in uncertainty.ASSUMPTIONS.values()
        ],
    })

n_runs = st.slider("Monte Carlo runs", 200, 2000, 1000, step=100, key="mc_runs")
if st.button("Run Monte Carlo uncertainty analysis"):
    with st.spinner(f"Running {n_runs} samples through kinetics.py and psa.py..."):
        mc_results = uncertainty.run_monte_carlo(
            n_runs=n_runs,
            hts_T_C=T_hts_C, hts_GHSV=ghsv_hts,
            lts_T_C=T_lts_C, lts_GHSV=ghsv_lts,
            psa_p_high=p_high, psa_p_low=p_low, psa_y_co2=y_co2,
        )
    st.session_state["mc_results"] = mc_results

if "mc_results" in st.session_state:
    mc_labels = {
        "hts": "HTS conversion", "lts": "LTS relative conversion",
        "overall": "Overall WGS conversion", "psa_recovery": "PSA recovery",
    }
    mc_targets = {"hts": 0.75, "lts": 0.40, "overall": 0.85, "psa_recovery": 0.75}
    mc_rows = []
    for key, label in mc_labels.items():
        s = uncertainty.summarize(st.session_state["mc_results"][key])
        mc_rows.append({
            "Output": label, "mean": s["mean"] * 100, "p5": s["p5"] * 100,
            "p95": s["p95"] * 100, "target": mc_targets[key] * 100,
        })
    mc_df = pd.DataFrame(mc_rows)

    st.dataframe(
        mc_df.rename(columns={
            "mean": "Mean (%)", "p5": "5th pct (%)", "p95": "95th pct (%)", "target": "Point-value target (%)",
        }).set_index("Output").round(1),
        use_container_width=True,
    )

    base = alt.Chart(mc_df).encode(y=alt.Y("Output:N", sort=None, title=None))
    ci_bars = base.mark_rule(size=4, color="#4C78A8").encode(
        x=alt.X("p5:Q", title="%", scale=alt.Scale(zero=False)), x2="p95:Q"
    )
    mean_points = base.mark_point(size=100, filled=True, color="black").encode(x="mean:Q")
    target_ticks = base.mark_tick(color="red", thickness=2, size=25).encode(x="target:Q")
    st.altair_chart((ci_bars + mean_points + target_ticks).properties(height=220), use_container_width=True)
    st.caption(
        "Blue line = 90% confidence interval (5th–95th percentile) · black dot = Monte Carlo mean · "
        "red tick = current point-value target."
    )

st.divider()

# ---------------------------------------------------------------------
# Section 6 — Central optimizer (v1: single-shot setpoint optimizer over
# the real physics, NOT real-time receding-horizon MPC — see
# python/optimizer.py for the full honest-scoping explanation)
# ---------------------------------------------------------------------
st.header("Optimizer")
st.warning(
    "**v1 — single-shot setpoint optimizer, not real MPC.** True model "
    "predictive control does receding-horizon optimization over time — "
    "repeatedly re-planning as a dynamic system evolves. kinetics.py and "
    "psa.py are steady-state functions (conversion at one fixed operating "
    "point, no time axis), not dynamic simulations, so a real MPC loop "
    "isn't buildable on top of them yet. This searches the real adjustable "
    "setpoints **once**, using the real physics as its internal model — "
    "not a separate approximation of it. A real receding-horizon MPC "
    "controller is a genuine v2, once a dynamic (time-domain) version of "
    "the physics core exists.",
    icon="⚠️",
)

objective = st.selectbox(
    "Objective", ["Maximize overall WGS conversion", "Maximize PSA recovery"], key="optimizer_objective"
)

if st.button("Run optimizer"):
    with st.spinner("Searching setpoints against the real kinetics.py / psa.py model..."):
        if objective == "Maximize overall WGS conversion":
            opt_result = optimizer.maximize_overall_wgs_conversion(
                x0=[T_hts_C, ghsv_hts, T_lts_C, ghsv_lts]
            )
        else:
            opt_result = optimizer.maximize_psa_recovery(y_co2=y_co2)
    st.session_state["optimizer_result"] = {"objective": objective, "result": opt_result}

if "optimizer_result" in st.session_state:
    saved_objective = st.session_state["optimizer_result"]["objective"]
    opt_result = st.session_state["optimizer_result"]["result"]

    if saved_objective == "Maximize overall WGS conversion":
        st.write(
            f"**Recommended setpoints:** HTS {opt_result['T_hts_C']:.1f}°C / {opt_result['ghsv_hts']:.0f} GHSV "
            f"· LTS {opt_result['T_lts_C']:.1f}°C / {opt_result['ghsv_lts']:.0f} GHSV"
        )
        ocol1, ocol2, ocol3 = st.columns(3)
        ocol1.metric("HTS conversion", f"{opt_result['X_hts']*100:.1f}%")
        ocol2.metric("LTS relative conversion", f"{opt_result['X_lts']*100:.1f}%")
        ocol3.metric("Overall WGS conversion", f"{opt_result['overall']*100:.1f}%")
        st.caption(
            f"scipy L-BFGS-B, {opt_result['n_evaluations']} evaluations, converged={opt_result['converged']}. "
            "Verified: recomputing kinetics.py directly at these setpoints reproduces this exact result — "
            "the answer isn't just reported, it's checked. Note: this optimizer has no penalty for extreme "
            "setpoints (catalyst degradation, capital cost, equipment limits aren't modeled), so a boundary "
            "solution like this is a legitimate answer to 'maximize conversion, no other constraints' — not "
            "necessarily an operationally sound recommendation on its own."
        )
        if st.button("Jump sliders to these values", key="jump_wgs"):
            st.session_state["_pending_slider_jump"] = {
                "hts_t": int(min(max(round(opt_result["T_hts_C"]), 300), 400)),
                "hts_ghsv": int(min(max(round(opt_result["ghsv_hts"]), 1000), 4000)),
                "lts_t": int(min(max(round(opt_result["T_lts_C"]), 180), 260)),
                "lts_ghsv": int(min(max(round(opt_result["ghsv_lts"]), 1000), 4000)),
            }
            st.rerun()
    else:
        st.write(
            f"**Recommended setpoints:** Adsorption pressure {opt_result['p_high']:.2f} bar(a) "
            f"· Purge pressure {opt_result['p_low']:.2f} bar(a)"
        )
        st.metric("PSA recovery", f"{opt_result['recovery']*100:.1f}%")
        st.caption(
            f"Grid search, {opt_result['n_evaluations']} evaluations. Verified: recomputing psa.py directly "
            "at these setpoints reproduces this exact result. Feed CO2 fraction held at the current slider "
            "value above."
        )
        if st.button("Jump sliders to these values", key="jump_psa"):
            st.session_state["_pending_slider_jump"] = {
                "p_high": round(min(max(opt_result["p_high"], 4.0), 14.0), 2),
                "p_low": round(min(max(opt_result["p_low"], 0.5), 3.0), 2),
            }
            st.rerun()

st.divider()

# ---------------------------------------------------------------------
# Section 7 — Operator copilot (rule-based v1, no LLM / API key)
# ---------------------------------------------------------------------
st.header("Operator Copilot")
st.caption(
    "Rule-based v1 — answers questions about WGS kinetics, PSA recovery, and the CHP "
    "dispatch GA using the current values above. No LLM call, no API key. Anything "
    "outside those topics gets an honest 'I don't cover that yet' instead of a guess."
)

question = st.text_input(
    "Ask about the current digital twin state",
    placeholder="e.g. why is HTS conversion low? / what happens if I increase PSA pressure? / why did the GA skip the microturbine?",
    key="copilot_question",
)

if question:
    copilot_state = {
        "hts": st.session_state.get("hts"),
        "lts": st.session_state.get("lts"),
        "overall": st.session_state.get("overall"),
        "psa": st.session_state.get("psa"),
        "dispatch": st.session_state.get("dispatch"),
    }
    answer = copilot.answer_question(question, copilot_state)
    st.info(answer if answer is not None else copilot.UNKNOWN_QUESTION_MESSAGE)

st.divider()

# ---------------------------------------------------------------------
# Section 8 — Vendor sourcing agent (v1: manual quote log, no web search)
# ---------------------------------------------------------------------
st.header("Vendor Sourcing")
st.warning(
    "**v1 — manual tracker only.** This does NOT search the web, call any vendor "
    "API, or auto-fill anything. You find a quote yourself (phone, email, a "
    "vendor's website) and log it below against the real equipment item. An "
    "actual research/browsing agent that sources quotes automatically is v2 "
    "and has not been built yet — this version makes no claim otherwise.",
    icon="⚠️",
)

registry = equipment_registry.load_registry()
quotes = vendor_log.load_quotes()
counts = vendor_log.status_counts(registry, quotes)

st.caption(
    f"Registry: {counts['total']} items from the real MSW equipment datasheet workbook "
    f"(`data/MSW_Equipment_Datasheets_Interactive.xlsx`) — not fabricated placeholder data."
)
cols = st.columns(4)
cols[0].metric("Total items", counts["total"])
cols[1].metric("Need sourcing", counts["needs_sourcing"])
cols[2].metric("Quoted", counts["quoted"])
cols[3].metric("Still open", counts["open"])
if counts["not_applicable"]:
    st.caption(f"{counts['not_applicable']} item(s) marked not applicable in the source workbook (no vendor needed).")

st.subheader("Log a found quote")
quoted_ids = {q["equipment_id"] for q in quotes}
item_labels = {
    item["id"]: f"{item['id']} — {item['name']}"
    + (" ✅ quoted" if item["id"] in quoted_ids else "")
    for item in registry
    if equipment_registry.needs_vendor_sourcing(item)
}
with st.form("log_quote_form", clear_on_submit=True):
    fcol1, fcol2 = st.columns(2)
    with fcol1:
        selected_id = st.selectbox(
            "Equipment item", options=list(item_labels.keys()), format_func=lambda k: item_labels[k]
        )
        vendor_name = st.text_input("Vendor name")
    with fcol2:
        price = st.number_input("Price (EUR)", min_value=0.0, step=100.0)
        quote_date = st.date_input("Quote date")
    notes = st.text_area("Notes", placeholder="e.g. lead time, contact, quote reference #")
    submitted = st.form_submit_button("Log quote")

if submitted:
    if not vendor_name.strip():
        st.error("Vendor name is required.")
    else:
        vendor_log.log_quote(selected_id, vendor_name, price, quote_date, notes)
        st.success(f"Logged {vendor_name} for {selected_id} at €{price:,.0f}.")
        st.rerun()

st.subheader("Registry status")
selected_category = st.selectbox(
    "Filter by category", options=["All"] + sorted(set(item["category"] for item in registry))
)
for item in registry:
    if selected_category != "All" and item["category"] != selected_category:
        continue
    item_quotes = vendor_log.quotes_for(item["id"], quotes)
    if not equipment_registry.needs_vendor_sourcing(item):
        status = "N/A (not applicable — see datasheet)"
    elif item_quotes:
        latest = item_quotes[0]
        status = f"✅ Quoted — {latest['vendor']}, €{latest['price']:,.0f} ({latest['date']})"
    else:
        status = "⏳ Open — needs a real vendor quote"

    with st.expander(f"{item['id']} — {item['name']}  ·  {status}"):
        st.caption(f"Category: {item['category']}  ·  Known spec fields: {item['parameters_filled']}")
        st.table({
            "Parameter": [p["parameter"] for p in item["parameters"]],
            "Value": [f"{p['value']} {p['unit'] or ''}".strip() for p in item["parameters"]],
        })
        if item_quotes:
            st.write("**Logged quotes:**")
            for q in item_quotes:
                st.write(f"- {q['vendor']} — €{q['price']:,.0f} on {q['date']}" + (f" — {q['notes']}" if q["notes"] else ""))

st.divider()

st.caption("HYGAS-AI — SMITH2 R&D Hydrogen Agency — NACHIP Pilot Programme")
