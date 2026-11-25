"""Simulation tab, per-section results (python/sim_sections.py, LiveRunner.section_history, ui_simulation_tab.render_section)."""
import os

import pytest

from python import live_runner, sim_sections as ss, tab1_integration as t1

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def snap():
    return t1.build_live_snapshot(4)[0]


def test_every_series_resolves_to_the_snapshot_value(snap):
    for section, (_prefixes, series) in ss.SECTIONS.items():
        got = ss.extract(snap, section)
        for label, item, cat, path, _u in series:
            assert got[label] is not None, (section, label)
            v = snap[(item, cat)]["value"]
            for part in (path.split(".") if path else []):
                v = v[part]
            assert got[label] == float(v)


def test_series_stay_inside_their_section_and_no_plant_key_is_read():
    for section, (prefixes, series) in ss.SECTIONS.items():
        assert all(item[:2] in prefixes for _l, item, *_r in series), section
    src = open(os.path.join(HERE, "python", "sim_sections.py"), encoding="utf-8").read()
    assert "PLANT" not in src.replace("PLANT key", "") and "plant_heat_integration" not in src and "HeatIntegration" not in src


def test_live_runner_records_the_section_series_and_leaves_the_rows_alone():
    r = live_runner.LiveRunner()
    row = r.tick()
    assert len(r.section_history) == 1 and r.section_history[0]["cycle"] == 1
    assert set(r.section_history[0]) == {"cycle", *ss.SECTIONS}
    assert r.section_history[0]["Feed Handling"]["As-received feed (kg/h)"] == row["feed_kg_h"]
