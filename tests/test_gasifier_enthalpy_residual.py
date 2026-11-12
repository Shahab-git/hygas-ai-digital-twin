"""Task A4.3: the residual of the GA-001 enthalpy balance and its reconciliation with the existing implied heat duty (python/gasifier_enthalpy.py: enthalpy_residual, enthalpy_residual_cases).
READ-ONLY; not validation against DOK-ING data (none exists); not a plant prediction. The residual is the heat the gasifier would have to add (+) or remove (-) to leave at its imposed temperature,
from a balance built on Assumed and Estimated inputs, with tar, shell loss and feed/recycle sensible heat Missing.

What is guarded: the exact split of the difference to balance_audit.gasifier_energy / (GA-001, EnergyBalance) into four named sensible-heat terms (nothing left unexplained), each term against a hand
calculation, the one-for-one dependence of the residual on the LHV case, that the sensible part does not depend on the LHV, the agreement with the engine's published energy entry, behaviour for a
non-air agent, and that the functions change nothing they read."""
import copy

import pytest

from _fakes import FakeSupabase, patched_supabase
from python import balance_audit as ba
from python import cycle_clock
from python import gasifier_enthalpy as ge
from python import tab1_integration as t1
from test_tail_gas_mode import _mode, _const

N = 20
KW = 1.0 / 3600.0


def _pair(overrides=None):
    cycle_clock.set_elapsed_hours(None)
    with patched_supabase(FakeSupabase()):
        return (t1.build_live_snapshot(n_cycles=N, overrides=overrides)[0], t1.build_live_snapshot(n_cycles=N - 1, overrides=overrides)[0])


@pytest.fixture(scope="module")
def heat_only():
    return _pair()


@pytest.fixture(scope="module")
def regasify():
    return _pair(_mode("regasify"))


@pytest.fixture(scope="module")
def oxygen():
    return _pair({("GA-001-INPUT", "gasifying_agent"): _const("oxygen")})


@pytest.fixture(scope="module")
def steam_only():
    return _pair({("GA-001-INPUT", "gasifying_agent"): _const("steam_only_0.4")})


# ---------------------------------------------------------------- the reconciliation
@pytest.mark.parametrize("pair_name", ["heat_only", "regasify", "oxygen", "steam_only"])
@pytest.mark.parametrize("case", list(ba.lhv_cases()))
def test_the_difference_to_the_existing_duty_splits_exactly_into_four_sensible_terms(request, pair_name, case):
    snap, prev = request.getfixturevalue(pair_name)
    r = ge.enthalpy_residual(snap, prev, ba.lhv_cases()[case])
    t = r["difference_terms"]
    assert set(t) == {"d_gas_kw", "d_graphite_kw", "d_oxidant_kw", "d_steam_kw"}
    assert r["difference_kw"] == pytest.approx(t["d_gas_kw"] + t["d_graphite_kw"] - t["d_oxidant_kw"] - t["d_steam_kw"], abs=1e-9)
    assert abs(r["difference_unexplained_kw"]) < 1e-9
    assert r["residual_kw"] == pytest.approx(r["audit_implied_duty_kw"] + r["difference_kw"], abs=1e-12)


def test_each_difference_term_against_a_hand_calculation(heat_only):
    snap, prev = heat_only
    lhv = 17.5
    r = ge.enthalpy_residual(snap, prev, lhv)
    ga = ba.ga001_terms(snap, prev)
    by = {x["name"]: x for x in ga["terms"]}
    t_gas = r["t_gas_c"]
    gas = by["product gas (wet)"]["species"]
    d_gas = sum(n * (ge.sensible_enthalpy_j_mol(sp, t_gas + 273.15) - ba.CP_J_MOLK[sp] * (t_gas - 25.0)) for sp, n in gas.items()) / 1000.0 * KW
    steam = by["gasifier steam"]["species"]["H2O"]
    d_steam = steam * (ge.sensible_enthalpy_j_mol("H2O", 350.0 + 273.15) - ba.CP_J_MOLK["H2O"] * (350.0 - 25.0)) / 1000.0 * KW
    ox = {"O2": ga["air_o2_mol_h"], "N2": ga["air_n2_mol_h"]}
    d_ox = sum(n * (ge.sensible_enthalpy_j_mol(sp, 200.0 + 273.15) - ba.CP_J_MOLK[sp] * (200.0 - 25.0)) for sp, n in ox.items()) / 1000.0 * KW
    c_solid = ga["feed_atoms"]["C"] + ga["recycle_atoms"]["C"] - (gas["CO"] + gas["CO2"] + gas["CH4"])
    kg_c = c_solid * 12.011 / 1000.0
    d_gr = (c_solid * ge.sensible_enthalpy_j_mol("C", t_gas + 273.15) / 1000.0 - kg_c * ba.SOLIDS_CP_KJ_KGK[0] * (t_gas - 25.0)) * KW
    t = r["difference_terms"]
    assert t["d_gas_kw"] == pytest.approx(d_gas, rel=1e-9)
    assert t["d_steam_kw"] == pytest.approx(d_steam, rel=1e-9)
    assert t["d_oxidant_kw"] == pytest.approx(d_ox, rel=1e-9)
    assert t["d_graphite_kw"] == pytest.approx(d_gr, rel=1e-6)          # 12.011 vs the engine's atomic mass: well inside 1e-6 of this small term


# ---------------------------------------------------------------- the residual itself
def test_the_residual_moves_one_for_one_with_the_lhv_case_and_the_sensible_part_does_not_move(heat_only):
    snap, prev = heat_only
    a, b = ge.enthalpy_residual(snap, prev, 15.0), ge.enthalpy_residual(snap, prev, 20.0)
    f = float(snap[("GA-001-INPUT", "dry_feed_rate_kg_h")]["value"])
    assert b["residual_kw"] - a["residual_kw"] == pytest.approx(-5.0 * f / 3.6, rel=1e-9)
    assert b["sensible_kw"] == pytest.approx(a["sensible_kw"], abs=1e-12)
    assert a["residual_kw"] > 0 > b["residual_kw"]                       # the DOK-ING LHV range straddles the point where the imposed temperature needs no external heat


def test_residual_is_formation_plus_sensible_and_a_percentage_of_the_feed_chemical_energy(heat_only):
    snap, prev = heat_only
    r = ge.enthalpy_residual(snap, prev, 17.5)
    assert r["residual_kw"] == pytest.approx(r["formation_kw"] + r["sensible_kw"], abs=1e-12)
    f = float(snap[("GA-001-INPUT", "dry_feed_rate_kg_h")]["value"])
    assert r["residual_pct_of_feed_chemical_energy"] == pytest.approx(100.0 * r["residual_kw"] / (f * 17.5 / 3.6), rel=1e-12)
    assert r["reading"] == ("the gasifier would need to ADD heat" if r["residual_kw"] > 0 else "the gasifier would have to REMOVE heat")
    assert "NOT validation" in r["status"] and len(r["missing_terms"]) == 3


def test_the_audit_duty_in_the_residual_equals_the_one_the_engine_publishes(heat_only, regasify):
    """(GA-001, EnergyBalance) is the engine's published energy entry: its implied duty per LHV case is the number the residual is reconciled against. heat_only: identical; regasify: the engine
    entry reads the recycle from the same snapshot, this function from the previous one, equal once the loop has converged (cycle 20)."""
    for pair, tol in ((heat_only, 1e-9), (regasify, 1e-6)):
        snap, prev = pair
        cases = snap[("GA-001", "EnergyBalance")]["value"]["cases"]
        for name, r in ge.enthalpy_residual_cases(snap, prev).items():
            assert r["audit_implied_duty_kw"] == pytest.approx(cases[name]["implied_gasifier_heat_duty_kw"], abs=tol)


def test_cases_cover_the_four_lhv_cases_of_the_audit(heat_only):
    snap, prev = heat_only
    cs = ge.enthalpy_residual_cases(snap, prev)
    assert list(cs) == list(ba.lhv_cases())
    for name, r in cs.items():
        assert r["lhv_mj_kg"] == ba.lhv_cases()[name]


def test_a_non_air_agent_runs_and_a_steam_only_agent_has_a_zero_oxidant_stream(oxygen, steam_only):
    r = ge.enthalpy_residual(*oxygen, 17.5)
    assert r["streams"]["in"][2]["name"].startswith("oxidant O2 (agent oxygen)")
    s = ge.enthalpy_residual(*steam_only, 17.5)
    assert s["streams"]["in"][2]["formation_kw"] == 0.0 and s["streams"]["in"][2]["sensible_kw"] == 0.0
    assert s["difference_terms"]["d_oxidant_kw"] == 0.0


def test_the_functions_change_nothing_they_read(heat_only):
    snap, prev = heat_only
    b_s, b_p = copy.deepcopy(snap), copy.deepcopy(prev)
    ge.enthalpy_residual_cases(snap, prev)
    assert snap == b_s and prev == b_p


def test_an_active_recycle_without_the_previous_snapshot_is_refused(regasify):
    snap, _ = regasify
    with pytest.raises(ba.AuditInputMissing):
        ge.enthalpy_residual(snap, None, 17.5)
