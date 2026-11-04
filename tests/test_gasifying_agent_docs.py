"""Task A1.4: section 7 of docs/gasifying_agent_study.md ("Live agents versus study scenarios") says what the code does. Offline; reads the document and the modules only.

Guards: the table lists exactly the live agents with the study scenario, O2 fraction, ER and steam-to-feed of the code; S3 is stated not to be live; the heat capacity quoted for the oxidant sensible heat
is the one the audit uses (and O2 is the N2 value); the air-based items (ER uncertainty band, dynamics.py) and the input-entries-versus-effective-values note are there; no agent is called Confirmed."""
import os
import re

from python import balance_audit as ba
from python import ga001_gasifier_model as ga001

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STUDY_OF = {"air": "S0", "enriched_30": "S1a", "enriched_50": "S1b", "oxygen": "S2", "steam_only_0.4": "S4a", "steam_only_0.8": "S4b"}


def _section():
    text = open(os.path.join(ROOT, "docs", "gasifying_agent_study.md"), encoding="utf-8").read().replace("\r\n", "\n")
    head = "## 7. Live agents versus study scenarios (task A1)"
    assert text.count(head) == 1 and text.index(head) < text.index("## Appendix: measured tables")
    return text.split(head)[1].split("## Appendix: measured tables")[0]


def _table_rows(sec):
    return {re.match(r"\| `(\w[\w.]*)`", ln).group(1): [c.strip() for c in ln.strip().strip("|").split("|")] for ln in sec.splitlines() if re.match(r"\| `(\w[\w.]*)`", ln)}


def test_the_table_lists_exactly_the_live_agents_with_the_study_scenario_and_the_values_of_the_code():
    rows = _table_rows(_section())
    assert tuple(rows) == ga001.GASIFYING_AGENT_NAMES
    for agent, cells in rows.items():
        assert cells[1] == STUDY_OF[agent], agent
        spec = ga001.GASIFYING_AGENTS[agent]
        if spec["o2_fraction"] is not None and agent != "air":
            assert f"{spec['o2_fraction']:g}" in cells[2].replace("1.0", "1"), (agent, cells[2])
        if spec["er"] is not None:
            assert cells[3] == f"{spec['er']:g}", (agent, cells[3])
        if spec["steam_to_feed"] is not None:
            assert cells[4] == f"{spec['steam_to_feed']:g}", (agent, cells[4])
        if agent.startswith("steam_only"):
            assert "no oxygen used" in cells[2]


def test_chemical_looping_is_stated_not_to_be_a_live_agent_and_nothing_is_called_confirmed():
    sec = _section()
    assert "S3 (chemical-looping equivalent) is not a live agent" in sec
    assert not [n for n in ga001.GASIFYING_AGENT_NAMES if "loop" in n or "carrier" in n]
    assert sec.count("Confirmed") == 1 and "no agent is Confirmed" in sec
    assert "no selector in the UI" in sec.lower() or "no selector in the ui" in sec.lower()


def test_the_heat_capacity_basis_quoted_is_the_one_the_audit_uses_and_o2_takes_the_n2_value():
    sec = _section()
    assert ba.CP_J_MOLK["O2"] == ba.CP_J_MOLK["N2"] == 30.6
    assert f"CP_J_MOLK['N2'] = {ba.CP_J_MOLK['N2']:g} J/mol.K" in sec and "300-1200 K mean" in sec and "from 25 degC to 200 degC" in sec
    assert "same value for O2" in sec and "Estimated" in sec


def test_the_air_based_items_and_the_input_versus_effective_note_are_documented():
    sec = _section()
    assert "The ER uncertainty band" in sec and "+/-15 %" in sec and "run_ga001_uncertainty" in sec
    assert "python/dynamics.py" in sec and "reads no agent" in sec and "ER limits must not be read for those agents" in sec
    assert "tail-gas burner air" in sec.lower() or "The tail-gas burner air" in sec
    assert "Input entries versus the values the model used" in sec and "effective_inputs" in sec and "effective_equivalence_ratio" in sec
    assert "(0.25 and 0.4)" in sec


def test_the_missing_terms_the_check_and_the_tolerance_are_described_as_the_code_has_them():
    sec = _section()
    assert "Missing" in sec and "neither is ever 0 kW or \"closed\"" in sec and "no oxygen used" in sec
    assert "is **not set** (None)" in sec and "`consistent` is None" in sec and "without a wet or dry basis" in sec and "resolved status is **Assumed**" in sec
    assert ga001.SA005_RESOLVED_STATUS == "Assumed" and ga001.AGENT_CONSISTENCY_TOLERANCE_VOL_PCT is None
    assert "121 became 123" in sec
    low = sec.lower()
    assert "not validation against dok-ing data" in low
