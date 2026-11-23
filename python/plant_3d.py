"""P3-1: data and HTML for the "3D Plant" tab. CLASS: a schematic visualisation of the 91 registry items, not a model.

What the picture claims, and what it does not:
- The LAYOUT is a process-ordered schematic (one row per group, FE -> GA -> GC -> HB -> EU, then SA and AI). DOK-ING has given no CAD or
  layout, so positions are NOT to scale and carry no information; the page says so.
- SIZES: five items have an explicit dimension in data/equipment_registry.json (DIMENSIONS_FROM_REGISTRY below, each with its source row);
  every other item gets a per-group default size and is marked as an estimate. The shapes are generic (cylinder or box), not vendor drawings.
- STATE colour on each item is the SAME per-item state the Plant Overview tab counts (passed in from app.py), including the relabel of
  FAULT as DESIGN FINDING; nothing is recomputed here.
"""
import json
import math
import os

ROOT = os.path.join(os.path.dirname(__file__), "..")
GROUP_ORDER = ("FE", "GA", "GC", "HB", "EU", "SA", "AI")
GROUP_NAMES = {"FE": "Feed handling", "GA": "Gasification", "GC": "Gas cleaning", "HB": "Hydrogen & BoP",
               "EU": "Electrical & utilities", "SA": "Sensors & analysers", "AI": "Automation & AI"}

# id -> (shape, width/diameter m, height m, depth m or None, source of the figures in data/equipment_registry.json)
DIMENSIONS_FROM_REGISTRY = {
    "GA-001": ("cyl", 0.6, 4.0, None, "GA-001 reactor diameter 0.6 m, height 4.0 m"),
    "GC-004": ("cyl", 0.4, 3.0, None, "GC-004 quench tower diameter 0.4 m, height 3.0 m"),
    "GC-006": ("cyl", 0.35, 1.5, None, "GC-006 bed diameter 0.35 m, bed height 1.5 m"),
    "GC-008": ("cyl", 0.3, 2.0, None, "GC-008 scrubber diameter 0.3 m, height 2.0 m"),
    "FE-003": ("box", 3.0, 0.35, 0.4, "FE-003 conveyor length 3 m, belt width 0.4 m (height estimated)"),
}
# P3-3: items whose registry row states a COUNT (vessels, stages, modules) or a VOLUME but no dimension. The detailed shape draws the stated
# count; the footprint is still an ESTIMATE (basis stays "estimate", amber ring). id -> (count, what is counted, registry source)
COUNTS_FROM_REGISTRY = {
    "HB-006": (4, "adsorber vessels", "HB-006 Number of adsorber vessels = 4"),
    "HB-013": (3, "Type IV vessels (cascade bank)", "HB-013 Number of vessels = 3, Type IV composite"),
    "HB-010": (2, "membrane modules", "HB-010 Number of membrane modules = 2"),
    "HB-012": (4, "compression stages", "HB-012 Number of stages = 4"),
    "GC-010": (4, "filter bags", "GC-010 Number of bags = 4"),
    "GC-003": (1, "cyclone", "GC-003 Number of cyclones (parallel) = 1"),
    "FE-004": (2, "shredder rotors", "FE-004 Number of rotors = 2 (dual-shaft)"),
    "GC-012": (1, "carbon bed of 50 L", "GC-012 Carbon bed volume = 50 L"),
    "HB-014": (1, "reactor of 0.5 m3", "HB-014 Reactor volume = 0.5 m3"),
    "HB-015": (2, "carrier tanks of 1 m3 each", "HB-015 Lean and Rich carrier tank volume = 1 m3 each"),
}
# footprint for those items: ESTIMATES. Volume items: a cylinder of the registry volume with an ASSUMED height/diameter ratio (below);
# count items: a per-item estimate wide enough to show the stated count. id -> (shape, w, h, d)
def _cyl_from_volume(volume_m3, h_over_d):
    d = (4.0 * volume_m3 / (math.pi * h_over_d)) ** (1.0 / 3.0)
    return round(d, 3), round(d * h_over_d, 3)


_gc12_d, _gc12_h = _cyl_from_volume(0.05, 3.0)      # 50 L, H/D = 3 ASSUMED
_hb14_d, _hb14_h = _cyl_from_volume(0.5, 2.0)       # 0.5 m3, H/D = 2 ASSUMED
_hb15_d, _hb15_h = _cyl_from_volume(1.0, 1.5)       # 1 m3 each, H/D = 1.5 ASSUMED
ESTIMATE_OVERRIDES = {
    "HB-006": ("box", 2.0, 2.2, 0.6), "HB-013": ("box", 2.4, 0.5, 0.9), "HB-010": ("box", 1.4, 0.4, 0.5),
    "HB-012": ("box", 1.6, 1.2, 0.8), "GC-010": ("box", 1.0, 1.8, 0.8), "GC-003": ("cyl", 0.5, 1.4, None),
    "FE-004": ("box", 1.4, 1.2, 1.0), "GC-012": ("cyl", _gc12_d, _gc12_h, None), "HB-014": ("cyl", _hb14_d, _hb14_h, None),
    "HB-015": ("box", round(2 * _hb15_d + 0.3, 3), _hb15_h, _hb15_d),
}
# per-group default (shape, width/diameter, height, depth): ESTIMATES, labelled as such
DEFAULT_ESTIMATE = {
    "FE": ("box", 1.2, 1.2, 1.0), "GA": ("cyl", 0.5, 1.6, None), "GC": ("cyl", 0.3, 1.6, None),
    "HB": ("cyl", 0.4, 1.5, None), "EU": ("box", 1.0, 1.2, 0.8), "SA": ("box", 0.25, 0.4, 0.25), "AI": ("box", 0.5, 0.6, 0.4),
}
STATE_LABELS = {"running_live": "Computed this cycle (model)", "running_assumed": "Assumed inputs only",
                "static": "Static (no live key)", "missing": "Missing", "fault": "DESIGN FINDING"}
GAP_M = 0.7
ROW_PITCH_M = 4.8


def registry_names():
    with open(os.path.join(ROOT, "data", "equipment_registry.json"), encoding="utf-8") as fh:
        reg = json.load(fh)
    items = reg if isinstance(reg, list) else next(v for v in reg.values() if isinstance(v, list))
    return {i["id"]: i["name"] for i in items}


def scene_items(item_states, names=None):
    """item_states: the list from app._plant_overview_item_states(snap) (one dict per item with id, group, state).
    Returns one dict per item with a position, a size, a shape and the labels the page shows."""
    names = names if names is not None else registry_names()
    by_group = {g: [] for g in GROUP_ORDER}
    for it in item_states:
        by_group.setdefault(it["group"], []).append(it)
    out = []
    for row, g in enumerate(GROUP_ORDER):
        rows = sorted(by_group.get(g, []), key=lambda i: i["id"])
        sized = []
        for it in rows:
            if it["id"] in DIMENSIONS_FROM_REGISTRY:
                shape, w, h, d, src = DIMENSIONS_FROM_REGISTRY[it["id"]]
                basis, note = "registry", src
            elif it["id"] in COUNTS_FROM_REGISTRY:
                shape, w, h, d = ESTIMATE_OVERRIDES[it["id"]]
                n, what, src = COUNTS_FROM_REGISTRY[it["id"]]
                basis, note = "estimate", f"drawn with the registry's stated count ({src}); footprint is an estimate"
            else:
                shape, w, h, d = DEFAULT_ESTIMATE[g]
                basis, note = "estimate", "size is a per-group default estimate, not a registry value"
            sized.append((it, shape, w, h, d if d is not None else w, basis, note))
        total = sum(s[2] for s in sized) + GAP_M * max(len(sized) - 1, 0)
        x = -total / 2.0
        for it, shape, w, h, d, basis, note in sized:
            out.append({"id": it["id"], "name": names.get(it["id"], it["id"]), "group": g, "state": it["state"],
                        "state_label": STATE_LABELS[it["state"]], "shape": shape, "w": w, "h": h, "d": d,
                        "basis": basis, "basis_note": note, "count": COUNTS_FROM_REGISTRY.get(it["id"], (0,))[0], "x": round(x + w / 2.0, 3), "z": row * ROW_PITCH_M})
            x += w + GAP_M
    return out


MODEL_GLB = os.path.join(ROOT, "assets", "plant_model.glb")


def model_glb_base64(glb_path=None):
    """BL-2: the Blender model (assets/plant_model.glb, from blender/generate_plant.py) as base64 for the page, or None when the file is absent.
    The page then offers a 'Blender model' view next to the schematic; without the file the tab is the schematic only."""
    import base64
    path = glb_path or MODEL_GLB
    if not os.path.exists(path):
        return None
    with open(path, "rb") as fh:
        return base64.b64encode(fh.read()).decode("ascii")


def build_html(items, bundle_path=None, height=640, glb_path=None, default_view="blender"):
    path = bundle_path or os.path.join(ROOT, "assets", "plant3d.bundle.js")
    with open(path, encoding="utf-8") as fh:
        bundle = fh.read()
    glb = model_glb_base64(glb_path)
    data = json.dumps({"items": items, "groups": GROUP_NAMES, "order": GROUP_ORDER, "glb": glb,
                       "default_view": default_view if glb else "schematic"}).replace("</", "<\\/")
    return ("<!doctype html><html><head><meta charset='utf-8'><style>html,body{margin:0;height:100%;background:#0f1722}"
            "#wrap{position:relative;width:100%;height:@H@px}canvas{display:block}</style></head><body>"
            "<div id='wrap'></div><script>window.__PLANT3D__=@D@;</script><script>@B@</script></body></html>"
            ).replace("@H@", str(height)).replace("@D@", data).replace("@B@", bundle)
