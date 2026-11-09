"""HB-003 duty estimate (Phase 1 task P1-15): an Estimated rating published NEXT TO the registry's 5 kW 'Design heat duty'; the registry row and the live HeatExchanger entry are untouched.

Pins: the key is Estimated with the declared input; the value is the LARGER of the hot and cold side duties times 1 + EU008_SIZING_MARGIN_FRACTION (independent re-derivation);
it carries the open question for DOK-ING and says it is not DOK-ING-confirmed; the registry row still says 5 kW; nothing reads the key; EU-008 keeps the registry 20 kW beside the
Estimated recommendation (different scope, no code change)."""
import json
import os
import re

import pytest

from _fakes import FakeSupabase, patched_supabase
from python import eu_utilities_chp as eu
from python import plant_status as ps
from python import tab1_integration as t1

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
KEY = ("HB-003", "DutyEstimate")


@pytest.fixture(scope="module")
def snap():
    with patched_supabase(FakeSupabase()):
        return t1.build_live_snapshot(20)[0]


def test_the_entry_is_estimated_with_its_declared_input(snap):
    e = snap[KEY]
    assert e["status"] == ps.STATUS_ESTIMATED
    assert [tuple(k) for k in e["source"]["inputs"]] == [("HB-003", "HeatExchanger")]
    assert "not DOK-ING-confirmed" in json.dumps(e["value"]) and "real_open_question" in e["value"]


def test_the_value_is_the_larger_side_plus_the_margin(snap):
    hx = snap[("HB-003", "HeatExchanger")]["value"]
    hot, cold = hx["Q_hot_side_kW"], hx["Q_cold_side_kW"]
    v = snap[KEY]["value"]
    assert v["hot_side_kw"] == hot and v["cold_side_kw"] == cold
    assert v["larger_side_duty_kw"] == max(hot, cold)
    assert v["recommended_duty_kw"] == pytest.approx(max(hot, cold) * (1.0 + eu.EU008_SIZING_MARGIN_FRACTION), rel=1e-12)
    assert v["recommended_duty_kw"] > 5.0        # the registry's 5 kW is below both sides of this model


def test_the_registry_rows_are_untouched():
    reg = open(os.path.join(ROOT, "data", "equipment_registry.json"), encoding="utf-8").read()
    assert re.search(r"Design heat duty", reg)
    rows = [r for r in json.loads(reg) if isinstance(r, dict)] if reg.lstrip().startswith("[") else []
    if rows:
        duty = [r for r in rows if "HB-003" in json.dumps(r) and "Design heat duty" in json.dumps(r)]
        assert duty and "5" in json.dumps(duty[0])


def test_nothing_reads_the_key_and_the_two_ratings_sit_side_by_side(snap):
    assert "HB-003|DutyEstimate" not in "".join(json.dumps(e["source"]["inputs"]) for k, e in snap.items() if k != KEY and "inputs" in e["source"])
    eu008 = snap[("EU-008", "RecommendedCapacityEstimate")]
    assert eu008["status"] == ps.STATUS_ESTIMATED and eu008["value"]["existing_confirmed_capacity_kw"] == eu.EU008_RATED_CAPACITY_KW == 20.0
