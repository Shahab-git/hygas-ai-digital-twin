"""P4-1 (named test_a10_ so it runs before the tests that load app.py with runpy, see test_a2_summary_tab.py): the Summary tab's Live section
(python/live_runner.py). AppTest does not run st.fragment timers, so the periodic refresh itself is not exercised here; the button, the runner
and the rendered values are. Offline AppTest of the real app.py; nothing here shows a deployed app."""
import sys
from unittest import mock

import streamlit as st
from streamlit.testing.v1 import AppTest
from _fakes import FakeSupabase, patched_supabase
import test_app_smoke as smoke

sys.path.insert(0, smoke.ROOT)


def _run(click=False):
    st.cache_data.clear()
    with patched_supabase(FakeSupabase({"plant_state_current": smoke._store_rows()})), \
            mock.patch("urllib.request.urlopen", side_effect=smoke._offline_urlopen):
        at = AppTest.from_file(smoke.APP, default_timeout=120).run()
        if click:
            next(b for b in at.button if b.key == "_live_toggle").click().run()
    assert not at.exception, [str(e.value)[:300] for e in at.exception]
    return at


def test_live_section_starts_stopped_and_labelled_simulated():
    at = _run()
    text = " ".join(c.value for c in at.caption)
    assert "SIMULATED" in text and "not the published hourly runtime" in text
    assert [b.label for b in at.button if b.key == "_live_toggle"] == ["Start live run"]
    assert any("Not started" in i.value for i in at.info)


def test_start_runs_one_cycle_and_shows_the_live_label_and_metrics():
    at = _run(click=True)
    assert at.session_state["_live_running"] is True
    assert [b.label for b in at.button if b.key == "_live_toggle"] == ["Stop live run"]
    md = " ".join(m.value for m in at.markdown)
    assert "LIVE - SIMULATED" in md and "cycle 1" in md
    assert "Cooling demand" in " ".join(m.label for m in at.metric)
