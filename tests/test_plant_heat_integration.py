"""("PLANT", "HeatIntegration"): the read-only plant heat source / sink inventory (heat-integration stage 1).

What is pinned: a hand-checkable synthetic case; the sums close; Missing terms are listed and never zero; the key is in both tail_gas_modes and recomputes identically; it mutates no state and
nothing reads it; every other entry of the 120 that origin/main (f628406) publishes is unchanged in both modes (tests/fixtures/snapshot_origin_main_f628406.json.gz, made from the
unmodified code: exact for structure, strings and integers, 1e-12 relative for floats); the persisted key count rises by exactly one and none is lost (the runtime's 90 % shrink guard
cannot trip); a source below the need's temperature is reported as a mismatch and not counted; no database or network."""
import ast
import copy
import gzip
import importlib.util
import json
import math
import os
import re
import subprocess

import pytest

import _d2_wording
from _fakes import FakeSupabase, patched_supabase
from python import balance_audit as ba
from python import plant_heat_integration as phi
from python import plant_status as ps
from python import simulation_engine as se
from python import shared_plant_state as sps
from python import tab1_integration as t1

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "snapshot_origin_main_f628406.json.gz")
KEY = "PLANT|HeatIntegration"
A1_KEY = "GA-001-INPUT|gasifying_agent"                  # task A1 (deliberate edit): the gasifying-agent switch, one more new key
A1_3_KEY = "GA-001|AgentConsistency"                        # task A1.3 (deliberate edit): the read-only agent-consistency entry, one more new key
MID = "DOK-ING midpoint (Assumed point)"
N = 20


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


def getter(snap):
    return lambda k: (snap[k] if k in snap and snap[k]["status"] != ps.STATUS_MISSING else None)


@pytest.fixture(scope="module")
def fake():
    return FakeSupabase()


@pytest.fixture(scope="module")
def runs(fake):
    out = {}
    with patched_supabase(fake):
        out["default"] = t1.build_live_snapshot(N)[0]
        out["heat_only"] = t1.build_live_snapshot(N, overrides={("GA-001-INPUT", "tail_gas_mode"): _const("heat_only")})[0]
    return out


@pytest.fixture(scope="module")
def main_snap():
    with gzip.open(FIXTURE, "rb") as fh:
        return json.loads(fh.read().decode("utf-8"))


def _mid(snap):
    return snap[("PLANT", "HeatIntegration")]["value"]["cases"][MID]


# ------------------------------------------------------------------ (a) hand-checkable synthetic cases

def test_uniform_profile_conserves_the_energy_and_stays_inside_its_interval():
    bins = phi._uniform(12.0, 100.0, 300.0)
    assert sum(kw for _t, kw in bins) == pytest.approx(12.0, abs=1e-12) and all(100.0 < t < 300.0 for t, _ in bins)
    assert phi._uniform(0.0, 1.0, 2.0) == [] and phi._uniform(5.0, 400.0, 400.0) == [(400.0, 5.0)]


def test_match_by_hand_a_source_serves_only_needs_below_its_temperature_minus_the_approach():
    # 100 kW released evenly between 100 and 300 degC; a 30 kW need at 150 degC is served (150 + 20 <= 170..300); a 50 kW need at 400 degC cannot be
    supply = [("S", t, kw) for t, kw in phi._uniform(100.0, 100.0, 300.0)]
    alloc, unmet, unused = phi.match(supply, [("cool", "b", 150.0, 30.0), ("hot", "b", 400.0, 50.0)], dt_min=20.0)
    assert sum(alloc.values()) == pytest.approx(30.0, abs=1e-9) and alloc[("cool", "S")] == pytest.approx(30.0, abs=1e-9)
    assert unmet == {"hot": pytest.approx(50.0, abs=1e-9)} and unused["S"] == pytest.approx(70.0, abs=1e-9)
    # the coldest qualifying heat is used first: the 30 kW comes from the 170-ish bins, leaving everything above 300-... untouched
    assert unused["S"] + sum(alloc.values()) == pytest.approx(100.0, abs=1e-9)
    # a source entirely below the need's level supplies nothing
    alloc, unmet, unused = phi.match([("S", 100.0, 10.0)], [("n", "b", 100.0, 10.0)], dt_min=20.0)
    assert alloc == {} and unmet == {"n": 10.0} and unused == {"S": 10.0}


def test_flue_gas_by_hand_pure_hydrogen_tail_gas():
    """100 mol/h H2 burned with 1.5 x stoichiometric air (O2 stoich 50 mol/h): chemical = 100 x 241.826 kJ/h; flue = 100 H2O + (75 x 79/21 =) 282.14 N2 + 25 O2; the energy closes."""
    n_nm3 = 100.0 * ba.NM3_PER_MOL
    chem, flue, t_ad, released, loss = phi._flue({"H2": n_nm3, "CO": 0.0, "CH4": 0.0, "CO2": 0.0, "N2": 0.0}, 1.5, 180.0)
    assert chem == pytest.approx(100.0 * 241.826 / 3600.0, rel=1e-12)
    assert flue["H2O"] == pytest.approx(100.0) and flue["O2"] == pytest.approx(25.0) and flue["N2"] == pytest.approx(75.0 * 0.79 / 0.21)
    cp_sum = 100 * ba.CP_J_MOLK["H2O"] + (75.0 * 0.79 / 0.21) * ba.CP_J_MOLK["N2"] + 25 * ba.CP_J_MOLK["O2"]
    assert t_ad == pytest.approx(25.0 + chem * 3600.0 * 1000.0 / cp_sum, rel=1e-12)
    assert released + loss == pytest.approx(chem, abs=1e-9) and loss == pytest.approx(cp_sum * (180.0 - 25.0) / 3.6e6, rel=1e-12)


def _synthetic_get(runs, patch):
    snap = copy.deepcopy(runs["default"])
    for k, f in patch.items():
        snap[k] = f(snap[k])
    return getter(snap), snap


def test_product_gas_cooling_by_hand_through_the_whole_function(runs):
    """1000 mol/h of pure N2 (22.414 Nm3/h, no water) cooled from 450 to 350 degC at the repo's mean cp 30.6 J/mol.K: 1000 x 30.6 x 100 / 3.6e6 = 0.85 kW."""
    def outputs(e):
        v = dict(e["value"], dry_flow_nm3_h=1000.0 * ba.NM3_PER_MOL, wet_flow_nm3_h=1000.0 * ba.NM3_PER_MOL, N2_mol_pct_dry=100.0, H2_mol_pct_dry=0.0, CO_mol_pct_dry=0.0, CO2_mol_pct_dry=0.0, CH4_mol_pct_dry=0.0)
        return dict(e, value=v)
    get, _ = _synthetic_get(runs, {("GA-001", "Outputs"): outputs, ("GA-001-INPUT", "operating_temperature_C"): lambda e: dict(e, value=450.0)})
    v = phi.compute(get, assumptions={"gas_cooler_outlet_c": 350.0}, lhv_cases={"x": 17.5})
    src = next(s for s in v["sources"] if s["name"].startswith("product-gas sensible heat"))
    assert src["kw_available"] == pytest.approx(1000.0 * ba.CP_J_MOLK["N2"] * 100.0 / 3.6e6, rel=1e-12) == pytest.approx(0.85, abs=1e-12) and (src["t_low_c"], src["t_high_c"]) == (350.0, 450.0)
    case = v["cases"]["x"]["by_source"][src["name"]]
    assert case["kw_recovered"] == pytest.approx(0.85 * phi.ASSUMED["recovery_gas_cooler"]["value"], rel=1e-12), "the recovery fraction (0.7) is applied exactly once"


# ------------------------------------------------------------------ (b) the energy sums close

@pytest.mark.parametrize("mode", ["default", "heat_only"])
def test_the_energy_sums_close_in_every_case(runs, mode):
    v = runs[mode][("PLANT", "HeatIntegration")]["value"]
    for name, c in v["cases"].items():
        assert c["source_recovered_counted_kw"] - c["demand_total_kw"] == pytest.approx(c["net_energy_basis_kw"], abs=1e-9), name
        assert c["matched_kw"] + c["unmet_kw"] == pytest.approx(c["demand_total_kw"], abs=1e-9), name
        assert c["matched_kw"] + c["unused_source_kw"] == pytest.approx(c["source_recovered_counted_kw"], abs=1e-9), name
        assert sum(x["kw_recovered"] for x in c["by_source"].values()) == pytest.approx(c["source_recovered_counted_kw"], abs=1e-9)
        assert c["supplementary_fuel_kw"] == c["unmet_kw"] and c["supplementary_fuel_as_h2_kg_day"] == pytest.approx(c["unmet_kw"] * 24.0 / phi.H2_LHV_KWH_PER_KG, rel=1e-12)
        assert c["temperature_level_mismatch_kw"] == pytest.approx(min(c["unmet_kw"], c["unused_source_kw"]), abs=1e-12)
    ass = {x["name"]: x["value"] for x in v["assumed_inputs"]}
    for src in v["sources"]:
        for c in v["cases"].values():
            got = c["by_source"][src["name"]]["kw_recovered"]
            want = src["kw_available"] * ass[src["recovery_key"]] if src["counted"] and src["recoverable_in_principle"] and src["recovery_key"] else 0.0
            assert got == pytest.approx(want, rel=1e-12, abs=1e-15), (src["name"], "recovered = available x its recovery fraction, applied once")
    sinks = {s["name"]: s["kw"] for s in v["sinks"]}
    assert v["energy_balance_demand_kw"] == pytest.approx(sum(list(sinks.values())[:4]), abs=1e-12)
    eb = runs[mode][("GA-001", "EnergyBalance")]["value"]["cases"][MID]
    assert v["energy_balance_demand_kw"] == pytest.approx(eb["heat_demand_total_kw"], abs=1e-9), "the four demands are exactly (GA-001, EnergyBalance)'s"
    fl = next(s for s in v["sources"] if s["name"].startswith("flue gas"))
    assert fl["kw_available"] + fl["stack_loss_kw"] == pytest.approx(runs[mode][("GA-001", "EnergyBalance")]["value"]["tail_gas"]["chemical_kw"], abs=1e-9)
    bands = v["steam_band_split"]
    assert sum(bands.values()) == pytest.approx(1.0, abs=1e-12)


def test_the_tail_gas_is_counted_once_and_only_in_heat_only(runs):
    for mode, counted in (("default", False), ("heat_only", True)):
        v = runs[mode][("PLANT", "HeatIntegration")]["value"]
        chem = next(s for s in v["sources"] if s["name"].startswith("PSA tail-gas"))
        fl = next(s for s in v["sources"] if s["name"].startswith("flue gas"))
        assert chem["counted"] is False, "the chemical energy is reported, never counted (the flue gas carries it)"
        assert fl["counted"] is counted
        by = _mid(runs[mode])["by_source"]
        assert (by[fl["name"]]["kw_recovered"] > 0) is counted and by[chem["name"]]["kw_recovered"] == 0.0


# ------------------------------------------------------------------ (c) Missing terms are listed, never zero

def test_missing_terms_are_listed_and_a_missing_source_is_none_not_zero(runs):
    v = runs["default"][("PLANT", "HeatIntegration")]["value"]
    assert len(v["missing_terms"]) >= 7 and any("air-separation" in t for t in v["missing_terms"]) and any("burner" in t for t in v["missing_terms"])
    assert [m["name"] for m in v["missing_sinks"]][0].startswith("HB-016") and all(m["status"] == ps.STATUS_MISSING and "kw" not in m for m in v["missing_sinks"])
    snap = copy.deepcopy(runs["default"])
    del snap[("GA-001", "CarbonAccounting")]
    v2 = phi.compute(getter(snap))
    cb = next(s for s in v2["sources"] if s["name"].startswith("carbon-black"))
    assert cb["status"] == ps.STATUS_MISSING and cb["kw_available"] is None and cb["counted"] is False
    assert "missing_reason" in phi.compute(lambda k: None)                              # a Missing required input gives a reason, not numbers


# ------------------------------------------------------------------ (d) both modes, recomputed identically

@pytest.mark.parametrize("mode", ["default", "heat_only"])
def test_the_key_is_published_in_both_modes_and_recomputes_identically(runs, mode):
    snap = runs[mode]
    e = snap[("PLANT", "HeatIntegration")]
    assert e["status"] == ps.STATUS_CALCULATED and e["value"]["tail_gas_mode"] == ("regasify" if mode == "default" else "heat_only")
    again = phi._native(phi.compute(getter(snap)))
    stored = json.loads(json.dumps(e["value"], sort_keys=True, default=str))
    fresh = json.loads(json.dumps(again, sort_keys=True, default=str))
    assert _same(stored, fresh) is True, "the published value is the pure function of the published state (floats to 1e-12: the engine reads the lagged tail gas in the last digits)"
    assert json.dumps(phi._native(phi.compute(getter(snap))), sort_keys=True) == json.dumps(again, sort_keys=True), "two evaluations are bit-identical"


# ------------------------------------------------------------------ (e) mutates nothing, nothing reads it

def test_computing_the_key_mutates_no_state(runs):
    snap = runs["default"]
    before = json.dumps(_ser(snap), sort_keys=True)
    phi.compute(getter(snap))
    phi.compute(getter(snap), assumptions={"recovery_gas_cooler": 0.9})
    phi.heat_integration(getter(snap))                                  # the registered model function, not only compute()
    assert json.dumps(_ser(snap), sort_keys=True) == before


def test_the_key_does_not_depend_on_the_energybalance_entry_so_that_stays_a_leaf():
    engine = se.SimulationEngine(sps.SharedPlantState())
    from python import ga001_gasifier_model as ga001
    ga001.register_ga001(engine)
    spec = engine._models[("PLANT", "HeatIntegration")]
    eb_key = ("GA-001", "EnergyBalance")
    assert eb_key not in phi.DEPENDS_ON and eb_key not in spec["depends_on"] and eb_key not in spec["lagged_depends_on"]
    assert list(spec["depends_on"]) == phi.DEPENDS_ON + [ga001.GASIFYING_AGENT_KEY] and list(spec["lagged_depends_on"]) == phi.LAGGED          # task A1 (deliberate edit): the agent switch is declared at registration, not in the published inputs (phi.DEPENDS_ON)


def test_nothing_reads_the_key_and_no_model_depends_on_it():
    engine = se.SimulationEngine(sps.SharedPlantState())
    from python import ga001_gasifier_model as ga001
    ga001.register_ga001(engine)
    key = ("PLANT", "HeatIntegration")
    assert key in engine._models
    for k, spec in engine._models.items():
        if k != key:
            assert key not in spec["depends_on"] and key not in spec["lagged_depends_on"], k
    hits = []
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "outputs", ".venv", "venv", "node_modules")]
        for name in files:
            rel = os.path.relpath(os.path.join(base, name), ROOT).replace(os.sep, "/")
            if not name.endswith(".py") or rel.startswith("tests/") or rel in ("python/plant_heat_integration.py", "scripts/run_heat_integration_report.py"):
                continue
            text = open(os.path.join(base, name), encoding="utf-8").read()
            if re.search(r"plant_heat_integration|HeatIntegration", text):
                hits.append(rel)
    # LEDGER (deliberate edit): python/ledger_coverage.py names the module in its scan list and python/ledger_rows.py reads its ASSUMED constants for the design-basis ledger; neither reads the KEY
    assert hits == ["python/ga001_gasifier_model.py", "python/ledger_coverage.py", "python/ledger_rows.py"], hits               # the registration line + the two ledger modules that name the module


# ------------------------------------------------------------------ (f) nothing else moved, (g) the key count rises by exactly one

@pytest.mark.parametrize("label,fixture_key", [("default", "default|20"), ("heat_only", "heat_only|20")])
def test_every_entry_of_origin_main_is_unchanged_in_both_modes(runs, main_snap, label, fixture_key):
    new = _ser(runs[label])
    # LEDGER D2 / WORDING W1 (deliberate edit): notes were reworded after this fixture was made. forward() applies the old -> new pairs of tests/_d2_wording.py to the FIXTURE, so the live
    # snapshot is compared as it is and an old phrase returning in it is a difference.
    old = _d2_wording.forward(main_snap[fixture_key])
    assert len(old) == 120 and set(old) <= set(new)
    skip = {"GA-001-INPUT|tail_gas_mode"} if label == "heat_only" else set()          # in heat_only the switch's own entry is this test's override (its model name differs)
    bad = {k: _same(old[k], new[k]) for k in old if k not in skip}
    assert {k: v for k, v in bad.items() if v is not True} == {}, "a gas-side, energy-key, carbon or hydrogen entry moved"


@pytest.mark.parametrize("label,fixture_key", [("default", "default|20"), ("heat_only", "heat_only|20")])
def test_the_persisted_key_count_rises_by_exactly_one_and_none_is_lost(runs, main_snap, label, fixture_key):
    new = {f"{k[0]}|{k[1]}" for k in runs[label]}
    old = set(main_snap[fixture_key])
    assert old - new == set(), sorted(old - new)
    assert new - old == {KEY, A1_KEY, A1_3_KEY} and len(new) == len(old) + 3 == 123          # A1 (deliberate edit): +1 = the switch input (GA-001-INPUT, gasifying_agent); A1.3 adds (GA-001, AgentConsistency): 122
    assert len(old) / len(new) > 0.9                                      # growth never trips the runtime's 90 % shrink guard


def test_the_runtimes_shrink_guard_accepts_the_new_set(main_snap, runs):
    spec = importlib.util.spec_from_file_location("run_continuous_cycle_under_test", os.path.join(ROOT, "scripts", "run_continuous_cycle.py"))
    driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)
    old = {tuple(k.split("|", 1)) for k in main_snap["default|20"]}
    new = set(runs["default"])
    assert driver.check_shrink(old, new) is None and driver.check_shrink(new, old) is None


# ------------------------------------------------------------------ (h) a source below the need's level is a mismatch, not counted

def test_heat_below_the_needs_level_is_reported_as_a_mismatch_and_not_counted(runs):
    """A gasifier at 120 degC with 20 times the gas flow: 56 kW of gas heat is released between 65 and 120 degC. It can serve only the needs at 100 degC and below (the low end of
    the liquid-heating bands, part of the air preheat and the reheat, the dryer), about 14 kW; it cannot serve evaporation at 159 degC, superheat or the 350 degC reheat.
    The rest EXISTS (it is recovered) but is neither matched nor counted: it is the level mismatch, and it is named."""
    def outputs(e):
        return dict(e, value=dict(e["value"], dry_flow_nm3_h=20.0 * e["value"]["dry_flow_nm3_h"], wet_flow_nm3_h=20.0 * e["value"]["wet_flow_nm3_h"]))
    get, _ = _synthetic_get(runs, {("GA-001", "Outputs"): outputs, ("GA-001-INPUT", "operating_temperature_C"): lambda e: dict(e, value=120.0)})
    c = phi.compute(get, lhv_cases={"x": 17.5}, duty_fn=lambda lhv: (0.0, ps.STATUS_CALCULATED))["cases"]["x"]
    assert c["unmet_kw"] > 10.0 and c["unused_source_kw"] > 10.0 and c["temperature_level_mismatch_kw"] > 10.0
    assert c["matched_kw"] + c["unused_source_kw"] == pytest.approx(c["source_recovered_counted_kw"], abs=1e-9)
    assert c["matched_kw"] < 20.0, "only the low-level needs are served"
    assert c["temperature_level_mismatch_kw"] == pytest.approx(min(c["unmet_kw"], c["unused_source_kw"]), abs=1e-12)
    assert c["mismatch_share_of_unmet"] == pytest.approx(c["temperature_level_mismatch_kw"] / c["unmet_kw"], abs=1e-12) and 0.0 < c["mismatch_share_of_unmet"] < 1.0
    gas = next(n for n in c["by_source"] if n.startswith("product-gas"))
    assert c["by_source"][gas]["kw_unused_level_or_surplus"] > 10.0, "gas heat below every unmet need's level stays unused"
    # at the real gasifier temperature the same kind of heat is released up to 950 degC and every need is served as far as the energy goes: no mismatch
    assert phi.compute(getter(runs["default"]), lhv_cases={"x": 17.5})["cases"]["x"]["temperature_level_mismatch_kw"] == 0.0


# ------------------------------------------------------------------ constants are named and tagged

def test_every_constant_and_assumed_input_is_named_tagged_and_in_range(runs):
    v = runs["default"][("PLANT", "HeatIntegration")]["value"]
    for a in v["assumed_inputs"]:
        assert a["status"] == ps.STATUS_ASSUMED and a["low"] <= a["value"] <= a["high"] and a["basis"], a["name"]
    assert phi.DH_WGS_KJ_MOL == pytest.approx(-41.158, abs=1e-9)
    assert phi.H2_LHV_KWH_PER_KG == pytest.approx(33.3, abs=0.05)
    for name in ("steam_6bar", "dh_wgs_kj_mol", "h2_lhv_kwh_per_kg"):
        assert v["constants"][name]["status"] in (ps.STATUS_ESTIMATED, ps.STATUS_CALCULATED) and v["constants"][name]["source"] or name == "steam_6bar"
    assert v["constants"]["steam_6bar"]["status"] == ps.STATUS_ESTIMATED and "steam tables" in v["constants"]["steam_6bar"]["source"]


# ------------------------------------------------------------------ (i) no database / network, no engine file but the registration line

def test_no_database_or_network_call(fake):
    assert fake.calls == [], fake.calls


def test_the_module_has_no_database_network_or_scada_code():
    code = "\n".join(line for line in open(os.path.join(ROOT, "python", "plant_heat_integration.py"), encoding="utf-8").read().splitlines() if not line.lstrip().startswith("#"))
    for forbidden in (r"\bimport requests\b", r"\burllib\b", r"\bimport supabase\b", r"\bcreate_client\b", r"\.upsert\(", r"\.table\(", r"\.execute\(", r"streamlit"):
        assert not re.search(forbidden, code), forbidden


def test_this_tasks_commits_touch_the_engine_only_at_the_registration_line():
    """Scoped to this task's commits (messages start with 'Heat integration'). Skipped when git or origin/main is unavailable."""
    try:
        subprocess.run(["git", "rev-parse", "--verify", "origin/main"], cwd=ROOT, capture_output=True, check=True)
        names = subprocess.run(["git", "log", "origin/main..HEAD", "--grep=^Heat integration", "--name-only", "--format="], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
        diff = subprocess.run(["git", "diff", "origin/main..HEAD", "--", "python/ga001_gasifier_model.py"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except Exception:                                                   # noqa: BLE001
        pytest.skip("git history not available")
    subjects = subprocess.run(["git", "log", "origin/main..HEAD", "--format=%s"], cwd=ROOT, capture_output=True, text=True).stdout.splitlines()
    if not subjects or not all(s.startswith("Heat integration") for s in subjects):
        pytest.skip("not a heat-integration range")
    forbidden = {"python/simulation_engine.py", "python/shared_plant_state.py", "python/tab1_integration.py", "python/dynamics.py", "python/plant_status.py", "scripts/run_continuous_cycle.py",
                 "requirements.txt", "data/equipment_registry.json", "app.py", "python/ui_transient_tab.py"}
    assert not (set(names) & forbidden) and not [n for n in names if n.startswith(".github/")], sorted(set(names) & forbidden)
    added = [l[1:].strip() for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++")]
    removed = [l for l in diff.splitlines() if l.startswith("-") and not l.startswith("---")]
    assert removed == [] and added == ["# Read-only plant heat source / sink inventory ((\"PLANT\", \"HeatIntegration\"), a leaf like the two above; heat-integration stage 1).",
                                      "from . import plant_heat_integration", "plant_heat_integration.register(engine)"], (added, removed)
