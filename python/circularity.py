"""
Circularity scoring v1 — ash and carbon black byproduct value.

Builds on the ported gasifier mass balance in gasifier_mass_balance.py
to produce three things:

  1. Byproduct mass flow rates (kg/h) — real, linear mass-balance
     numbers sourced from the equipment datasheets (see
     gasifier_mass_balance.py's docstring), not assumptions.

  2. A revenue-potential estimate, using an assumed market price per kg
     for each byproduct. These prices are OUR OWN reasonable placeholder
     assumptions, explicitly NOT sourced from any real market pricing
     data — there is no real market data in this project yet. Same
     honesty standard as psa.py's SELECTIVITY constants and
     predictive_maintenance.py's activity thresholds: stated plainly
     here, not presented as more rigorous than it is.

  3. A "diversion from landfill" fraction: total byproduct mass / total
     dry feed mass. This one needs NO price assumption at all — it's a
     real mass-balance ratio, computed directly from the (real) mass
     flows above.
"""
from . import gasifier_mass_balance

# Our own assumed placeholder market prices — NOT sourced from any real
# market data. Directional reasoning only: ash aggregate (GA-009: EN
# 12620 construction-grade, crushed/stabilized/screened bulk material)
# is a low-value bulk product; carbon black (GA-010: "industrial/pigment
# grade... not premium tire-grade", per that equipment's own datasheet
# remarks) is a higher-value but still non-premium product. Replace both
# the moment real offtake-agreement or market pricing exists.
ASH_PRICE_EUR_PER_KG = 0.03
CARBON_BLACK_PRICE_EUR_PER_KG = 0.40


def circularity_summary(dry_feed_kg_h=gasifier_mass_balance.DEFAULT_DRY_FEED_KG_H):
    """Returns dry_feed_kg_h, ash_kg_h, carbon_black_kg_h, per-stream and
    total revenue-potential (EUR/h, assumption-based — see module
    docstring), and diversion_fraction (real mass ratio, no price
    assumption)."""
    flows = gasifier_mass_balance.byproduct_mass_flows(dry_feed_kg_h)
    ash_kg_h = flows["ash_kg_h"]
    cb_kg_h = flows["carbon_black_kg_h"]

    ash_revenue = ash_kg_h * ASH_PRICE_EUR_PER_KG
    cb_revenue = cb_kg_h * CARBON_BLACK_PRICE_EUR_PER_KG
    total_byproduct_kg_h = ash_kg_h + cb_kg_h
    diversion_fraction = total_byproduct_kg_h / dry_feed_kg_h if dry_feed_kg_h > 0 else 0.0

    return {
        "dry_feed_kg_h": dry_feed_kg_h,
        "ash_kg_h": ash_kg_h,
        "carbon_black_kg_h": cb_kg_h,
        "ash_revenue_eur_h": ash_revenue,
        "carbon_black_revenue_eur_h": cb_revenue,
        "total_revenue_eur_h": ash_revenue + cb_revenue,
        "diversion_fraction": diversion_fraction,
    }


if __name__ == "__main__":
    s = circularity_summary()
    print(f"At design dry feed rate ({s['dry_feed_kg_h']} kg/h):")
    print(f"  Ash:          {s['ash_kg_h']:.3f} kg/h  ->  €{s['ash_revenue_eur_h']:.3f}/h "
          f"(@ €{ASH_PRICE_EUR_PER_KG}/kg, assumed placeholder)")
    print(f"  Carbon black: {s['carbon_black_kg_h']:.3f} kg/h  ->  €{s['carbon_black_revenue_eur_h']:.3f}/h "
          f"(@ €{CARBON_BLACK_PRICE_EUR_PER_KG}/kg, assumed placeholder)")
    print(f"  Total revenue potential: €{s['total_revenue_eur_h']:.3f}/h "
          f"(€{s['total_revenue_eur_h']*8760:,.0f}/yr at 100% uptime — illustrative only)")
    print(f"  Diversion from landfill: {s['diversion_fraction']*100:.2f}% of dry feed mass "
          f"(real mass-balance ratio, no price assumption)")
