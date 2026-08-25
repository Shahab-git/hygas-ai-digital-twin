"""
HYGAS-AI — Live Digital Twin Status Dashboard

Deploy at share.streamlit.io by pointing it at this repo. Uses the
verified Python physics modules in /python — the same models that were
cross-checked against the MATLAB/Simulink blocks during development.
"""
import streamlit as st
from python import kinetics, psa, chp, dispatch_ga

st.set_page_config(page_title="HYGAS-AI Digital Twin", layout="wide")

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

    cols = st.columns(4)
    for i, (name, load) in enumerate(dispatch.items()):
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

st.caption("HYGAS-AI — SMITH2 R&D Hydrogen Agency — NACHIP Pilot Programme")
