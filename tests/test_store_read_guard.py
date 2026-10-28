"""Never overwrite the stored plant state after a failed read (round 2).

Drives scripts/run_continuous_cycle.py's main() end to end against the in-memory fake
client (tests/_fakes.py): no network, no credentials, time.sleep patched so the 2 s / 4 s
back-off costs nothing. Every scenario asserts on the calls the fake recorded.
"""
import contextlib
import copy
import importlib.util
import io
import os
import time

import pytest
from postgrest.exceptions import APIError

from _fakes import MISSING_TABLE_MESSAGE, FakeSupabase, patched_supabase

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DRIVER_PATH = os.path.join(ROOT, "scripts", "run_continuous_cycle.py")
T1, T2 = "2026-10-27T08:17:00+00:00", "2026-10-27T12:17:00+00:00"
STATE = "plant_state_current"

PGRST205 = {"message": "Could not find the table 'public.plant_state_current' in the schema cache",
            "code": "PGRST205", "hint": None, "details": None}


@pytest.fixture
def driver(monkeypatch):
    spec = importlib.util.spec_from_file_location("run_continuous_cycle_under_test", DRIVER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sleeps = []
    monkeypatch.setattr(time, "sleep", lambda seconds: sleeps.append(seconds))
    module.recorded_sleeps = sleeps
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.delenv("HYGAS_ALLOW_SHRINK", raising=False)
    return module


def _run(driver, fake, now_iso, writes=True):
    """Runs main(); returns (exit_code or None, stdout). Never lets SystemExit escape."""
    os.environ["HYGAS_ALLOW_DB_WRITES"] = "1" if writes else "0"
    out = io.StringIO()
    code = None
    try:
        with patched_supabase(fake), contextlib.redirect_stdout(out):
            driver.main(now_iso=now_iso)
    except SystemExit as exc:
        code = exc.code
    finally:
        os.environ["HYGAS_ALLOW_DB_WRITES"] = "0"
    return code, out.getvalue()


@pytest.fixture(scope="module")
def seeded_rows():
    """A realistic store: the rows one real driver run persists (118 keys)."""
    spec = importlib.util.spec_from_file_location("run_continuous_cycle_seed", DRIVER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fake = FakeSupabase()
    os.environ["HYGAS_ALLOW_DB_WRITES"] = "1"
    try:
        with patched_supabase(fake), contextlib.redirect_stdout(io.StringIO()):
            module.main(now_iso=T1)
    finally:
        os.environ["HYGAS_ALLOW_DB_WRITES"] = "0"
    rows = fake.tables[STATE]
    assert len(rows) >= 100
    return rows


def _store(seeded_rows, **extra):
    return FakeSupabase({STATE: copy.deepcopy(seeded_rows), **extra.pop("tables", {})}, **extra)


def _writes(fake):
    return [c for c in fake.calls if c[0] != "select"]


def _upserts(fake):
    return fake.count("upsert", STATE)


def _guard_against_building(driver, monkeypatch):
    built = []
    for name in ("rehydrate", "register_full_engine"):
        monkeypatch.setattr(driver, name, lambda *a, _n=name, **k: built.append(_n))
    monkeypatch.setattr(driver.se, "SimulationEngine", lambda *a, **k: built.append("SimulationEngine"))
    return built


# ---------------------------------------------------------------------------- 1. unreadable + writes on -> abort
def test_1_unreadable_store_with_writes_aborts_before_anything_runs(driver, seeded_rows, monkeypatch):
    pending = {"plant_operator_setpoints": [{"id": 1, "engine_key": "GA-001-INPUT|equivalence_ratio", "value": 0.3,
                                             "applied_at": None, "requested_by": "t", "requested_at": "x"}]}
    fake = _store(seeded_rows, tables=pending,
                  failures={(STATE, "select"): [Exception("connection reset by peer")] * 3})
    built = _guard_against_building(driver, monkeypatch)
    code, out = _run(driver, fake, T2)
    assert code not in (None, 0) and code == driver.EXIT_STORE_UNREACHABLE
    assert fake.count("select", STATE) == 3, "3 attempts expected"
    assert driver.recorded_sleeps == [2, 4], "back-off 2 s then 4 s"
    assert _writes(fake) == [], f"nothing may be written: {_writes(fake)}"
    assert built == [], f"engine/state must not be built: {built}"
    assert fake.tables["plant_operator_setpoints"][0]["applied_at"] is None, "setpoint must not be marked"
    assert "read attempt 1/3 failed" in out and "read attempt 3/3 failed" in out and "ERROR:" in out
    assert len(fake.tables[STATE]) == len(seeded_rows), "stored state untouched"


@pytest.mark.parametrize("error", [
    TimeoutError("timed out"),
    APIError({"message": "JWT expired", "code": "PGRST301", "hint": None, "details": None}),
    APIError({"message": "Bad gateway", "code": "502", "hint": None, "details": None}),
    OSError("[Errno -2] Name or service not known"),
], ids=["timeout", "auth", "5xx", "dns"])
def test_1b_other_failures_are_unreachable_not_empty(driver, seeded_rows, error):
    fake = _store(seeded_rows, failures={(STATE, "select"): [error] * 3})
    code, _out = _run(driver, fake, T2)
    assert code == driver.EXIT_STORE_UNREACHABLE and _writes(fake) == []


def test_1c_malformed_response_is_unreachable(driver, seeded_rows, monkeypatch):
    class Bad:
        data = {"not": "a list"}

    class BadQuery:
        def select(self, *a, **k):
            return self

        def execute(self):
            return Bad()

    class BadClient:
        calls = []

        def table(self, name):
            return BadQuery()

    os.environ["HYGAS_ALLOW_DB_WRITES"] = "1"
    try:
        with patched_supabase(BadClient()), contextlib.redirect_stdout(io.StringIO()):
            with pytest.raises(driver.StoreUnreachable):
                driver.read_store()
    finally:
        os.environ["HYGAS_ALLOW_DB_WRITES"] = "0"


# ---------------------------------------------------------------------------- 2. one failure, then success
def test_2_read_fails_once_then_succeeds(driver, seeded_rows):
    fake = _store(seeded_rows, failures={(STATE, "select"): [Exception("transient")]})
    before = len(seeded_rows)
    code, out = _run(driver, fake, T2)
    assert code is None, out
    assert fake.count("select", STATE) == 2, "exactly one retry"
    assert driver.recorded_sleeps == [2]
    assert _upserts(fake) == 1
    assert "read attempt 1/3 failed" in out and "store read outcome: ok" in out
    counter = {(r["equipment_id"], r["category"]): r for r in fake.tables[STATE]}[("RUNTIME", "CycleCounter")]
    assert counter["entry"]["value"] == 2, "state continued from the stored counter (1 -> 2)"
    assert len(fake.tables[STATE]) >= len(seeded_rows)


# ---------------------------------------------------------------------------- 3. table missing -> bootstrap
@pytest.mark.parametrize("error", [
    APIError(PGRST205),
    Exception(MISSING_TABLE_MESSAGE % "plant_state_current"),
    Exception('relation "public.plant_state_current" does not exist'),
], ids=["APIError PGRST205", "plain exception, audit text", "postgres 42P01 text"])
def test_3_missing_table_bootstraps_and_upserts(driver, error):
    fake = FakeSupabase(failures={(STATE, "select"): [error]})
    code, out = _run(driver, fake, T1)
    assert code is None, out
    assert driver.recorded_sleeps == [], "a missing table is not retried"
    assert _upserts(fake) == 1 and len(fake.tables[STATE]) >= 100
    assert "table_missing" in out and "Bootstrapping from empty" in out


# ---------------------------------------------------------------------------- 4. empty table -> bootstrap
def test_4_empty_table_bootstraps(driver):
    fake = FakeSupabase()
    code, out = _run(driver, fake, T1)
    assert code is None and _upserts(fake) == 1
    assert "store read outcome: empty" in out and len(fake.tables[STATE]) >= 100


# ---------------------------------------------------------------------------- 5. read fails + dry run
def test_5_unreadable_store_dry_run_continues_from_empty_without_writes(driver, seeded_rows):
    fake = _store(seeded_rows, failures={(STATE, "select"): [Exception("down")] * 3})
    code, out = _run(driver, fake, T2, writes=False)
    assert code is None, out
    assert _writes(fake) == []
    assert "dry run: continuing from an EMPTY snapshot" in out and "Dry run: snapshot NOT persisted" in out


# ---------------------------------------------------------------------------- 6. shrink guard
def _drop_models(driver, monkeypatch, n):
    original = driver.register_full_engine

    def trimmed(engine, elapsed_info=None):
        original(engine, elapsed_info=elapsed_info)
        for key in sorted((k for k in engine._models if k[0] != "RUNTIME"), key=str)[:n]:
            del engine._models[key]

    monkeypatch.setattr(driver, "register_full_engine", trimmed)


def test_6_shrink_guard_aborts_and_override_proceeds(driver, seeded_rows, monkeypatch):
    stored = len(seeded_rows)
    _drop_models(driver, monkeypatch, 38)
    fake = _store(seeded_rows)
    code, out = _run(driver, fake, T2)
    assert code == driver.EXIT_SHRINK_GUARD, out
    assert _upserts(fake) == 0 and _writes(fake) == []
    assert f"store holds {stored} key(s)" in out and "would persist only 80" in out and "First 20 missing" in out
    assert len(fake.tables[STATE]) == stored

    monkeypatch.setenv("HYGAS_ALLOW_SHRINK", "1")
    fake2 = _store(seeded_rows)
    code2, out2 = _run(driver, fake2, T2)
    assert code2 is None, out2
    assert _upserts(fake2) == 1 and "shrink guard overridden" in out2


def test_6b_bootstrap_is_never_judged_by_the_shrink_guard(driver, monkeypatch):
    _drop_models(driver, monkeypatch, 38)
    fake = FakeSupabase()          # empty store
    code, out = _run(driver, fake, T1)
    assert code is None, out
    assert _upserts(fake) == 1


def test_6c_check_shrink_thresholds(driver):
    stored = {("A", str(i)) for i in range(116)}
    assert driver.check_shrink(stored, set(list(stored)[:80]))["n_missing"] == 36
    assert driver.check_shrink(stored, set(list(stored)[:105])) is None          # 90.5 %
    assert driver.check_shrink(stored, set(list(stored)[:80]), override=True) is None
    assert driver.check_shrink({("B", str(i)) for i in range(19)}, {("B", "0")}) is None   # < 20 stored keys
    assert len(driver.check_shrink(stored, set())["missing_first_20"]) == 20


# ---------------------------------------------------------------------------- 7. setpoint marking order
def _pending(driver):
    return {"plant_operator_setpoints": [{"id": 1, "engine_key": "GA-001-INPUT|equivalence_ratio", "value": 0.3,
                                          "applied_at": None, "requested_by": "test", "requested_at": "x"}]}


def test_7a_setpoint_is_marked_only_after_the_upsert(driver, seeded_rows):
    fake = _store(seeded_rows, tables=_pending(driver))
    code, out = _run(driver, fake, T2)
    assert code is None, out
    order = [c for c in fake.calls if c in (("upsert", STATE), ("update", "plant_operator_setpoints"))]
    assert order == [("upsert", STATE), ("update", "plant_operator_setpoints")], order
    assert fake.tables["plant_operator_setpoints"][0]["applied_at"] is not None
    assert "marked applied after the successful save" in out


def test_7b_failed_save_marks_nothing(driver, seeded_rows):
    fake = _store(seeded_rows, tables=_pending(driver), failures={(STATE, "upsert"): [Exception("write failed")]})
    out = io.StringIO()
    os.environ["HYGAS_ALLOW_DB_WRITES"] = "1"
    try:
        with patched_supabase(fake), contextlib.redirect_stdout(out):
            with pytest.raises(Exception, match="write failed"):
                driver.main(now_iso=T2)
    finally:
        os.environ["HYGAS_ALLOW_DB_WRITES"] = "0"
    assert fake.count("update", "plant_operator_setpoints") == 0
    assert fake.tables["plant_operator_setpoints"][0]["applied_at"] is None
    assert "stay pending for the next run" in out.getvalue()


def test_7c_shrink_abort_marks_nothing(driver, seeded_rows, monkeypatch):
    _drop_models(driver, monkeypatch, 38)
    fake = _store(seeded_rows, tables=_pending(driver))
    code, out = _run(driver, fake, T2)
    assert code == driver.EXIT_SHRINK_GUARD
    assert fake.count("update", "plant_operator_setpoints") == 0
    assert "stay pending for the next run" in out


def test_7d_dry_run_marks_nothing(driver, seeded_rows):
    fake = _store(seeded_rows, tables=_pending(driver))
    code, out = _run(driver, fake, T2, writes=False)
    assert code is None and _writes(fake) == []
    assert "NOT marked applied in the DB" in out


# ---------------------------------------------------------------------------- 8. step summary
def test_8a_step_summary_written_when_the_variable_is_set(driver, seeded_rows, monkeypatch, tmp_path):
    target = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(target))
    fake = _store(seeded_rows)
    code, out = _run(driver, fake, T2)
    assert code is None, out
    text = target.read_text(encoding="utf-8")
    assert "### Continuous cycle -- OK -- state saved" in text
    for needle in ("Time (UTC) | 2026-10-27T12:17:00", "Elapsed hours used | 4.0000 h (not clamped)",
                   "Previous published_at | 2026-10-27T08:17:00", "RUNTIME/CycleCounter | 2",
                   f"Keys read / rows upserted | {len(seeded_rows)} / "):
        assert needle in text, (needle, text)
    assert "http" not in text and "apikey" not in text.lower()


def test_8b_abort_is_written_to_the_summary(driver, seeded_rows, monkeypatch, tmp_path):
    target = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(target))
    fake = _store(seeded_rows, failures={(STATE, "select"): [Exception("db down https://x.supabase.co/rest/v1/a?apikey=eyJabcdefghij.klmnopqrst.uvwxyz")] * 3})
    code, _out = _run(driver, fake, T2)
    assert code == driver.EXIT_STORE_UNREACHABLE
    text = target.read_text(encoding="utf-8")
    assert "ABORTED (exit status 2)" in text and "store unreadable" in text and "stored state untouched" in text
    assert "http" not in text and "eyJ" not in text, "no URLs or key-like tokens may reach the summary"


def test_8c_without_the_variable_nothing_is_written_and_nothing_fails(driver, seeded_rows, tmp_path):
    assert "GITHUB_STEP_SUMMARY" not in os.environ
    code, out = _run(driver, _store(seeded_rows), T2)
    assert code is None, out
    assert list(tmp_path.iterdir()) == []


def test_8d_an_unwritable_summary_path_never_changes_the_outcome(driver, seeded_rows, monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path))     # a directory: open() fails
    code, out = _run(driver, _store(seeded_rows), T2)
    assert code is None, out
    assert "could not write the step summary" in out


# ---------------------------------------------------------------------------- classifier / scrubber units
def test_classifier_and_scrubber(driver):
    assert driver.is_table_missing_error(APIError(PGRST205))
    assert driver.is_table_missing_error(Exception(MISSING_TABLE_MESSAGE % "x"))
    assert not driver.is_table_missing_error(APIError({"message": "JWT expired", "code": "PGRST301"}))
    assert not driver.is_table_missing_error(TimeoutError("timed out"))
    text = driver.safe_error_text(Exception("fail https://a.supabase.co/rest/v1/t?apikey=eyJabcdefghij.klmnopqrst.uvwxyz"))
    assert "http" not in text and "eyJ" not in text and text.startswith("Exception:")
    # back-compat wrapper keeps its documented legacy behaviour and has no caller
    fake = FakeSupabase(failures={(STATE, "select"): [Exception("x")] * 3})
    with patched_supabase(fake), contextlib.redirect_stdout(io.StringIO()):
        assert driver.load_persisted_snapshot() == {}
