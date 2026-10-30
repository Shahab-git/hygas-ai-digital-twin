"""Carbon-black cards (app.py `_ga_derived_byproduct_flows`, `_ga_carbon_black_note`): the three card values show the engine's derived
carbon black when ("GA-001","CarbonAccounting") is in the snapshot and fall back to the old 5 % rule when it is absent or Missing (older snapshots).

The engine entry used here is a REAL one, built by the unchanged engine (tab1_integration.build_live_snapshot, 2 cycles) and added to the stored sample snapshot
(tests/fixtures/sample_snapshot.json, a TEST FIXTURE). Offline: counting fake store, blocked network; the app must write nothing."""
import copy
import json
import os
import runpy
import urllib.error
from unittest import mock

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from _fakes import FakeSupabase, patched_supabase
from python import gasifier_mass_balance
from python import tab1_integration as t1

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP = os.path.join(ROOT, "app.py")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "sample_snapshot.json")
KEY = ("GA-001", "CarbonAccounting")
LABEL = "⚫ Carbon black recovery (derived)"


def _fixture_rows():
    with open(FIXTURE, encoding="utf-8") as handle:
        doc = json.load(handle)
    return [{"equipment_id": e["key"][0], "category": e["key"][1], "entry": e["entry"], "cycle": 1, "published_at": "2026-09-10T00:04:00Z"} for e in doc["entries"]]


@pytest.fixture(scope="module")
def engine_entries():
    """The real CarbonAccounting and conversion-input entries from the unchanged engine (native JSON types, as the store holds them)."""
    with patched_supabase(FakeSupabase()):
        snap, _state, _engine = t1.build_live_snapshot(2)
    return {k: json.loads(json.dumps(t1._native(snap[k]))) for k in (KEY, ("GA-001-INPUT", "carbon_conversion_efficiency"))}


def _run_app(rows):
    st.cache_data.clear()
    fake = FakeSupabase({"plant_state_current": rows})
    with patched_supabase(fake), mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("network blocked in tests")):
        at = AppTest.from_file(APP, default_timeout=90).run()
    assert not at.exception, [str(e.value)[:300] for e in at.exception]
    assert [c for c in fake.calls if c[0] != "select"] == [], "the app wrote to the (fake) database"
    return at


def test_the_rendered_card_follows_the_snapshot_derived_then_fallback(engine_entries):
    feed = next(r for r in _fixture_rows() if (r["equipment_id"], r["category"]) == ("GA-001-INPUT", "dry_feed_rate_kg_h"))["entry"]["value"]
    rule = gasifier_mass_balance.byproduct_mass_flows(feed)["carbon_black_kg_h"]
    derived = engine_entries[KEY]["value"]["carbon_black_kg_h"]

    rows = _fixture_rows()
    for k in (KEY, ("GA-001-INPUT", "carbon_conversion_efficiency")):
        rows = [r for r in rows if (r["equipment_id"], r["category"]) != k]
        rows.append({"equipment_id": k[0], "category": k[1], "entry": engine_entries[k], "cycle": 1, "published_at": "2026-09-10T00:04:00Z"})
    at = _run_app(rows)
    card = [m for m in at.metric if m.label == LABEL]
    assert len(card) == 1 and card[0].value == f"{derived:.3f} kg/h", ([m.value for m in card], derived)
    text = " ".join(str(c.value) for c in at.caption)
    assert "derived from unconverted carbon (conversion 0.90, Assumed)" in text and "datasheet cross-check 1.88 kg/h" in text

    at = _run_app(_fixture_rows())
    card = [m for m in at.metric if m.label == LABEL]
    assert len(card) == 1 and card[0].value == f"{rule:.3f} kg/h", ([m.value for m in card], rule)
    assert "derived from unconverted carbon" not in " ".join(str(c.value) for c in at.caption)


# NOTE: this AppTest-based test is defined BEFORE the tests that use the runpy-loaded `app` fixture on purpose: in one process an AppTest run after a bare-mode
# runpy of app.py fails with a Streamlit form-context error (the reverse order is what tests/test_app_smoke.py -> tests/test_tab2_counts.py already does).
@pytest.fixture(scope="module")
def app():
    fake = FakeSupabase({"plant_state_current": _fixture_rows()})
    with patched_supabase(fake), mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("network blocked in tests")):
        return runpy.run_path(APP, run_name="app_under_test")


@pytest.fixture(scope="module")
def base_snapshot(app):
    snap = {(r["equipment_id"], r["category"]): app["_restore_input_tuples"](r["entry"]) for r in _fixture_rows()}
    assert KEY not in snap, "the stored sample is an older snapshot without the key"
    return snap


def _with_engine(base, entries):
    snap = copy.deepcopy(base)
    snap[KEY] = entries[KEY]
    snap[("GA-001-INPUT", "carbon_conversion_efficiency")] = entries[("GA-001-INPUT", "carbon_conversion_efficiency")]
    return snap


def test_key_present_the_derived_value_is_shown_with_its_label_and_the_datasheet_cross_check(app, base_snapshot, engine_entries):
    snap = _with_engine(base_snapshot, engine_entries)
    flows = app["_ga_derived_byproduct_flows"](snap)
    derived = engine_entries[KEY]["value"]["carbon_black_kg_h"]
    assert flows["carbon_black_kg_h"] == derived and flows["carbon_black_source"] == "engine"
    assert derived != pytest.approx(flows["carbon_black_rule_kg_h"], rel=1e-3), "the two rules differ (the whole point of the alignment)"
    note = app["_ga_carbon_black_note"](flows)
    assert "derived from unconverted carbon (conversion 0.90, Assumed)" in note, note
    ds = engine_entries[KEY]["value"]["datasheet_cross_check"]["ga008_nominal_at_old_design_scaled_kg_h"]
    assert f"datasheet cross-check {ds:.2f} kg/h" in note and "1.88 kg/h" in note
    assert flows["carbon_black_status_line"].startswith("Calculated") and "unconverted" in flows["carbon_black_status_line"], "the engine's own status line is carried"


def test_key_absent_or_missing_the_old_rule_is_shown_unchanged(app, base_snapshot, engine_entries):
    feed = base_snapshot[("GA-001-INPUT", "dry_feed_rate_kg_h")]["value"]
    rule = gasifier_mass_balance.byproduct_mass_flows(feed)
    flows = app["_ga_derived_byproduct_flows"](base_snapshot)
    assert flows["carbon_black_kg_h"] == rule["carbon_black_kg_h"] and flows["carbon_black_source"] == "5 % datasheet rule"
    assert app["_ga_carbon_black_note"](flows) == ""
    snap = _with_engine(base_snapshot, engine_entries)
    snap[KEY] = {**snap[KEY], "status": "Missing", "value": None, "missing_reason": "test: key Missing"}
    flows = app["_ga_derived_byproduct_flows"](snap)
    assert flows["carbon_black_kg_h"] == rule["carbon_black_kg_h"] and flows["carbon_black_source"] == "5 % datasheet rule"


def test_the_ash_flow_and_the_dry_feed_do_not_change(app, base_snapshot, engine_entries):
    old = app["_ga_derived_byproduct_flows"](base_snapshot)
    new = app["_ga_derived_byproduct_flows"](_with_engine(base_snapshot, engine_entries))
    assert new["ash_kg_h"] == old["ash_kg_h"] and new["dry_feed_kg_h"] == old["dry_feed_kg_h"]
    assert app["_ga_carbon_black_note"](None) == ""
