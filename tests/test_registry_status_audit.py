"""Registry status audit (scripts/run_registry_status_audit.py): read-only, offline, applies nothing.

Guards: the counts add up to the number of rows the registry and the two fill tables really hold (counted here independently from the raw JSON and the fill dicts); the audit's
assumption about the default (a row without a status is Confirmed) is the code's real default; every E1 / E2-related quote is read back from the DOK-ING file at the stated line; the registry
file is byte-identical after the script runs (and equals the committed blob); no database or network; this task's commits touch no engine, registry or existing test file."""
import hashlib
import importlib.util
import json
import os
import subprocess

import pytest

from _fakes import FakeSupabase, patched_supabase
from python import equipment_datasheet as eds
from python import equipment_engineering_estimates as eee
from python import equipment_rfi_fills as erf

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(ROOT, "scripts", "run_registry_status_audit.py")
REGISTRY = os.path.join(ROOT, "data", "equipment_registry.json")


def _sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


@pytest.fixture(scope="module")
def fake():
    return FakeSupabase()


@pytest.fixture(scope="module")
def audit():
    spec = importlib.util.spec_from_file_location("run_registry_status_audit", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def result(audit, fake, tmp_path_factory):
    before = _sha(REGISTRY)
    out = tmp_path_factory.mktemp("audit")
    with patched_supabase(fake):
        rows = audit.build_rows()
        audit.write_outputs(rows, str(out))
    return {"rows": rows, "out": out, "sha_before": before, "sha_after": _sha(REGISTRY)}


def _raw_counts():
    with open(REGISTRY, encoding="utf-8") as f:
        reg = json.load(f)
    params = [p for it in reg for p in it["parameters"]]
    rfi = [p for cats in erf.RFI_FILLS.values() for rows in cats.values() for p in rows]
    est = [p for cats in eee.ESTIMATE_FILLS.values() for rows in cats.values() for p in rows]
    return params, rfi, est


def test_the_audit_runs_offline_and_writes_its_two_outputs(result, fake):
    assert (result["out"] / "registry_status_audit.md").stat().st_size > 1000
    assert (result["out"] / "registry_status_audit.csv").stat().st_size > 1000
    assert fake.calls == [], fake.calls


def test_counts_add_up_to_the_rows_that_really_exist(audit, result):
    params, rfi, est = _raw_counts()
    c = audit.counts(result["rows"])
    assert c["rows"] == len(params) + len(rfi) + len(est) == len(result["rows"])
    assert (c["registry"], c["RFI_FILLS"], c["ESTIMATE_FILLS"]) == (len(params), len(rfi), len(est))
    assert c["explicit_confirmed"] + c["explicit_other"] + c["no_status"] == c["rows"]
    no_status_with_value = sum(1 for p in params + rfi if "status" not in p and p.get("value") is not None)
    assert c["effective_confirmed"] == no_status_with_value > 0, "every row without a status key and with a value is Confirmed by the code's default"
    assert c["E1"] + c["E2"] + c["E3"] + c["E4"] == c["effective_confirmed"]
    assert c["explicit_other"] == len(est) and all(p["status"] == eds.STATUS_ESTIMATE for p in est)
    assert c["no_value"] == sum(1 for p in params if p.get("value") is None)


def test_the_audits_default_is_the_old_default_and_the_code_no_longer_has_it():
    """PROVENANCE PHASE 2 (deliberate edit; was `..._is_the_codes_real_default`, which pinned the default this task removes): the audit script keeps describing the registry as
    it was stored, under the OLD default (STATUS_DEFAULT = Confirmed, the historical behaviour it measured); the code must no longer have that default."""
    spec = importlib.util.spec_from_file_location("a2", SCRIPT)
    a = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(a)
    assert a.STATUS_DEFAULT == eds.STATUS_CONFIRMED, "the audit still reports the registry as stored under the old default"
    assert eds.slot_status([{"parameter": "x", "value": "1"}]) != eds.STATUS_CONFIRMED, "a row without a status must NOT count as Confirmed any more"
    assert eds.slot_status([{"parameter": "x", "value": "1", "status": eds.STATUS_ESTIMATE}]) == eds.STATUS_ESTIMATE


def test_every_curated_quote_is_on_its_line_in_the_dokink_file(audit):
    with open(os.path.join(ROOT, audit.RFI_REL), encoding="utf-8") as f:
        lines = f.read().splitlines()
    ev = audit.evidence_lines()
    assert len(ev) == len(audit.E1_EVIDENCE) + len(audit.E2_RELATED)
    for rel, line, quote in ev:
        assert rel == "data/dokink_rfi_answers.md"
        assert 1 <= line <= len(lines) and quote in lines[line - 1], (line, quote, lines[line - 1] if line <= len(lines) else None)


def test_every_e1_row_carries_a_quote_that_exists_and_every_curated_key_is_a_real_row(audit, result):
    rows = {(r["source"], r["item_id"], r["parameter"]): r for r in result["rows"]}
    with open(os.path.join(ROOT, audit.RFI_REL), encoding="utf-8") as f:
        lines = f.read().splitlines()
    e1 = [r for r in result["rows"] if r["class"] == "E1"]
    assert len(e1) == len(audit.E1_EVIDENCE)
    for key in list(audit.E1_EVIDENCE) + list(audit.E2_RELATED):
        assert key in rows, f"curated evidence names a row that does not exist: {key}"
    for r in e1:
        rel, line = r["evidence_file_line"].rsplit(":", 1)
        assert r["evidence_quote"] and r["evidence_quote"] in lines[int(line) - 1], r["parameter"]
        assert r["match"] in ("literal", "unit conversion")
    for r in result["rows"]:
        if r["class"] == "E2" and r["related_line"]:
            assert r["related_line"].startswith("data/dokink_rfi_answers.md:")


def test_the_registry_file_is_unchanged_by_the_script(result):
    assert result["sha_before"] == result["sha_after"]
    try:
        committed = subprocess.run(["git", "rev-parse", "HEAD:data/equipment_registry.json"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
        current = subprocess.run(["git", "hash-object", REGISTRY], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except Exception:                                                   # noqa: BLE001
        pytest.skip("git not available")
    assert committed == current, "the registry file in the working tree differs from the committed blob"


def test_the_headline_rows_are_classified_as_the_evidence_says(result):
    by = {(r["item_id"], r["parameter"]): r for r in result["rows"] if r["source"] == "registry"}
    air = by[("GA-003", "Primary air flow rate (design)")]
    assert air["effective_status"] == "Confirmed" and air["class"] == "E3" and air["subreason"] == "not confirmed"
    assert by[("GA-003", "Air-to-fuel equivalence ratio (ER)")]["class"] == "E2"
    assert by[("GA-001", "Operating temperature (typical)")]["class"] == "E3"
    for tag in ("SA-001", "SA-002", "SA-003", "SA-004", "SA-005"):
        r = next(x for (i, p), x in by.items() if i == tag and p.startswith("Expected"))
        assert r["class"] == "E3", tag
    assert by[("HB-006", "H₂ purity (design)")]["class"] == "E1"
    assert by[("HB-012", "Discharge pressure (design)")]["class"] == "E1"
    assert by[("GA-004", "Air preheat temperature")]["class"] == "E4"


def test_estimate_fills_are_explicit_and_not_audited_as_confirmed(result):
    est = [r for r in result["rows"] if r["source"] == "ESTIMATE_FILLS"]
    assert est and all(r["effective_status"] == eds.STATUS_ESTIMATE and r["class"] == "" for r in est)


def test_cross_check_flags_the_parameter_table_rows_that_disagree(audit, result):
    cc = audit.cross_check(result["rows"])
    by = {(x["tag"], x["table_row"][:8]): x for x in cc}
    air = next(x for x in cc if x["tag"] == "GA-003.air_flow_design_Nm3_h")
    # PROVENANCE PHASE 2 (deliberate edit): the parameter table now resolves its registry rows with the owner's answers, so the disagreement this test used to pin is gone:
    # the GA-003 air row is Calculated (owner: CALCULATED), the E3 audit class and the table agree, and no tag is Confirmed in one row and Assumed in another any more.
    assert air["table_status"] == "Calculated" and air["audit_class"] == "E3" and air["agree"] is True
    assert not any(x["table_row"] == "(all rows of the tag)" for x in cc), by.keys()
    assert all(x["table_status"] != "Confirmed" or x["audit_class"] == "E1" for x in cc), "a Confirmed table row must have DOK-ING evidence"


def test_this_tasks_commits_touch_no_engine_registry_or_existing_test_file():
    """Scoped to this task's commits (messages start with 'Registry audit'). Skipped when git or origin/main is unavailable."""
    try:
        subprocess.run(["git", "rev-parse", "--verify", "origin/main"], cwd=ROOT, capture_output=True, check=True)
        names = subprocess.run(["git", "log", "origin/main..HEAD", "--grep=^Registry audit", "--name-only", "--format="], cwd=ROOT, capture_output=True, text=True,
                               check=True).stdout.split()
    except Exception:                                                   # noqa: BLE001
        pytest.skip("git history not available")
    allowed = {"scripts/run_registry_status_audit.py", "tests/test_registry_status_audit.py", "docs/registry_status_audit.md", "CLAUDE.md"}
    assert set(names) <= allowed, sorted(set(names) - allowed)
