"""Provenance worksheet (phase 1): generator, validator, overlay, checker. NOTHING is applied and nothing is wired.

Guards: the worksheet has one row per registry / fill row (815) and prefills only what the audit proved (E1); the validator rejects Confirmed without a DOK-ING source, a similar-plant
origin without a source, bad origins, duplicate and unknown row ids, and reports a changed value as a conflict that never reaches the overlay; the documented origin->status mapping is
the code's; a synthetic filled sheet gives the expected row- and slot-level counts; the generator leaves the registry byte-identical; no database / network; no engine, app or datasheet
file imports the module; this task's commits touch no existing file except CLAUDE.md. Offline: counting fake store."""
import copy
import hashlib
import importlib
import importlib.util
import os
import re
import subprocess
import sys

import pytest

from _fakes import FakeSupabase, patched_supabase
from python import equipment_datasheet as eds
from python import equipment_engineering_estimates as eee
from python import equipment_rfi_fills as erf

po = importlib.import_module("python.provenance_overlay")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REGISTRY = os.path.join(ROOT, "data", "equipment_registry.json")
OVERLAY_DEFAULT = os.path.join(ROOT, "data", "registry_status_overlay.json")
GEN = os.path.join(ROOT, "scripts", "make_provenance_worksheet.py")
CHK = os.path.join(ROOT, "scripts", "check_provenance_worksheet.py")
# PROVENANCE PHASE 2 (deliberate edit): scripts/export_provenance_csv.py is a new member of this family (it loads the module by name), so the "nobody else imports it" scan must allow it.
OWN = {"python/provenance_overlay.py", "scripts/make_provenance_worksheet.py", "scripts/check_provenance_worksheet.py", "scripts/export_provenance_csv.py", "tests/test_provenance_overlay.py",
       "tests/test_apply_provenance.py"}      # the phase 2 tests belong to the family too (deliberate edit: they import the module to check the committed overlay)


def _sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def fake():
    return FakeSupabase()


@pytest.fixture(scope="module")
def gen():
    return _load("make_provenance_worksheet", GEN)


@pytest.fixture(scope="module")
def chk():
    return _load("check_provenance_worksheet", CHK)


@pytest.fixture(scope="module")
def sheet(gen, fake):
    before = _sha(REGISTRY)
    with patched_supabase(fake):
        rows = gen.build_worksheet_rows()
    assert _sha(REGISTRY) == before
    return rows


@pytest.fixture(scope="module")
def universe():
    return po.row_universe()


def as_sheet(rows):
    """What a CSV round trip gives the loader: text cells only."""
    return [{c: ("" if r[c] is None else str(r[c])) for c in ("row_id", "value", "origin", "source", "note")} for r in rows]


# ---------------------------------------------------------------- the worksheet

def test_worksheet_has_one_row_per_registry_and_fill_row(sheet, universe):
    assert len(sheet) == 815 == len(universe)
    assert [r["row_id"] for r in sheet] and len({r["row_id"] for r in sheet}) == 815
    assert {r["row_id"] for r in sheet} == {u["row_id"] for u in universe}
    assert [r["priority"] for r in sheet] == sorted(r["priority"] for r in sheet), "most important first"
    assert {"registry": 757, "RFI_FILLS": 10, "ESTIMATE_FILLS": 48} == {k: sum(1 for u in universe if u["source_kind"] == k) for k in ("registry", "RFI_FILLS", "ESTIMATE_FILLS")}


def test_only_the_audit_proven_e1_rows_are_prefilled_and_match_the_audit(sheet, gen):
    audit = gen._load_audit()
    e1 = {po.row_id(r["source"], r["item_id"], r["parameter"]): r for r in audit.build_rows() if r["class"] == "E1"}
    prefilled = {r["row_id"]: r for r in sheet if r["origin"]}
    assert set(prefilled) == set(e1) and len(e1) == 16
    for rid, r in prefilled.items():
        assert r["origin"] == po.ORIGIN_DOKING and r["audit_class"] == "E1"
        assert e1[rid]["evidence_file_line"] in r["source"], rid
        assert e1[rid]["evidence_quote"] in r["audit_evidence"]
        assert r["proposed_status_from_audit"] == "Confirmed"


def test_e4_owner_cells_are_blank_and_e2_e3_show_their_remark_without_a_guessed_origin(sheet):
    e4 = [r for r in sheet if r["audit_class"] == "E4"]
    assert len(e4) == 690 and all(r["origin"] == r["source"] == r["note"] == "" and r["audit_evidence"] == "" and r["proposed_status_from_audit"] == "" for r in e4)
    e23 = [r for r in sheet if r["audit_class"] in ("E2", "E3")]
    assert len(e23) == 60 and all(r["origin"] == "" and r["audit_evidence"] for r in e23)
    assert all(r["proposed_status_from_audit"] == "" for r in e23 if r["audit_class"] == "E2")
    assert all(r["origin"] == "" for r in sheet if r["audit_class"] not in ("E1",))


def test_the_priority_one_list_has_the_rows_the_task_names(sheet):
    top = {(r["item"], r["field"]) for r in sheet if r["priority"] == 1}
    for key in (("GA-001", "Operating temperature (typical)"), ("GA-003", "Primary air flow rate (design)"), ("GA-003", "Air-to-fuel equivalence ratio (ER)"), ("GA-004", "Air preheat temperature"),
                ("GA-005", "Ash discharge rate (design)"), ("GA-008", "Design capacity"), ("HB-007", "H₂ recovery rate (design)"), ("HB-008", "Adsorption pressure (design)"),
                ("SA-001", "Expected H₂ concentration"), ("SA-005", "Expected N₂ concentration")):
        assert key in top, key
    assert 30 <= len(top) <= 70


def test_the_generator_leaves_the_registry_and_the_committed_overlay_byte_identical(gen, sheet, tmp_path):
    # PROVENANCE PHASE 2 (deliberate edit; was `..._and_writes_no_overlay`): data/registry_status_overlay.json now exists on purpose, so "does not exist" became "not touched".
    before, overlay_before = _sha(REGISTRY), _sha(OVERLAY_DEFAULT)
    gen.write_csv(sheet, str(tmp_path / "w.csv"))
    gen.write_xlsx(sheet, str(tmp_path / "w.xlsx"))
    assert _sha(REGISTRY) == before
    assert _sha(OVERLAY_DEFAULT) == overlay_before
    back = po.load_worksheet(str(tmp_path / "w.csv"))
    assert len(back) == 815 and [r["row_id"] for r in back] == [r["row_id"] for r in sheet]


def test_the_csv_round_trip_keeps_values_and_the_xlsx_is_a_usable_form(gen, sheet, tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    p = tmp_path / "w.xlsx"
    ev = dict(sheet[0], audit_evidence="=1+1 looks like a formula", value="=2")
    assert gen.write_xlsx([ev] + sheet[1:], str(p))
    wb = openpyxl.load_workbook(str(p))
    ws = wb["Provenance"]
    assert wb.sheetnames == ["Provenance", "How to fill this", "Top rows"] and ws.freeze_panes == "A2" and ws.max_row == 816
    dv = ws.data_validations.dataValidation
    assert len(dv) == 1 and dv[0].type == "list" and all(o in dv[0].formula1 for o in po.ORIGINS)
    assert not [c.coordinate for row in ws.iter_rows() for c in row if c.data_type == "f"], "text starting with '=' must stay text"
    rows = po.load_worksheet(str(p))
    assert len(rows) == 815 and rows[0]["audit_evidence"].startswith("=1+1")


def test_without_openpyxl_only_the_csv_is_written(gen, sheet, tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "openpyxl", None)
    assert gen.write_xlsx(sheet, str(tmp_path / "w.xlsx")) is False and not (tmp_path / "w.xlsx").exists()
    with pytest.raises(RuntimeError):
        po.load_worksheet(str(tmp_path / "x.xlsx"))


# ---------------------------------------------------------------- the validator

def _rows_with(sheet, **fills):
    """as_sheet rows with the owner cells set for the given row_id -> (origin, source, note)."""
    rows = as_sheet(sheet)
    index = {r["row_id"]: r for r in rows}
    for rid, (origin, source, note) in fills.items():
        index[rid].update(origin=origin, source=source, note=note)
    return rows


@pytest.fixture(scope="module")
def e4_ids(sheet):
    return [r["row_id"] for r in sheet if r["audit_class"] == "E4"]


def _errors(rep):
    return {e["kind"] for e in rep["errors"]}


def test_confirmed_without_a_dokink_source_is_rejected(sheet, universe, e4_ids):
    rep = po.validate(_rows_with(sheet, **{e4_ids[0]: ("DOK-ING", "", "")}), universe)
    assert "missing_source" in _errors(rep) and not rep["valid"]
    assert "Confirmed needs a citable DOK-ING source" in rep["errors"][0]["message"]
    assert e4_ids[0] not in po.to_overlay(rep["valid_rows"])
    ok = po.validate(_rows_with(sheet, **{e4_ids[0]: ("DOK-ING", "DOK-ING e-mail 2026-10-12", "")}), universe)
    assert ok["valid"] and po.to_overlay(ok["valid_rows"])[e4_ids[0]]["status"] == "Confirmed"


def test_similar_plant_without_a_source_is_rejected_and_never_maps_to_confirmed(sheet, universe, e4_ids):
    rep = po.validate(_rows_with(sheet, **{e4_ids[0]: ("SIMILAR_PLANT", "", "")}), universe)
    assert "missing_source" in _errors(rep)
    ok = po.validate(_rows_with(sheet, **{e4_ids[0]: ("SIMILAR_PLANT", "Basu 2010, Table 5", "")}), universe)
    assert po.to_overlay(ok["valid_rows"])[e4_ids[0]]["status"] == "Estimated"


def test_assumed_needs_a_reason_and_calculated_needs_a_formula(sheet, universe, e4_ids):
    rep = po.validate(_rows_with(sheet, **{e4_ids[0]: ("ASSUMED", "", ""), e4_ids[1]: ("CALCULATED", "", "n")}), universe)
    assert _errors(rep) == {"missing_note", "missing_source"}
    ok = po.validate(_rows_with(sheet, **{e4_ids[0]: ("ASSUMED", "", "design margin"), e4_ids[1]: ("CALCULATED", "python/x.py:12", "")}), universe)
    ov = po.to_overlay(ok["valid_rows"])
    assert ok["valid"] and (ov[e4_ids[0]]["status"], ov[e4_ids[1]]["status"]) == ("Assumed", "Calculated")


def test_bad_origin_duplicate_and_unknown_row_ids_are_rejected(sheet, universe, e4_ids):
    rows = _rows_with(sheet, **{e4_ids[0]: ("CONFIRMED", "x", "")})
    rows.append(dict(rows[5]))                                                       # duplicate of an existing row_id
    rows.append({"row_id": "registry|XX-999|nothing", "value": "1", "origin": "ASSUMED", "source": "", "note": "r"})
    rep = po.validate(rows, universe)
    assert _errors(rep) == {"bad_origin", "duplicate_row_id", "unknown_row_id"}
    assert e4_ids[0] not in po.to_overlay(rep["valid_rows"])


def test_a_blank_origin_is_a_gap_never_dokink_and_unknown_stays_unverified(sheet, universe, e4_ids):
    rep = po.validate(_rows_with(sheet, **{e4_ids[0]: ("UNKNOWN", "", ""), e4_ids[1]: ("", "DOK-ING e-mail", "")}), universe)
    assert rep["valid"] and po.to_overlay(rep["valid_rows"]).keys() == {r["row_id"] for r in sheet if r["origin"]}
    assert e4_ids[0] in rep["gaps"] and e4_ids[1] in rep["gaps"]
    assert po.validate(_rows_with(sheet), universe)["counts_by_origin"]["DOK-ING"] == 16


def test_a_changed_value_is_a_conflict_and_is_not_applied(sheet, universe, e4_ids):
    rows = _rows_with(sheet, **{e4_ids[0]: ("ASSUMED", "", "reason")})
    next(r for r in rows if r["row_id"] == e4_ids[0])["value"] = "999999"
    rep = po.validate(rows, universe)
    assert [c["row_id"] for c in rep["conflicts"]] == [e4_ids[0]] and not rep["valid"]
    assert e4_ids[0] not in po.to_overlay(rep["valid_rows"]), "a conflict must not be applied"
    same = _rows_with(sheet, **{e4_ids[0]: ("ASSUMED", "", "reason")})
    v = next(r for r in same if r["row_id"] == e4_ids[0])
    v["value"] = v["value"] + ".0" if re.fullmatch(r"\d+", v["value"]) else v["value"]
    assert po.validate(same, universe)["conflicts"] == [], "60 and 60.0 are the same number"


def test_the_documented_mapping_is_the_codes():
    assert po.ORIGINS == ("DOK-ING", "SIMILAR_PLANT", "ASSUMED", "CALCULATED", "UNKNOWN")
    assert po.ORIGIN_TO_STATUS == {"DOK-ING": "Confirmed", "SIMILAR_PLANT": "Estimated", "ASSUMED": "Assumed", "CALCULATED": "Calculated"}
    assert po.UNVERIFIED == "Unverified (registry)" and "UNKNOWN" not in po.ORIGIN_TO_STATUS
    with open(os.path.join(ROOT, "docs", "provenance_worksheet.md"), encoding="utf-8") as f:
        doc = f.read()
    for origin, status in po.ORIGIN_TO_STATUS.items():
        m = re.search(r"\| `%s` \|[^|]*\| ([A-Za-z]+)[^|]*\|" % re.escape(origin), doc)
        assert m and m.group(1) == status, (origin, m and m.group(1))
    assert re.search(r"\| `UNKNOWN` / blank \|[^|]*\| stays \"Unverified \(registry\)\"", doc)
    for origin, (field, _msg) in po.REQUIRED_FIELD.items():
        assert origin in po.ORIGIN_TO_STATUS and field in ("source", "note")


# ---------------------------------------------------------------- the would-be counts

def test_the_worksheet_as_generated_gives_16_confirmed_and_750_unverified(sheet, universe):
    rep = po.validate(as_sheet(sheet), universe)
    eff = po.effect(po.to_overlay(rep["valid_rows"]))
    # PROVENANCE PHASE 2 (deliberate edit): `today` now means the committed overlay; the old default's numbers are `before_phase2_default`.
    assert eff["before_phase2_default"]["rows"]["Confirmed"] == 766 and eff["before_phase2_default"]["slots"]["Confirmed"] == 262
    assert eff["today"]["rows"]["Confirmed"] == 16 and eff["today"]["slots"]["Confirmed"] == 13 and eff["today"]["rows"][po.UNVERIFIED] == 737
    assert eff["would_be"]["rows"] == {"Confirmed": 16, "Estimated": 0, "Estimated (existing fills)": 48, "Assumed": 0, "Calculated": 0, po.UNVERIFIED: 750}
    assert eff["would_be"]["slots"]["Confirmed"] == 13 and eff["would_be"]["slots"]["Missing"] == eff["today"]["slots"]["Missing"] == 236


def test_a_synthetic_filled_sheet_gives_the_expected_counts(sheet, universe, e4_ids):
    fills = {}
    for i, rid in enumerate(e4_ids[:20]):
        fills[rid] = [("DOK-ING", "DOK-ING e-mail 2026-10-12", ""), ("SIMILAR_PLANT", "Basu 2010", ""), ("ASSUMED", "", "design margin"), ("CALCULATED", "python/x.py:1", ""),
                      ("UNKNOWN", "", "")][i % 5]
    rep = po.validate(_rows_with(sheet, **fills), universe)
    assert rep["valid"]
    ov = po.to_overlay(rep["valid_rows"])
    eff = po.effect(ov)["would_be"]
    assert eff["rows"] == {"Confirmed": 16 + 4, "Estimated": 4, "Estimated (existing fills)": 48, "Assumed": 4, "Calculated": 4, po.UNVERIFIED: 766 - (16 + 4 + 4 + 4 + 4)}   # UNKNOWN stays unverified
    assert sum(eff["rows"].values()) == 814
    # slot level, computed independently: a slot is Confirmed if any of its rows is
    ds = eee.apply_estimates(erf.apply_rfi_fills(eds.build_all_datasheets()))
    confirmed_slots = 0
    for item_id, entry in ds.items():
        for rows in entry["datasheet"].values():
            hit = False
            for r in rows:
                kind = "registry" if "source" not in r else ("ESTIMATE_FILLS" if r.get("status") == eds.STATUS_ESTIMATE else "RFI_FILLS")
                if ov.get(po.row_id(kind, item_id, r["parameter"]), {}).get("status") == "Confirmed":
                    hit = True
            confirmed_slots += hit
    assert eff["slots"]["Confirmed"] == confirmed_slots
    assert eff["slots"]["Confirmed"] + eff["slots"]["Engineering Estimate (non-Confirmed)"] + eff["slots"]["Missing"] == eff["slots"]["total"] == 546


def test_the_checker_reports_without_writing_and_refuses_to_write_an_invalid_sheet(chk, gen, sheet, tmp_path, capsys):
    good = tmp_path / "good.csv"
    gen.write_csv(sheet, str(good))
    text, ok, overlay = chk.report(str(good))
    # PROVENANCE PHASE 2 (deliberate edit): the report headings were renamed (three columns now) and the committed overlay exists, so "not written" became "byte-identical".
    overlay_before = _sha(OVERLAY_DEFAULT)
    assert ok and len(overlay) == 16 and "Counts, row level" in text and "before phase 2 (old default)" in text and "Nothing is applied by this report" in text
    assert _sha(OVERLAY_DEFAULT) == overlay_before
    bad = tmp_path / "bad.csv"
    rows = copy.deepcopy(sheet)
    rows[40]["origin"], rows[40]["source"] = "DOK-ING", ""
    gen.write_csv(rows, str(bad))
    out = tmp_path / "overlay.json"
    assert chk.main([str(bad), "--write", "--out", str(out)]) == 1 and not out.exists()
    assert chk.main([str(good), "--write", "--out", str(out)]) == 0 and out.exists()
    assert _sha(OVERLAY_DEFAULT) == overlay_before, "only `--write` with the default path may change the committed overlay, and these runs wrote to a temp path"
    capsys.readouterr()


# ---------------------------------------------------------------- offline, not wired, nothing else touched

def test_no_database_or_network_call_was_made(fake):
    assert fake.calls == [], fake.calls


def test_the_new_files_contain_no_database_network_or_scada_code():
    for rel in sorted(OWN - {"tests/test_provenance_overlay.py"}):
        with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
            code = "\n".join(line for line in f.read().splitlines() if not line.lstrip().startswith("#"))
        for forbidden in (r"\bimport requests\b", r"\burllib\b", r"\bimport supabase\b", r"\bcreate_client\b", r"\.upsert\(", r"\.table\(", r"\.execute\("):
            assert not re.search(forbidden, code), (rel, forbidden)


def test_no_engine_app_or_datasheet_file_imports_the_overlay_module():
    offenders = []
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "outputs", ".venv", "venv", "node_modules")]
        for name in files:
            rel = os.path.relpath(os.path.join(base, name), ROOT).replace(os.sep, "/")
            if not name.endswith(".py") or rel in OWN:
                continue
            with open(os.path.join(base, name), encoding="utf-8") as f:
                src = f.read()
            if re.search(r"provenance_overlay", src):
                offenders.append(rel)
    assert offenders == [], offenders


def test_no_default_to_confirmed_and_the_registry_json_is_untouched():
    # PROVENANCE PHASE 2 (deliberate edit; was `..._the_default_status_and_the_registry_are_not_touched`, which pinned the default phase 2 removes): the default is gone, the registry
    # JSON still carries no status key (status lives in the overlay, never in the registry file).
    assert eds.slot_status([{"parameter": "x", "value": "1"}]) != eds.STATUS_CONFIRMED, "a row without a status must not count as Confirmed"
    with open(REGISTRY, encoding="utf-8") as f:
        assert '"status"' not in f.read()


def test_this_tasks_commits_touch_only_new_files_and_claude_md():
    """Scoped to this task's commits (messages start with 'Provenance worksheet'). Skipped when git or origin/main is unavailable."""
    try:
        subprocess.run(["git", "rev-parse", "--verify", "origin/main"], cwd=ROOT, capture_output=True, check=True)
        names = subprocess.run(["git", "log", "origin/main..HEAD", "--grep=^Provenance worksheet", "--name-only", "--format="], cwd=ROOT, capture_output=True, text=True,
                               check=True).stdout.split()
    except Exception:                                                   # noqa: BLE001
        pytest.skip("git history not available")
    allowed = OWN | {"docs/provenance_worksheet.md", "CLAUDE.md"}
    assert set(names) <= allowed, sorted(set(names) - allowed)
