"""BL-2: the Blender GLB is embedded in the 3D tab. No Blender needed: the GLB's JSON chunk is read directly."""
import json, struct
from pathlib import Path

from python import plant_3d

ROOT = Path(__file__).resolve().parents[1]
GLB = ROOT / "assets" / "plant_model.glb"


def _json_chunk():
    b = GLB.read_bytes()
    assert b[:4] == b"glTF"
    n, kind = struct.unpack("<II", b[12:20])
    assert kind == 0x4E4F534A
    return json.loads(b[20:20 + n])


def test_glb_exists_and_is_small_enough_to_embed():
    assert GLB.exists() and GLB.stat().st_size < 4_000_000


def test_glb_has_the_91_registry_ids_as_node_extras():
    ids = [n["extras"]["equipment_id"] for n in _json_chunk()["nodes"] if "equipment_id" in n.get("extras", {})]
    reg = json.loads((ROOT / "data" / "equipment_registry.json").read_text(encoding="utf-8"))
    text = json.dumps(reg)
    assert len(ids) == 91 and len(set(ids)) == 91
    assert all(i in text for i in ids)


def test_build_html_embeds_the_model_and_defaults_to_it():
    items = plant_3d.scene_items({})
    html = plant_3d.build_html(items)
    assert '"default_view": "blender"' in html and '"glb"' in html
    none = plant_3d.build_html(items, glb_path=ROOT / "does_not_exist.glb")
    assert '"default_view": "schematic"' in none
