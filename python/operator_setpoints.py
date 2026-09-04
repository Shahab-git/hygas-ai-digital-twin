"""
Operator Setpoints -- Continuous Simulation Runtime, Section 5
(docs/continuous_runtime_design.md, approved design).

Builds ONLY the mechanism that design specifies: a durable table
(plant_operator_setpoints, see data/plant_operator_setpoints_schema.sql)
holding a pending-or-applied operator setpoint request, plus the tiny
reader-factory function the continuous runtime's own driver script
(scripts/run_continuous_cycle.py) uses to APPLY a pending request via
SimulationEngine.promote_to_measurement() -- the SAME existing,
unmodified method Phase 6's measurement_promotion.py already uses for
sensor promotion, reused here for a second purpose, not a new engine
capability (design doc section 5's own explicit point: "an operator
setpoint... simply already exists in the published state" is a case
_topological_order()'s own docstring already names).

Deliberately a SEPARATE, small module from measurement_promotion.py (the
design doc's own explicit call, section 5 item 3, "plausibly a new, small
module rather than crowding measurement_promotion.py, since it serves a
conceptually different purpose despite the mechanical similarity"):
mechanically similar (both swap which function run_cycle() calls for one
key) but conceptually different -- this table records an OPERATOR's own
design/setpoint CHOICE, not a sensor's real MEASURED reading, and the two
must never be confused (status=Assumed here, never status=Measured).

NOT built here, out of this task's own explicit scope: the Tab 1
operator-input widget itself (a future, separate piece of work). This
module and its own table are real and functional the moment any writer
calls request_setpoint() or inserts a row directly -- nothing here
depends on that future widget existing.
"""
from datetime import datetime, timezone

from . import plant_status as ps
from . import vendor_log

_TABLE = "plant_operator_setpoints"


def key_to_str(key):
    """(equipment_id, category) -> 'equipment_id|category' -- the SAME
    string format measurement_promotion.py's own _key_str() already uses
    for its own table's engine_key column, kept consistent, not
    reinvented (both tables use the identical convention)."""
    return f"{key[0]}|{key[1]}"


def key_from_str(key_str):
    """The inverse of key_to_str() -- needed here (and not in
    measurement_promotion.py, which never reads its own engine_key back
    into a tuple) because THIS module's own caller
    (scripts/run_continuous_cycle.py) reads engine_key back OUT of
    Supabase as a plain string and must reconstruct the real
    (equipment_id, category) tuple key promote_to_measurement() itself
    requires."""
    equipment_id, category = key_str.split("|", 1)
    return (equipment_id, category)


def make_operator_setpoint_reader(value, source_note):
    """Builds a reader_fn matching the exact shape every model function in
    this project already returns -- mirrors
    measurement_promotion.make_synthetic_measurement_reader()'s own shape
    exactly (design doc section 5's own code block), with one real,
    deliberate difference: status=STATUS_ASSUMED, never STATUS_MEASURED --
    an operator-entered setpoint is a real design choice, not a sensor
    reading, and must never be mistaken for one downstream."""
    def reader_fn(get_input):
        return {
            "value": value, "status": ps.STATUS_ASSUMED,
            "model": None,  # an operator setpoint has no "model" -- it's chosen, not calculated
            "inputs": [],   # it is its own root, not derived from other entries
            "validation_basis": ps.VALIDATION_NA,
            "confidence_note": source_note,
        }
    return reader_fn


def list_pending_setpoints():
    """Every row with applied_at IS NULL -- what the continuous runtime's
    own driver script applies at the start of each tick (design doc
    section 5, step 4). Degrades gracefully to an empty list, not a
    crash, if the table doesn't exist yet in this Supabase project (same
    discipline as measurement_promotion.list_promoted_measurements())."""
    try:
        resp = (
            vendor_log._get_client().table(_TABLE).select("*")
            .is_("applied_at", "null").execute()
        )
        return resp.data
    except Exception:
        return []


def mark_setpoint_applied(engine_key_str):
    """Stamps one row's own applied_at = now(), after the driver script
    has actually applied it via promote_to_measurement() -- so the SAME
    row isn't re-applied (and re-logged as a fresh request) every
    subsequent tick. Degrades gracefully (a real, reported failure via the
    return value, not a crash) if the write itself fails."""
    try:
        vendor_log._get_client().table(_TABLE).update(
            {"applied_at": datetime.now(timezone.utc).isoformat()}
        ).eq("engine_key", engine_key_str).execute()
        return True
    except Exception:
        return False


def request_setpoint(engine_key_tuple, value, requested_by=""):
    """Durably records a NEW pending setpoint request -- upserted on
    engine_key (a fresh request for the same key replaces the still-
    pending one, per the table's own schema comment), applied_at left
    null so the driver script's own list_pending_setpoints() picks it up
    on its next tick. NOT called anywhere in this codebase yet (no UI
    writer exists -- see module docstring); provided so a future Tab 1
    widget has a single, real, already-tested entry point to call rather
    than writing to Supabase directly itself. Raises on failure -- the
    caller decides how to surface that (a future UI would show a real
    error, not silently drop the request)."""
    payload = {
        "engine_key": key_to_str(engine_key_tuple), "value": value,
        "requested_by": requested_by,
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "applied_at": None,
    }
    resp = vendor_log._get_client().table(_TABLE).upsert(payload, on_conflict="engine_key").execute()
    return resp.data[0] if resp.data else None


if __name__ == "__main__":
    from . import shared_plant_state as sps
    from . import simulation_engine as se

    print("=== key_to_str()/key_from_str() round-trip ===")
    key = ("GA-001-INPUT", "equivalence_ratio")
    key_str = key_to_str(key)
    assert key_str == "GA-001-INPUT|equivalence_ratio", f"REGRESSION: {key_str!r}"
    assert key_from_str(key_str) == key, f"REGRESSION: round-trip failed, got {key_from_str(key_str)!r}"
    print(f"  {key!r} -> {key_str!r} -> {key_from_str(key_str)!r} -- PASSED.")

    print("\n=== make_operator_setpoint_reader(): shape + status (task requirement: Assumed, never Measured) ===")
    reader = make_operator_setpoint_reader(0.30, "operator setpoint test: ER=0.30")
    result = reader(lambda k: None)
    assert result["status"] == ps.STATUS_ASSUMED, f"REGRESSION: expected Assumed, got {result['status']}"
    assert result["status"] != ps.STATUS_MEASURED, "REGRESSION: an operator setpoint must NEVER read as Measured."
    assert result["value"] == 0.30
    assert result["model"] is None and result["inputs"] == []
    print(f"  status={result['status']} (Assumed, not Measured) value={result['value']} -- PASSED.")

    print("\n=== Mechanically applied via promote_to_measurement() -- the SAME existing, unmodified method ===")
    state = sps.SharedPlantState()
    engine = se.SimulationEngine(state)

    def _default_er(get_input):
        return {
            "value": 0.25, "status": ps.STATUS_ASSUMED, "inputs": [],
            "validation_basis": ps.VALIDATION_NA, "confidence_note": "default baseline",
        }

    engine.register_model(("GA-001-INPUT", "equivalence_ratio"), _default_er, unit="dimensionless")
    engine.run_cycle(now="2026-09-12T00:00:00Z")
    before = state.get_entry(("GA-001-INPUT", "equivalence_ratio"))
    assert before["value"] == 0.25, f"REGRESSION: baseline value should be 0.25, got {before['value']}"
    print(f"  Before promotion: value={before['value']} (the registered default).")

    engine.promote_to_measurement(("GA-001-INPUT", "equivalence_ratio"), reader)
    original_spec = engine._models[("GA-001-INPUT", "equivalence_ratio")]
    assert original_spec["fn"] is reader, "REGRESSION: the registered function was not actually swapped."
    assert original_spec["unit"] == "dimensionless", (
        f"REGRESSION: unit changed from registration ({original_spec['unit']})."
    )
    engine.run_cycle(now="2026-09-12T01:00:00Z")
    after = state.get_entry(("GA-001-INPUT", "equivalence_ratio"))
    assert after["value"] == 0.30, f"REGRESSION: expected the operator setpoint (0.30), got {after['value']}"
    assert after["status"] == ps.STATUS_ASSUMED
    print(f"  After promotion + one more cycle: value={after['value']} (the operator setpoint), "
          f"status={after['status']} -- PASSED, no new engine capability was needed.")

    print("\n=== Supabase-backed functions degrade gracefully if the table doesn't exist yet ===")
    pending = list_pending_setpoints()
    assert isinstance(pending, list), "REGRESSION: list_pending_setpoints() must always return a list, never raise."
    applied_ok = mark_setpoint_applied("SYNTHETIC-TEST-KEY|not-a-real-row")
    assert isinstance(applied_ok, bool), "REGRESSION: mark_setpoint_applied() must always return a bool, never raise."
    print(f"  list_pending_setpoints() -> {len(pending)} row(s) (empty list if the table doesn't exist yet -- "
          f"run data/plant_operator_setpoints_schema.sql to enable it). "
          f"mark_setpoint_applied() on a synthetic key -> {applied_ok} -- PASSED, neither call raised.")

    print("\nAll operator_setpoints.py self-tests PASSED.")
