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
  1.88 kg/h / 37.5 kg/h dry feed ≈ 5% carbon black content (dry basis),
  internally consistent with the 3.75 kg/h ash figure GA-009's remarks
  independently state (37.5 kg/h x 10% = 3.75 kg/h).

byproduct_mass_flows() below reproduces that ORIGINAL linear
relationship — dry feed rate x mass fraction — read off the equipment
datasheets. It is a port of an existing design-basis number, not a new
model, and adds no physics beyond what the datasheets already imply.
"""

DEFAULT_DRY_FEED_KG_H = 37.5  # design-basis dry feed rate (equipment_registry: FE-001/GA-001 chain)
ASH_FRACTION = 0.10           # GA-005: "10% ash content (dry basis)"
CARBON_BLACK_FRACTION = 0.05  # derived from GA-008's stated 1.88 kg/h nominal / 37.5 kg/h dry feed


def byproduct_mass_flows(dry_feed_kg_h=DEFAULT_DRY_FEED_KG_H):
    """Ported linear mass balance: byproduct rate = dry feed rate x mass
    fraction. Returns {"ash_kg_h", "carbon_black_kg_h"}."""
    return {
        "ash_kg_h": dry_feed_kg_h * ASH_FRACTION,
        "carbon_black_kg_h": dry_feed_kg_h * CARBON_BLACK_FRACTION,
    }


if __name__ == "__main__":
    flows = byproduct_mass_flows()
    print(f"At design dry feed rate ({DEFAULT_DRY_FEED_KG_H} kg/h):")
    print(f"  Ash:          {flows['ash_kg_h']:.3f} kg/h  (expect 3.750, matches GA-009's stated ~3.75 kg/h)")
    print(f"  Carbon black: {flows['carbon_black_kg_h']:.3f} kg/h  (expect 1.875, matches GA-008's stated ~1.88 kg/h)")

    print("\nLinearity check: doubling dry feed rate must exactly double both outputs")
    base = byproduct_mass_flows(37.5)
    doubled = byproduct_mass_flows(75.0)
    print(f"  ash: {base['ash_kg_h']:.4f} -> {doubled['ash_kg_h']:.4f}  "
          f"(ratio={doubled['ash_kg_h']/base['ash_kg_h']:.6f}, expect 2.000000)")
    print(f"  carbon black: {base['carbon_black_kg_h']:.4f} -> {doubled['carbon_black_kg_h']:.4f}  "
          f"(ratio={doubled['carbon_black_kg_h']/base['carbon_black_kg_h']:.6f}, expect 2.000000)")
    assert abs(doubled["ash_kg_h"] / base["ash_kg_h"] - 2.0) < 1e-9
    assert abs(doubled["carbon_black_kg_h"] / base["carbon_black_kg_h"] - 2.0) < 1e-9
    print("PASS: genuinely linear, not just plausible-looking numbers.")
