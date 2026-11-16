"""STAB-2: the app shows one standing SIMULATED banner above the tabs, with a Measured count
computed from the published snapshot (not a typed constant).

Offline AppTest runs of the REAL app.py with the fake store from test_app_smoke. The Measured
count is cross-checked against the fixture rows themselves. Nothing here shows the deployed app.
"""
import re
from unittest import mock

import streamlit as st
from streamlit.testing.v1 import AppTest

from _fakes import FakeSupabase, patched_supabase
import test_app_smoke as smoke


def _run(fake):
    st.cache_data.clear()
    with patched_supabase(fake), mock.patch("urllib.request.urlopen", side_effect=smoke._offline_urlopen):
        return AppTest.from_file(smoke.APP, default_timeout=90).run()


def measured_in_store(rows):
    return sum(1 for r in rows if r["entry"].get("status") == "Measured")


def _banners(at):
    return [str(m.value) for m in at.markdown if "sim-banner" in str(m.value)]


def test_one_banner_with_a_count_that_matches_the_store():
    rows = smoke._store_rows()
    at = _run(FakeSupabase({"plant_state_current": rows}))
    assert not at.exception, [str(e.value)[:300] for e in at.exception]
    banners = _banners(at)
    assert len(banners) == 1, len(banners)
    assert "SIMULATED" in banners[0] and "no measurements from the plant yet" in banners[0] and measured_in_store(rows) == 0
    measured = measured_in_store(rows)
    m = re.search(r"(\d+) of (\d+) published values are Measured", banners[0])
    assert m, banners[0]
    assert int(m.group(1)) == measured and int(m.group(2)) == len(rows)


def test_banner_still_shows_when_the_store_is_unreachable():
    at = _run(FakeSupabase({}, missing_tables=("plant_state_current",)))
    assert not at.exception, [str(e.value)[:300] for e in at.exception]
    assert len(_banners(at)) == 1


def test_banner_counts_a_measured_entry_when_one_exists():
    rows = smoke._store_rows()
    rows[0]["entry"] = dict(rows[0]["entry"], status="Measured")
    at = _run(FakeSupabase({"plant_state_current": rows}))
    measured = sum(1 for r in rows if r["entry"].get("status") == "Measured")
    assert measured >= 1
    banner = _banners(at)[0]
    assert f"{measured} of {len(rows)} published values are Measured" in banner
    # the lead sentence must follow the count: with a Measured value it may NOT claim "no measurements"
    assert "no measurements from the plant yet" not in banner and "Model results plus some Measured values" in banner
    assert "the rest are model results" not in banner
