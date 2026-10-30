"""Provenance phase 2: the owner's origin answers decide the status of a registry row; there is NO default to Confirmed; the app shows the evidence honestly.

Guards: no code path turns a missing status into Confirmed (behaviour AND a scan of the sources); each origin maps to its documented status; a corrupted overlay (DOK-ING without a
source, a status that does not match its origin, an unknown origin, malformed JSON) can never produce Confirmed; the counts equal the checker's table (Confirmed 16 rows / 13 slots,
Unverified 737 rows); the app's cards and captions follow the resolved status (GA-008 / GA-009 capacity read 'Unverified (registry)' unless the overlay says otherwise); the parameter
table and the datasheet resolve every shared row identically; the snapshot is unchanged (120 keys, none about status); no database or network; this task's commits touch no engine,
snapshot, runtime, workflow or registry file.

ORDER: the AppTest-based test is first on purpose (in one process an AppTest run after a bare-mode runpy of app.py fails with a Streamlit form-context error; tests/test_app_smoke.py ->
tests/test_tab2_counts.py already follow this order)."""
import json
import os
import re
import runpy
import subprocess
import urllib.error
from unittest import mock

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from _fakes import FakeSupabase, patched_supabase
from python import equipment_datasheet as eds
from python import equipment_engineering_estimates as eee
from python import equipment_rfi_fills as erf
from python import parameter_table as pt
from python import provenance_overlay as po
from python import registry_status as rs
from python import tab1_integration as t1

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP = os.path.join(ROOT, "app.py")
OVERLAY = os.path.join(ROOT, "data", "registry_status_overlay.json")
CSV = os.path.join(ROOT, "data", "provenance", "provenance_worksheet_filled.csv")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "sample_snapshot.json")
BLOCKED = urllib.error.URLError("network blocked in tests")


def _rows():
    with open(FIXTURE, encoding="utf-8") as h:
        doc = json.load(h)
    return [{"equipment_id": e["key"][0], "category": e["key"][1], "entry": e["entry"], "cycle": 1, "published_at": "2026-09-10T00:04:00Z"} for e in doc["entries"]]


def _app_test():
    st.cache_data.clear()
    fake = FakeSupabase({"plant_state_current": _rows()})
    with patched_supabase(fake), mock.patch("urllib.request.urlopen", side_effect=BLOCKED):
        at = AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception, [str(e.value)[:300] for e in at.exception]
    assert [c for c in fake.calls if c[0] != "select"] == [], "the app wrote to the (fake) database"
    return at


def _texts(at):
    return " ".join(str(c.value) for c in at.caption) + " " + " ".join(str(m.value) for m in at.markdown)


def _resolved():
    return eds.resolve_datasheets(eee.apply_estimates(erf.apply_rfi_fills(eds.build_all_datasheets())))


# ---------------------------------------------------------------- the rendered app (first: see the ORDER note)

def test_the_rendered_app_shows_the_new_counts_and_the_captions_follow_the_resolved_status(monkeypatch, tmp_path):
    s = eds.summarize(_resolved())
    assert (s["confirmed_category_slots"], s["estimated_category_slots"], s["missing_category_slots"]) == (13, 297, 236)

    at = _app_test()
    metrics = {}
    for m in at.metric:
        metrics.setdefault(m.label, []).append(m.value)
    assert metrics["Confirmed (DOK-ING-sourced) slots"] == ["13 / 546"] and metrics["Not-confirmed slots"] == ["297 / 546"]
    assert str(s["evidence_label_slots"]["Unverified (registry)"]) in metrics["Unverified (registry)"]
    text = _texts(at)
    assert "Confirmed means a DOK-ING source is cited; unverified rows have no stated origin yet." in text
    assert "vs GA-008's Unverified (registry) design capacity 3 kg/h" in text and "vs GA-009's Unverified (registry) design capacity 5 kg/h" in text
    assert "vs GA-008's Confirmed design capacity" not in text and "vs GA-009's Confirmed design capacity" not in text

    # the same app with an overlay that cites a DOK-ING source for GA-008 only: that caption (and only that one) reads Confirmed
    doc = json.load(open(OVERLAY, encoding="utf-8"))
    doc["entries"][rs.row_id("registry", "GA-008", "Design capacity")] = {"origin": "DOK-ING", "status": "Confirmed", "source": "DOK-ING e-mail 2026-10-30 (test)", "note": ""}
    alt = tmp_path / "overlay.json"
    alt.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(rs, "OVERLAY_PATH", str(alt))
    text = _texts(_app_test())
    assert "vs GA-008's Confirmed design capacity 3 kg/h" in text and "vs GA-009's Unverified (registry) design capacity 5 kg/h" in text


# ---------------------------------------------------------------- no default to Confirmed

def test_no_code_path_maps_a_missing_status_to_confirmed():
    assert rs.resolve_row("registry", "FE-001", {"parameter": "Total hopper capacity", "value": "2"}, {})["status"] == rs.STATUS_UNVERIFIED
    assert rs.resolve_row("registry", "FE-001", {"parameter": "x", "value": "1", "status": "Confirmed"}, {})["status"] == rs.STATUS_UNVERIFIED, "an explicit Confirmed with no citation is not honoured"
    assert eds.slot_status([{"parameter": "x", "value": "1"}]) == eds.STATUS_ESTIMATE
    assert eds.slot_status([{"parameter": "x", "value": "1", "status": "Confirmed"}]) == eds.STATUS_ESTIMATE, "Confirmed without a cited source does not make a slot Confirmed"
    assert eds.slot_status([{"parameter": "x", "value": "1", "status": "Confirmed", "status_source": "DOK-ING e-mail"}]) == eds.STATUS_CONFIRMED
    raw = eee.apply_estimates(erf.apply_rfi_fills(eds.build_all_datasheets()))                    # never resolved: nothing may count as Confirmed
    assert eds.summarize(raw)["confirmed_category_slots"] == 0
    assert eds.summarize()["confirmed_category_slots"] >= 0 and eds.summarize(ids=["GA-001"])["total_category_slots"] == 6


def test_no_source_file_defaults_a_missing_status_to_confirmed():
    pat = re.compile(r"""\.get\(\s*["']status["']\s*,\s*(?:[\w.]*STATUS_CONFIRMED|["']Confirmed["'])\s*\)""")
    offenders = []
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "outputs", "tests", ".venv", "venv", "node_modules")]
        for name in files:
            if name.endswith(".py"):
                rel = os.path.relpath(os.path.join(base, name), ROOT).replace(os.sep, "/")
                text = open(os.path.join(base, name), encoding="utf-8").read()
                offenders += [(rel, text[:m.start()].count("\n") + 1) for m in pat.finditer(text)]
    # the ONE allowed occurrence is the documented comparison with the old behaviour (provenance_overlay._legacy_default_counts)
    assert [o[0] for o in offenders] == ["python/provenance_overlay.py"], offenders
    src = open(os.path.join(ROOT, "python", "provenance_overlay.py"), encoding="utf-8").read().splitlines()
    start = max(i for i in range(offenders[0][1]) if src[i].startswith("def "))
    assert src[start].startswith("def _legacy_default_counts"), src[start]


@pytest.mark.parametrize("origin,status", [("DOK-ING", "Confirmed"), ("SIMILAR_PLANT", "Estimated"), ("ASSUMED", "Assumed"), ("CALCULATED", "Calculated")])
def test_each_origin_maps_to_its_documented_status(origin, status):
    assert rs.ORIGIN_TO_STATUS[origin] == status == po.ORIGIN_TO_STATUS[origin]
    entry = {"origin": origin, "status": status, "source": "a cited source", "note": "a reason"}
    res = rs.resolve_row("registry", "FE-001", {"parameter": "Total hopper capacity", "value": "2"}, {rs.row_id("registry", "FE-001", "Total hopper capacity"): entry})
    assert res["status"] == status and res["origin"] == origin


def test_unknown_and_blank_origins_stay_unverified():
    rid = rs.row_id("registry", "FE-001", "Total hopper capacity")
    for origin in ("UNKNOWN", "", None, "MAYBE"):
        res = rs.resolve_row("registry", "FE-001", {"parameter": "Total hopper capacity", "value": "2"}, {rid: {"origin": origin, "status": "Assumed", "source": "s", "note": "n"}})
        assert res["status"] == rs.STATUS_UNVERIFIED, origin
    assert "UNKNOWN" not in rs.ORIGIN_TO_STATUS


def test_a_corrupted_overlay_can_never_make_a_row_confirmed(tmp_path):
    rid = rs.row_id("registry", "FE-001", "Total hopper capacity")
    row = {"parameter": "Total hopper capacity", "value": "2"}
    bad_entries = [{"origin": "DOK-ING", "status": "Confirmed", "source": "", "note": ""},                 # no citable source
                   {"origin": "DOK-ING", "status": "Confirmed", "source": "   ", "note": ""},
                   {"origin": "ASSUMED", "status": "Confirmed", "source": "x", "note": "r"},                # status does not match the origin
                   {"origin": "SIMILAR_PLANT", "status": "Confirmed", "source": "x", "note": ""},
                   {"origin": "", "status": "Confirmed", "source": "x", "note": ""},                        # blank origin is not DOK-ING
                   {"status": "Confirmed", "source": "x"},
                   "Confirmed", None, 7]
    for e in bad_entries:
        assert rs.resolve_row("registry", "FE-001", row, {rid: e})["status"] == rs.STATUS_UNVERIFIED, e
    doc = {"header": {"format": 1}, "entries": {rid: bad_entries[0], "registry|FE-001|Number of hoppers": {"origin": "ASSUMED", "status": "Assumed", "source": "", "note": "ok"}}}
    p = tmp_path / "o.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    entries, header = rs.load_overlay(str(p))
    assert set(entries) == {"registry|FE-001|Number of hoppers"} and header["n_ignored"] == 1
    for text in ("{not json", json.dumps({"header": {}}), json.dumps({"entries": [1]})):
        p.write_text(text, encoding="utf-8")
        assert rs.load_overlay(str(p))[0] == {} and "error" in rs.load_overlay(str(p))[1]
    assert rs.load_overlay(str(tmp_path / "missing.json"))[0] == {}
    # end to end: with a corrupted overlay nothing is Confirmed
    p.write_text(json.dumps({"header": {}, "entries": {rs.row_id("registry", "HB-006", "H₂ purity (design)"): bad_entries[0]}}), encoding="utf-8")
    ds = eds.resolve_datasheets(eee.apply_estimates(erf.apply_rfi_fills(eds.build_all_datasheets())), rs.load_overlay(str(p))[0])
    assert eds.summarize(ds)["confirmed_category_slots"] == 0


# ---------------------------------------------------------------- counts

def test_the_counts_equal_the_checkers_would_be_table_and_the_committed_overlay():
    s = eds.summarize(_resolved())
    assert (s["confirmed_category_slots"], s["estimated_category_slots"], s["missing_category_slots"], s["total_category_slots"]) == (13, 297, 236, 546)
    rows = s["evidence_label_rows"]
    assert rows == {"Confirmed": 16, "Estimated (literature-informed)": 1, "Assumed": 10, "Calculated": 2, "Unverified (registry)": 737, eds.STATUS_ESTIMATE: 48}
    entries = po.load_worksheet(CSV)
    rep = po.validate(entries)
    assert rep["valid"] and rep["counts_by_origin"] == {"DOK-ING": 16, "SIMILAR_PLANT": 1, "ASSUMED": 10, "CALCULATED": 2, "UNKNOWN": 4, "(blank)": 782}
    eff = po.effect(po.to_overlay(rep["valid_rows"]))
    assert eff["today"] == eff["would_be"], "the committed overlay IS the committed worksheet"
    assert eff["today"]["rows"]["Confirmed"] == 16 and eff["today"]["slots"]["Confirmed"] == 13 and eff["today"]["rows"][po.UNVERIFIED] == 737
    assert eff["before_phase2_default"]["rows"]["Confirmed"] == 766 and eff["before_phase2_default"]["slots"]["Confirmed"] == 262


def test_the_committed_overlay_is_exactly_what_the_committed_worksheet_generates():
    doc = json.load(open(OVERLAY, encoding="utf-8"))
    head = doc["header"]
    assert head["source_file"] == "provenance_worksheet_filled.csv" and head["source_sha256"] == po.sha256_lf(CSV) and head["n_entries"] == len(doc["entries"]) == 29
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", head["generated_at"])
    rep = po.validate(po.load_worksheet(CSV))
    assert doc["entries"] == dict(sorted(po.to_overlay(rep["valid_rows"]).items()))
    assert rs.load_overlay()[1]["n_ignored"] == 0, "every committed entry satisfies its own rule"


def test_the_four_unknown_rows_are_unverified_and_named():
    rows = {r["row_id"]: r for r in po.load_worksheet(CSV)}
    unknown = sorted(rid for rid, r in rows.items() if r["origin"].upper() == "UNKNOWN")
    assert unknown == ["registry|GA-001|Design pressure", "registry|GA-001|Residence time (design)", "registry|GA-004|Air preheat temperature", "registry|GA-004|Steam temperature (design)"]
    res = _resolved()
    for rid in unknown:
        _, item, param = rid.split("|")
        row = next(r for rows_ in res[item]["datasheet"].values() for r in rows_ if r["parameter"] == param)
        assert row["status"] == rs.STATUS_UNVERIFIED


# ---------------------------------------------------------------- one resolver for the table and the datasheet

def test_the_parameter_table_and_the_datasheet_resolve_every_shared_row_identically():
    res = _resolved()
    shared = 0
    for r in pt.build_table():
        if r["overridable_via"] != pt.VIA_REGISTRY:
            continue
        m = re.fullmatch(r"registry (\S+) '(.+)'", r["source"])
        item, param = m.group(1), m.group(2)
        row = next(x for rows_ in res[item]["datasheet"].values() for x in rows_ if x["parameter"] == param)
        assert r["status"] == row["status"], (r["tag"], r["status"], row["status"])
        shared += 1
    assert shared == 6
    ash = next(r for r in pt.build_table() if r["tag"] == "GA-001.ash_fraction")
    ga005 = next(x for rows_ in res["GA-005"]["datasheet"].values() for x in rows_ if x["parameter"] == "Ash discharge rate (design)")
    assert ash["status"] == ga005["status"]
    assert not [r for r in pt.build_table() if r["status"] == "Confirmed"], "no table row is Confirmed: no parameter in it has a DOK-ING source in the worksheet"


# ---------------------------------------------------------------- the engine and the snapshot are unchanged

def test_the_snapshot_keys_are_unchanged_and_say_nothing_about_status(monkeypatch):
    fake = FakeSupabase()
    with patched_supabase(fake):
        snap, _state, _engine = t1.build_live_snapshot(2)
    assert len(snap) == 120 and all(isinstance(k, tuple) and len(k) == 2 for k in snap)
    assert not [k for k in snap if re.search(r"overlay|provenance|registry_status|unverified", " ".join(k), re.I)]
    assert fake.calls == []


def test_nothing_in_the_engine_or_runtime_imports_the_resolver():
    for rel in ("python/simulation_engine.py", "python/shared_plant_state.py", "python/tab1_integration.py", "python/dynamics.py", "python/ga001_gasifier_model.py",
                "python/plant_status.py", "scripts/run_continuous_cycle.py"):
        text = open(os.path.join(ROOT, rel), encoding="utf-8").read()
        assert "registry_status" not in text and "equipment_datasheet" not in re.sub(r"#.*|\"\"\"[\s\S]*?\"\"\"", "", text), rel


def test_this_tasks_commits_touch_no_engine_snapshot_runtime_workflow_or_registry_file():
    """Scoped to this task's commits (messages start with 'Provenance apply'). Skipped when git or origin/main is unavailable."""
    try:
        subprocess.run(["git", "rev-parse", "--verify", "origin/main"], cwd=ROOT, capture_output=True, check=True)
        names = subprocess.run(["git", "log", "origin/main..HEAD", "--grep=^Provenance apply", "--name-only", "--format="], cwd=ROOT, capture_output=True, text=True,
                               check=True).stdout.split()
    except Exception:                                                   # noqa: BLE001
        pytest.skip("git history not available")
    forbidden = {"python/simulation_engine.py", "python/shared_plant_state.py", "python/tab1_integration.py", "python/dynamics.py", "python/ga001_gasifier_model.py",
                 "python/plant_status.py", "python/ui_transient_tab.py", "scripts/run_continuous_cycle.py", "requirements.txt", "data/equipment_registry.json"}
    assert not (set(names) & forbidden) and not [n for n in names if n.startswith(".github/")], sorted(set(names) & forbidden)
    blob = subprocess.run(["git", "rev-parse", "HEAD:data/equipment_registry.json"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    origin = subprocess.run(["git", "rev-parse", "origin/main:data/equipment_registry.json"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    assert blob == origin, "the registry JSON is byte-identical to origin/main"


def test_no_database_or_network_call_in_the_resolver_modules():
    for rel in ("python/registry_status.py", "scripts/export_provenance_csv.py"):
        code = "\n".join(line for line in open(os.path.join(ROOT, rel), encoding="utf-8").read().splitlines() if not line.lstrip().startswith("#"))
        for forbidden in (r"\bimport requests\b", r"\burllib\b", r"\bimport supabase\b", r"\bcreate_client\b", r"\.upsert\(", r"\.table\(", r"\.execute\("):
            assert not re.search(forbidden, code), (rel, forbidden)


def test_the_export_script_round_trips_a_small_xlsx(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    import importlib.util
    spec = importlib.util.spec_from_file_location("export_provenance_csv", os.path.join(ROOT, "scripts", "export_provenance_csv.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Provenance"
    ws.append(mod.COLUMNS)
    ws.append(["registry|FE-001|Total hopper capacity", 1, "FE", "FE-001", "Total hopper capacity", "2", "t", "E2", "=looks like a formula", "", "ASSUMED", "", "reason"])
    ws["I2"].data_type = "s"
    p = tmp_path / "w.xlsx"
    wb.save(str(p))
    out = tmp_path / "w.csv"
    rows = mod.export(str(p), str(out))
    back = po.load_worksheet(str(out))
    assert len(rows) == len(back) == 1 and back[0]["origin"] == "ASSUMED" and back[0]["audit_evidence"].startswith("=looks like")
    assert b"\r\n" not in out.read_bytes(), "LF line endings, so the SHA-256 is the same on every platform"
