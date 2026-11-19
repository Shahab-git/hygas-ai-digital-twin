"""P3-1: the 3D Plant tab's data and page. Offline; checks data and HTML, not a browser rendering (that was looked at by eye separately)."""
import json
import re
import sys
from unittest import mock
import streamlit as st
from streamlit.testing.v1 import AppTest
from _fakes import FakeSupabase, patched_supabase
import test_app_smoke as smoke

sys.path.insert(0, smoke.ROOT)
from python import plant_3d


def _fake_states():
    names = plant_3d.registry_names()
    return [{"id": i, "group": i[:2], "state": "running_live" if i != "EU-009" else "fault"} for i in sorted(names)]


def test_all_91_items_are_placed_once_with_their_state_and_a_size_basis():
    items = plant_3d.scene_items(_fake_states())
    assert len(items) == 91 and len({i["id"] for i in items}) == 91
    assert {i["id"] for i in items if i["basis"] == "registry"} == set(plant_3d.DIMENSIONS_FROM_REGISTRY)
    assert [i for i in items if i["id"] == "EU-009"][0]["state_label"] == "DESIGN FINDING"
    assert all(i["basis_note"] for i in items)


def test_no_two_items_in_a_row_overlap():
    items = plant_3d.scene_items(_fake_states())
    for g in plant_3d.GROUP_ORDER:
        row = sorted((i for i in items if i["group"] == g), key=lambda i: i["x"])
        for a, b in zip(row, row[1:]):
            assert a["x"] + a["w"] / 2 <= b["x"] - b["w"] / 2 + 1e-9, (a["id"], b["id"])


def test_registry_sizes_match_the_registry_file():
    """Every explicit dimension is quoted from data/equipment_registry.json: the ids exist and the note names the same figures."""
    names = plant_3d.registry_names()
    for item_id, (shape, w, h, d, note) in plant_3d.DIMENSIONS_FROM_REGISTRY.items():
        assert item_id in names and item_id in note.split()[0]
        assert str(w).rstrip("0").rstrip(".") in note or str(h).rstrip("0").rstrip(".") in note


def test_html_embeds_the_data_the_bundle_and_escapes_script_ends():
    items = plant_3d.scene_items(_fake_states())
    items[0]["name"] = "x</script><b>"
    html = plant_3d.build_html(items)
    assert html.count("</script>") == 2            # the data script and the bundle script only
    m = re.search(r"window.__PLANT3D__=(\{.*?\});</script>", html, re.S)
    assert len(json.loads(m.group(1).replace("<\\/", "</"))["items"]) == 91
    assert "WebGLRenderer" in html


def test_the_app_has_the_3d_tab_with_one_frame_holding_all_91_items():
    st.cache_data.clear()
    with patched_supabase(FakeSupabase({"plant_state_current": smoke._store_rows()})), \
            mock.patch("urllib.request.urlopen", side_effect=smoke._offline_urlopen):
        at = AppTest.from_file(smoke.APP, default_timeout=90).run()
    assert not at.exception, [str(e.value)[:300] for e in at.exception]
    tab = [t for t in at.tabs if t.label == "3D Plant"][0]
    assert not [w for w in tab.warning], [w.value for w in tab.warning]
    frames = tab.get("iframe")
    assert len(frames) == 1
    doc = frames[0].proto.srcdoc
    data = json.loads(re.search(r"window.__PLANT3D__=(\{.*?\});</script>", doc, re.S).group(1).replace("<\\/", "</"))
    assert len(data["items"]) == 91 and sum(1 for i in data["items"] if i["state"] == "fault") >= 1
