"""Data-replacement layer, step 1: parameter table, precedence rule, replay validation, residual report (scripts/run_residual_report.py).

Guards: the table follows the constants it reads (drift mutation); the precedence rule keeps its order, never lets Calculated/Estimated/Assumed replace Confirmed, lets a
Measured value replace Confirmed only with passing quality and reports both values; the replay validator flags unit mismatch, non-monotonic time, duplicates, unknown tags
and drops nothing; a SYNTHETIC dataset (the model's own snapshot plus a known offset) is recovered exactly by the residual report; nothing is wired into the engine/app; no
database or network. Offline: counting fake store."""
import copy
import importlib.util
import os
import re
import subprocess
from dataclasses import replace

import pytest

from _fakes import FakeSupabase, patched_supabase
from python import data_precedence as dp
from python import dynamics
from python import equipment_registry
from python import ga001_gasifier_model as ga001
from python import gasifier_mass_balance
from python import measurement_replay as mr
from python import parameter_table as pt
from python import plant_status as ps
from python import psa
from python import tab1_integration as t1
from python import uncertainty

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(ROOT, "scripts", "run_residual_report.py")
NEW_FILES = {"python/parameter_table.py", "python/data_precedence.py", "python/measurement_replay.py", "scripts/run_residual_report.py", "tests/test_data_layer.py"}
NEW_MODULES = ("parameter_table", "data_precedence", "measurement_replay")
c = dp.candidate


@pytest.fixture(scope="module")
def script():
    spec = importlib.util.spec_from_file_location("run_residual_report", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def fake():
    return FakeSupabase()


@pytest.fixture(scope="module")
def snapshot(fake):
    with patched_supabase(fake):
        snap, _state, _engine = t1.build_live_snapshot(2)
    return snap


@pytest.fixture(scope="module")
def table():
    return pt.build_table()


def row(table, tag, via=None):
    return next(r for r in table if r["tag"] == tag and (via is None or r["overridable_via"] == via))


# ---------------------------------------------------------------- (a) parameter table

def test_every_row_has_the_columns_a_valid_status_and_a_real_file_line(table):
    assert table, "empty table"
    for r in table:
        assert tuple(r) == pt.COLUMNS
        assert r["status"] in pt.TABLE_STATUSES
        path, line = r["file_line"].rsplit(":", 1)
        with open(os.path.join(ROOT, path), encoding="utf-8") as f:
            assert 1 <= int(line) <= len(f.read().splitlines()), r["file_line"]
        assert r["overridable_via"] in (pt.VIA_ENGINE, pt.VIA_REGISTRY, pt.VIA_DYNAMICS, pt.VIA_CODE)


def test_the_table_reads_the_user_s_parameters(table):
    tags = {r["tag"] for r in table}
    for t in ("GA-001.ER", "GA-001.carbon_conversion", "GA-001.steam_to_feed_kg_kg", "GA-001.T_gasifier_C", "GA-001.feedstock_daf_CHON", "GA-001.ash_fraction",
              "GA-001.tail_gas_mode", "GA-001.unconverted_C_to_carbon_black", "HB-006.psa_K1", "GA-001.tau_conv_s", "GA-001.tau_gas_s", "HB-009.tau_rec_s",
              "GA-003.air_flow_design_Nm3_h", "GA-003.steam_flow_design_kg_h"):
        assert t in tags, t


def test_drift_the_table_changes_when_an_underlying_constant_changes(monkeypatch, table):
    """The mutation proof: change the owning constant, the table row changes; nothing in the table is a copy."""
    base = {t: row(table, t)["value"] for t in ("GA-001.carbon_conversion", "GA-001.ash_fraction", "HB-006.psa_K1", "GA-001.tau_gas_s", "GA-001.ER", "GA-001.T_gasifier_C")}
    monkeypatch.setattr(ga001, "CARBON_CONVERSION_EFFICIENCY", 0.5)
    monkeypatch.setattr(gasifier_mass_balance, "ASH_FRACTION", 0.2)
    monkeypatch.setattr(psa, "K1", 0.5)
    monkeypatch.setattr(dynamics, "TAU_SPECS", {**dynamics.TAU_SPECS, "tau_gas": replace(dynamics.TAU_SPECS["tau_gas"], default_s=77.0)})
    monkeypatch.setitem(uncertainty.ASSUMPTIONS["air_equivalence_ratio"], "point", 0.31)
    monkeypatch.setattr(ga001, "GA001_OPERATING_TEMPERATURE_C", 800.0)
    t2 = pt.build_table()
    assert row(t2, "GA-001.carbon_conversion")["value"] == 0.5 != base["GA-001.carbon_conversion"]
    assert row(t2, "GA-001.ash_fraction")["value"] == 0.2
    assert row(t2, "HB-006.psa_K1")["value"] == 0.5
    assert row(t2, "GA-001.tau_gas_s")["value"] == 77.0
    assert row(t2, "GA-001.ER", pt.VIA_ENGINE)["value"] == 0.31
    assert row(t2, "GA-001.T_gasifier_C", pt.VIA_ENGINE)["value"] == 800.0
    assert row(t2, "GA-001.T_gasifier_C", pt.VIA_REGISTRY)["value"] == 950.0, "the registry row is read from the registry, not from the constant"


def test_drift_a_changed_range_and_a_changed_registry_row_show_up(monkeypatch, table):
    monkeypatch.setattr(ga001, "CARBON_CONVERSION_EFFICIENCY_RANGE", (0.1, 0.2))
    real = equipment_registry.load_registry()
    mutated = copy.deepcopy(real)
    for item in mutated:
        if item["id"] == "GA-003":
            for p in item["parameters"]:
                if p["parameter"] == "Primary air flow rate (design)":
                    p["value"] = "61"
    monkeypatch.setattr(equipment_registry, "load_registry", lambda: mutated)
    t2 = pt.build_table()
    r = row(t2, "GA-001.carbon_conversion")
    assert (r["range_low"], r["range_high"]) == (0.1, 0.2)
    assert row(t2, "GA-003.air_flow_design_Nm3_h")["value"] == 61.0
    assert row(table, "GA-003.air_flow_design_Nm3_h")["value"] == 60.0


def test_a_moved_source_fails_loudly_instead_of_pointing_at_a_guess():
    with pytest.raises(LookupError):
        pt._find_line("python/psa.py", r"^THIS_CONSTANT_DOES_NOT_EXIST\s*=")


def test_override_ability_is_checked_against_the_engine_not_typed(monkeypatch, table):
    assert row(table, "GA-001.ER", pt.VIA_ENGINE)["overridable_via"] == pt.VIA_ENGINE
    assert row(table, "GA-001.ash_fraction")["overridable_via"] == pt.VIA_CODE
    assert row(table, "HB-006.psa_K1")["overridable_via"] == pt.VIA_CODE
    monkeypatch.setattr(pt, "registered_engine_keys", lambda: set())
    t2 = pt.build_table()
    assert all(r["overridable_via"] != pt.VIA_ENGINE for r in t2), "with no registered input every engine-input row must turn into 'code only'"


def test_code_only_parameters_are_listed_under_their_own_heading_not_hidden(table):
    md = pt.to_markdown(table)
    head, tail = md.split("## Parameters that CANNOT be overridden without a code edit")
    for r in pt.code_only_rows(table):
        assert f"| {r['tag']} |" in tail and f"| {r['tag']} |" not in head
    assert "| GA-001.ash_fraction |" in tail and "| GA-001.ER |" in head


def test_registry_caveat_is_carried_verbatim(table):
    note = row(table, "GA-003.air_flow_design_Nm3_h")["note"]
    assert "not DOK-ING-confirmed, treat as an estimate" in note


# ---------------------------------------------------------------- (b) precedence

def test_measured_beats_confirmed_with_both_values_in_the_audit_trail():
    res = dp.resolve([c(950.0, "Confirmed", "2026-01-01T00:00:00Z", "registry"), c(930.0, "Measured", "2026-10-30T10:00:00Z", "thermocouple", quality="good")])
    assert (res["status"], res["value"]) == ("Measured", 930.0)
    assert res["override"]["kind"] == "Measured replaces Confirmed"
    assert res["override"]["measured"]["value"] == 930.0 and res["override"]["confirmed"][0]["value"] == 950.0
    assert [t["outcome"] for t in res["trail"]] == ["superseded", "winner"]
    assert res["replaced"][0]["value"] == 950.0


@pytest.mark.parametrize("lower", ["Calculated", "Estimated", "Assumed"])
def test_confirmed_is_never_replaced_by_a_lower_status_even_if_newer(lower):
    res = dp.resolve([c(950.0, "Confirmed", "2020-01-01T00:00:00Z", "doking"), c(1.0, lower, "2030-01-01T00:00:00Z", "model")])
    assert (res["status"], res["value"], res["override"]) == ("Confirmed", 950.0, None)


@pytest.mark.parametrize("quality,flags", [("suspect", []), ("bad", []), (None, []), ("good", ["unit_mismatch"]), ("good", ["duplicate"]), ("good", ["non_monotonic_time"]),
                                           ("good", ["physically_impossible"])])
def test_a_measured_value_that_fails_quality_does_not_override_and_is_named(quality, flags):
    res = dp.resolve([c(950.0, "Confirmed", "2026-01-01T00:00:00Z", "registry"), c(1.0, "Measured", "2026-10-30T00:00:00Z", "plc", quality=quality, flags=flags)])
    assert (res["status"], res["value"], res["override"]) == ("Confirmed", 950.0, None)
    assert len(res["blocked_overrides"]) == 1 and res["blocked_overrides"][0]["measured"]["value"] == 1.0
    assert res["trail"][1]["outcome"] == "rejected"


def test_a_non_blocking_flag_does_not_stop_a_measurement():
    res = dp.resolve([c(0.25, "Assumed", None, "table"), c(0.31, "Measured", "2026-10-30T00:00:00Z", "plc", quality="good", flags=["outside_assumed_range"])])
    assert (res["status"], res["value"]) == ("Measured", 0.31)


def test_missing_never_wins():
    res = dp.resolve([c(None, "Missing", "2030-01-01T00:00:00Z", "newest"), c(0.25, "Assumed", "2000-01-01T00:00:00Z", "old")])
    assert (res["status"], res["value"]) == ("Assumed", 0.25)
    assert res["trail"][0]["outcome"] == "ignored"
    only = dp.resolve([c(None, "Missing", None, "a"), c(None, "Missing", None, "b")])
    assert (only["winner"], only["status"], only["value"]) == (None, "Missing", None)
    assert dp.resolve([])["status"] == "Missing"


def test_the_order_is_measured_confirmed_calculated_estimated_assumed_missing():
    order = ["Measured", "Confirmed", "Calculated", "Estimated", "Assumed", "Missing"]
    assert list(dp.PRECEDENCE) == order
    cands = {s: c(None if s == "Missing" else order.index(s) + 10, s, "2026-01-01T00:00:00Z", s, quality="good" if s == "Measured" else None) for s in order}
    for i in range(len(order) - 1):
        assert dp.resolve([cands[s] for s in reversed(order[i:])])["status"] == order[i]


def test_ties_newest_wins_and_equal_timestamps_are_reported():
    res = dp.resolve([c(1.0, "Assumed", "2026-01-01T00:00:00Z", "old"), c(2.0, "Assumed", "2026-06-01T00:00:00Z", "new")])
    assert res["value"] == 2.0 and not res["tie"]
    res = dp.resolve([c(1.0, "Assumed", "2026-01-01T00:00:00Z", "a"), c(2.0, "Assumed", "2026-01-01T00:00:00Z", "b")])
    assert res["tie"] and res["value"] == 1.0 and "tie" in res["trail"][1]["reason"]


def test_candidates_are_validated_like_plant_state_entries():
    with pytest.raises(ValueError):
        c(1.0, "Missing")
    with pytest.raises(ValueError):
        c(None, "Assumed")
    with pytest.raises(ValueError):
        c(1.0, "Guessed")
    with pytest.raises(ValueError):
        c(1.0, "Measured", "2026-10-30T10:00:00", quality="good")                      # naive timestamp
    with pytest.raises(ValueError):
        c(1.0, "Measured", "2026-10-30T10:00:00Z", quality="excellent")


def test_dry_run_lists_what_would_change_and_touches_nothing(table):
    before = copy.deepcopy(table)
    consts = (ga001.GA001_OPERATING_TEMPERATURE_C, ga001.CARBON_CONVERSION_EFFICIENCY, uncertainty.ASSUMPTIONS["air_equivalence_ratio"]["point"])
    ms = [{"timestamp": "2026-10-30T10:00:00Z", "tag": "GA-001.T_gasifier_C", "value": 930.0, "unit": "degC", "quality": "good", "source": "syn"},
          {"timestamp": "2026-10-30T10:00:00Z", "tag": "GA-001.ER", "value": 0.3, "unit": "-", "quality": "suspect", "source": "syn"},
          {"timestamp": "2026-10-30T10:00:00Z", "tag": "GA-001.carbon_conversion", "value": 0.9, "unit": "kg/h", "quality": "good", "source": "syn"},
          {"timestamp": "2026-10-30T10:00:00Z", "tag": "NOT.a_parameter", "value": 1.0, "unit": "-", "quality": "good", "source": "syn"}]
    out = dp.dry_run(table, ms)
    by = {x["tag"]: x for x in out["changes"]}
    t = by["GA-001.T_gasifier_C"]
    assert (t["model_value"], t["resolved_value"], t["resolved_status"], t["changes"]) == (950.0, 930.0, "Measured", True)
    # PROVENANCE PHASE 2 (deliberate edit): the registry row for the gasifier temperature is no longer Confirmed by default; the owner's worksheet says ASSUMED. A good Measured
    # value therefore wins over Assumed candidates and there is no Measured-over-Confirmed override to report (the override machinery itself is tested in the precedence tests above).
    assert t["abs_change"] == -20.0 and t["override"] is None, "930 beats the Assumed registry 950; no Confirmed value is overridden"
    assert by["GA-001.ER"]["changes"] is False and by["GA-001.ER"]["n_rejected"] == 1
    assert by["GA-001.carbon_conversion"]["changes"] is False and by["GA-001.carbon_conversion"]["n_rejected"] == 1, "wrong unit is rejected, not converted"
    assert out["not_parameters"] == [{"tag": "NOT.a_parameter", "n_readings": 1}]
    assert table == before
    assert consts == (ga001.GA001_OPERATING_TEMPERATURE_C, ga001.CARBON_CONVERSION_EFFICIENCY, uncertainty.ASSUMPTIONS["air_equivalence_ratio"]["point"])


def test_dry_run_takes_the_model_value_from_the_row_the_engine_reads_not_from_the_registry_row(table):
    """The registry row (which the engine ignores) is made to differ and listed FIRST: the model value must still be the engine input's."""
    t2 = copy.deepcopy(table)
    for r in t2:
        if r["tag"] == "GA-001.T_gasifier_C" and r["overridable_via"] == pt.VIA_REGISTRY:
            r["value"] = 951.0
    t2 = sorted(t2, key=lambda r: r["overridable_via"] != pt.VIA_REGISTRY)             # registry rows first
    out = dp.dry_run(t2, [{"timestamp": "2026-10-30T10:00:00Z", "tag": "GA-001.T_gasifier_C", "value": 940.0, "unit": "degC", "quality": "good", "source": "syn"}])
    ch = out["changes"][0]
    assert ch["model_value"] == 950.0 and ch["model_status"] == "Assumed"
    assert ch["abs_change"] == -10.0, "the change is measured against what the model uses, not against the registry row"


# ---------------------------------------------------------------- (c) replay validation

CSV = """timestamp,tag,value,unit,quality,source
2026-10-30T10:00:00Z,HB-012.h2_kg_h,3.1,kg/h,good,syn
2026-10-30T10:05:00Z,HB-012.h2_kg_h,3.2,kg/h,good,syn
2026-10-30T10:05:00Z,HB-012.h2_kg_h,3.3,kg/h,good,syn
2026-10-30T10:02:00Z,HB-012.h2_kg_h,3.2,kg/h,good,syn
2026-10-30T10:06:00Z,HB-012.h2_kg_h,3.2,Nm3/h,good,syn
2026-10-30T10:06:00Z,NOPE.x,1,kg/h,good,syn
2026-10-30T10:07:00Z,SA-001.H2_vol_pct,140,vol%,good,syn
2026-10-30T10:07:00Z,GA-001.T_gasifier_C,950,degC,suspect,syn
2026-10-30 10:07:00,GA-001.ER,0.3,-,good,syn
2026-10-30T10:08:00Z,GA-001.ER,abc,-,good,syn
2026-10-30T10:09:00Z,GA-001.ER,0.25,-,excellent,syn
"""


def flags_of(rep):
    return {r["row"]: r["flags"] for r in rep["readings"]}


def test_the_validator_flags_every_defect_and_drops_nothing():
    raw = mr.parse_csv_text(CSV)
    rep = mr.replay(mr.InMemorySource(raw))
    assert len(rep["readings"]) == len(raw) == 11
    f = flags_of(rep)
    assert f[1] == [] and f[2] == []
    assert "duplicate" in f[3]
    assert "non_monotonic_time" in f[4]
    assert "unit_mismatch" in f[5]
    assert "unknown_tag" in f[6]
    assert "physically_impossible" in f[7]
    assert "quality_suspect" in f[8] and not (set(f[8]) & dp.BLOCKING_FLAGS)
    assert "bad_timestamp" in f[9] and "outside_assumed_range" in f[9]
    assert "bad_value" in f[10]
    assert "bad_quality_label" in f[11]
    kinds = {i["kind"] for i in rep["issues"]}
    assert {"duplicate", "non_monotonic_time", "unit_mismatch", "unknown_tag", "physically_impossible", "bad_timestamp", "bad_value", "bad_quality_label"} <= kinds
    # rows 1, 2 are clean; row 6 is 'good' with only the informational unknown_tag flag (it matches no parameter, so it can replace nothing)
    assert [r["row"] for r in mr.usable(rep["readings"])] == [1, 2, 6]


def test_a_duplicate_says_whether_the_value_conflicts():
    rep = mr.validate(mr.parse_csv_text(CSV))
    msg = next(i["message"] for i in rep["issues"] if i["kind"] == "duplicate")
    assert "CONFLICTING" in msg


def test_unit_spellings_are_normalised_not_converted():
    assert dp.normalise_unit("Nm³/h") == dp.normalise_unit("Nm3/h")
    assert dp.normalise_unit("°C") == dp.normalise_unit("degC")
    assert dp.normalise_unit(None) == dp.normalise_unit("") == dp.normalise_unit("-")
    assert dp.normalise_unit("kg/h") != dp.normalise_unit("Nm3/h")


def test_missing_columns_are_refused_and_json_is_read(tmp_path):
    with pytest.raises(mr.ReplayFormatError):
        mr.parse_csv_text("timestamp,tag,value\n2026-10-30T10:00:00Z,HB-012.h2_kg_h,3\n")
    with pytest.raises(mr.ReplayFormatError):
        mr.parse_json_text('[{"timestamp": "2026-10-30T10:00:00Z", "tag": "x", "value": 1}]')
    p = tmp_path / "r.json"
    p.write_text('{"readings": [{"timestamp": "2026-10-30T10:00:00Z", "tag": "HB-012.h2_kg_h", "value": 3.1, "unit": "kg/h", "quality": "good", "source": "s"}]}', encoding="utf-8")
    rep = mr.replay(mr.FileSource(str(p)))
    assert rep["counts"] == {} and rep["readings"][0]["value"] == 3.1
    p2 = tmp_path / "r.csv"
    p2.write_text(CSV, encoding="utf-8")
    assert len(mr.replay(mr.FileSource(str(p2)))["readings"]) == 11


def test_since_is_exclusive_and_keeps_unparseable_timestamps():
    raw = mr.parse_csv_text(CSV)
    got = mr.InMemorySource(raw).read(since="2026-10-30T10:05:00Z")
    rows = {r["row"] for r in got}
    assert 1 not in rows and 2 not in rows and 3 not in rows       # at or before 10:05
    assert 9 in rows, "a row with an unparseable timestamp is never silently filtered out"


def test_the_live_feed_interface_is_only_an_interface():
    with pytest.raises(NotImplementedError):
        mr.MeasurementSource().read()


# ---------------------------------------------------------------- (d) synthetic recovery

def test_synthetic_offsets_are_recovered_exactly_through_replay_and_residual_report(script, snapshot):
    cat = mr.build_catalog()
    offsets = {"HB-012.h2_kg_h": 0.5, "SA-001.H2_vol_pct": -2.0, "GA-001.dry_flow_nm3_h": 4.0, "GA-001.T_gasifier_C": -15.0, "GA-001.ER": 0.01}
    raw = script.make_synthetic(snapshot, cat, offsets, n=6)
    assert all(r["source"].startswith("SYNTHETIC") for r in raw)
    rep = mr.replay(mr.InMemorySource(raw), cat)
    assert rep["counts"].get("unit_mismatch") is None and len(rep["readings"]) == len(raw)
    rows, unmapped = script.residual_rows(snapshot, rep["readings"], cat)
    got = {r["tag"]: r for r in rows}
    assert set(got) == set(offsets) and unmapped == []
    for tag, off in offsets.items():
        assert got[tag]["residual_abs"] == pytest.approx(off, abs=1e-9), tag          # measured - model = the known offset, sign included
        assert got[tag]["residual_max_abs"] == pytest.approx(abs(off), abs=1e-9)
        assert got[tag]["model_status"] != "Measured" and got[tag]["measured_status"].startswith("Measured")
    assert got["HB-012.h2_kg_h"]["residual_rel"] == pytest.approx(0.5 / got["HB-012.h2_kg_h"]["model"], rel=1e-9)
    assert got["HB-012.h2_kg_h"]["n_used"] == 6 and got["HB-012.h2_kg_h"]["n_flagged"] == 0


def test_flagged_readings_are_counted_and_excluded_from_the_statistics_not_dropped(script, snapshot):
    cat = mr.build_catalog()
    raw = script.make_synthetic(snapshot, cat, {"HB-012.h2_kg_h": 0.5}, n=4)
    bad = dict(raw[1], quality="bad", value=raw[1]["value"] + 1000.0)
    raw[1] = bad
    rep = mr.replay(mr.InMemorySource(raw), cat)
    rows, _ = script.residual_rows(snapshot, rep["readings"], cat)
    r = rows[0]
    assert (r["n_readings"], r["n_used"], r["n_flagged"]) == (4, 3, 1)
    assert r["residual_abs"] == pytest.approx(0.5, abs=1e-9), "the bad reading must not enter the residual"
    assert "bad 1" in r["measured_status"]


def test_unmapped_and_unknown_tags_are_listed(script, snapshot):
    cat = mr.build_catalog()
    raw = mr.parse_csv_text("timestamp,tag,value,unit,quality,source\n2026-10-30T10:00:00Z,GA-003.air_flow_Nm3_h,55,Nm3/h,good,s\n2026-10-30T10:00:00Z,NOPE.x,1,kg/h,good,s\n")
    rows, unmapped = script.residual_rows(snapshot, mr.validate(raw, cat)["readings"], cat)
    assert rows == [] and {u["tag"] for u in unmapped} == {"GA-003.air_flow_Nm3_h", "NOPE.x"}


def test_identifiability_list_names_only_real_tags_and_every_parameter_is_checked(script, table):
    ident = script.identifiability(table)
    assert {i["parameter"] for i in ident} >= {"GA-001.carbon_conversion", "GA-001.ER", "GA-001.tau_conv_s", "HB-006.psa_K1"}
    assert next(i for i in ident if i["parameter"] == "GA-001.tail_gas_mode")["constrained_by"] == []
    bad = list(script.IDENTIFIABILITY) + [("GA-001.no_such_parameter", [], "x", [], "y")]
    orig = script.IDENTIFIABILITY
    script.IDENTIFIABILITY = bad
    try:
        with pytest.raises(LookupError):
            script.identifiability(table)
    finally:
        script.IDENTIFIABILITY = orig


def test_the_rendered_report_is_labelled_synthetic(script, snapshot):
    cat = mr.build_catalog()
    raw = script.make_synthetic(snapshot, cat, {"HB-012.h2_kg_h": 0.5}, n=3)
    rep = mr.replay(mr.InMemorySource(raw), cat)
    rows, unmapped = script.residual_rows(snapshot, rep["readings"], cat)
    text = script.render(snapshot, rep, rows, unmapped, script.identifiability(None, cat), script.SYNTHETIC_LABEL)
    assert "SYNTHETIC" in text and "Proves the plumbing, not the physics" in text and "Nothing is fitted" in text


# ---------------------------------------------------------------- (e) no database / network

def test_no_database_call_was_made(fake):
    assert fake.calls == [], fake.calls


def test_the_new_modules_contain_no_database_network_or_scada_code():
    for rel in ("python/parameter_table.py", "python/data_precedence.py", "python/measurement_replay.py", "scripts/run_residual_report.py"):
        with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
            src = f.read()
        code = "\n".join(line for line in src.splitlines() if not line.lstrip().startswith("#"))
        for forbidden in (r"\bimport requests\b", r"\burllib\b", r"\bimport supabase\b", r"\bcreate_client\b", r"\bopcua\b", r"\bmodbus\b", r"\.upsert\(", r"\.table\(", r"\.execute\("):
            assert not re.search(forbidden, code), (rel, forbidden)


# ---------------------------------------------------------------- (f) nothing is wired

def test_no_engine_runtime_or_app_file_imports_the_new_modules():
    offenders = []
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "outputs", ".venv", "venv", "node_modules")]
        for name in files:
            rel = os.path.relpath(os.path.join(base, name), ROOT).replace(os.sep, "/")
            if not name.endswith(".py") or rel in NEW_FILES:
                continue
            with open(os.path.join(base, name), encoding="utf-8") as f:
                src = f.read()
            for m in NEW_MODULES:
                if re.search(r"(from\s+python\s+import[^\n]*\b%s\b|import\s+python\.%s\b|from\s+python\.%s\b|from\s+\.\s+import[^\n]*\b%s\b|from\s+\.%s\b)" % (m, m, m, m, m), src):
                    offenders.append((rel, m))
    assert offenders == [], offenders


def test_this_tasks_commits_touch_no_engine_file():
    """Scoped to this task's commits (messages start with 'Data layer'). Skipped when git or origin/main is unavailable (a shallow CI checkout)."""
    try:
        subprocess.run(["git", "rev-parse", "--verify", "origin/main"], cwd=ROOT, capture_output=True, check=True)
        names = subprocess.run(["git", "log", "origin/main..HEAD", "--grep=^Data layer", "--name-only", "--format="], cwd=ROOT, capture_output=True, text=True,
                               check=True).stdout.split()
    except Exception:                                                   # noqa: BLE001
        pytest.skip("git history not available")
    allowed = NEW_FILES | {"docs/measurement_replay_schema.md", "docs/data_replacement_layer.md", "CLAUDE.md"}
    assert set(names) <= allowed, sorted(set(names) - allowed)
