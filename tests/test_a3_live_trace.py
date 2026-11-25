"""P2-2: the Summary tab's model trace. Offline; the trace is simulated output of the unchanged engine."""
import sys
from unittest import mock
import streamlit as st
from streamlit.testing.v1 import AppTest
from _fakes import FakeSupabase, patched_supabase
import test_app_smoke as smoke

sys.path.insert(0, smoke.ROOT)
from python import live_trace, tab1_integration as t1


def test_the_last_point_equals_a_plain_snapshot_of_the_same_length():
    n = 6
    rows = live_trace.run_trace(n)
    snap = t1.build_live_snapshot(n)[0]
    last = rows[-1]
    assert [r["cycle"] for r in rows] == list(range(1, n + 1))
    assert abs(last["h2_kg_h"] - float(snap[("HB-012", "Compressor")]["value"]["h2_kg_h"])) < 1e-12
    assert abs(last["cooling_kw"] - float(snap[("EU-008", "CoolingSupply")]["value"]["demand_kw"])) < 1e-12
    assert abs(last["storage_kg"] - float(snap[("HB-013", "Storage")]["value"]["level_kg"])) < 1e-12


def test_a_feed_step_changes_the_feed_and_later_the_hydrogen_but_not_before():
    base = live_trace.run_trace(12)
    step = live_trace.run_trace(12, feed_step=(6, 50.0))
    assert [r["feed_kg_h"] for r in step[:5]] == [r["feed_kg_h"] for r in base[:5]]
    assert step[5]["feed_kg_h"] == 50.0 and base[5]["feed_kg_h"] != 50.0
    assert [r["h2_kg_h"] for r in step[:5]] == [r["h2_kg_h"] for r in base[:5]]
    assert step[-1]["h2_kg_h"] > base[-1]["h2_kg_h"]       # more feed, more hydrogen (model direction)


def test_the_app_runs_the_trace_on_the_button_only():
    st.cache_data.clear()
    with patched_supabase(FakeSupabase({"plant_state_current": smoke._store_rows()})), \
            mock.patch("urllib.request.urlopen", side_effect=smoke._offline_urlopen):
        at = AppTest.from_file(smoke.APP, default_timeout=120).run()
        assert not at.exception and "_summary_trace" not in at.session_state
        btn = [b for b in at.tabs[-1].button if b.label == "Run 30-cycle trace"]
        assert len(btn) == 1
        btn[0].click().run()
    assert not at.exception, [str(e.value)[:300] for e in at.exception]
    tr = at.session_state["_summary_trace"]
    assert len(tr) == 30 and tr[-1]["feed_kg_h"] == 50.0 and tr[0]["feed_kg_h"] != 50.0
