"""
Continuous Simulation Runtime -- headless driver script
(docs/continuous_runtime_design.md, approved design, sections 1/3/5/6).

Run manually (`python scripts/run_continuous_cycle.py`) or on a real
schedule via .github/workflows/continuous_cycle.yml (hourly cron, which
GitHub treats as best-effort: real gaps of 3-6 h were measured in the
2026-10-27 audit). AUDIT FIX A: the accumulation step is no longer assumed
to be 1 h -- this script measures the real elapsed time since the previous
published_at, clamps it to [0.05, 12.0] h and passes it to
python/cycle_clock.py, so HB-013/EU-010/FE-001 stay correct at any cadence.

DATABASE WRITES: this script only persists / marks setpoints / logs when the
environment variable HYGAS_ALLOW_DB_WRITES=1 is set (the workflow sets it;
nothing else does). Without it the run is a dry run that only READS.

Run once, after:
  1. data/plant_state_current_schema.sql has been run in the Supabase SQL
     Editor, and
  2. .streamlit/secrets.toml has SUPABASE_URL and SUPABASE_KEY set (or,
     in CI, the workflow has written that same file from repo secrets --
     see .github/workflows/continuous_cycle.yml).
data/plant_operator_setpoints_schema.sql is optional -- its own reader
(python/operator_setpoints.py) degrades gracefully to "0 pending" if that
table doesn't exist yet.

ONE invocation = ONE real tick:
  1. Rehydrate a SharedPlantState from Supabase's plant_state_current
     table, using ONLY shared_plant_state.py's existing public write API
     (new_writer_handle / begin_cycle / set_entry / publish_cycle) -- no
     new method was added to that module (design doc section 3's own
     explicit constraint, checked directly against the current file
     before writing this: still true).
  2. Apply any pending operator setpoints (plant_operator_setpoints,
     python/operator_setpoints.py) and attempt to replay durable
     measurement promotions (measurement_promotions,
     python/measurement_promotion.py) -- both via
     SimulationEngine.promote_to_measurement(), the SAME existing,
     unmodified method, applied BEFORE the real cycle runs (design doc
     sections 5/6).
  3. Call engine.run_cycle(now=<real UTC timestamp>) exactly once. This
     also runs AI-011's own already-registered logging model
     (ai_automation_layer.get_ai011_logging_status()), which writes to
     digital_twin_cycle_log automatically, completely unmodified -- no
     separate write is coded here for that table.
  4. Persist the new published snapshot back to plant_state_current
     (upserted, one row per (equipment_id, category) key).
  5. Exit. This process does not stay resident (design doc section 1) --
     it is a trigger, not a daemon.

Follows scripts/migrate_vendor_quotes_to_supabase.py's own existing
pattern: sys.path.insert(...), `from python... import ...`, a main()
runnable standalone, no Streamlit import required to execute.
"""
import os
import re
import sys
import time
from collections import namedtuple
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from python import ai_automation_layer as ai  # noqa: E402
from python import cycle_clock  # noqa: E402
from python import eu_utilities_chp as eu  # noqa: E402
from python import fe_feed_handling as fe  # noqa: E402
from python import ga001_gasifier_model as ga001  # noqa: E402
from python import gc_gas_cleaning_chain as gc  # noqa: E402
from python import hb_remaining_chain as hbrem  # noqa: E402
from python import hb_wgs_psa_storage_chain as hbchain  # noqa: E402
from python import measurement_promotion  # noqa: E402
from python import operator_setpoints  # noqa: E402
from python import sa_virtual_sensors as sa  # noqa: E402
from python import shared_plant_state as sps  # noqa: E402
from python import simulation_engine as se  # noqa: E402
from python import tab1_integration  # noqa: E402
from python import vendor_log  # noqa: E402

_STATE_TABLE = "plant_state_current"

EXIT_STORE_UNREACHABLE = 2


def writes_allowed():
    return vendor_log.db_writes_allowed()  # HYGAS_ALLOW_DB_WRITES == "1"


def register_full_engine(engine, elapsed_info=None):
    """EXACTLY the same registration set, in the same order, as
    tab1_integration.build_live_snapshot() -- FE -> GA-001 -> GC -> HB(+
    remaining) -> EU -> SA -> AI. Duplicated here (not imported/called)
    because build_live_snapshot() itself always builds a BRAND NEW state
    and runs n synthetic-timestamp cycles from scratch -- not what a real,
    rehydrated, single-real-tick continuous run needs."""
    fe.register_fe_chain(engine)
    ga001.register_ga001(engine)
    gc.register_gc_chain(engine)
    hbchain.register_hb_chain(engine)
    hbrem.register_hb_remaining(engine)
    eu.register_eu_chain(engine)
    sa.register_sa_sensors(engine)
    ai.register_ai_layer(engine)
    if elapsed_info is not None:
        # Driver-only entries (audit fixes A4/C1): ElapsedHours + CycleCounter.
        cycle_clock.register_runtime_models(engine, elapsed_info)


class StoreUnreachable(RuntimeError):
    """plant_state_current could not be READ (auth, timeout, 5xx, DNS, malformed
    response ...) after all retries. This is NOT the same as "empty" or "table
    missing": the store may be full of accumulated state we simply could not see,
    so a writing run must not bootstrap from empty and overwrite it."""


# The three outcomes of a store read that do NOT raise.
STORE_OK = "ok"                      # rows were read
STORE_EMPTY = "empty"                # table exists, zero rows -> first-ever run, bootstrap allowed
STORE_TABLE_MISSING = "table_missing"  # table does not exist yet -> bootstrap allowed

StoreRead = namedtuple("StoreRead", "rows outcome detail")

READ_ATTEMPTS = 3
READ_BACKOFF_SECONDS = (2, 4)        # waited after attempt 1 and attempt 2

# PostgREST: PGRST205 = "Could not find the table 'public.x' in the schema cache"
# (the exact text the 2026-10-27 audit saw for digital_twin_cycle_log); Postgres 42P01 =
# undefined_table ("relation ... does not exist").
_TABLE_MISSING_CODES = ("PGRST205", "42P01")
_TABLE_MISSING_TEXT = re.compile(r"PGRST205|Could not find the table|relation .{0,120} does not exist", re.I)


def is_table_missing_error(exc):
    code = getattr(exc, "code", None)
    if code in _TABLE_MISSING_CODES:
        return True
    return bool(_TABLE_MISSING_TEXT.search(str(exc)))


def safe_error_text(exc, limit=220):
    """One-line error text that is safe to print/log: no URLs, no key-like tokens."""
    text = f"{type(exc).__name__}: {exc}"
    text = re.sub(r"https?://\S+", "<url>", text)
    text = re.sub(r"eyJ[\w-]{10,}\.[\w-]+\.[\w-]+", "<token>", text)
    text = re.sub(r"\b(sb_|sk-|key[-_=:])\S{8,}", "<token>", text, flags=re.I)
    return " ".join(text.split())[:limit]


def _validate_rows(data):
    """Malformed response -> ValueError (counted as a failed attempt)."""
    if not isinstance(data, list):
        raise ValueError(f"malformed response: expected a list of rows, got {type(data).__name__}")
    for row in data:
        if not isinstance(row, dict) or "equipment_id" not in row or "category" not in row or not isinstance(row.get("entry"), dict):
            raise ValueError("malformed response: a row lacks equipment_id / category / entry")
    return data


def read_store():
    """Reads every row of plant_state_current with 3 attempts (2 s, 4 s back-off
    between them) and CLASSIFIES the outcome:
      * rows came back              -> StoreRead(rows, "ok")
      * table exists, no rows       -> StoreRead([], "empty")          bootstrap allowed
      * table does not exist        -> StoreRead([], "table_missing")   bootstrap allowed
      * anything else after retries -> raises StoreUnreachable
    A missing table is recognised immediately (retrying cannot create it)."""
    last = None
    for attempt in range(1, READ_ATTEMPTS + 1):
        try:
            resp = vendor_log._get_client().table(_STATE_TABLE).select("*").execute()
            rows = _validate_rows(resp.data)
            if not rows:
                return StoreRead([], STORE_EMPTY, "table exists but has no rows (first-ever run)")
            return StoreRead(rows, STORE_OK, f"{len(rows)} row(s)")
        except Exception as exc:  # noqa: BLE001 -- classified below, never swallowed silently
            if is_table_missing_error(exc):
                return StoreRead([], STORE_TABLE_MISSING, f"table {_STATE_TABLE} does not exist yet ({safe_error_text(exc)})")
            last = exc
            print(f"  read attempt {attempt}/{READ_ATTEMPTS} failed: {safe_error_text(exc)}")
            if attempt < READ_ATTEMPTS:
                time.sleep(READ_BACKOFF_SECONDS[attempt - 1])
    raise StoreUnreachable(f"{_STATE_TABLE} unreadable after {READ_ATTEMPTS} attempts: {safe_error_text(last)}")


def load_persisted_rows():
    """Rows of plant_state_current. [] only for an empty or missing table;
    raises StoreUnreachable when the store could not be read."""
    return read_store().rows


def snapshot_from_rows(rows):
    return {(row["equipment_id"], row["category"]): row["entry"] for row in rows}


def previous_published_at(rows):
    """The newest published_at among the persisted rows (all rows of one
    publish share it), or None for an empty store."""
    stamps = [r.get("published_at") for r in rows if r.get("published_at")]
    return max(stamps) if stamps else None


def load_persisted_snapshot():
    """Back-compat wrapper (entries only). Kept for any outside caller; it has none
    in this repo (checked with grep -- main() is the only user of the row loader).
    It keeps the OLD swallow-everything behaviour on purpose: an unreadable store
    returns {} here. That is only acceptable for read-only callers -- never base a
    decision to WRITE on it; main() uses read_store() and aborts instead."""
    try:
        return snapshot_from_rows(load_persisted_rows())
    except StoreUnreachable as exc:
        print(f"  {exc} -- returning an empty snapshot (read-only legacy wrapper).")
        return {}


def rehydrate(persisted_entries, now_iso):
    """Existing public write API ONLY (new_writer_handle / begin_cycle /
    set_entry / publish_cycle) -- design doc section 3's own explicit
    constraint: no new method on shared_plant_state.py. If
    persisted_entries is empty (first-ever run, or the store was
    unreachable), begin_cycle()/publish_cycle() still run over zero
    entries -- a real, harmless, empty publish, not a special case."""
    state = sps.SharedPlantState()
    boot_handle = state.new_writer_handle()
    state.begin_cycle(boot_handle, now=now_iso)
    for (equipment_id, category), entry in persisted_entries.items():
        state.set_entry(
            boot_handle, (equipment_id, category),
            value=entry["value"], unit=entry["unit"], status=entry["status"],
            model=entry["source"]["model"], inputs=entry["source"]["inputs"],
            validation_basis=entry["validation_basis"],
            confidence_note=entry["confidence_note"],
            missing_reason=entry.get("missing_reason"),
        )
    state.publish_cycle(boot_handle)
    # boot_handle is now spent -- constructing SimulationEngine(state) next
    # issues its OWN fresh handle, correctly invalidating boot_handle, the
    # SAME single-writer discipline shared_plant_state.py already enforces.
    return state


def apply_pending_operator_setpoints(engine):
    """design doc section 5, step 4."""
    pending = operator_setpoints.list_pending_setpoints()
    applied = []
    for row in pending:
        key = operator_setpoints.key_from_str(row["engine_key"])
        if key not in engine._models:
            print(f"  Skipped setpoint for unregistered key {row['engine_key']!r} -- not applied.")
            continue
        reader = operator_setpoints.make_operator_setpoint_reader(
            row["value"],
            f"Operator setpoint, requested_by={row.get('requested_by') or 'unknown'} "
            f"at {row.get('requested_at')}",
        )
        engine.promote_to_measurement(key, reader)
        if writes_allowed():
            operator_setpoints.mark_setpoint_applied(row["engine_key"])
        else:
            print(f"  HYGAS_ALLOW_DB_WRITES!=1 -> setpoint {row['engine_key']!r} applied in memory, NOT marked applied in the DB.")
        applied.append(row["engine_key"])
    return applied


def replay_measurement_promotions(engine):
    """design doc section 6: the driver script's own startup sequence is
    the natural place to replay measurement_promotions -- fixing the
    pre-existing gap the design phase found (a promotion never survived
    the dashboard's own repeated from-scratch engine rebuilds).

    HONEST LIMITATION, stated plainly, not glossed over:
    measurement_promotion.py's own module docstring already states a
    promotion's own real reader is "a live callable... not serializable
    data" -- no real sensor/PLC reader exists anywhere in this project
    yet (confirmed directly, not assumed), so there is currently nothing
    real to reconnect. This function DOES call the real, existing
    list_promoted_measurements() (proving the replay mechanism itself
    runs, every tick) and reports what it finds -- it does not, and
    structurally cannot, fabricate a reader function for a sensor that
    doesn't exist. The moment a real reader is ever wired (a
    per-key {engine_key: reader_fn} mapping maintained alongside a real
    sensor/PLC integration), this is the one place it would be replayed
    from, unmodified."""
    promoted = measurement_promotion.list_promoted_measurements()
    for row in promoted:
        key = tuple(row["engine_key"].split("|", 1))
        if key not in engine._models:
            print(f"  Skipped promotion replay for unregistered key {row['engine_key']!r}.")
            continue
        print(
            f"  NOTE: {row['engine_key']!r} was promoted to a measurement "
            f"(source={row.get('source_description')!r}) but no real reader function exists in "
            f"this project yet to reconnect -- not reapplied this cycle (see this function's own "
            f"docstring)."
        )
    return promoted


def persist_snapshot(state, now_iso=None):
    """Upserts the FULL published snapshot into plant_state_current, one
    row per (equipment_id, category) key. Reuses tab1_integration.py's own
    existing _native() numpy-safety helper (design doc section 3's own
    explicit instruction) rather than duplicating it -- several upstream
    models (e.g. GA-001's equilibrium solver) return numpy scalars, which
    are not natively JSON-serializable."""
    snapshot = state.get_snapshot()
    published_at = state.published_at
    # Audit fix C1: `cycle` is the monotonic RUNTIME/CycleCounter, NOT
    # SharedPlantState.published_cycle (which is always 2 after a rehydrate).
    counter_entry = snapshot.get(cycle_clock.COUNTER_KEY)
    if counter_entry is not None and counter_entry["status"] != "Missing":
        cycle = int(counter_entry["value"])
    else:
        cycle = state.published_cycle
    # Audit fix C3: set updated_at explicitly -- a fallback for when the
    # data/migrations/001 BEFORE UPDATE trigger is not installed (a plain
    # upsert never touches the column default after the first insert).
    updated_at = now_iso or published_at
    rows = [
        {
            "equipment_id": equipment_id, "category": category,
            "entry": tab1_integration._native(entry),
            "cycle": cycle, "published_at": published_at, "updated_at": updated_at,
        }
        for (equipment_id, category), entry in snapshot.items()
    ]
    if not rows:
        print("  Nothing to persist this cycle (empty snapshot).")
        return 0
    vendor_log._get_client().table(_STATE_TABLE).upsert(
        rows, on_conflict="equipment_id,category",
    ).execute()
    return len(rows)


def main(now_iso=None):
    t0 = time.monotonic()
    now_iso = now_iso or datetime.now(timezone.utc).isoformat()
    print(f"=== Continuous cycle run starting at {now_iso} ===")
    allow = writes_allowed()
    if not allow:
        print("  HYGAS_ALLOW_DB_WRITES!=1 -> DRY RUN: reads only, nothing will be written to the database.")

    print("Loading persisted state from Supabase (plant_state_current)...")
    try:
        store = read_store()
    except StoreUnreachable as exc:
        if allow:
            # Writing run + unreadable store: bootstrapping from empty would overwrite the accumulated
            # state (inventories, damped temperatures, cycle counter). Stop before building or running
            # anything and without persisting; the red Actions run is the alert.
            print(f"ERROR: {exc} -- aborting WITHOUT running a cycle or writing anything (the stored state is untouched).")
            raise SystemExit(EXIT_STORE_UNREACHABLE)
        print(f"  {exc} -- dry run: continuing from an EMPTY snapshot (read-only, nothing will be written).")
        store = StoreRead([], "unreachable_dry_run", str(exc))
    rows = store.rows
    persisted = snapshot_from_rows(rows)
    print(f"  store read outcome: {store.outcome} -- {len(persisted)} persisted key(s) found.")
    if store.outcome == STORE_TABLE_MISSING:
        print(f"  NOTE: {store.detail}. Bootstrapping from empty (first run before the schema exists).")

    # Audit fix A3: real elapsed time since the previous publish becomes dt.
    elapsed = cycle_clock.compute_elapsed_hours(previous_published_at(rows), now_iso)
    if elapsed["clamped"]:
        print(f"  ELAPSED-TIME CLAMP: {elapsed['clamp_reason']} -> using {elapsed['elapsed_h_used']} h")
    elif elapsed["clamp_reason"]:
        print(f"  {elapsed['clamp_reason']}")
    print(f"  Elapsed hours used as the cycle time step: {elapsed['elapsed_h_used']:.4f} h "
          f"(previous published_at={elapsed['previous_published_at']})")
    cycle_clock.set_elapsed_hours(elapsed["elapsed_h_used"])

    try:
        print("Rehydrating SharedPlantState via the existing public write API...")
        state = rehydrate(persisted, now_iso)

        print("Building the engine (FE -> GA-001 -> GC -> HB(+remaining) -> EU -> SA -> AI + RUNTIME)...")
        engine = se.SimulationEngine(state)
        register_full_engine(engine, elapsed_info=elapsed)

        print("Applying pending operator setpoints...")
        applied_setpoints = apply_pending_operator_setpoints(engine)
        print(f"  {len(applied_setpoints)} setpoint(s) applied: {applied_setpoints}")

        print("Replaying durable measurement promotions...")
        replay_measurement_promotions(engine)

        print("Running one real cycle...")
        cycle_no, published_at = engine.run_cycle(now=now_iso)
        print(f"  Published cycle {cycle_no} at {published_at}.")
    finally:
        cycle_clock.set_elapsed_hours(None)

    counter = state.get_snapshot().get(cycle_clock.COUNTER_KEY)
    if counter is not None:
        print(f"  RUNTIME/CycleCounter = {counter['value']}")

    if allow:
        print("Persisting the new snapshot to plant_state_current...")
        n_rows = persist_snapshot(state, now_iso=now_iso)
        print(f"  {n_rows} row(s) upserted.")
    else:
        print("Dry run: snapshot NOT persisted.")

    elapsed_s = time.monotonic() - t0
    print(f"=== Continuous cycle run finished in {elapsed_s:.2f}s ===")
    return elapsed_s


if __name__ == "__main__":
    main()
