"""G5-07: the cross-module disagreement figures (python/disagreement_rows.py) are reproduced and pinned.

CHARACTERIZATION: these tests record the differences the repo has TODAY between the live engine and the registry / DOK-ING statements. They do not say the
live value or the registry value is right. When a figure changes on purpose (an owner decision, new DOK-ING data), update the pinned number in the same change.
P1-06d: the figures are pinned for the REAL default (tail_gas_mode "heat_only" since P1-06) and, separately, for the mode they were first measured on
(`regasify`, the numbers of docs/cross_module_disagreements.md as dated 2026-11-06), selected explicitly through the engine override.
Offline: counting fake store, no credentials, no network."""
import pytest

from _fakes import FakeSupabase, patched_supabase
from python import cycle_clock, disagreement_rows as dr, tab1_integration as t1
from test_tail_gas_mode import _mode


def _build(mode):
    cycle_clock.set_elapsed_hours(None)
    fake = FakeSupabase()
    with patched_supabase(fake):
        snap = t1.build_live_snapshot(n_cycles=30, overrides=_mode(mode) if mode else None)[0]
    return {(r["row"], r["quantity"]): r for r in dr.rows(snap, dr.load_registry())}


@pytest.fixture(scope="module")
def table():
    return _build(None)                       # the real default


@pytest.fixture(scope="module")
def table_regasify():
    return _build("regasify")                 # explicit: the mode of the 2026-11-06 figures


def _check(table, row, quantity, live, registry, unit):
    r = table[(row, quantity)]
    assert r["unit"] == unit
    assert r["live"] == pytest.approx(live, abs=5e-3)
    assert r["registry"] == pytest.approx(registry, abs=1e-9)
    assert r["difference_pct"] == pytest.approx(100.0 * (r["live"] - registry) / registry, rel=1e-12)


# live figures per mode: (heat_only = real default, regasify = the 2026-11-06 figures)
SYNGAS = {"heat_only": (24.785, 22.064, 12.113, 1.799, 39.240), "regasify": (27.452, 21.461, 9.799, 1.645, 39.642)}
FLOW = {"heat_only": (78.787, 36.148, 55.747, 76.976), "regasify": (102.753, 38.096, 78.024, 78.790)}
PLANT = {"heat_only": (39.983, 5.733, 8.448, 96.667, 1.688), "regasify": (51.992, 7.376, 10.717, 96.667, 2.013)}


@pytest.fixture(params=["heat_only", "regasify"])
def mode_table(request, table, table_regasify):
    return request.param, (table if request.param == "heat_only" else table_regasify)


def test_the_default_table_is_the_heat_only_table(table):
    assert table[(1, "syngas H2, dry")]["live"] == pytest.approx(SYNGAS["heat_only"][0], abs=5e-3)


def test_syngas_composition_against_the_registry_expected_table(mode_table):
    mode, table = mode_table
    for (q, reg), live in zip((("syngas H2, dry", 32.5), ("syngas CO, dry", 28.0), ("syngas CO2, dry", 22.0), ("syngas CH4, dry", 8.0), ("syngas N2, dry", 10.0)), SYNGAS[mode]):
        _check(table, 1, q, live, reg, "vol%")


def test_flow_psa_feed_hydrogen_and_recovery_against_the_registry(mode_table):
    mode, table = mode_table
    flow, feed_h2, h2, rec = FLOW[mode]
    _check(table, 3, "syngas flow, dry", flow, 50.0, "Nm3/h")
    _check(table, 4, "PSA feed H2", feed_h2, 55.0, "vol%")
    _check(table, 7, "hydrogen product", h2, 50.0, "kg/day")
    _check(table, 7, "hydrogen product (registry design)", h2, 44.4, "kg/day")
    _check(table, 8, "PSA recovery", rec, 75.0, "%")


def test_cooling_heat_exchanger_scrubber_and_carbon_black_figures(mode_table):
    mode, table = mode_table
    cool, hot, cold, hcl, cb = PLANT[mode]
    _check(table, 10, "EU-008 cooling demand", cool, 20.0, "kW")
    _check(table, 11, "HB-003 hot-side duty", hot, 5.0, "kW")
    _check(table, 11, "HB-003 cold-side duty", cold, 5.0, "kW")
    _check(table, 12, "GC-009 HCl removal", hcl, 97.0, "%")
    _check(table, 13, "carbon black, engine (derived) vs 5 % rule", cb, 1.87515, "kg/h")
