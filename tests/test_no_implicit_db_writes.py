"""Audit fix J3: engine runs, imports and self-tests never write to the database
implicitly (audit findings 4/21). Uses a counting fake client; no credentials."""
import collections
import os
import re

import pytest

from _fakes import FakeSupabase, patched_supabase
from python import cycle_clock, measurement_promotion, operator_setpoints, tab1_integration
from python import shared_plant_state as sps
from python import simulation_engine as se

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(autouse=True)
def _no_flag(monkeypatch):
    monkeypatch.delenv("HYGAS_ALLOW_DB_WRITES", raising=False)
    cycle_clock.set_elapsed_hours(None)


def test_three_snapshots_without_the_flag_make_zero_client_calls():
    fake = FakeSupabase()
    with patched_supabase(fake):
        for _ in range(3):
            snapshot, _state, _engine = tab1_integration.build_live_snapshot()
    assert fake.calls == [], f"unexpected database calls: {fake.calls}"
    logged = snapshot[("AI-011", "LoggingStatus")]
    assert logged["status"] == "Calculated"
    assert logged["value"]["logged"] is False
    assert logged["value"]["reason"] == "writes disabled outside the continuous runtime"
    assert "error" not in logged["value"], "a skipped write must not be reported as an error"


def test_with_the_flag_exactly_one_insert_per_cycle(monkeypatch):
    monkeypatch.setenv("HYGAS_ALLOW_DB_WRITES", "1")
    fake = FakeSupabase()
    with patched_supabase(fake):
        snapshot, _state, _engine = tab1_integration.build_live_snapshot(n_cycles=5)
    assert collections.Counter(fake.calls) == {("insert", "digital_twin_cycle_log"): 5}
    assert len(fake.tables["digital_twin_cycle_log"]) == 5
    assert snapshot[("AI-011", "LoggingStatus")]["value"]["logged"] is True


def test_selftest_writers_are_guarded_without_the_flag():
    fake = FakeSupabase()
    with patched_supabase(fake):
        state = sps.SharedPlantState()
        engine = se.SimulationEngine(state)
        engine.register_model(("T", "X"), lambda gi: {"value": 1.0, "status": "Calculated", "model": "t", "inputs": []}, unit="-")
        reader = measurement_promotion.make_synthetic_measurement_reader(1.0, unit="-", source_note="test")
        result = measurement_promotion.record_measurement(engine, ("T", "X"), reader, source_description="test")
        applied = operator_setpoints.mark_setpoint_applied("SYNTHETIC-TEST-KEY|not-a-real-row")
    assert result["applied"] is True and result["logged"] is False
    assert applied is False
    assert [c for c in fake.calls if c[0] != "select"] == []


# Every place the code CAN write. A new writer fails this test until someone decides
# whether it needs the HYGAS_ALLOW_DB_WRITES guard (engine/self-test reachable) or is
# an explicit user action (button / manual script) and adds it here with a reason.
KNOWN_WRITERS = {
    "python/ai_automation_layer.py": (1, "AI-011 cycle log -- GUARDED by db_writes_allowed()"),
    "python/measurement_promotion.py": (1, "audit trail -- GUARDED"),
    "python/operator_setpoints.py": (2, "mark_setpoint_applied GUARDED; request_setpoint = explicit operator call, no caller"),
    "python/confirmation_loop.py": (2, "UI buttons (mark asked / record confirmation); __main__ only reads"),
    "python/vendor_log.py": (1, "UI 'log quote' button"),
    "scripts/migrate_vendor_quotes_to_supabase.py": (1, "manual one-off migration script"),
    "scripts/run_continuous_cycle.py": (1, "the continuous runtime's upsert -- dry run unless the flag is set"),
}


def test_the_set_of_database_writers_is_the_known_one():
    # Supabase writes in this repo are all single-line `.table(<name>).<op>(` calls.
    pattern = re.compile(r"\.table\([^)]*\)\.(insert|upsert|update|delete)\(")
    found = {}
    for folder in ("python", "scripts"):
        for name in sorted(os.listdir(os.path.join(ROOT, folder))):
            if name.endswith(".py"):
                rel = f"{folder}/{name}"
                with open(os.path.join(ROOT, rel), encoding="utf-8") as handle:
                    hits = pattern.findall(handle.read())
                if hits:
                    found[rel] = len(hits)
    with open(os.path.join(ROOT, "app.py"), encoding="utf-8") as handle:
        assert not pattern.search(handle.read()), "app.py writes to the database directly"
    unexpected = {f: n for f, n in found.items() if f not in KNOWN_WRITERS}
    assert unexpected == {}, f"new database writers need a guard decision: {unexpected}"
    for rel, (count, _why) in KNOWN_WRITERS.items():
        assert found.get(rel) == count, f"{rel}: expected {count} write call(s), found {found.get(rel)}"
