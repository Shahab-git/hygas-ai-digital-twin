"""BL-3: documented links, their routing, and the claims the model makes about them. No Blender needed."""
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "blender"))
sys.path.insert(0, ROOT)
os.environ.setdefault("HYGAS_ALLOW_DB_WRITES", "0")
import plant_layout as L  # noqa: E402
import plant_links as K  # noqa: E402


def test_the_link_file_equals_the_live_engine_dependency_graph():
    """Every drawn link is an engine depends_on edge between two physical items, and no such edge is missing."""
    assert K.derive_from_engine() == sorted(K.load_links())


def test_links_only_join_physical_registry_items_and_are_not_instruments_or_software():
    ids = {i["id"] for i in L.build_layout()}
    for a, b in K.load_links():
        assert a in ids and b in ids and a != b
        assert a in K.PHYSICAL_IDS and b in K.PHYSICAL_IDS
        assert not a.startswith(("SA-", "AI-")) and not b.startswith(("SA-", "AI-"))
        assert a not in L.NON_PHYSICAL and b not in L.NON_PHYSICAL


def test_the_link_file_says_a_link_is_not_a_verified_pipe():
    doc = json.load(open(K.LINKS_JSON, encoding="utf-8"))
    assert "NOT a verified pipe" in doc["note"] and doc["source"].endswith("depends_on")


def test_routes_are_deterministic_and_start_and_end_on_the_two_items():
    lay = L.build_layout()
    r1, r2 = K.route_all(lay), K.route_all(lay)
    assert r1 == r2 and len(r1) == len(K.load_links())
    by = {i["id"]: i for i in lay}
    for r in r1:
        a, b = by[K._host(r["from"], L.TAG_OF)], by[K._host(r["to"], L.TAG_OF)]
        p, q = r["points"][0], r["points"][-1]
        assert abs(p[0] - a["x"]) <= a["w"] / 2 + 0.2 and abs(q[0] - b["x"]) <= b["w"] / 2 + 0.2, (r["from"], r["to"])
        assert len(r["points"]) >= 2


def test_no_pipe_segment_passes_through_equipment_it_is_not_connected_to():
    lay = L.build_layout()
    boxes = {i["id"]: K._box(i) for i in lay if not i["tag_of"] and i["id"] not in L.NON_PHYSICAL}
    for r in K.route_all(lay):
        for p, q in zip(r["points"], r["points"][1:]):
            for k, box in boxes.items():
                assert not K.segment_hits_box(p, q, box), (r["from"], r["to"], k)


def test_pipe_supports_do_not_stand_inside_any_equipment_footprint():
    lay = L.build_layout()
    boxes = [K._box(i) for i in lay if not i["tag_of"] and i["id"] not in L.NON_PHYSICAL]
    for r in K.route_all(lay):
        for (x, y, _z) in r["supports"]:
            assert not any(b[0] < x < b[2] and b[1] < y < b[3] for b in boxes)


def test_the_generator_marks_links_as_model_dependencies_with_assumed_routing():
    src = open(os.path.join(ROOT, "blender", "generate_plant.py"), encoding="utf-8").read()
    assert "model dependency (engine depends_on), not a verified pipe" in src and '"schematic, assumed"' in src


def test_overhead_runs_sit_on_the_rack_tiers_except_where_an_end_item_is_taller():
    lay = L.build_layout()
    by = {i["id"]: i for i in lay}
    top = K.RACK_Z + K.LEVEL * (K.TIERS - 1)
    for r in K.route_all(lay):
        if r["kind"] != "overhead":
            continue
        zr = max(p[2] for p in r["points"])
        ends = max(K._box(by[K._host(r[e], L.TAG_OF)])[4] for e in ("from", "to")) + 0.5
        assert K.RACK_Z - 1e-9 <= zr <= max(top, ends) + 1e-9, (r["from"], r["to"], zr)


def test_a_detour_never_leaves_the_pad_corridor_more_than_the_largest_offset():
    lay = L.build_layout()
    by = {i["id"]: i for i in lay}
    for r in K.route_all(lay):
        ys = [p[1] for p in r["points"]]
        lo = min(by[K._host(r["from"], L.TAG_OF)]["y"], by[K._host(r["to"], L.TAG_OF)]["y"])
        hi = max(by[K._host(r["from"], L.TAG_OF)]["y"], by[K._host(r["to"], L.TAG_OF)]["y"])
        assert lo - max(map(abs, K.DETOUR)) - 0.3 <= min(ys) and max(ys) <= hi + max(map(abs, K.DETOUR)) + 0.3
