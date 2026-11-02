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
import socket
import sys

import pytest

import _d2_wording
from _fakes import FakeSupabase, patched_supabase
from python import equipment_datasheet as ed
from python import ledger_consumers as lcons
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
    assert len(table) == 26, "build_table() is unchanged: its 26 rows"
    by = {(r["tag"], r["source"]): r for r in ledger}
    for r in table:
        # A3b 2.8: the ledger VIEW of GA-001.ash_fraction does not borrow GA-005's status (a discharge rate is not a mass fraction), so its status and note differ from the table row;
        # build_table() itself is untouched (tests/test_apply_provenance.py still pins it to GA-005's resolved status). Every other column of that row, and every column of every other row, is equal.
        cols = [c for c in pt.COLUMNS if not (r["tag"] == "GA-001.ash_fraction" and c in ("status", "note"))]
        assert all(by[(r["tag"], r["source"])][c] == r[c] for c in cols), r["tag"]
    ash = by[("GA-001.ash_fraction", "module constant gasifier_mass_balance.ASH_FRACTION (reused by ga001 as ASH_FRACTION)")]
    assert ash["status"] == "Assumed" and ash["status_via"] == "own" and ash["origin"] == "NOT STATED"
    assert next(x for x in table if x["tag"] == "GA-001.ash_fraction")["status"] != "Assumed", "the table row keeps its own (borrowed) status"
    assert len(ledger) == 26 + len(lr.build_rows()) == len(by)
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
    assert len(items) == 360 and len(exceptions) == 189 and len(items) - len(exceptions) == 171     # A3b 2.3: 7 HHV coefficients moved from one row to exceptions (184 -> 191); 2.4: two persisted-verdict thresholds became rows (191 -> 189, PARAMETERs 169 -> 171)


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
        assert reason in r["note"], tag
    assert by["FE-003.nominal_kg_h"]["status"] == "Confirmed" and by["FE-003.nominal_kg_h"]["status_via"] == "registry counterpart: FE-003/Nominal feed rate"
    assert by["HB-012.discharge_bar_a"]["status"] == "Confirmed" and "701 bar" not in by["HB-012.discharge_bar_a"]["note"] or "bar(a) = bar(g) + 1 bar" in by["HB-012.discharge_bar_a"]["note"]
    assert by["FE-001.default_delivery_rate_kg_h"]["status"] == "Assumed"


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
CONFIRMED_PIN = {
    "ga001_gasifier_model.py": (15, 20, 44), "ga001_energy_balance.py": (1, 0, 0), "gasifier_mass_balance.py": (2, 0, 1), "gc_gas_cleaning_chain.py": (0, 12, 85),
    "hb_wgs_psa_storage_chain.py": (2, 0, 35), "hb_remaining_chain.py": (1, 25, 72), "eu_utilities_chp.py": (6, 14, 38), "balance_audit.py": (1, 3, 5), "fe_feed_handling.py": (5, 10, 21),
    "uncertainty.py": (0, 26, 4), "reference_feeds.py": (1, 1, 2), "tab1_integration.py": (12, 4, 8),
}
PERSISTED_REGISTRY_STATED = 88      # REGISTRY-STATED mentions on a string-literal line whose text occurs in a persisted note of the live snapshot (both tail_gas_modes); see the A3b report


def test_the_confirmed_mentions_are_pinned_per_class_and_file():
    mentions = lc.confirmed_mentions()
    got = {k.split("/")[-1]: tuple(v[c] for c in lc.MENTION_CLASSES) for k, v in lc.mention_counts(mentions).items()}
    assert got == CONFIRMED_PIN, {k: (got.get(k), CONFIRMED_PIN.get(k)) for k in set(got) | set(CONFIRMED_PIN) if got.get(k) != CONFIRMED_PIN.get(k)}
    assert len(mentions) == 476 and len(lc.CONFIRMED_SCOPE) == 18
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
    assert len(ledger) == 173                                  # A3b 2.3: PLANT.hhv_correlation_coefficients is no longer a row (-1); 2.4: two verdict-threshold rows (+2)


def test_every_code_row_has_the_function_that_names_it(built):
    by = {r["tag"]: r for r in built[0]}
    assert "psa.psa_recovery" in by["HB-006.psa_K1"]["consumers"]
    assert by["GC-003.efficiency"]["consumers"] == ["gc_gas_cleaning_chain.gc003_dust"]
    assert any(c.startswith("eu_utilities_chp.eu004") for c in by["EU-004.jacket_kwth_rated"]["consumers"])


# ------------------------------------------------------------------ (F.4) the engine is unchanged

@pytest.mark.parametrize("mode,fixture_key", [("default", "default|20"), ("heat_only", "heat_only|20")])
def test_every_persisted_entry_equals_origin_main_in_both_tail_gas_modes(runs, main_snap, mode, fixture_key):
    new = _ser(runs[mode])
    old = main_snap[fixture_key]
    assert set(new) == set(old) and len(new) == 121, "same persisted keys, same count"
    new_wording = {k: v for k, v in new.items() if k.startswith(_d2_wording.ENTRIES)}
    undone = _d2_wording.undo(new)
    diffs = {k: _same(old[k], undone[k]) for k in old if k not in ("GA-001-INPUT|tail_gas_mode",) or mode == "default"}
    bad = {k: v for k, v in diffs.items() if v is not True}
    assert bad == {}, bad
    # the one deliberate text change is really there (and only in the entries that can carry it)
    text = json.dumps(new_wording)
    assert "registry '>98% removal efficiency' (Unverified (registry), not DOK-ING-confirmed)" in text
    assert "registry >90% efficiency (>d50=15um; Unverified (registry))" in text
    assert "ACTUAL/DOK-ING VALUE: Unverified (registry), not DOK-ING-confirmed -- 20 kW" in text
    assert "ACTUAL/DOK-ING VALUE: Confirmed" not in json.dumps(new)
    changed = [k for k in old if old[k] != new[k] and k != "GA-001-INPUT|tail_gas_mode"]
    assert all(k.startswith(_d2_wording.ENTRIES) for k in changed), changed


def test_the_runtime_shrink_guard_accepts_the_persisted_set(runs, main_snap):
    spec = importlib.util.spec_from_file_location("run_continuous_cycle", os.path.join(ROOT, "scripts", "run_continuous_cycle.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    stored = [tuple(k.split("|", 1)) for k in main_snap["default|20"]]
    new = list(runs["default"])
    assert set(stored) == set(new) and len(new) == 121
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

def test_the_d2_exemption_list_is_exactly_the_four_listed_phrase_pairs():
    """tests/_d2_wording.py may map back ONLY these phrases and only inside these three snapshot entries. Adding a pair or an entry fails here; a new one needs a decision."""
    assert _d2_wording.PAIRS == (
        ("registry '>98% removal efficiency' (Unverified (registry), not DOK-ING-confirmed)", "own Confirmed '>98% removal efficiency'"),
        ("registry >90% efficiency (>d50=15um; Unverified (registry))", "own Confirmed >90% efficiency (>d50=15um)"),
        ("ACTUAL/DOK-ING VALUE: Unverified (registry), not DOK-ING-confirmed -- 20 kW", "ACTUAL/DOK-ING VALUE: Confirmed -- 20 kW"),
        ("Unverified (registry), not DOK-ING-confirmed -- 20 kW, scoped to EU-004 jacket cooling only (per EU-008's own", "Confirmed -- 20 kW, scoped to EU-004 jacket cooling only (per EU-008's own"),
    )
    assert _d2_wording.ENTRIES == ("FE-002|", "GC-001|", "EU-008|")
    src = open(os.path.join(ROOT, "tests", "_d2_wording.py"), encoding="utf-8").read()
    assert src.count(".replace(") == 1, "undo() maps through PAIRS only; no second replacement rule"


def test_undo_changes_nothing_but_those_phrases():
    probe = {"FE-002|X": {"a": "Confirmed -- 30 kW", "b": ["own Confirmed text", 1.5, None], "c": {"d": "Unverified (registry)"}},
             "HB-001|X": {"a": _d2_wording.PAIRS[0][0]}}                          # outside ENTRIES: never touched
    assert _d2_wording.undo(probe) == probe
    inside = {"FE-002|X": {"a": _d2_wording.PAIRS[0][0] + " tail"}}
    assert _d2_wording.undo(inside) == {"FE-002|X": {"a": _d2_wording.PAIRS[0][1] + " tail"}}


@pytest.mark.parametrize("mode,fixture_key", [("default", "default|20"), ("heat_only", "heat_only|20")])
def test_the_persisted_text_differences_are_exactly_these_four_fields(runs, main_snap, mode, fixture_key):
    new, old = _ser(runs[mode]), main_snap[fixture_key]
    differing = set()
    for k in old:
        if k == "GA-001-INPUT|tail_gas_mode":
            continue
        r = _same(old[k], new[k])
        if r is not True:
            differing |= {(k, path) for path in r}
    assert differing == {("EU-008|RecommendedCapacityEstimate", "/confidence_note"), ("EU-008|RecommendedCapacityEstimate", "/value/actual_dokking_value"),
                         ("FE-002|TrampMetalReject", "/missing_reason"), ("GC-001|Dust", "/missing_reason")}, differing


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
