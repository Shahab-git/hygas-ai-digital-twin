"""Task A4.4: the sensitivity of the GA-001 enthalpy residual to the imposed gas temperature (python/gasifier_enthalpy.py: temperature_sensitivity; scripts/run_enthalpy_temperature_sensitivity.py).
READ-ONLY; not a prediction of the temperature the plant would settle at; not validation against DOK-ING data (none exists). The engine is run unchanged with ("GA-001-INPUT", "operating_temperature_C")
overridden; GA-001 has no energy balance, so the temperature enters only through the water-gas-shift equilibrium constant.

What is guarded: the table's arithmetic (rows sorted, slopes), the refusal of a mislabelled or too-short input, that the exact reconciliation of A4.3 holds at EVERY temperature, that the 950 degC point equals
the A4.3 residual of the default snapshot, the shape of the result (the sensible part rises, the formation part moves little, so the residual rises with temperature), that the LHV case moves the residual far more
than the whole 850-950 degC span, and that the script prints the table offline and writes nothing."""
import importlib.util
import os

import pytest

from _fakes import FakeSupabase, patched_supabase
from python import cycle_clock
from python import gasifier_enthalpy as ge
from python import tab1_integration as t1

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(ROOT, "scripts", "run_enthalpy_temperature_sensitivity.py")
TEMPS = (850.0, 900.0, 950.0)


def _script():
    spec = importlib.util.spec_from_file_location("run_enthalpy_temperature_sensitivity", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def snaps():
    return _script().build(TEMPS, "heat_only")


@pytest.fixture(scope="module")
def default_pair():
    cycle_clock.set_elapsed_hours(None)
    with patched_supabase(FakeSupabase()):
        return t1.build_live_snapshot(n_cycles=20)[0], t1.build_live_snapshot(n_cycles=19)[0]


def test_rows_are_sorted_by_temperature_and_the_slope_is_the_change_per_100_k(snaps):
    rows = ge.temperature_sensitivity({t: snaps[t] for t in reversed(TEMPS)}, 17.5)
    assert [r["t_c"] for r in rows] == sorted(TEMPS)
    assert rows[0]["slope_kw_per_100k"] is None
    for a, b in zip(rows, rows[1:]):
        assert b["slope_kw_per_100k"] == pytest.approx(100.0 * (b["residual_kw"] - a["residual_kw"]) / (b["t_c"] - a["t_c"]), rel=1e-12)


def test_a_mislabelled_temperature_or_a_single_temperature_is_refused(snaps):
    with pytest.raises(ValueError):
        ge.temperature_sensitivity({850.0: snaps[900.0], 900.0: snaps[900.0]}, 17.5)
    with pytest.raises(ValueError):
        ge.temperature_sensitivity({900.0: snaps[900.0]}, 17.5)


@pytest.mark.parametrize("lhv", [15.0, 17.5, 20.0])
def test_the_exact_reconciliation_of_a43_holds_at_every_temperature(snaps, lhv):
    for r in ge.temperature_sensitivity(snaps, lhv):
        assert abs(r["difference_unexplained_kw"]) < 1e-9
        assert r["residual_kw"] == pytest.approx(r["formation_kw"] + r["sensible_kw"], abs=1e-12)


def test_the_950_point_equals_the_a43_residual_of_the_default_snapshot(snaps, default_pair):
    row = ge.temperature_sensitivity(snaps, 17.5)[-1]
    ref = ge.enthalpy_residual(*default_pair, 17.5)
    assert row["t_c"] == 950.0
    assert row["residual_kw"] == pytest.approx(ref["residual_kw"], abs=1e-9)
    assert row["audit_implied_duty_kw"] == pytest.approx(ref["audit_implied_duty_kw"], abs=1e-9)


def test_the_sensible_part_rises_with_temperature_and_the_formation_part_moves_little(snaps):
    rows = ge.temperature_sensitivity(snaps, 17.5)
    assert all(b["sensible_kw"] > a["sensible_kw"] for a, b in zip(rows, rows[1:]))
    assert all(b["residual_kw"] > a["residual_kw"] for a, b in zip(rows, rows[1:]))
    assert abs(rows[-1]["formation_kw"] - rows[0]["formation_kw"]) < 2.0           # measured about 0.65 kW over 850-950 degC
    assert rows[-1]["sensible_kw"] - rows[0]["sensible_kw"] > 3.0                  # measured about 4.7 kW


def test_the_lhv_case_moves_the_residual_far_more_than_the_whole_temperature_span(snaps):
    lo, hi = ge.temperature_sensitivity(snaps, 15.0), ge.temperature_sensitivity(snaps, 20.0)
    temperature_span = lo[-1]["residual_kw"] - lo[0]["residual_kw"]
    lhv_span = lo[-1]["residual_kw"] - hi[-1]["residual_kw"]
    assert temperature_span > 0
    assert lhv_span > 5.0 * temperature_span                                      # measured about 52 kW against 5.3 kW


def test_the_composition_follows_the_engine_h2_falls_as_the_temperature_rises(snaps):
    rows = ge.temperature_sensitivity(snaps, 17.5)
    assert all(b["h2_mol_pct_dry"] < a["h2_mol_pct_dry"] for a, b in zip(rows, rows[1:]))


def test_the_script_prints_the_table_offline_and_writes_nothing(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    before = set(os.listdir(ROOT))
    _script().main(["--temps", "900", "950", "--lhv", "17.5"])
    out = capsys.readouterr().out
    assert "tail_gas_mode = heat_only" in out and "not validation against DOK-ING data" in out
    assert "| 900 |" in out and "| 950 |" in out and "LHV 17.5 MJ/kg dry" in out
    assert set(os.listdir(ROOT)) == before and os.listdir(tmp_path) == []
