"""Gasifying-agent study (scripts/run_agent_comparison.py): the scenarios are the unchanged engine with only the oxidant's N2 (or ER / steam ratio) changed.

Guards: the wrapper at the air fraction reproduces the committed snapshot of origin/main; every scenario closes C/H/O/N; N2 in an O2-blown case is zero when the feed has no N
and equals the fuel N otherwise; the closure check can actually fail; the script makes no database call; this study's commits touch no engine file. Offline: counting fake store."""
import importlib.util
import json
import gzip
import math
import os
import subprocess

import pytest

from _fakes import FakeSupabase, patched_supabase
from python import balance_audit as ba
from python import cycle_clock
from python import ga001_gasifier_model as ga001
from python import tab1_integration as t1

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(ROOT, "scripts", "run_agent_comparison.py")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "snapshot_origin_main_198bfcb.json.gz")
N, NP = 5, 4


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("run_agent_comparison", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def fake():
    return FakeSupabase()


@pytest.fixture(scope="module")
def main_snap():
    with gzip.open(FIXTURE, "rb") as fh:
        return json.loads(fh.read().decode("utf-8"))["default|5"]


def _same(a, b, path=""):
    if isinstance(a, float) or isinstance(b, float):
        return (math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-15) or [path]) if isinstance(a, (int, float)) and isinstance(b, (int, float)) else [path]
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
def runs(mod, fake):
    cycle_clock.set_elapsed_hours(None)
    mod.N_CONV = N
    out = {}
    with patched_supabase(fake):
        for sc in mod.SCENARIOS:
            out[sc["id"]] = mod.run_scenario(sc, "regasify")
        out["S2_heat_only"] = mod.run_scenario([s for s in mod.SCENARIOS if s["id"] == "S2"][0], "heat_only")
    return out


def _sc(mod, sid):
    return [s for s in mod.SCENARIOS if s["id"] == sid][0]


# ------------------------------------------------------------------ S0 and the wrapper reproduce main
def test_s0_reproduces_the_main_snapshot_values_exactly(runs, main_snap):
    r = runs["S0"]
    out = main_snap["GA-001|Outputs"]["value"]
    assert r["h2_kg_day"] == main_snap["HB-012|Compressor"]["value"]["h2_kg_h"] * 24.0
    assert r["pct"]["N2"] == out["N2_mol_pct_dry"] and r["pct"]["H2"] == out["H2_mol_pct_dry"] and r["dry_flow"] == out["dry_flow_nm3_h"]
    assert r["lhv"] == main_snap["SA-006|Reading"]["value"]


def test_the_wrapper_at_the_air_fraction_changes_nothing(mod, fake, main_snap):
    """The wrapper with f = 0.21 must give the main snapshot again (floats within 1e-12): it only swaps the oxidant N2, and air is the identity."""
    with patched_supabase(fake):
        snap = t1.build_live_snapshot(n_cycles=N, overrides={("GA-001", "Outputs"): mod.make_wrapper(mod.AIR_O2_FRACTION)})[0]
    new = {f"{k[0]}|{k[1]}": json.loads(json.dumps(v, sort_keys=True, default=str)) for k, v in snap.items()}
    bad = {}
    for k, old in main_snap.items():
        a, b = json.loads(json.dumps(old, sort_keys=True, default=str)), new[k]
        a, b = dict(a, confidence_note=""), dict(b, confidence_note="")           # the notes quote numbers to full repr; the values are compared to 1e-12
        r = _same(a, b)
        if r is not True:
            bad[k] = r
    assert bad == {}, bad


def test_swap_oxidant_n2_by_hand(mod):
    # 100 mol dry gas: H2 30, CO 20, CO2 10, CH4 0, N2 40 (all fuel-free of N: fuel N2 = 0); O2 in the air that carried the N2: 40 / (0.79/0.21)
    out = {"dry_flow_nm3_h": 100 * ga001.NM3_PER_MOL, "wet_flow_nm3_h": 125 * ga001.NM3_PER_MOL, "H2_mol_pct_dry": 30.0, "CO_mol_pct_dry": 20.0, "CO2_mol_pct_dry": 10.0,
           "CH4_mol_pct_dry": 0.0, "N2_mol_pct_dry": 40.0, "H2O_mol_pct_wet": 20.0, "recycle_active": False}
    o2 = 40.0 / (0.79 / 0.21)
    pure = mod.swap_oxidant_n2(out, 0.0, 1.0)
    assert pure["N2_mol_pct_dry"] == pytest.approx(0.0, abs=1e-12) and pure["H2_mol_pct_dry"] == pytest.approx(100 * 30 / 60) and pure["dry_flow_nm3_h"] == pytest.approx(60 * ga001.NM3_PER_MOL)
    assert pure["wet_flow_nm3_h"] == pytest.approx(85 * ga001.NM3_PER_MOL) and pure["H2O_mol_pct_wet"] == pytest.approx(100 * 25 / 85)
    half = mod.swap_oxidant_n2(out, 0.0, 0.5)
    assert half["N2_mol_pct_dry"] == pytest.approx(100 * o2 / (60 + o2))                       # N2 = O2 x (1-f)/f = O2 at f = 0.5
    fuel = mod.swap_oxidant_n2(dict(out, N2_mol_pct_dry=45.0), 5.0, 1.0)                        # fuel N2 stays
    assert fuel["N2_mol_pct_dry"] == pytest.approx(100 * 5 / 65)


# ------------------------------------------------------------------ closure
@pytest.mark.parametrize("key", ["S0", "S1a", "S1b", "S2", "S3", "S4a", "S4b", "S2_heat_only"])
def test_every_scenario_closes_c_h_o_n(runs, key):
    c = runs[key]["closure"]
    for cv in ("ga001", "loop"):
        for el in ("C", "H", "O", "N"):
            assert abs(c[cv][el]) < 1e-9, (key, cv, el, c[cv][el])


def test_the_closure_check_can_fail(mod, fake):
    """Claim the wrong oxidant for a given gas: nitrogen must not close. A skipped or trivial check would return ~0 here."""
    s2 = _sc(mod, "S2")
    ov = mod.overrides_for(s2, "regasify")
    with patched_supabase(fake):
        snap = t1.build_live_snapshot(n_cycles=N, overrides=ov)[0]
        prev = t1.build_live_snapshot(n_cycles=NP, overrides=ov)[0]
    right = mod.scenario_closure(snap, prev, s2)
    wrong = mod.scenario_closure(snap, prev, _sc(mod, "S0"))                  # S0's air N2 claimed for the O2-blown gas
    assert abs(right["ga001"]["N"]) < 1e-9 and abs(wrong["ga001"]["N"]) > 0.1
    assert abs(wrong["loop"]["N"]) > 0.1


# ------------------------------------------------------------------ nitrogen
def test_o2_blown_n2_is_the_fuel_n_and_zero_when_the_feed_has_none(mod, fake, runs):
    s2 = _sc(mod, "S2")
    with patched_supabase(fake):
        snap = t1.build_live_snapshot(n_cycles=N, overrides=mod.overrides_for(s2, "regasify"))[0]
        nofuel = {**mod.overrides_for(s2, "regasify"), ("GA-001-INPUT", "feedstock_composition"): mod._const({"C": 0.5, "H": 0.06, "O": 0.44, "N": 0.0})}
        snap0 = t1.build_live_snapshot(n_cycles=N, overrides=nofuel)[0]
    n2 = ba.gas_species_mol_h(snap[("GA-001", "Outputs")]["value"])["N2"]
    f = snap[("GA-001-INPUT", "dry_feed_rate_kg_h")]["value"]
    assert n2 == pytest.approx((1 - ga001.ASH_FRACTION) * 0.01 * f * 1000.0 / ga001.M_N / 2.0, rel=1e-9)         # fuel N only
    assert ba.gas_species_mol_h(snap0[("GA-001", "Outputs")]["value"])["N2"] == pytest.approx(0.0, abs=1e-9)
    assert snap0[("GA-001", "Outputs")]["value"]["N2_mol_pct_dry"] == pytest.approx(0.0, abs=1e-9)


@pytest.mark.parametrize("sid,f", [("S1a", 0.30), ("S1b", 0.50)])
def test_enriched_air_n2_follows_the_enrichment(mod, fake, runs, sid, f):
    sc = _sc(mod, sid)
    with patched_supabase(fake):
        snap = t1.build_live_snapshot(n_cycles=N, overrides=mod.overrides_for(sc, "regasify"))[0]
        prev = t1.build_live_snapshot(n_cycles=NP, overrides=mod.overrides_for(sc, "regasify"))[0]
    d = ba.ga001_terms(snap, prev)
    fuel_n2 = d["feed_atoms"]["N"] / 2.0
    n2 = ba.gas_species_mol_h(snap[("GA-001", "Outputs")]["value"])["N2"]
    assert n2 == pytest.approx(fuel_n2 + d["air_o2_mol_h"] * (1 - f) / f, rel=1e-9)
    assert runs["S0"]["pct"]["N2"] > runs["S1a"]["pct"]["N2"] > runs["S1b"]["pct"]["N2"] > runs["S2"]["pct"]["N2"]       # more O2 in the oxidant, less N2 in the gas


def test_the_steam_ratio_of_the_steam_only_scenarios_reaches_the_engine(mod, fake):
    seen = {}
    with patched_supabase(fake):
        for sid in ("S4a", "S4b"):
            snap = t1.build_live_snapshot(n_cycles=2, overrides=mod.overrides_for(_sc(mod, sid), "regasify"))[0]
            seen[sid] = (snap[("GA-001-INPUT", "steam_to_feed_ratio")]["value"], snap[("GA-001-INPUT", "equivalence_ratio")]["value"])
    assert seen == {"S4a": (0.4, 0.0), "S4b": (0.8, 0.0)}


def test_s3_has_s2s_gas_and_no_gas_phase_oxidant_in_the_energy(runs):
    a, b = runs["S2"], runs["S3"]
    assert a["pct"] == b["pct"] and a["h2_kg_day"] == b["h2_kg_day"]
    assert b["energy"][17.5]["duty"] != a["energy"][17.5]["duty"]                 # S3 has no oxidant sensible heat (the carrier terms are Missing)


# ------------------------------------------------------------------ no database, no engine edit
def test_the_script_made_no_database_call(runs, fake):
    assert fake.calls == [], fake.calls
    assert os.environ.get("HYGAS_ALLOW_DB_WRITES") == "0"


def test_this_studys_commits_touch_no_engine_file():
    """Scoped to the commits of this study (their messages start with 'Gasifying agent study'), so later legitimate engine work does not trip it.
    Skipped when git or origin/main is unavailable (e.g. a shallow CI checkout)."""
    try:
        subprocess.run(["git", "rev-parse", "--verify", "origin/main"], cwd=ROOT, capture_output=True, check=True)
        names = subprocess.run(["git", "log", "origin/main..HEAD", "--grep=^Gasifying agent study", "--name-only", "--format="], cwd=ROOT, capture_output=True,
                               text=True, check=True).stdout.split()
    except Exception:                                                   # noqa: BLE001
        pytest.skip("git history not available")
    allowed = {"scripts/run_agent_comparison.py", "tests/test_agent_comparison.py", "docs/gasifying_agent_study.md", "CLAUDE.md"}
    assert set(names) <= allowed, sorted(set(names) - allowed)
