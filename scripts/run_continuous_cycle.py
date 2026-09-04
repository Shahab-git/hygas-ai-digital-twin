"""
Continuous Simulation Runtime -- headless driver script
(docs/continuous_runtime_design.md, approved design, sections 1/3/5/6).

Run manually (`python scripts/run_continuous_cycle.py`) or on a real
schedule via .github/workflows/continuous_cycle.yml (`cron: "0 * * * *"`
-- once per real hour, matching hb_wgs_psa_storage_chain.py's own
ASSUMED_HOURS_PER_CYCLE = 1.0 exactly, per the design doc's own section 2
reasoning -- this is not a free choice, it's the one interval that keeps
HB-013/EU-010/FE-001's accumulation math correct, unmodified).

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
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from python import ai_automation_layer as ai  # noqa: E402
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


def register_full_engine(engine):
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


def load_persisted_snapshot():
    """Reads every row from plant_state_current. Returns {} if the table
    is empty or doesn't exist yet (a real, expected first-run/pre-schema
    condition, not an error) -- the caller then runs a bootstrap cycle
    with no prior history, exactly like today's own in-process
    build_live_snapshot() cold start."""
    try:
        resp = vendor_log._get_client().table(_STATE_TABLE).select("*").execute()
        rows = resp.data or []
    except Exception as exc:
        print(f"  plant_state_current not reachable ({exc}) -- starting from an empty snapshot.")
        return {}
    return {(row["equipment_id"], row["category"]): row["entry"] for row in rows}


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
        operator_setpoints.mark_setpoint_applied(row["engine_key"])
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


def persist_snapshot(state):
    """Upserts the FULL published snapshot into plant_state_current, one
    row per (equipment_id, category) key. Reuses tab1_integration.py's own
    existing _native() numpy-safety helper (design doc section 3's own
    explicit instruction) rather than duplicating it -- several upstream
    models (e.g. GA-001's equilibrium solver) return numpy scalars, which
    are not natively JSON-serializable."""
    snapshot = state.get_snapshot()
    published_at = state.published_at
    cycle = state.published_cycle
    rows = [
        {
            "equipment_id": equipment_id, "category": category,
            "entry": tab1_integration._native(entry),
            "cycle": cycle, "published_at": published_at,
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


def main():
    t0 = time.monotonic()
    now_iso = datetime.now(timezone.utc).isoformat()
    print(f"=== Continuous cycle run starting at {now_iso} ===")

    print("Loading persisted state from Supabase (plant_state_current)...")
    persisted = load_persisted_snapshot()
    print(f"  {len(persisted)} persisted key(s) found.")

    print("Rehydrating SharedPlantState via the existing public write API...")
    state = rehydrate(persisted, now_iso)

    print("Building the engine (FE -> GA-001 -> GC -> HB(+remaining) -> EU -> SA -> AI)...")
    engine = se.SimulationEngine(state)
    register_full_engine(engine)

    print("Applying pending operator setpoints...")
    applied_setpoints = apply_pending_operator_setpoints(engine)
    print(f"  {len(applied_setpoints)} setpoint(s) applied: {applied_setpoints}")

    print("Replaying durable measurement promotions...")
    replay_measurement_promotions(engine)

    print("Running one real cycle...")
    cycle_no, published_at = engine.run_cycle(now=now_iso)
    print(f"  Published cycle {cycle_no} at {published_at}.")

    print("Persisting the new snapshot to plant_state_current...")
    n_rows = persist_snapshot(state)
    print(f"  {n_rows} row(s) upserted.")

    elapsed = time.monotonic() - t0
    print(f"=== Continuous cycle run finished in {elapsed:.2f}s ===")
    return elapsed


if __name__ == "__main__":
    main()
