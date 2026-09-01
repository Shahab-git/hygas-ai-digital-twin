"""
Central Simulation / Digital Twin Engine v1 -- Digital Twin Phase 0
(Foundational Infrastructure).

Implements the executor shell from docs/digital_twin_engineering_plan.md's
Section 6 (the 12-step update cycle) and Section 6.0 (responsibility
boundaries): the ONE orchestrator that evaluates a registered set of
equipment models in dependency order and publishes their results into a
SharedPlantState. Per Section 6.0, this is the only thing that computes the
Shared Plant State -- every Tab, Tab 1, and the AI-012/AI-013 intelligence
layer are readers of what this engine produces, never producers of it.

THIS MODULE CONTAINS NO EQUIPMENT PHYSICS. Phase 0 registers only clearly-
labeled synthetic test-fixture models (see this file's own __main__ block) to
exercise the executor shell -- GA-001, the Gas Cleaning train, and every real
equipment model are Phase 1+ work, explicitly out of scope here per the task
that created this file. Nothing in this module imports kinetics.py, psa.py,
chp.py, or gasifier_mass_balance.py, and none of them is touched by it.

WHAT THIS ENGINE ACTUALLY DOES, matching the plan's 12 steps at the shell
level (a later phase's real equipment models plug into steps 2-4 without
this shell changing):

  1. Inputs enter the system      -- out of scope for the shell itself; a
     registered model's `depends_on`/`lagged_depends_on` keys are exactly
     where a real model would read a live setpoint or boundary condition.
  2. Equipment state evaluation   -- not built in Phase 0 (no equipment
     states exist yet); the hook point is `register_model`'s eventual state-
     gating, left for a later phase per the task's explicit "do not touch
     any equipment model" instruction.
  3. Equipment models execute     -- run_cycle() below, in topologically-
     sorted dependency order (Kahn's algorithm, a standard, textbook graph
     algorithm -- not invented here).
  4. Outputs propagate downstream -- each model's result is staged
     immediately, so the NEXT model in this same cycle's order can read it
     via get_staged_entry().
  5. Downstream recalculation     -- falls out of steps 3-4 automatically,
     exactly as the plan's own Section 6 states (nothing extra to build).
  6. Utility/circular dependencies -- register_model's `lagged_depends_on`
     mechanism (see below), built generically now even though the real
     GC<->EU-008 pair does not exist until Phase 2, per this phase's explicit
     instruction to build the MECHANISM now against a synthetic pair.
  7-11. Feedback, per-Tab results, integrated state, alarms -- all Phase 1+
     work layered ON TOP of this shell; nothing in this file assumes they
     exist.
  12. Logging/persistence          -- SharedPlantState.publish_cycle()'s own
     cycle number + timestamp IS the per-cycle record; a durable log
     (AI-011's role, Supabase-backed like vendor_log.py/confirmation_loop.py)
     is explicitly Phase 4 work, not built here.

THE ONE-CYCLE LAG MECHANISM, generalized (Section 6 step 6 / roadmap Part 8):
a model registered with a `lagged_depends_on` key reads that key's value from
the PREVIOUS published cycle (SharedPlantState.get_entry(), which always
reflects the last publish, never the in-progress one), rather than the
current cycle's staging area. This deliberately excludes lagged edges from
the topological-sort graph -- they can never create a same-cycle ordering
cycle by construction, which is the actual mechanism (not a special case bolted
on after the fact) that lets a genuinely circular real-world dependency (like
Gas Cleaning's cooling demand and the Cooling Tower's own duty, Phase 2) be
represented at all without an unsolvable same-cycle deadlock.

STRUCTURAL MISSING PROPAGATION: before calling a registered model's function,
the engine checks every one of its declared SAME-CYCLE dependencies
(depends_on). If ANY is currently Missing, the model function is NOT called
at all -- the engine writes a Missing entry for that model's own output,
automatically, naming which upstream key(s) were the blocker. A model
function therefore never has to contain its own "what if my required
same-cycle input is Missing" branch for that case; it is simply never
invoked; a later cycle where the same problem is cleared runs the model
function normally. This is the concrete meaning of "returns Missing by the
getter contract, not per-model special-case logic" for the ordinary,
non-lagged case, which is the overwhelming majority of real dependencies
(e.g. GC-002 needing GC-001's flow).

LAGGED dependencies (lagged_depends_on) are the one deliberate exception,
found necessary while building this module's own test, not designed in
speculatively: a Missing lagged read (no previous cycle exists yet for that
key, or that key itself was Missing last cycle) is NOT hard-blocked -- it is
handed to the model function as a real, Missing-shaped entry via get_input(),
and the model function itself decides how to bootstrap. Hard-blocking lagged
reads the same way as same-cycle ones would deadlock any two-sided lagged
pair permanently (each side eternally waiting on the other's first value,
which neither could ever produce first) -- this is exactly the kind of
"real Cooling Tower doesn't switch off just because it's cycle 1, it starts
at a sensible default" judgment call a genuine utility-balance model has to
make anyway, so it is left to the model, not silently resolved by the engine
guessing a default on the model's behalf.
"""
from . import plant_status as ps
from . import shared_plant_state as sps


class DependencyCycleError(Exception):
    """Raised when the SAME-CYCLE (non-lagged) dependency graph contains a
    genuine cycle -- a real modeling bug (two models needing each other's
    output within the same pass), distinct from a legitimate circular
    real-world relationship, which must be declared via lagged_depends_on
    instead. Never silently resolved -- the whole point of raising this is
    that a real cycle needs a human decision (is this actually supposed to
    be a lagged pair?), not an engine guess."""


class SimulationEngine:
    """The one orchestrator. See module docstring."""

    def __init__(self, state):
        if not isinstance(state, sps.SharedPlantState):
            raise TypeError("SimulationEngine requires a shared_plant_state.SharedPlantState instance.")
        self._state = state
        self._handle = state.new_writer_handle()
        self._models = {}  # key -> {"fn", "unit", "depends_on", "lagged_depends_on"}

    def register_model(self, key, fn, unit, depends_on=(), lagged_depends_on=()):
        """Registers one equipment model's output slot.

        key: the (equipment_id, category)-style identifier this model
          produces -- must be unique across all registered models.
        fn: callable(get_input) -> dict with keys value/status/model/inputs/
          validation_basis/confidence_note (NOT unit/cycle/timestamp -- the
          engine supplies those). Only ever called when every declared
          dependency currently resolves to a non-Missing entry.
        unit: this model's own output unit, stated at registration time so
          the engine can still write a correctly-shaped (if Missing) entry
          even on a cycle where fn is never called.
        depends_on: keys this model needs from THIS SAME cycle, already
          computed earlier in topological order. Participates in cycle
          detection.
        lagged_depends_on: keys this model reads from the PREVIOUS published
          cycle -- deliberately excluded from the ordering graph, the
          mechanism that breaks a genuine circular real-world dependency.
        """
        if key in self._models:
            raise ValueError(f"register_model: {key!r} is already registered.")
        self._models[key] = {
            "fn": fn, "unit": unit,
            "depends_on": tuple(depends_on), "lagged_depends_on": tuple(lagged_depends_on),
        }

    def _topological_order(self):
        """Kahn's algorithm over the same-cycle (depends_on) edges only --
        a standard, textbook algorithm for exactly this problem, not
        invented here. Raises DependencyCycleError, naming every key still
        stuck with unresolved in-edges, if the graph isn't a DAG."""
        in_degree = {k: 0 for k in self._models}
        edges = {k: [] for k in self._models}  # dependency -> [dependents]
        for key, spec in self._models.items():
            for dep in spec["depends_on"]:
                if dep not in self._models:
                    # A same-cycle dependency on a key nobody registered a model
                    # for is not itself an error here -- it may be an external
                    # input (an operator setpoint, a design-basis constant) that
                    # simply already exists in the published state from before
                    # this engine even started. It does not participate in
                    # ordering since nothing THIS engine runs produces it.
                    continue
                edges[dep].append(key)
                in_degree[key] += 1

        ready = [k for k, deg in in_degree.items() if deg == 0]
        order = []
        while ready:
            # Sort for determinism -- registration order alone isn't stable
            # across dict implementations well enough to make tests reproducible.
            ready.sort(key=str)
            node = ready.pop(0)
            order.append(node)
            for dependent in edges[node]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    ready.append(dependent)

        if len(order) != len(self._models):
            stuck = [k for k in self._models if k not in order]
            raise DependencyCycleError(
                f"Same-cycle dependency graph is not a DAG -- these keys have an unresolved "
                f"circular dependency and were never scheduled: {stuck}. If this is a genuine "
                f"real-world circular relationship (like a utility-balance pair), declare it via "
                f"lagged_depends_on instead of depends_on -- see module docstring."
            )
        return order

    def run_cycle(self, now=None):
        """Executes exactly one full update cycle: opens a new staging area,
        runs every registered model in dependency order (skipping, with an
        automatic Missing entry, any model whose declared inputs aren't all
        resolvable), and publishes. Returns (cycle_number, published_at)."""
        order = self._topological_order()
        self._state.begin_cycle(self._handle, now=now)

        for key in order:
            spec = self._models[key]
            blocking = []
            resolved_inputs = []

            for dep in spec["depends_on"]:
                resolved_inputs.append(dep)
                entry = self._state.get_staged_entry(self._handle, dep)
                if entry is None:
                    # Not produced by any model this engine runs, and not
                    # already sitting in last cycle's published state either
                    # -- an external input nobody has ever supplied.
                    entry = self._state.get_entry(dep)
                if entry["status"] == ps.STATUS_MISSING:
                    blocking.append(dep)

            # NOTE: lagged_depends_on deliberately does NOT participate in
            # hard blocking. A lagged read reflects the PREVIOUS published
            # cycle -- on cycle 1 (or any cycle before that key has ever been
            # produced) there IS no previous value, which is a genuine,
            # expected bootstrap condition for a converging pair (roadmap
            # Part 8), not an unresolvable failure the way a missing SAME-
            # CYCLE input is. Forcing lagged reads through the same hard-
            # block rule as depends_on would deadlock any two-sided lagged
            # pair forever (each side waiting on the other's first value,
            # which neither can ever produce) -- caught empirically while
            # building this test. So: a Missing lagged read is handed to the
            # model function AS a Missing-shaped entry via get_input(), and
            # the model decides how to bootstrap (exactly the judgment call
            # a REAL utility-balance model has to make too -- a real cooling
            # tower doesn't switch off because it's cycle 1, it starts at
            # some sensible default). This is the one place a model function
            # is allowed to look at a Missing status itself, and only for a
            # lagged input, never for a same-cycle depends_on one.

            resolved_inputs.extend(spec["lagged_depends_on"])

            if blocking:
                self._state.set_entry(
                    self._handle, key, value=None, unit=spec["unit"], status=ps.STATUS_MISSING,
                    model=_dotted_name(spec["fn"]), inputs=resolved_inputs,
                    validation_basis=ps.VALIDATION_NA,
                    missing_reason=(
                        f"upstream input(s) {blocking} are Missing this cycle -- "
                        f"{key!r}'s model was not invoked, per structural Missing propagation"
                    ),
                )
                continue

            def get_input(dep_key, _spec=spec):
                if dep_key in _spec["lagged_depends_on"]:
                    return self._state.get_entry(dep_key)
                staged = self._state.get_staged_entry(self._handle, dep_key)
                return staged if staged is not None else self._state.get_entry(dep_key)

            result = spec["fn"](get_input)
            self._state.set_entry(
                self._handle, key, value=result["value"], unit=spec["unit"], status=result["status"],
                model=result.get("model") or _dotted_name(spec["fn"]),
                inputs=result.get("inputs", resolved_inputs),
                validation_basis=result.get("validation_basis", ps.VALIDATION_NA),
                confidence_note=result.get("confidence_note", ""),
                missing_reason=result.get("missing_reason"),
            )

        return self._state.publish_cycle(self._handle)


def _dotted_name(fn):
    module = getattr(fn, "__module__", "?")
    name = getattr(fn, "__qualname__", getattr(fn, "__name__", repr(fn)))
    return f"{module}.{name}"


if __name__ == "__main__":
    # ------------------------------------------------------------------
    # EVERY model function below is a clearly-labeled SYNTHETIC TEST
    # FIXTURE -- named and commented as such throughout, on purpose, so
    # none of it could ever be mistaken for a real equipment model later.
    # No physics, no real equipment, no fabricated engineering claim.
    # ------------------------------------------------------------------

    print("=== Exit criterion: a dummy two-item chain (A -> B) runs a full cycle, ===")
    print("=== publishes to the Shared Plant State, and is traced end to end     ===")
    state = sps.SharedPlantState()
    engine = SimulationEngine(state)

    def _dummy_test_fixture_model_a(get_input):
        """SYNTHETIC TEST FIXTURE, not a real equipment model. Produces a
        fixed value -- exists only to give _dummy_test_fixture_model_b
        something real to depend on."""
        return {
            "value": 10.0, "status": ps.STATUS_MEASURED,
            "validation_basis": ps.VALIDATION_NA,
            "confidence_note": "Phase 0 synthetic test fixture -- not a real measurement.",
        }

    def _dummy_test_fixture_model_b(get_input):
        """SYNTHETIC TEST FIXTURE, not a real equipment model. Doubles A's
        value -- exists only to exercise the executor's same-cycle
        dependency resolution and provenance chain."""
        a = get_input(("DUMMY-A", "Outputs"))
        return {
            "value": a["value"] * 2.0, "status": ps.STATUS_CALCULATED,
            "model": "simulation_engine.__main__._dummy_test_fixture_model_b",
            "inputs": [("DUMMY-A", "Outputs")],
            "validation_basis": ps.VALIDATION_INTERNAL_CONSISTENCY,
            "confidence_note": "Phase 0 synthetic test fixture -- doubles A, nothing physical.",
        }

    engine.register_model(("DUMMY-A", "Outputs"), _dummy_test_fixture_model_a, unit="synthetic-unit")
    engine.register_model(
        ("DUMMY-B", "Outputs"), _dummy_test_fixture_model_b, unit="synthetic-unit",
        depends_on=[("DUMMY-A", "Outputs")],
    )

    cycle_no, published_at = engine.run_cycle(now="2026-09-01T12:00:00Z")
    snapshot = state.get_snapshot()

    print(f"  Published cycle {cycle_no} at {published_at}")
    a_entry = snapshot[("DUMMY-A", "Outputs")]
    b_entry = snapshot[("DUMMY-B", "Outputs")]
    print(f"  DUMMY-A: value={a_entry['value']} status={a_entry['status']}")
    print(f"  DUMMY-B: value={b_entry['value']} status={b_entry['status']} model={b_entry['source']['model']}")

    assert a_entry["status"] == ps.STATUS_MEASURED and a_entry["value"] == 10.0
    assert b_entry["status"] == ps.STATUS_CALCULATED and b_entry["value"] == 20.0
    assert b_entry["source"]["inputs"] == [("DUMMY-A", "Outputs")]

    chain = ps.resolve_provenance_chain(snapshot, ("DUMMY-B", "Outputs"))
    chain_keys = {n["key"] for n in chain}
    print(f"  Automated provenance trace from DUMMY-B: {sorted(str(k) for k in chain_keys)}")
    assert chain_keys == {("DUMMY-B", "Outputs"), ("DUMMY-A", "Outputs")}, (
        "REGRESSION: automated provenance trace did not reach both nodes of the dummy A->B chain."
    )
    assert ps.is_fully_traceable(snapshot, ("DUMMY-B", "Outputs")), (
        "REGRESSION: the dummy A->B chain, rooted entirely in a Measured value, should be fully traceable."
    )
    print("EXIT CRITERION PASSED -- dummy A->B chain ran a full cycle, published, and its "
          "Missing/Calculated status traces end to end, automatically (not just asserted).")

    print("\n=== Structural Missing propagation: a model with a Missing dependency is never even called ===")
    state2 = sps.SharedPlantState()
    engine2 = SimulationEngine(state2)
    _fn_c_was_called = {"value": False}

    def _dummy_test_fixture_model_missing_source(get_input):
        """SYNTHETIC TEST FIXTURE. Deliberately produces Missing, with a
        stated reason -- simulating an upstream item that genuinely cannot
        compute (the HB-010-style case), not an error."""
        return {
            "value": None, "status": ps.STATUS_MISSING,
            "missing_reason": "synthetic test: no required data available",
        }

    def _dummy_test_fixture_model_downstream_of_missing(get_input):
        """SYNTHETIC TEST FIXTURE. Should NEVER actually run in this test --
        its own body sets a flag if it does, which the test asserts False."""
        _fn_c_was_called["value"] = True
        return {"value": 123.0, "status": ps.STATUS_CALCULATED}

    engine2.register_model(("DUMMY-MISSING", "Outputs"), _dummy_test_fixture_model_missing_source, unit="-")
    engine2.register_model(
        ("DUMMY-DOWNSTREAM", "Outputs"), _dummy_test_fixture_model_downstream_of_missing, unit="-",
        depends_on=[("DUMMY-MISSING", "Outputs")],
    )
    engine2.run_cycle(now="2026-09-01T12:01:00Z")
    snap2 = state2.get_snapshot()
    downstream_entry = snap2[("DUMMY-DOWNSTREAM", "Outputs")]
    assert not _fn_c_was_called["value"], (
        "REGRESSION: a model function was called even though its declared dependency was Missing -- "
        "propagation must be structural (the engine skips the call), not left to per-model logic."
    )
    assert downstream_entry["status"] == ps.STATUS_MISSING
    assert "DUMMY-MISSING" in str(downstream_entry["missing_reason"])
    print(f"  DUMMY-DOWNSTREAM missing_reason: {downstream_entry['missing_reason']}")
    print("PASSED -- downstream model was never invoked; Missing propagated automatically, by contract.")

    print("\n=== A genuine same-cycle dependency cycle is rejected, not silently resolved ===")
    state3 = sps.SharedPlantState()
    engine3 = SimulationEngine(state3)

    def _dummy_test_fixture_model_x(get_input):
        return {"value": 1.0, "status": ps.STATUS_CALCULATED}

    def _dummy_test_fixture_model_y(get_input):
        return {"value": 1.0, "status": ps.STATUS_CALCULATED}

    engine3.register_model(("DUMMY-X", "Outputs"), _dummy_test_fixture_model_x, unit="-",
                            depends_on=[("DUMMY-Y", "Outputs")])
    engine3.register_model(("DUMMY-Y", "Outputs"), _dummy_test_fixture_model_y, unit="-",
                            depends_on=[("DUMMY-X", "Outputs")])
    try:
        engine3.run_cycle(now="2026-09-01T12:02:00Z")
        raise AssertionError("REGRESSION: a genuine same-cycle circular dependency was NOT rejected.")
    except DependencyCycleError as e:
        print(f"PASSED -- correctly rejected: {e}")

    print(
        "\n=== One-cycle-lag mechanism: a SYNTHETIC converging pair (the real GC<->EU-008 pair "
        "doesn't exist until Phase 2) ==="
    )
    state4 = sps.SharedPlantState()
    engine4 = SimulationEngine(state4)

    # A fixed external "design target" both sides are converging toward --
    # analogous to how a real utility-balance pair converges toward the
    # ACTUAL steady demand once both sides have exchanged a few cycles'
    # worth of lagged readings, per the plan's Section 10 limitation 4 /
    # roadmap Part 8.

    def _dummy_test_fixture_seed(get_input):
        """SYNTHETIC TEST FIXTURE. A fixed external target value, standing in
        for a real design-basis constant."""
        return {"value": 100.0, "status": ps.STATUS_ASSUMED, "validation_basis": ps.VALIDATION_INTERNAL_CONSISTENCY}

    def _lagged_value_or_bootstrap(get_input, key, bootstrap_value, bootstrap_note):
        """Shared helper for the two fixtures below: reads a lagged input,
        falling back to an explicit, stated bootstrap default on the first
        cycle (when the lagged read is genuinely Missing -- no prior cycle
        exists for that key yet). Not engine machinery -- a convenience
        local to these two SYNTHETIC TEST FIXTURES only."""
        entry = get_input(key)
        if entry["status"] == ps.STATUS_MISSING:
            return bootstrap_value, bootstrap_note
        return entry["value"], ""

    def _dummy_test_fixture_demand_side(get_input):
        """SYNTHETIC TEST FIXTURE, standing in for a Gas-Cleaning-style
        'cooling demand' item: damps halfway toward LAST cycle's supply-side
        reading each cycle (the lagged read). On the very first cycle, no
        prior supply reading exists yet -- an honest, explicit bootstrap
        default (0.0, "no prior data, conservative start") is used instead
        of silently treating Missing as zero or crashing."""
        supply_prev_value, note = _lagged_value_or_bootstrap(
            get_input, ("DUMMY-SUPPLY-SIDE", "Outputs"), 0.0,
            "cycle-1 bootstrap: no prior SUPPLY-SIDE reading, started at 0.0",
        )
        seed = get_input(("DUMMY-SEED", "Outputs"))
        new_value = supply_prev_value + 0.5 * (seed["value"] - supply_prev_value)
        return {
            "value": new_value, "status": ps.STATUS_CALCULATED,
            "inputs": [("DUMMY-SEED", "Outputs"), ("DUMMY-SUPPLY-SIDE", "Outputs")],
            "validation_basis": ps.VALIDATION_INTERNAL_CONSISTENCY, "confidence_note": note,
        }

    def _dummy_test_fixture_supply_side(get_input):
        """SYNTHETIC TEST FIXTURE, standing in for a Cooling-Tower-style
        'supply duty' item: damps halfway toward LAST cycle's demand-side
        reading AND its own last cycle's output (a lagged SELF-dependency --
        a real, legitimate pattern for any damped/filtered response, not a
        quirk of this test) -- the symmetric counterpart to the demand
        side's own damped-movement shape, which is what produces genuine,
        gradual convergence instead of a one-sided jump-to-target."""
        demand_prev_value, note1 = _lagged_value_or_bootstrap(
            get_input, ("DUMMY-DEMAND-SIDE", "Outputs"), 0.0,
            "cycle-1 bootstrap: no prior DEMAND-SIDE reading, started at 0.0",
        )
        own_prev_value, note2 = _lagged_value_or_bootstrap(
            get_input, ("DUMMY-SUPPLY-SIDE", "Outputs"), 0.0,
            "cycle-1 bootstrap: no prior own reading, started at 0.0",
        )
        new_value = own_prev_value + 0.5 * (demand_prev_value - own_prev_value)
        return {
            "value": new_value, "status": ps.STATUS_CALCULATED,
            "inputs": [("DUMMY-DEMAND-SIDE", "Outputs"), ("DUMMY-SUPPLY-SIDE", "Outputs")],
            "validation_basis": ps.VALIDATION_INTERNAL_CONSISTENCY,
            "confidence_note": note1 or note2,
        }

    engine4.register_model(("DUMMY-SEED", "Outputs"), _dummy_test_fixture_seed, unit="-")
    engine4.register_model(
        ("DUMMY-DEMAND-SIDE", "Outputs"), _dummy_test_fixture_demand_side, unit="-",
        depends_on=[("DUMMY-SEED", "Outputs")],
        lagged_depends_on=[("DUMMY-SUPPLY-SIDE", "Outputs")],
    )
    engine4.register_model(
        ("DUMMY-SUPPLY-SIDE", "Outputs"), _dummy_test_fixture_supply_side, unit="-",
        lagged_depends_on=[("DUMMY-DEMAND-SIDE", "Outputs"), ("DUMMY-SUPPLY-SIDE", "Outputs")],
    )

    gaps = []
    for i in range(30):
        engine4.run_cycle(now=f"2026-09-01T13:{i:02d}:00Z")
        snap = state4.get_snapshot()
        demand_v = snap[("DUMMY-DEMAND-SIDE", "Outputs")]["value"]
        supply_v = snap[("DUMMY-SUPPLY-SIDE", "Outputs")]["value"]
        gap = abs(demand_v - supply_v) if demand_v is not None and supply_v is not None else None
        gaps.append(gap)

    print(f"  Demand/supply gap per cycle: {[round(g, 4) if g is not None else None for g in gaps]}")
    real_gaps = [g for g in gaps if g is not None]
    assert len(real_gaps) >= 20, "REGRESSION: the lagged pair never produced enough real cycles to test convergence."
    # Check the real DOWNWARD TREND at several checkpoints, not just the two
    # endpoints -- a genuinely converging (not coincidentally-lucky) series.
    checkpoints = [real_gaps[4], real_gaps[9], real_gaps[19], real_gaps[-1]]
    print(f"  Checkpoint gaps (cycles 5, 10, 20, {len(real_gaps)}): {[round(c, 4) for c in checkpoints]}")
    assert checkpoints == sorted(checkpoints, reverse=True), (
        f"REGRESSION: lagged pair's gap did not shrink monotonically across checkpoints: {checkpoints}."
    )
    assert real_gaps[-1] < 1.0, f"REGRESSION: lagged pair did not converge below tolerance (final gap={real_gaps[-1]})."
    print(f"PASSED -- gap shrank from {real_gaps[0]:.4f} to {real_gaps[-1]:.4f} over {len(real_gaps)} cycles, "
          f"below the 1.0 tolerance -- the one-cycle-lag mechanism converges, on a synthetic pair, exactly "
          f"as Section 10 limitation 4 / roadmap Part 8 describe it will for the real GC<->EU-008 pair in Phase 2.")

    print("\nAll simulation_engine.py self-tests PASSED.")
