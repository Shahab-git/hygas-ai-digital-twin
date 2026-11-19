"""P3-3: shapes drawn from a registry COUNT or VOLUME. The counts must equal the registry rows, the footprint must stay labelled as an
estimate, and the JS table must cover exactly these items. Reads the registry JSON and the JS source as text; nothing renders a scene."""
import json
import math
import os
import re
import sys

import test_app_smoke as smoke

sys.path.insert(0, smoke.ROOT)
from python import plant_3d

SRC = open(os.path.join(smoke.ROOT, "web3d", "src", "main.js"), encoding="utf-8").read()
REG = {i["id"]: i for i in json.load(open(os.path.join(smoke.ROOT, "data", "equipment_registry.json"), encoding="utf-8"))}


def _value(item_id, parameter):
    return next(p["value"] for p in REG[item_id]["parameters"] if p["parameter"] == parameter)


def test_counts_equal_the_registry_rows():
    rows = {"HB-006": "Number of adsorber vessels", "HB-013": "Number of vessels", "HB-010": "Number of membrane modules",
            "HB-012": "Number of stages", "GC-010": "Number of bags", "GC-003": "Number of cyclones (parallel)",
            "FE-004": "Number of rotors"}
    for item_id, parameter in rows.items():
        stated = int(re.match(r"\d+", _value(item_id, parameter)).group())
        assert plant_3d.COUNTS_FROM_REGISTRY[item_id][0] == stated, item_id


def test_volume_items_reproduce_the_registry_volume_and_stay_estimates():
    for item_id, litres, ratio, n in (("GC-012", 50.0, 3.0, 1), ("HB-014", 500.0, 2.0, 1), ("HB-015", 1000.0, 1.5, 2)):
        _, w, h, d = plant_3d.ESTIMATE_OVERRIDES[item_id]
        dia = w if item_id != "HB-015" else d
        assert abs(math.pi * dia * dia / 4 * dia * ratio * 1000 - litres) < litres * 0.01, item_id
    assert _value("GC-012", "Carbon bed volume") == "50" and _value("HB-014", "Reactor volume") == "0.5"
    assert _value("HB-015", "Lean carrier tank volume") == "1" and _value("HB-015", "Rich carrier tank volume") == "1"


def test_scene_marks_them_estimate_with_count_and_disjoint_from_registry_sized_items():
    assert not set(plant_3d.COUNTS_FROM_REGISTRY) & set(plant_3d.DIMENSIONS_FROM_REGISTRY)
    states = [{"id": i, "group": i[:2], "state": "static"} for i in REG]
    by_id = {s["id"]: s for s in plant_3d.scene_items(states, names={i: i for i in REG})}
    for item_id, (n, _, _) in plant_3d.COUNTS_FROM_REGISTRY.items():
        assert by_id[item_id]["basis"] == "estimate" and by_id[item_id]["count"] == n, item_id
    assert by_id["GA-001"]["basis"] == "registry" and by_id["GA-001"]["count"] == 0


def test_js_counted_table_covers_exactly_those_items():
    block = SRC[SRC.index("const COUNTED = {"):SRC.index("function build(it)")]
    assert set(re.findall(r"'([A-Z]{2}-\d{3})'\(it, g\)", block)) == set(plant_3d.COUNTS_FROM_REGISTRY)
