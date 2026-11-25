"""Simulation tab, device picker (python/ui_simulation_tab.py): offline, on the live engine, no writes."""
import os
import re

import pytest

from python import ui_simulation_tab as u

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEED = ("FE-001-INPUT", "msw_delivery_rate_kg_h")


@pytest.fixture(scope="module")
def ids():
    return {i for i, _n, _c in u.registry_items()}


@pytest.fixture(scope="module")
def base(ids):
    return u.run_snapshot({}, ids)


def test_the_picker_lists_all_91_items_once(ids):
    items = u.registry_items()
    assert len(items) == 91 and len(ids) == 91


def test_defaults_build_no_override_and_the_default_scenario_has_zero_delta(ids, base):
    assert u.build_overrides({}, u.TAIL_GAS_DEFAULT) == {}
    again = u.run_snapshot(u.build_overrides({}, u.TAIL_GAS_DEFAULT), ids)
    for i in sorted(ids):
        for r in u.item_table(base, again, i):
            assert r["delta"] in (None, 0.0), (i, r)


def test_a_feed_step_changes_an_item_downstream_of_the_feed(ids, base):
    scen = u.run_snapshot(u.build_overrides({FEED: 50.0}, u.TAIL_GAS_DEFAULT), ids)
    rows = [r for r in u.item_table(base, scen, "FE-005") if r["key"].endswith("dry_solids_kg_h")]
    assert rows and rows[0]["delta"] > 5.0


def test_items_without_a_live_key_are_marked_no_model(ids, base):
    nokey = sorted(i for i in ids if not u.item_keys(base, i))
    assert nokey and "GA-002" in nokey
    assert all(u.item_table(base, None, i) == [] for i in nokey)


def test_no_temperature_input_and_no_heat_report_and_no_writes():
    src = open(os.path.join(HERE, "python", "ui_simulation_tab.py"), encoding="utf-8").read()
    assert "operating_temperature" not in "".join(k[1] for k in u.SCENARIO_INPUTS)
    assert "HeatIntegration" not in src.replace("plant heat report", "") and "plant_heat_integration" not in src
    assert not re.search(r"\.open\(|write_text|supabase|requests\.|urlopen|to_csv|\"w\"", src)
