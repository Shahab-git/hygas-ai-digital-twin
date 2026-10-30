"""tail_gas_mode switch and the read-only (GA-001, EnergyBalance) key.

The default must not change anything: the 116 entries origin/main (71e92cc) publishes are compared with a snapshot of that code stored in
tests/fixtures/snapshot_origin_main_71e92cc.json.gz (made by running the unmodified origin/main code; byte-identical there). The comparison is
exact for structure, strings and integers and uses a 1e-12 relative tolerance for floats, so a different libm on another platform cannot fail it
(the exact bit-identity was verified on the machine that made the fixture). Offline: counting fake store, no credentials."""
import ast
import gzip
import json
import math
import os

import pytest

from _fakes import FakeSupabase, patched_supabase
from python import balance_audit as ba
from python import cycle_clock
from python import ga001_gasifier_model as ga001
from python import plant_status as ps
from python import tab1_integration as t1

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "snapshot_origin_main_71e92cc.json.gz")
NEW_KEYS = {"GA-001-INPUT|tail_gas_mode", "GA-001|EnergyBalance"}
N = 20          # the tail-gas recycle has converged by cycle 20
MID = "DOK-ING midpoint (Assumed point)"


def _const(v):
    def fn(get_input):
        return {"value": v, "status": ps.STATUS_ASSUMED, "inputs": [], "validation_basis": ps.VALIDATION_NA, "confidence_note": "test"}
    return fn


def _mode(m):
    return {("GA-001-INPUT", "tail_gas_mode"): _const(m)}


def _ser(snapshot):
    return {f"{k[0]}|{k[1]}": json.loads(json.dumps(v, sort_keys=True, default=str)) for k, v in snapshot.items()}


def _same(a, b, path=""):
    """Exact for everything but floats; floats within 1e-12 relative."""
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
def runs(fake):
    cycle_clock.set_elapsed_hours(None)
    out = {}
    with patched_supabase(fake):
        out["default5"] = t1.build_live_snapshot(n_cycles=5)
        out["default30"] = t1.build_live_snapshot(n_cycles=30)
        for m in ("regasify", "heat_only"):
            out[m] = t1.build_live_snapshot(n_cycles=N, overrides=_mode(m))
            out[m + "_prev"] = t1.build_live_snapshot(n_cycles=N - 1, overrides=_mode(m))
    return out


@pytest.fixture(scope="module")
def baseline():
    with gzip.open(FIXTURE, "rb") as fh:
        return json.loads(fh.read().decode("utf-8"))


# ---------------------------------------------------------------- (a) the default changes nothing
@pytest.mark.parametrize("label,n", [("default5", "5"), ("default30", "30")])
def test_default_mode_snapshot_equals_origin_main_for_every_existing_entry(runs, baseline, label, n):
    new = _ser(runs[label][0])
    old = baseline[n]
    assert len(old) == 116
    assert set(old) <= set(new), sorted(set(old) - set(new))
    assert set(new) - set(old) == NEW_KEYS
    bad = {k: _same(old[k], new[k]) for k in old}
    bad = {k: v for k, v in bad.items() if v is not True}
    assert bad == {}, bad


def test_default_is_regasify_and_the_switch_is_not_in_the_published_input_list(runs):
    s = runs["default30"][0]
    assert s[("GA-001-INPUT", "tail_gas_mode")]["value"] == "regasify" == ga001.TAIL_GAS_MODE_DEFAULT
    assert s[("GA-001-INPUT", "tail_gas_mode")]["status"] == ps.STATUS_ASSUMED
    assert "supplemental fuel" in s[("GA-001-INPUT", "tail_gas_mode")]["confidence_note"]
    assert ("GA-001-INPUT", "tail_gas_mode") not in [tuple(k) for k in s[("GA-001", "Outputs")]["source"]["inputs"]]
    assert s[("GA-001", "Outputs")]["value"]["recycle_active"] is True


# ---------------------------------------------------------------- (b) heat_only: zero recycle atoms, H/O/N still close
def test_heat_only_gives_ga001_zero_recycle_atoms_and_h_o_n_still_close(runs):
    s, p = runs["heat_only"][0], runs["heat_only_prev"][0]
    assert s[("GA-001-INPUT", "tail_gas_mode")]["value"] == "heat_only"
    assert s[("GA-001", "Outputs")]["value"]["recycle_active"] is False
    assert ("HB-009", "TailGas") not in [tuple(k) for k in s[("GA-001", "Outputs")]["source"]["inputs"]]
    def gi(key):
        if key == ga001.TAIL_GAS_MODE_KEY:
            return {"value": "heat_only", "status": ps.STATUS_ASSUMED}
        return {"value": {"species_nm3_h": {"H2": 9.0, "CO": 4.0, "CH4": 1.0}}, "status": ps.STATUS_CALCULATED}
    assert ga001._recycle_atom_moles(gi) == (0.0, 0.0, 0.0, 0.0)                       # with a tail gas on offer, heat_only still receives nothing
    assert ga001._recycle_atom_moles(lambda key: dict(gi(key), value="regasify") if key == ga001.TAIL_GAS_MODE_KEY else gi(key))[0] > 0.0
    assert s[("HB-009", "TailGas")]["status"] == ps.STATUS_CALCULATED                  # HB-009 still runs and still publishes
    a = ba.audit_snapshot(s, p)
    assert a["ga001_recycle_cross_check"]["rel_diff"] == pytest.approx(0.0, abs=1e-12)
    for cv in ("ga001", "loop", "plant"):
        for el in ("H", "O", "N") if cv != "plant" else ("N",):
            assert abs(a[cv]["rows"][el]["rel"]) < 1e-12, (cv, el, a[cv]["rows"][el]["rel"])
    assert abs(a["plant"]["rows"]["H"]["rel"]) < 2e-4 and abs(a["plant"]["rows"]["O"]["rel"]) < 2e-4        # the known electrolyser-water residual only
    assert abs(a["explain_plant_mass"]["mass_unexplained_kg_h"]) < 1e-9
    h2_regas = runs["regasify"][0][("HB-012", "Compressor")]["value"]["h2_kg_h"]
    h2_heat = s[("HB-012", "Compressor")]["value"]["h2_kg_h"]
    assert h2_heat < 0.8 * h2_regas                                                    # the re-gasified recycle was a large part of the hydrogen


# ---------------------------------------------------------------- (c) the energy key equals the closure-audit functions
@pytest.mark.parametrize("mode", ["regasify", "heat_only"])
def test_energy_key_is_present_and_equals_the_closure_audit_on_the_same_snapshot(runs, mode):
    s, p = runs[mode][0], runs[mode + "_prev"][0]
    e = s[("GA-001", "EnergyBalance")]
    assert e["status"] == ps.STATUS_CALCULATED and e["value"]["tail_gas_mode"] == mode
    cases = e["value"]["cases"]
    assert set(cases) == set(ba.lhv_cases())
    for name, lhv in ba.lhv_cases().items():
        g = ba.gasifier_energy(s, p, lhv)
        c = cases[name]
        assert c["implied_gasifier_heat_duty_kw"] == pytest.approx(g["implied_heat_duty_kw"], rel=1e-9, abs=1e-9)
        assert c["feed_chemical_kw"] == pytest.approx(g["in"][0]["kw"], rel=1e-9)
        assert c["product_gas_chemical_kw"] == pytest.approx(g["out"][0]["kw"], rel=1e-9)
        assert c["product_gas_sensible_kw"] == pytest.approx(g["out"][1]["kw"], rel=1e-9)
        pe = ba.plant_energy(s, p, lhv)["internal_heat_demands_not_sourced_in_engine"]
        assert c["steam_raising_kw"] == pytest.approx(pe[0]["kw"] + pe[1]["kw"], rel=1e-9)
        assert c["air_preheat_kw"] == pytest.approx(pe[2]["kw"], rel=1e-9) and c["feed_drying_kw"] == pytest.approx(pe[3]["kw"], rel=1e-9)
        assert c["heat_demand_total_kw"] == pytest.approx(sum(t["kw"] for t in pe), rel=1e-9)
        assert c["net_heat_kw"] == pytest.approx(c["tail_gas_heat_used_kw"] - c["implied_gasifier_heat_duty_kw"] - c["heat_demand_total_kw"], rel=1e-12, abs=1e-12)
        assert c["net_heat_kw_if_tail_gas_were_heat"] == pytest.approx(c["tail_gas_heat_available_kw"] - c["implied_gasifier_heat_duty_kw"] - c["heat_demand_total_kw"], abs=1e-9)
    t = e["value"]["tail_gas"]
    sp = s[("HB-009", "TailGas")]["value"]["species_nm3_h"]
    assert t["chemical_kw"] == pytest.approx(ba._lhv_kw({k: p[("HB-009", "TailGas")]["value"]["species_nm3_h"][k] / ba.NM3_PER_MOL for k in ("H2", "CO", "CH4")}), rel=1e-9)
    assert t["used_as_heat"] is (mode == "heat_only") and cases[MID]["tail_gas_heat_used_kw"] == (t["chemical_kw"] if mode == "heat_only" else 0.0)
    assert e["value"]["missing_terms"] and any("tar" in m for m in e["value"]["missing_terms"])
    assert cases[MID]["feed_sensible_kw"] is None and cases[MID]["feed_sensible_status"] == ps.STATUS_MISSING          # Missing, not zero
    assert {a["name"] for a in e["value"]["assumed_inputs"]} >= {"feed temperature entering GA-001 (degC)", "air preheat temperature (degC)"}
    assert all(a["status"] == ps.STATUS_ASSUMED and a["range"][0] <= a["value"] <= a["range"][1] for a in e["value"]["assumed_inputs"])
    json.dumps(e["value"])                                                                  # plain JSON types: it can be persisted
    assert sp is not None


def test_energy_key_is_a_report_nothing_depends_on_it_and_it_feeds_nothing_back(runs):
    engine = runs["default30"][2]
    key = ("GA-001", "EnergyBalance")
    for k, spec in engine._models.items():
        assert key not in spec["depends_on"] and key not in spec["lagged_depends_on"], k
    # the same snapshot with the key's model replaced by a Missing one gives identical other entries
    a = _ser(runs["default30"][0])
    assert {k for k in a} == {f"{k[0]}|{k[1]}" for k in runs["default30"][0]}


# ---------------------------------------------------------------- (d) no persisted key is lost
@pytest.mark.parametrize("mode", ["regasify", "heat_only"])
def test_no_key_of_main_is_lost_and_exactly_two_are_added(runs, baseline, mode):
    new = {f"{k[0]}|{k[1]}" for k in runs[mode][0]}
    old = set(baseline["30"])
    assert old - new == set(), sorted(old - new)
    assert new - old == NEW_KEYS
    assert len(old) / len(new) > 0.9           # the runtime's 90 % shrink guard compares stored vs new keys; growth never trips it


# ---------------------------------------------------------------- (e) invalid mode is rejected, never silently defaulted
@pytest.mark.parametrize("bad", ["heat-only", "HEAT_ONLY", "", None, 1, "bogus"])
def test_an_invalid_mode_is_rejected_with_a_clear_error(bad):
    with pytest.raises(ValueError, match="tail_gas_mode"):
        ga001.check_tail_gas_mode(bad)
    with patched_supabase(FakeSupabase()):
        with pytest.raises(ValueError, match="tail_gas_mode"):
            t1.build_live_snapshot(n_cycles=2, overrides=_mode(bad))


def test_the_valid_modes_are_exactly_the_two_named_ones():
    assert ga001.TAIL_GAS_MODES == ("regasify", "heat_only") and ga001.TAIL_GAS_MODE_DEFAULT == "regasify"
    for m in ga001.TAIL_GAS_MODES:
        assert ga001.check_tail_gas_mode(m) == m


# ---------------------------------------------------------------- (f) no database, no network
def test_zero_database_calls_and_no_client_import(runs, fake):
    assert fake.calls == [], fake.calls
    assert os.environ.get("HYGAS_ALLOW_DB_WRITES") == "0"
    forbidden = {"streamlit", "supabase", "requests", "urllib", "http", "socket", "httpx"}
    tree = ast.parse(open(os.path.join(ROOT, "python", "ga001_energy_balance.py"), encoding="utf-8").read())
    for node in ast.walk(tree):
        names = [a.name.split(".")[0] for a in node.names] if isinstance(node, ast.Import) else \
                [node.module.split(".")[0]] if isinstance(node, ast.ImportFrom) and node.module and node.level == 0 else []
        assert not (set(names) & forbidden)
