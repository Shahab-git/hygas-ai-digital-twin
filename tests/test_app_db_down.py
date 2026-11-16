"""STAB-1: the Streamlit app must survive an unreachable quote-log database.

Before this change `vendor_log.load_quotes()` (app.py, Vendor Sourcing section of Tab 1) was
unguarded: with no Supabase secrets or no network it raised and Streamlit stopped the script
there, so no later tab was drawn. These tests run the REAL app.py through AppTest, offline,
with the quote table failing (a failure injected into the fake client, not a real outage).

What is NOT shown here: the deployed app (it has secrets); this checks the failure path only.
"""
import os
from unittest import mock

import streamlit as st
from streamlit.testing.v1 import AppTest

from _fakes import FakeSupabase, patched_supabase
import test_app_smoke as smoke

APP = smoke.APP


def _run(fake):
    st.cache_data.clear()
    with patched_supabase(fake), mock.patch("urllib.request.urlopen", side_effect=smoke._offline_urlopen):
        return AppTest.from_file(APP, default_timeout=90).run()


def test_quote_table_unreachable_does_not_stop_the_other_tabs():
    fake = FakeSupabase({"plant_state_current": smoke._store_rows()},
                        failures={("vendor_quotes", "select"): [RuntimeError("Missing secret 'SUPABASE_URL'")] * 5})
    at = _run(fake)
    assert not at.exception, [str(e.value)[:300] for e in at.exception]
    labels = [t.label for t in at.tabs]
    assert len(labels) == 11 and labels[-1] == "Transient What-If", labels
    # the later tabs really rendered (Tab 2 counters exist), not just declared
    assert [m for m in at.metric if m.label == "🔴 Design findings"], "Tab 2 did not render after the vendor section"
    warnings = " ".join(str(w.value) for w in at.warning)
    assert "Quote log unavailable" in warnings
    assert [c for c in fake.calls if c[0] != "select"] == [], "the app wrote to the (fake) database"


def test_logging_is_disabled_while_the_database_is_down():
    fake = FakeSupabase({"plant_state_current": smoke._store_rows()},
                        failures={("vendor_quotes", "select"): [RuntimeError("down")] * 5})
    at = _run(fake)
    buttons = [b for b in at.button if b.label == "Log quote"]
    assert len(buttons) == 1 and buttons[0].disabled is True


def test_the_normal_path_is_unchanged_when_the_database_works():
    fake = FakeSupabase({"plant_state_current": smoke._store_rows()})
    at = _run(fake)
    assert not at.exception, [str(e.value)[:300] for e in at.exception]
    assert "Quote log unavailable" not in " ".join(str(w.value) for w in at.warning)
    buttons = [b for b in at.button if b.label == "Log quote"]
    assert len(buttons) == 1 and buttons[0].disabled is False
