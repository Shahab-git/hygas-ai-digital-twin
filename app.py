"""
HYGAS-AI — Live Digital Twin Status Dashboard

Deploy at share.streamlit.io by pointing it at this repo. Uses the
verified Python physics modules in /python — the same models that were
cross-checked against the MATLAB/Simulink blocks during development.
"""
import altair as alt
import pandas as pd
import streamlit as st
from python import (
    kinetics, psa, chp, dispatch_ga, copilot, equipment_registry, vendor_log,
    uncertainty, optimizer, predictive_maintenance, compliance, regulatory_drafting,
    root_cause, multi_agent_negotiation, confirmation_loop, gasifier_mass_balance, circularity,
    multi_module_orchestration,
)

st.set_page_config(page_title="HYGAS-AI Digital Twin", layout="wide")

# Apply any pending "jump sliders to these values" request from the
# Optimizer section (Section 6) *before* the slider widgets below are
# instantiated — Streamlit forbids writing to a widget's session_state
# key after that widget has already rendered in the same script run, so
# the actual jump has to happen up here, one rerun after the button click.
if "_pending_slider_jump" in st.session_state:
    for _k, _v in st.session_state.pop("_pending_slider_jump").items():
        st.session_state[_k] = _v

# Replay any already-confirmed assumptions from Supabase into
# uncertainty.py's live ASSUMPTIONS *before* the Uncertainty Analysis and
# Compliance Documentation sections run below — set_confirmed()'s effect
# lives only in this process's memory, so a fresh process (redeploy,
# restart) needs this replay every time. Degrades gracefully if the
# assumption_confirmations table doesn't exist yet (see
# data/confirmation_schema.sql) rather than crashing the whole app.
try:
    _confirmation_status = confirmation_loop.sync_confirmed_from_db()
except Exception:
    _confirmation_status = None

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
# Section 7 — Predictive maintenance (v1: catalyst activity via inverse
# kinetics; thresholds are our own assumed defaults — see
# python/predictive_maintenance.py for the full reasoning)
# ---------------------------------------------------------------------
st.header("Predictive Maintenance")
st.warning(
    "**v1 — inverse-kinetics activity monitoring; thresholds are our own "
    "assumed defaults.** Enter a live-sensor conversion reading and this "
    "back-calculates the catalyst activity factor (effective k0 ÷ healthy "
    "calibrated k0) that would produce it, using kinetics.py's own forward "
    "model in reverse — not a separate approximation of it. The 0.95 / "
    "0.85 status thresholds are reasonable defaults we picked, **not** "
    "sourced from any real catalyst degradation data — there isn't any in "
    "this project yet.",
    icon="⚠️",
)

pm_stage = st.selectbox("Stage", ["HTS", "LTS"], key="pm_stage")

if pm_stage == "HTS":
    pm_state = st.session_state.get("hts", {"X": 0.75, "T_C": 350, "GHSV": 2000})
else:
    pm_state = st.session_state.get("lts", {"X": 0.40, "T_C": 220, "GHSV": 2000, "y_CO_in": 0.07})

pm_expected_pct = pm_state["X"] * 100
st.caption(
    f"Current slider-predicted {pm_stage} conversion at T={pm_state['T_C']:.0f}°C, "
    f"GHSV={pm_state['GHSV']:.0f}: {pm_expected_pct:.1f}%"
)

pm_observed_pct = st.number_input(
    f"Observed {pm_stage} conversion from a live sensor (%)",
    min_value=0.0, max_value=100.0, value=round(pm_expected_pct, 1), step=0.5, key="pm_observed",
)

if st.button("Check catalyst activity"):
    if pm_stage == "HTS":
        pm_result = predictive_maintenance.back_calculate_activity_hts(
            observed_X=pm_observed_pct / 100, T_C=pm_state["T_C"], GHSV=pm_state["GHSV"],
        )
    else:
        pm_result = predictive_maintenance.back_calculate_activity_lts(
            observed_X=pm_observed_pct / 100, T_C=pm_state["T_C"], GHSV=pm_state["GHSV"],
            y_CO_in=pm_state["y_CO_in"],
        )
    st.session_state["pm_result"] = pm_result
    st.session_state["pm_context"] = {
        "stage": pm_stage, "T_C": pm_state["T_C"], "GHSV": pm_state["GHSV"],
        "y_CO_in": pm_state.get("y_CO_in"),
    }
    st.session_state.pop("root_cause_result", None)  # stale from a previous reading

if "pm_result" in st.session_state:
    pm_result = st.session_state["pm_result"]
    if "error" in pm_result:
        st.error(pm_result["error"])
    else:
        pm_status_icon = {"healthy": "🟢", "watch": "🟡", "flag for maintenance": "🔴"}[pm_result["status"]]
        pcol1, pcol2, pcol3 = st.columns(3)
        pcol1.metric("Activity factor", f"{pm_result['activity_factor']:.3f}")
        pcol2.metric("Status", f"{pm_status_icon} {pm_result['status'].title()}")
        pcol3.metric(
            "Expected → observed",
            f"{pm_result['expected_X']*100:.1f}% → {pm_result['observed_X']*100:.1f}%",
        )
        st.caption(
            "Activity factor = effective k0 ÷ healthy calibrated k0, back-calculated by root-finding "
            "kinetics.py's own forward model at the current T/GHSV. Thresholds: >0.95 healthy, "
            "0.85–0.95 watch, <0.85 flag for maintenance."
        )

        if pm_result["status"] in ("watch", "flag for maintenance"):
            st.caption(
                "**Root-cause diagnosis v1 — rule-based reasoning over existing model outputs, not a new "
                "inference engine.** Compares this activity factor against the range that unconfirmed "
                "design-basis assumptions alone (uncertainty.py's ±15% bands) could produce with a "
                "perfectly healthy catalyst, and checks whether the reading is even physically achievable "
                "at this T/GHSV (kinetics.py's own bounds)."
            )
            if st.button("Diagnose"):
                ctx = st.session_state["pm_context"]
                st.session_state["root_cause_result"] = root_cause.diagnose(
                    ctx["stage"], pm_result["observed_X"], ctx["T_C"], ctx["GHSV"], y_CO_in=ctx["y_CO_in"],
                )

        if "root_cause_result" in st.session_state:
            rc_result = st.session_state["root_cause_result"]
            rc_band = rc_result["assumption_band"]
            st.write(
                f"**Assumption-only band:** [{rc_band['lo']:.3f}, {rc_band['hi']:.3f}] — the activity "
                f"factor range {' and '.join(rc_band['assumptions_used'])} uncertainty alone could "
                f"produce at these conditions with a perfectly healthy catalyst."
            )
            rc_rank_icon = {1: "🥇", 2: "🥈", 3: "🥉"}
            for e in rc_result["explanations"]:
                icon = rc_rank_icon.get(e["rank"], "⚠️")
                plausible_str = "plausible" if e["plausible"] else "not the primary explanation here"
                st.markdown(f"{icon} **{e['label']}** _({plausible_str})_")
                st.write(e["reasoning"])

st.divider()

# ---------------------------------------------------------------------
# Section 8 — Operator copilot (rule-based v1, no LLM / API key)
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
# Section 9 — Vendor sourcing agent (v1: manual quote log, no web search)
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

# ---------------------------------------------------------------------
# Section 10 — Compliance documentation (v1: organizes real plant data
# into audit-checklist shape; NOT actual RFNBO certification — see
# python/compliance.py for the full limitation statement)
# ---------------------------------------------------------------------
st.header("Compliance Documentation")
st.warning(
    "**This is NOT RFNBO certification.** Real RFNBO (Renewable Fuel of Non-Biological Origin) "
    "certification requires an accredited third-party auditor assessing the plant against EU "
    "Delegated Regulation (EU) 2023/1184 and the related methodology regulation (EU) 2023/1185 — "
    "additionality, temporal/geographic correlation for renewable electricity, greenhouse-gas "
    "savings thresholds, mass-balance chain-of-custody, and more. This repo cannot implement that "
    "process or make that legal determination, and makes no such claim. What this **does** do: "
    "organize the plant's actual data into the checklist shape a real audit would start from, and "
    "clearly separate what's genuinely validated from what's still an assumption or undocumented.",
    icon="⚠️",
)

compliance_checklist = compliance.build_checklist()
compliance_counts = compliance.summarize_checklist(compliance_checklist)

ccol1, ccol2, ccol3, ccol4 = st.columns(4)
ccol1.metric(f"🟢 {compliance.EVIDENCED}", compliance_counts[compliance.EVIDENCED])
ccol2.metric(f"🔵 {compliance.CONFIRMED}", compliance_counts[compliance.CONFIRMED])
ccol3.metric(f"🟡 {compliance.ASSUMPTION_PENDING}", compliance_counts[compliance.ASSUMPTION_PENDING])
ccol4.metric(f"🔴 {compliance.NOT_DOCUMENTED}", compliance_counts[compliance.NOT_DOCUMENTED])

_compliance_icons = {
    compliance.EVIDENCED: "🟢",
    compliance.CONFIRMED: "🔵",
    compliance.ASSUMPTION_PENDING: "🟡",
    compliance.NOT_DOCUMENTED: "🔴",
}

for _category in ["Mass/Energy Balance Traceability", "Design-Basis Assumptions", "Feedstock Traceability"]:
    st.subheader(_category)
    for _item in [i for i in compliance_checklist if i["category"] == _category]:
        _icon = _compliance_icons[_item["status"]]
        _title = f"{_icon} {_item['item']} — {_item['status']}"
        if _item["value"]:
            _title += f"  ({_item['value']})"
        with st.expander(_title):
            st.caption(f"**Source:** {_item['source']}")
            st.write(_item["notes"])

st.subheader("Draft Compliance Summary")
st.caption(
    "**This is drafting, not legal writing.** The generated document needs review by "
    "someone qualified — compliance/legal counsel, or an accredited RFNBO auditor — "
    "before it goes anywhere near a real submission, same spirit as the checklist "
    "above. Every fact in it is pulled from the checklist itself at generation time, "
    "not written separately."
)

if st.button("Generate draft compliance summary"):
    st.session_state["compliance_draft"] = regulatory_drafting.generate_draft_summary(compliance_checklist)

if "compliance_draft" in st.session_state:
    st.download_button(
        "Download draft (.md)",
        data=st.session_state["compliance_draft"],
        file_name="hygas_ai_draft_compliance_summary.md",
        mime="text/markdown",
    )
    with st.expander("Preview draft", expanded=True):
        st.markdown(st.session_state["compliance_draft"])

st.divider()

# ---------------------------------------------------------------------
# Section 11 — Multi-module negotiation (v1: hypothetical plant variants
# negotiating over a shared grid export constraint — see
# python/multi_agent_negotiation.py for the full honest-scoping statement)
# ---------------------------------------------------------------------
st.header("Multi-Module Negotiation")
st.warning(
    "**These are simulated hypothetical plant variants, not live data from real additional "
    "facilities.** This repo represents exactly one real plant. 'Plant B' and 'Plant C' below are "
    "illustrative ±20% variants of this plant's own dispatch parameters — a stand-in for what a "
    "real multi-plant fleet might look like, built on the real `dispatch_ga.py` optimization, not "
    "invented numbers.",
    icon="⚠️",
)
st.caption(
    "**Mechanism: merit-order allocation, not full iterative negotiation** — chosen because it's "
    "simpler to verify exactly (one sort, one greedy fill, no convergence loop) and it's how real "
    "grid operators already allocate scarce export capacity: the most fuel-efficient generation is "
    "dispatched first. Each hypothetical plant runs its own dispatch_ga optimization to get its "
    "'ask'; plants are then served in efficiency order until the shared capacity runs out."
)

shared_capacity_kw = st.number_input(
    "Shared grid export capacity (kW)", min_value=10.0, max_value=200.0, value=70.0, step=5.0,
    key="negotiation_capacity",
)

if st.button("Run negotiation"):
    plant_variants = [
        {"name": "Plant A (this plant, current budgets)",
         "syngas_budget_kw": float(syngas_budget), "h2_budget_kw": float(h2_budget)},
        {"name": "Plant B (+20% feed rate, illustrative)",
         "syngas_budget_kw": float(syngas_budget) * 1.2, "h2_budget_kw": float(h2_budget) * 1.2},
        {"name": "Plant C (−20% feed rate, illustrative)",
         "syngas_budget_kw": float(syngas_budget) * 0.8, "h2_budget_kw": float(h2_budget) * 0.8},
    ]
    with st.spinner("Each plant running its own dispatch_ga optimization, then negotiating..."):
        st.session_state["negotiation_result"] = multi_agent_negotiation.negotiate(
            shared_capacity_kw, variants=plant_variants,
        )

if "negotiation_result" in st.session_state:
    neg = st.session_state["negotiation_result"]
    ncol1, ncol2, ncol3 = st.columns(3)
    ncol1.metric("Shared capacity", f"{neg['shared_capacity_kw']:.1f} kW")
    ncol2.metric("Total asked", f"{neg['total_asked_kw']:.1f} kW")
    ncol3.metric("Total allocated", f"{neg['total_allocated_kw']:.1f} kW")
    st.caption(
        f"Sum of allocations ({neg['total_allocated_kw']:.2f} kW) respects the shared constraint "
        f"({neg['shared_capacity_kw']:.2f} kW) by construction — a greedy fill against a hard cap, "
        f"not clipped after the fact. Merit order (most efficient first): "
        + " → ".join(neg["merit_order"])
    )

    for p in neg["plants"]:
        served_icon = "✅" if p["fully_served"] else "⚠️"
        with st.expander(
            f"{served_icon} {p['name']} — merit rank #{p['merit_rank']}, "
            f"{p['allocation_kw']:.1f} / {p['ask_kw']:.1f} kW allocated"
        ):
            st.write(
                f"**Fuel budgets:** syngas {p['syngas_budget_kw']:.1f} kW, H2 {p['h2_budget_kw']:.1f} kW"
            )
            st.write(f"**Dispatch efficiency:** {p['efficiency']*100:.2f}% (electrical kW out ÷ fuel kW in)")
            st.write(
                f"**Ask:** {p['ask_kw']:.2f} kW  →  **Allocated:** {p['allocation_kw']:.2f} kW "
                f"({'fully served' if p['fully_served'] else 'partially served — squeezed by higher-efficiency plants ranked above it'})"
            )
            st.table({
                "Unit": list(p["dispatch"].keys()),
                "Load factor": [f"{v*100:.1f}%" for v in p["dispatch"].values()],
            })

st.divider()

# ---------------------------------------------------------------------
# Section 12 — Confirmation-loop agent (v1: drafts confirmation-request
# content and tracks status; does NOT send real correspondence — see
# python/confirmation_loop.py for the full scope statement)
# ---------------------------------------------------------------------
st.header("Confirmation Tracker")
st.warning(
    "**Does NOT send real emails or messages to DOK-ING.** No real correspondence capability, "
    "and no authority to represent you externally — same drafting-not-correspondence spirit as "
    "the Draft Compliance Summary above. This drafts confirmation-request content and tracks "
    "status here; actually sending it and following up is on you.",
    icon="⚠️",
)

if _confirmation_status is None:
    st.error(
        "The confirmation-tracking table isn't set up yet — run `data/confirmation_schema.sql` "
        "in the Supabase SQL Editor (same project as the vendor quote log) to enable this section."
    )
else:
    if st.button("Generate all 6 confirmation requests (.md)"):
        st.session_state["all_requests_draft"] = confirmation_loop.generate_all_requests_draft()
    if "all_requests_draft" in st.session_state:
        st.download_button(
            "Download all requests (.md)", data=st.session_state["all_requests_draft"],
            file_name="hygas_ai_confirmation_requests.md", mime="text/markdown",
        )

    _cl_status_icon = {"not_yet_asked": "⚪", "awaiting_response": "🟡", "confirmed": "🟢"}

    for _key, _cfg in uncertainty.ASSUMPTIONS.items():
        _row = _confirmation_status[_key]
        _lo, _hi = uncertainty.bounds(_key)
        _icon = _cl_status_icon[_row["status"]]
        with st.expander(f"{_icon} {_cfg['label']} — {_row['status'].replace('_', ' ').title()}"):
            st.caption(
                f"Current range used by the Monte Carlo: [{_lo:.3g}, {_hi:.3g}]"
                + (" — **CONFIRMED**" if uncertainty.is_confirmed(_key) else " (assumed, ±15% default)")
            )
            if _row["confirmed_value"] is not None:
                st.write(
                    f"Confirmed value: **{_row['confirmed_value']:g}**"
                    + (f"  ·  notes: {_row['notes']}" if _row["notes"] else "")
                )

            if st.button("Generate request draft", key=f"gen_req_{_key}"):
                st.session_state[f"req_draft_{_key}"] = confirmation_loop.generate_request_draft(_key)
            if f"req_draft_{_key}" in st.session_state:
                st.markdown(st.session_state[f"req_draft_{_key}"])
                if st.button("Mark as asked", key=f"mark_asked_{_key}"):
                    confirmation_loop.mark_asked(_key)
                    st.rerun()

            st.write("**Record a confirmed value:**")
            with st.form(f"confirm_form_{_key}", clear_on_submit=False):
                _fcol1, _fcol2, _fcol3 = st.columns(3)
                _c_val = _fcol1.number_input("Confirmed value", value=float(_cfg["point"]), key=f"cval_{_key}")
                _c_lo = _fcol2.number_input(
                    "Confirmed range low", value=float(_cfg["point"]) * 0.98, key=f"clo_{_key}"
                )
                _c_hi = _fcol3.number_input(
                    "Confirmed range high", value=float(_cfg["point"]) * 1.02, key=f"chi_{_key}"
                )
                _c_notes = st.text_input("Notes", key=f"cnotes_{_key}")
                _submitted = st.form_submit_button("Record confirmation")
            if _submitted:
                if _c_lo >= _c_hi:
                    st.error("Confirmed range low must be less than confirmed range high.")
                else:
                    confirmation_loop.record_confirmation(_key, _c_val, _c_lo, _c_hi, notes=_c_notes)
                    st.success(
                        f"Recorded: {_cfg['label']} confirmed to [{_c_lo:.3g}, {_c_hi:.3g}]. "
                        "The Uncertainty Analysis and Compliance Documentation sections above now "
                        "use this range — re-run the Monte Carlo to see the narrower CI."
                    )
                    st.rerun()

st.divider()

# ---------------------------------------------------------------------
# Section 13 — Circularity scoring (v1: ash/carbon-black byproduct mass
# balance + assumption-based revenue potential — see
# python/gasifier_mass_balance.py and python/circularity.py)
# ---------------------------------------------------------------------
st.header("Circularity Scoring")
st.caption(
    "Byproduct mass flows use the real design-basis mass fractions embedded in this repo's own "
    "equipment datasheets (GA-005: \"10% ash content, dry basis\"; GA-008's stated capacity implies "
    "~5% carbon black) — a ported linear relationship, not a new model. The **revenue-potential "
    "figures use our own assumed placeholder prices, not real market pricing** — there's no real "
    "market data in this project yet. The diversion fraction needs no price assumption at all; "
    "it's a real mass-balance ratio."
)

circ_feed_kg_h = st.number_input(
    "Dry feed rate (kg/h)", min_value=1.0, max_value=200.0,
    value=gasifier_mass_balance.DEFAULT_DRY_FEED_KG_H, step=0.5, key="circ_feed",
)
circ = circularity.circularity_summary(circ_feed_kg_h)

ccol1, ccol2, ccol3 = st.columns(3)
ccol1.metric("Ash output", f"{circ['ash_kg_h']:.2f} kg/h", help="10% of dry feed — GA-005's own design figure")
ccol2.metric(
    "Carbon black output", f"{circ['carbon_black_kg_h']:.2f} kg/h",
    help="~5% of dry feed — consistent with GA-008's stated design capacity",
)
ccol3.metric(
    "Diversion from landfill", f"{circ['diversion_fraction']*100:.1f}%",
    help="Total byproduct mass ÷ dry feed mass — a real ratio, no price assumption",
)

st.caption(
    f"**Revenue potential (assumption-based):** ash €{circ['ash_revenue_eur_h']:.3f}/h "
    f"(@ €{circularity.ASH_PRICE_EUR_PER_KG:.2f}/kg placeholder) + carbon black "
    f"€{circ['carbon_black_revenue_eur_h']:.3f}/h (@ €{circularity.CARBON_BLACK_PRICE_EUR_PER_KG:.2f}/kg "
    f"placeholder) = **€{circ['total_revenue_eur_h']:.3f}/h** "
    f"(€{circ['total_revenue_eur_h']*8760:,.0f}/yr at 100% uptime, illustrative only — neither price "
    f"is sourced from any real market or offtake data)."
)

st.divider()

# ---------------------------------------------------------------------
# Section 14 — Multi-module orchestration (v1: coordinates cooperating
# hypothetical WGS-train modules of the SAME plant toward one shared
# output target — distinct from Section 11's Multi-Module Negotiation,
# which divides one scarce resource among COMPETING hypothetical plants.
# See python/multi_module_orchestration.py for the full distinction.)
# ---------------------------------------------------------------------
st.header("Multi-Module Orchestration")
st.warning(
    "**Simulated hypothetical plant modules, not live data from real additional hardware.** This "
    "repo represents exactly one real WGS train. The 3 modules below are illustrative variants of "
    "kinetics.py's own physics at different operating temperatures — not real separate equipment. "
    "**Distinct from Multi-Module Negotiation above:** that section divides one shared *scarce* "
    "resource among *competing* hypothetical plants; this section coordinates *cooperating* "
    "modules of the *same* plant to jointly hit one shared output target at minimum cost.",
    icon="⚠️",
)

mo_target = st.number_input(
    "Target H2 output (relative GHSV-equivalent units — see caption below)",
    min_value=100.0, max_value=10000.0, value=2500.0, step=100.0, key="mo_target",
)
st.caption(
    "Output is modeled as throughput × overall WGS conversion, in the same GHSV units kinetics.py "
    "already uses — a relative/illustrative basis, not a real kg/h mass balance (unlike "
    "circularity.py's feed rate, which IS a real, sourced number for the one actual train this "
    "repo models)."
)

mo_offline = st.multiselect(
    "Take module(s) offline (simulated scheduled maintenance)",
    options=[m["name"] for m in multi_module_orchestration.DEFAULT_MODULES],
    key="mo_offline",
)

if st.button("Run orchestration"):
    st.session_state["mo_result"] = multi_module_orchestration.orchestrate(
        mo_target, offline_module_names=mo_offline,
    )

if "mo_result" in st.session_state:
    _mo = st.session_state["mo_result"]
    if not _mo["feasible"]:
        st.error(_mo["reason"])
    else:
        st.success(
            f"Target met exactly: {_mo['total_output']:.1f} output at "
            f"{_mo['total_throughput']:.1f} total throughput (minimized)."
        )

    _mo_status_icon = {"healthy": "🟢", "watch": "🟡", "flag for maintenance": "🔴"}
    for _m in _mo["modules"]:
        _icon = _mo_status_icon[_m["status"]]
        if _m["forced_offline"]:
            _avail_str = "OFFLINE (scheduled maintenance)"
        elif not _m["available"]:
            _avail_str = "OFFLINE (flagged for maintenance — activity factor below predictive_maintenance's threshold)"
        else:
            _avail_str = "available"
        with st.expander(f"{_icon} {_m['name']} — {_avail_str}"):
            st.write(
                f"HTS temperature: {_m['T_hts_C']:.0f}°C  ·  Activity factor: {_m['activity_factor']:.2f}  ·  "
                f"Status: {_m['status']}"
            )
            if _m["available"]:
                st.write(f"**Load (GHSV):** {_m['ghsv']:.0f} / {_m['ghsv_max']:.0f} max")
                st.write(
                    f"**Output:** {_m['output']:.1f}  "
                    f"({_m.get('share_of_target', 0)*100:.1f}% of target — the hotter/more efficient "
                    f"a module is at this load, the larger its share)"
                )
            else:
                st.write("Not contributing to the allocation — offline.")

st.divider()

st.caption("HYGAS-AI — SMITH2 R&D Hydrogen Agency — NACHIP Pilot Programme")
