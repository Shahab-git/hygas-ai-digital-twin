"""P2-1 (named test_a2_ so it runs before the tests that load app.py with runpy: an AppTest after a runpy load fails with a form-context error, see test_ga_carbon_black_card.py): the Summary tab reads every number from the snapshot and the app shows it. Offline AppTest of the
real app.py; nothing here shows a deployed app or a browser rendering."""
import os, sys
from unittest import mock
import streamlit as st
from streamlit.testing.v1 import AppTest
from _fakes import FakeSupabase, patched_supabase
import test_app_smoke as smoke

sys.path.insert(0, smoke.ROOT)
from python import summary_tab, tab1_integration as t1


def _snap():
    return t1.build_live_snapshot()[0]


def test_summary_data_matches_the_snapshot():
    snap = _snap()
    d = summary_tab.summary_data(snap)
    assert d["total"] == len(snap) and sum(d["counts"].values()) == len(snap)
    assert d["counts"]["Measured"] == sum(1 for e in snap.values() if e["status"] == "Measured")
    assert abs(d["h2_kg_day"] - float(snap[("HB-012", "Compressor")]["value"]["h2_kg_h"]) * 24) < 1e-9
    assert d["h2_reference_kg_day"] == 50.0
    c = d["cooling"]
    assert c["demand_kw"] == float(snap[("EU-008", "CoolingSupply")]["value"]["demand_kw"])
    assert c["rating_kw"] == float(snap[("EU-008", "RecommendedCapacityEstimate")]["value"]["actual_dokking_value_kw"])


def test_missing_entries_give_none_not_a_number():
    d = summary_tab.summary_data({})
    assert d["total"] == 0 and d["h2_kg_day"] is None and d["cooling"] is None and d["psa_recovery"] is None


def test_the_summary_tab_is_removed_and_the_trace_stays_in_simulation():
    """2026-11-26: the Summary tab is gone; its trace and live run live in Simulation > Plant-wide."""
    st.cache_data.clear()
    with patched_supabase(FakeSupabase({"plant_state_current": smoke._store_rows()})), \
            mock.patch("urllib.request.urlopen", side_effect=smoke._offline_urlopen):
        at = AppTest.from_file(smoke.APP, default_timeout=90).run()
    assert not at.exception, [str(e.value)[:300] for e in at.exception]
    assert "Summary" not in [t.label for t in at.tabs] and at.tabs[0].label == "Digital Twin"
    assert at.tabs[11].label == "Simulation" and len(at.tabs) == 12 + 8
    assert any(b.label == "Start live run" for b in at.tabs[11].button)


def test_fixed_sentences_follow_the_measured_count():
    """P2-1b: the 'no measurements' statement is derived from the count, so it cannot go stale."""
    snap = dict(_snap())
    assert any("Plant measurements: none exist yet" in i for i in summary_tab.summary_data(snap)["open_items"])
    snap[("EU-009", "GridBalance")] = dict(snap[("EU-009", "GridBalance")], status="Measured")
    d = summary_tab.summary_data(snap)
    assert d["counts"]["Measured"] == 1
    assert not any("none exist yet" in i for i in d["open_items"])
