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
    assert pt.LEDGER_COLUMNS[:len(pt.COLUMNS)] == pt.COLUMNS and pt.LEDGER_COLUMNS[len(pt.COLUMNS):] == ("ledger_id", "consumers", "upgrade_question", "origin", "source_line")
    table, ledger = pt.build_table(), pt.build_ledger()
    assert len(table) == 26, "build_table() is unchanged: its 26 rows"
    by = {(r["tag"], r["source"]): r for r in ledger}
    for r in table:
        assert all(by[(r["tag"], r["source"])][c] == r[c] for c in pt.COLUMNS), r["tag"]
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
    assert len(items) == 360 and len(exceptions) == 184 and len(items) - len(exceptions) == 176


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
    assert len(ledger) == 172


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
    assert tuple(rows[0]) == pt.LEDGER_COLUMNS and len(rows) == 1 + len(built[0])


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
