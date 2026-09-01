"""
Shared Plant State v1 -- Digital Twin Phase 0 (Foundational Infrastructure).

Implements the conceptual schema from docs/digital_twin_engineering_plan.md's
Section 6.0 / roadmap Part 11: the ONE data structure every Equipment Model,
every Tab, and the AI/Optimization/Intelligence Layer (AI-012/AI-013) read
through, and that ONLY the Central Simulation Engine (simulation_engine.py)
ever writes to.

THIS MODULE COMPUTES NO PROCESS VALUES. It is pure architecture -- a typed
store plus the discipline enforced around it. Nothing in this file knows
what a gasifier or a heat exchanger is; it only knows how to hold, publish,
and traceably serve whatever a model hands it, per plant_status.py's
five-way status contract.

DESIGN GUARANTEES, each one a stated requirement from the Phase 0 task, and
each one enforced by code below, not just by convention:

  1. SINGLE-WRITER. Every mutating method (set_entry, begin_cycle,
     publish_cycle) requires a `WriterHandle` obtained from
     new_writer_handle(). Calling new_writer_handle() again invalidates the
     previous handle -- so at most one caller can ever hold a valid handle
     at a time, and a stale or forged handle is rejected with
     PermissionError, not silently accepted. In the finished architecture,
     SimulationEngine is the only thing that ever calls new_writer_handle().

  2. MULTI-READER. get_snapshot() and get_entry() need no handle at all --
     any Tab, any AI-012/013-style consumer, any test, can call them freely.

  3. ATOMIC PER-CYCLE PUBLISH. Writes during a cycle land in a private
     staging area (_staging), invisible to every reader. publish_cycle()
     swaps the ENTIRE staging area into the published snapshot in one step
     and deep-copies it, so no reader ever observes a partially-updated
     cycle, and no reader can mutate the store by mutating what they were
     handed back.

  4. FULL PROVENANCE CHAIN. Every entry's own shape (plant_status.py) names
     the model that produced it and the exact upstream keys it read; walking
     that chain back to Measured/Assumed/Missing roots is
     plant_status.resolve_provenance_chain(), not duplicated here.

  5. MISSING AS A FIRST-CLASS RESULT. get_entry() on a key nobody has ever
     written returns a real Missing-status entry (via
     plant_status's-shaped default), never a KeyError and never None on its
     own -- "absent" and "Missing" are made to mean the same observable
     thing on purpose, so a caller can never accidentally treat "nothing
     written yet" as a different case from "explicitly Missing".
"""
import copy
from datetime import datetime, timezone

from . import plant_status as ps


class WriterHandle:
    """An opaque token. Holding the CURRENT one is what "being the writer"
    means -- nothing about this class's own identity matters beyond that
    SharedPlantState can tell one instance from another (`is`), which is
    exactly what enforces single-writer without any extra bookkeeping."""
    __slots__ = ()


class SharedPlantState:
    """The one store. See module docstring for the five guarantees this
    class exists to provide."""

    def __init__(self):
        self._published = {}          # key -> entry dict, the last fully-published snapshot
        self._published_cycle = 0     # 0 = nothing published yet
        self._published_at = None
        self._staging = None          # dict while a cycle is open, else None
        self._staging_cycle = None
        self._staging_started_at = None
        self._current_handle = None   # the only WriterHandle allowed to mutate right now

    # --- Writer-handle lifecycle -------------------------------------

    def new_writer_handle(self):
        """Issues a fresh WriterHandle and immediately invalidates whatever
        handle existed before -- so at most one is ever valid. Called once,
        by SimulationEngine's own constructor, in the finished architecture."""
        self._current_handle = WriterHandle()
        return self._current_handle

    def _check_handle(self, handle):
        if handle is None or handle is not self._current_handle:
            raise PermissionError(
                "SharedPlantState: rejected a write from a handle that is not the current "
                "writer handle. Only the Central Simulation Engine (via the handle it obtained "
                "from new_writer_handle()) may mutate the Shared Plant State -- this guard is "
                "what makes 'single-writer' an enforced property, not just a documented one."
            )

    # --- Writing (requires a valid handle) -----------------------------

    def begin_cycle(self, handle, now=None):
        """Opens a new staging area for the NEXT cycle number. Must be
        called before any set_entry() in that cycle. `now` is injectable
        for deterministic tests; defaults to the real current UTC time."""
        self._check_handle(handle)
        if self._staging is not None:
            raise RuntimeError(
                "SharedPlantState.begin_cycle() called while a cycle is already open -- "
                "publish_cycle() (or discard_cycle()) the current one first."
            )
        self._staging = {}
        self._staging_cycle = self._published_cycle + 1
        self._staging_started_at = now if now is not None else datetime.now(timezone.utc).isoformat()
        return self._staging_cycle

    def discard_cycle(self, handle):
        """Abandons the currently-open staging cycle without publishing it
        -- e.g. if the engine hits an unrecoverable error mid-cycle. Readers
        never saw it, so this is always safe."""
        self._check_handle(handle)
        self._staging = None
        self._staging_cycle = None
        self._staging_started_at = None

    def set_entry(self, handle, key, value, unit, status, model=None, inputs=(),
                  validation_basis=ps.VALIDATION_NA, confidence_note="", missing_reason=None):
        """Writes ONE entry into the currently-open staging cycle. `key` is
        an (equipment_id, category) tuple (or any hashable identifier -- the
        store itself doesn't require the equipment registry's own shape,
        since Phase 0 has no real equipment items yet). Validated via
        plant_status.validate_entry_shape() before it is accepted -- a
        malformed entry raises here, at write time, not discovered later."""
        self._check_handle(handle)
        if self._staging is None:
            raise RuntimeError("SharedPlantState.set_entry() called with no cycle open -- call begin_cycle() first.")

        entry = {
            "value": value, "unit": unit, "status": status,
            "source": {"model": model, "inputs": list(inputs)},
            "validation_basis": validation_basis, "confidence_note": confidence_note,
            "cycle": self._staging_cycle, "timestamp": self._staging_started_at,
            "missing_reason": missing_reason,
        }
        ps.validate_entry_shape(key, entry)
        self._staging[key] = entry

    def publish_cycle(self, handle):
        """Atomically swaps the staging area into the published snapshot.
        Deep-copies on the way in, so nothing the caller still holds a
        reference to can mutate the store after the fact. Returns
        (cycle_number, published_at)."""
        self._check_handle(handle)
        if self._staging is None:
            raise RuntimeError("SharedPlantState.publish_cycle() called with no open cycle to publish.")
        self._published = copy.deepcopy(self._staging)
        self._published_cycle = self._staging_cycle
        self._published_at = self._staging_started_at
        self._staging = None
        self._staging_cycle = None
        self._staging_started_at = None
        return self._published_cycle, self._published_at

    def get_staged_entry(self, handle, key):
        """WRITER-ONLY read of the currently-open staging cycle -- requires
        the valid handle, exactly like the write methods. This exists for
        exactly one caller in the finished architecture: the Central
        Simulation Engine itself, which needs to read a value it (or an
        earlier step in the SAME cycle's topological order) already staged
        this cycle, before that cycle is published. No ordinary reader gets
        this capability -- get_snapshot()/get_entry() never touch
        self._staging, which is what keeps atomicity real for everyone else.
        Returns None if the key hasn't been staged yet this cycle (the
        caller is expected to know its own dependency graph well enough not
        to ask before the answer exists -- this is an internal engine
        primitive, not a public "maybe it's there" API)."""
        self._check_handle(handle)
        if self._staging is None:
            raise RuntimeError("SharedPlantState.get_staged_entry() called with no cycle open.")
        entry = self._staging.get(key)
        return copy.deepcopy(entry) if entry is not None else None

    # --- Reading (no handle required -- any number of readers) --------

    def get_snapshot(self):
        """Returns a deep-copied, safe-to-mutate-by-the-caller-without-
        affecting-the-store view of the last published cycle. This is what
        Tabs, AI-012/013, and every model's own upstream-input lookups read
        from -- never the live staging area, which stays invisible to every
        reader by construction (there is no reader-facing method that
        touches self._staging at all)."""
        return copy.deepcopy(self._published)

    def get_entry(self, key):
        """One entry from the current published snapshot. An absent key
        (nothing has ever been written for it) returns a real, correctly-
        shaped Missing entry -- never a KeyError, never None -- so "never
        written yet" and "explicitly computed as Missing" are indistinguishable
        to a caller, which is the intended, honest behavior (roadmap Part 11's
        'Missing values are first-class, never an absent key')."""
        entry = self._published.get(key)
        if entry is not None:
            return copy.deepcopy(entry)
        return {
            "value": None, "unit": None, "status": ps.STATUS_MISSING,
            "source": {"model": None, "inputs": []},
            "validation_basis": ps.VALIDATION_NA,
            "confidence_note": "",
            "cycle": self._published_cycle, "timestamp": self._published_at,
            "missing_reason": f"no entry has ever been published for key {key!r}",
        }

    @property
    def published_cycle(self):
        return self._published_cycle

    @property
    def published_at(self):
        return self._published_at


if __name__ == "__main__":
    print("=== Single-writer enforcement: an unrecognized handle is rejected ===")
    state = SharedPlantState()
    handle = state.new_writer_handle()
    forged = WriterHandle()
    try:
        state.begin_cycle(forged)
        raise AssertionError("REGRESSION: a forged/wrong WriterHandle was accepted.")
    except PermissionError as e:
        print(f"PASSED -- correctly rejected: {e}")

    print("\n=== Single-writer enforcement: issuing a new handle invalidates the old one ===")
    old_handle = handle
    new_handle = state.new_writer_handle()
    assert new_handle is not old_handle
    try:
        state.begin_cycle(old_handle)
        raise AssertionError("REGRESSION: a stale (superseded) WriterHandle was still accepted.")
    except PermissionError as e:
        print(f"PASSED -- correctly rejected: {e}")
    handle = new_handle

    print("\n=== Reading before anything is published: absent keys return Missing, never KeyError ===")
    entry = state.get_entry(("NEVER-WRITTEN", "Outputs"))
    assert entry["status"] == ps.STATUS_MISSING and entry["value"] is None
    print(f"PASSED -- {entry['missing_reason']}")

    print("\n=== Atomicity: readers see nothing until publish_cycle() is called ===")
    state.begin_cycle(handle, now="2026-09-01T00:00:00Z")
    state.set_entry(handle, ("SYN-A", "Outputs"), value=5.0, unit="kg/h", status=ps.STATUS_MEASURED)
    mid_cycle_read = state.get_entry(("SYN-A", "Outputs"))
    assert mid_cycle_read["status"] == ps.STATUS_MISSING, (
        "REGRESSION: a reader observed a value from a cycle that has not been published yet -- "
        "atomicity is broken."
    )
    print("PASSED -- mid-cycle staged write is invisible to readers, exactly as required.")
    cycle_no, published_at = state.publish_cycle(handle)
    post_publish_read = state.get_entry(("SYN-A", "Outputs"))
    assert post_publish_read["status"] == ps.STATUS_MEASURED and post_publish_read["value"] == 5.0
    print(f"PASSED -- after publish_cycle() (cycle {cycle_no}), the same read now sees the real value.")

    print("\n=== Multi-reader: two independent get_snapshot() calls return consistent, isolated copies ===")
    snap1 = state.get_snapshot()
    snap2 = state.get_snapshot()
    assert snap1 == snap2 and snap1 is not snap2
    snap1[("SYN-A", "Outputs")]["value"] = 999.0  # mutate the caller's own copy
    snap3 = state.get_snapshot()
    assert snap3[("SYN-A", "Outputs")]["value"] == 5.0, (
        "REGRESSION: mutating a snapshot returned to one reader affected the store itself."
    )
    print("PASSED -- snapshots are independent, deep-copied views; mutating one never affects the store.")

    print("\n=== A malformed entry is rejected at write time (via plant_status.validate_entry_shape) ===")
    state.begin_cycle(handle, now="2026-09-01T00:05:00Z")
    try:
        state.set_entry(handle, ("SYN-BAD", "Outputs"), value=None, unit="kg/h", status=ps.STATUS_MEASURED)
        raise AssertionError("REGRESSION: a Measured entry with value=None was accepted.")
    except ValueError as e:
        print(f"PASSED -- correctly rejected at write time: {e}")
    state.discard_cycle(handle)

    print("\n=== A first-class Missing entry can be written and read back correctly ===")
    state.begin_cycle(handle, now="2026-09-01T00:10:00Z")
    state.set_entry(
        handle, ("SYN-MISSING", "Performance Indicators"), value=None, unit="%",
        status=ps.STATUS_MISSING, missing_reason="synthetic test: required input not available",
    )
    state.publish_cycle(handle)
    missing_entry = state.get_entry(("SYN-MISSING", "Performance Indicators"))
    assert missing_entry["status"] == ps.STATUS_MISSING and missing_entry["value"] is None
    assert missing_entry["missing_reason"] == "synthetic test: required input not available"
    print("PASSED -- Missing entries round-trip correctly, with their reason preserved.")

    print("\n=== get_staged_entry(): writer-only mid-cycle read, invisible to ordinary readers ===")
    state.begin_cycle(handle, now="2026-09-01T00:15:00Z")
    state.set_entry(handle, ("SYN-STAGE", "Outputs"), value=7.0, unit="kg/h", status=ps.STATUS_MEASURED)
    staged = state.get_staged_entry(handle, ("SYN-STAGE", "Outputs"))
    assert staged is not None and staged["value"] == 7.0
    assert state.get_entry(("SYN-STAGE", "Outputs"))["status"] == ps.STATUS_MISSING, (
        "REGRESSION: get_staged_entry() leaked an unpublished value into the ordinary reader path."
    )
    try:
        state.get_staged_entry(forged, ("SYN-STAGE", "Outputs"))
        raise AssertionError("REGRESSION: get_staged_entry() accepted a forged handle.")
    except PermissionError:
        pass
    state.discard_cycle(handle)
    print("PASSED -- staged reads work for the writer only, stay invisible to every other reader.")

    print("\nAll shared_plant_state.py self-tests PASSED.")
