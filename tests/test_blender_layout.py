"""Stage 1 of the Blender plant model: the layout is pure Python, so it is tested here without Blender (CI has no bpy).
The bpy generator itself (blender/generate_plant.py) is checked by running it; its own validate_scene asserts 91 assemblies."""
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "blender"))
import plant_layout as L  # noqa: E402


def test_all_91_registry_items_are_placed_once_with_their_registry_name_and_category():
    lay = L.build_layout()
    reg = {r["id"]: r for r in L.load_registry()}
    assert len(lay) == 91 and {i["id"] for i in lay} == set(reg)
    for it in lay:
        assert it["name"] == reg[it["id"]]["name"] and it["category"] == reg[it["id"]]["category"]


def test_validate_passes_no_overlap_inside_the_site_and_deterministic():
    summary = L.validate()
    assert summary["items"] == 91 and len(summary["zones"]) == 7
    assert json.dumps(L.build_layout(), sort_keys=True) == json.dumps(L.build_layout(), sort_keys=True)


def test_registry_stated_sizes_are_used_and_labelled_and_everything_else_is_labelled_assumed():
    by = {i["id"]: i for i in L.build_layout()}
    assert (by["GA-001"]["w"], by["GA-001"]["h"], by["GA-001"]["size_basis"]) == (0.6, 4.0, "registry")
    assert by["GC-004"]["size_basis"] == by["GC-008"]["size_basis"] == by["GC-006"]["size_basis"] == "registry"
    assert by["FE-003"]["w"] == 3.0 and by["FE-003"]["size_basis"] == "registry"
    assert {i["size_basis"] for i in by.values()} <= {"registry", "estimate", "assumed"}
    assert by["EU-007"]["size_basis"] == "assumed" and "no vendor" in by["EU-007"]["size_note"]


def test_tags_and_non_physical_items_are_declared_not_hidden():
    by = {i["id"]: i for i in L.build_layout()}
    assert by["GA-002"]["tag_of"] == "GA-001" and "assumption" in by["GA-002"]["geometry_status"]
    assert by["AI-010"]["geometry_status"].startswith("non-physical placeholder")
    assert all(by[t]["tag_of"] for t in L.TAG_OF)


def test_no_connection_data_is_invented():
    """The registry has no connection fields; the layout must not claim any (stage 3 draws only documented chains)."""
    keys = set().union(*[set(i) for i in L.build_layout()])
    assert not any("connect" in k or "upstream" in k or "downstream" in k for k in keys)


def test_the_assumptions_doc_is_current():
    with open(os.path.join(ROOT, "docs", "blender_plant_assumptions.md"), encoding="utf-8") as fh:
        assert fh.read() == L.assumptions_markdown(), "run: python blender/plant_layout.py --write-docs"
