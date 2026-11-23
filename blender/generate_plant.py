"""HYGAS-AI plant model for Blender (stage 1). Run with Blender's Python (or `pip install bpy`, Blender 5.3):

    python blender/generate_plant.py --out build/blender            # builds, validates, exports GLB, renders preview
    blender --background --python blender/generate_plant.py -- --out build/blender --blend

WHAT THIS IS: a SCHEMATIC ENGINEERING MODEL with documented assumptions, not vendor CAD. Every registry item becomes ONE independent
assembly (an Empty named by the registry ID) with metadata; sizes are registry-stated where the registry states one, else ASSUMED
representative sizes (see blender/plant_layout.py and docs/blender_plant_assumptions.md). The only links drawn (stage 3) are the
model dependencies in data/plant_links.json (derived from the live engine); routing and pipe diameter are assumed, nothing else is connected.
Deterministic: no randomness; two runs give the same layout (checked in tests/test_blender_layout.py).
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import plant_layout as L  # noqa: E402
import plant_links as K  # noqa: E402

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

PLINTH = 0.12   # concrete plinth height (m), ASSUMED


# ----------------------------------------------------------------------------------------------------------- materials
def _mat(name, rgb, metal, rough, alpha=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1.0)
    b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rough
    if alpha < 1.0:
        b.inputs["Alpha"].default_value = alpha
    return m


def make_materials():
    zone_paint = {"FE": (0.78, 0.55, 0.18), "GA": (0.70, 0.18, 0.12), "GC": (0.18, 0.45, 0.62), "HB": (0.12, 0.52, 0.38),
                  "EU": (0.45, 0.32, 0.60), "SA": (0.85, 0.74, 0.15), "AI": (0.50, 0.52, 0.58)}
    mats = {"stainless": _mat("stainless_steel", (0.78, 0.80, 0.82), 1.0, 0.22),
            "carbon": _mat("carbon_steel", (0.30, 0.31, 0.33), 0.8, 0.45),
            "concrete": _mat("concrete", (0.48, 0.48, 0.46), 0.0, 0.9),
            "insulation": _mat("insulation", (0.85, 0.82, 0.70), 0.0, 0.8),
            "rubber": _mat("rubber", (0.05, 0.05, 0.05), 0.0, 0.85),
            "glass": _mat("glass", (0.6, 0.8, 0.9), 0.0, 0.05, 0.35),
            "copper": _mat("copper", (0.72, 0.42, 0.25), 1.0, 0.3),
            "asphalt": _mat("asphalt", (0.10, 0.10, 0.11), 0.0, 0.7),
            "grass": _mat("ground", (0.16, 0.20, 0.14), 0.0, 1.0),
            "building": _mat("building_cladding", (0.70, 0.72, 0.74), 0.2, 0.6),
            "screen": _mat("screen", (0.05, 0.10, 0.15), 0.0, 0.2),
            "pipe": _mat("pipe_link", (0.55, 0.58, 0.62), 0.9, 0.3),
            "grating": _mat("grating", (0.35, 0.36, 0.38), 0.8, 0.5),
            "safety_yellow": _mat("safety_yellow", (0.90, 0.72, 0.10), 0.2, 0.5)}
    for z, c in zone_paint.items():
        mats["paint_" + z] = _mat("paint_" + z, c, 0.4, 0.4)
        # BL-5: a link inside one zone takes a muted version of that zone's colour; links between zones stay neutral steel
        mats["pipe_" + z] = _mat("pipe_" + z, tuple(0.55 * v + 0.45 * 0.55 for v in c), 0.9, 0.3)
    mats["marking"] = _mat("road_marking", (0.85, 0.85, 0.80), 0.0, 0.7)
    mats["label"] = _mat("id_label", (1.0, 0.98, 0.85), 0.0, 0.5)
    b = mats["label"].node_tree.nodes["Principled BSDF"]          # self-lit so the sign stays readable in shade
    b.inputs["Emission Color"].default_value = (1.0, 0.98, 0.85, 1.0)
    b.inputs["Emission Strength"].default_value = 2.0
    mats["label_plate"] = _mat("id_label_plate", (0.05, 0.07, 0.10), 0.0, 0.6)
    return mats


# ----------------------------------------------------------------------------------------------------------- primitives
def _finish(o, mat, parent, smooth=True):
    o.data.materials.append(mat)
    if smooth:
        for p in o.data.polygons:
            p.use_smooth = True
    o.parent = parent
    return o


def box(parent, mat, size, loc, name="box"):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object
    o.scale = size
    o.name = name
    return _finish(o, mat, parent, smooth=False)


def cyl(parent, mat, r, h, loc, axis="z", verts=24, name="cyl"):
    rot = {"z": (0, 0, 0), "x": (0, math.pi / 2, 0), "y": (math.pi / 2, 0, 0)}[axis]
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=h, vertices=verts, location=loc, rotation=rot)
    o = bpy.context.object
    o.name = name
    return _finish(o, mat, parent)


def cone(parent, mat, r1, r2, h, loc, verts=24, name="cone"):
    bpy.ops.mesh.primitive_cone_add(radius1=r1, radius2=r2, depth=h, vertices=verts, location=loc)
    o = bpy.context.object
    o.name = name
    return _finish(o, mat, parent)


def dome(parent, mat, r, loc, squash=0.4, flip=False, name="head"):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=24, ring_count=10)
    o = bpy.context.object
    o.scale.z = squash * (-1 if flip else 1)
    o.name = name
    return _finish(o, mat, parent)


def ring(parent, mat, r, z, t=0.04, name="flange"):
    return cyl(parent, mat, r, t, (0, 0, z), name=name)


# ----------------------------------------------------------------------------------------------------------- recipes
# Each recipe builds parts in the assembly's local frame (origin = centre of the footprint on the plinth top, z up).
# w/d/h = footprint x, footprint y, height. All parts are ILLUSTRATIVE geometry for the stated recipe, not vendor drawings.
def r_vertical_vessel(p, M, w, d, h, paint, *, lining=False, platform=False, legs=True):
    r = w / 2.0
    cyl(p, M[paint], r, h * 0.84, (0, 0, h * 0.5), name="shell")
    dome(p, M[paint], r, (0, 0, h * 0.5 + h * 0.42), name="top_head")
    dome(p, M[paint], r, (0, 0, h * 0.5 - h * 0.42), flip=True, name="bottom_head")
    for z in (0.12, 0.5, 0.88):
        ring(p, M["carbon"], r * 1.1, h * z, name="flange")
    if lining:                                            # refractory/insulation band representation
        cyl(p, M["insulation"], r * 1.08, h * 0.3, (0, 0, h * 0.38), name="refractory_lining")
    if legs:
        for a in range(4):
            ang = math.radians(45 + 90 * a)
            cyl(p, M["carbon"], 0.03, h * 0.12, (math.cos(ang) * r * 0.8, math.sin(ang) * r * 0.8, h * 0.06), verts=8, name="leg")
    cyl(p, M["carbon"], 0.05, 0.4, (r + 0.2, 0, h * 0.7), axis="x", verts=12, name="nozzle_in")
    cyl(p, M["carbon"], 0.05, 0.4, (-r - 0.2, 0, h * 0.3), axis="x", verts=12, name="nozzle_out")
    cyl(p, M["carbon"], 0.04, 0.3, (0, 0, h + 0.15), verts=12, name="vent_nozzle")
    if platform:
        box(p, M["carbon"], (r * 3.0, r * 3.0, 0.05), (0, 0, h * 0.62), name="platform")
        for k in range(8):
            ang = math.radians(45 * k)
            cyl(p, M["carbon"], 0.012, 0.9, (math.cos(ang) * r * 1.45, math.sin(ang) * r * 1.45, h * 0.62 + 0.45), verts=6, name="handrail_post")
        box(p, M["carbon"], (0.45, 0.04, h * 0.64), (0, -r * 1.7, h * 0.32), name="ladder")


def r_tower(p, M, w, d, h, paint):
    r = w / 2.0
    cyl(p, M[paint], r, h, (0, 0, h / 2), name="shell")
    dome(p, M[paint], r, (0, 0, h), name="top_head")
    cyl(p, M["glass"], r * 1.02, h * 0.08, (0, 0, h * 0.35), name="sight_glass")
    for z in (0.08, 0.92):
        ring(p, M["carbon"], r * 1.12, h * z, name="flange")
    cyl(p, M["carbon"], 0.04, 0.35, (r + 0.18, 0, h * 0.2), axis="x", verts=12, name="nozzle_in")
    cyl(p, M["carbon"], 0.04, 0.35, (0, r + 0.18, h * 0.97), axis="y", verts=12, name="nozzle_out")
    box(p, M["carbon"], (r * 2.4, r * 2.4, 0.05), (0, 0, 0.1), name="skirt_base")


def r_cyclone(p, M, w, d, h, paint):
    r = w / 2.0
    cyl(p, M[paint], r, h * 0.4, (0, 0, h * 0.8), name="barrel")
    cone(p, M[paint], r, 0.05, h * 0.55, (0, 0, h * 0.325), name="cone")
    cyl(p, M["carbon"], 0.05, h * 0.2, (0, 0, h * 1.05), verts=12, name="vortex_finder")
    box(p, M["carbon"], (0.16, r * 1.1, 0.16), (0, r * 0.7, h * 0.92), name="tangential_inlet")
    cyl(p, M["carbon"], 0.06, 0.15, (0, 0, 0.07), verts=12, name="dust_outlet")


def r_hopper(p, M, w, d, h, paint):
    cone(p, M[paint], w * 0.7, w * 0.15, h * 0.55, (0, 0, h * 0.28), verts=4, name="hopper_cone").rotation_euler[2] = math.pi / 4
    box(p, M[paint], (w, d, h * 0.45), (0, 0, h * 0.78), name="upper_box")
    for sx in (-1, 1):
        for sy in (-1, 1):
            cyl(p, M["carbon"], 0.05, h * 0.25, (sx * w * 0.42, sy * d * 0.42, h * 0.12), verts=8, name="leg")
    box(p, M["carbon"], (0.5, 0.5, 0.06), (0, 0, h * 0.02), name="outlet_flange")


def r_box_machine(p, M, w, d, h, paint, drum=False, rotors=0):
    box(p, M[paint], (w, d, h * 0.7), (0, 0, h * 0.5), name="housing")
    box(p, M["carbon"], (w * 1.02, d * 1.02, 0.05), (0, 0, h * 0.85), name="top_plate")
    cyl(p, M["carbon"], 0.18, 0.5, (w * 0.55, 0, h * 0.4), axis="x", name="drive_motor")
    if drum:
        cyl(p, M["stainless"], d * 0.35, w * 0.7, (0, 0, h * 0.95), axis="x", name="drum")
    for k in range(rotors):
        cyl(p, M["stainless"], d * 0.18, w * 0.8, (0, (k - (rotors - 1) / 2.0) * d * 0.4, h * 1.05), axis="x", name="rotor")
    cone(p, M[paint], w * 0.5, w * 0.2, h * 0.4, (0, 0, h * 1.25), verts=4, name="feed_hopper").rotation_euler[2] = math.pi / 4


def r_conveyor(p, M, w, d, h, paint, screw=False):
    if screw:
        cyl(p, M[paint], d * 0.45, w, (0, 0, h * 0.5), axis="x", verts=16, name="screw_casing")
        cyl(p, M["carbon"], d * 0.3, 0.3, (-w * 0.5 - 0.15, 0, h * 0.5), axis="x", name="drive_motor")
        for s in (-1, 1):
            box(p, M["carbon"], (0.06, d * 0.8, h * 0.4), (s * w * 0.4, 0, h * 0.2), name="support")
        return
    box(p, M["carbon"], (w, d * 0.9, 0.06), (0, 0, h * 0.55), name="frame_side")
    box(p, M["rubber"], (w * 0.98, d * 0.7, 0.03), (0, 0, h * 0.62), name="belt")
    for k in range(7):
        cyl(p, M["stainless"], 0.04, d * 0.75, (-w * 0.45 + k * w * 0.15, 0, h * 0.57), axis="y", verts=8, name="roller")
    cyl(p, M["carbon"], 0.14, 0.4, (w * 0.5 + 0.2, 0, h * 0.55), axis="x", name="drive_motor")
    for s in (-1, 1):
        for sy in (-1, 1):
            box(p, M["carbon"], (0.06, 0.06, h * 0.55), (s * w * 0.4, sy * d * 0.4, h * 0.27), name="leg")


def r_dryer(p, M, w, d, h, paint):
    cyl(p, M[paint], d * 0.42, w, (0, 0, h * 0.55), axis="x", verts=32, name="rotary_drum")
    cyl(p, M["insulation"], d * 0.46, w * 0.8, (0, 0, h * 0.55), axis="x", verts=32, name="insulation")
    for s in (-1, 1):
        cyl(p, M["carbon"], d * 0.5, 0.08, (s * w * 0.3, 0, h * 0.55), axis="x", name="riding_ring")
        box(p, M["carbon"], (0.3, d * 0.8, h * 0.45), (s * w * 0.3, 0, h * 0.22), name="trunnion_support")
    cyl(p, M["carbon"], 0.15, 0.4, (w * 0.55, 0, h * 0.3), axis="x", name="drive_motor")


def r_skid(p, M, w, d, h, paint):
    box(p, M["carbon"], (w, d, 0.08), (0, 0, 0.04), name="baseplate")
    box(p, M[paint], (w * 0.6, d * 0.8, h * 0.8), (-w * 0.15, 0, h * 0.45), name="cabinet")
    cyl(p, M["carbon"], 0.14, w * 0.3, (w * 0.3, 0, h * 0.3), axis="x", name="blower_motor")
    cyl(p, M["carbon"], 0.1, 0.4, (w * 0.45, 0, h * 0.8), axis="z", verts=12, name="discharge")


def r_instrument(p, M, w, d, h, paint):
    cyl(p, M["stainless"], 0.03, h * 0.5, (0, 0, h * 0.25), verts=10, name="impulse_line")
    box(p, M[paint], (0.12, 0.1, 0.16), (0, 0, h * 0.58), name="transmitter_body")
    box(p, M["screen"], (0.09, 0.01, 0.06), (0, -0.055, h * 0.6), name="display")
    cyl(p, M["carbon"], 0.04, 0.03, (0, 0, h * 0.5), verts=10, name="mount_flange")


def r_analyser(p, M, w, d, h, paint):
    box(p, M[paint], (w, d, h * 0.9), (0, 0, h * 0.5), name="enclosure")
    box(p, M["screen"], (w * 0.55, 0.02, h * 0.2), (0, -d * 0.5 - 0.01, h * 0.7), name="display")
    box(p, M["carbon"], (w * 0.8, d * 0.8, 0.04), (0, 0, 0.02), name="base")
    cyl(p, M["stainless"], 0.02, 0.35, (w * 0.3, d * 0.55, h * 0.4), axis="y", verts=8, name="sample_line")


def r_horizontal_vessel(p, M, w, d, h, paint, banks=1):
    r = d / 2.0 if banks == 1 else d / (2.0 * banks)
    for k in range(banks):
        yk = (k - (banks - 1) / 2.0) * (d / banks)
        cyl(p, M[paint], r * 0.95, w * 0.9, (0, yk, h * 0.55), axis="x", verts=24, name="shell")
        dome_l = dome(p, M[paint], r * 0.95, (-w * 0.45, yk, h * 0.55), squash=0.4, name="head")
        dome_l.rotation_euler[1] = math.pi / 2
        dome_r = dome(p, M[paint], r * 0.95, (w * 0.45, yk, h * 0.55), squash=0.4, name="head")
        dome_r.rotation_euler[1] = -math.pi / 2
    for s in (-1, 1):
        box(p, M["carbon"], (0.08, d * 0.9, h * 0.4), (s * w * 0.3, 0, h * 0.2), name="saddle")
    cyl(p, M["carbon"], 0.07, 0.25, (0, 0, h * 0.55 + r * 1.0), verts=12, name="manway")


def r_hx(p, M, w, d, h, paint):
    cyl(p, M[paint], d * 0.5, w * 0.8, (0, 0, h * 0.55), axis="x", verts=28, name="shell")
    for s in (-1, 1):
        cyl(p, M["carbon"], d * 0.58, 0.18, (s * w * 0.46, 0, h * 0.55), axis="x", name="channel_head")
        box(p, M["carbon"], (0.1, d * 0.9, h * 0.4), (s * w * 0.28, 0, h * 0.2), name="saddle")
    cyl(p, M["carbon"], 0.05, 0.3, (-w * 0.3, 0, h * 0.55 + d * 0.5 + 0.1), verts=12, name="shell_nozzle")
    cyl(p, M["carbon"], 0.05, 0.3, (w * 0.3, 0, h * 0.55 - d * 0.5 - 0.1), verts=12, name="shell_nozzle")


def r_psa(p, M, w, d, h, paint, vessels=4):
    for k in range(vessels):
        x = (k - (vessels - 1) / 2.0) * (w / vessels)
        cyl(p, M[paint], w / vessels * 0.38, h * 0.8, (x, 0, h * 0.5), name="adsorber_vessel")
        dome(p, M[paint], w / vessels * 0.38, (x, 0, h * 0.9))
        dome(p, M[paint], w / vessels * 0.38, (x, 0, h * 0.1), flip=True)
    cyl(p, M["stainless"], 0.06, w, (0, 0.25, h * 0.2), axis="x", verts=12, name="manifold_bottom")
    cyl(p, M["stainless"], 0.06, w, (0, 0.25, h * 0.95), axis="x", verts=12, name="manifold_top")
    box(p, M["carbon"], (w * 1.05, d, 0.08), (0, 0, 0.04), name="skid_base")


def r_compressor(p, M, w, d, h, paint, stages=4):
    box(p, M["carbon"], (w, d, 0.1), (0, 0, 0.05), name="baseplate")
    cyl(p, M["carbon"], d * 0.4, w * 0.4, (-w * 0.28, 0, h * 0.45), axis="x", name="electric_motor")
    box(p, M[paint], (w * 0.45, d * 0.8, h * 0.7), (w * 0.15, 0, h * 0.45), name="compressor_casing")
    for k in range(stages):
        cyl(p, M["stainless"], 0.07, h * 0.3, (w * 0.0 + k * w * 0.11, d * 0.2, h * 0.9), verts=12, name="stage_cylinder")
    cyl(p, M["stainless"], 0.04, 0.4, (w * 0.5 + 0.1, 0, h * 0.5), axis="x", verts=10, name="discharge")


def r_bank(p, M, w, d, h, paint, vessels=3):
    n = vessels
    for k in range(n):
        y = (k - (n - 1) / 2.0) * (d / n)
        cyl(p, M[paint], d / n * 0.4, w, (0, y, h * 0.55 + 0.25), axis="x", name="type_iv_vessel")
    for s in (-1, 1):
        box(p, M["carbon"], (0.1, d, 0.45), (s * w * 0.35, 0, 0.22), name="rack_frame")
    cyl(p, M["stainless"], 0.04, d, (w * 0.5, 0, h * 0.55 + 0.25), axis="y", verts=10, name="manifold")


def r_container(p, M, w, d, h, paint):
    box(p, M[paint], (w, d, h), (0, 0, h / 2), name="container_body")
    for k in range(6):
        box(p, M["carbon"], (0.03, d * 1.01, h * 0.9), (-w * 0.45 + k * w * 0.18, 0, h / 2), name="corrugation_rib")
    box(p, M["carbon"], (0.9, 0.05, 1.7), (w * 0.2, -d * 0.5 - 0.02, 0.9), name="door")
    box(p, M["carbon"], (w * 0.3, d * 0.5, 0.15), (-w * 0.25, 0, h + 0.07), name="roof_unit")


def r_genset(p, M, w, d, h, paint):
    r_container(p, M, w, d, h, paint)
    cyl(p, M["stainless"], 0.1, 1.6, (w * 0.4, d * 0.2, h + 0.8), verts=14, name="exhaust_stack")
    box(p, M["carbon"], (0.5, d * 0.6, 0.5), (w * 0.5 + 0.25, 0, 0.35), name="radiator")


def r_cabinet(p, M, w, d, h, paint):
    box(p, M[paint], (w, d, h), (0, 0, h / 2), name="cabinet_body")
    box(p, M["carbon"], (w * 0.9, 0.03, h * 0.9), (0, -d * 0.5 - 0.015, h / 2), name="door")
    box(p, M["screen"], (w * 0.3, 0.02, h * 0.1), (0, -d * 0.5 - 0.04, h * 0.7), name="display")
    box(p, M["carbon"], (w * 0.5, d * 0.5, 0.15), (0, 0, h + 0.07), name="roof_cooling_unit")


def r_microturbine(p, M, w, d, h, paint):
    box(p, M[paint], (w, d, h * 0.8), (0, 0, h * 0.45), name="enclosure")
    cyl(p, M["stainless"], 0.12, 0.8, (w * 0.3, 0, h * 0.95), verts=14, name="exhaust")
    box(p, M["carbon"], (w * 0.3, d * 0.7, h * 0.15), (-w * 0.25, 0, h * 0.88), name="air_intake")


def r_flare(p, M, w, d, h, paint):
    cyl(p, M["carbon"], 0.18, h * 0.9, (0, 0, h * 0.45), verts=20, name="flare_stack")
    cone(p, M["stainless"], 0.18, 0.28, 0.3, (0, 0, h * 0.9 + 0.15), name="tip")
    box(p, M["carbon"], (1.0, 1.0, 0.1), (0, 0, 0.05), name="base")
    for a in range(3):
        ang = math.radians(120 * a)
        cyl(p, M["carbon"], 0.015, h * 0.55, (math.cos(ang) * 0.6, math.sin(ang) * 0.6, h * 0.25), verts=6, name="guy_support")


def r_cooling_tower(p, M, w, d, h, paint):
    box(p, M["building"], (w, d, h * 0.8), (0, 0, h * 0.4), name="casing")
    cyl(p, M["carbon"], w * 0.38, 0.4, (0, 0, h * 0.8 + 0.2), name="fan_stack")
    for k in range(4):
        box(p, M["carbon"], (w * 0.65, 0.05, 0.04), (0, 0, h * 0.8 + 0.3), name="fan_blade").rotation_euler[2] = math.radians(45 * k)
    box(p, M["glass"], (w * 0.9, 0.02, h * 0.3), (0, -d * 0.5 - 0.01, h * 0.3), name="louvre")


def r_meter(p, M, w, d, h, paint):
    box(p, M["carbon"], (w, d, h), (0, 0, h / 2), name="meter_cabinet")
    box(p, M["screen"], (w * 0.6, 0.02, h * 0.15), (0, -d * 0.5 - 0.01, h * 0.7), name="display")
    cyl(p, M["copper"], 0.02, h * 0.3, (w * 0.3, 0, h + 0.1), verts=8, name="cable_gland")


def r_plate_hx(p, M, w, d, h, paint):
    box(p, M[paint], (w, d, h * 0.9), (0, 0, h * 0.5), name="plate_pack")
    for k in range(9):
        box(p, M["stainless"], (w * 1.02, 0.01, h * 0.88), (0, -d * 0.45 + k * d * 0.11, h * 0.5), name="plate")
    for s in (-1, 1):
        cyl(p, M["carbon"], 0.04, 0.2, (s * w * 0.3, d * 0.5 + 0.1, h * 0.8), axis="y", verts=10, name="nozzle")


def r_dispenser(p, M, w, d, h, paint):
    box(p, M[paint], (w, d, h * 0.65), (0, 0, h * 0.33), name="dispenser_body")
    box(p, M["screen"], (w * 0.6, 0.02, h * 0.15), (0, -d * 0.5 - 0.01, h * 0.55), name="display")
    cyl(p, M["rubber"], 0.015, 1.4, (w * 0.5 + 0.05, -d * 0.3, h * 0.4), verts=8, name="hose")
    box(p, M["carbon"], (w * 1.8, d * 1.6, 0.08), (0, 0, h * 0.95), name="canopy")
    for sx in (-1, 1):
        cyl(p, M["carbon"], 0.04, h * 0.9, (sx * w * 0.85, d * 0.7, h * 0.45), verts=8, name="canopy_post")


def r_rack(p, M, w, d, h, paint, cloud=False):
    box(p, M["carbon"], (w, d, h), (0, 0, h / 2), name="rack_frame")
    for k in range(8):
        box(p, M["screen"] if k % 2 == 0 else M["carbon"], (w * 0.85, 0.02, h * 0.07), (0, -d * 0.5 - 0.01, h * 0.12 + k * h * 0.1), name="server_unit")
    if cloud:
        dome(p, M["glass"], 0.35, (0, 0, h + 0.4), squash=0.7, name="cloud_marker")


def r_mast(p, M, w, d, h, paint):
    cyl(p, M["carbon"], 0.06, h, (0, 0, h / 2), verts=12, name="mast")
    box(p, M["stainless"], (0.4, 0.04, 0.04), (0, 0, h * 0.92), name="wind_sensor_arm")
    cyl(p, M["glass"], 0.08, 0.2, (0, 0, h * 0.97), verts=14, name="radiation_shield")
    box(p, M["carbon"], (0.8, 0.8, 0.1), (0, 0, 0.05), name="mast_base")


def r_pole(p, M, w, d, h, paint):
    cyl(p, M["carbon"], 0.06, h, (0, 0, h / 2), verts=12, name="pole")
    box(p, M["screen"], (0.14, 0.2, 0.12), (0, -0.05, h), name="camera_housing")
    cyl(p, M["glass"], 0.05, 0.04, (0, -0.16, h), axis="y", verts=14, name="lens")


def r_workstation(p, M, w, d, h, paint):
    box(p, M["carbon"], (w, d, 0.05), (0, 0, 0.75), name="desk_top")
    for sx in (-1, 1):
        box(p, M["carbon"], (0.05, d, 0.75), (sx * w * 0.45, 0, 0.37), name="desk_leg")
    box(p, M["screen"], (0.5, 0.03, 0.3), (0, 0.1, 1.0), name="monitor")


RECIPES = {
    "hopper": lambda p, M, w, d, h, c: r_hopper(p, M, w, d, h, c),
    "separator": lambda p, M, w, d, h, c: r_box_machine(p, M, w, d, h, c, drum=True),
    "conveyor": lambda p, M, w, d, h, c: r_conveyor(p, M, w, d, h, c),
    "shredder": lambda p, M, w, d, h, c: r_box_machine(p, M, w, d, h, c, rotors=2),
    "dryer": r_dryer,
    "screw": lambda p, M, w, d, h, c: r_conveyor(p, M, w, d, h, c, screw=True),
    "rotary_valve": lambda p, M, w, d, h, c: (cyl(p, M[c], w * 0.4, h * 0.6, (0, 0, h * 0.5), name="valve_body"),
                                              cyl(p, M["carbon"], w * 0.5, 0.05, (0, 0, h * 0.2), name="flange"),
                                              cyl(p, M["carbon"], w * 0.5, 0.05, (0, 0, h * 0.8), name="flange"),
                                              cyl(p, M["carbon"], 0.08, 0.3, (w * 0.5, 0, h * 0.5), axis="x", name="drive_motor")),
    "analyser": r_analyser, "instrument": r_instrument,
    "reactor": lambda p, M, w, d, h, c: r_vertical_vessel(p, M, w, d, h, c, lining=True, platform=True),
    "wgs_reactor": lambda p, M, w, d, h, c: r_vertical_vessel(p, M, w, d, h, c),
    "skid": r_skid,
    "drain": lambda p, M, w, d, h, c: (cone(p, M[c], w * 0.6, w * 0.12, h * 0.8, (0, 0, h * 0.5), name="drain_cone"),
                                       cyl(p, M["carbon"], 0.1, 0.2, (0, 0, h * 0.08), verts=12, name="slide_valve")),
    "bin": lambda p, M, w, d, h, c: (box(p, M[c], (w, d, h * 0.8), (0, 0, h * 0.55), name="bin_body"),
                                     box(p, M["carbon"], (w * 1.04, d * 1.04, 0.05), (0, 0, h * 0.95), name="lid"),
                                     [box(p, M["carbon"], (0.06, 0.06, h * 0.2), (sx * w * 0.4, sy * d * 0.4, h * 0.1), name="leg")
                                      for sx in (-1, 1) for sy in (-1, 1)]),
    "process_unit": lambda p, M, w, d, h, c: (r_cabinet(p, M, w, d, h, c), cyl(p, M["stainless"], 0.12, 0.8, (w * 0.3, 0, h + 0.5), verts=14, name="dust_extract_duct")),
    "silo": lambda p, M, w, d, h, c: (cyl(p, M[c], w / 2, h * 0.65, (0, 0, h * 0.6), name="silo_shell"),
                                      cone(p, M[c], w / 2, 0.1, h * 0.3, (0, 0, h * 0.15), name="silo_cone"),
                                      dome(p, M[c], w / 2, (0, 0, h * 0.93), squash=0.3, name="silo_roof"),
                                      [cyl(p, M["carbon"], 0.04, h * 0.2, (math.cos(math.radians(45 + 90 * a)) * w * 0.4, math.sin(math.radians(45 + 90 * a)) * w * 0.4, h * 0.1), verts=8, name="leg") for a in range(4)]),
    "cyclone": r_cyclone, "tower": r_tower,
    "bag_filter": lambda p, M, w, d, h, c: (box(p, M[c], (w, d, h * 0.55), (0, 0, h * 0.62), name="filter_housing"),
                                            cone(p, M[c], w * 0.7, w * 0.12, h * 0.3, (0, 0, h * 0.2), verts=4, name="dust_hopper").rotation_euler.__setitem__(2, math.pi / 4),
                                            box(p, M["carbon"], (w * 0.8, d * 0.3, 0.05), (0, -d * 0.5 - 0.01, h * 0.62), name="access_cover"),
                                            cyl(p, M["carbon"], 0.06, 0.3, (w * 0.5 + 0.15, 0, h * 0.7), axis="x", verts=12, name="inlet")),
    "adsorber": lambda p, M, w, d, h, c: r_vertical_vessel(p, M, w, d, h, c),
    "blower": lambda p, M, w, d, h, c: (box(p, M["carbon"], (w, d, 0.08), (0, 0, 0.04), name="baseplate"),
                                        cyl(p, M["carbon"], d * 0.4, w * 0.45, (-w * 0.25, 0, h * 0.45), axis="x", name="motor"),
                                        cyl(p, M[c], d * 0.45, d * 0.55, (w * 0.22, 0, h * 0.45), axis="y", name="volute"),
                                        cyl(p, M["carbon"], 0.07, 0.3, (w * 0.22, 0, h * 0.45 + d * 0.45), verts=12, name="outlet")),
    "tank_h": r_horizontal_vessel,
    "vessel_v": lambda p, M, w, d, h, c: r_vertical_vessel(p, M, w, d, h, c),
    "vessel_h": lambda p, M, w, d, h, c: r_horizontal_vessel(p, M, w, d, h, c),
    "hx": r_hx, "psa": r_psa,
    "membrane": lambda p, M, w, d, h, c: r_horizontal_vessel(p, M, w, d, h, c, banks=2),
    "container": r_container, "compressor": r_compressor, "bank": r_bank, "dispenser": r_dispenser, "cabinet": r_cabinet,
    "genset": r_genset, "microturbine": r_microturbine, "flare": r_flare, "cooling_tower": r_cooling_tower, "meter": r_meter,
    "plate_hx": r_plate_hx, "mast": r_mast, "pole": r_pole, "workstation": r_workstation,
    "rack": lambda p, M, w, d, h, c: r_rack(p, M, w, d, h, c),
}


def add_details(holder, M, it):
    """BL-3 extra detail on top of the recipe (ASSUMED, illustrative): manways, lifting lugs and cladding bands on vessels, level gauge and
    manway on horizontal tanks, idler rollers on conveyors. Detail never changes the footprint or the registry size."""
    r, w, d, h, c = it["recipe"], it["w"], it["d"], it["h"], "paint_" + it["zone"]
    if it["tag_of"] or it["id"] in L.NON_PHYSICAL:
        return
    if r in ("reactor", "wgs_reactor", "vessel_v", "adsorber", "tower", "psa"):
        rr = min(w, d) / 2.0 if r != "psa" else 0.15
        mw = max(0.05, min(0.13, rr * 0.55))
        cyl(holder, M["carbon"], mw * 1.25, 0.05, (0, -rr - 0.03, h * 0.35), axis="y", verts=16, name="manway_flange")
        cyl(holder, M["stainless"], mw, 0.03, (0, -rr - 0.07, h * 0.35), axis="y", verts=16, name="manway_cover")
        for sx in (-1, 1):
            box(holder, M["carbon"], (0.05, 0.04, 0.1), (sx * rr * 0.6, 0, h + 0.02), name="lifting_lug")
        if r in ("reactor", "wgs_reactor"):
            for z in (0.25, 0.45, 0.65, 0.8):
                cyl(holder, M["stainless"], rr * 1.06, 0.03, (0, 0, h * z), verts=24, name="cladding_band")
    elif r in ("tank_h", "vessel_h", "membrane"):
        box(holder, M["stainless"], (0.05, 0.05, 0.3), (w * 0.2, d / 2 + 0.04, h * 0.45), name="level_gauge")
        cyl(holder, M["carbon"], 0.1, 0.06, (-w * 0.2, 0, h * 0.95), verts=16, name="manway_flange")
        cyl(holder, M["stainless"], 0.08, 0.04, (-w * 0.2, 0, h * 0.95 + 0.04), verts=16, name="manway_cover")
    elif r in ("conveyor", "screw"):
        for k in range(1, int(w / 0.3)):
            cyl(holder, M["rubber"], 0.03, d * 0.95, (-w / 2 + k * 0.3, 0, h * 0.7), axis="y", verts=8, name="idler_roller")



# ----------------------------------------------------------------------------------------------------------- BL-3: access structure
# Platforms, ladders, cages, stairs and handrails. ASSUMED geometry (no DOK-ING drawing): heights follow the item height, widths are generic.
def handrails(p, M, cx, cy, z, sx, sy, h=1.0, name="handrail"):
    """Rectangular handrail (posts every ~1 m, top and mid rail) around a platform centred at (cx, cy) with size sx x sy at level z."""
    nx, ny = max(1, int(sx / 1.0)), max(1, int(sy / 1.0))
    for i in range(nx + 1):
        for sgn in (-1, 1):
            box(p, M["safety_yellow"], (0.04, 0.04, h), (cx - sx / 2 + sx * i / nx, cy + sgn * sy / 2, z + h / 2), name=name + "_post")
    for j in range(1, ny):
        for sgn in (-1, 1):
            box(p, M["safety_yellow"], (0.04, 0.04, h), (cx + sgn * sx / 2, cy - sy / 2 + sy * j / ny, z + h / 2), name=name + "_post")
    for sgn in (-1, 1):
        for zz in (h, h * 0.5):
            box(p, M["safety_yellow"], (sx, 0.03, 0.03), (cx, cy + sgn * sy / 2, z + zz), name=name + "_rail")
            box(p, M["safety_yellow"], (0.03, sy, 0.03), (cx + sgn * sx / 2, cy, z + zz), name=name + "_rail")


def platform(p, M, cx, cy, z, sx, sy, name="platform"):
    box(p, M["grating"], (sx, sy, 0.05), (cx, cy, z), name=name + "_grating")
    for sgn in (-1, 1):
        box(p, M["carbon"], (sx, 0.06, 0.1), (cx, cy + sgn * sy / 2, z - 0.07), name=name + "_beam")
    handrails(p, M, cx, cy, z, sx, sy)


def ladder(p, M, x, y, z_top, face="y", cage=True):
    """Vertical ladder with rungs every 0.3 m; a safety cage (hoops every 0.9 m) when taller than 2.4 m. face: wall the ladder stands on."""
    for sgn in (-1, 1):
        if face == "y":
            box(p, M["carbon"], (0.04, 0.04, z_top), (x + sgn * 0.2, y, z_top / 2), name="ladder_rail")
        else:
            box(p, M["carbon"], (0.04, 0.04, z_top), (x, y + sgn * 0.2, z_top / 2), name="ladder_rail")
    for k in range(1, int(z_top / 0.3)):
        if face == "y":
            box(p, M["carbon"], (0.4, 0.02, 0.02), (x, y, k * 0.3), name="rung")
        else:
            box(p, M["carbon"], (0.02, 0.4, 0.02), (x, y, k * 0.3), name="rung")
    if cage and z_top > 2.4:
        for zz in [2.2 + 0.9 * i for i in range(int((z_top - 2.2) / 0.9) + 1)]:
            cyl(p, M["safety_yellow"], 0.28, 0.02, (x, y + (0.28 if face == "y" else 0), zz), verts=14, name="cage_hoop")


def stair(p, M, x0, y_edge, z_top, length, width=0.9):
    """Straight stair rising toward the platform edge at (x0, y_edge): the top tread is at the edge, the foot is `length` metres away in -y."""
    n = max(3, int(z_top / 0.2))
    run = length / n
    for i in range(n):
        y = y_edge - (n - 1 - i) * run - run / 2
        box(p, M["grating"], (width, run * 0.95, 0.04), (x0, y, z_top * (i + 1) / n), name="tread")
    for sgn in (-1, 1):
        for k in range(7):
            t = k / 6
            box(p, M["safety_yellow"], (0.04, 0.04, 1.0), (x0 + sgn * width / 2, y_edge - length * (1 - t), z_top * t + 0.5), name="stair_post")
        box(p, M["safety_yellow"], (0.04, math.hypot(length, z_top), 0.03), (x0 + sgn * width / 2, y_edge - length / 2, z_top / 2 + 1.0), name="stair_rail").rotation_euler.__setitem__(0, math.atan2(z_top, length))


def add_access(holder, M, it):
    """Item-specific access structure (ASSUMED): which items get a ladder or a stair+platform is a rule on id/recipe and height."""
    i, h, w, d, r = it["id"], it["h"], it["w"], it["d"], it["recipe"]
    if it["tag_of"] or i in L.NON_PHYSICAL:
        return
    if i in ("FE-001", "GA-001", "EU-008", "GC-004"):                       # stair + platform at the top
        if i == "GA-001":
            z, sx = h * 0.62 + PLINTH, w * 1.5            # the reactor recipe already draws this platform
        else:
            z, sx = h * (0.6 if i == "FE-001" else 0.98) + PLINTH, max(w, d) + 0.9
            platform(holder, M, 0, 0, z - PLINTH, sx, sx, name="top_platform")
        stair(holder, M, 0, -sx / 2, z - PLINTH, 3.4)
    elif r in ("vessel_v", "wgs_reactor", "adsorber", "tower", "silo", "psa", "flare") and h >= 1.4:
        ladder(holder, M, w / 2 + 0.25, 0, h, cage=True)


# ----------------------------------------------------------------------------------------------------------- BL-3: documented links
def _tube(parent, mat, a, b, r, name="pipe"):
    a, b = Vector(a), Vector(b)
    v = b - a
    if v.length < 1e-6:
        return None
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=v.length, vertices=12, location=(a + b) / 2)
    o = bpy.context.object
    o.rotation_mode = "QUATERNION"
    o.rotation_quaternion = v.to_track_quat("Z", "Y")
    o.name = name
    return _finish(o, mat, parent)


def build_links(M, lay):
    """One Empty per documented link (named LINK_<from>_<to>) holding the pipe segments, elbows, end flanges and supports.
    Metadata says what it is: a model dependency, schematic routing, assumed diameter. Nothing here is a P&ID."""
    col = bpy.data.collections.new("08_Documented_Links")
    bpy.context.scene.collection.children.link(col)
    out = {}
    zone_of = {i["id"]: i["zone"] for i in lay}
    for r in K.route_all(lay):
        za, zb = zone_of[r["from"]], zone_of[r["to"]]
        pipe_mat = M["pipe_" + za] if za == zb else M["pipe"]
        root = bpy.data.objects.new("LINK_%s_%s" % (r["from"], r["to"]), None)
        col.objects.link(root)
        for k, v in (("link_from", r["from"]), ("link_to", r["to"]), ("link_kind", r["kind"]),
                     ("link_basis", "model dependency (engine depends_on), not a verified pipe"),
                     ("link_routing", "schematic, assumed"), ("link_points", json.dumps([[round(v, 3) for v in q] for q in r["points"]])), ("link_diameter", "assumed %.0f mm outer" % (K.PIPE_R * 2000))):
            root[k] = v
        before = set(bpy.data.objects)
        pts = r["points"]
        for q, w in zip(pts, pts[1:]):
            _tube(root, pipe_mat, q, w, K.PIPE_R, name="pipe_run")
        for q in pts[1:-1]:
            bpy.ops.mesh.primitive_uv_sphere_add(radius=K.PIPE_R * 1.08, location=q, segments=12, ring_count=8)
            _finish(bpy.context.object, pipe_mat, root).name = "elbow"
        for q, w in ((pts[0], pts[1]), (pts[-1], pts[-2])):
            d = (Vector(w) - Vector(q)).normalized()
            bpy.ops.mesh.primitive_cylinder_add(radius=K.PIPE_R * 1.7, depth=0.04, vertices=12, location=Vector(q) + d * 0.06)
            o = bpy.context.object
            o.rotation_mode = "QUATERNION"
            o.rotation_quaternion = d.to_track_quat("Z", "Y")
            _finish(o, M["carbon"], root).name = "flange"
        for (sx, sy, sz) in r["supports"]:
            box(root, M["carbon"], (0.14, 0.14, sz), (sx, sy, sz / 2), name="pipe_support_post")
            box(root, M["carbon"], (0.6, 0.1, 0.1), (sx, sy, sz - 0.1), name="pipe_support_beam")
        for o in set(bpy.data.objects) - before:
            for c in list(o.users_collection):
                c.objects.unlink(o)
            col.objects.link(o)
        out[(r["from"], r["to"])] = root
    return out


# ----------------------------------------------------------------------------------------------------------- site
def build_site(M):
    col = bpy.data.collections.new("00_Site")
    bpy.context.scene.collection.children.link(col)
    root = bpy.data.objects.new("Site", None)
    col.objects.link(root)
    made = []

    def part(o):
        for c in o.users_collection:
            c.objects.unlink(o)
        col.objects.link(o)
        o.parent = root
        made.append(o)

    # ground, perimeter road, zone pads
    sw, sd = L.SITE_W, L.SITE_D
    o = box(None, M["grass"], (sw + 30, sd + 30, 0.1), (sw / 2, sd / 2, -0.06), name="ground")
    part(o)
    for (cx, cy, w, d) in ((sw / 2, -3.0, sw + 8, 5.0), (sw / 2, sd + 3.0, sw + 8, 5.0), (-3.0, sd / 2, 5.0, sd - 2), (sw + 3.0, sd / 2, 5.0, sd - 2)):
        part(box(None, M["asphalt"], (w, d, 0.02), (cx, cy, 0.01), name="road"))
    for k in range(int(sw / 5.0)):                    # dashed centre line on the two long roads (decorative)
        for cy in (-3.0, sd + 3.0):
            part(box(None, M["marking"], (2.0, 0.12, 0.01), (2.5 + 5.0 * k, cy, 0.025), name="road_marking"))
    pads = L.zone_pads()
    for z, (x0, y0, x1, y1) in pads.items():
        part(box(None, M["concrete"], (x1 - x0, y1 - y0, 0.06), ((x0 + x1) / 2, (y0 + y1) / 2, 0.03), name="pad_" + z))
    # analyser shelter: three walls + roof, open front (so the instruments stay visible) ; control building: closed box shell, glass band
    x0, y0, x1, y1 = pads["SA"]
    for (cx, cy, w, d) in (((x0 + x1) / 2, y1 - 0.1, x1 - x0, 0.2), (x0 + 0.1, (y0 + y1) / 2, 0.2, y1 - y0), (x1 - 0.1, (y0 + y1) / 2, 0.2, y1 - y0)):
        part(box(None, M["building"], (w, d, 2.6), (cx, cy, 1.4), name="shelter_wall"))
    part(box(None, M["carbon"], (x1 - x0 + 0.4, y1 - y0 + 0.4, 0.12), ((x0 + x1) / 2, (y0 + y1) / 2, 2.75), name="shelter_roof"))
    x0, y0, x1, y1 = pads["AI"]
    for (cx, cy, w, d) in (((x0 + x1) / 2, y1 - 0.1, x1 - x0, 0.2), (x0 + 0.1, (y0 + y1) / 2, 0.2, y1 - y0), (x1 - 0.1, (y0 + y1) / 2, 0.2, y1 - y0)):
        part(box(None, M["building"], (w, d, 2.5), (cx, cy, 1.3), name="control_building_wall"))
    part(box(None, M["carbon"], (x1 - x0 + 0.4, y1 - y0 + 0.4, 0.12), ((x0 + x1) / 2, (y0 + y1) / 2, 2.62), name="control_roof"))
    return root


# ----------------------------------------------------------------------------------------------------------- main build
def build_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    M = make_materials()
    lay = L.build_layout()
    colls = {}
    for z in L.ZONES:
        c = bpy.data.collections.new("%s_%s" % (z, L.ZONE_NAMES[z].replace(" ", "_").replace("&", "and")))
        bpy.context.scene.collection.children.link(c)
        colls[z] = c
    build_site(M)
    roots = {}
    for it in lay:
        root = bpy.data.objects.new(it["id"], None)
        root.empty_display_type = "PLAIN_AXES"
        root.empty_display_size = 0.3
        colls[it["zone"]].objects.link(root)
        base_z = 0.0 if it["tag_of"] else PLINTH
        if it["tag_of"]:
            root.location = (it["x"], it["y"], it["z"] + PLINTH)
        else:
            root.location = (it["x"], it["y"], 0.0)
        # metadata (the digital-twin keys the spec asks for)
        for k, v in (("equipment_id", it["id"]), ("equipment_name", it["name"]), ("category", it["category"]),
                     ("geometry_status", it["geometry_status"]), ("data_provenance", it["data_provenance"]),
                     ("source_registry", it["source_registry"]), ("process_zone", L.ZONE_NAMES[it["zone"]]),
                     ("size_basis", it["size_basis"]), ("size_note", it["size_note"]), ("placement", it["placement"])):
            root[k] = v
        roots[it["id"]] = root
        before = set(bpy.data.objects)
        if not it["tag_of"]:
            plinth = box(root, M["concrete"], (it["w"] + 0.3, it["d"] + 0.3, PLINTH), (0, 0, PLINTH / 2), name="plinth")
            plinth.location.z = PLINTH / 2
        holder = bpy.data.objects.new(it["id"] + "_geo", None)      # holds the recipe parts above the plinth
        colls[it["zone"]].objects.link(holder)
        holder.parent = root
        holder.location = (0, 0, 0 if it["tag_of"] else PLINTH)
        paint = "paint_" + it["zone"]
        if it["tag_of"] or it["recipe"] == "instrument":
            r_instrument(holder, M, it["w"], it["d"], it["h"], paint)
        elif it["id"] in L.NON_PHYSICAL:
            r_rack(holder, M, it["w"], it["d"], it["h"], paint, cloud=(it["id"] == "AI-010"))
        else:
            RECIPES[it["recipe"]](holder, M, it["w"], it["d"], it["h"], paint)
            add_details(holder, M, it)
            add_access(holder, M, it)
        for o in set(bpy.data.objects) - before:                # every part belongs to the item's zone collection
            for c in list(o.users_collection):
                c.objects.unlink(o)
            colls[it["zone"]].objects.link(o)
    links = build_links(M, lay)
    return lay, roots, links, M


def build_labels(M, lay):
    """Render-only ID signs above each physical item (not exported to the GLB: the tab draws its own). Decorative, text = registry ID."""
    col = bpy.data.collections.new("09_Labels")
    bpy.context.scene.collection.children.link(col)
    for it in lay:
        if it["tag_of"] or it["id"] in L.NON_PHYSICAL:
            continue
        z = PLINTH + it["h"] + 0.75
        bpy.ops.object.text_add(location=(it["x"], it["y"] - 0.24, z), rotation=(math.radians(68), 0, 0))
        t = bpy.context.object
        t.name = "label_" + it["id"]
        t.data.body = it["id"]
        t.data.size = 0.34
        t.data.align_x = "CENTER"
        t.data.extrude = 0.01
        t.data.materials.append(M["label"])
        th = math.radians(68)
        up, nrm = Vector((0, math.cos(th), math.sin(th))), Vector((0, -math.sin(th), math.cos(th)))
        pc = Vector((it["x"], it["y"] - 0.24, z)) + up * 0.17 - nrm * 0.04      # plate centred behind the glyphs, thin side along the normal
        bpy.ops.mesh.primitive_cube_add(size=1, location=pc, rotation=(th, 0, 0))
        b = bpy.context.object
        b.scale = (1.0, 0.46, 0.03)
        b.name = "label_plate_" + it["id"]
        b.data.materials.append(M["label_plate"])
        for o in (t, b):
            for c in list(o.users_collection):
                c.objects.unlink(o)
            col.objects.link(o)
    return col


def validate_scene(lay, roots, links=None):
    ids = [i["id"] for i in lay]
    assert len(roots) == 91 and set(roots) == set(ids), "an assembly is missing"
    reg = {r["id"]: r for r in L.load_registry()}
    problems = []
    for i, ob in roots.items():
        for k in ("equipment_id", "equipment_name", "category", "geometry_status", "data_provenance", "source_registry", "process_zone"):
            if k not in ob.keys():
                problems.append((i, "missing " + k))
        if ob["equipment_id"] != i or ob["equipment_name"] != reg[i]["name"] or ob["category"] != reg[i]["category"]:
            problems.append((i, "registry mismatch"))
        n = sum(1 for c in ob.children_recursive if c.type == "MESH")
        if n < 1:
            problems.append((i, "no geometry"))
    assert not problems, problems
    zones_present = {ob["process_zone"] for ob in roots.values()}
    assert len(zones_present) == 7, zones_present
    links = links or {}
    expected = set(K.load_links())
    assert set(links) == expected, "link set differs from data/plant_links.json"
    for (a, b), ob in links.items():
        assert ob["link_from"] == a and ob["link_to"] == b and a in roots and b in roots, (a, b)
        assert sum(1 for c in ob.children_recursive if c.type == "MESH") >= 3, (a, b)
    return {"links": len(links), "assemblies": len(roots), "unique_ids": len(set(roots)), "zones": len(zones_present),
            "mesh_objects": sum(1 for o in bpy.data.objects if o.type == "MESH"),
            "triangles": sum(len(o.data.polygons) for o in bpy.data.objects if o.type == "MESH")}


def add_cameras_and_lights():
    sc = bpy.context.scene
    w = bpy.data.worlds.new("sky")
    w.use_nodes = True
    sc.world = w
    bg = w.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.55, 0.65, 0.78, 1.0)
    bg.inputs[1].default_value = 0.9
    try:   # BL-5: what the camera sees (a pale sky gradient) is separate from the light the scene receives (neutral, so the ground stays green)
        nt = w.node_tree
        lp = nt.nodes.new("ShaderNodeLightPath")
        mix = nt.nodes.new("ShaderNodeMixShader")
        out = nt.nodes["World Output"]
        light = nt.nodes.new("ShaderNodeBackground")
        light.inputs[0].default_value = (0.85, 0.88, 0.92, 1.0)
        light.inputs[1].default_value = 0.55
        sky = nt.nodes.new("ShaderNodeTexSky")
        sky.sun_disc = False
        sky.sun_elevation = math.radians(35)
        cam_bg = nt.nodes.new("ShaderNodeBackground")
        cam_bg.inputs[1].default_value = 1.3
        nt.links.new(sky.outputs["Color"], cam_bg.inputs[0])
        nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
        nt.links.new(light.outputs[0], mix.inputs[1])
        nt.links.new(cam_bg.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs["Surface"])
    except Exception as exc:                              # a Blender without these nodes keeps the flat colour
        print("sky setup not used:", exc)
    bpy.ops.object.light_add(type="SUN", location=(20, -20, 40))
    sun = bpy.context.object
    sun.data.energy = 3.5
    sun.data.angle = math.radians(2.5)                    # soft shadow edge
    sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(35))
    views = {"isometric": ((-14, -22, 30), (32, 22, 1.5)), "aerial": ((32, 23, 80), (32, 23, 0)),
             "feed_and_gasification": ((-2, -6, 9), (16, 9, 1.5)), "gas_cleaning": ((20, 5, 14), (28, 19, 1.0)),
             "hydrogen": ((0, 17, 9), (26, 29, 1.2)), "utilities": ((-3, 30, 6), (16, 37, 1.2)), "control_and_analysers": ((40, 14, 7), (53, 23, 1.5))}
    cams = {}
    for name, (loc, tgt) in views.items():
        bpy.ops.object.camera_add(location=loc)
        cam = bpy.context.object
        cam.name = "cam_" + name
        cam.data.lens = 28 if name != "aerial" else 22
        cam.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        cams[name] = cam
    return cams


def render(cam, path, samples=40, res=(1600, 900)):
    sc = bpy.context.scene
    sc.camera = cam
    sc.render.engine = "CYCLES"
    sc.view_settings.view_transform = "Standard"     # AgX washed the zone colours out
    sc.view_settings.exposure = -0.4
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.cycles.device = "CPU"
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def main(argv):
    args = {"out": "build/blender", "blend": False, "views": "isometric", "samples": 40, "res": (1600, 900)}
    it = iter(argv)
    for a in it:
        if a == "--out":
            args["out"] = next(it)
        elif a == "--blend":
            args["blend"] = True
        elif a == "--views":
            args["views"] = next(it)
        elif a == "--samples":
            args["samples"] = int(next(it))
        elif a == "--res":
            args["res"] = tuple(int(v) for v in next(it).split("x"))
    os.makedirs(args["out"], exist_ok=True)
    lay, roots, links, M = build_scene()
    report = validate_scene(lay, roots, links)
    cams = add_cameras_and_lights()
    glb = os.path.join(args["out"], "plant.glb")
    for o in cams.values():
        o.select_set(False)
    bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", export_extras=True, export_apply=True, export_cameras=False, export_lights=False)
    report["glb_bytes"] = os.path.getsize(glb)
    build_labels(M, lay)                                  # after the GLB export on purpose: signs are for the renders only
    mapping = [{"equipment_id": i["id"], "name": i["name"], "blender_object": i["id"], "zone": i["zone"], "recipe": i["recipe"],
                "size_basis": i["size_basis"], "geometry_status": i["geometry_status"]} for i in lay]
    with open(os.path.join(args["out"], "equipment_mapping.json"), "w") as fh:
        json.dump(mapping, fh, indent=1, sort_keys=True)
    if args["blend"]:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(args["out"], "HYGAS_AI_Industrial_Plant.blend"))
    for v in (args["views"].split(",") if args["views"] else []):
        render(cams[v], os.path.join(args["out"], "render_%s.png" % v), samples=args["samples"], res=args["res"])
    with open(os.path.join(args["out"], "validation_report.json"), "w") as fh:
        json.dump(report, fh, indent=1, sort_keys=True)
    print("VALIDATION", json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
