"""
Real Sensor/PLC Migration Groundwork -- Digital Twin Phase 6 (roadmap Part
17), THE FINAL PHASE of the approved roadmap.

Builds the PROMOTION MECHANISM ONLY -- no real sensor is wired here. No
real DOK-ING sensor/PLC data source exists yet anywhere in this project;
this phase proves the mechanism works via a synthetic test, exactly as
the roadmap specifies (task requirement 3).

=== The template, reused as a pattern not as code (task requirement 1) ===
Directly modeled on confirmation_loop.py's own record_confirmation()/
set_confirmed() two-part split: (1) durably record the DECISION to
Supabase, (2) apply it live so every downstream reader is immediately,
automatically affected with zero code changes of its own. The two operate
on genuinely different data, so the CODE differs even though the PATTERN
doesn't: confirmation_loop.py's own assumption_confirmations table
durably stores a STATIC, one-time design-basis VALUE (e.g. steam-to-feed
ratio = 0.4), applied once into uncertainty.py's own in-memory
ASSUMPTIONS dict via set_confirmed(). This module's own
measurement_promotions table durably stores METADATA about a PROMOTION
DECISION (which engine key is now measurement-backed, by what reader
description, since when) -- NOT the constantly-changing live VALUE
itself, which is inherently cyclical (recomputed/re-read every cycle) and
has no business living in a slowly-changing Supabase row. The actual live
application is simulation_engine.py's own new promote_to_measurement()
method (this module's own record_measurement() calls it) -- the SAME
"swap the live source, downstream stays completely oblivious" idea
confirmation_loop.py already proved for the static registry, now built
for the live cyclical Central Simulation Engine instead.

Stated plainly, not overclaimed: replay_promotions_from_db() is a real,
honest AUDIT TRAIL of past promotion decisions (which keys, by whom, when,
what reader description) -- it does NOT auto-reconnect a real reader on a
fresh process, because a reader is a live callable (a function that would,
in reality, poll a PLC/OPC-UA tag), not serializable data. A fresh process
still needs record_measurement() called again with a real, live reader
function once one exists -- this module tracks and surfaces THAT it
happened, not a way to skip doing it again.

=== The core guarantee (task requirement 2) ===
record_measurement(engine, key, reader_fn, ...) preserves the SAME key,
unit, depends_on, and lagged_depends_on the key was already registered
with -- only the function run_cycle() calls for it changes, from a
simulated (Calculated/Estimated) one to reader_fn. Downstream consumers
keep reading the exact same getter and simply receive a Measured entry
instead -- nothing downstream needs to change (proven in this module's
own self-test using SA-001's real H2 reading, whose real downstream
consumer, AI-007's ScadaSnapshot, is never touched).

=== Not a second writer (task requirement 4) ===
record_measurement() calls engine.promote_to_measurement(), which only
ever swaps WHICH FUNCTION run_cycle() calls for one key -- the actual
write into SharedPlantState still only ever happens inside run_cycle()'s
own existing set_entry() call, under the SAME single WriterHandle, with
the SAME validate_entry_shape() enforcement as every other model. Neither
this module nor simulation_engine.py's new method calls set_entry(),
new_writer_handle(), or publish_cycle() anywhere in their own source --
verified directly in this module's own self-test (a real, mechanical
check, the same discipline as AI-013's own read-only enforcement,
Phase 4).
"""
from datetime import datetime, timezone

from . import plant_status as ps
from . import vendor_log

_TABLE = "measurement_promotions"


def _key_str(key):
    return f"{key[0]}|{key[1]}"


def make_synthetic_measurement_reader(value, unit=None, source_note="synthetic test sensor (Phase 6)"):
    """Builds a reader_fn matching the exact shape every model function in
    this project already returns -- the ONLY thing that marks this as a
    real measurement is status=STATUS_MEASURED. This factory exists purely
    for this module's own synthetic self-test (task requirement 3) -- a
    real reader would poll an actual PLC/OPC-UA tag instead of returning a
    fixed constant, but the SHAPE it must return is identical."""
    def reader_fn(get_input):
        return {
            "value": value, "status": ps.STATUS_MEASURED,
            "model": None,  # a real sensor reading has no "model" -- it's not calculated from anything
            "inputs": [],  # a real measurement is its own root, not derived from other entries
            "validation_basis": ps.VALIDATION_NA,
            "confidence_note": f"{source_note}: value={value!r}{f' {unit}' if unit else ''}.",
        }
    return reader_fn


def record_measurement(engine, key, reader_fn, source_description=""):
    """THE core promotion entry point (task requirement 1/2). Two steps,
    same split as confirmation_loop.py's own record_confirmation():
      1. engine.promote_to_measurement(key, reader_fn) -- applies it LIVE,
         immediately, for every subsequent run_cycle().
      2. Durably records the promotion DECISION to Supabase (reusing
         vendor_log.py's own proven client, Phase 4's own AI-011
         precedent -- not duplicated). Degrades gracefully (a real,
         reported failure, not a crash) if the table doesn't exist yet in
         this Supabase project -- see data/measurement_promotions_schema.sql.
    Returns {"applied": True, "logged": bool, "error": str|None}."""
    engine.promote_to_measurement(key, reader_fn)  # step 1 -- always succeeds or raises cleanly
    result = {"applied": True, "logged": False, "error": None}
    try:
        payload = {
            "engine_key": _key_str(key), "source_description": source_description,
            "promoted_at": datetime.now(timezone.utc).isoformat(),
        }
        vendor_log._get_client().table(_TABLE).upsert(payload, on_conflict="engine_key").execute()
        result["logged"] = True
    except Exception as exc:
        result["error"] = str(exc)
    return result


def list_promoted_measurements():
    """Reads back the durable audit trail (task requirement 1's own
    'reuse the pattern' -- confirmation_loop.py's own load_status()
    equivalent). Degrades gracefully to an empty list, not a crash, if the
    table doesn't exist yet."""
    try:
        resp = vendor_log._get_client().table(_TABLE).select("*").execute()
        return resp.data
    except Exception:
        return []


if __name__ == "__main__":
    from . import ai_automation_layer as ai
    from . import tab1_integration

    print("=== Task requirement 3: SA-001's real H2 reading, baseline (simulated) ===")
    snap0, state, engine = tab1_integration.build_live_snapshot(n_cycles=3)
    sa001_before = snap0[("SA-001", "Reading")]
    ai007_before = snap0[("AI-007", "ScadaSnapshot")]["value"]["SA"]
    print(f"  SA-001 before: status={sa001_before['status']}  value={sa001_before['value']}  "
          f"model={sa001_before['source']['model']}")
    print(f"  AI-007's own ScadaSnapshot['SA'] before (a real downstream consumer -- "
          f"ai_automation_layer.py's own get_ai007_scada_snapshot() reads ('SA-001','Reading') "
          f"same-cycle): {ai007_before}")
    assert sa001_before["status"] == ps.STATUS_CALCULATED, f"Expected Calculated baseline, got {sa001_before['status']}"
    assert ai007_before == sa001_before["value"]

    print("\n=== Promoting SA-001 to a real (synthetic) measurement ===")
    SYNTHETIC_H2_PCT = 32.7  # a plausible, distinct value -- deliberately different from the
                              # simulated baseline above, so the swap is unmistakable
    reader = make_synthetic_measurement_reader(SYNTHETIC_H2_PCT, unit="vol%",
                                                source_note="Phase 6 synthetic test sensor for SA-001")
    promo_result = record_measurement(engine, ("SA-001", "Reading"), reader,
                                       source_description="Phase 6 self-test -- synthetic SA-001 H2 sensor")
    print(f"  record_measurement() result: {promo_result}")
    if not promo_result["logged"]:
        print(f"  (Durable audit-trail write did not persist: {promo_result['error']} -- run "
              f"data/measurement_promotions_schema.sql to enable it. The LIVE promotion itself "
              f"({promo_result['applied']}) is independent of this and always succeeded.)")
    assert promo_result["applied"] is True

    print("\n=== Task requirement 2/3: the swap, mechanically verified ===")
    original_spec = engine._models[("SA-001", "Reading")]
    assert original_spec["fn"] is reader, "REGRESSION: the registered function was not actually swapped."
    assert original_spec["unit"] == "vol%", f"REGRESSION: unit changed from registration ({original_spec['unit']})."
    assert original_spec["depends_on"] == (("GC-013", "Gas"),), (
        f"REGRESSION: depends_on changed from registration ({original_spec['depends_on']}) -- the "
        f"engine's own scheduling for this key must stay exactly as it was."
    )
    print(f"  ('SA-001','Reading')'s own registration: unit={original_spec['unit']!r} (unchanged), "
          f"depends_on={original_spec['depends_on']} (unchanged) -- only fn swapped -- PASSED.")

    engine.run_cycle(now="2026-09-11T00:10:00Z")
    snap1 = state.get_snapshot()
    sa001_after = snap1[("SA-001", "Reading")]
    print(f"  SA-001 after promotion: status={sa001_after['status']}  value={sa001_after['value']}  "
          f"cycle={sa001_after['cycle']}")
    assert sa001_after["status"] == ps.STATUS_MEASURED, f"REGRESSION: status should be Measured, got {sa001_after['status']}"
    assert sa001_after["value"] == SYNTHETIC_H2_PCT
    assert sa001_after["unit"] == "vol%", "REGRESSION: the published entry's own unit changed."
    assert sa001_after["cycle"] == state.published_cycle, (
        "REGRESSION: SA-001's own entry wasn't published on the SAME cycle as everything else -- "
        "evidence of a second, out-of-band write path."
    )
    print("  PASSED -- status flipped Calculated -> Measured, value/unit genuinely changed, "
          "published on the SAME cycle number as every other entry (proving it went through the "
          "SAME single-writer run_cycle() flow, not a side channel).")

    print("\n=== Task requirement 2: zero downstream code change -- AI-007 automatically reflects it ===")
    ai007_after = snap1[("AI-007", "ScadaSnapshot")]["value"]["SA"]
    print(f"  AI-007's own ScadaSnapshot['SA'] after (ai_automation_layer.py NOT touched, NOT "
          f"re-imported, NOT redefined -- the SAME get_ai007_scada_snapshot() function object "
          f"registered back in build_live_snapshot()): {ai007_after}")
    assert ai007_after == SYNTHETIC_H2_PCT, (
        f"REGRESSION: AI-007's own downstream reading ({ai007_after}) doesn't reflect SA-001's "
        f"new Measured value ({SYNTHETIC_H2_PCT}) -- the promotion did not propagate."
    )
    print("  PASSED -- AI-007's own real downstream consumer automatically received the Measured "
          "value with ZERO code changes anywhere in ai_automation_layer.py.")

    print("\n=== Task requirement 3: the SAME correctness checks apply identically ===")
    full_entry = state.get_entry(("SA-001", "Reading"))
    ps.validate_entry_shape(("SA-001", "Reading"), full_entry)  # raises on any violation
    print("  validate_entry_shape() accepts the Measured entry -- PASSED (same mechanical check, "
          "no special-casing for Measured).")
    assert ps.is_fully_traceable(snap1, ("SA-001", "Reading")), (
        "REGRESSION: a real Measured leaf (no inputs, by construction) should be trivially fully "
        "traceable -- it IS its own root, correctly, not Missing."
    )
    print("  is_fully_traceable(('SA-001','Reading')) == True -- PASSED (a real measurement is "
          "its own root; resolve_provenance_chain() needed no special-casing for Measured either).")
    chain = ps.resolve_provenance_chain(snap1, ("AI-007", "ScadaSnapshot"))
    sa001_node = next(n for n in chain if n["key"] == ("SA-001", "Reading"))
    assert sa001_node["status"] == ps.STATUS_MEASURED
    print("  resolve_provenance_chain() from AI-007's own ScadaSnapshot still reaches SA-001's "
          "entry correctly, now showing Measured -- PASSED, same provenance machinery, no changes.")

    print("\n=== Task requirement 4: confirmed NOT a second writer (mechanical, not asserted) ===")
    import ast
    import inspect
    import textwrap
    _BANNED_CALLS = {"set_entry", "new_writer_handle", "publish_cycle", "begin_cycle", "discard_cycle"}

    def _called_names(fn):
        """AST-based, not a raw substring scan -- deliberately, found necessary
        while writing this test: a naive substring search over inspect.getsource()
        also matches these names appearing in the function's own DOCSTRING (which
        explains the mechanism in prose, using these exact words) as a false
        positive. Walking real ast.Call nodes only flags actual invocations.
        textwrap.dedent() first -- engine.promote_to_measurement is a class
        method, so inspect.getsource() returns it indented, which ast.parse()
        cannot handle directly."""
        tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
        calls = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                target = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", None)
                if target:
                    calls.add(target)
        return calls

    calls_engine_method = _called_names(engine.promote_to_measurement)
    calls_this_module = _called_names(record_measurement)
    violations_engine = calls_engine_method & _BANNED_CALLS
    violations_module = calls_this_module & _BANNED_CALLS
    assert not violations_engine, f"REGRESSION: promote_to_measurement() actually CALLS {violations_engine} -- a second write path."
    assert not violations_module, f"REGRESSION: record_measurement() actually CALLS {violations_module} -- a second write path."
    print("  AST-walked promote_to_measurement()'s and record_measurement()'s own real function "
          "calls (not a docstring text match): neither actually CALLS set_entry/new_writer_handle/"
          "publish_cycle/begin_cycle/discard_cycle anywhere -- "
          "PASSED. The only write remains run_cycle()'s own existing set_entry() call, under the "
          "SAME single WriterHandle every other model already uses.")

    print("\n=== Second representative variable: EU-009's electrical balance ===")
    snap2, state2, engine2 = tab1_integration.build_live_snapshot(n_cycles=3)
    eu009_before = snap2[("EU-009", "GridBalance")]
    eu010_before = snap2[("EU-010", "UPS")]["value"]["net_kw_seen"]
    print(f"  EU-009 before: status={eu009_before['status']}  net_kw={eu009_before['value']['net_kw']}")
    print(f"  EU-010's own real downstream consumer (net_kw_seen): {eu010_before}")
    SYNTHETIC_GRID_BALANCE = {"generation_kw": 61.0, "consumption_kw": 12.0, "net_kw": 49.0}
    reader2 = make_synthetic_measurement_reader(SYNTHETIC_GRID_BALANCE, unit="kW",
                                                 source_note="Phase 6 synthetic test sensor for EU-009")
    record_measurement(engine2, ("EU-009", "GridBalance"), reader2,
                        source_description="Phase 6 self-test -- synthetic EU-009 revenue meter")
    engine2.run_cycle(now="2026-09-11T00:20:00Z")
    snap3 = state2.get_snapshot()
    eu009_after = snap3[("EU-009", "GridBalance")]
    eu010_after = snap3[("EU-010", "UPS")]["value"]["net_kw_seen"]
    assert eu009_after["status"] == ps.STATUS_MEASURED and eu009_after["value"] == SYNTHETIC_GRID_BALANCE
    assert eu010_after == SYNTHETIC_GRID_BALANCE["net_kw"], (
        f"REGRESSION: EU-010's own downstream reading ({eu010_after}) doesn't reflect EU-009's new "
        f"Measured net_kw ({SYNTHETIC_GRID_BALANCE['net_kw']})."
    )
    print(f"  EU-009 after: status={eu009_after['status']}  net_kw={eu009_after['value']['net_kw']}")
    print(f"  EU-010's own real downstream consumer after (eu_utilities_chp.py NOT touched): {eu010_after}")
    print("  PASSED -- the SAME mechanism, a SECOND independent representative variable, a SECOND "
          "real downstream consumer (EU-010, untouched) -- confirms this isn't a one-off special case.")

    print("\n=== Durable audit trail ===")
    promoted = list_promoted_measurements()
    print(f"  list_promoted_measurements(): {len(promoted)} row(s) -- {promoted}")

    print("\nAll measurement_promotion.py self-tests PASSED.")
