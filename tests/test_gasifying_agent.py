"""Task A1: the gasifying agent as an explicit, checked configuration (switch ("GA-001-INPUT", "gasifying_agent"), default "air").

A1.1: the agent table and the switch (Assumed, never Confirmed, oxygen cost and external heat duty Missing); the N2 term of solve_product_gas; the default is bit-identical to origin/main
(701de71 fixture, every old persisted entry); each live agent reproduces the corresponding scenario of the gasifying-agent study (scripts/run_agent_comparison.py, which swaps the N2 after the
unchanged model) to 1e-12 relative; C, H, O, N closure of the solver for every agent; N2 falls with the O2 fraction of the oxidant; an invalid agent raises. Offline: counting fake store.

A1.2 (below): the downstream consumers follow the agent: the closure audit (C, H, O, N for every agent, audit-based), the energy numbers of the study (gasifier duty, heat demands,
cold-gas efficiencies), the oxidant preheat (Assumed, flagged), the oxygen-carrier estimate (effective ER) and the explicit Missing terms (oxygen source, external heat duty) of the heat summaries.
For the default agent the audit, the energy balance and the heat inventory are unchanged (the A5 baselines are pinned in tests/test_closure_scenarios.py).

NOT validation against DOK-ING data: none exists. The study scenario S3 (chemical looping) is not a live agent."""
import gzip
import importlib.util
import json
import math
import os

import pytest

import _d2_wording
from _fakes import FakeSupabase, patched_supabase
from _intentional_changes import INTENTIONAL
from python import balance_audit as ba
from python import cycle_clock
from python import ga001_energy_balance as eb
from python import ga001_gasifier_model as ga001
from python import plant_heat_integration as phi
from python import plant_status as ps
from python import tab1_integration as t1

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "snapshot_origin_main_701de71.json.gz")
SCRIPT = os.path.join(ROOT, "scripts", "run_agent_comparison.py")
KEY = ga001.GASIFYING_AGENT_KEY
NEW_KEYS = {"GA-001-INPUT|gasifying_agent", "GA-001|AgentConsistency"}          # A1.1 the switch; A1.3 the read-only consistency entry
AGENT_TO_STUDY = {"air": "S0", "enriched_30": "S1a", "enriched_50": "S1b", "oxygen": "S2", "steam_only_0.4": "S4a", "steam_only_0.8": "S4b"}
N = 5
NP = N - 1
LHV_CASES = (15.0, 17.5, 20.0)                          # the study's three feed LHVs (MJ/kg dry): the low end, MID_LHV and the high end of DOK-ING's range


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
    assert set(new) - set(old) == NEW_KEYS | {"HB-003|DutyEstimate"} and set(old) - set(new) == set() and len(old) == 121
    expected = _d2_wording.forward(old)                        # the reworded notes of tests/_d2_wording.py applied to the stored fixture
    bad = {k: _same(expected[k], new[k]) for k in expected if k != "GA-001-INPUT|tail_gas_mode" and k not in INTENTIONAL and _same(expected[k], new[k]) is not True}
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


# ================================================================ A1.2: the downstream consumers follow the agent

@pytest.fixture(scope="module")
def live_prev(fake):
    """{agent: snapshot of the cycle before} (the audit reads the lagged recycle from it, as the study does)."""
    cycle_clock.set_elapsed_hours(None)
    with patched_supabase(fake):
        return {a: t1.build_live_snapshot(NP, overrides=None if a == "air" else {KEY: _const(a)})[0] for a in ga001.GASIFYING_AGENT_NAMES}


NON_DEFAULT = [a for a in ga001.GASIFYING_AGENT_NAMES if a != "air"]


# ---------------------------------------------------------------- test 3: audit-based C, H, O, N closure for every agent

@pytest.mark.parametrize("agent", ga001.GASIFYING_AGENT_NAMES)
def test_the_audit_closes_c_h_o_n_for_every_agent_in_the_gasifier_and_the_loop(agent, live, live_prev):
    out = ba.audit_snapshot(live[agent], live_prev[agent])
    assert out["missing_inputs"] == [], out["missing_inputs"]
    for cv in ("ga001", "loop"):
        for el in ("C", "H", "O", "N"):
            assert abs(out[cv]["rows"][el]["rel"]) < 1e-9, (agent, cv, el, out[cv]["rows"][el]["rel"])
    ok, detail = ba.atom_balance_like_verify(live[agent], live_prev[agent])              # the solver's own guard, rebuilt from the published snapshot
    assert ok, (agent, detail)


@pytest.mark.parametrize("agent", ["enriched_30", "enriched_50", "oxygen"])
def test_the_audit_closure_check_can_fail_an_oxidant_that_is_not_the_agents_does_not_close(agent, live, live_prev):
    """The same published gas audited as if the agent were air (the switch removed from the snapshot): nitrogen must NOT close. A trivial check would stay at ~0."""
    snap = {k: v for k, v in live[agent].items() if k != KEY}
    prev = {k: v for k, v in live_prev[agent].items() if k != KEY}
    wrong = ba.audit_snapshot(snap, prev)
    assert abs(wrong["ga001"]["rows"]["N"]["rel"]) > 0.05 and abs(wrong["loop"]["rows"]["N"]["rel"]) > 0.05
    assert ba.atom_balance_like_verify(snap, prev)[0] is False


def test_the_default_audit_is_unlabelled_and_a_non_default_audit_names_its_agent_and_its_oxidant(live, live_prev):
    d = ba.audit_snapshot(live["air"], live_prev["air"])
    assert "gasifying_agent" not in d
    names = [t["name"] for t in ba.ga001_terms(live["air"], live_prev["air"])["terms"]]
    assert "air O2" in names and "air N2" in names and not any("oxidant" in n for n in names)
    assert "Gasifying agent" not in d["ga001"]["rows"]["N"]["closure_why"]
    for agent in NON_DEFAULT:
        o = ba.audit_snapshot(live[agent], live_prev[agent])
        assert o["gasifying_agent"] == agent
        names = [t["name"] for t in ba.ga001_terms(live[agent], live_prev[agent])["terms"]]
        assert f"oxidant O2 (agent {agent})" in names and f"oxidant N2 (agent {agent})" in names and "air N2" not in names
        for cv in ("ga001", "loop", "plant"):
            for q in ("H", "O", "N"):
                assert f"Gasifying agent '{agent}'" in o[cv]["rows"][q]["closure_why"] and "not an independent check" in o[cv]["rows"][q]["closure_why"]
            assert "Gasifying agent" not in o[cv]["rows"]["C"]["closure_why"]


# ---------------------------------------------------------------- test 2 (energy part): the live numbers equal the study's

@pytest.mark.parametrize("agent", ga001.GASIFYING_AGENT_NAMES)
def test_a_live_agent_equals_the_study_scenario_in_the_gasifier_duty_the_heat_demands_and_the_efficiencies(agent, live, live_prev, runs):
    snap, prev = live[agent], live_prev[agent]
    d = ba.ga001_terms(snap, prev)
    n_gs = d["terms"][4]["species"]["H2O"]
    hb005 = snap[("HB-005", "Steam")]["value"]["steam_kg_h"]
    evap = snap[("FE-005", "MoistureBalance")]["value"]["water_evaporated_kg_h"]
    demands = ba.heat_demands(n_gs, hb005, d["air_o2_mol_h"], d["air_n2_mol_h"], evap, d["agent"])
    for lhv in LHV_CASES:
        s = runs[agent]["energy"][lhv]
        g = ba.gasifier_energy(snap, prev, lhv)
        live_vals = {"duty": g["implied_heat_duty_kw"], "demand": sum(x["kw"] for x in demands), "steam_kw": demands[0]["kw"] + demands[1]["kw"], "air_kw": demands[2]["kw"], "dry_kw": demands[3]["kw"],
                     "cge_incl_recycle": g["cold_gas_efficiency_incl_recycle"], "cge_net": g["cold_gas_efficiency_net_of_recycle"], "feed_kw": g["in"][0]["kw"], "gas_chem_kw": g["out"][0]["kw"]}
        study_vals = {k: s[k] for k in live_vals}
        assert _same(live_vals, study_vals) is True, (agent, lhv, live_vals, study_vals)


@pytest.mark.parametrize("agent", ga001.GASIFYING_AGENT_NAMES)
def test_the_engine_energy_balance_carries_the_same_duty_as_the_audit_functions(agent, live, live_prev):
    snap, prev = live[agent], live_prev[agent]
    v = snap[("GA-001", "EnergyBalance")]["value"]
    for name, lhv in ba.lhv_cases().items():
        g = ba.gasifier_energy(snap, prev, lhv)
        got, want = v["cases"][name]["implied_gasifier_heat_duty_kw"], g["implied_heat_duty_kw"]
        assert abs(got - want) <= 1e-6 * max(1.0, abs(want)), (agent, name, got, want)           # the engine entry reads the lagged recycle of its own cycle: equal to the audit's to the lag


# ---------------------------------------------------------------- oxidant preheat: Assumed and flagged for every non-default agent

def test_the_oxidant_preheat_is_estimated_air_by_default_and_assumed_and_flagged_for_every_other_agent(live, live_prev):
    def demand(agent):
        d = ba.ga001_terms(live[agent], live_prev[agent])
        out = ba.heat_demands(d["terms"][4]["species"]["H2O"], 100.0, d["air_o2_mol_h"], d["air_n2_mol_h"], 1.0, d["agent"])
        return out[2]
    air = demand("air")
    assert air["name"] == "preheat air to 200 degC" and air["status"] == ps.STATUS_ESTIMATED and air["kw"] > 0
    for agent in NON_DEFAULT:
        x = demand(agent)
        assert x["status"] == ps.STATUS_ASSUMED and "[FLAGGED]" in x["name"] and "FLAGGED" in x["source"] and agent in x["name"], (agent, x)
    assert demand("steam_only_0.4")["kw"] == 0.0 and demand("steam_only_0.8")["kw"] == 0.0         # no oxidant: no flow, and still flagged (checked above)
    assert demand("oxygen")["kw"] < air["kw"]                                                          # the same O2, no N2 to heat
    for agent in NON_DEFAULT:
        e = live[agent][("GA-001", "EnergyBalance")]["value"]
        assert e["heat_demand_status"] == ps.STATUS_ASSUMED and any("[FLAGGED]" in x["name"] for x in e["heat_demands"])
    assert live["air"][("GA-001", "EnergyBalance")]["value"]["heat_demand_status"] == ps.STATUS_ESTIMATED


# ---------------------------------------------------------------- oxygen source and external heat duty: explicit Missing, never 0 kW or "closed"

def _summaries(snap):
    return [snap[("GA-001", "EnergyBalance")]["value"], snap[("PLANT", "HeatIntegration")]["value"]]


def _term_ok(t):
    text = json.dumps(t).lower()
    return t["status"] == ps.STATUS_MISSING and t["kw"] is None and bool(t["missing_reason"]) and "closed" not in text and "0 kw" not in text and "0.0 kw" not in text


@pytest.mark.parametrize("agent", NON_DEFAULT)
def test_oxygen_cost_and_external_heat_duty_are_explicit_missing_terms_in_the_heat_summaries_for_a_non_default_agent(agent, live):
    for value in _summaries(live[agent]):
        block = value["agent"]
        assert block["gasifying_agent"] == agent and block["status"] == ps.STATUS_ASSUMED
        terms = {t["name"]: t for t in block["missing_terms"]}
        oxygen = "oxygen source (air-separation / oxygen-enrichment heat or electricity)" if ga001.GASIFYING_AGENTS[agent]["oxidant"] else "oxygen source (no oxygen used by this agent)"
        assert set(terms) == {oxygen, "external (allothermal) heat duty"}
        assert all(_term_ok(t) for t in terms.values()), terms
        listed = " ".join(value["missing_terms"])
        assert "oxygen source" in listed and "external (allothermal) heat duty" in listed and listed.count("Missing (") >= 2
    assert _summaries(live[agent])[0]["missing_terms"][:len(eb.MISSING_TERMS)] == eb.MISSING_TERMS
    if ga001.GASIFYING_AGENTS[agent]["oxidant"]:
        assert _summaries(live[agent])[1]["missing_terms"][:len(phi.MISSING_TERMS)] == phi.MISSING_TERMS


@pytest.mark.parametrize("agent", ["steam_only_0.4", "steam_only_0.8"])
def test_a_steam_only_agent_says_no_oxygen_used_and_never_implies_an_air_separation_unit_is_needed(agent, live):
    """Clarification of A1.3: the steam-only wording is 'no oxygen used'. Neither heat summary, the agent table nor the preheat text may name an air-separation unit for it."""
    texts = [json.dumps(v["agent"]) + " ".join(v["missing_terms"]) for v in _summaries(live[agent])]
    texts.append(json.dumps(ga001.GASIFYING_AGENTS[agent]))
    texts += [x["name"] + x["source"] for x in live[agent][("GA-001", "EnergyBalance")]["value"]["heat_demands"] if "preheat" in x["name"]]
    for text in texts:
        low = text.lower()
        assert "air-separation" not in low and "air separation" not in low and " asu" not in low and "enrichment" not in low, text
    assert all("no oxygen used" in json.dumps(v["agent"]) for v in _summaries(live[agent]))
    assert any("no oxygen used" in x for x in _summaries(live[agent])[1]["missing_terms"])
    for other in ("enriched_30", "enriched_50", "oxygen"):                      # the agents that DO use oxygen keep the unit wording
        assert "air-separation" in json.dumps(live[other][("PLANT", "HeatIntegration")]["value"]["agent"])


def test_a_missing_term_that_read_zero_kw_or_closed_would_be_refused():
    """The check used above is not vacuous: it accepts the real terms and rejects a term that says 0 kW, is not Missing or says closed."""
    good = ga001.agent_missing_terms("oxygen")
    assert good and all(_term_ok(t) for t in good)
    for bad in (dict(good[0], kw=0.0), dict(good[0], status="Calculated"), dict(good[0], missing_reason="closed"), dict(good[0], missing_reason="the duty is 0 kW"), dict(good[0], missing_reason="")):
        assert not _term_ok(bad), bad


def test_the_default_heat_summaries_have_no_agent_block_and_their_missing_terms_are_the_module_lists(live):
    e, h = _summaries(live["air"])
    assert "agent" not in e and "agent" not in h
    assert e["missing_terms"] == eb.MISSING_TERMS and h["missing_terms"] == phi.MISSING_TERMS
    assert ga001.agent_missing_terms("air") == [] and ga001.agent_summary_block("air") is None


# ---------------------------------------------------------------- the oxygen-carrier estimate follows the effective ER

def test_the_oxygen_carrier_estimate_uses_the_effective_er_and_says_so_for_a_non_default_agent(live):
    air = live["air"][("GA-001", "OxygenCarrierCirculationEstimate")]["value"]
    assert "GASIFYING AGENT" not in air["consistency_check"]["note"] and air["o2_demand_kg_h"] > 0
    steam = live["steam_only_0.4"][("GA-001", "OxygenCarrierCirculationEstimate")]["value"]
    assert steam["o2_demand_kg_h"] == 0.0 and "GASIFYING AGENT 'steam_only_0.4'" in steam["consistency_check"]["note"]      # the ER input (0.25) would have given a positive demand
    oxy = live["oxygen"][("GA-001", "OxygenCarrierCirculationEstimate")]["value"]
    assert oxy["o2_demand_kg_h"] == air["o2_demand_kg_h"] and "GASIFYING AGENT 'oxygen'" in oxy["consistency_check"]["note"]       # same ER, so the same O2


# ---------------------------------------------------------------- combustion air for burning the tail gas stays air for every agent

def test_the_tail_gas_burner_air_of_the_heat_inventory_is_air_for_every_agent():
    import inspect
    assert "agent" not in inspect.signature(phi._flue).parameters
    species = {"H2": 10.0, "CO": 5.0, "CH4": 1.0, "CO2": 3.0, "N2": 2.0}
    chem, flue, t_ad, rel, loss = phi._flue(species, 1.2, 150.0)
    n = {s: v / ba.NM3_PER_MOL for s, v in species.items()}
    o2 = 0.5 * n["H2"] + 0.5 * n["CO"] + 2.0 * n["CH4"]
    assert flue["N2"] == pytest.approx(n["N2"] + o2 * 1.2 * ga001.AIR_N2_PER_O2, rel=1e-12)


# ================================================================ A1.3: the agent-consistency check (read-only, tolerance not set)

JUDGEMENT_WORDS = ("wrong", "error", "fail", "invalid", "bad", "mismatch", "inconsistent", "violat", "incorrect", "contradict", "unrealistic", "reject")


def test_the_check_reports_the_numbers_and_the_difference_by_name_and_gives_no_verdict_without_a_tolerance():
    c = ga001.agent_consistency("oxygen", 2.5)
    assert c["agent"] == "oxygen" and c["agent_status"] == ps.STATUS_ASSUMED
    assert c["expected_n2_vol_pct"] == 10.0 and c["computed_n2_vol_pct_dry"] == 2.5 and c["deviation_vol_pct"] == -7.5          # model minus registry
    assert c["tolerance_vol_pct"] is None and c["consistent"] is None and c["tolerance_note"] == "tolerance not set"
    assert "No tolerance is set, so no verdict is given." in c["reading"]
    assert c["expected_source"]["resolved_status"] == "Assumed"
    assert "not stated" in c["expected_source"]["basis_wet_or_dry"] and "wet or dry" in c["expected_source"]["basis_wet_or_dry"]
    assert "without a wet or dry basis" in c["reading"] and "resolved status Assumed" in c["reading"] and "-7.50 vol%" in c["reading"]
    assert ga001.AGENT_CONSISTENCY_TOLERANCE_VOL_PCT is None


def test_a_numeric_tolerance_flags_a_deliberately_inconsistent_registry_value_as_outside_and_a_close_one_as_within():
    far = ga001.agent_consistency("oxygen", 2.5, expected_n2_vol_pct=10.0, tolerance_vol_pct=1.0)
    near = ga001.agent_consistency("oxygen", 2.5, expected_n2_vol_pct=3.0, tolerance_vol_pct=1.0)
    edge = ga001.agent_consistency("oxygen", 2.5, expected_n2_vol_pct=3.5, tolerance_vol_pct=1.0)
    assert far["consistent"] is False and "outside the tolerance of 1 vol%" in far["reading"] and far["tolerance_note"] == "tolerance passed in by the caller"
    assert near["consistent"] is True and "within the tolerance of 1 vol%" in near["reading"]
    assert edge["consistent"] is True                                                           # |deviation| == tolerance is within
    assert far["deviation_vol_pct"] == -7.5 and near["deviation_vol_pct"] == -0.5


@pytest.mark.parametrize("tol", [None, 1.0])
@pytest.mark.parametrize("agent", ga001.GASIFYING_AGENT_NAMES)
def test_the_wording_is_neutral_for_every_agent_with_and_without_a_tolerance(agent, tol):
    reading = ga001.agent_consistency(agent, 39.6, tolerance_vol_pct=tol)["reading"].lower()
    assert not [w for w in JUDGEMENT_WORDS if w in reading], reading
    assert f"declared agent '{agent}'" in reading


@pytest.mark.parametrize("bad", [-1.0, float("nan"), float("inf"), True, False, "1", [1.0]])
def test_an_invalid_tolerance_raises(bad):
    with pytest.raises(ValueError):
        ga001.agent_consistency("air", 39.6, tolerance_vol_pct=bad)


@pytest.mark.parametrize("bad", [None, True, "10", float("nan"), float("inf")])
def test_an_invalid_number_or_agent_raises(bad):
    with pytest.raises(ValueError):
        ga001.agent_consistency("air", bad)
    with pytest.raises(ValueError):
        ga001.agent_consistency("air", 39.6, expected_n2_vol_pct=bad)
    with pytest.raises(ValueError):
        ga001.agent_consistency(bad if isinstance(bad, str) else "nitrogen", 39.6)


@pytest.mark.parametrize("agent", ga001.GASIFYING_AGENT_NAMES)
def test_the_live_entry_is_calculated_names_the_agent_and_publishes_the_numbers(agent, live):
    e = live[agent][("GA-001", "AgentConsistency")]
    v, g = e["value"], live[agent][("GA-001", "Outputs")]["value"]
    assert e["status"] == ps.STATUS_CALCULATED and e["source"]["model"] == "ga001_gasifier_model.ga001_agent_consistency"
    assert v["agent"] == agent and v["computed_n2_vol_pct_dry"] == g["N2_mol_pct_dry"] and v["expected_n2_vol_pct"] == 10.0
    assert v["deviation_vol_pct"] == pytest.approx(g["N2_mol_pct_dry"] - 10.0, rel=1e-15)
    assert v["tolerance_vol_pct"] is None and v["consistent"] is None and v["tolerance_note"] == "tolerance not set"
    assert v["expected_source"]["resolved_status"] == "Assumed" and "wet or dry" in v["expected_source"]["basis_wet_or_dry"]
    eff = v["effective_inputs"]
    er, steam, _ = ga001.agent_oxidant(agent, 0.25, 0.4)
    assert (eff["equivalence_ratio"], eff["steam_to_feed_ratio"], eff["oxidant_o2_fraction"]) == (er, steam, ga001.GASIFYING_AGENTS[agent]["o2_fraction"])
    assert [tuple(k) for k in e["source"]["inputs"]] == [("GA-001", "Outputs"), KEY, ("GA-001-INPUT", "equivalence_ratio"), ("GA-001-INPUT", "steam_to_feed_ratio")]
    assert "judges nothing" in e["confidence_note"] and "not validation against DOK-ING data" in e["confidence_note"]


def test_the_registry_row_the_check_quotes_is_still_what_the_resolver_says_and_the_value_is_the_registry_value():
    """The engine must not import the resolver (tests/test_apply_provenance.py), so the status is a constant of ga001; this test is the drift guard for it."""
    from python import equipment_registry, registry_status
    row = next(p for it in equipment_registry.load_registry() if it["id"] == "SA-005" for p in it["parameters"] if p["parameter"].startswith("Expected N"))
    assert registry_status.resolve_row(registry_status.SOURCE_REGISTRY, "SA-005", row)["status"] == ga001.SA005_RESOLVED_STATUS == "Assumed"
    assert float(row["value"]) == ga001.SA005_EXPECTED_N2_VOL_PCT and row["unit"] == "vol%"
    assert "wet" not in (row.get("remarks") or "").lower() and "dry" not in (row.get("remarks") or "").lower(), "the registry row states no basis"


# ---------------------------------------------------------------- it feeds nothing

def test_nothing_reads_the_entry_so_no_value_gate_maturity_class_or_ai_model_can_change(fake):
    def run(overrides=None):
        cycle_clock.set_elapsed_hours(None)
        with patched_supabase(fake):
            return t1.build_live_snapshot(N, overrides=overrides)
    snap, _state, engine = run()
    key = ga001.AGENT_CONSISTENCY_KEY
    for k, spec in engine._models.items():                                   # no registered model depends on it
        assert key not in spec["depends_on"] and key not in spec["lagged_depends_on"], k
    other, _s, _e = run({key: _const({"report_only": "replaced"})})           # replace the entry by a constant: every OTHER entry is unchanged
    assert set(other) == set(snap) and other[key]["value"] == {"report_only": "replaced"}
    assert {k: json.dumps(v, sort_keys=True, default=str) for k, v in snap.items() if k != key} == {k: json.dumps(v, sort_keys=True, default=str) for k, v in other.items() if k != key}


def test_no_engine_gate_maturity_or_ai_module_names_the_entry():
    names = []
    for folder in ("python", "scripts"):
        for f in sorted(os.listdir(os.path.join(ROOT, folder))):
            if f.endswith(".py") and "AgentConsistency" in open(os.path.join(ROOT, folder, f), encoding="utf-8").read():
                names.append(f"{folder}/{f}")
    assert names == ["python/ga001_gasifier_model.py"], names                  # the model that publishes it; the readiness gate, maturity, AI and engine modules never mention it


LEGACY_REGASIFY_DEFAULT = True      # P1-06b: not yet exercised on the real default (heat_only): agent scenarios are compared with the regasify default of the study; tests/conftest.py restores the old default for this module
