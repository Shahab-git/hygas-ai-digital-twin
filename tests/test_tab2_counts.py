"""Audit fix J4: Tab 2's categories sum to 91 on a stored sample snapshot, and its
other display helpers (fault events, staleness, finding text, schematic badges,
keep-alive line) behave as specified.

The snapshot is tests/fixtures/sample_snapshot.json -- a TEST FIXTURE (trimmed
copy of an offline simulated run), not plant data. app.py is executed through
runpy in Streamlit's bare mode with a fake Supabase client and blocked network
(weather / GitHub), i.e. the real production code path, nothing mocked inside it.
"""
import json
import os
import runpy
import urllib.error
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from _fakes import FakeSupabase, patched_supabase

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "sample_snapshot.json")


def _fixture_rows():
    with open(FIXTURE, encoding="utf-8") as handle:
        doc = json.load(handle)
    assert "TEST FIXTURE" in doc["_comment"]
    return [{"equipment_id": e["key"][0], "category": e["key"][1], "entry": e["entry"], "cycle": 1,
             "published_at": "2026-09-10T00:04:00Z"} for e in doc["entries"]]


@pytest.fixture(scope="module")
def app():
    fake = FakeSupabase({"plant_state_current": _fixture_rows()})
    blocked = urllib.error.URLError("network blocked in tests")
    with patched_supabase(fake), mock.patch("urllib.request.urlopen", side_effect=blocked):
        namespace = runpy.run_path(os.path.join(ROOT, "app.py"), run_name="app_under_test")
    assert not [c for c in fake.calls if c[0] != "select"], "app.py wrote to the (fake) database"
    return namespace


@pytest.fixture(scope="module")
def snapshot(app):
    restore = app["_restore_input_tuples"]
    return {(r["equipment_id"], r["category"]): restore(r["entry"]) for r in _fixture_rows()}


def test_categories_sum_to_91(app, snapshot):
    counts, total = app["_plant_overview_status_counts"](snapshot)
    assert total == 91
    assert set(counts) == {"running_live", "running_assumed", "static", "missing", "fault"}
    assert sum(counts.values()) == 91, counts
    # the sample reproduces the audited split: 55 live + 12 assumed-only = 67 "running"
    assert counts["running_live"] + counts["running_assumed"] == 67
    assert counts["running_assumed"] == 12


def test_one_fault_event_marks_two_items(app, snapshot):
    info = app["_plant_overview_fault_events"](snapshot)
    counts, _ = app["_plant_overview_status_counts"](snapshot)
    assert info["n_events"] == 1 and info["events"] == [("AI-004", "EU-009-State")]
    assert info["affected_items"] == ["EU-009", "AI-004"]
    assert counts["fault"] == 2          # two ITEMS, one EVENT


def test_compact_schematic_marks_eu_fault_from_the_same_states(app, snapshot):
    items = app["_plant_overview_item_states"](snapshot)
    assert len(items) == 91
    assert app["_plant_overview_group_badge"](items, "EU")[2] == "FAULT"
    assert app["_plant_overview_group_badge"](items, "FE")[2] == "Running"
    assert app["_plant_overview_group_badge"](items, "HB")[2].endswith("missing")
    svg = app["_plant_overview_compact_svg"](snapshot)
    assert ">FAULT<" in svg


def test_missing_caption_lists_equipment_with_any_missing_entry(app, snapshot):
    ids = app["_plant_overview_missing_equipment_ids"](snapshot)
    assert len(ids) == 11 and "FE-002" in ids and "AI-002" in ids


def test_finding_text_has_no_literal_markdown(app, snapshot):
    for finding in app["_plant_overview_active_findings"](snapshot):
        html = app["_plant_overview_md_to_html"](finding["detail"])
        assert "**" not in html and "`" not in html, finding["id"]
    assert app["_plant_overview_md_to_html"]("a **FAULT** b `x` <c>") == "a <b>FAULT</b> b <code>x</code> &lt;c&gt;"


@pytest.mark.parametrize("age,level", [(None, "unknown"), (0.5, "fresh"), (2.0, "fresh"), (2.01, "stale"),
                                        (5.9, "stale"), (6.0, "stale"), (6.01, "very_stale")])
def test_freshness_levels(app, age, level):
    assert app["_freshness_level"](age) == level


def test_keepalive_warning_after_45_days(app):
    now = datetime(2026, 10, 27, tzinfo=timezone.utc)
    assert app["_keepalive_warning"]((now - timedelta(days=45)).isoformat(), now) is None
    text = app["_keepalive_warning"]("2026-09-08T18:01:29Z", now)
    assert text and "2026-11-07" in text
    assert app["_keepalive_warning"](None, now) is None
