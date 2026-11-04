"""Task A1: the gasifying agent as an explicit, checked configuration (switch ("GA-001-INPUT", "gasifying_agent"), default "air").

A1.1 (this part): the agent table and the switch (Assumed, never Confirmed, oxygen cost and external heat duty Missing); the N2 term of solve_product_gas; the default is bit-identical to origin/main
(701de71 fixture, every old persisted entry); each live agent reproduces the corresponding scenario of the gasifying-agent study (scripts/run_agent_comparison.py, which swaps the N2 after the
unchanged model) to 1e-12 relative; C, H, O, N closure of the solver for every agent; N2 falls with the O2 fraction of the oxidant; an invalid agent raises. Offline: counting fake store.

NOT validation against DOK-ING data: none exists. The study scenario S3 (chemical looping) is not a live agent."""
import gzip
import importlib.util
import json
import math
import os

import pytest

import _d2_wording
from _fakes import FakeSupabase, patched_supabase
from python import cycle_clock
from python import ga001_gasifier_model as ga001
from python import plant_status as ps
from python import tab1_integration as t1

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "snapshot_origin_main_701de71.json.gz")
SCRIPT = os.path.join(ROOT, "scripts", "run_agent_comparison.py")
KEY = ga001.GASIFYING_AGENT_KEY
NEW_KEYS = {"GA-001-INPUT|gasifying_agent"}                  # A1.1; A1.3 adds ("GA-001", "AgentConsistency")
AGENT_TO_STUDY = {"air": "S0", "enriched_30": "S1a", "enriched_50": "S1b", "oxygen": "S2", "steam_only_0.4": "S4a", "steam_only_0.8": "S4b"}
N = 5


def _const(v):
    def fn(get_input):
        return {"value": v, "status": ps.STATUS_ASSUMED, "inputs": [], "validation_basis": ps.VALIDATION_NA, "confidence_note": "test"}
    return fn


def _ser(snapshot):
    return {f"{k[0]}|{k[1]}": json.loads(json.dumps(v, sort_keys=True, default=str)) for k, v in snapshot.items()}


def _same(a, b, path=""):
    if isinstance(a, float) or isinstance(b, float):
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-15) or [path]
        return [path]
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            return [path + "/<keys>"]
        bad = []
        for k in a:
            r = _same(a[k], b[k], f"{path}/{k}")
            bad += [] if r is True else r
        return bad or True
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [path + "/<len>"]
        bad = []
        for i, (x, y) in enumerate(zip(a, b)):
            r = _same(x, y, f"{path}[{i}]")
            bad += [] if r is True else r
        return bad or True
    return True if a == b else [path]


@pytest.fixture(scope="module")
def fake():
    return FakeSupabase()


@pytest.fixture(scope="module")
def study():
    spec = importlib.util.spec_from_file_location("run_agent_comparison", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.N_CONV = N
    return m


@pytest.fixture(scope="module")
def live(fake):
    """{agent: snapshot} of the LIVE engine with the agent switch, N cycles, tail_gas_mode default."""
    cycle_clock.set_elapsed_hours(None)
    with patched_supabase(fake):
        return {a: t1.build_live_snapshot(N, overrides=None if a == "air" else {KEY: _const(a)})[0] for a in ga001.GASIFYING_AGENT_NAMES}


@pytest.fixture(scope="module")
def runs(study, fake):
    cycle_clock.set_elapsed_hours(None)
    sc = {s["id"]: s for s in study.SCENARIOS}
    with patched_supabase(fake):
        return {agent: study.run_scenario(sc[sid], "regasify", with_closure=False) for agent, sid in AGENT_TO_STUDY.items()}


# ---------------------------------------------------------------- the table: Assumed, Missing, no S3

def test_the_agent_table_is_these_six_and_chemical_looping_is_not_one():
    assert ga001.GASIFYING_AGENT_NAMES == ("air", "enriched_30", "enriched_50", "oxygen", "steam_only_0.4", "steam_only_0.8")
    assert ga001.GASIFYING_AGENT_DEFAULT == "air" and not any("loop" in a or "carrier" in a or a == "S3" for a in ga001.GASIFYING_AGENTS)


def test_every_agent_definition_is_assumed_and_the_oxygen_cost_and_external_heat_duty_are_missing_not_zero():
    for name, spec in ga001.GASIFYING_AGENTS.items():
        assert spec["status"] == ps.STATUS_ASSUMED != "Confirmed", name
        for term in ("oxygen_source_cost", "external_heat_duty"):
            assert spec[term]["status"] == ps.STATUS_MISSING and spec[term]["value"] is None and spec[term]["missing_reason"], (name, term)
    entry = ga001._input_gasifying_agent(lambda k: None)
    assert entry["value"] == "air" and entry["status"] == ps.STATUS_ASSUMED and "Switch, not a measurement" in entry["confidence_note"]


def test_the_air_agent_duplicates_neither_er_nor_steam_and_the_other_agents_set_only_what_the_study_sets():
    air = ga001.GASIFYING_AGENTS["air"]
    assert air["er"] is None and air["steam_to_feed"] is None
    assert (ga001.GASIFYING_AGENTS["steam_only_0.4"]["er"], ga001.GASIFYING_AGENTS["steam_only_0.4"]["steam_to_feed"]) == (0.0, None)
    assert (ga001.GASIFYING_AGENTS["steam_only_0.8"]["er"], ga001.GASIFYING_AGENTS["steam_only_0.8"]["steam_to_feed"]) == (0.0, 0.8)
    for a in ("enriched_30", "enriched_50", "oxygen"):
        assert ga001.GASIFYING_AGENTS[a]["er"] is None and ga001.GASIFYING_AGENTS[a]["steam_to_feed"] is None
    assert [ga001.GASIFYING_AGENTS[a]["o2_fraction"] for a in ("enriched_30", "enriched_50", "oxygen")] == [0.30, 0.50, 1.0]


def test_agent_oxidant_air_reads_the_inputs_unchanged_and_uses_no_n2_ratio():
    assert ga001.agent_oxidant("air", 0.31, 0.47) == (0.31, 0.47, None)
    assert ga001.agent_oxidant("oxygen", 0.31, 0.47) == (0.31, 0.47, 0.0)
    assert ga001.agent_oxidant("enriched_30", 0.31, 0.47)[2] == pytest.approx(0.70 / 0.30, rel=1e-15)
    assert ga001.agent_oxidant("steam_only_0.4", 0.31, 0.47) == (0.0, 0.47, 0.0)
    assert ga001.agent_oxidant("steam_only_0.8", 0.31, 0.47) == (0.0, 0.8, 0.0)


# ---------------------------------------------------------------- invalid values raise

@pytest.mark.parametrize("bad", [None, True, False, 0, 1, 1.0, "", "AIR", "Air", "nitrogen", "chemical_looping", "steam_only", ["air"], ("air",), {"air": 1}])
def test_an_invalid_agent_raises_value_error_and_nothing_guesses_a_default(bad):
    with pytest.raises(ValueError):
        ga001.check_gasifying_agent(bad)
    with pytest.raises(ValueError):
        ga001._gasifying_agent(lambda k: {"value": bad, "status": ps.STATUS_ASSUMED})
    with pytest.raises(ValueError):
        ga001.agent_oxidant(bad, 0.25, 0.4)


def test_an_invalid_agent_in_the_live_engine_raises(fake):
    with patched_supabase(fake):
        with pytest.raises(ValueError):
            t1.build_live_snapshot(2, overrides={KEY: _const("nitrogen")})


def test_a_missing_switch_entry_means_air():
    assert ga001._gasifying_agent(lambda k: {"value": None, "status": ps.STATUS_MISSING}) == "air"


# ---------------------------------------------------------------- 1: the default is bit-identical to origin/main

def test_the_default_agent_leaves_every_old_persisted_entry_unchanged(fake):
    with gzip.open(FIXTURE, "rb") as fh:
        old = json.loads(fh.read().decode("utf-8"))["default|20"]
    with patched_supabase(fake):
        new = _ser(t1.build_live_snapshot(20)[0])
    assert set(new) - set(old) == NEW_KEYS and set(old) - set(new) == set() and len(old) == 121
    expected = _d2_wording.forward(old)                        # the reworded notes of tests/_d2_wording.py applied to the stored fixture
    bad = {k: _same(expected[k], new[k]) for k in expected if k != "GA-001-INPUT|tail_gas_mode" and _same(expected[k], new[k]) is not True}
    assert bad == {}, bad
    assert new["GA-001-INPUT|gasifying_agent"]["value"] == "air" and new["GA-001-INPUT|gasifying_agent"]["status"] == "Assumed"


def test_the_default_outputs_entry_carries_no_agent_key_and_the_other_agents_carry_the_effective_values(live):
    air = live["air"][("GA-001", "Outputs")]
    assert "gasifying_agent" not in air["value"] and "Gasifying agent" not in air["confidence_note"]
    st = live["steam_only_0.8"][("GA-001", "Outputs")]
    assert st["value"]["gasifying_agent"] == "steam_only_0.8" and st["value"]["effective_equivalence_ratio"] == 0.0 and st["value"]["effective_steam_to_feed_ratio"] == 0.8
    assert "Assumed switch, no DOK-ING source" in st["confidence_note"] and "Missing" in st["confidence_note"]
    # the ER and steam-to-feed INPUT entries keep showing the inputs (the input functions are untouched)
    assert live["steam_only_0.8"][("GA-001-INPUT", "equivalence_ratio")]["value"] == live["air"][("GA-001-INPUT", "equivalence_ratio")]["value"] == 0.25
    assert live["steam_only_0.8"][("GA-001-INPUT", "steam_to_feed_ratio")]["value"] == live["air"][("GA-001-INPUT", "steam_to_feed_ratio")]["value"] == 0.4


def test_the_solver_with_the_explicit_air_ratio_equals_the_default_path_bit_for_bit():
    x, y, z, nc = ga001.elemental_atomic_ratios(ga001.FEEDSTOCK_C_FRACTION, ga001.FEEDSTOCK_H_FRACTION, ga001.FEEDSTOCK_O_FRACTION, ga001.FEEDSTOCK_N_FRACTION, ga001.ASH_FRACTION)
    steam = (0.4 / nc) * 1000.0 / ga001.M_H2O
    a = ga001.solve_product_gas(x, y, z, 0.25, steam, 0.9, 0.05, 1223.15)
    b = ga001.solve_product_gas(x, y, z, 0.25, steam, 0.9, 0.05, 1223.15, ga001.AIR_N2_PER_O2)
    c = ga001.solve_product_gas(x, y, z, 0.25, steam, 0.9, 0.05, 1223.15, None)
    assert a == b == c


# ---------------------------------------------------------------- 2: each live agent equals its study scenario

@pytest.mark.parametrize("agent", ga001.GASIFYING_AGENT_NAMES)
def test_a_live_agent_equals_the_study_scenario_in_species_moles_and_the_downstream_chain(agent, live, runs):
    r, snap = runs[agent], live[agent]
    assert "error" not in r, r
    g = snap[("GA-001", "Outputs")]["value"]
    moles = {s: g["dry_flow_nm3_h"] * g[f"{s}_mol_pct_dry"] / 100.0 for s in ("H2", "CO", "CO2", "CH4", "N2")}
    study_moles = {s: r["dry_flow"] * r["pct"][s] / 100.0 for s in moles}
    assert _same(moles, study_moles) is True, (agent, moles, study_moles)
    assert _same(g["dry_flow_nm3_h"], r["dry_flow"]) is True
    assert _same(snap[("SA-006", "Reading")]["value"], r["lhv"]) is True
    assert _same(snap[("HB-012", "Compressor")]["value"]["h2_kg_h"] * 24.0, r["h2_kg_day"]) is True
    assert _same(snap[("GA-001", "CarbonAccounting")]["value"]["carbon_black_kg_h"], r["cb"]) is True
    assert _same(snap[("HB-006", "PSA")]["value"]["recovery"], r["psa_recovery"]) is True


# ---------------------------------------------------------------- 3: C, H, O, N closure of the solver for every agent

def _solver_case(agent):
    x, y, z, nc = ga001.elemental_atomic_ratios(ga001.FEEDSTOCK_C_FRACTION, ga001.FEEDSTOCK_H_FRACTION, ga001.FEEDSTOCK_O_FRACTION, ga001.FEEDSTOCK_N_FRACTION, ga001.ASH_FRACTION)
    er, steam_ratio, n2 = ga001.agent_oxidant(agent, 0.25, 0.4)
    steam = (steam_ratio / nc) * 1000.0 / ga001.M_H2O
    product = ga001.solve_product_gas(x, y, z, er, steam, 0.9, 0.05, 1223.15, n2)
    return x, y, z, er, steam, product, n2


@pytest.mark.parametrize("agent", ga001.GASIFYING_AGENT_NAMES)
def test_c_h_o_n_close_for_every_agent_with_the_agents_own_oxidant(agent):
    x, y, z, er, steam, product, n2 = _solver_case(agent)
    ok, detail = ga001.verify_atom_balance(x, y, z, er, steam, product, 0.9, n2_per_o2=n2)
    assert ok, detail
    for k in ("C_gas_target_vs_actual", "C_gas_plus_unconverted_vs_fed", "H_target_vs_actual", "O_target_vs_actual", "N_target_vs_actual"):
        t, a = detail[k]
        assert abs(t - a) < 1e-8 * max(1.0, abs(t)), (agent, k, detail[k])


@pytest.mark.parametrize("agent", ["enriched_30", "enriched_50", "oxygen"])
def test_the_n_guard_can_fail_it_rejects_the_air_n2_ratio_for_an_agent_that_has_less_n2(agent):
    x, y, z, er, steam, product, n2 = _solver_case(agent)
    ok, detail = ga001.verify_atom_balance(x, y, z, er, steam, product, 0.9)              # the guard told the air ratio: the N balance must break
    assert not ok and detail["N_target_vs_actual"][0] != pytest.approx(detail["N_target_vs_actual"][1], rel=1e-6)


# ---------------------------------------------------------------- 4: N2 falls with the O2 fraction of the oxidant

def test_n2_falls_strictly_as_the_oxidant_o2_fraction_rises_at_fixed_er_and_feed():
    order = ["air", "enriched_30", "enriched_50", "oxygen"]          # O2 fractions 0.21 < 0.30 < 0.50 < 1.0
    n2 = [_solver_case(a)[5]["N2"] for a in order]
    assert [ga001.GASIFYING_AGENTS[a]["o2_fraction"] for a in order] == sorted(ga001.GASIFYING_AGENTS[a]["o2_fraction"] for a in order)
    assert all(a > b for a, b in zip(n2, n2[1:])), n2
    x, y, z, *_ = _solver_case("oxygen")
    assert n2[-1] == pytest.approx(z / 2.0, rel=1e-12), "pure oxygen: only the fuel nitrogen is left"
    assert _solver_case("steam_only_0.4")[5]["N2"] == pytest.approx(z / 2.0, rel=1e-12)
