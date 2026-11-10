"""
Circularity scoring v1 — ash and carbon black byproduct value.

Builds on the ported gasifier mass balance in gasifier_mass_balance.py
to produce three things:

  1. Byproduct mass flow rates (kg/h): ash from the 10 % ash fraction
     (gasifier_mass_balance.py, a project assumption inside DOK-ING's 5-15 %
     range); carbon black from the live engine's DERIVED figure (P1-05(d), see
     ENGINE_CARBON_BLACK_FRACTION_OF_DRY_FEED below), no longer from the legacy
     5 % datasheet rule.

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
from . import fe_feed_handling, gasifier_mass_balance

# P0-FB2 Step 1 (feed basis): the circularity default is DRY SOLIDS, derived from the two feed-chain constants, not a typed
# number. 41.67 kg/h is the project's as-received feed (DOK-ING stated 1 tonne/day, no wet/dry basis; the as-received reading is a
# project decision) and 10 % inlet moisture is an Assumed value (FE-005, inside DOK-ING's 5-15 (20) % range). The result,
# 37.503 kg/h, is exactly what FE-005 hands to GA-001 from cycle 2, so the static ash (10 %) and carbon black (5 % rule) below
# agree with the live engine's ash. It is dry solids INCLUDING ash. Gasifier_mass_balance.DEFAULT_DRY_FEED_KG_H (41.67, as-received
# under a dry name) is NOT changed here: it is still the cycle-1 fallback and the default of byproduct_mass_flows() (task P0-FB2 step 2).
DEFAULT_DRY_SOLIDS_FEED_KG_H = (fe_feed_handling.FE001_DEFAULT_DELIVERY_RATE_KG_H
                                * (1.0 - fe_feed_handling.FE005_INLET_MOISTURE_FRACTION))

# P1-05(d): carbon black comes from the engine's derived value, not the legacy 5 % rule. The engine publishes it in ("GA-001","CarbonAccounting")
# as unconverted carbon x split (carbon_black_kg_h, Calculated; conversion 0.90 and split 1.0 are Assumed). This static module cannot import the
# live engine, so the converged engine value at the DEFAULT feed (2.01319 kg/h on 37.503 kg/h dry solids, default tail_gas_mode "regasify",
# 30 cycles) is PINNED here as a fraction of the dry feed. tests/test_p1_05d_carbon_black.py recomputes it from the engine and fails on drift.
# SIMPLIFICATIONS: (1) it is the default-mode figure ("heat_only" and other conversions/splits give other values); (2) scaling it linearly with the
# feed is approximate (the engine is not linear above about +20 % feed: 2.416 kg/h at +30 % against 2.617 linear); (3) the legacy rule gave 5 %.
ENGINE_CARBON_BLACK_FRACTION_OF_DRY_FEED = 0.0536807889


def derived_carbon_black_kg_h(dry_feed_kg_h):
    """Carbon black (kg/h) at the engine's derived fraction of the dry feed (see ENGINE_CARBON_BLACK_FRACTION_OF_DRY_FEED for its limits)."""
    return dry_feed_kg_h * ENGINE_CARBON_BLACK_FRACTION_OF_DRY_FEED


# Our own assumed placeholder market prices — NOT sourced from any real
# market data. Directional reasoning only: ash aggregate (GA-009: EN
# 12620 construction-grade, crushed/stabilized/screened bulk material)
# is a low-value bulk product; carbon black (GA-010: "industrial/pigment
# grade... not premium tire-grade", per that equipment's own datasheet
# remarks) is a higher-value but still non-premium product. Replace both
# the moment real offtake-agreement or market pricing exists.
ASH_PRICE_EUR_PER_KG = 0.03
CARBON_BLACK_PRICE_EUR_PER_KG = 0.40


def circularity_summary(dry_feed_kg_h=DEFAULT_DRY_SOLIDS_FEED_KG_H):
    """Returns dry_feed_kg_h, ash_kg_h, carbon_black_kg_h, per-stream and
    total revenue-potential (EUR/h, assumption-based — see module
    docstring), and diversion_fraction (real mass ratio, no price
    assumption)."""
    flows = gasifier_mass_balance.byproduct_mass_flows(dry_feed_kg_h)
    ash_kg_h = flows["ash_kg_h"]
    cb_rule_kg_h = flows["carbon_black_kg_h"]                    # legacy 5 % rule, kept only as the cross-check
    cb_kg_h = derived_carbon_black_kg_h(dry_feed_kg_h)

    ash_revenue = ash_kg_h * ASH_PRICE_EUR_PER_KG
    cb_revenue = cb_kg_h * CARBON_BLACK_PRICE_EUR_PER_KG
    total_byproduct_kg_h = ash_kg_h + cb_kg_h
    diversion_fraction = total_byproduct_kg_h / dry_feed_kg_h if dry_feed_kg_h > 0 else 0.0

    return {
        "dry_feed_kg_h": dry_feed_kg_h,
        "ash_kg_h": ash_kg_h,
        "carbon_black_kg_h": cb_kg_h,
        "carbon_black_rule_kg_h": cb_rule_kg_h,
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
