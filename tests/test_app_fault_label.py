"""STAB-3: the red "FAULT" state is shown as "DESIGN FINDING" (display only).

The state value in the data stays "FAULT" (the engine, tab1_integration's logic and every comparison
are untouched); only what the app SHOWS is relabelled, because the state is the verdict of the
SIMULATED AI-004 PLC interlock (EU-009 trips when EU-008's modelled cooling duty exceeds its 20 kW
rating), a design finding of the model and not an alarm from a running plant.

Offline AppTest runs of the REAL app.py (fake store from test_app_smoke). Nothing here shows the
deployed app or a browser rendering.
"""
import re
import sys
import os
from unittest import mock

import streamlit as st
from streamlit.testing.v1 import AppTest

from _fakes import FakeSupabase, patched_supabase
import test_app_smoke as smoke

sys.path.insert(0, smoke.ROOT)
from python import tab1_integration as t1


def _run():
    st.cache_data.clear()
    with patched_supabase(FakeSupabase({"plant_state_current": smoke._store_rows()})), \
            mock.patch("urllib.request.urlopen", side_effect=smoke._offline_urlopen):
        return AppTest.from_file(smoke.APP, default_timeout=90).run()


def test_the_data_state_is_still_fault_in_the_fixture():
    """Guard: the relabel is display-only, so the fixture still carries the state value FAULT."""
    rows = smoke._store_rows()
    assert any(r["entry"].get("value") == "FAULT" for r in rows), "the fixture must still contain a FAULT state"


def test_header_and_tab2_show_design_finding_not_fault():
    at = _run()
    assert not at.exception, [str(e.value)[:300] for e in at.exception]
    header = " ".join(str(m.value) for m in at.markdown if "PLANT STATUS" in str(m.value))
    assert "DESIGN FINDING" in header and ">FAULT<" not in header and "FAULT</span>" not in header, header[:400]
    labels = [m.label for m in at.metric]
    assert "🔴 Design findings" in labels and not [l for l in labels if "FAULT" in l], labels
    assert [m.value for m in at.metric if m.label == "Overall plant status"] in (["DESIGN FINDING"], [])
    captions = " ".join(str(c.value) for c in at.caption)
    assert "design-finding items" in captions and " FAULT items" not in captions


def test_no_visible_label_says_running_live_values_any_more():
    at = _run()
    labels = [m.label for m in at.metric]
    assert "🟢 Computed this cycle (model)" in labels and "🟡 Assumed inputs only" in labels
    assert not [l for l in labels if "Running – live values" in l]


def test_alarm_line_helper_relabels_only_the_state_value():
    assert t1._display_status("FAULT") == "DESIGN FINDING" and t1._display_status("RUNNING") == "RUNNING"
    assert t1._display_status_text("EU-009: FAULT") == "EU-009: DESIGN FINDING"
    assert t1._display_status_text("EU-008 cooling ... fault_status_as_specified=FAULT") == \
        "EU-008 cooling ... fault_status_as_specified=FAULT"      # a field name = value pair is data, untouched
    assert t1._display_status_text("EU-001: state unavailable (upstream Missing)") == "EU-001: state unavailable (upstream Missing)"
