"""The maturity captions in the rendered app (task A10): every section that presents one of the AI / optimisation / virtual-sensing modules shows its class, and the lines that implied
validation, a live sensor or learning on plant data are gone. Captions only: no layout change, no new widget, no change to counts.

This file renders app.py through AppTest, so it must sort before any test that runs app.py with runpy (the ordering rule of the other app tests): the name starts with test_ai_.
Offline: the same canned store and canned weather / commit responses as tests/test_app_smoke.py."""
import ast
import os
import re
from unittest import mock

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from _fakes import FakeSupabase, patched_supabase
from python import maturity as mt
from test_app_smoke import _offline_urlopen, _store_rows

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP = os.path.join(ROOT, "app.py")
# rendered with no click: 16 of the 18 modules that are presented in the app; root_cause appears after a 'watch' reading and time_series_sim after the TDA run;
# operator_setpoints is not presented anywhere in app.py (it is the runtime's setpoint mechanism)
RENDERED = ("copilot", "optimizer", "predictive_maintenance", "pinn_kinetics", "federated_learning", "multi_agent_negotiation", "multi_module_orchestration", "sim_to_real", "tda_analysis",
            "novelty_audit", "safety_flags", "regulatory_drafting", "performance_guarantee", "sa_virtual_sensors", "ai_automation_layer", "uncertainty")
CONDITIONAL = ("root_cause", "time_series_sim")
BANNED_VALIDATION_CLAIM = re.compile(r"already[- ]validated|live[- ]validated|independently[- ]validated|genuinely validated", re.I)
REMOVED_PHRASES = ("already validated exactly", "from a live sensor", "range this project has already validated", "own validated physics-informed loss", "on this project's own validated physics",
                   "live-registered virtual sensors", "already-validated WGS reaction kinetics", "live-validated SOFC part-load efficiency curve", "independently-validated physics model",
                   "chp.py's own already-validated physics", "what's genuinely validated")


@pytest.fixture(scope="module")
def app():
    st.cache_data.clear()
    fake = FakeSupabase({"plant_state_current": _store_rows()})
    with patched_supabase(fake), mock.patch("urllib.request.urlopen", side_effect=_offline_urlopen):
        at = AppTest.from_file(APP, default_timeout=90).run()
    return at, fake


def _texts(at):
    out = [str(e.value) for coll in (at.caption, at.markdown, at.warning, at.info, at.success, at.error) for e in coll]
    out += [str(getattr(w, "label", "")) for coll in (at.number_input, at.button, at.slider, at.selectbox) for w in coll]
    return out


def test_the_app_renders_without_exception_and_writes_nothing(app):
    at, fake = app
    assert not at.exception, [str(e.value)[:300] for e in at.exception]
    assert [c for c in fake.calls if c[0] != "select"] == []
    assert len(at.tabs) == 11


@pytest.mark.parametrize("module", RENDERED)
def test_each_presenting_section_shows_its_maturity_class(app, module):
    caps = [str(c.value) for c in app[0].caption]
    assert caps.count(mt.caption(module)) == 1, module
    assert mt.caption(module).startswith(f"Maturity: {mt.class_of(module)} — ")


_TREE = []


def _caption_calls():
    if not _TREE:
        with open(APP, encoding="utf-8") as fh:
            _TREE.append(ast.parse(fh.read()))
    tree = _TREE[0]
    return [n.args[0].args[0].value for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "caption" and n.args
            and isinstance(n.args[0], ast.Call) and isinstance(n.args[0].func, ast.Attribute) and n.args[0].func.attr == "caption" and isinstance(n.args[0].func.value, ast.Name)
            and n.args[0].func.value.id == "maturity"]


def test_every_presented_module_has_exactly_one_caption_call_in_app_py_including_the_conditional_ones():
    calls = _caption_calls()
    assert sorted(calls) == sorted(RENDERED + CONDITIONAL) and len(calls) == len(set(calls)) == 18
    assert "operator_setpoints" not in calls


def test_each_caption_is_directly_under_its_header():
    with open(APP, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    for i, l in enumerate(lines):
        m = re.search(r'st\.caption\(maturity\.caption\("(\w+)"\)\)', l)
        if m and m.group(1) not in ("root_cause",):
            prev = lines[i - 1].strip()
            assert prev.startswith(("st.header(", "st.subheader(")), (m.group(1), prev[:80])


def test_the_lines_that_implied_more_than_the_module_does_are_gone(app):
    blob = "\n".join(_texts(app[0]))
    for phrase in REMOVED_PHRASES:
        assert phrase not in blob, phrase
    with open(APP, encoding="utf-8") as fh:
        src = fh.read()
    for phrase in REMOVED_PHRASES:
        assert phrase not in src, phrase
    assert "typed in by hand (%) — no live sensor is connected" in blob


def _flat(text):
    """Source text with string-literal joins removed, so a sentence split over several literals can be searched."""
    return " ".join(re.sub(r'"\s*\n\s*"', "", text).split())


def test_no_validation_claim_without_evidence_in_app_py_or_in_the_rendered_app(app):
    """A10b: 'already-validated', 'live-validated', 'independently-validated', 'genuinely validated' are gone from every string and comment of app.py and from the rendered text; the
    replacements name the documented target (kinetics.py's header: 75.0 % / 40.0 % design targets) or say there is no comparison data (the CHP part-load shape)."""
    with open(APP, encoding="utf-8") as fh:
        src = fh.read()
    assert BANNED_VALIDATION_CLAIM.findall(src) == []
    assert BANNED_VALIDATION_CLAIM.findall("\n".join(_texts(app[0]))) == []
    flat = _flat(src)
    assert "reproduces the 75.0 % / 40.0 % design targets quoted from prior MATLAB/Simulink work, with no comparison with plant data" in flat
    assert "checked only at full load, where it reproduces the rated 55 %; no comparison data exists for the part-load shape" in flat


def test_the_datasheet_fill_texts_no_longer_claim_validation():
    with open(os.path.join(ROOT, "python", "equipment_engineering_estimates.py"), encoding="utf-8") as fh:
        text = fh.read()
    flat = _flat(text)
    for phrase in ("kinetics.py's own live-validated lts_conversion() output", "independently-validated lts_conversion() output", "chp.py's own live-validated part-load correlation",
                   "chp.py's own live, independently-validated part-load correlation for SOFC"):
        assert phrase not in flat, phrase
    assert "it reproduces the 40.0% design target; no plant data" in flat and "checked only at full load" in flat


def test_no_maturity_caption_or_ai_section_claims_validation_learning_or_real_time_control(app):
    blob = "\n".join(_texts(app[0]))
    for cap in (mt.caption(m) for m in RENDERED):
        for sentence in re.split(r"(?<=[.;])\s+", cap):
            if re.search(r"validat", sentence, re.I):
                assert re.search(r"\bnot\b", sentence, re.I), sentence
        assert not re.search(r"real[- ]time|learn(s|ed|ing)? on plant|trained on plant|predicts? (the )?(failure|fail)", cap, re.I), cap
    assert not re.search(r"real[- ]time (control|optimi[sz]ation)", blob, re.I)
    assert "Maturity: TRAINED_ON_PLANT_DATA" not in blob and "Maturity: VALIDATED_ON_HELDOUT" not in blob
