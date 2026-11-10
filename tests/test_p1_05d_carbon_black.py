"""P1-05(d): the static carbon black (circularity.py, the GA-008 / GA-010 estimate fills, the app's Circularity section) is the engine's DERIVED value,
not the legacy 5 % rule. Guards: the pinned fraction equals the converged engine value (fails on drift); the legacy rule and the engine's cross-check are
untouched; ash is untouched; the engine publishes the same numbers as before (no engine change). Offline."""
import os
import sys

import pytest

REAL_TAIL_GAS_DEFAULT = True      # P1-06: this module tests the engine on its REAL default (heat_only); tests/conftest.py does not restore the old default for it

sys.path.insert(0, os.path.dirname(__file__))
from _fakes import FakeSupabase, patched_supabase
from python import circularity, cycle_clock
from python import equipment_engineering_estimates as eee
from python import gasifier_mass_balance as gmb
from python import tab1_integration as t1


@pytest.fixture(scope="module")
def snap():
    cycle_clock.set_elapsed_hours(None)
    with patched_supabase(FakeSupabase()):
        return t1.build_live_snapshot(n_cycles=30)[0]


def test_the_pinned_fraction_equals_the_converged_engine_value(snap):
    acc = snap[("GA-001", "CarbonAccounting")]["value"]
    feed = snap[("GA-001-INPUT", "dry_feed_rate_kg_h")]["value"]
    assert feed == pytest.approx(circularity.DEFAULT_DRY_SOLIDS_FEED_KG_H, abs=1e-9)
    assert circularity.ENGINE_CARBON_BLACK_FRACTION_OF_DRY_FEED == pytest.approx(acc["carbon_black_kg_h"] / feed, rel=1e-8)
    assert circularity.derived_carbon_black_kg_h(feed) == pytest.approx(acc["carbon_black_kg_h"], rel=1e-8)


def test_circularity_summary_before_and_after():
    s = circularity.circularity_summary()
    assert s["carbon_black_kg_h"] == pytest.approx(1.687635, abs=1e-5)            # was 1.87515 (2.01319 with the previous regasify default, P1-06)
    assert s["carbon_black_rule_kg_h"] == pytest.approx(1.87515, abs=1e-9)
    assert s["carbon_black_revenue_eur_h"] == pytest.approx(1.687635 * circularity.CARBON_BLACK_PRICE_EUR_PER_KG, abs=1e-5)     # 0.675, was 0.750 (0.805 with regasify)
    assert s["ash_kg_h"] == pytest.approx(3.7503, abs=1e-9) and s["ash_revenue_eur_h"] == pytest.approx(3.7503 * 0.03, abs=1e-9)   # ash untouched
    assert s["diversion_fraction"] == pytest.approx(0.10 + 0.045, rel=1e-9)   # 14.5 % (P1-06; 15.37 % with regasify), was 15.00 %


def test_the_fills_carry_the_derived_figure():
    got = {(i, r["parameter"]): r["value"] for i, secs in eee.ESTIMATE_FILLS.items() for rows in secs.values() for r in rows}
    assert got[("GA-008", "Estimated carbon-black-laden fines inflow rate")] == "~1.688"
    assert got[("GA-010", "Estimated recovered carbon-black inflow rate (from GA-008)")] == ">=1.60"
    assert eee._GA_ASH_KG_H == pytest.approx(3.7503, abs=1e-9)


def test_the_legacy_rule_and_the_engine_cross_check_are_untouched(snap):
    assert gmb.CARBON_BLACK_FRACTION == 0.05 and gmb.ASH_FRACTION == 0.10
    assert gmb.byproduct_mass_flows(41.67)["carbon_black_kg_h"] == pytest.approx(2.0835, abs=1e-9)
    cross = snap[("GA-001", "CarbonAccounting")]["value"]["datasheet_cross_check"]
    assert cross["datasheet_rule_kg_h"] == pytest.approx(1.87515, abs=1e-9)


def test_the_linear_scaling_is_an_approximation_that_is_stated():
    """The fraction scales linearly with the entered feed; the engine is not linear above about +20 % feed (2.416 vs 2.617 kg/h at +30 %). The docstring says so."""
    assert "approximate" in circularity.__doc__ + open(circularity.__file__).read()
    assert circularity.derived_carbon_black_kg_h(2 * 37.503) == pytest.approx(2 * circularity.derived_carbon_black_kg_h(37.503), rel=1e-12)
