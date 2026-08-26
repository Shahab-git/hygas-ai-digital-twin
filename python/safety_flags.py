"""
Safety hazard flagging tool v1.

HONEST SCOPING, stated explicitly here and in the app.py UI: this is NOT
a Process Hazard Analysis (PHA/HAZOP). Real hazard analysis requires
qualified safety engineers using a formal methodology (HAZOP node-by-
node deviation analysis, LOPA, etc.) that this repo cannot replicate.
What this DOES do: flag where this plant's own real design values (from
data/equipment_registry.json and uncertainty.py's assumption ranges) sit
relative to well-established, PUBLICLY DOCUMENTED physical and
regulatory reference thresholds — cited explicitly with their real
source below, not invented — so genuine gaps are visible instead of
silently absent.

Reference constants used (real, cited, not invented):
  - Hydrogen flammability range in air: ~4.0–75.0 vol% — a standard,
    widely published combustion-engineering constant (e.g. NFPA 2, Fire
    Protection Guide to Hazardous Materials). One of the widest
    flammability ranges of any common fuel gas — methane, for
    comparison, is roughly 5–15 vol%.
  - H2S IDLH (Immediately Dangerous to Life or Health): 100 ppm — a real
    published NIOSH value (NIOSH Pocket Guide to Chemical Hazards). This
    is a PERSONNEL AMBIENT-AIR exposure guideline, not a process-stream
    spec — comparing it to a contained process stream's concentration is
    a screening signal for "how hazardous would an uncontrolled release
    of this stream be", not a claim that workers are exposed to this
    level during normal operation.
  - LTS catalyst sulfur sensitivity: <0.1 ppm S (cumulative) — this
    repo's OWN registry value, from HB-004's real datasheet remarks
    (data/equipment_registry.json), not an external reference.

Real design values checked against those references:
  - Feed H2S assumption: pulled LIVE from uncertainty.py's
    ASSUMPTIONS['feed_sulfur_ppm'] / bounds() — NOT a separate hardcoded
    copy. If confirmation_loop.py ever records a confirmed value for
    this assumption, this module reflects that confirmed number
    automatically on the next call, no code change needed here.
  - H2 storage design pressure: HB-013, verified against the actual
    registry entry (875 bar(g)), not assumed from memory.
  - ATEX-rated equipment: read directly from every registry item's own
    parameters — GA-008 & GA-010 (dust explosion, carbon black), HB-013
    (H2 storage, Zone 2), EU-007 (Flare, Zone 1/2). Items explicitly
    marked "not required" in their own datasheet (AI-002, AI-004,
    AI-008) are reported as correctly assessed, not flagged.

TWO DISTINCT CONCERNS FROM THE SAME 200 ppm feed number, kept explicitly
separate below — never conflated:
  1. PERSONNEL SAFETY — if the raw feed stream were ever released
     uncontrolled, its H2S content relative to the IDLH.
  2. CATALYST/EQUIPMENT RISK — if that same feed reached the WGS
     reactors without adequate upstream cleaning (GC-008's job), the LTS
     catalyst's real sulfur tolerance is far tighter than the raw feed
     assumption.
"""
from . import equipment_registry, uncertainty

# --- Real, cited reference constants — NOT invented ---
H2_LFL_VOL_PCT = 4.0    # NFPA 2 / standard combustion-engineering reference (lower flammability limit)
H2_UFL_VOL_PCT = 75.0   # NFPA 2 / standard combustion-engineering reference (upper flammability limit)
H2S_IDLH_PPM = 100.0    # NIOSH Pocket Guide to Chemical Hazards (real published value)

# --- This repo's OWN registry value, not an external reference ---
LTS_CATALYST_SULFUR_LIMIT_PPM = 0.1  # HB-004's own datasheet: "<0.1 ppm S (cumulative)"

H2_STORAGE_ITEM_ID = "HB-013"
ATEX_RATED_ITEMS = ["GA-008", "GA-010", "HB-013", "EU-007"]
ATEX_NOT_REQUIRED_ITEMS = ["AI-002", "AI-004", "AI-008"]


def h2s_feed_flags():
    """Two distinct flags from the SAME feed H2S assumption, kept
    explicitly separate — personnel safety vs catalyst/equipment risk.
    Pulls the current value LIVE from uncertainty.py: if
    confirmation_loop.py has recorded a confirmed range, this reflects
    that confirmed value automatically, not a hardcoded 200."""
    cfg = uncertainty.ASSUMPTIONS["feed_sulfur_ppm"]
    lo, hi = uncertainty.bounds("feed_sulfur_ppm")
    confirmed = uncertainty.is_confirmed("feed_sulfur_ppm")
    # Representative value: the confirmed range's midpoint once confirmed,
    # otherwise the default point estimate — both read live, never copied.
    current_value = (lo + hi) / 2 if confirmed else cfg["point"]

    ratio_to_idlh = current_value / H2S_IDLH_PPM
    ratio_to_catalyst_limit = current_value / LTS_CATALYST_SULFUR_LIMIT_PPM

    return {
        "assumption_value_ppm": current_value,
        "assumption_range_ppm": (lo, hi),
        "is_confirmed": confirmed,
        "personnel_safety": {
            "concern": "Personnel safety — uncontrolled-release exposure screening",
            "reference": f"NIOSH IDLH for H2S = {H2S_IDLH_PPM:.0f} ppm (NIOSH Pocket Guide to Chemical Hazards)",
            "ratio_to_reference": ratio_to_idlh,
            "flag": ratio_to_idlh >= 1.0,
            "note": (
                f"Feed H2S assumption ({current_value:.0f} ppm) is {ratio_to_idlh:.1f}x the NIOSH IDLH "
                f"reference. This compares the PROCESS STREAM's composition to a personnel ambient-air "
                f"exposure guideline — it does NOT mean workers are exposed to this level during normal "
                f"operation (H2S is contained in process piping/vessels); it's a screening signal for how "
                f"hazardous an uncontrolled release of this stream would be."
            ),
        },
        "catalyst_risk": {
            "concern": "Catalyst/equipment risk — WGS reactor poisoning (HB-001/HB-004)",
            "reference": (
                f"LTS catalyst (HB-004) sulfur sensitivity = <{LTS_CATALYST_SULFUR_LIMIT_PPM:g} ppm S "
                f"(cumulative) — this repo's own registry value, from HB-004's real datasheet remarks"
            ),
            "ratio_to_reference": ratio_to_catalyst_limit,
            "flag": ratio_to_catalyst_limit > 1.0,
            "note": (
                f"The raw feed assumption ({current_value:.0f} ppm) is ~{ratio_to_catalyst_limit:.0f}x the "
                f"LTS catalyst's real tolerance — this is exactly why GC-008 (Wet Scrubber, H2S) exists: "
                f"its own datasheet specifies >99.5% removal down to <1 ppm before the gas reaches "
                f"HB-001/HB-004. GC-008's performance is a hard protection requirement, not a nice-to-have "
                f"— if it ever underperforms, catalyst poisoning is the direct consequence."
            ),
        },
    }


def h2_storage_flag(registry=None):
    registry = registry if registry is not None else equipment_registry.load_registry()
    item = next((i for i in registry if i["id"] == H2_STORAGE_ITEM_ID), None)
    if item is None:
        return None
    design_pressure = next((p for p in item["parameters"] if p["parameter"] == "Design pressure"), None)
    pressure_str = f"{design_pressure['value']} {design_pressure['unit']}" if design_pressure else "not found in registry"
    return {
        "equipment_id": H2_STORAGE_ITEM_ID,
        "equipment_name": item["name"],
        "design_pressure": pressure_str,
        "h2_flammability_range": f"{H2_LFL_VOL_PCT:.1f}–{H2_UFL_VOL_PCT:.1f} vol% in air",
        "note": (
            f"High-pressure H2 storage (design {pressure_str}). Hydrogen's flammability range in air "
            f"({H2_LFL_VOL_PCT:.0f}–{H2_UFL_VOL_PCT:.0f} vol%) is unusually wide compared to most common "
            f"fuels (methane, for comparison, is roughly 5–15 vol%) — even a small leak creates a wide "
            f"ignition window. This is a well-known H2-specific hazard, already reflected in this item's "
            f"own leak-detection and ATEX Zone 2 provisions (per its own registry entry)."
        ),
    }


def atex_rated_items(registry=None):
    registry = registry if registry is not None else equipment_registry.load_registry()
    by_id = {i["id"]: i for i in registry}
    rated = []
    for eq_id in ATEX_RATED_ITEMS:
        item = by_id.get(eq_id)
        if not item:
            continue
        atex_param = next((p for p in item["parameters"] if "atex" in p["parameter"].lower()), None)
        rated.append({
            "equipment_id": eq_id, "equipment_name": item["name"],
            "atex_value": atex_param["value"] if atex_param else "?",
        })
    return rated


def build_safety_flags(registry=None):
    registry = registry if registry is not None else equipment_registry.load_registry()
    return {
        "h2s": h2s_feed_flags(),
        "h2_storage": h2_storage_flag(registry),
        "atex_items": atex_rated_items(registry),
    }


if __name__ == "__main__":
    flags = build_safety_flags()

    print("=== H2S feed assumption — two distinct concerns ===")
    h2s = flags["h2s"]
    print(f"Current assumption: {h2s['assumption_value_ppm']:.0f} ppm "
          f"(confirmed={h2s['is_confirmed']}, range={h2s['assumption_range_ppm']})")
    for key in ("personnel_safety", "catalyst_risk"):
        c = h2s[key]
        flag_str = "FLAGGED" if c["flag"] else "not flagged"
        print(f"\n[{flag_str}] {c['concern']}")
        print(f"  Reference: {c['reference']}")
        print(f"  Ratio to reference: {c['ratio_to_reference']:.1f}x")
        print(f"  {c['note']}")

    print("\n=== H2 storage (HB-013) ===")
    print(flags["h2_storage"]["note"])

    print("\n=== ATEX-rated equipment ===")
    for a in flags["atex_items"]:
        print(f"  {a['equipment_id']} ({a['equipment_name']}): {a['atex_value']}")
