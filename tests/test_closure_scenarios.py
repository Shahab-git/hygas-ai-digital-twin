"""Closure audit of the scenarios and the reference feeds, with enforced versus verified closure (task A5). READ-ONLY: the audit changes no result.

  * the case list (7 agent scenarios + 8 reference feeds, both tail_gas_modes) and a live run of S0 and S2 that audits without an engine edit; the committed `scenario_cases` baseline
    covers all 30 cases in both states and matches a fresh run (drift test); the existing `cases` of the baseline are unchanged versus origin/main;
  * a deliberately unbalanced stream is detected in every element row, a stream dropped from the plant sum is detected;
  * every closure row carries `closure_kind`; the kinds are pinned, the ENFORCED rows stay at round-off in every case while a VERIFIED row reacts to a perturbed independent side;
  * the energy rows list their Missing terms and never count them as zero;
  * every persisted entry equals the unmodified origin/main fixture (tests/fixtures/snapshot_origin_main_701de71.json.gz) in both tail-gas modes, the key count is unchanged, no database or
    network call is made.
Offline: counting fake store, no credentials."""
import copy
import gzip
import importlib.util
import json
import math
import os
import subprocess

import pytest

from _fakes import FakeSupabase, patched_supabase
from python import balance_audit as ba
from python import balance_closure_kind as bck
from python import balance_scenarios as bs
from python import plant_status as ps
from python import tab1_integration as t1

try:                                                    # present once the design-basis ledger branch is merged: three snapshot notes were reworded there (text only)
    import _d2_wording
    _undo = _d2_wording.undo
except ImportError:                                     # pragma: no cover
    def _undo(x):
        return x

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "snapshot_origin_main_701de71.json.gz")
BASELINE = os.path.join(ROOT, "docs", "balance_audit_baseline.json")
N = 30
CASE_S2 = "S2 oxygen-blown + steam 0.4 (same O2 as S0) | regasify"
CASE_S0 = "S0 current: air ER 0.25 + steam 0.4 | regasify"


def _script():
    spec = importlib.util.spec_from_file_location("run_balance_audit", os.path.join(ROOT, "scripts", "run_balance_audit.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def rba():
    return _script()


@pytest.fixture(scope="module")
def fake():
    return FakeSupabase()


@pytest.fixture(scope="module")
def specs(rba):
    return rba.scenario_specs()


@pytest.fixture(scope="module")
def live(rba, specs, fake):
    """The default snapshot (= case S0 | regasify, audited with the scenario machinery too) and the executed case S2 | regasify (30 cycles). Not the 30 cases: those are the committed
    baseline, compared in the drift test."""
    chosen = [s for s in specs if s["name"] == CASE_S2]
    with patched_supabase(fake):
        snap, prev = t1.build_live_snapshot(N)[0], t1.build_live_snapshot(N - 1)[0]
    return {"snap": snap, "prev": prev, "audit": ba.audit_snapshot(snap, prev, t1.compute_tab1_kpis(snap)), "res": rba.run_scenarios(chosen, states=(N,)),
            "s0": bs.audit_case(snap, prev, None, "air", None, None)}


@pytest.fixture(scope="module")
def baseline():
    with open(BASELINE, encoding="utf-8") as fh:
        return json.load(fh)


def _tol_ok(r):
    return r["verdict"] == ba.classify(r["rel"]) or r["rel"] != r["rel"]


# ------------------------------------------------------------------ (1) coverage

def test_the_case_list_is_the_seven_agent_scenarios_and_the_eight_feeds_in_both_modes(specs):
    agent = [s for s in specs if s["group"] == "agent"]
    feed = [s for s in specs if s["group"] == "feed"]
    assert len(agent) == 14 and len(feed) == 16 and {s["mode"] for s in specs} == {"regasify", "heat_only"}
    assert {s["name"].split(" ")[0] for s in agent} == {"S0", "S1a", "S1b", "S2", "S3", "S4a", "S4b"}
    labels = " ".join(s["name"] for s in feed)
    for f in ("default stand-in", "cotton", "wool", "polyethylene (PE)", "polypropylene (PP)", "polystyrene (PS)", "PET", "blend M1"):
        assert f in labels, f
    assert all("equivalent by construction" in s["note"] for s in agent if s["name"].startswith("S3 ")) and not any(s["note"] for s in agent if not s["name"].startswith("S3 "))


def test_scenario_and_feed_cases_audit_without_an_engine_edit_and_the_report_is_the_residual(live):
    for name, c in [(CASE_S2, live["res"][CASE_S2][N]), (CASE_S0, live["s0"])]:
        assert c["missing_inputs"] == [] and set(c["rows"]) == {"ga001", "loop", "plant"}, name
        for cv, rows in c["rows"].items():
            assert set(rows) == {"C", "H", "O", "N", "ash", "mass"}
            for q, r in rows.items():
                assert _tol_ok(r), (name, cv, q)                        # the verdict is the module's own classification of the residual, whatever it is
                assert r["closure_kind"] in bck.KINDS and r["closure_refs"]
        assert set(c["energy_gasifier"]) and set(c["energy_plant"])


def test_the_swapped_oxidant_artefact_is_reported_beside_the_scenario_aware_rows(live):
    c = live["res"][CASE_S2][N]
    assert c["oxidant"]["substituted_for_the_audit_air_terms"] is True
    assert abs(c["stock_rows"]["ga001"]["N"]["rel"]) > 0.9 and abs(c["rows"]["ga001"]["N"]["rel"]) < 1e-12        # stock audit: air assumed; scenario-aware: closes
    assert live["s0"]["oxidant"]["substituted_for_the_audit_air_terms"] is False and "stock_rows" not in live["s0"]


def test_the_committed_baseline_has_all_thirty_cases_in_both_states_and_none_is_unauditable(baseline, specs):
    sc = baseline["scenario_cases"]
    assert set(sc["cases"]) == {s["name"] for s in specs} and len(sc["cases"]) == 30 and sc["n_converged"] == 30 and sc["n_five"] == 5
    for name, states in sc["cases"].items():
        assert set(states) == {"5", "30"}, name
        for st in states.values():
            assert st["missing_inputs"] == [] and "error" not in st, name
            assert set(st) >= {"ga001", "loop", "plant", "plant_energy_closure_residual_kw", "ga001_implied_heat_duty_kw"}
            assert all(r["closure_kind"] in bck.KINDS for cv in ("ga001", "loop", "plant") for r in st[cv].values())


# ------------------------------------------------------------------ (4) baseline

def test_the_scenario_baseline_matches_a_fresh_run(live, baseline):
    for name, case in ((CASE_S2, live["res"][CASE_S2][N]), (CASE_S0, live["s0"])):
        fresh = bs.baseline_entry(case)
        assert bs.drift(baseline["scenario_cases"]["cases"][name]["30"], json.loads(json.dumps(fresh))) == [], name


def test_the_drift_check_itself_sees_an_edited_baseline(live, baseline):
    entry = json.loads(json.dumps(baseline["scenario_cases"]["cases"][CASE_S2]["30"]))
    entry["plant"]["H"]["residual_kg_h"] *= 1.01
    assert bs.drift(entry, json.loads(json.dumps(bs.baseline_entry(live["res"][CASE_S2][N])))) == ["/plant/H/residual_kg_h"]


def test_the_existing_baseline_cases_are_unchanged_versus_origin_main(baseline):
    try:
        old = subprocess.run(["git", "show", "origin/main:docs/balance_audit_baseline.json"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except Exception:                                    # noqa: BLE001 -- shallow checkout / no git
        pytest.skip("origin/main not available")
    if "scenario_cases" in json.loads(old):
        pytest.skip("origin/main already carries scenario_cases (this branch has been merged)")
    rest = {k: v for k, v in baseline.items() if k != "scenario_cases"}
    assert json.dumps(rest, indent=1) + "\n" == old.replace("\r\n", "\n"), "the original keys of the baseline changed"


# ------------------------------------------------------------------ (2) an unbalanced stream is detected

def _perturbed(live, key, field, factor=None, add=None):
    snap = copy.deepcopy(live["snap"])
    v = snap[key]["value"]
    if isinstance(field, tuple):
        v = v[field[0]]
        field = field[1]
    v[field] = v[field] * factor if factor is not None else v[field] + add
    return ba.audit_snapshot(snap, live["prev"], None)


@pytest.mark.parametrize("element,field,add", [("C", "CO2_mol_pct_dry", 0.5), ("H", "H2_mol_pct_dry", 0.5), ("O", "CO_mol_pct_dry", 0.5), ("N", "N2_mol_pct_dry", 0.5)])
def test_an_unbalanced_gas_stream_is_detected_in_each_ga001_element_row(live, element, field, add):
    a = _perturbed(live, ("GA-001", "Outputs"), field, add=add)
    row = a["ga001"]["rows"][element]
    assert abs(row["rel"]) > ba.TOL_STATED and row["verdict"] == ba.VERDICT_NO
    assert abs(live["audit"]["ga001"]["rows"][element]["rel"]) < ba.TOL_NUMERICAL


def test_an_unbalanced_ash_stream_is_detected(live, monkeypatch):
    real = ba.gmb.byproduct_mass_flows
    monkeypatch.setattr(ba.gmb, "byproduct_mass_flows", lambda f: dict(real(f), ash_kg_h=real(f)["ash_kg_h"] * 1.05))
    a = ba.audit_snapshot(live["snap"], live["prev"], None)
    assert a["ga001"]["rows"]["ash"]["verdict"] == ba.VERDICT_NO and a["plant"]["rows"]["ash"]["verdict"] == ba.VERDICT_NO


@pytest.mark.parametrize("species,elements", [("N2", ("N",)), ("CO2", ("C", "O")), ("H2", ("H",))])
def test_an_unbalanced_tail_gas_stream_is_detected_in_the_loop_and_the_plant(live, species, elements):
    snap = copy.deepcopy(live["snap"])
    snap[("HB-009", "TailGas")]["value"]["species_nm3_h"][species] *= 1.05
    a = ba.audit_snapshot(snap, live["prev"], None)
    for cv in ("loop", "plant"):
        for el in elements:
            assert abs(a[cv]["rows"][el]["rel"]) > ba.TOL_STATED, (cv, el)
        assert a[cv]["rows"]["mass"]["verdict"] in (ba.VERDICT_NO, ba.VERDICT_STATED)


@pytest.mark.parametrize("dropped,elements", [("quench condensate (GC-004)", ("H", "O")), ("WGS unreacted steam (knocked out, no equipment)", ("H", "O"))])
def test_a_stream_dropped_from_the_plant_sum_is_detected(live, monkeypatch, dropped, elements):
    real = ba.plant_terms

    def without(snapshot, previous_snapshot=None, scope="plant"):
        d = real(snapshot, previous_snapshot, scope)
        return dict(d, terms=[t for t in d["terms"] if t["name"] != dropped])
    monkeypatch.setattr(ba, "plant_terms", without)
    a = ba.audit_snapshot(live["snap"], live["prev"], None)
    assert any(t["name"] == dropped for t in real(live["snap"], live["prev"], "plant")["terms"])          # it really is a term of the real sum
    for el in elements:
        assert abs(a["plant"]["rows"][el]["rel"]) > ba.TOL_STATED, el
    assert a["plant"]["rows"]["mass"]["verdict"] == ba.VERDICT_NO


# ------------------------------------------------------------------ (3) closure_kind

PINNED = {("ga001", "C"): "ENFORCED", ("ga001", "H"): "ENFORCED", ("ga001", "O"): "ENFORCED", ("ga001", "N"): "ENFORCED", ("ga001", "ash"): "ENFORCED", ("ga001", "mass"): "ENFORCED",
          ("loop", "C"): "PARTLY", ("loop", "H"): "PARTLY", ("loop", "O"): "PARTLY", ("loop", "N"): "VERIFIED", ("loop", "ash"): "ENFORCED", ("loop", "mass"): "PARTLY",
          ("plant", "C"): "PARTLY", ("plant", "H"): "PARTLY", ("plant", "O"): "PARTLY", ("plant", "N"): "VERIFIED", ("plant", "ash"): "ENFORCED", ("plant", "mass"): "PARTLY",
          ("storage", "h2_created_by_clamp"): "VERIFIED", ("energy_gasifier", "implied_heat_duty"): "ENFORCED", ("energy_plant", "closure_residual"): "VERIFIED"}


def test_every_closure_row_has_its_kind_and_the_kinds_are_pinned(live):
    assert {k: v[0] for k, v in bck.TABLE.items()} == PINNED and len(PINNED) == 21
    a = live["audit"]
    for cv in ("ga001", "loop", "plant"):
        for q, r in a[cv]["rows"].items():
            assert r["closure_kind"] == PINNED[(cv, q)] and r["closure_why"] and r["closure_refs"], (cv, q)
    assert a["storage"]["closure_kind"] == "VERIFIED"
    assert all(e["closure_kind"] == "ENFORCED" for e in a["energy_gasifier"].values()) and all(e["closure_kind"] == "VERIFIED" for e in a["energy_plant"].values())
    assert {k: sum(1 for v in PINNED.values() if v == k) for k in bck.KINDS} == {"ENFORCED": 9, "VERIFIED": 4, "PARTLY": 8}
    assert bck.summary(a)["N"] == {"ENFORCED": 1, "VERIFIED": 2}


def test_enforced_rows_are_reported_as_closing_by_construction_and_every_reference_resolves(live):
    for (cv, q), (kind, why, refs) in bck.TABLE.items():
        info = bck.info(cv, q)
        assert info["closure_kind"] == kind and (("closes by construction" in info["closure_why"]) == (kind == "ENFORCED")), (cv, q)
        assert len(info["closure_refs"]) == len(refs) and all(r.rsplit(":", 1)[1].isdigit() for r in info["closure_refs"])
    assert bck.check_refs() == []


def test_labelling_changes_no_number(live):
    d = ba.ga001_terms(live["snap"], live["prev"])["terms"]
    rows = ba.closure(d)["rows"]                                    # closure() itself is not labelled
    assert all("closure_kind" not in r for r in rows.values())
    for q in ("C", "H", "O", "N", "ash", "mass"):
        assert live["audit"]["ga001"]["rows"][q]["residual_kg_h"] == rows[q]["residual_kg_h"]


def test_enforced_rows_stay_at_round_off_in_every_executed_case_and_a_verified_row_reacts_to_its_independent_side(live):
    assert all(abs(live["audit"]["ga001"]["rows"][q]["rel"]) < 1e-12 for q in ("C", "H", "O", "N", "ash", "mass"))
    for d in list(live["res"].values()) + [{N: live["s0"]}]:
        assert all(abs(d[N]["rows"]["ga001"][q]["rel"]) < 1e-12 for q in ("C", "H", "O", "N", "ash", "mass"))       # ENFORCED: cannot fail whatever the oxidant or the feed
        for cv in ("loop", "plant"):
            assert abs(d[N]["rows"][cv]["ash"]["rel"]) < 1e-12 and abs(d[N]["rows"][cv]["N"]["rel"]) < 1e-12
    snap = copy.deepcopy(live["snap"])
    snap[("HB-009", "TailGas")]["value"]["species_nm3_h"]["N2"] *= 1.02                 # the independent side of the VERIFIED N rows
    a = ba.audit_snapshot(snap, live["prev"], None)
    assert abs(a["loop"]["rows"]["N"]["rel"]) > 1e-3 and abs(a["plant"]["rows"]["N"]["rel"]) > 1e-3
    snap2 = copy.deepcopy(live["snap"])
    snap2[("HB-011", "Electrolyser")]["value"]["water_l_h"] *= 1.5                       # PARTLY plant H / O: its independent stream
    b = ba.audit_snapshot(snap2, live["prev"], None)
    assert abs(b["plant"]["rows"]["H"]["rel"]) > abs(live["audit"]["plant"]["rows"]["H"]["rel"]) * 1.5
    assert abs(b["ga001"]["rows"]["H"]["rel"]) < 1e-12                                   # ... which the ENFORCED GA-001 row never sees


# ------------------------------------------------------------------ (5) Missing energy terms

def test_missing_energy_terms_are_listed_and_never_counted_as_zero(live):
    c = live["res"][CASE_S2][N]
    m = c["energy_missing_terms"]
    assert any("tar" in t for t in m["gasifier"]) and any("heat loss" in t for t in m["gasifier"])
    assert any("heat loss" in t for t in m["plant"]) and any("boiler" in t for t in m["plant"]) and any("air-separation" in t for t in m["scenario"])
    assert any("stack" in t for t in m["not_in_either_balance"])
    g = ba.gasifier_energy(live["snap"], live["prev"], 17.5)
    p = ba.plant_energy(live["snap"], live["prev"], 17.5)
    words = ("tar", "heat loss", "boiler", "make-up water and cooling-tower", "nameplate", "refractory")
    for t in g["in"] + g["out"] + p["in"] + p["out"]:
        assert t["kw"] == t["kw"] and not any(w in t["name"] for w in words), t["name"]       # a Missing term is not a zero-valued line of the sum
    assert g["missing_terms"] and p["missing_terms"]


def test_the_scenario_missing_terms_follow_the_oxidant(live):
    assert bs.SCENARIO_MISSING_TERMS["air"] == [] and all(bs.SCENARIO_MISSING_TERMS[k] for k in ("gas", "carrier", "none"))
    assert live["s0"]["energy_missing_terms"]["scenario"] == []


# ------------------------------------------------------------------ (6) nothing else moved

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


def _const(v):
    def fn(get_input):
        return {"value": v, "status": ps.STATUS_ASSUMED, "inputs": [], "validation_basis": ps.VALIDATION_NA, "confidence_note": "test"}
    return fn


def _ser(snapshot):
    return {f"{k[0]}|{k[1]}": json.loads(json.dumps(v, sort_keys=True, default=str)) for k, v in snapshot.items()}


@pytest.mark.parametrize("mode,key", [("default", "default|20"), ("heat_only", "heat_only|20")])
def test_every_persisted_entry_equals_origin_main_in_both_tail_gas_modes_and_the_key_count_is_unchanged(fake, mode, key):
    with gzip.open(FIXTURE, "rb") as fh:
        old = json.loads(fh.read().decode("utf-8"))[key]
    with patched_supabase(fake):
        snap = t1.build_live_snapshot(20, overrides=None if mode == "default" else {("GA-001-INPUT", "tail_gas_mode"): _const("heat_only")})[0]
    new = _undo(_ser(snap))
    assert set(new) == set(old) and len(new) == 121
    bad = {k: _same(old[k], new[k]) for k in old if k != "GA-001-INPUT|tail_gas_mode"}
    assert {k: v for k, v in bad.items() if v is not True} == {}


def test_no_database_or_network_call_was_made(fake):
    assert [c for c in fake.calls if c[0] != "select"] == []
