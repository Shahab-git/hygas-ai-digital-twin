"""Task A1.4: the read-only display of the gasifying agent in the GA-001 live card (app.py `_ga_agent_view`, `_render_ga_agent_panel`).

The card shows the active agent, the values the model used (effective ER, steam-to-feed, oxidant O2 fraction), the registry's expected N2 beside the model's dry N2 (with the registry row's resolved
status, the unstated wet / dry basis and "no verdict" while no tolerance is set) and the Missing terms, in neutral wording. There is NO selector, nothing is written, and a stored snapshot from before
the switch (no agent entries) still renders, as air. The entries used are REAL ones from the unchanged engine (tab1_integration.build_live_snapshot) put into the stored sample snapshot
(tests/fixtures/sample_snapshot.json, a TEST FIXTURE). Offline: counting fake store, blocked network.

FILE NAME: it starts with "test_a1" on purpose. An AppTest run after a bare-mode runpy of app.py in the same process fails with a Streamlit form-context error (see the note in tests/test_ga_carbon_black_card.py),
so every AppTest-based module must sort before the modules that runpy the app.
"""
import ast
import json
import os
import re
import urllib.error
from unittest import mock

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from _fakes import FakeSupabase, patched_supabase
from python import cycle_clock
from python import ga001_gasifier_model as ga001
from python import plant_status as ps
from python import tab1_integration as t1

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP = os.path.join(ROOT, "app.py")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "sample_snapshot.json")
PANEL = "Gasifying agent (read-only)"
AGENT_KEYS = [("GA-001-INPUT", "gasifying_agent"), ("GA-001", "AgentConsistency"), ("GA-001", "EnergyBalance"), ("GA-001", "Outputs"),
              ("GA-001-INPUT", "equivalence_ratio"), ("GA-001-INPUT", "steam_to_feed_ratio")]
JUDGEMENT_WORDS = ("wrong", "error", "fail", "invalid", "bad", "mismatch", "inconsistent", "violat", "incorrect", "contradict", "unrealistic", "reject")


def _const(v):
    def fn(get_input):
        return {"value": v, "status": ps.STATUS_ASSUMED, "inputs": [], "validation_basis": ps.VALIDATION_NA, "confidence_note": "test"}
    return fn


def _fixture_rows():
    with open(FIXTURE, encoding="utf-8") as handle:
        doc = json.load(handle)
    return [{"equipment_id": e["key"][0], "category": e["key"][1], "entry": e["entry"], "cycle": 1, "published_at": "2026-09-10T00:04:00Z"} for e in doc["entries"]]


def _rows_with(entries):
    rows = [r for r in _fixture_rows() if (r["equipment_id"], r["category"]) not in entries]
    rows += [{"equipment_id": k[0], "category": k[1], "entry": e, "cycle": 1, "published_at": "2026-09-10T00:04:00Z"} for k, e in entries.items()]
    return rows


def _live_entries(agent):
    cycle_clock.set_elapsed_hours(None)
    with patched_supabase(FakeSupabase()):
        snap, _s, _e = t1.build_live_snapshot(5, overrides=None if agent == "air" else {ga001.GASIFYING_AGENT_KEY: _const(agent)})
    return {k: json.loads(json.dumps(t1._native(snap[k]))) for k in AGENT_KEYS}


def _run(rows):
    st.cache_data.clear()
    fake = FakeSupabase({"plant_state_current": rows})
    with patched_supabase(fake), mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("network blocked in tests")):
        at = AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception, [str(e.value)[:300] for e in at.exception]
    assert [c for c in fake.calls if c[0] != "select"] == [], "the app wrote to the (fake) database"
    return at


def _panel_text(at):
    """The text of the agent panel, in order: the children (markdown and captions) of the expander labelled PANEL."""
    panel = next(e for e in at.expander if e.label == PANEL)
    return [c.value for _, c in sorted(panel.children.items()) if hasattr(c, "value")]


@pytest.fixture(scope="module")
def apps():
    """{label: AppTest after run}: an OLD stored snapshot (no agent entries) and the live entries of air, steam-only and oxygen."""
    out = {"old": _run(_fixture_rows())}
    for agent in ("air", "steam_only_0.8", "oxygen"):
        out[agent] = _run(_rows_with(_live_entries(agent)))
    return out


# ---------------------------------------------------------------- what the card shows

def test_an_old_stored_snapshot_still_renders_the_panel_as_air_and_says_it_predates_the_switch(apps):
    assert any(e.label == PANEL for e in apps["old"].expander)
    lines = _panel_text(apps["old"])
    assert lines[0].startswith("Active agent: **air**")
    assert any("predates the switch" in x for x in lines)
    assert not any("vol%" in x for x in lines), "no consistency entry in an old snapshot: no numbers are invented"
    assert not any(x.startswith("Missing:") for x in lines)


def test_the_air_agent_shows_its_effective_values_the_n2_numbers_and_no_missing_terms(apps):
    lines = _panel_text(apps["air"])
    text = " ".join(lines)
    assert lines[0].startswith("Active agent: **air**") and "predates" not in text
    assert "ER 0.25" in text and "steam-to-feed 0.4 kg/kg" in text and "oxidant O₂ fraction 21 %" in text
    assert "registry expected N₂ 10 vol%" in text and "resolved status Assumed" in text and "wet or dry basis not stated" in text
    assert re.search(r"Model dry N₂ 39\.\d\d vol%", text) and "difference (model minus registry) +29." in text
    assert "tolerance not set, no verdict is given" in text
    assert not any(x.startswith("Missing:") for x in lines)


def test_a_steam_only_agent_shows_the_effective_values_no_oxygen_used_and_the_missing_terms(apps):
    lines = _panel_text(apps["steam_only_0.8"])
    text = " ".join(lines)
    assert lines[0].startswith("Active agent: **steam_only_0.8**")
    assert "ER 0 " in text and "steam-to-feed 0.8 kg/kg" in text and "no oxygen used, no oxidant" in text
    missing = [x for x in lines if x.startswith("Missing:")]
    assert len(missing) == 2 and "external (allothermal) heat duty" in missing[1] and "no oxygen used" in missing[0]
    low = text.lower()
    assert "air-separation" not in low and "air separation" not in low and "asu" not in low.split()


def test_an_oxygen_agent_shows_its_o2_fraction_and_the_two_missing_terms(apps):
    lines = _panel_text(apps["oxygen"])
    text = " ".join(lines)
    assert lines[0].startswith("Active agent: **oxygen**") and "oxidant O₂ fraction 100 %" in text
    missing = [x for x in lines if x.startswith("Missing:")]
    assert len(missing) == 2 and "oxygen source" in missing[0] and "external (allothermal) heat duty" in missing[1]
    assert all("Missing" in x and "0 kW" not in x and "closed" not in x.lower() for x in missing)


def test_the_wording_is_neutral_in_every_case(apps):
    for label, at in apps.items():
        text = " ".join(_panel_text(at)).lower()
        assert not [w for w in JUDGEMENT_WORDS if w in text], (label, text)


# ---------------------------------------------------------------- read only: no selector, nothing written

def test_the_rendered_app_has_no_widget_that_selects_an_agent(apps):
    for label, at in apps.items():
        widgets = [w for kind in ("selectbox", "radio", "select_slider", "toggle", "checkbox", "multiselect", "button", "text_input", "number_input", "slider")
                   for w in getattr(at, kind)]
        assert not [w.label for w in widgets if re.search(r"gasifying|agent|oxidant", str(w.label), re.I)], (label, [w.label for w in widgets])


def test_the_panel_code_uses_only_expander_markdown_and_caption_and_no_other_source_line_pairs_the_agent_with_a_widget():
    src = open(APP, encoding="utf-8").read()
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_render_ga_agent_panel")
    used = {n.func.attr for n in ast.walk(fn) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) and n.func.value.id == "st"}
    assert used == {"expander", "markdown", "caption"}, used
    widget = re.compile(r"st\.(selectbox|radio|select_slider|toggle|checkbox|multiselect|button|text_input|number_input|slider|form)\(")
    assert not [ln for ln in src.splitlines() if re.search(r"gasifying_agent|GASIFYING_AGENT|_ga_agent", ln) and widget.search(ln)]
    assert "set_input" not in ast.get_source_segment(src, fn) and "promote" not in ast.get_source_segment(src, fn)


# ---------------------------------------------------------------- the view function on odd data

def _view_fn():
    src = open(APP, encoding="utf-8").read()
    fn = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "_ga_agent_view")
    ns = {"ps": ps}
    exec(compile(ast.Module([fn], []), "app.py", "exec"), ns)
    return ns["_ga_agent_view"]


def test_the_view_function_never_raises_on_missing_or_odd_entries_and_defaults_to_air():
    view = _view_fn()
    assert view({})["agent"] == "air" and view({})["effective"] is None and view({})["consistency"] is None and view({})["missing_terms"] == []
    sw = {"value": "oxygen", "status": ps.STATUS_ASSUMED}
    assert view({("GA-001-INPUT", "gasifying_agent"): sw})["agent"] == "oxygen"
    for bad in ({"value": None, "status": ps.STATUS_MISSING}, {"value": 3, "status": ps.STATUS_ASSUMED}, {"value": "air"}):
        assert view({("GA-001-INPUT", "gasifying_agent"): bad})["agent"] in ("air",), bad
    assert view({("GA-001", "AgentConsistency"): {"value": None, "status": ps.STATUS_MISSING}})["consistency"] is None
    assert view({("GA-001", "EnergyBalance"): {"value": {"no_agent_block": 1}, "status": ps.STATUS_CALCULATED}})["missing_terms"] == []
