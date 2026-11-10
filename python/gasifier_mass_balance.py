"""
Gasifier ash / carbon-black mass balance — ported, not new physics.

Checked first, per the task: no ash/carbon-black mass balance logic
exists anywhere in this Python codebase before this file. kinetics.py
only covers WGS reaction kinetics (downstream of the gasifier), psa.py
only covers PSA recovery, and there's no gasifier module at all yet
(see CLAUDE.md's "Not yet built" list — the gasifier itself isn't
implemented in either language). What DOES already exist: the
design-basis mass fractions themselves, embedded as remarks in the real
equipment datasheets already in this repo
(data/equipment_registry.json, sourced from
data/MSW_Equipment_Datasheets_Interactive.xlsx):

  GA-005 (Bed Drain / Ash Discharge System): "Ash discharge rate
  (design) = 10% of feed ... Matches the 10% ash content (dry basis)
  already used in the mass/energy balance."

  GA-008 (Carbon Black Recovery & Classification Unit): "Design
  capacity = 3 kg/h ... Margin above the ~1.88 kg/h nominal (2.25 kg/h
  at 120% turndown) already used in the mass/energy balance" —
  1.88 kg/h / 37.5 kg/h dry feed (the ORIGINAL design point, see
  RECALIBRATION below) ≈ 5% carbon black content (dry basis),
  internally consistent with the 3.75 kg/h ash figure GA-009's remarks
  independently state (37.5 kg/h x 10% = 3.75 kg/h) at that original
  design point.

byproduct_mass_flows() below reproduces that ORIGINAL linear
relationship — dry feed rate x mass fraction — read off the equipment
datasheets. It is a port of an existing design-basis number, not a new
model, and adds no physics beyond what the datasheets already imply.

RECALIBRATION (feed rate only — the fractions did NOT change): DOK-ING's
real, formal RFI response (data/dokink_rfi_answers.md, RFI #1) confirmed
a nominal capacity of 1 tonne/day (1,000 kg/day = 41.67 kg/h), superseding
this module's original 900 kg/day (37.5 kg/h) design point. Per the
user's explicit recalibration decision, DEFAULT_DRY_FEED_KG_H is updated
to 41.67; ASH_FRACTION (0.10) and CARBON_BLACK_FRACTION (0.05) are
UNCHANGED — they are percentages of feed mass, not absolute quantities,
and nothing in DOK-ING's response revises them. Only the absolute
byproduct mass flows scale, by the same ~11.12% the feed rate itself
scaled (41.67 / 37.5): ash 3.750 -> 4.167 kg/h, carbon black
1.875 -> 2.0835 kg/h (see self-test below for the live-computed values).

HONEST CONSEQUENCE of this recalibration, not smoothed over: the new
computed ash/carbon-black figures (4.167 / 2.0835 kg/h) no longer match
GA-008's/GA-009's own STATED NOMINAL figures (1.88 / 3.75 kg/h) as
closely as the original 37.5 kg/h design point did — those registry
entries are DOK-ING's own static historical datasheet data (data/
equipment_registry.json), not recalculated here, and this project's
hard rule forbids editing that file to match a downstream physics
decision. Both new figures remain comfortably inside GA-008's (3 kg/h)
and GA-009's (5 kg/h) stated DESIGN CAPACITY margins, so no equipment
capacity is exceeded — but the close numeric agreement between the
computed mass-balance figures and the equipment's own nominal sizing,
which existed at the old design point, is now a real, growing gap
worth knowing about, not a discrepancy to hide.

P1-05(c) (2026-11-10, feed-basis correction): DEFAULT_DRY_FEED_KG_H is now what its name says, the DRY solids (41.67 x (1 - 0.10) = 37.503 kg/h, the figure FE-005 hands
to GA-001); the as-received 41.67 has its own name, DEFAULT_AS_RECEIVED_FEED_KG_H. The default of byproduct_mass_flows() and GA-001's cycle-1 fallback follow it, so ash and
the 5 % carbon-black rule at the default are 3.7503 / 1.87515 kg/h (they were 4.167 / 2.0835 on the as-received figure). The history above is kept as written.
"""

DEFAULT_AS_RECEIVED_FEED_KG_H = 41.67  # DOK-ING's stated 1 tonne/day (1,000 kg/day, data/dokink_rfi_answers.md, RFI #1) / 24 h. DOK-ING did NOT state wet or dry; treating it as AS-RECEIVED is a project decision (Phase 3).
DEFAULT_INLET_MOISTURE_FRACTION = 0.10  # Assumed (DOK-ING gave 5-15 (20) %, basis not stated); the same value as fe_feed_handling.FE005_INLET_MOISTURE_FRACTION (tests/test_p1_05c_feed_basis.py pins the equality; this module imports nothing).
# P1-05(c): this constant is now what its name says, DRY solids (including ash): 41.67 x (1 - 0.10) = 37.503 kg/h, the figure FE-005 hands to GA-001. It held the as-received 41.67 before.
DEFAULT_DRY_FEED_KG_H = DEFAULT_AS_RECEIVED_FEED_KG_H * (1.0 - DEFAULT_INLET_MOISTURE_FRACTION)
ASH_FRACTION = 0.10           # UNCHANGED by the recalibration — GA-005: "10% ash content (dry basis)", a fraction of feed mass, not an absolute quantity
CARBON_BLACK_FRACTION = 0.05  # UNCHANGED by the recalibration — derived from GA-008's stated 1.88 kg/h nominal / the ORIGINAL 37.5 kg/h dry feed design point


def byproduct_mass_flows(dry_feed_kg_h=DEFAULT_DRY_FEED_KG_H):
    """Ported linear mass balance: byproduct rate = dry feed rate x mass
    fraction. Returns {"ash_kg_h", "carbon_black_kg_h"}."""
    return {
        "ash_kg_h": dry_feed_kg_h * ASH_FRACTION,
        "carbon_black_kg_h": dry_feed_kg_h * CARBON_BLACK_FRACTION,
    }


if __name__ == "__main__":
    flows = byproduct_mass_flows()
    print(f"At design dry feed rate ({DEFAULT_DRY_FEED_KG_H} kg/h, dry solids of DOK-ING's stated 1,000 kg/day as-received):")
    print(f"  Ash:          {flows['ash_kg_h']:.4f} kg/h  (the old 37.5 kg/h design point gave 3.750; "
          f"GA-009's own stated nominal is ~3.75 kg/h -- since P1-05(c) the dry solids 37.503 kg/h nearly match it again)")
    print(f"  Carbon black: {flows['carbon_black_kg_h']:.4f} kg/h  (the old 37.5 kg/h design point gave 1.875; "
          f"GA-008's own stated nominal is ~1.88 kg/h)")
    print(f"  Scale factor vs. the old 37.5 kg/h design point: {DEFAULT_DRY_FEED_KG_H / 37.5:.4f} "
          f"(+{(DEFAULT_DRY_FEED_KG_H / 37.5 - 1) * 100:.2f}%)")

    print("\nFraction-unchanged check: ASH_FRACTION/CARBON_BLACK_FRACTION must be untouched by the recalibration")
    assert ASH_FRACTION == 0.10, f"REGRESSION: ASH_FRACTION changed to {ASH_FRACTION}, should still be 0.10."
    assert CARBON_BLACK_FRACTION == 0.05, f"REGRESSION: CARBON_BLACK_FRACTION changed to {CARBON_BLACK_FRACTION}, should still be 0.05."
    print("PASS: both fractions are exactly what they were before the recalibration -- only the absolute "
          "feed rate input changed.")

    print("\nLinearity check: doubling dry feed rate must exactly double both outputs")
    base = byproduct_mass_flows(DEFAULT_DRY_FEED_KG_H)
    doubled = byproduct_mass_flows(DEFAULT_DRY_FEED_KG_H * 2)
    print(f"  ash: {base['ash_kg_h']:.4f} -> {doubled['ash_kg_h']:.4f}  "
          f"(ratio={doubled['ash_kg_h']/base['ash_kg_h']:.6f}, expect 2.000000)")
    print(f"  carbon black: {base['carbon_black_kg_h']:.4f} -> {doubled['carbon_black_kg_h']:.4f}  "
          f"(ratio={doubled['carbon_black_kg_h']/base['carbon_black_kg_h']:.6f}, expect 2.000000)")
    assert abs(doubled["ash_kg_h"] / base["ash_kg_h"] - 2.0) < 1e-9
    assert abs(doubled["carbon_black_kg_h"] / base["carbon_black_kg_h"] - 2.0) < 1e-9
    print("PASS: genuinely linear, not just plausible-looking numbers.")

