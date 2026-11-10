"""HB-010 Separation (Phase 1 task P1-12): the one persisted entry that deliberately differs from the 701de71 fixture (tests/_intentional_changes.py).

Pins: it is an intentional exception (P1-05(a) added two others); the fixture still says Missing; the live entry is Estimated, inherits from Feed and SelectivityEstimate, holds the recovery at the registry
85 % (not computed), derives the purity from the selectivity range at the live feed H2 (independent re-derivation), keeps the purity low <= used <= high, and nothing reads it."""
import gzip
import json
import os

import pytest

from _fakes import FakeSupabase, patched_supabase
from _intentional_changes import INTENTIONAL
from python import hb_remaining_chain as hbrem
from python import plant_status as ps
from python import tab1_integration as t1

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "snapshot_origin_main_701de71.json.gz")


@pytest.fixture(scope="module")
def snap():
    with patched_supabase(FakeSupabase()):
        return t1.build_live_snapshot(20)[0]


def test_it_is_the_only_intentional_exception_and_the_fixture_still_says_missing():
    assert "HB-010|Separation" in INTENTIONAL                      # P1-05(a) added two more; test_p1_05a_h2_lhv.py pins those
    with gzip.open(FIXTURE, "rb") as fh:
        old = json.loads(fh.read().decode("utf-8"))["default|20"]["HB-010|Separation"]
    assert old["status"] == "Missing" and old["value"] is None


def test_the_live_entry_is_estimated_with_declared_inputs_and_a_held_recovery(snap):
    e = snap[("HB-010", "Separation")]
    assert e["status"] == ps.STATUS_ESTIMATED
    assert [tuple(k) for k in e["source"]["inputs"]] == [("HB-010", "Feed"), ("HB-010", "SelectivityEstimate")]
    v = e["value"]
    assert v["recovery"] == hbrem.HB010_CONFIRMED_RECOVERY == 0.85 and "not computed" in v["recovery_basis"]
    assert "stage cut" in v["not_modelled"] and "Estimated" in e["confidence_note"] and "not validated" in e["confidence_note"]


def test_the_purity_is_the_stated_relation_at_the_live_feed(snap):
    v = snap[("HB-010", "Separation")]["value"]
    x = snap[("HB-010", "Feed")]["value"]["feed_composition"]["y_H2"]
    lo, hi = snap[("HB-010", "SelectivityEstimate")]["value"]["digital_twin_engineering_baseline_range"]
    pur = lambda a: (a * x / (1 - x)) / (1 + a * x / (1 - x))
    assert v["permeate_h2_purity"] == pytest.approx(pur((lo + hi) / 2), rel=1e-12)
    assert v["permeate_h2_purity_range"][0] == pytest.approx(pur(lo), rel=1e-12) and v["permeate_h2_purity_range"][1] == pytest.approx(pur(hi), rel=1e-12)
    assert v["permeate_h2_purity_range"][0] < v["permeate_h2_purity"] < v["permeate_h2_purity_range"][1] < 1.0
    assert v["product_h2_flow_nm3_h"] == pytest.approx(0.85 * hbrem.HB010_FEED_FLOW_NM3_H * x, rel=1e-12)
    assert v["permeate_flow_nm3_h"] == pytest.approx(v["product_h2_flow_nm3_h"] / v["permeate_h2_purity"], rel=1e-12)


def test_no_registered_model_depends_on_it():
    from python import ledger_consumers as lcons
    assert lcons.declared_readers().get(("HB-010", "Separation"), []) == []
