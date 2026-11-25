"""Tour and design-finding data for the 3D tab (python/plant_3d_story.py): every number is the snapshot's own, every id is a registry id,
the wording asks questions and never claims a measurement or a fault of the plant, and the page carries the data without a network request."""
import json
import os
import re

import pytest

from python import plant_3d, plant_3d_story, summary_tab, tab1_integration

ROOT = os.path.join(os.path.dirname(__file__), "..")


@pytest.fixture(scope="module")
def snap():
    s, _state, _engine = tab1_integration.build_live_snapshot()
    return s


@pytest.fixture(scope="module")
def story(snap):
    return plant_3d_story.story_data(snap)


def _text(story):
    return " ".join(l for st in story["tour"] + story["findings"] for l in st["lines"] + [st.get("ask", ""), st["title"]])


def test_every_item_id_named_is_in_the_registry(story):
    names = plant_3d.registry_names()
    for f in story["findings"]:
        assert f["items"] and all(i in names for i in f["items"]), f
    for st in story["tour"]:
        assert all(i in names for i in st["focus"]), st


def test_the_numbers_are_the_snapshots_own(snap, story):
    sm = summary_tab.summary_data(snap)
    text = _text(story)
    assert "%.1f kg/day" % sm["h2_kg_day"] in text
    assert "about %.0f kW" % sm["cooling"]["demand_kw"] in text and "%.0f kW" % sm["cooling"]["rating_kw"] in text
    n2 = float(snap[("GA-001", "Outputs")]["value"]["N2_mol_pct_dry"])
    assert "%.1f vol%%" % n2 in text
    assert "%d of %d published values are Measured" % (sm["counts"].get("Measured", 0), sm["total"]) in text


def test_the_wording_asks_and_never_claims_a_measurement_or_a_plant_fault(story):
    assert len(story["findings"]) == 4 and all(f["ask"].strip() for f in story["findings"])
    text = _text(story).lower()
    for bad in ("is undersized", "is wrong", "confirmed", "measured value", "verified pipe"):
        assert bad not in text, bad
    cooling = next(f for f in story["findings"] if f["id"] == "cooling")
    assert "unverified (registry)" in " ".join(cooling["lines"]).lower()
    assert "EU-004" in " ".join(cooling["lines"])


def test_the_story_is_json_and_the_page_carries_it(story):
    json.dumps(story)
    items = plant_3d.scene_items([{"id": i, "group": i[:2], "state": "running_live"} for i in plant_3d.registry_names()])
    html = plant_3d.build_html(items, story=story)
    assert '"story"' in html and "Cooling capacity" in html
    assert plant_3d.build_html(items, story=None).count('"story": null') == 1


def test_the_bundle_has_the_tour_and_findings_buttons_and_no_network_call():
    with open(os.path.join(ROOT, "assets", "plant3d.bundle.js"), encoding="utf-8") as fh:
        b = fh.read()
    for s in ("Design findings: ", "Tour", "Question for DOK-ING"):
        assert s in b, s
    with open(os.path.join(ROOT, "web3d", "src", "main.js"), encoding="utf-8") as fh:
        src = fh.read()
    assert "fetch(" not in src and not re.search(r"XMLHttpRequest|WebSocket|sendBeacon", src)
    with open(os.path.join(ROOT, "python", "plant_3d_story.py"), encoding="utf-8") as fh:
        assert "fetch(" not in fh.read()


def test_the_heat_finding_has_no_number_and_the_module_does_not_read_the_read_only_heat_report():
    with open(os.path.join(ROOT, "python", "plant_3d_story.py"), encoding="utf-8") as fh:
        src = fh.read()
    assert not re.search(r"plant_heat_integration|HeatIntegration", src)      # tests/test_plant_heat_integration.py: nobody else reads that key
    story = plant_3d_story.story_data({})
    heat = next(f for f in story["findings"] if f["id"] == "heat")
    assert not re.search(r"\d", " ".join(heat["lines"]))
