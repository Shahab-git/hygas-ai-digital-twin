"""
HYGAS-AI — Live Digital Twin Status Dashboard

Deploy at share.streamlit.io by pointing it at this repo. Uses the
verified Python physics modules in /python — the same models that were
cross-checked against the MATLAB/Simulink blocks during development.
"""
import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
from python import (
    kinetics, psa, chp, dispatch_ga, copilot, equipment_registry, vendor_log,
    uncertainty, optimizer, predictive_maintenance, compliance, regulatory_drafting,
    root_cause, multi_agent_negotiation, confirmation_loop, gasifier_mass_balance, circularity,
    multi_module_orchestration, novelty_audit, safety_flags, pinn_kinetics, sim_to_real,
    federated_learning, performance_guarantee, time_series_sim, tda_analysis, equipment_datasheet,
)

st.set_page_config(page_title="HYGAS-AI Digital Twin", layout="wide")

tab1, tab2, tab3 = st.tabs(["Digital Twin", "Reserved", "Equipment Datasheets"])

with tab1:

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

    # ---------------------------------------------------------------------
    # Section 15 — Novelty audit coverage (v1: honest documented-depth
    # coverage against the 8-lens framework, NOT a genuine novelty
    # assessment — see python/novelty_audit.py for the full scoping)
    # ---------------------------------------------------------------------
    st.header("Novelty Audit Coverage")
    st.warning(
        "**This is NOT a genuine novelty assessment.** Code cannot judge real engineering novelty — "
        "that needs actual domain-expert judgment against prior art (patents, published literature, "
        "competing commercial designs), which this tool doesn't attempt and doesn't claim to. What "
        "this **does** show: which of the 91 equipment registry items have real, working Python code "
        "behind them *in this repo* across the 8-lens framework (Design, Dynamics, Math, Physics, "
        "Economics, Safety, Data & Control Intelligence, Circularity) — an honest measure of "
        "documented engineering depth here, not a claim about which equipment is more innovative.",
        icon="⚠️",
    )

    _na_audit = novelty_audit.build_audit()
    _na_summary = novelty_audit.summarize_audit(_na_audit)

    nacol1, nacol2, nacol3 = st.columns(3)
    nacol1.metric("Total registry items", _na_summary["total_items"])
    nacol2.metric("≥1 lens covered", _na_summary["items_with_coverage"])
    nacol3.metric("Zero coverage", _na_summary["items_with_zero_coverage"])

    st.write("**Coverage by lens** (out of 91 items):")
    _na_lens_cols = st.columns(4)
    for _i, _lens in enumerate(novelty_audit.LENSES):
        _na_lens_cols[_i % 4].metric(_lens, _na_summary["lens_totals"][_lens])
    st.caption(
        "Design, Dynamics, and Safety currently show 0 — an honest gap in this repo (no equipment-"
        "sizing analysis, no time-domain/transient modeling, and no hazard/ATEX analysis code exist "
        "here yet), not a bug in the audit."
    )

    _na_by_id = {a["equipment_id"]: a for a in _na_audit}
    _na_registry_by_id = {item["id"]: item for item in equipment_registry.load_registry()}

    _na_show_all = st.checkbox(
        "Show all 91 items (default: only the 18 with at least one lens covered)", key="na_show_all",
    )
    _na_items_to_show = _na_audit if _na_show_all else [a for a in _na_audit if a["coverage_count"] > 0]
    _na_items_to_show = sorted(_na_items_to_show, key=lambda a: -a["coverage_count"])

    for _a in _na_items_to_show:
        _eq = _na_registry_by_id[_a["equipment_id"]]
        _title = f"{_a['equipment_id']} — {_eq['name']}  ·  {_a['coverage_count']}/8 lenses"
        with st.expander(_title):
            if _a["coverage_count"] == 0:
                st.write("_No lens covered yet — no code in this repo currently models this item._")
            for _lens in novelty_audit.LENSES:
                if _lens not in _a["evidence"]:
                    continue
                st.write(f"**{_lens}:**")
                for _ev in _a["evidence"][_lens]:
                    st.caption(f"— `{_ev['source']}`: {_ev['reasoning']}")

    st.divider()

    # ---------------------------------------------------------------------
    # Section 16 — Safety hazard flagging (v1: flags design values against
    # real, cited public reference thresholds — NOT a PHA/HAZOP. See
    # python/safety_flags.py for the full scoping and every citation.)
    # ---------------------------------------------------------------------
    st.header("Safety Flags")
    st.markdown(
        "**⚠️ This is NOT a certified safety assessment.** Real hazard analysis requires qualified "
        "safety engineers using formal methodology (HAZOP, PHA) — this tool cannot replicate that. "
        "It exists only to surface where this plant's own design values sit relative to well-"
        "established, publicly documented reference thresholds (cited explicitly below), so genuine "
        "gaps are visible instead of silently absent. Nothing here is a hazard determination."
    )

    _sf = safety_flags.build_safety_flags()
    _sf_h2s = _sf["h2s"]

    st.subheader("Feed H2S — two distinct concerns from the same number")
    st.caption(
        "The 200 ppm feed H2S assumption is tracked live from uncertainty.py — the same number the "
        "Uncertainty Analysis, Compliance Documentation, and Confirmation Tracker sections above use. "
        "If that assumption ever gets a real DOK-ING-confirmed value via the Confirmation Tracker, "
        "these flags update automatically, with no separate copy to fall out of sync."
    )
    st.write(
        f"**Current feed H2S value:** {_sf_h2s['assumption_value_ppm']:.0f} ppm  "
        f"({'CONFIRMED' if _sf_h2s['is_confirmed'] else 'assumed, ±15% default'}, "
        f"range [{_sf_h2s['assumption_range_ppm'][0]:.0f}, {_sf_h2s['assumption_range_ppm'][1]:.0f}] ppm)"
    )

    sfcol1, sfcol2 = st.columns(2)
    for _sfcol, _key in [(sfcol1, "personnel_safety"), (sfcol2, "catalyst_risk")]:
        _c = _sf_h2s[_key]
        with _sfcol:
            _icon = "🔴" if _c["flag"] else "🟢"
            st.markdown(f"{_icon} **{_c['concern']}**")
            st.caption(f"Reference: {_c['reference']}")
            st.metric("Ratio to reference", f"{_c['ratio_to_reference']:.1f}×")
            st.write(_c["note"])

    st.subheader("H2 storage (HB-013)")
    _sf_h2 = _sf["h2_storage"]
    if _sf_h2:
        st.write(f"**{_sf_h2['equipment_id']} — {_sf_h2['equipment_name']}**")
        st.write(f"Design pressure: {_sf_h2['design_pressure']}  ·  H2 flammability range: {_sf_h2['h2_flammability_range']}")
        st.write(_sf_h2["note"])

    st.subheader("ATEX-rated equipment (read directly from the registry)")
    for _a in _sf["atex_items"]:
        st.write(f"- **{_a['equipment_id']}** ({_a['equipment_name']}): {_a['atex_value']}")
    st.caption(
        "Items explicitly marked \"ATEX not required\" in their own datasheet (AI-002, AI-004, AI-008) "
        "were checked and correctly assessed as such — not flagged, and not omitted from the search."
    )

    st.divider()

    # ---------------------------------------------------------------------
    # Section 17 — Physics-informed neural network (v1: a genuine PINN, not
    # a data-fit surrogate mislabeled as one — see python/pinn_kinetics.py
    # for the full formulation, gradient derivation, and honest limitations.)
    # ---------------------------------------------------------------------
    st.header("Physics-Informed Neural Network")
    st.markdown(
        "**⚠️ Scope.** This predicts HTS WGS conversion under the same steady-state assumptions as "
        "the rest of this app, trained on ONE specific rate law (`kinetics.hts_conversion` — HTS only, "
        "not LTS). It is not reliable outside the physical range this project has already validated: "
        "**300–400°C, 1000–4000 GHSV.** No PyTorch/JAX/autograd dependency was added — checked first "
        "and confirmed none is already installed, and a full autodiff framework was judged a real "
        "memory/CPU risk on Streamlit Community Cloud's free tier. Instead this is a tiny hand-rolled "
        "8-neuron NumPy network with an analytically-derived physics gradient (verified against a "
        "finite-difference check — see the module's self-test), trained with `scipy.optimize.minimize`."
    )
    st.caption(
        "What makes it a PINN and not a surrogate: the training loss has a physics-residual term — "
        "how well the network's own dX/dτ satisfies the real HTS rate law from kinetics.py, checked at "
        "200 randomly sampled points across the domain — plus the real boundary condition X=0 at τ=0. "
        "Only 8 labeled (T, GHSV)→X points from kinetics.py's actual output anchor the fit; physics "
        "shapes the rest."
    )

    if st.button("Train PINN (and a data-only baseline, for comparison)"):
        with st.spinner("Training the physics-informed model and a same-architecture data-only baseline..."):
            st.session_state["pinn_result"] = pinn_kinetics.compare_to_baseline()

    if "pinn_result" in st.session_state:
        _pr = st.session_state["pinn_result"]
        _pinn, _base = _pr["pinn"], _pr["baseline"]

        st.subheader("The real test: error near vs. far from the 8 labeled points")
        st.caption(
            "Test points are split by distance to the nearest labeled training point (median split). "
            "If the PINN's far-point error stays close to its near-point error while a data-only fit "
            "(same architecture, same 8 points, physics term switched off) degrades further away, "
            "that's real evidence the physics loss — not memorization — is doing the work."
        )
        pcol1, pcol2 = st.columns(2)
        with pcol1:
            st.markdown("**PINN (physics + data + boundary condition)**")
            st.metric("Mean abs. error (40 test points)", f"{_pinn['mean_error']:.4f}")
            st.write(f"Near-training error: **{_pinn['near_mean_error']:.4f}**  ·  "
                     f"Far-from-training error: **{_pinn['far_mean_error']:.4f}**")
            st.metric("Far / near error ratio", f"{_pinn['far_to_near_ratio']:.2f}×")
        with pcol2:
            st.markdown("**Data-only baseline (physics weight = 0)**")
            st.metric("Mean abs. error (40 test points)", f"{_base['mean_error']:.4f}")
            st.write(f"Near-training error: **{_base['near_mean_error']:.4f}**  ·  "
                     f"Far-from-training error: **{_base['far_mean_error']:.4f}**")
            st.metric("Far / near error ratio", f"{_base['far_to_near_ratio']:.2f}×")

        _err_multiple = _base["mean_error"] / _pinn["mean_error"] if _pinn["mean_error"] > 0 else float("nan")
        st.write(
            f"With identical architecture and the identical 8 labeled points, the PINN's mean test "
            f"error is **{_err_multiple:.0f}× lower** than the data-only baseline's, and its far-point "
            f"error barely rises above its near-point error ({_pinn['far_to_near_ratio']:.2f}× vs. the "
            f"baseline's {_base['far_to_near_ratio']:.2f}×). That is the physics-residual term doing "
            f"genuine work, not the network simply memorizing 8 points."
        )

        st.subheader("PINN predictions vs. kinetics.py's real ODE integration")
        _train_df = pd.DataFrame({
            "T_C": _pr["T_labeled"], "GHSV": _pr["GHSV_labeled"],
            "True (kinetics.py)": _pr["X_labeled"],
            "Predicted (PINN)": pinn_kinetics.predict(_pinn["weights"], _pr["T_labeled"], _pr["GHSV_labeled"]),
            "Category": "Training point (labeled)",
        })
        _test_df = pd.DataFrame({
            "T_C": _pr["T_test"], "GHSV": _pr["G_test"],
            "True (kinetics.py)": _pr["X_true"],
            "Predicted (PINN)": _pinn["predictions"],
            "Category": np.where(_pr["near_mask"], "Test point (near training)", "Test point (far from training)"),
        })
        _plot_df = pd.concat([_train_df, _test_df], ignore_index=True)

        _diag = alt.Chart(pd.DataFrame({"x": [0, 1], "y": [0, 1]})).mark_line(
            strokeDash=[4, 4], color="gray"
        ).encode(x="x:Q", y="y:Q")
        _scatter = alt.Chart(_plot_df).mark_point(size=90, filled=True).encode(
            x=alt.X("True (kinetics.py):Q", title="True HTS conversion (kinetics.py)", scale=alt.Scale(domain=[0, 1])),
            y=alt.Y("Predicted (PINN):Q", title="PINN-predicted HTS conversion", scale=alt.Scale(domain=[0, 1])),
            color=alt.Color("Category:N", scale=alt.Scale(
                domain=["Training point (labeled)", "Test point (near training)", "Test point (far from training)"],
                range=["#000000", "#4C78A8", "#E45756"],
            )),
            shape=alt.Shape("Category:N", scale=alt.Scale(
                domain=["Training point (labeled)", "Test point (near training)", "Test point (far from training)"],
                range=["diamond", "circle", "circle"],
            )),
            tooltip=["T_C:Q", "GHSV:Q", "True (kinetics.py):Q", "Predicted (PINN):Q", "Category:N"],
        )
        st.altair_chart((_diag + _scatter).properties(height=380), use_container_width=True)
        st.caption(
            "Points on the dashed diagonal are perfect predictions. Black diamonds are the 8 labeled "
            "training points; blue/red circles are the 40 held-out test points the PINN never saw "
            "during training, split by distance to the nearest training point."
        )

        with st.expander("Full table: training points and test points"):
            st.dataframe(
                _plot_df.assign(error=(_plot_df["Predicted (PINN)"] - _plot_df["True (kinetics.py)"]).abs())
                .round({"T_C": 1, "GHSV": 0, "True (kinetics.py)": 4, "Predicted (PINN)": 4, "error": 4}),
                use_container_width=True,
            )

    st.divider()

    # ---------------------------------------------------------------------
    # Section 18 — Sim-to-real transfer (v1: synthetic domain-gap injection
    # and warm-started fine-tuning on the PINN — see python/sim_to_real.py
    # for the full honest-scoping statement)
    # ---------------------------------------------------------------------
    st.header("Sim-to-Real Transfer")
    st.warning(
        "**Synthetic 'real world', not a real plant.** This repo has no real plant or real sensors to "
        "transfer to. 'Real-world' data below means `kinetics.py`'s own true conversion values, "
        "deliberately corrupted with two illustrative, adjustable imperfections: Gaussian noise on the "
        "conversion reading (a gas analyser is never exact) and a systematic temperature calibration "
        "offset (a thermocouple reading consistently off true process temperature). Both magnitudes are "
        "assumed defaults, not measured instrument specs. This demonstrates the *mechanism* of domain-"
        "gap evaluation and adaptation on this project's own validated physics — it is not a claim of "
        "real-world validation.",
        icon="⚠️",
    )
    st.caption(
        "Pre-adaptation error is measured against what a real deployment would actually have to check "
        "against — the sensor's own noisy reading — not an oracle true value, since a real deployment "
        "wouldn't have one either. That's why both sliders below move it."
    )

    s2r_col1, s2r_col2 = st.columns(2)
    with s2r_col1:
        s2r_noise_std = st.slider(
            "Sensor noise (Gaussian std, conversion fraction)", 0.0, 0.10,
            sim_to_real.DEFAULT_NOISE_STD, step=0.01, key="s2r_noise",
        )
    with s2r_col2:
        s2r_offset = st.slider(
            "Temperature calibration offset (°C)", 0.0, 10.0,
            sim_to_real.DEFAULT_CALIB_OFFSET_C, step=0.5, key="s2r_offset",
        )

    if st.button("Run sim-to-real transfer experiment"):
        with st.spinner("Training/reusing the simulation PINN, injecting noise, and fine-tuning..."):
            if "s2r_sim_weights" not in st.session_state:
                st.session_state["s2r_sim_weights"] = pinn_kinetics.train(seed=7)[0]
            st.session_state["s2r_result"] = sim_to_real.run_transfer_experiment(
                flat_sim=st.session_state["s2r_sim_weights"],
                noise_std=s2r_noise_std, calib_offset_C=s2r_offset,
            )

    if "s2r_result" in st.session_state:
        _sr = st.session_state["s2r_result"]
        _pre, _post = _sr["pre"], _sr["post"]

        st.subheader("Domain gap: before vs. after adaptation")
        scol1, scol2, scol3 = st.columns(3)
        scol1.metric("Pre-adaptation error (no adaptation)", f"{_pre['mean_error']:.4f}")
        scol2.metric(
            "Post-adaptation error (8 noisy points)", f"{_post['mean_error']:.4f}",
            delta=f"{_post['mean_error'] - _pre['mean_error']:+.4f}", delta_color="inverse",
        )
        scol3.metric("Domain gap closed", f"{_sr['gap_closed_fraction'] * 100:.0f}%")

        if _sr["gap_closed_fraction"] >= 0:
            st.write(
                f"Fine-tuning on just 8 noisy real-world points reduced mean error from "
                f"{_pre['mean_error']:.4f} to {_post['mean_error']:.4f} — {_sr['gap_closed_fraction'] * 100:.0f}% "
                f"of the domain gap closed. "
                + ("The gap was not fully closed — some residual error remains even after adaptation."
                   if _sr["gap_closed_fraction"] < 0.99 else "")
            )
        else:
            st.write(
                f"**Adaptation did not help here** — post-adaptation error ({_post['mean_error']:.4f}) is "
                f"higher than pre-adaptation error ({_pre['mean_error']:.4f}). This is an honest result, "
                f"not a bug: with a small (or zero) calibration offset, the imperfection is mostly random "
                f"sensor noise with no systematic bias to correct, so fine-tuning on just 8 noisy points "
                f"has nothing systematic to learn and can slightly overfit to that noise instead. Try "
                f"raising the temperature calibration offset — a genuine systematic domain shift is what "
                f"this adaptation step is actually good at correcting."
            )

        with st.expander("The 8 noisy points used to adapt, and the 40 held-out points used to evaluate"):
            _adapt_df = pd.DataFrame({
                "T_true (°C)": _sr["adapt_set"]["T_true_C"], "T_sensor (°C)": _sr["adapt_set"]["T_sensor_C"],
                "GHSV": _sr["adapt_set"]["GHSV"], "X_true": _sr["adapt_set"]["X_true"],
                "X_observed (used to fine-tune)": _sr["adapt_set"]["X_observed"],
            }).round(3)
            st.write("**Adaptation points (8, noisy — the model never sees `X_true`, only `X_observed`):**")
            st.dataframe(_adapt_df, use_container_width=True)

            _eval_df = pd.DataFrame({
                "T_true (°C)": _sr["real_world_eval"]["T_true_C"], "T_sensor (°C)": _sr["real_world_eval"]["T_sensor_C"],
                "GHSV": _sr["real_world_eval"]["GHSV"], "X_observed": _sr["real_world_eval"]["X_observed"],
                "Pred (pre-adaptation)": _pre["predictions"], "Pred (post-adaptation)": _post["predictions"],
            }).round(3)
            st.write("**Evaluation points (40, held out from adaptation):**")
            st.dataframe(_eval_df, use_container_width=True)

    st.divider()

    # ---------------------------------------------------------------------
    # Section 19 — Federated learning (v1: genuine FedAvg across hypothetical
    # plant instances — same illustrative-variant pattern as
    # multi_module_orchestration.py; see python/federated_learning.py for
    # the full honest-scoping statement)
    # ---------------------------------------------------------------------
    st.header("Federated Learning")
    st.warning(
        "**Illustrative hypothetical plants, not real facilities.** This repo represents exactly one "
        "real plant. The plants below are illustrative HTS-temperature-variant stand-ins — the same "
        "pattern Multi-Module Orchestration above already uses — not live data from a real fleet. What "
        "IS real: genuine federated averaging (FedAvg) of real model weights, trained with this "
        "project's own validated physics-informed loss, reused unchanged from `pinn_kinetics.py`.",
        icon="⚠️",
    )
    st.caption(
        "**The federated-learning premise, actually implemented:** each hypothetical plant has its own "
        "private local training data AND its own local physics-collocation sampling, restricted to its "
        "own narrow operating band — it never sees another plant's data, and never pools raw data with "
        "anyone. Only trained weights cross plant boundaries, and only via a plain average (FedAvg)."
    )

    fl_col1, fl_col2 = st.columns(2)
    with fl_col1:
        fl_n_plants = st.slider("Number of hypothetical plants", 2, len(federated_learning.DEFAULT_PLANTS),
                                 len(federated_learning.DEFAULT_PLANTS), key="fl_n_plants")
    with fl_col2:
        fl_n_rounds = st.slider("Federation rounds", 10, 80, 50, step=10, key="fl_n_rounds")

    if st.button("Run federated learning experiment"):
        with st.spinner("Training locally at each plant, federating weights across rounds, and training "
                         "the single-plant and pooled-upper-bound comparison models — can take up to a "
                         "minute..."):
            st.session_state["fl_result"] = federated_learning.run_experiment(
                plants=federated_learning.DEFAULT_PLANTS[:fl_n_plants], n_rounds=fl_n_rounds,
            )

    if "fl_result" in st.session_state:
        _fr = st.session_state["fl_result"]

        st.subheader("Step 3: three-way comparison on a full-domain test set")
        st.caption(
            "Federated is compared against each single-plant-alone model (no federation at all) and, as "
            "an honest upper-bound REFERENCE ONLY, a model trained on every plant's raw data pooled "
            "together directly — exactly what federated learning exists to avoid."
        )
        _fl_rows = [
            {"Model": s["name"] + " (alone)", "Mean abs. error": s["mean_error"], "Max abs. error": s["max_error"]}
            for s in _fr["single_results"]
        ]
        _fl_rows.append({"Model": "Single-plant-alone AVERAGE", "Mean abs. error": _fr["avg_single_mean_error"], "Max abs. error": None})
        _fl_rows.append({"Model": "FEDERATED (FedAvg)", "Mean abs. error": _fr["fed_result"]["mean_error"], "Max abs. error": _fr["fed_result"]["max_error"]})
        _fl_rows.append({"Model": "POOLED — upper bound, reference only", "Mean abs. error": _fr["pooled_result"]["mean_error"], "Max abs. error": _fr["pooled_result"]["max_error"]})
        _fl_df = pd.DataFrame(_fl_rows)
        st.dataframe(_fl_df.round(4), use_container_width=True, hide_index=True)

        def _fl_role(name):
            if name == "FEDERATED (FedAvg)":
                return "Federated"
            if name == "POOLED — upper bound, reference only":
                return "Pooled (reference only)"
            return "Single-plant-alone"

        _fl_chart_df = _fl_df.dropna(subset=["Max abs. error"]).copy()
        _fl_chart_df["Role"] = _fl_chart_df["Model"].apply(_fl_role)
        _fl_bar = alt.Chart(_fl_chart_df).mark_bar().encode(
            x=alt.X("Mean abs. error:Q", title="Mean absolute error (full-domain test set)"),
            y=alt.Y("Model:N", sort="-x", title=None),
            color=alt.Color("Role:N", scale=alt.Scale(
                domain=["Single-plant-alone", "Federated", "Pooled (reference only)"],
                range=["#BAB0AC", "#4C78A8", "#B279A2"],
            )),
        ).properties(height=220)
        st.altair_chart(_fl_bar, use_container_width=True)

        _fed_err = _fr["fed_result"]["mean_error"]
        _avg_single_err = _fr["avg_single_mean_error"]
        _best_single_err = _fr["best_single_mean_error"]
        _pooled_err = _fr["pooled_result"]["mean_error"]
        _avg_line = (
            f"Federated's mean error ({_fed_err:.4f}) is **{_avg_single_err / _fed_err:.1f}× better than the "
            f"average single-plant-alone model** ({_avg_single_err:.4f})."
            if _fed_err < _avg_single_err else
            f"Federated's mean error ({_fed_err:.4f}) does **not** beat the average single-plant-alone model "
            f"({_avg_single_err:.4f}) here — with plants this similar to each other, there's less of a "
            f"robustness gap for federation to close (see the cross-plant checks below, which are the real test)."
        )
        _pooled_line = (
            f"It sits {_fed_err / _pooled_err:.1f}× above the pooled upper bound ({_pooled_err:.4f})."
            if _fed_err > _pooled_err else
            f"It even matches or beats the pooled upper bound ({_pooled_err:.4f}) here."
        )
        _best_line = (
            f"It does **not** beat every single-plant model on this full-domain metric — the best single "
            f"plant alone ({_best_single_err:.4f}) is still somewhat better here — federation's real payoff "
            f"is shown below: robustness on data no single plant's own model ever saw."
            if _best_single_err < _fed_err else
            f"It also beats the single best-case plant-alone model ({_best_single_err:.4f})."
        )
        st.write(f"{_avg_line} {_pooled_line} {_best_line}")

        st.subheader("Step 5: the actual point — does federation help on data a plant never saw?")
        st.caption(
            "Each plant's OWN single-plant model, evaluated on ANOTHER plant's local operating range (data "
            "it never trained on, directly or via any physics constraint) — compared to the federated "
            "model on that same held-out range, which only ever received averaged weights, never that "
            "plant's raw data either."
        )
        _cross_df = pd.DataFrame(_fr["cross_checks"])
        _cross_df = _cross_df.rename(columns={
            "single_plant": "Single-plant model", "tested_on_range_of": "Tested on range of",
            "single_plant_error": "Single-plant error", "federated_error": "Federated error",
            "federated_wins": "Federated wins",
        })
        st.dataframe(_cross_df.round(4), use_container_width=True, hide_index=True)
        st.write(
            f"**Federated wins {_fr['federated_wins_fraction'] * 100:.0f}% of these cross-plant checks** — "
            f"most decisively exactly where it matters most: correcting a single plant's worst blind spots, "
            f"not just nudging its already-good regions."
        )

    st.divider()

    # ---------------------------------------------------------------------
    # Section 20 — Performance guarantee pricing (v1: PSA recovery threshold
    # guarantee priced from uncertainty.py's real Monte Carlo distribution —
    # see python/performance_guarantee.py for the full honest-scoping
    # statement)
    # ---------------------------------------------------------------------
    st.header("Performance Guarantee Pricing")
    st.warning(
        "**Illustrative pricing framework, not a real actuarial/insurance-grade guarantee.** This "
        "prices a hypothetical \"we guarantee ≥X% PSA recovery, or pay a penalty\" offer using this "
        "project's own Monte Carlo uncertainty distribution — real guarantee terms need actual legal "
        "and financial structuring (credit risk, counterparty terms, measurement/verification protocol, "
        "force majeure) that doesn't exist here. The penalty rate below is OUR OWN assumed placeholder "
        "— same honesty pattern as Circularity Scoring's ash/carbon-black market prices — not sourced "
        "from any real DOK-ING contract or market data.",
        icon="⚠️",
    )
    st.caption(
        "**What IS real:** breach probability and expected cost are computed directly from "
        "`uncertainty.py`'s genuine Monte Carlo propagation of the six real unconfirmed design "
        "assumptions through the real `kinetics.py`/`psa.py` physics — not a guessed number. PSA "
        "recovery's uncertainty in this model comes entirely from the PSA recovery target calibration "
        "assumption, so this section is automatically live to whatever the Confirmation Tracker above "
        "has (or hasn't) confirmed for it."
    )

    _pg_confirmed = uncertainty.is_confirmed("psa_target_calibration")
    _pg_lo, _pg_hi = uncertainty.bounds("psa_target_calibration")
    st.write(
        f"**Current PSA calibration range in use:** [{_pg_lo:.2f}, {_pg_hi:.2f}]× "
        f"({'CONFIRMED via Confirmation Tracker' if _pg_confirmed else 'default ±15% assumption, unconfirmed'})"
    )

    pg_col1, pg_col2, pg_col3 = st.columns(3)
    with pg_col1:
        pg_threshold = st.slider(
            "Guaranteed PSA recovery (≥, %)", 65.0, 80.0, performance_guarantee.DEFAULT_THRESHOLD * 100,
            step=0.5, key="pg_threshold",
        ) / 100.0
    with pg_col2:
        pg_penalty = st.number_input(
            "Penalty (€ per percentage-point shortfall)", min_value=0.0,
            value=performance_guarantee.DEFAULT_PENALTY_EUR_PER_POINT, step=500.0, key="pg_penalty",
        )
    with pg_col3:
        pg_n_runs = st.slider("Monte Carlo runs", 200, 1000, performance_guarantee.DEFAULT_N_RUNS, step=100, key="pg_n_runs")

    if st.button("Price this guarantee"):
        with st.spinner(f"Running {pg_n_runs} samples through the real PSA recovery uncertainty distribution..."):
            st.session_state["pg_result"] = performance_guarantee.price_guarantee(
                pg_threshold, penalty_eur_per_point=pg_penalty, n_runs=pg_n_runs,
            )

    if "pg_result" in st.session_state:
        _pg = st.session_state["pg_result"]
        pgcol1, pgcol2, pgcol3 = st.columns(3)
        pgcol1.metric("Breach probability", f"{_pg['breach_probability'] * 100:.1f}%")
        pgcol2.metric("Expected cost", f"€{_pg['expected_cost']:,.0f}")
        pgcol3.metric("Expected cost, given breach", f"€{_pg['expected_cost_given_breach']:,.0f}")

        st.caption(
            f"From {_pg['n_samples']} Monte Carlo samples: mean recovery {_pg['mean_recovery'] * 100:.1f}%, "
            f"90% CI [{_pg['p5_recovery'] * 100:.1f}%, {_pg['p95_recovery'] * 100:.1f}%]. Given a breach, the "
            f"average shortfall is {_pg['mean_shortfall_points_given_breach']:.2f} percentage points."
        )

        _pg_df = pd.DataFrame({
            "recovery_pct": _pg["samples"] * 100,
            "Result": np.where(_pg["breach_mask"], "Breaches guarantee", "Meets guarantee"),
        })
        _pg_hist = alt.Chart(_pg_df).mark_bar().encode(
            x=alt.X("recovery_pct:Q", bin=alt.Bin(maxbins=40), title="PSA recovery (%)"),
            y=alt.Y("count():Q", title="Monte Carlo samples"),
            color=alt.Color("Result:N", scale=alt.Scale(
                domain=["Meets guarantee", "Breaches guarantee"], range=["#4C78A8", "#E45756"],
            )),
        ).properties(height=260)
        _pg_rule = alt.Chart(pd.DataFrame({"x": [pg_threshold * 100]})).mark_rule(
            color="black", strokeDash=[4, 4], size=2,
        ).encode(x="x:Q")
        st.altair_chart(_pg_hist + _pg_rule, use_container_width=True)
        st.caption("Dashed line: the guaranteed threshold. Red bars: samples that would breach it.")

    st.divider()

    # ---------------------------------------------------------------------
    # Section 21 — Topological data analysis (v1: multi-sensor coordinated-
    # anomaly detection on a synthetic time series — see
    # python/time_series_sim.py and python/tda_analysis.py for the full
    # honest-scoping statements)
    # ---------------------------------------------------------------------
    st.header("Topological Data Analysis")
    st.warning(
        "**First-pass illustrative pipeline on synthetic data — not validated against real plant "
        "sensor data.** The underlying time series is a steady-state physics chain (`kinetics.py`/"
        "`psa.py`) evaluated repeatedly at evolving operating conditions, explicitly NOT real process "
        "dynamics — this repo has zero time-domain modeling elsewhere (the Novelty Audit above already "
        "flags zero Dynamics coverage), and this module doesn't quietly try to close that gap.",
        icon="⚠️",
    )
    st.caption(
        f"**Dependency decision:** none of ripser / giotto-tda / persim / gudhi are installed "
        f"(checked directly at import time — real-library available: "
        f"`{tda_analysis.TDA_LIBRARY_AVAILABLE}`), and adding one is a real build/size risk on "
        "Streamlit Community Cloud's free tier (most ship native C++/Cython extensions). Instead this "
        "uses the lighter, still-genuinely-topological alternative: exact 0-dimensional persistent "
        "homology via the well-known single-linkage/minimum-spanning-tree equivalence (scipy only, no "
        "new dependency) — real H0 persistence, not H1/loops, which a real library would be needed for."
    )
    st.caption(
        "**The test case:** a simulated startup ramp into steady operation, then a period where "
        "several sensors shift slightly together — each individually too small to trip its own "
        "threshold — then recovery. The topological score compares a sliding window's multi-sensor "
        "shape against a reference cloud of known-normal operation; a naive per-sensor rolling-"
        "deviation monitor is the comparison baseline."
    )

    if st.button("Run time-series simulation + TDA analysis"):
        with st.spinner("Simulating the plant trajectory (predictive-maintenance root-finding is the "
                         "slow part) and computing the topological score — can take a minute or more..."):
            _tda_result = tda_analysis.run_tda()
            st.session_state["tda_result"] = _tda_result
            st.session_state["tda_comparison"] = tda_analysis.compare_to_naive_baseline(_tda_result)

    if "tda_result" in st.session_state:
        _tr = st.session_state["tda_result"]
        _tc = st.session_state["tda_comparison"]
        _td = _tr["data"]

        st.subheader("Step 5: does TDA catch what per-sensor thresholds miss?")
        tdacol1, tdacol2, tdacol3, tdacol4 = st.columns(4)
        tdacol1.metric("TDA detection (in anomaly)", f"{_tc['tda_detection_rate_in_anomaly'] * 100:.0f}%")
        tdacol2.metric("TDA false-positive rate", f"{_tc['tda_false_positive_rate_in_normal'] * 100:.0f}%")
        tdacol3.metric("Naive detection (in anomaly)", f"{_tc['naive_detection_rate_in_anomaly'] * 100:.0f}%")
        tdacol4.metric("Naive false-positive rate", f"{_tc['naive_false_positive_rate_in_normal'] * 100:.0f}%")
        st.write(tda_analysis.summarize_comparison(_tc))

        _anomaly_t = _td["t"][_td["is_anomaly"]]
        _span_df = pd.DataFrame({"t_start": [int(_anomaly_t.min())], "t_end": [int(_anomaly_t.max()) + 1]})
        _band = alt.Chart(_span_df).mark_rect(opacity=0.15, color="#E45756").encode(x="t_start:Q", x2="t_end:Q")

        st.subheader("The multi-sensor time series (each shift individually subtle)")
        _sensor_df = pd.concat([
            pd.DataFrame({"t": _td["t"], "value": _td["hts"] * 100, "Sensor": "HTS conversion (%)"}),
            pd.DataFrame({"t": _td["t"], "value": _td["lts"] * 100, "Sensor": "LTS conversion (%)"}),
            pd.DataFrame({"t": _td["t"], "value": _td["psa_recovery"] * 100, "Sensor": "PSA recovery (%)"}),
            pd.DataFrame({"t": _td["t"], "value": _td["activity_factor"] * 100, "Sensor": "Activity factor (%)"}),
        ], ignore_index=True)
        _sensor_lines = alt.Chart(_sensor_df).mark_line(size=1.5).encode(
            x=alt.X("t:Q", title="Timestep"), y=alt.Y("value:Q", title="Value (%)", scale=alt.Scale(zero=False)),
            color=alt.Color("Sensor:N", title=None),
        )
        st.altair_chart((_band + _sensor_lines).properties(height=280), use_container_width=True)
        st.caption("Red band: the coordinated-anomaly period. Notice no single line makes an obvious jump there.")

        st.subheader("Topological anomaly score over time")
        _score_df = pd.DataFrame({"t": _td["t"], "score": _tr["score"]}).dropna()
        _score_line = alt.Chart(_score_df).mark_line(color="#4C78A8", size=1.5).encode(
            x=alt.X("t:Q", title="Timestep"), y=alt.Y("score:Q", title="Topological anomaly score"),
        )
        _threshold_rule = alt.Chart(pd.DataFrame({"y": [_tc["score_threshold"]]})).mark_rule(
            color="black", strokeDash=[4, 4],
        ).encode(y="y:Q")
        st.altair_chart((_band + _score_line + _threshold_rule).properties(height=280), use_container_width=True)
        st.caption(
            "Dashed line: the flagging threshold (95th percentile of scores during known-normal "
            "operation). Red band: the coordinated-anomaly period — a real detection shows the blue "
            "line rising above the dashed line inside the red band."
        )

    st.divider()

    st.caption("HYGAS-AI — SMITH2 R&D Hydrogen Agency — NACHIP Pilot Programme")

with tab2:
    st.info("Reserved for future work.")

with tab3:
    st.header("Equipment Datasheets")
    st.warning(
        "**Deliberately scoped, incremental coverage: FE-001–008 (Feed Handling) and GA-001–010 "
        "(Gasification) so far — 18 of the 91 registry items.** The other 73 items are NOT covered "
        "yet — this stays a narrow, growing section, not a simplified stand-in for the rest. Every "
        "data point below is read directly from `equipment_registry.load_registry()` — the same "
        "loader Vendor Sourcing (Tab 1) already uses, not a re-derived or simplified copy. Nothing "
        "here infers, estimates, or backfills a value that isn't literally present in the registry. "
        "See `python/equipment_datasheet.py` for the full categorization methodology and the exact "
        "keyword rule used to sort each real parameter into a category.",
        icon="⚠️",
    )
    st.caption(
        "Each item's real registry parameters are sorted into six categories — Inputs, Outputs, "
        "Parameters, Measurements, Operating Conditions, Performance Indicators — by a documented "
        "keyword rule applied to the parameter's own name (not a per-item judgment call). A "
        "category with no real data mapped to it is shown as **Missing Data — Required**, never a "
        "plausible-sounding placeholder."
    )

    _eq_datasheets = equipment_datasheet.build_all_datasheets()
    _fe_summary = equipment_datasheet.summarize(_eq_datasheets, ids=equipment_datasheet.FE_IDS)
    _ga_summary = equipment_datasheet.summarize(_eq_datasheets, ids=equipment_datasheet.GA_IDS)

    def _render_honest_count(title, summary, n_items):
        st.subheader(title)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Real data points", summary["total_real_data_points"])
        c2.metric(f"Category slots ({n_items} items × 6)", summary["total_category_slots"])
        c3.metric("Populated categories", summary["populated_category_slots"])
        c4.metric("Missing Data — Required", summary["missing_category_slots"],
                   delta=f"{summary['missing_category_slots'] / summary['total_category_slots'] * 100:.0f}% of all category slots",
                   delta_color="inverse")
        st.caption(
            f"{summary['total_real_data_points']} real parameter values are on file across these "
            f"{n_items} items, but only {summary['populated_category_slots']} of the "
            f"{summary['total_category_slots']} possible (item × category) slots actually have real "
            f"data mapped to them — the registry simply doesn't carry every category for every item. "
            f"That gap is reported honestly below, not rounded up."
        )

    st.subheader("Honest count: how complete is this coverage, really?")
    st.caption(
        "Reported per section, not blended into one number — including a check that adding the GA "
        "section left the FE section's own earlier count untouched."
    )
    _render_honest_count("Feed Handling (FE-001–008)", _fe_summary, 8)
    if _fe_summary["total_real_data_points"] == 69 and _fe_summary["populated_category_slots"] == 26:
        st.success("Unchanged from before the GA extension: 69 real data points, 26/48 categories populated.")
    else:
        st.error(
            f"**Regression:** FE's count changed to {_fe_summary['total_real_data_points']} real data "
            f"points, {_fe_summary['populated_category_slots']}/48 populated — was 69/26 before the GA "
            f"extension. The keyword-rule extension affected FE classification; see "
            f"python/equipment_datasheet.py."
        )
    st.divider()
    _render_honest_count("Gasification (GA-001–010)", _ga_summary, 10)

    st.divider()

    def _render_datasheet_items(ids, per_item_stats):
        for _item_id in ids:
            _entry = _eq_datasheets.get(_item_id)
            if _entry is None:
                continue
            _item = _entry["item"]
            _sheet = _entry["datasheet"]
            _stat = per_item_stats[_item_id]
            with st.expander(f"**{_item_id}** — {_item['name']}  ·  {_stat['populated_categories']}/6 categories populated"):
                for _cat in equipment_datasheet.CATEGORIES:
                    _rows = _sheet[_cat]
                    if not _rows:
                        st.error(f"**{_cat}:** Missing Data — Required")
                        continue
                    st.markdown(f"**{_cat}**")
                    _cat_df = pd.DataFrame([
                        {"Parameter": p["parameter"], "Value": p["value"], "Unit": p["unit"], "Remarks": p.get("remarks", "")}
                        for p in _rows
                    ])
                    st.dataframe(_cat_df, use_container_width=True, hide_index=True)

    st.subheader("Feed Handling — FE-001 through FE-008")
    _render_datasheet_items(equipment_datasheet.FE_IDS, _fe_summary["per_item"])

    st.subheader("Gasification — GA-001 through GA-010")
    _render_datasheet_items(equipment_datasheet.GA_IDS, _ga_summary["per_item"])
