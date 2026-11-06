"""G5-07: the cross-module disagreement figures (python/disagreement_rows.py) are reproduced and pinned.

CHARACTERIZATION: these tests record the differences the repo has TODAY between the live engine and the registry / DOK-ING statements. They do not say the
live value or the registry value is right. When a figure changes on purpose (an owner decision, new DOK-ING data), update the pinned number in the same change.
Offline: counting fake store, no credentials, no network."""
import pytest

from _fakes import FakeSupabase, patched_supabase
from python import cycle_clock, disagreement_rows as dr, tab1_integration as t1


@pytest.fixture(scope="module")
def table():
    cycle_clock.set_elapsed_hours(None)
    fake = FakeSupabase()
    with patched_supabase(fake):
        snap = t1.build_live_snapshot(n_cycles=30)[0]
    return {(r["row"], r["quantity"]): r for r in dr.rows(snap, dr.load_registry())}


def _check(table, row, quantity, live, registry, unit):
    r = table[(row, quantity)]
    assert r["unit"] == unit
    assert r["live"] == pytest.approx(live, abs=5e-3)
    assert r["registry"] == pytest.approx(registry, abs=1e-9)
    assert r["difference_pct"] == pytest.approx(100.0 * (r["live"] - registry) / registry, rel=1e-12)


def test_syngas_composition_against_the_registry_expected_table(table):
    for q, live, reg in (("syngas H2, dry", 27.452, 32.5), ("syngas CO, dry", 21.461, 28.0), ("syngas CO2, dry", 9.799, 22.0),
                         ("syngas CH4, dry", 1.645, 8.0), ("syngas N2, dry", 39.642, 10.0)):
        _check(table, 1, q, live, reg, "vol%")


def test_flow_psa_feed_hydrogen_and_recovery_against_the_registry(table):
    _check(table, 3, "syngas flow, dry", 102.753, 50.0, "Nm3/h")
    _check(table, 4, "PSA feed H2", 38.096, 55.0, "vol%")
    _check(table, 7, "hydrogen product", 78.024, 50.0, "kg/day")
    _check(table, 7, "hydrogen product (registry design)", 78.024, 44.4, "kg/day")
    _check(table, 8, "PSA recovery", 78.790, 75.0, "%")


def test_cooling_heat_exchanger_scrubber_and_carbon_black_figures(table):
    _check(table, 10, "EU-008 cooling demand", 51.992, 20.0, "kW")
    _check(table, 11, "HB-003 hot-side duty", 7.376, 5.0, "kW")
    _check(table, 11, "HB-003 cold-side duty", 10.717, 5.0, "kW")
    _check(table, 12, "GC-009 HCl removal", 96.667, 97.0, "%")
    _check(table, 13, "carbon black, engine (derived) vs 5 % rule", 2.013, 1.87515, "kg/h")


def test_the_formatted_table_lists_every_row(table):
    text = dr.format_table(list(table.values()))
    assert text.count("\n") == len(table) + 1 and "No tolerance" not in text
