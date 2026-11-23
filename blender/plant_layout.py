"""Process-oriented site layout for the Blender plant model (stage 1). Pure Python: no bpy, so it is testable anywhere.

WHAT THIS IS: a SCHEMATIC ENGINEERING LAYOUT with documented assumptions. It is NOT vendor CAD and NOT a surveyed site plan.
SOURCE OF TRUTH: data/equipment_registry.json supplies every ID, name and category (nothing is invented). Sizes come from the
registry where it states one (python/plant_3d.py DIMENSIONS_FROM_REGISTRY / COUNTS_FROM_REGISTRY) and are labelled "registry";
every other size is an ASSUMED representative size from RECIPE_DEFAULTS and is labelled "assumed".
NOT IN THE REGISTRY (so NOT modelled as fact): connections between items. The layout order inside a zone follows the registry ID order,
which is an ASSUMPTION about the process order (listed in docs/blender_plant_assumptions.md), not a verified P&ID.

Numeric check (the way this repo asks for): `python blender/plant_layout.py` builds the layout and asserts 91 unique registry IDs,
a footprint with no overlap between independent items, and determinism (two builds are identical). It prints the counts.
"""
import json
import math
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "python"))
import plant_3d  # noqa: E402  (registry-stated dimensions and counts are reused, not retyped)

ZONES = ("FE", "GA", "GC", "HB", "EU", "SA", "AI")
ZONE_NAMES = {"FE": "Feed handling", "GA": "Gasification", "GC": "Gas cleaning", "HB": "Hydrogen & balance of plant",
              "EU": "Electrical & utilities", "SA": "Sensors & analysers", "AI": "Automation & instrumentation"}

# recipe -> (width x, depth y, height z) in metres. ASSUMED representative sizes (no vendor data). Registry sizes override these.
RECIPE_DEFAULTS = {
    "hopper": (2.0, 2.0, 2.0), "separator": (1.6, 1.0, 1.2), "conveyor": (3.0, 0.6, 0.6), "shredder": (1.4, 1.2, 1.0),
    "dryer": (3.0, 1.0, 1.1), "screw": (2.0, 0.5, 0.6), "rotary_valve": (0.5, 0.5, 0.5), "analyser": (0.6, 0.5, 0.9),
    "reactor": (0.6, 0.6, 4.0), "wgs_reactor": (0.5, 0.5, 2.0), "skid": (1.2, 0.8, 1.0), "drain": (0.7, 0.7, 0.9), "bin": (1.0, 1.0, 1.0),
    "process_unit": (1.6, 1.2, 1.8), "silo": (0.9, 0.9, 2.2), "cyclone": (0.4, 0.4, 1.5), "tower": (0.3, 0.3, 2.0),
    "bag_filter": (1.0, 0.8, 1.8), "adsorber": (0.35, 0.35, 1.5), "blower": (0.8, 0.5, 0.6), "tank_h": (1.2, 0.7, 0.7),
    "vessel_v": (0.5, 0.5, 1.5), "vessel_h": (1.2, 0.8, 0.8), "hx": (1.8, 0.5, 0.5), "psa": (2.0, 0.6, 2.2),
    "membrane": (1.4, 0.5, 0.5), "container": (2.4, 1.2, 2.0), "compressor": (1.6, 0.8, 1.2), "bank": (2.4, 0.9, 0.5),
    "dispenser": (0.8, 0.6, 2.0), "cabinet": (1.0, 0.8, 1.8), "genset": (3.0, 1.2, 1.8), "microturbine": (1.5, 0.8, 1.6),
    "flare": (0.4, 0.4, 6.0), "cooling_tower": (1.6, 1.6, 2.4), "meter": (0.6, 0.3, 0.9), "plate_hx": (0.6, 0.4, 1.0),
    "instrument": (0.3, 0.3, 0.5), "mast": (0.3, 0.3, 4.0), "pole": (0.3, 0.3, 3.0), "rack": (0.6, 0.9, 2.0),
    "workstation": (1.2, 0.7, 1.1),
}

# id -> recipe. Every one of the 91 IDs is listed; tests check that this set equals the registry's set.
RECIPE = {
    "FE-001": "hopper", "FE-002": "separator", "FE-003": "conveyor", "FE-004": "shredder", "FE-005": "dryer",
    "FE-006": "analyser", "FE-007": "screw", "FE-008": "rotary_valve",
    "GA-001": "reactor", "GA-002": "instrument", "GA-003": "skid", "GA-004": "instrument", "GA-005": "drain",
    "GA-006": "screw", "GA-007": "bin", "GA-008": "process_unit", "GA-009": "process_unit", "GA-010": "silo",
    "GC-001": "cyclone", "GC-002": "instrument", "GC-003": "cyclone", "GC-004": "tower", "GC-005": "instrument",
    "GC-006": "adsorber", "GC-007": "tower", "GC-008": "tower", "GC-009": "tower", "GC-010": "bag_filter",
    "GC-011": "instrument", "GC-012": "adsorber", "GC-013": "blower", "GC-014": "instrument", "GC-015": "tank_h",
    "SA-001": "analyser", "SA-002": "analyser", "SA-003": "analyser", "SA-004": "analyser", "SA-005": "analyser",
    "SA-006": "analyser", "SA-007": "instrument", "SA-008": "analyser", "SA-009": "analyser", "SA-010": "instrument",
    "SA-011": "instrument", "SA-012": "instrument",
    "HB-001": "wgs_reactor", "HB-002": "instrument", "HB-003": "hx", "HB-004": "wgs_reactor", "HB-005": "vessel_h",
    "HB-006": "psa", "HB-007": "instrument", "HB-008": "instrument", "HB-009": "vessel_v", "HB-010": "membrane",
    "HB-011": "container", "HB-012": "compressor", "HB-013": "bank", "HB-014": "vessel_v", "HB-015": "tank_h",
    "HB-016": "vessel_v", "HB-017": "adsorber", "HB-018": "dispenser",
    "EU-001": "cabinet", "EU-002": "instrument", "EU-003": "genset", "EU-004": "instrument", "EU-005": "microturbine",
    "EU-006": "cabinet", "EU-007": "flare", "EU-008": "cooling_tower", "EU-009": "meter", "EU-010": "cabinet",
    "EU-011": "hx", "EU-012": "plate_hx", "EU-013": "meter",
    "AI-001": "mast", "AI-002": "pole", "AI-003": "instrument", "AI-004": "rack", "AI-005": "rack", "AI-006": "rack",
    "AI-007": "rack", "AI-008": "rack", "AI-009": "rack", "AI-010": "rack", "AI-011": "rack", "AI-012": "rack",
    "AI-013": "rack", "AI-014": "rack", "AI-015": "workstation",
}
# Registry rows that describe another row's equipment from a different measured angle (name says "(Pressure)", "(DP)", ...).
# ASSUMPTION (not stated by the registry): they are drawn as an instrument tag mounted on the parent unit, still as their own
# selectable assembly with their own ID. id -> parent id.
TAG_OF = {"GA-002": "GA-001", "GA-004": "GA-003", "GC-002": "GC-001", "GC-005": "GC-004", "GC-011": "GC-010",
          "GC-014": "GC-013", "HB-002": "HB-001", "HB-007": "HB-006", "HB-008": "HB-006", "EU-002": "EU-001",
          "EU-004": "EU-003", "AI-003": "GA-001"}
# Registry items that are software or cloud services, not hardware you can stand next to: drawn as a rack placeholder only.
NON_PHYSICAL = {"AI-006": "MQTT broker (software)", "AI-010": "cloud service (off-site)", "AI-011": "database (software)",
                "AI-012": "AI model server (software on a server)", "AI-013": "digital twin engine (software)",
                "AI-014": "orchestration controller (software)"}

GAP = 1.4            # clear distance between independent items in a lane (m), ASSUMED
LANE_PITCH = 8.0    # distance between process lanes (m), leaves a pipe-rack corridor between lanes (stage 3 puts pipes there)
PAD_MARGIN = 0.4
# (zone, lane index, x start). The lanes run along +x; GA is offset so the flow steps across the site instead of one block.
ZONE_PLACE = {"FE": (0, 0.0), "GA": (1, 8.0), "GC": (2, 16.0), "HB": (3, 4.0), "EU": (4, 0.0)}
# Items placed on a sensor rack, in the analyser shelter and in the control building, not in a process lane.
SHELTER = ("SA-001", "SA-002", "SA-003", "SA-004", "SA-005", "SA-006", "SA-008", "SA-009")
FIELD_INSTRUMENTS = ("SA-007", "SA-010", "SA-011", "SA-012")   # on the gas line: placed beside the last gas-cleaning units
CONTROL_BUILDING = tuple("AI-%03d" % n for n in range(4, 16))
SITE_W, SITE_D = 64.0, 46.0


def load_registry():
    with open(os.path.join(ROOT, "data", "equipment_registry.json"), encoding="utf-8") as fh:
        reg = json.load(fh)
    items = reg if isinstance(reg, list) else next(v for v in reg.values() if isinstance(v, list))
    return items


def _size(item_id):
    """(w, d, h, basis, note). Registry-stated size first, then the assumed recipe default."""
    recipe = RECIPE[item_id]
    w, d, h = RECIPE_DEFAULTS[recipe]
    if item_id in plant_3d.DIMENSIONS_FROM_REGISTRY:
        shape, a, b, c, src = plant_3d.DIMENSIONS_FROM_REGISTRY[item_id]
        if shape == "cyl":
            w, d, h = a, a, b
        else:
            w, d, h = a, c, b
        return w, d, h, "registry", src
    if item_id in plant_3d.ESTIMATE_OVERRIDES:
        shape, a, b, c = plant_3d.ESTIMATE_OVERRIDES[item_id]
        n, what, src = plant_3d.COUNTS_FROM_REGISTRY.get(item_id, (0, "", "volume stated in the registry"))
        if shape == "cyl":
            w, d, h = a, a, b
        else:
            w, d, h = a, (c if c is not None else a), b
        return w, d, h, "estimate", "registry states %s; footprint is an estimate" % src
    return w, d, h, "assumed", "representative size for a '%s' (no vendor or registry dimension)" % recipe


def _lane(ids, y0, x0, sizes):
    out, x = {}, x0
    for i in ids:
        w, d, h = sizes[i][:3]
        out[i] = (x + w / 2.0, y0 + d / 2.0)
        x += w + GAP
    return out, x


def build_layout():
    reg = load_registry()
    names = {r["id"]: r for r in reg}
    sizes = {i: _size(i) for i in RECIPE}
    placed = {}
    independent = {z: [i for i in sorted(RECIPE) if i.startswith(z + "-") and i not in TAG_OF and i not in SHELTER
                       and i not in FIELD_INSTRUMENTS and i not in CONTROL_BUILDING and i != "AI-001" and i != "AI-002"]
                   for z in ZONES}
    for zone, (lane, x0) in ZONE_PLACE.items():
        pos, _ = _lane(independent[zone], 3.0 + lane * LANE_PITCH, x0 + 3.0, sizes)
        placed.update(pos)
    # sensors on the gas line: just after the last gas-cleaning unit
    last_gc = max((i for i in independent["GC"]), key=lambda i: placed[i][0])
    fx = placed[last_gc][0] + sizes[last_gc][0] / 2.0 + 1.5
    for k, i in enumerate(FIELD_INSTRUMENTS):
        placed[i] = (fx + k * 0.9, 3.0 + 2 * LANE_PITCH + 0.5)
    # analyser shelter (open-front hut) east of the process lanes; racks in a row inside it
    sx0, sy0 = 49.0, 3.0
    for k, i in enumerate(SHELTER):
        placed[i] = (sx0 + 1.0 + (k % 4) * 1.0, sy0 + 1.2 + (k // 4) * 1.1)
    # control building: server racks in a row
    cx0, cy0 = 49.0, 20.0
    for k, i in enumerate(CONTROL_BUILDING):
        placed[i] = (cx0 + 1.0 + (k % 6) * 1.2, cy0 + 1.3 + (k // 6) * 2.4)
    placed["AI-001"] = (SITE_W - 3.0, 4.0)          # weather mast near the east edge
    placed["AI-002"] = (2.0, 1.5)                   # camera pole at the feed reception
    out = []
    for r in reg:
        i = r["id"]
        w, d, h, basis, note = sizes[i]
        if i in TAG_OF:
            p = TAG_OF[i]
            px, py = placed[p]
            pw, pd, ph = sizes[p][:3]
            k = sorted(t for t, q in TAG_OF.items() if q == p).index(i)
            x, y, z = px + pw / 2.0 + 0.15 + 0.35 * k, py, min(ph * 0.55, 1.6)
            where = "tag on " + p
        else:
            x, y = placed[i]
            z, where = 0.0, "free standing"
        geometry = "non-physical placeholder: " + NON_PHYSICAL[i] if i in NON_PHYSICAL else (
            "instrument tag on %s (assumption)" % TAG_OF[i] if i in TAG_OF else "representative equipment recipe '%s'" % RECIPE[i])
        out.append({"id": i, "name": r["name"], "category": r["category"], "zone": i[:2], "recipe": RECIPE[i],
                    "x": round(x, 3), "y": round(y, 3), "z": round(z, 3), "w": round(w, 3), "d": round(d, 3), "h": round(h, 3),
                    "size_basis": basis, "size_note": note, "placement": where, "tag_of": TAG_OF.get(i),
                    "geometry_status": geometry, "data_provenance": "name/ID/category: data/equipment_registry.json; size: " + basis,
                    "source_registry": "data/equipment_registry.json"})
    return out


def zone_pads():
    """Bounding pad per process zone/building from the placed items (metres): zone -> (x0, y0, x1, y1)."""
    lay = build_layout()
    pads = {}
    for z in ("FE", "GA", "GC", "HB", "EU"):
        its = [i for i in lay if i["zone"] == z and not i["tag_of"] and i["id"] not in FIELD_INSTRUMENTS]
        pads[z] = (min(i["x"] - i["w"] / 2 for i in its) - PAD_MARGIN, min(i["y"] - i["d"] / 2 for i in its) - PAD_MARGIN,
                   max(i["x"] + i["w"] / 2 for i in its) + PAD_MARGIN, max(i["y"] + i["d"] / 2 for i in its) + PAD_MARGIN)
    pads["SA"] = (49.0, 3.0, 55.0, 6.5)
    pads["AI"] = (49.0, 20.0, 58.0, 27.0)
    return pads


def validate(lay=None):
    lay = lay or build_layout()
    reg_ids = [r["id"] for r in load_registry()]
    ids = [i["id"] for i in lay]
    assert len(ids) == len(set(ids)) == len(reg_ids) == 91, (len(ids), len(set(ids)), len(reg_ids))
    assert sorted(ids) == sorted(reg_ids), "layout IDs differ from the registry IDs"
    assert set(RECIPE) == set(reg_ids), "recipe table differs from the registry IDs"
    free = [i for i in lay if not i["tag_of"]]
    bad = []
    for a in range(len(free)):
        for b in range(a + 1, len(free)):
            p, q = free[a], free[b]
            if abs(p["x"] - q["x"]) < (p["w"] + q["w"]) / 2.0 and abs(p["y"] - q["y"]) < (p["d"] + q["d"]) / 2.0:
                bad.append((p["id"], q["id"]))
    assert not bad, "footprints overlap: %s" % bad
    assert all(0 < i["x"] < SITE_W and 0 < i["y"] < SITE_D for i in lay), "an item lies outside the site"
    assert json.dumps(build_layout(), sort_keys=True) == json.dumps(lay, sort_keys=True), "layout is not deterministic"
    return {"items": len(ids), "zones": sorted({i["zone"] for i in lay}), "tags": sum(1 for i in lay if i["tag_of"]),
            "registry_sized": sum(1 for i in lay if i["size_basis"] == "registry"),
            "estimate_sized": sum(1 for i in lay if i["size_basis"] == "estimate"),
            "assumed_sized": sum(1 for i in lay if i["size_basis"] == "assumed")}


if __name__ == "__main__" and "--write-docs" not in sys.argv:
    print(validate())


def assumptions_markdown():
    """docs/blender_plant_assumptions.md is generated from the layout tables, so it cannot drift (a test compares them)."""
    lay = build_layout()
    out = ["# Blender plant model: layout and geometry assumptions (generated; do not edit by hand)", "",
           "Regenerate with `python blender/plant_layout.py --write-docs`. This model is a SCHEMATIC ENGINEERING LAYOUT, not vendor CAD, not a P&ID and not a surveyed site plan.", "",
           "## What is taken from the registry and what is assumed", "",
           "- Taken from `data/equipment_registry.json`: every ID, name and category (91 items, none invented).",
           "- Sizes stated by the registry (`registry`): %d items. Footprint estimated around a registry-stated count or volume (`estimate`): %d. Representative size assumed (`assumed`): %d." % (
               sum(1 for i in lay if i["size_basis"] == "registry"), sum(1 for i in lay if i["size_basis"] == "estimate"), sum(1 for i in lay if i["size_basis"] == "assumed")),
           "- NOT in the registry and therefore NOT drawn: connections between items (no upstream/downstream data). Stage 3 will draw only the documented process chain and mark the rest conceptual.",
           "- Item order inside a zone follows the registry ID order. That is an ASSUMPTION about the process order, not a verified P&ID.",
           "- Lane spacing (%.1f m), item gap (%.1f m), plinth height, site size (%.0f x %.0f m) and all `assumed` sizes are representative values chosen for the picture." % (LANE_PITCH, GAP, SITE_W, SITE_D),
           "", "## Registry rows drawn as an instrument tag on another unit (assumption: they describe the same equipment from another measured angle)", ""]
    out += ["- %s (%s) on %s" % (k, next(i["name"] for i in lay if i["id"] == k), v) for k, v in sorted(TAG_OF.items())]
    out += ["", "## Registry rows that are software or cloud services (drawn as a rack placeholder, not as hardware)", ""]
    out += ["- %s: %s" % (k, v) for k, v in sorted(NON_PHYSICAL.items())]
    out += ["", "## Per-item size basis", "", "| ID | Name | Recipe | Size (w x d x h, m) | Basis |", "|---|---|---|---|---|"]
    out += ["| %s | %s | %s | %.2f x %.2f x %.2f | %s |" % (i["id"], i["name"], i["recipe"], i["w"], i["d"], i["h"], i["size_basis"]) for i in lay]
    out += ["", "## Missing vendor dimensions and unverified connections", "",
            "- Vendor dimensions are missing for the %d `assumed` items and the footprints of the %d `estimate` items." % (
                sum(1 for i in lay if i["size_basis"] == "assumed"), sum(1 for i in lay if i["size_basis"] == "estimate")),
            "- All connections between items are unverified (none in the registry).", ""]
    return "\n".join(out)


if __name__ == "__main__" and "--write-docs" in sys.argv:
    with open(os.path.join(ROOT, "docs", "blender_plant_assumptions.md"), "w", encoding="utf-8") as fh:
        fh.write(assumptions_markdown())
    print("wrote docs/blender_plant_assumptions.md")
