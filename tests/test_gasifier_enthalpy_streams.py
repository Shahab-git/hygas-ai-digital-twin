"""Task A4.2: the stream enthalpies of GA-001 (python/gasifier_enthalpy.py: feed_formation_kw, stream_enthalpies). READ-ONLY; not validation against DOK-ING data (none exists);
not a plant prediction. The residual of the balance is task A4.3 and is NOT tested (or computed) here.

What is guarded: the one convention (H = formation + sensible, kW, elements at 298.15 K), the LHV-derived feed formation against an identity a reader can check by hand (a pure-methane
feed has methane's own formation enthalpy), the exact identity between the formation part and the chemical-energy terms balance_audit.gasifier_energy already publishes (two independent
routes to the same number), the sensible parts against NASA-9 evaluated by hand, that the function changes nothing it reads, and that nothing in the engine, the runtime or the app imports it."""
import copy
import os

import pytest

from _fakes import FakeSupabase, patched_supabase
from python import balance_audit as ba
from python import cycle_clock
from python import gasifier_enthalpy as ge
from python import tab1_integration as t1
from test_tail_gas_mode import _mode

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
N = 20          # the tail-gas recycle has converged by cycle 20 (as test_balance_audit)
KW = 1.0 / 3600.0


@pytest.fixture(scope="module")
def pair():
    """(snapshot, previous snapshot) on the REAL default (heat_only)."""
    cycle_clock.set_elapsed_hours(None)
    with patched_supabase(FakeSupabase()):
        return t1.build_live_snapshot(n_cycles=N)[0], t1.build_live_snapshot(n_cycles=N - 1)[0]


@pytest.fixture(scope="module")
def pair_regasify():
    cycle_clock.set_elapsed_hours(None)
    with patched_supabase(FakeSupabase()):
        return (t1.build_live_snapshot(n_cycles=N, overrides=_mode("regasify"))[0], t1.build_live_snapshot(n_cycles=N - 1, overrides=_mode("regasify"))[0])


# ---------------------------------------------------------------- the feed formation enthalpy
def test_a_pure_methane_feed_has_methanes_own_formation_enthalpy():
    """Hand-checkable: 10 mol/h of CH4 (C 10, H 40), LHV chosen as methane's own (802.3 kJ/mol): the derived formation is 10 x DHf(CH4)."""
    lhv_kj_mol = ba.LHV_KJ_MOL["CH4"]
    m_kg_h = 10 * 16.043 / 1000.0
    lhv_mj_kg = 10 * lhv_kj_mol / 1000.0 / m_kg_h
    assert ge.feed_formation_kw(10.0, 40.0, m_kg_h, lhv_mj_kg) == pytest.approx(10 * ba.HF_KJ_MOL["CH4"] * KW, rel=1e-12)


def test_a_graphite_feed_has_zero_formation_enthalpy_and_hydrogen_likewise():
    assert ge.feed_formation_kw(5.0, 0.0, 5 * 12.011 / 1000.0, 5 * ba.LHV_KJ_MOL["C"] / 1000.0 / (5 * 12.011 / 1000.0)) == pytest.approx(0.0, abs=1e-12)
    assert ge.feed_formation_kw(0.0, 6.0, 3 * 2.016 / 1000.0, 3 * ba.LHV_KJ_MOL["H2"] / 1000.0 / (3 * 2.016 / 1000.0)) == pytest.approx(0.0, abs=1e-12)


def test_a_higher_lhv_raises_the_feed_formation_enthalpy_one_for_one():
    a, b = ge.feed_formation_kw(100.0, 200.0, 5.0, 15.0), ge.feed_formation_kw(100.0, 200.0, 5.0, 20.0)
    assert b - a == pytest.approx(5.0 * 5.0 / 3.6, rel=1e-12)


# ---------------------------------------------------------------- the stream table
@pytest.mark.parametrize("case", list(ba.lhv_cases()))
def test_the_formation_part_equals_the_chemical_energy_terms_of_the_existing_energy_balance(pair, case):
    """Two independent routes: (formation out - formation in) here, and (chemical energy out - chemical energy in) of balance_audit.gasifier_energy (LHV-based) corrected for the
    residual moisture's liquid-water term. They are the same quantity in different clothes and must agree to round-off at every LHV case."""
    snap, prev = pair
    lhv = ba.lhv_cases()[case]
    r, e = ge.stream_enthalpies(snap, prev, lhv), ba.gasifier_energy(snap, prev, lhv)
    d_form = r["totals"]["out"]["formation_kw"] - r["totals"]["in"]["formation_kw"]
    ins, outs = {x["name"]: x["kw"] for x in e["in"]}, {x["name"]: x["kw"] for x in e["out"]}
    chem_out = outs["product gas chemical energy (H2, CO, CH4)"] + outs["carbon not in the gas: chemical energy (graphite LHV)"]
    chem_in = ins["dry feed chemical energy (dry mass x LHV)"] + ins["tail-gas recycle chemical energy (H2, CO, CH4)"]
    assert d_form == pytest.approx(chem_out - chem_in - ins["residual moisture (liquid water, 25 degC)"], abs=1e-9)


def test_totals_are_the_sums_of_the_rows_and_each_row_is_formation_plus_sensible(pair):
    snap, prev = pair
    r = ge.stream_enthalpies(snap, prev, 17.5)
    for side in ("in", "out"):
        for row in r[side]:
            assert row["total_kw"] == pytest.approx(row["formation_kw"] + row["sensible_kw"], abs=1e-12)
        for k in ("formation_kw", "sensible_kw", "total_kw"):
            assert r["totals"][side][k] == pytest.approx(sum(x[k] for x in r[side]), abs=1e-12)
    assert [x["name"] for x in r["in"]] == ["dry feed (formation derived from LHV)", "residual moisture (liquid water, 25 degC)", "air O2 + air N2", "gasifier steam (350 degC vapour)",
                                            "tail-gas recycle (H2, CO, CH4 at 25 degC)"]
    assert [x["name"] for x in r["out"]] == ["product gas (wet) at the operating temperature", "carbon not in the gas (graphite)", "ash"]


def test_the_product_gas_sensible_part_is_nasa9_evaluated_by_hand(pair):
    """sum n_i x dHs_i(T_gas) over the wet product gas, written out here (not through the module's helper)."""
    snap, prev = pair
    r = ge.stream_enthalpies(snap, prev, 17.5)
    gas = ba.gas_species_mol_h(snap[("GA-001", "Outputs")]["value"])
    t_k = float(snap[("GA-001-INPUT", "operating_temperature_C")]["value"]) + 273.15
    hand = sum(n * ge.sensible_enthalpy_j_mol(sp, t_k) for sp, n in gas.items()) / 1000.0 * KW
    row = r["out"][0]
    assert row["sensible_kw"] == pytest.approx(hand, rel=1e-12)
    assert row["formation_kw"] == pytest.approx(sum(n * ba.HF_KJ_MOL["H2O_g" if sp == "H2O" else sp] for sp, n in gas.items()) * KW, rel=1e-12)
    assert row["t_c"] == pytest.approx(t_k - 273.15)


def test_the_sensible_parts_of_the_inlet_streams_use_the_registry_temperatures_and_the_moisture_is_liquid(pair):
    snap, prev = pair
    r = ge.stream_enthalpies(snap, prev, 17.5)
    by = {x["name"]: x for x in r["in"]}
    steam_mol = ba.ga001_terms(snap, prev)["terms"][4]
    assert steam_mol["name"] == "gasifier steam"
    assert by["gasifier steam (350 degC vapour)"]["sensible_kw"] == pytest.approx(steam_mol["species"]["H2O"] * ge.sensible_enthalpy_j_mol("H2O", 623.15) / 1000.0 * KW, rel=1e-12)
    assert by["gasifier steam (350 degC vapour)"]["formation_kw"] == pytest.approx(steam_mol["species"]["H2O"] * ba.HF_KJ_MOL["H2O_g"] * KW, rel=1e-12)
    moist = by["residual moisture (liquid water, 25 degC)"]
    assert moist["sensible_kw"] == 0.0                                    # at the reference temperature
    assert moist["formation_kw"] < 0 and moist["formation_kw"] == pytest.approx(ba.ga001_terms(snap, prev)["terms"][1]["species"]["H2O"] * ba.HF_KJ_MOL["H2O_l"] * KW, rel=1e-12)
    assert by["dry feed (formation derived from LHV)"]["sensible_kw"] == 0.0     # feed temperature Missing: stated, not guessed
    assert by["air O2 + air N2"]["formation_kw"] == 0.0 and by["air O2 + air N2"]["sensible_kw"] > 0


def test_the_graphite_row_is_the_carbon_not_in_the_gas_at_the_operating_temperature(pair):
    """C in (feed + recycle) minus C in the gas (CO + CO2 + CH4), as graphite: formation 0, sensible n x dHs_C(T_gas in KELVIN)."""
    snap, prev = pair
    r = ge.stream_enthalpies(snap, prev, 17.5)
    ga = ba.ga001_terms(snap, prev)
    gas = ba.gas_species_mol_h(snap[("GA-001", "Outputs")]["value"])
    c_solid = ga["feed_atoms"]["C"] + ga["recycle_atoms"]["C"] - (gas["CO"] + gas["CO2"] + gas["CH4"])
    assert c_solid > 0
    row = r["out"][1]
    assert row["formation_kw"] == 0.0
    assert row["sensible_kw"] == pytest.approx(c_solid * ge.sensible_enthalpy_j_mol("C", r["t_gas_c"] + 273.15) / 1000.0 * KW, rel=1e-12)


def test_ash_is_inert_and_uses_the_assumed_solids_cp(pair):
    snap, prev = pair
    r = ge.stream_enthalpies(snap, prev, 17.5)
    ash = r["out"][2]
    f = float(snap[("GA-001-INPUT", "dry_feed_rate_kg_h")]["value"])
    assert ash["formation_kw"] == 0.0
    assert ash["sensible_kw"] == pytest.approx(0.10 * f * ba.SOLIDS_CP_KJ_KGK[0] * (r["t_gas_c"] - 25.0) * KW, rel=1e-12)
    assert ash["status"] == "Assumed"


def test_the_recycle_stream_is_empty_on_heat_only_and_carries_atoms_on_regasify(pair, pair_regasify):
    snap, prev = pair
    r_h = ge.stream_enthalpies(snap, prev, 17.5)
    assert r_h["in"][4]["formation_kw"] == 0.0 and r_h["in"][4]["sensible_kw"] == 0.0
    snap2, prev2 = pair_regasify
    r_r = ge.stream_enthalpies(snap2, prev2, 17.5)
    assert r_r["in"][4]["formation_kw"] < 0.0                                                    # H2 is 0, CO and CH4 are negative
    assert r_r["in"][4]["sensible_kw"] == 0.0                                                    # taken at 25 degC (Assumed)


def test_an_active_recycle_without_the_previous_snapshot_is_refused_not_guessed(pair_regasify):
    snap, _prev = pair_regasify
    with pytest.raises(ba.AuditInputMissing):
        ge.stream_enthalpies(snap, None, 17.5)


def test_a_temperature_outside_the_data_range_is_refused(pair):
    with pytest.raises(ValueError):
        ge._species_kw({"H2": 1.0}, 6000.0)                    # 6273 K > 6000 K: no extrapolation


def test_the_function_changes_nothing_it_reads(pair):
    snap, prev = pair
    before_s, before_p = copy.deepcopy(snap), copy.deepcopy(prev)
    ge.stream_enthalpies(snap, prev, 17.5)
    assert snap == before_s and prev == before_p


def test_every_row_carries_a_status_and_a_source_and_the_missing_terms_are_listed(pair):
    snap, prev = pair
    r = ge.stream_enthalpies(snap, prev, 17.5)
    for row in r["in"] + r["out"]:
        assert row["status"] in ("Assumed", "Estimated", "Calculated") and row["source"]
    assert len(r["missing_terms"]) == 3 and "tar" in r["missing_terms"][0]
    assert "NOT validation" in r["status"]


def test_nothing_in_the_engine_the_runtime_or_the_app_imports_the_module():
    hits = []
    for base in ("python", "scripts"):
        for dp, _dn, fn in os.walk(os.path.join(ROOT, base)):
            for f in fn:
                if f.endswith(".py") and f != "gasifier_enthalpy.py":
                    with open(os.path.join(dp, f), encoding="utf-8") as fh:
                        if "gasifier_enthalpy" in fh.read():
                            hits.append(os.path.relpath(os.path.join(dp, f), ROOT))
    with open(os.path.join(ROOT, "app.py"), encoding="utf-8") as fh:
        if "gasifier_enthalpy" in fh.read():
            hits.append("app.py")
    assert sorted(hits) == []
