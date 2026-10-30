"""Carbon bookkeeping: the conversion governs, the carbon black is derived, the 5 % rule is a cross-check, the guard covers C and N.

Guards the ACCOUNTING, not today's numbers: carbon closes to numerical precision across the sweeps; the derived carbon black equals the unconverted carbon
times the split; the cross-check feeds nothing; every gas-side entry is unchanged against the committed snapshot of origin/main 198bfcb (both tail-gas
modes) and exactly the two new keys are added; the extended verify_atom_balance fires on broken cases. Offline: counting fake store, no credentials."""
import copy
import gzip
import json
import math
import os

import pytest

from _fakes import FakeSupabase, patched_supabase
from python import balance_audit as ba
from python import cycle_clock
from python import ga001_gasifier_model as ga001
from python import gasifier_mass_balance as gmb
from python import plant_status as ps
from python import tab1_integration as t1

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "snapshot_origin_main_198bfcb.json.gz")
NEW_KEYS = {"GA-001-INPUT|unconverted_carbon_to_carbon_black", "GA-001|CarbonAccounting"}
ACC = ("GA-001", "CarbonAccounting")
N, NP = 5, 4          # the sweeps run the engine's default five-cycle state (and the cycle before it, for the lagged recycle)


def _const(v):
    def fn(get_input):
        return {"value": v, "status": ps.STATUS_ASSUMED, "inputs": [], "validation_basis": ps.VALIDATION_NA, "confidence_note": "test"}
    return fn


SWEEPS = {
    "default": {}, "heat_only": {("GA-001-INPUT", "tail_gas_mode"): _const("heat_only")},
    "ER 0.2125": {("GA-001-INPUT", "equivalence_ratio"): _const(0.2125)}, "ER 0.2875": {("GA-001-INPUT", "equivalence_ratio"): _const(0.2875)},
    "feed -30 %": {("FE-001-INPUT", "msw_delivery_rate_kg_h"): _const(41.67 * 0.7)}, "feed +30 %": {("FE-001-INPUT", "msw_delivery_rate_kg_h"): _const(41.67 * 1.3)},
    "conversion 0.85": {("GA-001-INPUT", "carbon_conversion_efficiency"): _const(0.85)}, "conversion 0.98": {("GA-001-INPUT", "carbon_conversion_efficiency"): _const(0.98)},
    "split 0.5": {("GA-001-INPUT", "unconverted_carbon_to_carbon_black"): _const(0.5)},
}


def _ser(snapshot):
    return {f"{k[0]}|{k[1]}": json.loads(json.dumps(v, sort_keys=True, default=str)) for k, v in snapshot.items()}


def _same(a, b, path=""):
    """Exact for everything but floats; floats within 1e-12 relative (another platform's libm cannot fail it)."""
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
def fake():
    return FakeSupabase()


@pytest.fixture(scope="module")
def runs(fake):
    cycle_clock.set_elapsed_hours(None)
    out = {}
    with patched_supabase(fake):
        for name, ov in SWEEPS.items():
            out[name] = (t1.build_live_snapshot(n_cycles=N, overrides=ov or None)[0], t1.build_live_snapshot(n_cycles=NP, overrides=ov or None)[0])
        out["default30"] = t1.build_live_snapshot(n_cycles=30)[0]               # converged (the recycle has settled)
    return out


@pytest.fixture(scope="module")
def main_snap():
    with gzip.open(FIXTURE, "rb") as fh:
        return json.loads(fh.read().decode("utf-8"))


# ------------------------------------------------------------------ carbon closes
@pytest.mark.parametrize("name", list(SWEEPS))
def test_carbon_closes_to_numerical_precision_in_every_sweep(runs, name):
    s, p = runs[name]
    a = ba.audit_snapshot(s, p)
    for cv in ("ga001", "loop", "plant"):
        row = a[cv]["rows"]["C"]
        assert abs(row["rel"]) < 1e-9, (name, cv, row["residual_kg_h"])
        assert row["verdict"] == ba.VERDICT_NUMERICAL
    assert abs(a["explain_carbon"]["difference_kg_h"]) < 1e-9 and abs(a["explain_carbon"]["measured_kg_h"]) < 1e-9
    assert abs(a["ga001_carbon"]["unassigned_C_kg_h"]) < 1e-9
    for cv in ("ga001", "loop"):
        for el in ("H", "O", "N"):
            assert abs(a[cv]["rows"][el]["rel"]) < 1e-12


def test_default_carbon_and_mass_close(runs):
    s, p = runs["default"]
    a = ba.audit_snapshot(s, p)
    assert a["ga001"]["rows"]["C"]["residual_kg_h"] == pytest.approx(0.0, abs=1e-12)        # was +0.1377 kg/h in the five-cycle state
    assert a["ga001"]["rows"]["mass"]["verdict"] == ba.VERDICT_NUMERICAL                    # the GA-001 total mass closes too
    assert "tar" in a["ga001"]["missing_terms"]                                             # closure of the modelled terms only


# ------------------------------------------------------------------ the derivation
@pytest.mark.parametrize("split", [1.0, 0.75, 0.5])
def test_carbon_black_is_the_unconverted_carbon_times_the_split(fake, split):
    with patched_supabase(fake):
        s = t1.build_live_snapshot(n_cycles=N, overrides={ga001.CARBON_BLACK_SPLIT_KEY: _const(split)})[0]
        p = t1.build_live_snapshot(n_cycles=NP, overrides={ga001.CARBON_BLACK_SPLIT_KEY: _const(split)})[0]
    v = s[ACC]["value"]
    d = ba.ga001_terms(s, p, derived_carbon_black=False)
    c_in = (d["feed_atoms"]["C"] + d["recycle_atoms"]["C"]) * ba.ATOMIC_MASS["C"] / 1000.0
    conv = s[("GA-001-INPUT", "carbon_conversion_efficiency")]["value"]
    unconv = (1.0 - conv) * c_in                                                            # independent re-derivation from the carbon in
    assert v["unconverted_carbon_kg_h"] == pytest.approx(unconv, rel=1e-12)
    assert v["carbon_black_kg_h"] == pytest.approx(unconv * split, rel=1e-12)
    assert v["remainder_kg_h"] == pytest.approx(unconv * (1.0 - split), abs=1e-12)
    assert v["carbon_black_split"] == split and v["carbon_black_split_status"] == ps.STATUS_ASSUMED and v["remainder_destination_status"] == ps.STATUS_MISSING
    assert v["gas_side_check"]["difference_to_unconverted_kg_h"] == pytest.approx(0.0, abs=1e-12)        # C in - C in the published gas = unconverted
    a = ba.audit_snapshot(s, p)
    assert abs(a["ga001"]["rows"]["C"]["rel"]) < 1e-9                                       # the remainder is counted as a labelled Missing-destination term
    if split < 1.0:
        assert "unconverted carbon not taken as carbon black (destination Missing)" in [t["name"] for t in a["ga001"]["terms"]]


@pytest.mark.parametrize("bad", [0.49, 1.01, -1, "x", None, True])
def test_a_split_outside_the_assumed_range_is_rejected(bad):
    with pytest.raises(ValueError, match="unconverted_carbon_to_carbon_black"):
        ga001.check_carbon_black_split(bad)
    with pytest.raises(ValueError):
        ga001.unconverted_carbon_fraction(1.2)


def test_the_cross_check_exists_and_feeds_nothing(runs, fake, monkeypatch):
    s = runs["default30"]
    x = s[ACC]["value"]["datasheet_cross_check"]
    assert x["feeds_nothing"] is True and x["ga008_capacity_kg_h"] == 3.0 and x["ga008_capacity_exceeded"] is False
    assert x["datasheet_rule_kg_h"] == pytest.approx(gmb.CARBON_BLACK_FRACTION * s[("GA-001-INPUT", "dry_feed_rate_kg_h")]["value"])
    assert x["ratio_derived_over_datasheet"] == pytest.approx(s[ACC]["value"]["carbon_black_kg_h"] / x["datasheet_rule_kg_h"])
    assert "GA-008 capacity 3.0 kg/h not exceeded" in x["status_line"]
    # change the 5 % constant: only the cross-check fields move, nothing else in the whole snapshot
    monkeypatch.setattr(gmb, "CARBON_BLACK_FRACTION", 0.5)
    with patched_supabase(fake):
        other = t1.build_live_snapshot(n_cycles=N)[0]
    s = runs["default"][0]
    a, b = _ser(s), _ser(other)
    for k in a:
        if k == "GA-001|CarbonAccounting":
            va, vb = copy.deepcopy(a[k]), copy.deepcopy(b[k])
            for d in (va, vb):
                d["value"].pop("datasheet_cross_check")
                d["confidence_note"] = ""
            assert _same(va, vb) is True
        else:
            assert _same(a[k], b[k]) is True, k
    assert b["GA-001|CarbonAccounting"]["value"]["datasheet_cross_check"]["datasheet_rule_kg_h"] != x["datasheet_rule_kg_h"]


def test_the_split_changes_only_the_carbon_accounting_and_its_input(runs):
    base, alt = _ser(runs["default"][0]), _ser(runs["split 0.5"][0])
    differing = {k for k in base if _same(base[k], alt[k]) is not True}
    assert differing == NEW_KEYS, differing                                                 # no gas-side entry moves with the split


# ------------------------------------------------------------------ nothing gas-side changed, nothing lost
@pytest.mark.parametrize("label,key", [("default", "default|5"), ("default30", "default|30"), ("heat_only", "heat_only|5")])
def test_every_entry_of_main_is_unchanged_in_both_tail_gas_modes(runs, main_snap, label, key):
    new = _ser(runs[label][0] if isinstance(runs[label], tuple) else runs[label])
    old = main_snap[key]
    assert len(old) == 118
    assert set(old) <= set(new), sorted(set(old) - set(new))
    assert set(new) - set(old) == NEW_KEYS
    # in heat_only the switch's own entry is the test's override (its model name and note are the override's), everything else must match
    skip = {"GA-001-INPUT|tail_gas_mode"} if label == "heat_only" else set()
    bad = {k: _same(old[k], new[k]) for k in old if k not in skip}
    assert {k: v for k, v in bad.items() if v is not True} == {}
    if label == "heat_only":
        assert new["GA-001-INPUT|tail_gas_mode"]["value"] == "heat_only"


def test_no_persisted_key_is_lost_and_the_shrink_guard_is_not_in_play(runs, main_snap):
    new = {f"{k[0]}|{k[1]}" for k in runs["default30"]}
    old = set(main_snap["default|30"])
    assert old - new == set() and len(old) / len(new) > 0.9
    json.dumps(runs["default30"][ACC]["value"])                                             # plain JSON types: it can be persisted


# ------------------------------------------------------------------ the extended guard
def _case(er=0.25):
    x, y, z, n_c = ga001.elemental_atomic_ratios(0.5, 0.06, 0.43, 0.01, 0.1)
    steam = (0.4 / n_c) * 1000.0 / ga001.M_H2O
    conv = 0.9
    product = ga001.solve_product_gas(x, y, z, er, steam, conv, 0.05, 950.0 + 273.15)
    return x, y, z, er, steam, product, conv


def test_the_guard_passes_on_a_real_solution_and_checks_c_h_o_and_n():
    x, y, z, er, steam, product, conv = _case()
    ok, detail = ga001.verify_atom_balance(x, y, z, er, steam, product, conv)
    assert ok and set(detail) == {"C_gas_target_vs_actual", "C_gas_plus_unconverted_vs_fed", "H_target_vs_actual", "O_target_vs_actual", "N_target_vs_actual"}
    for name in ("C_gas_target_vs_actual", "C_gas_plus_unconverted_vs_fed", "H_target_vs_actual", "O_target_vs_actual", "N_target_vs_actual"):
        t, a = detail[name]
        assert abs(t - a) < 1e-12, name


def test_the_guard_fires_when_a_carbon_bearing_product_component_is_removed():
    x, y, z, er, steam, product, conv = _case()
    broken = dict(product, CH4=0.0)
    ok, detail = ga001.verify_atom_balance(x, y, z, er, steam, broken, conv)
    assert not ok and abs(detail["C_gas_target_vs_actual"][0] - detail["C_gas_target_vs_actual"][1]) > 1e-3
    assert abs(detail["H_target_vs_actual"][0] - detail["H_target_vs_actual"][1]) > 1e-3             # CH4 carries 4 H: H sees it too
    ok2, detail2 = ga001.verify_atom_balance(x, y, z, er, steam, dict(product, CO=0.0), conv)
    assert not ok2


def test_the_guard_fires_when_the_unconverted_carbon_is_off_by_one_percent():
    x, y, z, er, steam, product, conv = _case()
    wrong_conv = 1.0 - (1.0 - conv) * 1.01                    # the unconverted carbon changed by 1 %
    ok, detail = ga001.verify_atom_balance(x, y, z, er, steam, product, wrong_conv)
    assert not ok
    h, o, n = (detail[k] for k in ("H_target_vs_actual", "O_target_vs_actual", "N_target_vs_actual"))
    assert all(abs(t - a) < 1e-12 for t, a in (h, o, n)), "H, O and N are unaffected: the failure is the carbon check alone"
    assert abs(detail["C_gas_target_vs_actual"][0] - detail["C_gas_target_vs_actual"][1]) > 1e-4


def test_the_guard_fires_when_the_n2_term_is_dropped():
    x, y, z, er, steam, product, conv = _case()
    ok, detail = ga001.verify_atom_balance(x, y, z, er, steam, dict(product, N2=0.0), conv)
    assert not ok
    assert all(abs(t - a) < 1e-12 for t, a in (detail["C_gas_target_vs_actual"], detail["H_target_vs_actual"], detail["O_target_vs_actual"])), "only the nitrogen check fails"
    assert abs(detail["N_target_vs_actual"][0] - detail["N_target_vs_actual"][1]) > 0.1
    ok2, _ = ga001.verify_atom_balance(x, y, z, er, steam, dict(product, N2=product["N2"] * 1.0001), conv)
    assert not ok2                                              # a 0.01 % nitrogen error is caught too


@pytest.mark.parametrize("name", list(SWEEPS))
def test_the_guard_passes_on_every_state_the_app_can_reach(runs, name):
    s, p = runs[name]
    ok, detail = ba.atom_balance_like_verify(s, p)
    assert ok, detail
    ok1, detail1 = ba.atom_balance_like_verify(t1_cycle_one(), None)
    assert ok1, detail1


_CYCLE_ONE = {}


def t1_cycle_one():
    if "s" not in _CYCLE_ONE:
        with patched_supabase(FakeSupabase()):
            _CYCLE_ONE["s"] = t1.build_live_snapshot(n_cycles=1)[0]
    return _CYCLE_ONE["s"]


# ------------------------------------------------------------------ no database, no network
def test_zero_database_calls(runs, fake):
    assert fake.calls == [], fake.calls
    assert os.environ.get("HYGAS_ALLOW_DB_WRITES") == "0"
