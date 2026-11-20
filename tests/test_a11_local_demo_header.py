"""P5-1 (named test_a11_ so it runs before the tests that load app.py with runpy, see test_a2_summary_tab.py): with HYGAS_LOCAL_DEMO=1 and no
reachable database the header says LOCAL DEMO and does not promise a next published tick; without the variable it says OFFLINE as before.
Offline AppTest of the real app.py (a failure injected into the fake client); nothing here shows the packaged Windows copy."""
import os
from unittest import mock

import streamlit as st
from streamlit.testing.v1 import AppTest

from _fakes import FakeSupabase, patched_supabase
import test_app_smoke as smoke


def _header(env):
    st.cache_data.clear()
    fake = FakeSupabase({}, failures={("plant_state_current", "select"): [RuntimeError("no database")] * 20})
    with mock.patch.dict(os.environ, env, clear=False), patched_supabase(fake), \
            mock.patch("urllib.request.urlopen", side_effect=smoke._offline_urlopen):
        at = AppTest.from_file(smoke.APP, default_timeout=120).run()
    assert not at.exception, [str(e.value)[:300] for e in at.exception]
    return " ".join(m.value for m in at.markdown if "SIMULATION RUNTIME" in m.value)


def test_local_demo_flag_changes_the_header_and_nothing_else_says_offline():
    h = _header({"HYGAS_LOCAL_DEMO": "1"})
    assert "LOCAL DEMO" in h and "OFFLINE" not in h and "best-effort" not in h


def test_without_the_flag_the_header_still_says_offline():
    h = _header({"HYGAS_LOCAL_DEMO": "0"})
    assert "OFFLINE" in h and "LOCAL DEMO" not in h
