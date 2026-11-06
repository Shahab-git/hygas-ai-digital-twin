"""Design-basis ledger (task A3): coverage, status rules, derived consumers, bit-identity of the engine, export freshness, offline.

  * every numeric constant that can influence a published key (python/ledger_coverage.py scan of the 17 modules) is a ledger row or a listed exception with a class and a reason;
  * Confirmed needs a DOK-ING source line; an ASSUMED / UNKNOWN origin can never be Confirmed; a Calculated row names its formula (python/ledger_coverage.status_problems);
  * consumers come from an instrumented engine run (ledger_consumers), not from hand-typing;
  * the engine is unchanged: every persisted entry of both tail_gas_modes equals tests/fixtures/snapshot_origin_main_701de71.json.gz (made from the unmodified origin/main),
    exact for structure / strings / integers, 1e-12 relative for floats; the only text differences are the six reworded phrases of task item D2 (tests/_d2_wording.py), and the
    new text is asserted present; the persisted key count (121) and the runtime's 90 % shrink guard are unaffected;
  * docs/design_basis_ledger.md / .csv equal a fresh generation; no database or network call is made.
Offline: counting fake store, no credentials."""
import gzip
import importlib.util
import json
import math
import os
import re
import shutil
import socket
import subprocess
import sys

import pytest

import _d2_wording
from _fakes import FakeSupabase, patched_supabase
from python import equipment_datasheet as ed
from python import ledger_consumers as lcons
from python import ledger_anchors as la
from python import ledger_coverage as lc
from python import ledger_notes as lnotes
from python import ledger_questions as lq
from python import ledger_rows as lr
from python import parameter_table as pt
from python import plant_status as ps
from python import simulation_engine as se
from python import shared_plant_state as sps
from python import tab1_integration as t1

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "snapshot_origin_main_701de71.json.gz")
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


@pytest.fixture(scope="module")
def fake():
    return FakeSupabase()


@pytest.fixture(scope="module")
def built(fake):
    """(ledger, scan items, exceptions, instrumented readers): the engine run that records the reads uses the counting fake store."""
    with patched_supabase(fake):
        readers = lcons.engine_input_readers(lambda: t1.build_live_snapshot(3))
    return pt.build_ledger(readers=readers), lc.scan(), lc.load_exceptions(), readers


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


# ------------------------------------------------------------------ the table itself is unchanged and the ledger extends it

def test_the_ledger_extends_the_table_without_changing_it():
    assert pt.LEDGER_COLUMNS[:len(pt.COLUMNS)] == pt.COLUMNS and pt.LEDGER_COLUMNS[len(pt.COLUMNS):] == ("ledger_id", "consumers", "upgrade_question", "origin", "source_line", "status_via", "anchor")
    table, ledger = pt.build_table(), pt.build_ledger()
    assert len(table) == 27, "build_table() is unchanged: its 26 rows + the gasifying_agent switch row (A1, deliberate edit)"
    by = {(r["tag"], r["source"]): r for r in ledger}
    for r in table:
        assert all(by[(r["tag"], r["source"])][c] == r[c] for c in pt.COLUMNS), r["tag"]       # A3c: strict again, every column of every table row (the ash_fraction exception of A3b is gone)
    ash = by[("GA-001.ash_fraction", "module constant gasifier_mass_balance.ASH_FRACTION (reused by ga001 as ASH_FRACTION)")]
    assert ash["status"] == "Assumed" and ash["status_via"] == "own" and ash["origin"] == "NOT STATED" and not ash["source_line"]
    assert next(x for x in table if x["tag"] == "GA-001.ash_fraction")["status"] == "Assumed", "ledger and table agree: one source of truth"
    assert len(ledger) == 27 + len(lr.build_rows()) == len(by)          # A1 (deliberate edit): 27 = 26 + the gasifying_agent switch row
    assert all(r["ledger_id"] == "LEDGER." + r["tag"] for r in ledger)
    assert all(set(r) >= set(pt.LEDGER_COLUMNS) for r in ledger)


def test_a_new_row_reads_the_owning_constant_and_does_not_copy_it():
    by = {r["tag"]: r for r in pt.build_ledger() if r["overridable_via"] == "code only"}
    from python import hb_remaining_chain as hbrem, gc_gas_cleaning_chain as gc, fe_feed_handling as fe
    assert by["HB-010.h2_recovery"]["value"] == hbrem.HB010_CONFIRMED_RECOVERY
    assert by["FE-003.nominal_kg_h"]["value"] == fe.FE003_NOMINAL_KG_H
    assert by["GC-005.blowdown_to_circulation_ratio"]["value"] == gc.QUENCH_BLOWDOWN_TO_CIRCULATION_RATIO
    assert by["GC-003.efficiency"]["value"] == 0.95 and by["GC-003.efficiency"]["file_line"].startswith("python/gc_gas_cleaning_chain.py:")
    assert by["HB-010.permeate_purity_range"]["range_low"] == hbrem.HB010_CONFIRMED_PURITY_RANGE[0]


def test_a_changed_hard_coded_literal_fails_loudly_in_the_ledger_not_silently():
    src = open(os.path.join(ROOT, "python", "gc_gas_cleaning_chain.py"), encoding="utf-8").read()
    assert "efficiency = 0.95" in src
    with pytest.raises(LookupError):
        lr.build_rows(sources={"python/gc_gas_cleaning_chain.py": src.replace("efficiency = 0.95", "efficiency = 0.96")})


# ------------------------------------------------------------------ (C) coverage

def test_every_parameter_is_a_ledger_row_or_a_listed_exception(built):
    ledger, items, exceptions, _ = built
    covered = lr.covered_keys()
    assert lc.uncovered(items, covered, exceptions) == []
    assert lc.stale(items, covered, exceptions) == {"covers_not_found": [], "exceptions_not_found": [], "both_row_and_exception": []}
    assert lc.exception_problems(exceptions) == []
    assert len(items) == 365 and len(exceptions) == 189 and len(items) - len(exceptions) == 176     # A3b 2.3: 7 HHV coefficients moved from one row to exceptions; A1 (deliberate edit): +4 agent constants, each a ledger row (184 -> 191); 2.4: two persisted-verdict thresholds became rows (191 -> 189, PARAMETERs 169 -> 171)


def test_the_scan_covers_the_seventeen_modules_and_finds_the_known_hard_coded_ones(built):
    items = built[1]
    assert {i["file"] for i in items} == {lc.rel_path(m) for m in lc.SCAN_MODULES} and len(lc.SCAN_MODULES) == 17
    keys = {i["key"] for i in items}
    assert lc.lit_key("python/gc_gas_cleaning_chain.py", "gc003_dust", 0.95) in keys
    assert lc.const_key("python/psa.py", "K1") in keys and lc.const_key("python/plant_heat_integration.py", "ASSUMED") in keys


def test_an_unregistered_constant_added_to_a_module_copy_is_found():
    src = open(os.path.join(ROOT, "python", "psa.py"), encoding="utf-8").read()
    items = lc.scan(sources={"python/psa.py": src + "\nNEW_UNREGISTERED_PARAMETER = 0.37\n"})
    left = lc.uncovered(items, lr.covered_keys(), lc.load_exceptions())
    assert [i["key"] for i in left] == [lc.const_key("python/psa.py", "NEW_UNREGISTERED_PARAMETER")]


def test_an_unregistered_hard_coded_number_added_to_a_function_is_found():
    src = open(os.path.join(ROOT, "python", "psa.py"), encoding="utf-8").read()
    items = lc.scan(sources={"python/psa.py": src + "\n\ndef f(x):\n    return x * 3.14159\n"})
    left = lc.uncovered(items, lr.covered_keys(), lc.load_exceptions())
    assert [i["key"] for i in left] == [lc.lit_key("python/psa.py", "f", 3.14159)]


def test_an_exception_needs_a_class_and_a_reason():
    bad = [{"key": "k1", "class": "PHYSICAL CONSTANT", "reason": ""}, {"key": "k2", "class": "PHYSICAL CONSTANT", "reason": "   "}, {"key": "k3", "class": "TUNING", "reason": "x"}]
    assert {k for k, _ in lc.exception_problems(bad)} == {"k1", "k2", "k3"}
    assert lc.exception_problems([{"key": "ok", "class": "NUMERICAL", "reason": "a tolerance"}]) == []


# ------------------------------------------------------------------ (A3b 2.3) published correlation coefficients

CORRELATION_KEYS = {
    "lit|python/ga001_gasifier_model.py|_wgs_keq|4577.8", "lit|python/ga001_gasifier_model.py|_wgs_keq|4.33", "lit|python/kinetics.py|_keq|4577.8", "lit|python/kinetics.py|_keq|4.33",
    "lit|python/balance_audit.py|feedstock_lhv_estimates|0.3491", "lit|python/balance_audit.py|feedstock_lhv_estimates|1.1783", "lit|python/balance_audit.py|feedstock_lhv_estimates|0.1034",
    "lit|python/balance_audit.py|feedstock_lhv_estimates|0.0151", "lit|python/balance_audit.py|feedstock_lhv_estimates|0.0211", "lit|python/balance_audit.py|feedstock_lhv_estimates|0.3383",
    "lit|python/balance_audit.py|feedstock_lhv_estimates|1.443"}


def test_the_wgs_and_hhv_coefficients_are_published_correlation_coefficients_and_nothing_else_is(built):
    exceptions = built[2]
    mine = {e["key"] for e in exceptions if e["class"] == lc.CLASS_CORRELATION}
    assert mine == CORRELATION_KEYS
    assert lc.CLASS_CORRELATION == "PUBLISHED CORRELATION COEFFICIENT" and lc.CLASS_CORRELATION in lc.EXCEPTION_CLASSES
    assert lc.exception_problems([e for e in exceptions if e["class"] == lc.CLASS_CORRELATION]) == []
    ledger_covers = {k for r in lr.build_rows() for k in r["covers"]}
    assert not (ledger_covers & CORRELATION_KEYS), "a coefficient is never both a ledger row and a correlation exception"
    assert not any("PLANT.hhv" in r["tag"] for r in built[0])


def test_every_correlation_reason_names_the_correlation_and_its_source_as_the_code_does(built):
    by = {e["key"]: e["reason"] for e in built[2] if e["class"] == lc.CLASS_CORRELATION}
    assert all("Moe (1962)" in by[k] for k in CORRELATION_KEYS if "4577.8" in k or k.endswith("|4.33"))
    assert all("Channiwala & Parikh (2002), Fuel 81" in by[k] for k in CORRELATION_KEYS if k.rsplit("|", 1)[1] in ("0.3491", "1.1783", "0.1034", "0.0151", "0.0211"))
    dulong = [by[k] for k in CORRELATION_KEYS if k.rsplit("|", 1)[1] in ("0.3383", "1.443")]
    assert len(dulong) == 2 and all("Dulong" in r and lc.NO_SOURCE in r for r in dulong), "the repo names Dulong but cites no publication: the entry says so"
    for r in by.values():
        assert "physical constant" not in r.lower() and "parameter" not in r.lower()
    # the names really are in the code (a rewritten docstring would make the reason stale)
    ba = open(os.path.join(ROOT, "python", "balance_audit.py"), encoding="utf-8").read()
    assert "Channiwala & Parikh (2002), Fuel 81" in ba and "Dulong:" in ba
    assert "Moe, J.M. (1962)" in open(os.path.join(ROOT, "python", "ga001_gasifier_model.py"), encoding="utf-8").read()
    assert "Moe (1962)" in open(os.path.join(ROOT, "python", "kinetics.py"), encoding="utf-8").read()


def test_a_correlation_entry_without_a_correlation_name_or_a_source_is_refused():
    base = {"key": "k", "class": lc.CLASS_CORRELATION}
    assert lc.exception_problems([dict(base, reason="a coefficient")])                         # names neither
    assert lc.exception_problems([dict(base, reason="coefficient of a correlation")])          # names no source
    assert lc.exception_problems([dict(base, reason="a coefficient of Moe (1962)")])           # does not say it is a correlation
    assert lc.exception_problems([dict(base, reason="coefficient of the Moe (1962) correlation")]) == []
    assert lc.exception_problems([dict(base, reason="coefficient of a published correlation; source NOT STATED in repo")]) == []


# ------------------------------------------------------------------ (A3b 2.4) verdict thresholds that decide a persisted value are parameters

def test_the_two_verdict_thresholds_that_decide_a_persisted_verdict_are_assumed_rows(built, runs):
    by = {r["tag"]: r for r in built[0]}
    for tag, val in (("HB-016.consistency_verdict_ratio_lower_bound", 0.2), ("GC-014.consistency_tolerance_fraction", 0.5)):
        assert by[tag]["value"] == val and by[tag]["status"] == "Assumed", tag
    snap = _ser(runs["default"])
    assert snap["GC-014|Pressure"]["value"]["consistency_check"]["verdict"] == "PARTIAL" and "(PARTIAL)" in snap["GC-014|Pressure"]["confidence_note"]
    assert snap["HB-016|KineticsBaselineEstimate"]["value"]["consistency_check"]["verdict"] == "PASS" and "(PASS)" in snap["HB-016|KineticsBaselineEstimate"]["confidence_note"]
    # the thresholds are not in the exception list any more (they would be both a row and an exception)
    keys = {e["key"] for e in built[2]}
    assert "lit|python/gc_gas_cleaning_chain.py|gc014_blower_pressure|0.5" not in keys and "lit|python/hb_remaining_chain.py|hb016_kinetics_baseline|0.2" not in keys


# ------------------------------------------------------------------ (A3b 2.8) status_via: a borrowed status needs the same quantity in the same basis

_NUM = __import__("re").compile(r"^[<~]?\s*(-?\d+(?:\.\d+)?)\s*$")
_RANGE = __import__("re").compile(r"^(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)$")


def _registry_numbers(text):
    """The number(s) a registry value text states: '85' -> [85.0], '<50' -> [50.0], '~1' -> [1.0], '95-98' -> [95.0, 98.0]; None when the text is not a plain number or range."""
    s = str(text).strip()
    m = _NUM.match(s)
    if m:
        return [float(m.group(1))]
    m = _RANGE.match(s)
    return [float(m.group(1)), float(m.group(2))] if m else None


def test_every_row_has_status_via_own_or_a_registry_counterpart(built):
    for r in built[0]:
        via = r["status_via"]
        assert via == "own" or via.startswith("registry counterpart: ") and "/" in via, (r["ledger_id"], via)
    assert pt.LEDGER_COLUMNS[-2:] == ("status_via", "anchor")
    assert sum(1 for r in built[0] if r["status_via"] != "own") == 63


def test_every_row_with_a_registry_counterpart_is_borrowed_or_explicitly_not_borrowed():
    reg_rows = {r["tag"] for r in lr.build_rows() if r["reg"]}
    assert reg_rows == (set(lr.BORROW) | set(lr.NOT_BORROWED)) - {"GA-001.ash_fraction"}, "a new row with a registry counterpart must be decided: BORROW (same quantity, same basis) or NOT_BORROWED"
    assert not (set(lr.BORROW) & set(lr.NOT_BORROWED))
    assert all(len(v) == 4 and v[3] for v in lr.BORROW.values()), "every borrowed row states its unit conversion or 'same quantity, same unit, same basis'"
    assert all(len(v) > 30 for v in lr.NOT_BORROWED.values()), "every refusal states why"


def test_a_borrowed_status_is_never_higher_than_the_counterparts_and_the_value_matches_it(built):
    from python import registry_status as rs
    by = {r["tag"] + "|" + r["source"]: r for r in built[0]}
    checked = 0
    for n in lr.build_rows():
        if not n["reg"] or n["tag"] in lr.NOT_BORROWED:
            continue
        row = next(r for r in built[0] if r["tag"] == n["tag"])
        res, p = lr._registry_status(n["reg"])
        assert row["status_via"] == "registry counterpart: %s/%s" % n["reg"], n["tag"]
        assert rs.rank_of(row["status"]) >= rs.rank_of(res["status"]), (n["tag"], "borrowed status is higher than the counterpart's resolved status")
        assert row["status"] == res["status"], n["tag"]
        factor, offset, tol, statement = lr.BORROW[n["tag"]]
        nums = _registry_numbers(p["value"])
        code = list(n["value"]) if isinstance(n["value"], (tuple, list)) else [n["value"]]
        if nums is None:
            raise AssertionError(f"{n['tag']}: registry text {p['value']!r} is not a number; a row whose counterpart cannot be compared belongs in NOT_BORROWED")
        assert len(nums) == len(code), n["tag"]
        for c, x in zip(code, nums):
            expected = factor * x + offset
            assert abs(c - expected) <= tol * max(abs(expected), 1e-12), (n["tag"], c, expected, statement)
        checked += 1
    assert checked == 63


def test_a_borrowed_row_whose_value_drifted_from_its_counterpart_is_caught():
    n = next(r for r in lr.build_rows() if r["tag"] == "HB-012.discharge_bar_a")
    res, p = lr._registry_status(n["reg"])
    factor, offset, tol, _ = lr.BORROW["HB-012.discharge_bar_a"]
    assert abs(n["value"] - (factor * _registry_numbers(p["value"])[0] + offset)) <= tol * n["value"]          # 701 bar(a) = 700 bar(g) + 1 bar
    assert abs(702.0 - (factor * _registry_numbers(p["value"])[0] + offset)) > tol * 702.0                    # 702 would not be


def test_the_refused_rows_are_assumed_with_their_reason_in_the_note(built):
    by = {r["tag"]: r for r in built[0]}
    for tag, reason in lr.NOT_BORROWED.items():
        r = by[tag]
        assert r["status"] == "Assumed" and r["status_via"] == "own" and r["origin"] == "NOT STATED" and not r["source_line"], tag
        assert reason in r["note"] or tag == "GA-001.ash_fraction", tag                            # the ash row is a table row: its own note carries the reason (checked in test_ash_fraction_is_assumed_in_the_table_and_the_ledger)
    assert by["FE-003.nominal_kg_h"]["status"] == "Confirmed" and by["FE-003.nominal_kg_h"]["status_via"] == "registry counterpart: FE-003/Nominal feed rate"
    hb012 = by["HB-012.discharge_bar_a"]                                                        # P0-CLOSE C1: the former `A and B or C` was satisfied by C alone; three separate assertions
    assert hb012["status"] == "Confirmed"
    assert "bar(a) = bar(g) + 1 bar" in hb012["note"]                                           # the conversion is stated
    assert "701 bar" not in hb012["note"] and not re.search(r"DOK-ING[^.]*701", hb012["note"])   # 701 is never given as DOK-ING's figure (DOK-ING stated 350/700 bar)
    assert by["FE-001.default_delivery_rate_kg_h"]["status"] == "Assumed"


# ------------------------------------------------------------------ (A3c 2) GA-001.ash_fraction: one source of truth

def test_ash_fraction_is_assumed_in_the_table_and_the_ledger_and_the_evidence_is_in_the_repo(built):
    from python import equipment_registry as er
    row = next(p for it in er.load_registry() if it["id"] == "GA-005" for p in it["parameters"] if p["parameter"] == "Ash discharge rate (design)")
    assert (row["value"], row["unit"]) == ("10", "% of feed") and "already used in the mass/energy balance" in row["remarks"], "the registry row is a discharge rate, basis not in the value, set to match the model"
    ash = next(r for r in built[0] if r["tag"] == "GA-001.ash_fraction")
    table = next(r for r in pt.build_table() if r["tag"] == "GA-001.ash_fraction")
    assert ash["status"] == table["status"] == "Assumed" and ash["note"] == table["note"] and ash["status_via"] == "own"
    lines = open(os.path.join(ROOT, "data", "dokink_rfi_answers.md"), encoding="utf-8").read().split(chr(10))
    assert "Ash 5" in lines[14] and "15%" in lines[14], "data/dokink_rfi_answers.md line 15 states the ash band the note quotes"
    assert "data/dokink_rfi_answers.md, line 15" in ash["note"] and "does NOT make the 10 % Confirmed" in ash["note"]
    assert (ash["range_low"], ash["range_high"]) == (0.05, 0.15) and ash["value"] == 0.1


# ------------------------------------------------------------------ (A3c 3) the refused borrowings, FE-001 and GA-002

def test_every_refused_borrowing_has_a_kind_and_is_listed_with_both_values_in_the_doc():
    assert set(lr.REFUSAL_KIND) == set(lr.NOT_BORROWED) and len(lr.NOT_BORROWED) == 15          # A1.3 (deliberate edit): 14 + GA-001.agent_check_expected_n2_vol_pct (the registry row gives no wet or dry basis)
    section = COMMITTED["design_basis_ledger.md"].split("## Refused borrowings")[1].split("## Known undeclared reads")[0]
    table = [l for l in section.split(chr(10)) if l.startswith("| ") and not l.startswith("| ledger row") and not l.startswith("|---")]
    assert len(table) == 15 and {l.split(" | ")[0][2:] for l in table} == set(lr.NOT_BORROWED)
    for l in table:
        cells = l.split(" | ")
        assert len(cells) == 7 and all(c.strip() for c in cells), l


def test_fe001_delivery_is_not_the_feed_rate_of_fe003_and_stays_assumed(built):
    from python import equipment_registry as er, fe_feed_handling as fe
    row = next(p for it in er.load_registry() if it["id"] == "FE-003" for p in it["parameters"] if p["parameter"] == "Nominal feed rate")
    assert (row["value"], row["unit"]) == ("0.042", "t/h")
    assert abs(float(row["value"]) * 1000.0 - fe.FE001_DEFAULT_DELIVERY_RATE_KG_H) > 0.3, "not a pure unit conversion: 42 against 41.67"
    assert abs(1000.0 / 24.0 - fe.FE001_DEFAULT_DELIVERY_RATE_KG_H) < 0.01, "1,000 kg/day / 24 h"
    src = open(os.path.join(ROOT, "python", "fe_feed_handling.py"), encoding="utf-8").read()
    assert "FE-001-INPUT" in src and "msw_delivery_rate_kg_h" in src and "AS-RECEIVED" in src
    assert "(delivery_rate_kg_h - FE003_NOMINAL_KG_H)" in src, "the hopper level changes by delivery minus feed: two different rates"
    line11 = open(os.path.join(ROOT, "data", "dokink_rfi_answers.md"), encoding="utf-8").read().split(chr(10))[10]
    assert "1,000 kg/day" in line11 and "deliver" not in line11.lower() and "as-received" not in line11.lower() and "dry" not in line11.lower()
    r = next(r for r in built[0] if r["tag"] == "FE-001.default_delivery_rate_kg_h")
    assert r["status"] == "Assumed" and r["status_via"] == "own"
    fed = next(r for r in built[0] if r["tag"] == "FE-003.nominal_kg_h")
    assert fed["status"] == "Confirmed" and fed["status_via"] == "registry counterpart: FE-003/Nominal feed rate", "the feed rate itself still borrows"


def test_ga002_typical_pressure_borrows_from_the_typical_row_and_never_from_a_design_row(built):
    from python import equipment_registry as er
    rows = {(it["id"], p["parameter"]): p for it in er.load_registry() if it["id"] in ("GA-001", "GA-002") for p in it["parameters"]}
    assert (rows[("GA-001", "Design pressure")]["value"], rows[("GA-001", "Design pressure")]["unit"]) == ("500", "mbar(g)")
    assert (rows[("GA-001", "Operating pressure (typical)")]["value"], rows[("GA-001", "Operating pressure (typical)")]["unit"]) == ("100", "mbar(g)")
    assert (rows[("GA-002", "Design pressure")]["value"], rows[("GA-002", "Operating pressure range")]["value"]) == ("500", "50-150")
    r = next(r for r in built[0] if r["tag"] == "GA-002.typical_pressure_mbar_g")
    assert r["value"] == 100.0 and r["status_via"] == "registry counterpart: GA-001/Operating pressure (typical)"
    assert lr.quantity_class(r["tag"] + " " + r["source"]) == lr.quantity_class("Operating pressure (typical)") == "operating" and lr.quantity_class("Design pressure") == "design"


def test_no_borrowing_crosses_a_design_row_and_a_typical_or_operating_row():
    assert lr.crosses_design_and_operating("GA-002.typical_pressure_mbar_g module constant gc_gas_cleaning_chain.GA002_TYPICAL_PRESSURE_MBAR_G", "Design pressure")
    assert lr.crosses_design_and_operating("GC-014.design_suction_mbar_g", "Operating pressure (typical)")
    assert not lr.crosses_design_and_operating("GC-014.design_suction_mbar_g", "Design suction pressure")
    assert not lr.crosses_design_and_operating("GA-002.typical_pressure_mbar_g", "Operating pressure (typical)")
    crossing = [n["tag"] for n in lr.build_rows() if n["reg"] and n["tag"] in lr.BORROW and lr.crosses_design_and_operating(n["tag"] + " " + n["source"], n["reg"][1])]
    assert crossing == [], crossing


# ------------------------------------------------------------------ (A3c 4) the widened isolation guards: the ledger modules are not part of the engine, the runtime or the app
# Three existing guards were widened for named ledger files (tests/test_data_layer.py: the export script and this file may import parameter_table; tests/test_plant_heat_integration.py and
# tests/test_reference_feeds.py: python/ledger_coverage.py and python/ledger_rows.py may name the modules plant_heat_integration / reference_feeds), plus scripts/make_provenance_worksheet.py
# (NOT_ENGINE lists the ledger module names). What those guards protect is that nothing in the engine, the runtime or the app reads these modules. These tests assert it for the ledger modules.

LEDGER_MODULES = ("ledger_rows", "ledger_coverage", "ledger_consumers", "ledger_questions", "ledger_notes", "ledger_anchors")
LEDGER_OWN = {"python/" + m + ".py" for m in LEDGER_MODULES} | {"python/parameter_table.py"}          # parameter_table.build_ledger imports them lazily, inside the function
LEDGER_USERS = {"scripts/export_design_basis_ledger.py"}                                           # the generator of the committed files
NAMES_ONLY = {"scripts/make_provenance_worksheet.py"}                                              # NOT_ENGINE lists the names as strings; it must not import them


def _repo_sources(override=None):
    out = {}
    for folder in ("python", "scripts"):
        for name in sorted(os.listdir(os.path.join(ROOT, folder))):
            if name.endswith(".py"):
                out[folder + "/" + name] = open(os.path.join(ROOT, folder, name), encoding="utf-8").read()
    out["app.py"] = open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()
    out.update(override or {})
    return out


def _imported_names(src):
    import ast
    names = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
    return names


def _ledger_offenders(sources):
    """Files outside the ledger that import a ledger module, or name one in any way (a string, importlib, a comment): the engine, the runtime, run_continuous_cycle.py, app.py and every other script."""
    bad = []
    for rel, src in sources.items():
        if rel in LEDGER_OWN or rel in LEDGER_USERS:
            continue
        imports = {n.split(".")[-1] for n in _imported_names(src)}
        if imports & set(LEDGER_MODULES):
            bad.append((rel, "imports", sorted(imports & set(LEDGER_MODULES))))
        elif rel not in NAMES_ONLY and re.search(r"\bledger_(?:%s)\b" % "|".join(m[7:] for m in LEDGER_MODULES), src):
            bad.append((rel, "names", None))
    return bad


def test_no_engine_runtime_script_or_app_file_imports_or_names_a_ledger_module():
    sources = _repo_sources()
    assert "app.py" in sources and "scripts/run_continuous_cycle.py" in sources and "python/tab1_integration.py" in sources and "python/simulation_engine.py" in sources
    assert len([r for r in sources if r.startswith("python/")]) > 50
    assert _ledger_offenders(sources) == []


def test_a_ledger_module_imported_or_named_by_the_engine_the_runtime_or_the_app_would_be_caught():
    s = _repo_sources()
    for rel, add in (("python/tab1_integration.py", chr(10) + "from . import ledger_rows" + chr(10)),
                     ("python/simulation_engine.py", chr(10) + "import python.ledger_coverage" + chr(10)),
                     ("scripts/run_continuous_cycle.py", chr(10) + "m = importlib.import_module('python.ledger_anchors')" + chr(10)),
                     ("app.py", chr(10) + "from python.ledger_notes import render_refused" + chr(10)),
                     ("python/hb_remaining_chain.py", chr(10) + "# reads ledger_questions" + chr(10))):
        assert _ledger_offenders(_repo_sources({rel: s[rel] + add})), rel
    assert _ledger_offenders(_repo_sources({"scripts/make_provenance_worksheet.py": s["scripts/make_provenance_worksheet.py"] + chr(10) + "from python import ledger_rows" + chr(10)}))


def test_the_widened_data_layer_guard_still_keeps_parameter_table_out_of_the_engine_the_runtime_and_the_app():
    users = {rel for rel, src in _repo_sources().items() if any(n.split(".")[-1] == "parameter_table" for n in _imported_names(src))}
    # the data-layer task's own files (measurement_replay, run_residual_report) plus the one file the ledger added to the allow-list
    assert users == {"python/measurement_replay.py", "scripts/run_residual_report.py", "scripts/export_design_basis_ledger.py"}, users
    assert "scripts/export_design_basis_ledger.py" not in {u for u in _repo_sources() if u != "scripts/export_design_basis_ledger.py" and "export_design_basis_ledger" in _repo_sources()[u]}, "nothing imports the export script"


def test_the_two_ledger_modules_allowed_to_name_plant_heat_integration_and_reference_feeds_do_not_read_their_outputs():
    for rel in ("python/ledger_coverage.py", "python/ledger_rows.py"):
        src = open(os.path.join(ROOT, rel), encoding="utf-8").read()
        assert "HeatIntegration" not in src and "get_input" not in src and "build_live_snapshot" not in src, rel + ": it must not read the heat-integration key or any engine output"
        assert not re.search(r"from\s+(?:python|\.)\s+import[^" + chr(10) + r"]*\b(?:plant_heat_integration|reference_feeds)\b", src), rel + ": no static import of the two modules (constants are read with importlib/getattr or the ast)"
    # and nobody else in python/ or the repo root names them besides their own modules and the ledger (the original guards, restated with the ledger names listed)
    named_ph = sorted(rel for rel, src in _repo_sources().items() if re.search(r"plant_heat_integration|HeatIntegration", src) and not rel.startswith("scripts/"))
    assert named_ph == ["python/ga001_gasifier_model.py", "python/ledger_coverage.py", "python/ledger_rows.py", "python/plant_heat_integration.py"], named_ph
    named_rf = sorted(rel for rel, src in _repo_sources().items() if "reference_feeds" in src and not rel.startswith("scripts/"))
    assert named_rf == ["python/ledger_coverage.py", "python/ledger_rows.py"], named_rf


# ------------------------------------------------------------------ (A3b 3) upgrade_question is a list of references to questions that exist

def test_rfi2_is_in_the_repo_unchanged_with_its_24_questions():
    raw = open(os.path.join(ROOT, "docs", "rfi2_dokink.md"), "rb").read().replace(b"\r\n", b"\n")
    import hashlib
    assert hashlib.sha256(raw).hexdigest() == "9ce3c1c67e5ca71bd10534d7eeb8a38bbc42a28ce7f0887528ac6ce16fa140bc", "docs/rfi2_dokink.md is the owner's file; it is not edited here"
    q = lq.rfi2_questions()
    assert sorted(q) == list(range(1, 25)) and "gasifier operating temperature" in q[17].lower()
    assert sorted(lq.rfi1_questions()) == list(range(1, 18)), "data/rfi_dokink.md stays the first, 17-question RFI"


def test_every_upgrade_question_reference_points_to_a_question_that_exists(built):
    refs = {r for row in built[0] for r in row["upgrade_question"]}
    assert refs and lq.problems(sorted(refs)) == []
    assert all(isinstance(row["upgrade_question"], list) for row in built[0])
    every = {r for refs_, _ in lq.RFI_MAP.values() for r in refs_} | {r for refs_, _ in lq.CONSIDERED.values() for r in refs_}
    assert lq.problems(sorted(every)) == []


def test_a_reference_to_a_question_that_does_not_exist_is_refused():
    assert lq.problems(["RFI2-25", "RFI2-0", "RFI1-18", "master_open_questions:1.99", "master_open_questions:2.1", "RFI3-1", "RFI2-3x", ""]) == ["RFI2-25", "RFI2-0", "RFI1-18", "master_open_questions:1.99", "master_open_questions:2.1", "RFI3-1", "RFI2-3x", ""]
    assert lq.problems(["RFI2-1", "RFI2-24", "RFI1-1", "RFI1-17", "master_open_questions:1.1", "master_open_questions:3.4"]) == []


def test_the_rfi_mapping_only_touches_rows_that_had_no_question_and_every_reason_is_stated(built):
    tags = {r["tag"] for r in built[0]}
    assert set(lq.RFI_MAP) <= tags and set(lq.CONSIDERED) <= tags and not (set(lq.RFI_MAP) & set(lq.CONSIDERED))
    assert not (set(lq.RFI_MAP) & set(lr.UPGRADE)), "a row that already had a master_open_questions reference is not remapped"
    for n in lr.build_rows():
        if n["tag"] in lq.RFI_MAP:
            assert n["upgrade_question"] == [], n["tag"]
    for tag, (refs, why) in list(lq.RFI_MAP.items()) + list(lq.CONSIDERED.items()):
        assert refs and len(why) > 20, tag
    by = {r["tag"]: r["upgrade_question"] for r in built[0]}
    assert by["GA-001.T_gasifier_C"] == ["RFI2-17"] and by["GA-001.tail_gas_mode"] == ["RFI2-9", "RFI2-20"] and by["UNC.feed_chlorine_ppm"] == ["RFI2-7", "RFI1-2"]
    assert by["HB-012.polytropic_n"] == ["master_open_questions:3.3"]
    for tag in lq.CONSIDERED:
        assert not any(r.startswith("RFI") for r in by[tag]), tag


# ------------------------------------------------------------------ (A3b 2.5 to 2.7, 4.1) the prose sections cite lines that exist

def test_every_line_cited_in_the_prose_sections_is_found():
    for u in lnotes.KNOWN_UNDECLARED_READS:
        for w in u["where"]:
            assert lnotes.locate(*w), w
    for _, f, tok, _ in lnotes.UNUSED_CONSTANTS:
        assert lnotes.locate(f, tok), tok
    for i in lnotes.INCONSISTENCIES:
        for _, f, tok in i["values"]:
            assert lnotes.locate(f, tok), tok
    assert "NOT FOUND" not in "\n".join(lnotes.render_prose())


def test_the_known_undeclared_reads_in_the_docs_are_the_ones_the_test_pins():
    docs = {(u["reads"], u["reader"]) for u in lnotes.KNOWN_UNDECLARED_READS}
    assert docs == KNOWN_UNDECLARED_READS


def test_the_two_recorded_inconsistencies_are_the_values_in_the_code():
    from python import eu_utilities_chp as eu, ga001_gasifier_model as ga
    assert eu.H2_LHV_MJ_PER_NM3 == 10.8 and eu.SYNGAS_SPECIES_LHV_MJ_PER_NM3["H2"] == 10.783
    assert ga.M_H2O == 18.015 and abs((2 * ga.M_H + ga.M_O) - 18.016) < 1e-9
    docs = open(os.path.join(ROOT, "docs", "design_basis_ledger.md"), encoding="utf-8").read()
    for heading in ("## Known undeclared reads", "## Inline literals", "## Constants nothing uses", "## Inconsistencies recorded, not fixed", "## Question references", "## RFI mapping"):
        assert heading in docs, heading


def test_the_three_constants_nothing_uses_are_still_unused(built):
    none = {r["ledger_id"] for r in built[0] if not r["consumers"]}
    assert {"LEDGER.FE-001.total_capacity_t", "LEDGER.FE-002.removal_efficiency", "LEDGER.HB-010.h2_recovery"} <= none
    for name, f, tok, _ in lnotes.UNUSED_CONSTANTS:
        hits = []
        for fn in os.listdir(os.path.join(ROOT, "python")):
            if fn.endswith(".py") and not fn.startswith("ledger_"):
                hits += [(fn, i) for i, line in enumerate(open(os.path.join(ROOT, "python", fn), encoding="utf-8"), 1) if name in line]
        code_lines = [h for h in hits if h[0] != f.split("/")[-1] or name + " =" in open(os.path.join(ROOT, f), encoding="utf-8").read().split("\n")[h[1] - 1]]
        assert len(code_lines) == 1, (name, hits)


# ------------------------------------------------------------------ (A3b 2.2) the "Confirmed" mention guard

# {file: (DOK-ING-SOURCED, GENERIC, REGISTRY-STATED)}: lines of the 18 engine modules that mention "confirmed" (case-insensitive), classified by python/ledger_coverage.classify_mention.
# The existing mentions are NOT rewritten. Any change to these numbers (a new mention, a removed one, a reworded one that moves class) fails here and must be made on purpose; a new
# REGISTRY-STATED use is the case this guard exists for: say where the value comes from (name the DOK-ING source) or do not call it Confirmed.
# Task A3d (Gate 5 wording) lowered three files ON PURPOSE (449 -> 436 lines; classes 49/159/241 -> 44/160/232): hb_wgs_psa_storage_chain (3, 6, 27) -> (2, 6, 26), eu_utilities_chp
# (5, 19, 34) -> (2, 20, 26), fe_feed_handling (6, 12, 18) -> (5, 12, 18). Lines that called an Assumed / Unverified (registry) constant Confirmed now state its ledger status.
# P0-CLOSE C3 lowered eu_utilities_chp once more, (2, 20, 26) -> (2, 20, 24) and 436 -> 434 lines: the two docstring lines (EU-008 "Confirmed 20kW rating", ~58kW paragraph) now say registry-stated,
# Unverified (registry), scoped by the registry remark to EU-004 jacket cooling. ai_automation_layer.py is not in CONFIRMED_SCOPE, so its three reworded lines move no pin.
# G5-12 wording fix lowered ga001_gasifier_model by one REGISTRY-STATED line, (16, 25, 36) -> (16, 25, 35) and 434 -> 433 lines: a comment that called DOK-ING's ash range 'confirmed' and 'cross-validated' now says 'range-checked ... stated'.
CONFIRMED_PIN = {
    "ga001_gasifier_model.py": (16, 25, 35), "ga001_energy_balance.py": (1, 0, 0), "gasifier_mass_balance.py": (2, 0, 1), "gc_gas_cleaning_chain.py": (0, 28, 60),
    "hb_wgs_psa_storage_chain.py": (2, 6, 26), "hb_remaining_chain.py": (1, 35, 47), "eu_utilities_chp.py": (2, 20, 24), "balance_audit.py": (2, 3, 4), "fe_feed_handling.py": (5, 12, 18),
    "uncertainty.py": (0, 26, 4), "reference_feeds.py": (1, 1, 2), "tab1_integration.py": (12, 4, 8),
}
PERSISTED_REGISTRY_STATED = 14      # was 88 before task W1.1. What remains on purpose: 3 persisted + 3 self-test prints that name DOK-ING's CONFIRMED ranges (RFI #2, named in the same sentence), 2 negations ("no
# blowdown figure is separately confirmed", "not Confirmed"), 2 negations ("is CONFIRMED ... anywhere", "not a DOK-ING/vendor-confirmed figure"), 2 questions that ask DOK-ING to confirm, one self-test assert
# message, one status check in code. None of them calls a registry value Confirmed. See docs/design_basis_ledger.md and the W1 report.


def test_the_confirmed_mentions_are_pinned_per_class_and_file():
    mentions = lc.confirmed_mentions()
    got = {k.split("/")[-1]: tuple(v[c] for c in lc.MENTION_CLASSES) for k, v in lc.mention_counts(mentions).items()}
    assert got == CONFIRMED_PIN, {k: (got.get(k), CONFIRMED_PIN.get(k)) for k in set(got) | set(CONFIRMED_PIN) if got.get(k) != CONFIRMED_PIN.get(k)}
    assert len(mentions) == 433 and len(lc.CONFIRMED_SCOPE) == 18
    assert {m["class"] for m in mentions} == set(lc.MENTION_CLASSES)


def test_a_new_registry_stated_confirmed_mention_changes_the_counts():
    src = open(os.path.join(ROOT, "python", "psa.py"), encoding="utf-8").read()
    before = lc.mention_counts(lc.confirmed_mentions())
    for added, klass in (("# the value is HB-006's own Confirmed 75 % recovery\n", lc.MENTION_REGISTRY),
                         ("# the value is HB-006's own Confirmed 75 % recovery (DOK-ING RFI #1 answer)\n", lc.MENTION_SOURCED),
                         ("# this is not a confirmed figure\n", lc.MENTION_GENERIC)):
        after = lc.mention_counts(lc.confirmed_mentions(sources={"python/ga001_gasifier_model.py": open(os.path.join(ROOT, "python", "ga001_gasifier_model.py"), encoding="utf-8").read() + "\n" + added}))
        f = "python/ga001_gasifier_model.py"
        assert after[f] != before[f] and after[f][klass] == before[f][klass] + 1, (added, after[f], before[f])
    assert src


def test_the_classifier_on_the_three_kinds_of_sentence():
    c = lc.classify_mention
    assert c(["GC-001's own Confirmed registry outlet temperature (880 degC), read directly."], 0) == lc.MENTION_REGISTRY
    assert c(["# the rate is Confirmed", "# DOK-ING RFI #1 answer, data/dokink_rfi_answers.md"], 0) == lc.MENTION_SOURCED
    assert c(["# the rate is Confirmed", "#", "#", "#", "# RFI #1 answer, four lines down"], 0) == lc.MENTION_REGISTRY, "the source must be within the next 3 lines"
    assert c(["None of this is confirmed anywhere in this project."], 0) == lc.MENTION_GENERIC
    assert c(["status = ps.STATUS_CONFIRMED"], 0) == lc.MENTION_GENERIC
    assert c(["# Confirmed / Calculated / Estimated are the project's statuses"], 0) == lc.MENTION_GENERIC
    assert c(["HB010_CONFIRMED_RECOVERY = 0.85   # registry-stated [Unverified (registry)]"], 0) == lc.MENTION_GENERIC


def test_the_registry_stated_mentions_that_reach_a_persisted_note_are_counted(runs):
    texts = []

    def walk(x):
        if isinstance(x, str):
            texts.append(x)
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, (list, tuple)):
            for v in x:
                walk(v)
    for mode in ("default", "heat_only"):
        walk(_ser(runs[mode]))
    hits = [m for m in lc.persisted_mentions(lc.confirmed_mentions(), texts) if m["class"] == lc.MENTION_REGISTRY]
    assert len(hits) == PERSISTED_REGISTRY_STATED, (len(hits), "a persisted REGISTRY-STATED wording changed: if it was reworded, lower the pin on purpose (and extend tests/_d2_wording.py only with a decision)")


# ------------------------------------------------------------------ (C.3) status rules

def test_the_ledger_obeys_the_status_rules(built):
    ledger = built[0]
    assert lc.status_problems(ledger) == []
    assert {r["status"] for r in ledger} <= set(pt.TABLE_STATUSES)
    for r in ledger:
        if r["status"] == "Confirmed":
            assert "DOK-ING" in r["source_line"] and r["origin"] == "DOK-ING", r["ledger_id"]
        assert r["origin"] in ("DOK-ING", "SIMILAR_PLANT", "ASSUMED", "CALCULATED", "UNKNOWN", pt.NOT_STATED), r["ledger_id"]


@pytest.mark.parametrize("row,fragment", [
    ({"ledger_id": "a", "status": "Confirmed", "origin": "DOK-ING", "source_line": ""}, "without a source_line"),
    ({"ledger_id": "b", "status": "Confirmed", "origin": "DOK-ING", "source_line": "the vendor brochure"}, "without a source_line"),
    ({"ledger_id": "c", "status": "Confirmed", "origin": "ASSUMED", "source_line": "DOK-ING RFI x"}, "ASSUMED cannot be Confirmed"),
    ({"ledger_id": "d", "status": "Confirmed", "origin": "UNKNOWN", "source_line": "DOK-ING RFI x"}, "UNKNOWN cannot be Confirmed"),
    ({"ledger_id": "e", "status": "Confirmed", "origin": "NOT STATED", "source_line": "DOK-ING RFI x"}, "needs origin DOK-ING"),
    ({"ledger_id": "f", "status": "Calculated", "origin": "CALCULATED", "source_line": "", "note": "derived somehow"}, "without a formula"),
])
def test_each_status_rule_violation_is_reported(row, fragment):
    problems = lc.status_problems([row])
    assert problems and fragment in problems[0][1], problems


def test_a_calculated_row_with_a_formula_passes():
    assert lc.status_problems([{"ledger_id": "ok", "status": "Calculated", "note": "0.25 x stoichiometric air", "source_line": ""}]) == []
    assert lc.status_problems([{"ledger_id": "ok2", "status": "Calculated", "note": "", "source_line": "the formula is ER x air"}]) == []


# ------------------------------------------------------------------ (B) consumers

def test_a_known_input_lists_the_keys_that_really_read_it(built):
    ledger, _, _, readers = built
    er = ("GA-001-INPUT", "equivalence_ratio")
    assert ("GA-001", "Outputs") in readers[er] and ("GA-001", "EnergyBalance") in readers[er]
    row = next(r for r in ledger if r["tag"] == "GA-001.ER" and r["overridable_via"] == "engine input")
    assert "GA-001|Outputs" in row["consumers"] and "GA-001|EnergyBalance" in row["consumers"], row["consumers"]


# Found by the instrumented run (task A3), reported and NOT fixed (engine files are out of scope): two models call get_input for a key they do not declare in depends_on /
# lagged_depends_on. Pinned here so that a THIRD hidden read fails this test, and so that fixing one of these means removing it from the list.
KNOWN_UNDECLARED_READS = {
    (("GA-001", "CarbonAccounting"), ("GA-001", "EnergyBalance")),     # balance_audit.carbon_black_flows (via ga001_terms) reads the derived carbon black
    (("WGS", "Composition"), ("HB-009", "TailGas")),                   # the PSA tail-gas handler reads the WGS composition
}


def test_instrumented_reads_agree_with_the_declared_dependencies_except_two_known_hidden_ones(built):
    readers = built[3]
    declared = lcons.declared_readers()
    undeclared = {(dep, m) for dep, models in readers.items() for m in models if m not in declared.get(dep, [])}
    assert undeclared == KNOWN_UNDECLARED_READS, undeclared ^ KNOWN_UNDECLARED_READS


def test_an_input_that_nothing_reads_is_reported():
    engine_state = sps.SharedPlantState()
    holder = {}

    def build():
        e = se.SimulationEngine(engine_state)
        e.register_model(("T", "used"), _const(1.0), unit="-")
        e.register_model(("T", "unused"), _const(2.0), unit="-")
        e.register_model(("T", "out"), lambda get_input: {"value": get_input(("T", "used"))["value"] * 2, "status": ps.STATUS_CALCULATED, "inputs": [("T", "used")],
                                                          "validation_basis": ps.VALIDATION_NA, "confidence_note": ""}, unit="-", depends_on=[("T", "used")])
        e.run_cycle(now="2026-09-10T00:00:00Z")
    readers = lcons.engine_input_readers(build)
    assert readers == {("T", "used"): [("T", "out")]} and ("T", "unused") not in readers


def test_rows_without_a_consumer_are_reported_not_deleted(built):
    ledger = built[0]
    none = {r["ledger_id"] for r in ledger if not r["consumers"]}
    assert {"LEDGER.FE-001.total_capacity_t", "LEDGER.FE-002.removal_efficiency", "LEDGER.HB-010.h2_recovery"} <= none      # constants nothing in the code uses
    assert len(ledger) == 179                                  # A3b 2.3: PLANT.hhv_correlation_coefficients is no longer a row (-1); 2.4: two verdict-threshold rows (+2)


def test_every_code_row_has_the_function_that_names_it(built):
    by = {r["tag"]: r for r in built[0]}
    assert "psa.psa_recovery" in by["HB-006.psa_K1"]["consumers"]
    assert by["GC-003.efficiency"]["consumers"] == ["gc_gas_cleaning_chain.gc003_dust"]
    assert any(c.startswith("eu_utilities_chp.eu004") for c in by["EU-004.jacket_kwth_rated"]["consumers"])


# ------------------------------------------------------------------ (F.4) the engine is unchanged

def _assert_only_the_d2_phrases_differ(old, new, mode):
    """`old` = the origin/main fixture entries, `new` = the serialised live snapshot. The fixture is mapped FORWARD (old phrase -> new phrase, tests/_d2_wording.PAIRS, only in the entries that
    carry them); every entry of the live snapshot must then equal it: strings exactly, floats within 1e-12 relative. So an old phrase that returns, or any other text or number that changes,
    fails. The entries that differ from the unmapped fixture at all must be entries that can carry the phrases.

    The float tolerance applies to BOTH checks. The fixture was made on Python 3.14. Python 3.12 changed the builtin sum() of floats to compensated (Neumaier) summation; Python 3.11,
    which the hourly job and CI run, adds left to right. Values that pass through sum() therefore differ in the last one or two bits on 3.11 (largest relative difference measured with a
    3.11-style sum(): 4.4e-14); a bit-exact comparison failed on 3.11 and passed on 3.12 although nothing had changed. A real change (1e-9 relative, one character of text, a phrase in another
    entry, an old phrase back) still fails: test_the_persisted_comparison_still_catches_a_real_change."""
    expected = _d2_wording.forward(old)
    diffs = {k: _same(expected[k], new[k]) for k in old if k not in ("GA-001-INPUT|tail_gas_mode",) or mode == "default"}
    bad = {k: v for k, v in diffs.items() if v is not True}
    assert bad == {}, bad
    changed = [k for k in old if k != "GA-001-INPUT|tail_gas_mode" and _same(old[k], new[k]) is not True]
    assert all(k.startswith(_d2_wording.ENTRIES) for k in changed), changed


@pytest.mark.parametrize("mode,fixture_key", [("default", "default|20"), ("heat_only", "heat_only|20")])
def test_every_persisted_entry_equals_origin_main_in_both_tail_gas_modes(runs, main_snap, mode, fixture_key):
    new = _ser(runs[mode])
    old = main_snap[fixture_key]
    assert set(new) - {"GA-001-INPUT|gasifying_agent", "GA-001|AgentConsistency"} == set(old) and len(new) == 123, "same persisted keys plus the two A1 keys, same count"          # A1 (deliberate edit): +1 = the switch input (GA-001-INPUT, gasifying_agent); A1.3 adds (GA-001, AgentConsistency): 123 in all
    new_wording = {k: v for k, v in new.items() if k.startswith(_d2_wording.ENTRIES)}
    _assert_only_the_d2_phrases_differ(old, new, mode)
    # the one deliberate text change is really there (and only in the entries that can carry it)
    text = json.dumps(new_wording)
    assert "registry '>98% removal efficiency' (Unverified (registry), not DOK-ING-confirmed)" in text
    assert "registry >90% efficiency (>d50=15um; Unverified (registry))" in text
    assert "ACTUAL/DOK-ING VALUE: Unverified (registry), not DOK-ING-confirmed -- 20 kW" in text
    assert "ACTUAL/DOK-ING VALUE: Confirmed" not in json.dumps(new)


def _first_float_leaf(x, path=()):
    """(path, value) of the first float leaf that is not zero."""
    if isinstance(x, float) and x != 0.0:
        return path, x
    if isinstance(x, dict):
        for k in sorted(x):
            r = _first_float_leaf(x[k], path + (k,))
            if r:
                return r
    if isinstance(x, list):
        for i, v in enumerate(x):
            r = _first_float_leaf(v, path + (i,))
            if r:
                return r
    return None


def _first_string_leaf(x, path=()):
    if isinstance(x, str) and len(x) > 5:
        return path, x
    if isinstance(x, dict):
        for k in sorted(x):
            r = _first_string_leaf(x[k], path + (k,))
            if r:
                return r
    if isinstance(x, list):
        for i, v in enumerate(x):
            r = _first_string_leaf(v, path + (i,))
            if r:
                return r
    return None


def _set(x, path, value):
    for step in path[:-1]:
        x = x[step]
    x[path[-1]] = value


def test_the_persisted_comparison_still_catches_a_real_change(runs, main_snap):
    import copy
    old = main_snap["default|20"]
    new = _ser(runs["default"])
    _assert_only_the_d2_phrases_differ(old, new, "default")                        # the real, unperturbed condition passes
    key = next(k for k in sorted(new) if not k.startswith(_d2_wording.ENTRIES) and k != "GA-001-INPUT|tail_gas_mode"          # an entry that carries no phrase at all
               and _first_float_leaf(new[k].get("value")) and _first_string_leaf(new[k]))
    assert not key.startswith(_d2_wording.ENTRIES)
    for n_, o_ in _d2_wording.PAIRS:                                              # 0) every old phrase coming back, one at a time, fails
        back = json.loads(json.dumps(new).replace(n_, o_))
        assert back != new, n_
        with pytest.raises(AssertionError):
            _assert_only_the_d2_phrases_differ(old, back, "default")

    ulp = copy.deepcopy(new)                                                      # a last-bit difference (what Python 3.11 produces) is tolerated
    path, v = _first_float_leaf(ulp[key]["value"])
    _set(ulp[key]["value"], path, v * (1.0 + 1e-13))
    _assert_only_the_d2_phrases_differ(old, ulp, "default")

    number = copy.deepcopy(new)                                                   # 1) one non-D2 numeric leaf moved by 1e-9 relative
    _set(number[key]["value"], path, v * (1.0 + 1e-9))
    with pytest.raises(AssertionError):
        _assert_only_the_d2_phrases_differ(old, number, "default")

    text = copy.deepcopy(new)                                                     # 2) one non-D2 string changed by one character
    spath, s = _first_string_leaf(text[key])
    _set(text[key], spath, s + "x")
    with pytest.raises(AssertionError):
        _assert_only_the_d2_phrases_differ(old, text, "default")

    phrase = copy.deepcopy(new)                                                   # 3) a D2 phrase appearing in an entry that may not carry it
    _set(phrase[key], spath, _d2_wording.PAIRS[0][0])
    assert _d2_wording.undo(phrase)[key] == phrase[key], "undo() does not touch entries outside the D2 prefixes, so it cannot hide this"
    with pytest.raises(AssertionError):
        _assert_only_the_d2_phrases_differ(old, phrase, "default")

    d2 = copy.deepcopy(new)                                                       # 4) a numeric change INSIDE an entry that may carry D2 text is caught too
    target = next((k for k in sorted(d2) if k.startswith(_d2_wording.ENTRIES) and _first_float_leaf(d2[k])), None)
    assert target is not None, "at least one D2 entry has a float leaf"
    path2, v2 = _first_float_leaf(d2[target])
    _set(d2[target], path2, v2 * (1.0 + 1e-9))
    with pytest.raises(AssertionError):
        _assert_only_the_d2_phrases_differ(old, d2, "default")


def test_the_runtime_shrink_guard_accepts_the_persisted_set(runs, main_snap):
    spec = importlib.util.spec_from_file_location("run_continuous_cycle", os.path.join(ROOT, "scripts", "run_continuous_cycle.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    stored = [tuple(k.split("|", 1)) for k in main_snap["default|20"]]
    new = list(runs["default"])
    assert set(stored) | {("GA-001-INPUT", "gasifying_agent"), ("GA-001", "AgentConsistency")} == set(new) and len(new) == 123          # A1 (deliberate edit): +1 = the switch input (GA-001-INPUT, gasifying_agent); A1.3 adds (GA-001, AgentConsistency): 123 in all
    assert mod.check_shrink(stored, new) is None
    assert mod.check_shrink(stored, new[:100]) is not None, "the guard itself is live: a persisted set that lost 21 keys is refused"


# A3b 1 (correction of the A3 report): the numbers pinned here, 6 / 249 / 291 over 756 data points, are what equipment_datasheet.summarize() returns with NO argument, i.e. the registry rows
# resolved against the overlay and nothing else. They are NOT what the app displays: app.py builds `_eq_datasheets` from the registry PLUS the RFI fills PLUS the engineering estimates
# (resolved), and every "Honest count" and the all-sections cards use summarize(_eq_datasheets...), which is 13 / 297 / 236 over 814 data points (pinned by tests/test_apply_provenance.py and
# tests/test_apply_wording.py). The test below is named for the A3 report's wording and kept; test_the_app_counts_are_the_resolved_chain_not_the_summarize_default states the difference.
def test_the_ui_status_counts_are_unchanged():
    s = ed.summarize()
    assert (s["total_real_data_points"], s["total_category_slots"], s["confirmed_category_slots"], s["estimated_category_slots"], s["missing_category_slots"]) == (756, 546, 6, 249, 291)
    expected = {"FE": (69, 48, 2, 24, 22), "GA": (84, 60, 0, 27, 33), "GC": (115, 90, 0, 52, 38), "SA": (85, 72, 0, 26, 46), "HB": (154, 108, 4, 52, 52), "EU": (114, 78, 0, 45, 33),
                "AI": (135, 90, 0, 23, 67)}
    groups = {"FE": ed.FE_IDS, "GA": ed.GA_IDS, "GC": ed.GC_IDS, "SA": ed.SA_IDS, "HB": ed.HB_IDS, "EU": ed.EU_IDS, "AI": ed.AI_IDS}
    for name, ids in groups.items():
        t = ed.summarize(ids=list(ids))
        assert (t["total_real_data_points"], t["total_category_slots"], t["confirmed_category_slots"], t["estimated_category_slots"], t["missing_category_slots"]) == expected[name], name


# ------------------------------------------------------------------ (A3b 2.1) the D2 exemption stays narrow

W1_FINGERPRINT = "e3f4ed31fd00a9a06b3c85db5a1ee39d50425ffb9c79a56102fa130097cc411d"      # sha256 of PAIRS_W1 + ENTRIES_W1 (tests/_d2_wording.w1_fingerprint()); changes when a W1 pair or entry is added, removed or reworded
# A3d (deliberate edit): was e35d0cf93220024a1e95cd20c8c3b800f4fb00b9c1d4b5f421f1621717326f1e. The HB-012 compressor pair moved from PAIRS_W1 (89 pairs) to PAIRS_A3D with the new wording of task A3d.
A3D_FINGERPRINT = "790301514144c8871ef1a3a33a53329af3382621ed368a28c318d68d4b295e99"      # sha256 of PAIRS_A3D + ENTRIES_A3D (tests/_d2_wording.a3d_fingerprint())


def test_the_exemption_list_is_exactly_the_listed_phrase_pairs():
    """tests/_d2_wording.py is the ONE exemption list: the 4 D2 pairs in 3 entry prefixes, plus the W1 pairs in the listed entries. Adding a pair or an entry fails here; a new one needs a decision."""
    assert _d2_wording.PAIRS_D2 == (
        ("registry '>98% removal efficiency' (Unverified (registry), not DOK-ING-confirmed)", "own Confirmed '>98% removal efficiency'"),
        ("registry >90% efficiency (>d50=15um; Unverified (registry))", "own Confirmed >90% efficiency (>d50=15um)"),
        ("ACTUAL/DOK-ING VALUE: Unverified (registry), not DOK-ING-confirmed -- 20 kW", "ACTUAL/DOK-ING VALUE: Confirmed -- 20 kW"),
        ("Unverified (registry), not DOK-ING-confirmed -- 20 kW, scoped to EU-004 jacket cooling only (per EU-008's own", "Confirmed -- 20 kW, scoped to EU-004 jacket cooling only (per EU-008's own"),
    )
    assert _d2_wording.ENTRIES_D2 == ("FE-002|", "GC-001|", "EU-008|")
    assert _d2_wording.PAIRS == _d2_wording.PAIRS_D2 + _d2_wording.PAIRS_W1 + _d2_wording.PAIRS_A3D and _d2_wording.ENTRIES == _d2_wording.ENTRIES_D2 + _d2_wording.ENTRIES_W1
    assert (len(_d2_wording.PAIRS_W1), len(_d2_wording.ENTRIES_W1)) == (88, 43)
    assert _d2_wording.w1_fingerprint() == W1_FINGERPRINT
    assert (len(_d2_wording.PAIRS_A3D), _d2_wording.ENTRIES_A3D) == (2, ("HB-012|Compressor", "EU-CHP|Dispatch")) and set(_d2_wording.ENTRIES_A3D) <= set(_d2_wording.ENTRIES_W1)
    assert _d2_wording.a3d_fingerprint() == A3D_FINGERPRINT
    assert all(isinstance(n, str) and isinstance(o, str) and n != o and n and o for n, o in _d2_wording.PAIRS)
    src = open(os.path.join(ROOT, "tests", "_d2_wording.py"), encoding="utf-8").read()
    assert src.count(".replace(") == 2, "forward() and undo() map through PAIRS only (one replace each); no other replacement rule"


def test_undo_changes_nothing_but_those_phrases():
    probe = {"FE-002|X": {"a": "Confirmed -- 30 kW", "b": ["own Confirmed text", 1.5, None], "c": {"d": "Unverified (registry)"}},
             "HB-001|X": {"a": _d2_wording.PAIRS[0][0]}}                          # outside ENTRIES: never touched
    assert _d2_wording.undo(probe) == probe
    inside = {"FE-002|X": {"a": _d2_wording.PAIRS[0][0] + " tail"}}
    assert _d2_wording.undo(inside) == {"FE-002|X": {"a": _d2_wording.PAIRS[0][1] + " tail"}}


def _differing_leaves(a, b, path=""):
    """[(path, kind)] of every leaf at which two serialised entries differ: text and structure exactly; two numbers are the same within 1e-12 relative (the 701de71 fixture was made on 3.14, where
    sum() is compensated; CI runs 3.11, where the last bit can differ -- max measured 4.4e-14). A number that moved more than that is reported with its kind."""
    if isinstance(a, dict) and isinstance(b, dict):
        return [x for k in sorted(set(a) | set(b)) for x in _differing_leaves(a.get(k), b.get(k), f"{path}/{k}")]
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return [x for i, (p, q) in enumerate(zip(a, b)) for x in _differing_leaves(p, q, f"{path}[{i}]")]
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        return [] if math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-15) else [(path, type(a).__name__)]
    return [] if a == b else [(path, type(a).__name__)]


EXPECTED_DIFFERING_LEAVES = (73, 45)      # (string fields, entries) at which the live snapshot differs from the 701de71 fixture; no number is among them


@pytest.mark.parametrize("mode,fixture_key", [("default", "default|20"), ("heat_only", "heat_only|20")])
def test_the_persisted_text_differences_are_exactly_the_mapped_fields(runs, main_snap, mode, fixture_key):
    old, new = main_snap[fixture_key], _ser(runs[mode])
    mapped = _d2_wording.forward(old)
    live = sorted((k + p, kind) for k in old if k != "GA-001-INPUT|tail_gas_mode" for p, kind in _differing_leaves(old[k], new[k]))
    by_map = sorted((k + p, kind) for k in old if k != "GA-001-INPUT|tail_gas_mode" for p, kind in _differing_leaves(old[k], mapped[k]))
    assert live == by_map, "the live snapshot differs from the fixture at exactly the fields the mapping changes, and nowhere else"
    assert {kind for _, kind in live} == {"str"}, "no number, list length or key moved: text only"
    assert (len(live), len({p.split("/")[0] for p, _ in live})) == EXPECTED_DIFFERING_LEAVES


def test_the_app_counts_are_the_resolved_chain_not_the_summarize_default():
    from python import equipment_engineering_estimates as eee, equipment_rfi_fills as erf
    default = ed.summarize()
    app = ed.summarize(ed.resolve_datasheets(eee.apply_estimates(erf.apply_rfi_fills(ed.build_all_datasheets()))))
    assert (default["confirmed_category_slots"], default["estimated_category_slots"], default["missing_category_slots"], default["total_real_data_points"]) == (6, 249, 291, 756)
    assert (app["confirmed_category_slots"], app["estimated_category_slots"], app["missing_category_slots"], app["total_real_data_points"]) == (13, 297, 236, 814)
    assert default["total_category_slots"] == app["total_category_slots"] == 546
    src = open(os.path.join(ROOT, "app.py"), encoding="utf-8").read().replace("\r\n", "\n")
    chain = ("_eq_datasheets = equipment_datasheet.resolve_datasheets(\n    equipment_engineering_estimates.apply_estimates(\n        equipment_rfi_fills.apply_rfi_fills(equipment_datasheet.build_all_datasheets())\n    )\n)")
    assert chain in src, "app.py builds its datasheets from the registry + RFI fills + estimates, resolved"
    assert src.count("equipment_datasheet.summarize(_eq_datasheets") >= 9 and "equipment_datasheet.summarize()" not in src, "every count in the app uses the app's chain, none the no-argument default"


COMMITTED = {n: open(os.path.join(ROOT, "docs", n), encoding="utf-8", newline="").read().replace(chr(13) + chr(10), chr(10)) for n in ("design_basis_ledger.md", "design_basis_ledger.csv")}


# ------------------------------------------------------------------ (A3c 1) anchors: the committed export does not depend on line numbers

def test_every_row_has_a_symbolic_anchor_and_no_two_rows_share_one(built):
    ledger = built[0]
    rep = la.anchor_report(ledger)
    assert rep["rows"] == len(ledger) == 179 and rep["shared"] == []          # A1 (deliberate edit): 173 + the gasifying_agent switch + 4 agent constants
    for r in ledger:
        a = r["anchor"]
        assert re.match(r"^(registry:[A-Z]+-\d+/.+|[a-z_0-9]+:[A-Za-z_0-9#+:'\[\]\(\)\. /,-]+)$", a), (r["ledger_id"], a)
        assert not re.search(r":\d+$", a), (r["ledger_id"], "an anchor ends in a symbol or #n, never in a bare line number")


def test_the_ambiguous_and_fallback_anchors_are_exactly_these(built):
    ledger = built[0]
    rep = la.anchor_report(ledger)
    assert rep["ambiguous"] == ["balance_audit:efficiency_check:h2_kw_engine#1", "chp:chp_efficiency:x+eta#1+eta#2+eta#3+eta#4+eta#5+eta#6+eta#7", "hb_wgs_psa_storage_chain:hb012_compressor:T1_K#1"]
    assert rep["fallback"] == ["gc_gas_cleaning_chain:gc004_cooling_duty#1", "gc_gas_cleaning_chain:gc004_cooling_duty#2"]


def test_a_literal_is_named_by_what_it_is_assigned_to_and_numbered_only_as_a_fallback():
    src = ("def f(a, b=0.37):\n"
           "    x = 3.5\n"
           "    y = g(k=4.5)\n"
           "    z = {'rate': 5.5}\n"
           "    return h(6.5) + 7.5\n"
           "def g2():\n"
           "    t = 8.5\n"
           "    t = 9.5\n")
    occ = la.function_literals(src, "f")
    assert [n for n, _, _ in occ] == ["b", "x", "k", "rate", None, None]
    assert la.literal_anchor("python/m.py", src, "f", [0.37])[0] == "m:f:b"
    assert la.literal_anchor("python/m.py", src, "f", [3.5])[0] == "m:f:x"
    assert la.literal_anchor("python/m.py", src, "f", [4.5])[0] == "m:f:k"
    assert la.literal_anchor("python/m.py", src, "f", [5.5])[0] == "m:f:rate"
    a, flags = la.literal_anchor("python/m.py", src, "f", [6.5])
    assert a == "m:f#5" and flags == {"fallback"}, "no stable name: module:function#n, n counted within that function only"
    assert la.literal_anchor("python/m.py", src, "f", [7.5])[0] == "m:f#6"
    a, flags = la.literal_anchor("python/m.py", src, "g2", [9.5])
    assert a == "m:g2:t#2" and flags == {"ambiguous"}, "two literals named t: an ordinal"
    assert la.literal_anchor("python/m.py", src, "g2", [8.5])[0] == "m:g2:t#1"


def test_an_anchor_does_not_contain_the_position_of_the_line_it_is_on():
    src = "\n\n\n# unrelated\n" + "def f():\n    x = 3.5\n"
    assert la.literal_anchor("python/m.py", src, "f", [3.5])[0] == la.literal_anchor("python/m.py", "def f():\n    x = 3.5\n", "f", [3.5])[0]


def test_the_committed_export_carries_no_code_line_numbers_and_no_file_line_column():
    for name, text in COMMITTED.items():
        assert not re.search(r"\.(py|json):\d+", text), (name, re.findall(r".{30}\.(?:py|json):\d+", text)[:3])
    assert "file_line" not in COMMITTED["design_basis_ledger.csv"].split("\n")[0] and "anchor" in COMMITTED["design_basis_ledger.csv"].split("\n")[0]
    assert la.strip_code_lines("see python/psa.py:12 and data/x.json:3-4 and data/dokink_rfi_answers.md:15") == "see python/psa.py and data/x.json and data/dokink_rfi_answers.md:15"


# ------------------------------------------------------------------ (A3c 1) the export on a temporary copy of the repository

COPY = ("python", "data", "docs", "scripts", "app.py", "tests/_fakes.py")             # the consumer search reads app.py and scripts/ too
UNRELATED = "# unrelated line added above (task A3c test)\n"


def _copy_repo(dst):
    for rel in COPY:
        src, to = os.path.join(ROOT, rel), os.path.join(dst, rel)
        if os.path.isdir(src):
            shutil.copytree(src, to, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            os.makedirs(os.path.dirname(to), exist_ok=True)
            shutil.copy(src, to)


def _export(dst):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    env.pop("HYGAS_ALLOW_DB_WRITES", None)
    r = subprocess.run([sys.executable, os.path.join("scripts", "export_design_basis_ledger.py")], cwd=dst, env=env, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout[-400:] + r.stderr[-1500:]
    return {n: open(os.path.join(dst, "docs", n), encoding="utf-8", newline="").read().replace("\r\n", "\n") for n in COMMITTED}


def _edit(dst, rel, fn):
    p = os.path.join(dst, rel)
    t = open(p, encoding="utf-8", newline="").read()
    nl = "\r\n" if "\r\n" in t else "\n"
    out = fn(t.replace("\r\n", "\n"))
    assert out != t.replace("\r\n", "\n"), f"the edit changed nothing in {rel}"
    open(p, "w", encoding="utf-8", newline="").write(out.replace("\n", nl))


def _shift_everything(dst):
    """Unrelated lines above every top-level function and every UPPER_CASE constant of every scanned module (and at the top of each file)."""
    for mod in lc.SCAN_MODULES + ("tab1_integration",):
        rel = lc.rel_path(mod)

        def shift(t):
            # not between a comment and the line it comments: the "Confirmed" class of a mention is decided by what stands in the next 3 lines (A3b 2.2), so a line inserted INSIDE such a
            # block is not an unrelated line
            lines, out = t.splitlines(), []
            for i, line in enumerate(lines):
                if re.match(r"(def |[A-Z][A-Z0-9_]* *=)", line) and not (i and lines[i - 1].lstrip().startswith("#")):
                    out.append(UNRELATED.strip())
                out.append(line)
            return UNRELATED * 3 + chr(10).join(out) + chr(10)
        _edit(dst, rel, shift)


def _same_after(dst):
    got = _export(dst)
    return {n: got[n] == COMMITTED[n] for n in COMMITTED}


def test_unrelated_lines_above_every_ledgered_constant_leave_the_export_identical(tmp_path):
    _copy_repo(str(tmp_path))
    _shift_everything(str(tmp_path))
    n_shifted = sum(open(os.path.join(tmp_path, lc.rel_path(m)), encoding="utf-8").read().count(UNRELATED) for m in lc.SCAN_MODULES)
    assert n_shifted > 300, "the copy really moved the lines"
    # build_ledger() still reports the moved lines (file_line is for interactive use) ...
    prog = "from python import parameter_table as pt; print(chr(10).join(r['tag'] + '|' + r['source'] + '|' + r['file_line'] for r in pt.build_ledger()))"
    moved = subprocess.run([sys.executable, "-c", prog], cwd=str(tmp_path), capture_output=True, text=True, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    assert moved.returncode == 0, moved.stderr[-800:]
    before = {r["tag"] + "|" + r["source"]: r["file_line"] for r in pt.build_ledger()}
    after = dict(line.rsplit("|", 1) for line in moved.stdout.strip().splitlines())
    assert sum(1 for k, v in after.items() if k in before and before[k] != v and not k.split("|", 1)[1].startswith("registry")) > 100
    # ... and the committed export is still exactly what is generated
    assert _same_after(str(tmp_path)) == {"design_basis_ledger.md": True, "design_basis_ledger.csv": True}


def _mut_value(dst):
    _edit(dst, "python/fe_feed_handling.py", lambda t: t.replace("FE001_LIVE_CAPACITY_T = 1.7\n", "FE001_LIVE_CAPACITY_T = 1.8\n", 1))


def _mut_status_origin(dst):
    import json
    p = os.path.join(dst, "data", "registry_status_overlay.json")
    d = json.load(open(p, encoding="utf-8"))
    del d["entries"]["registry|FE-003|Nominal feed rate"]
    json.dump(d, open(p, "w", encoding="utf-8"), indent=1)


def _mut_consumer(dst):
    _edit(dst, "python/fe_feed_handling.py", lambda t: t.rstrip("\n") + "\n\n\ndef _extra_reader_for_the_test():\n    return FE001_LIVE_CAPACITY_T\n")


def _mut_anchor(dst):
    _edit(dst, "python/gc_gas_cleaning_chain.py", lambda t: t.replace("    efficiency = 0.95\n    outlet_mg_nm3 = inlet_mg_nm3 * (1.0 - efficiency)\n", "    collection_eff = 0.95\n    outlet_mg_nm3 = inlet_mg_nm3 * (1.0 - collection_eff)\n", 1)
                                                         .replace('"efficiency": efficiency, "outlet_mg_nm3"', '"efficiency": collection_eff, "outlet_mg_nm3"', 1))


@pytest.mark.parametrize("mutate,what", [(_mut_value, "value"), (_mut_status_origin, "status and origin"), (_mut_consumer, "consumer"), (_mut_anchor, "anchor")])
def test_a_changed_value_status_origin_consumer_or_anchor_changes_the_export(tmp_path, mutate, what):
    _copy_repo(str(tmp_path))
    mutate(str(tmp_path))
    same = _same_after(str(tmp_path))
    assert same != {"design_basis_ledger.md": True, "design_basis_ledger.csv": True}, f"a changed {what} must make the export differ from the committed files"


# ------------------------------------------------------------------ (E) export freshness, offline

def _export_module():
    spec = importlib.util.spec_from_file_location("export_design_basis_ledger", os.path.join(ROOT, "scripts", "export_design_basis_ledger.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_committed_ledger_files_equal_a_fresh_generation(built):
    ex = _export_module()
    ledger, items, exceptions, _ = built
    for path, fresh in ((ex.MD_PATH, ex.render_md(ledger, items, exceptions)), (ex.CSV_PATH, ex.render_csv(ledger))):
        with open(path, encoding="utf-8") as f:
            assert f.read() == fresh, f"{os.path.relpath(path, ROOT)} is stale: run python scripts/export_design_basis_ledger.py"


def test_the_csv_has_one_row_per_ledger_row_and_the_ledger_columns(built):
    import csv
    ex = _export_module()
    rows = list(csv.reader(ex.render_csv(built[0]).splitlines()))
    assert tuple(rows[0]) == ex.EXPORT_COLUMNS and "file_line" not in rows[0] and "anchor" in rows[0] and len(rows) == 1 + len(built[0])


def test_no_database_or_network_call(fake, monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("network access attempted")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    with patched_supabase(fake):
        lcons.engine_input_readers(lambda: t1.build_live_snapshot(2))
    pt.build_ledger()
    lc.scan()
    assert [c for c in fake.calls if c[0] != "select"] == []


def test_the_new_modules_hold_no_database_network_or_secret_code():
    import ast
    for rel in ("python/ledger_coverage.py", "python/ledger_rows.py", "python/ledger_consumers.py", "scripts/export_design_basis_ledger.py"):
        tree = ast.parse(open(os.path.join(ROOT, rel), encoding="utf-8").read())
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        imports = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names} | {(n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        assert not ({"supabase", "requests", "urllib", "http", "socket", "streamlit"} & imports), rel
        assert "secrets" not in names and "create_client" not in names, rel
