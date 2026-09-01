"""
Five-way status/traceability framework v1 — Digital Twin Phase 0.

Generalizes equipment_engineering_estimates.py's existing three-way status
pattern (STATUS_CONFIRMED / STATUS_ESTIMATE / STATUS_MISSING, itself read by
equipment_datasheet.slot_status()) to the five-way status the Digital Twin
engineering plan's Section 8.1 defines for LIVE plant state, as opposed to the
static equipment registry:

  - Measured    -- a real sensor/PLC/lab reading (does not exist yet in this
    repo -- Phase 0 defines the status value, nothing produces it until a real
    sensor is wired in, per the plan's Section 8.3/roadmap Part 17).
  - Calculated  -- a live model output, computed THIS cycle from other live
    values, with a real Input -> Model -> Equation/Correlation -> Output chain.
  - Estimated   -- the direct analogue of equipment_engineering_estimates.py's
    STATUS_ESTIMATE: a correlation/literature/comparable-system value with no
    live recomputation.
  - Assumed     -- a design-basis default with a stated uncertainty range, not
    yet DOK-ING-confirmed -- the same concept uncertainty.py's ASSUMPTIONS
    dict already tracks, given its own visible status here instead of being
    folded silently into whatever consumes it.
  - Missing     -- exactly equipment_datasheet.STATUS_MISSING's meaning,
    carried into live plant state: "Missing / Cannot Calculate", never a
    plausible-looking invented number.

This module is a NEW, small, dependency-free module -- it does not import
equipment_engineering_estimates.py or equipment_datasheet.py, and neither of
those is changed by it. The relationship is a reused PATTERN (same discipline:
a real status field, checked structurally, never a bare number presented
without one), not reused code -- the two systems describe genuinely different
things (a static per-item registry vs. live, cyclical plant state) and the
engineering plan's Part 2 code-audit explicitly calls for this relationship
("reused as a pattern, not imported code").

HARD RULE, enforced by validate_entry_shape() below, not just documented:
a Missing entry MUST have value=None and a non-empty missing_reason; every
OTHER status MUST have a real (non-None) value and NO missing_reason. This is
the actual mechanism that makes "never fabricate a value, never leave Missing
unexplained" checkable rather than merely asserted in a docstring.

PROVENANCE, per the plan's Section 8.2 / roadmap Part 11: every Calculated (or
Estimated) entry names which model produced it and which OTHER plant-state
keys (or uncertainty.py-style assumption keys) it was computed from, each
carrying its own status -- resolve_provenance_chain() below walks that chain
back to its roots (Measured / Assumed / Missing) and is the mechanism Decision
2 ("automated enforcement, wherever practical") actually depends on, per the
Phase 0 task that created this module.
"""

# --- The five-way status ------------------------------------------------

STATUS_MEASURED = "Measured"
STATUS_CALCULATED = "Calculated"
STATUS_ESTIMATED = "Estimated"
STATUS_ASSUMED = "Assumed"
STATUS_MISSING = "Missing"

ALL_STATUSES = (STATUS_MEASURED, STATUS_CALCULATED, STATUS_ESTIMATED, STATUS_ASSUMED, STATUS_MISSING)

# A value is missing only under STATUS_MISSING -- every other status carries
# a real value. Stated as data (not just a comment) so validate_entry_shape()
# can check it mechanically.
_STATUSES_REQUIRING_VALUE = (STATUS_MEASURED, STATUS_CALCULATED, STATUS_ESTIMATED, STATUS_ASSUMED)

# --- Validation basis, per the engineering plan's Section 9 / GA-001's own
# five-way validation-status breakdown (plan Section 2.2) -- kept as a
# SEPARATE axis from the five-way status above, since a value can be
# Calculated with several different real validation bases (design-target
# reproduction vs. literature-range only being the load-bearing distinction
# the plan draws for GA-001 specifically). ---------------------------------

VALIDATION_LITERATURE = "Literature"
VALIDATION_ENGINEERING_CORRELATION = "EngineeringCorrelation"
VALIDATION_INTERNAL_CONSISTENCY = "InternalConsistency"
VALIDATION_DOKING_DESIGN_TARGET = "DOKINGDesignTarget"
VALIDATION_FUTURE_PLANT_DATA = "FuturePlantData"
VALIDATION_NA = "N/A"

ALL_VALIDATION_BASES = (
    VALIDATION_LITERATURE, VALIDATION_ENGINEERING_CORRELATION, VALIDATION_INTERNAL_CONSISTENCY,
    VALIDATION_DOKING_DESIGN_TARGET, VALIDATION_FUTURE_PLANT_DATA, VALIDATION_NA,
)


def validate_entry_shape(key, entry):
    """The automated, mechanical version of the five-way status's hard rule.
    Raises ValueError with a specific, actionable message on any violation --
    called by SharedPlantState.set_entry() on every write (shared_plant_state.py),
    so a malformed entry can never enter the state in the first place, and by
    this module's own self-test directly. Not merely documented: enforced."""
    if not isinstance(entry, dict):
        raise ValueError(f"{key!r}: entry must be a dict, got {type(entry).__name__}.")

    required_keys = {
        "value", "unit", "status", "source", "validation_basis",
        "confidence_note", "cycle", "timestamp", "missing_reason",
    }
    missing_keys = required_keys - set(entry.keys())
    if missing_keys:
        raise ValueError(f"{key!r}: entry is missing required field(s) {sorted(missing_keys)}.")

    status = entry["status"]
    if status not in ALL_STATUSES:
        raise ValueError(f"{key!r}: status {status!r} is not one of {ALL_STATUSES}.")

    if status == STATUS_MISSING:
        if entry["value"] is not None:
            raise ValueError(
                f"{key!r}: status=Missing but value={entry['value']!r} is not None -- "
                f"a Missing entry must never carry a fabricated or leftover value."
            )
        if not entry.get("missing_reason"):
            raise ValueError(
                f"{key!r}: status=Missing but missing_reason is empty -- every Missing "
                f"entry must name the specific blocking input, per the plan's Section 10/22."
            )
    else:
        if entry["value"] is None:
            raise ValueError(
                f"{key!r}: status={status} but value is None -- every non-Missing status "
                f"must carry a real value."
            )
        if entry.get("missing_reason"):
            raise ValueError(
                f"{key!r}: status={status} but missing_reason={entry['missing_reason']!r} is "
                f"set -- missing_reason must be empty/None for any non-Missing entry."
            )

    if entry["validation_basis"] not in ALL_VALIDATION_BASES:
        raise ValueError(
            f"{key!r}: validation_basis {entry['validation_basis']!r} is not one of "
            f"{ALL_VALIDATION_BASES}."
        )

    source = entry["source"]
    if not isinstance(source, dict) or "model" not in source or "inputs" not in source:
        raise ValueError(f"{key!r}: source must be a dict with 'model' and 'inputs' keys.")
    if not isinstance(source["inputs"], (list, tuple)):
        raise ValueError(f"{key!r}: source['inputs'] must be a list/tuple of keys.")
    if status in (STATUS_CALCULATED, STATUS_ESTIMATED) and source["model"] is None:
        raise ValueError(
            f"{key!r}: status={status} but source['model'] is None -- every Calculated or "
            f"Estimated value must always name the model/function (or, for an Estimated value, "
            f"the estimate-producing source) that produced it (Input -> Model -> "
            f"Equation/Correlation -> Output)."
        )


def resolve_provenance_chain(snapshot, key, _visited=None):
    """Walks a published SharedPlantState snapshot's source.inputs chain,
    starting at `key`, back to its roots. Returns a list of
    {key, status, validation_basis, depth} dicts, depth-first, root-first
    within each branch is NOT guaranteed (traversal order only), but EVERY
    node reached is included exactly once. Cycle-safe: a key that would
    revisit an already-visited node in the current walk is recorded once
    (its first visit) and not re-descended into, so a malformed/cyclic
    provenance graph terminates instead of recursing forever -- this is a
    defensive guard for a genuine authoring bug, not an expected case (the
    simulation engine's own dependency graph is itself required to be a DAG
    over non-lagged edges; a cycle showing up here would mean an entry's own
    'source.inputs' lied about what it actually depended on).

    `key` not present in the snapshot at all is treated as an implicit
    Missing root (no entry exists yet) -- consistent with
    SharedPlantState.get_entry()'s own "absent key -> Missing" contract,
    never a KeyError.
    """
    if _visited is None:
        _visited = set()
    if key in _visited:
        return []
    _visited.add(key)

    entry = snapshot.get(key)
    if entry is None:
        return [{"key": key, "status": STATUS_MISSING, "validation_basis": VALIDATION_NA,
                 "missing_reason": "no entry exists yet for this key"}]

    node = {
        "key": key, "status": entry["status"], "validation_basis": entry["validation_basis"],
        "missing_reason": entry.get("missing_reason"),
    }
    chain = [node]
    for input_key in entry["source"]["inputs"]:
        chain.extend(resolve_provenance_chain(snapshot, input_key, _visited))
    return chain


def missing_roots(snapshot, key):
    """The subset of resolve_provenance_chain()'s result that are actually
    Missing -- i.e. exactly which upstream inputs are blocking `key`, by
    name, for a UI or a test to report (roadmap Part 16: 'affected outputs
    identified'). Empty list means the chain is fully resolvable today."""
    return [n for n in resolve_provenance_chain(snapshot, key) if n["status"] == STATUS_MISSING]


def is_fully_traceable(snapshot, key):
    """True if `key` and every node in its provenance chain resolves to a
    real entry with a real status (i.e. no Missing roots anywhere in the
    chain). False does not mean 'broken' -- a value downstream of a
    permanently-Missing item (e.g. HB-010) is correctly, honestly NOT fully
    traceable to a complete set of real values, and this function is exactly
    how that gets detected automatically rather than asserted by convention."""
    return len(missing_roots(snapshot, key)) == 0


if __name__ == "__main__":
    print("=== validate_entry_shape: a well-formed Measured entry passes ===")
    good_measured = {
        "value": 42.0, "unit": "kg/h", "status": STATUS_MEASURED,
        "source": {"model": None, "inputs": []},
        "validation_basis": VALIDATION_NA, "confidence_note": "", "cycle": 1,
        "timestamp": "2026-09-01T00:00:00Z", "missing_reason": None,
    }
    validate_entry_shape(("TEST-001", "Inputs"), good_measured)
    print("PASSED")

    print("\n=== validate_entry_shape: a well-formed Missing entry passes ===")
    good_missing = {
        "value": None, "unit": "kg/h", "status": STATUS_MISSING,
        "source": {"model": None, "inputs": []},
        "validation_basis": VALIDATION_NA, "confidence_note": "",
        "cycle": 1, "timestamp": "2026-09-01T00:00:00Z",
        "missing_reason": "no membrane permeance/selectivity data exists",
    }
    validate_entry_shape(("TEST-002", "Outputs"), good_missing)
    print("PASSED")

    print("\n=== validate_entry_shape: REJECTS a Missing entry carrying a value (fabrication guard) ===")
    bad = dict(good_missing)
    bad["value"] = 99.0
    try:
        validate_entry_shape(("TEST-003", "Outputs"), bad)
        raise AssertionError("REGRESSION: a Missing entry with a real value was NOT rejected.")
    except ValueError as e:
        print(f"PASSED -- correctly rejected: {e}")

    print("\n=== validate_entry_shape: REJECTS a non-Missing entry with value=None ===")
    bad2 = dict(good_measured)
    bad2["value"] = None
    try:
        validate_entry_shape(("TEST-004", "Inputs"), bad2)
        raise AssertionError("REGRESSION: a Calculated/Measured entry with value=None was NOT rejected.")
    except ValueError as e:
        print(f"PASSED -- correctly rejected: {e}")

    print("\n=== validate_entry_shape: REJECTS a non-Missing entry that still carries missing_reason ===")
    bad3 = dict(good_measured)
    bad3["missing_reason"] = "should not be here"
    try:
        validate_entry_shape(("TEST-005", "Inputs"), bad3)
        raise AssertionError("REGRESSION: a non-Missing entry with a set missing_reason was NOT rejected.")
    except ValueError as e:
        print(f"PASSED -- correctly rejected: {e}")

    print("\n=== validate_entry_shape: REJECTS a Calculated entry with no model named ===")
    bad4 = dict(good_measured)
    bad4["status"] = STATUS_CALCULATED
    bad4["source"] = {"model": None, "inputs": []}
    try:
        validate_entry_shape(("TEST-006", "Inputs"), bad4)
        raise AssertionError("REGRESSION: a Calculated entry with no model was NOT rejected.")
    except ValueError as e:
        print(f"PASSED -- correctly rejected: {e}")

    print("\n=== validate_entry_shape: REJECTS an Estimated entry with no model named ===")
    bad5 = dict(good_measured)
    bad5["status"] = STATUS_ESTIMATED
    bad5["source"] = {"model": None, "inputs": []}
    try:
        validate_entry_shape(("TEST-007", "Inputs"), bad5)
        raise AssertionError("REGRESSION: an Estimated entry with no model was NOT rejected.")
    except ValueError as e:
        print(f"PASSED -- correctly rejected: {e}")

    print("\n=== resolve_provenance_chain: a 3-hop synthetic chain (Measured -> Calculated -> Calculated) ===")
    snapshot = {
        ("SYN-A", "Inputs"): {
            "value": 10.0, "unit": "kg/h", "status": STATUS_MEASURED,
            "source": {"model": None, "inputs": []}, "validation_basis": VALIDATION_NA,
            "confidence_note": "", "cycle": 1, "timestamp": "t1", "missing_reason": None,
        },
        ("SYN-B", "Outputs"): {
            "value": 20.0, "unit": "kg/h", "status": STATUS_CALCULATED,
            "source": {"model": "test.double", "inputs": [("SYN-A", "Inputs")]},
            "validation_basis": VALIDATION_ENGINEERING_CORRELATION,
            "confidence_note": "", "cycle": 1, "timestamp": "t1", "missing_reason": None,
        },
        ("SYN-C", "Outputs"): {
            "value": 40.0, "unit": "kg/h", "status": STATUS_CALCULATED,
            "source": {"model": "test.double", "inputs": [("SYN-B", "Outputs")]},
            "validation_basis": VALIDATION_ENGINEERING_CORRELATION,
            "confidence_note": "", "cycle": 1, "timestamp": "t1", "missing_reason": None,
        },
    }
    chain = resolve_provenance_chain(snapshot, ("SYN-C", "Outputs"))
    chain_keys = [n["key"] for n in chain]
    print(f"  Chain reached: {chain_keys}")
    assert set(chain_keys) == {("SYN-C", "Outputs"), ("SYN-B", "Outputs"), ("SYN-A", "Inputs")}, (
        "REGRESSION: provenance chain did not reach all three expected nodes."
    )
    assert is_fully_traceable(snapshot, ("SYN-C", "Outputs")), (
        "REGRESSION: a chain rooted entirely in a Measured value should be fully traceable."
    )
    print("PASSED -- all three nodes reached, chain is fully traceable to its Measured root.")

    print("\n=== resolve_provenance_chain: a chain with a Missing root is detected, not hidden ===")
    snapshot2 = dict(snapshot)
    snapshot2[("SYN-A", "Inputs")] = {
        "value": None, "unit": "kg/h", "status": STATUS_MISSING,
        "source": {"model": None, "inputs": []}, "validation_basis": VALIDATION_NA,
        "confidence_note": "", "cycle": 1, "timestamp": "t1",
        "missing_reason": "synthetic test: no upstream data",
    }
    assert not is_fully_traceable(snapshot2, ("SYN-C", "Outputs")), (
        "REGRESSION: a chain rooted in a Missing value must NOT be reported as fully traceable."
    )
    roots = missing_roots(snapshot2, ("SYN-C", "Outputs"))
    print(f"  Missing roots found: {[r['key'] for r in roots]} -- reason: {roots[0]['missing_reason']!r}")
    assert roots and roots[0]["key"] == ("SYN-A", "Inputs")
    print("PASSED -- Missing root correctly detected and named, not silently passed through.")

    print("\n=== resolve_provenance_chain: an absent key (never written) resolves as an implicit Missing root ===")
    chain3 = resolve_provenance_chain(snapshot, ("SYN-NEVER-WRITTEN", "Inputs"))
    assert len(chain3) == 1 and chain3[0]["status"] == STATUS_MISSING
    print("PASSED -- absent key treated as Missing, never a KeyError, never a fabricated value.")

    print("\n=== resolve_provenance_chain: cyclic provenance terminates instead of recursing forever ===")
    cyclic_snapshot = {
        ("SYN-X", "Outputs"): {
            "value": 1.0, "unit": "-", "status": STATUS_CALCULATED,
            "source": {"model": "test.cyclic", "inputs": [("SYN-Y", "Outputs")]},
            "validation_basis": VALIDATION_INTERNAL_CONSISTENCY,
            "confidence_note": "", "cycle": 1, "timestamp": "t1", "missing_reason": None,
        },
        ("SYN-Y", "Outputs"): {
            "value": 1.0, "unit": "-", "status": STATUS_CALCULATED,
            "source": {"model": "test.cyclic", "inputs": [("SYN-X", "Outputs")]},
            "validation_basis": VALIDATION_INTERNAL_CONSISTENCY,
            "confidence_note": "", "cycle": 1, "timestamp": "t1", "missing_reason": None,
        },
    }
    cyclic_chain = resolve_provenance_chain(cyclic_snapshot, ("SYN-X", "Outputs"))
    assert {n["key"] for n in cyclic_chain} == {("SYN-X", "Outputs"), ("SYN-Y", "Outputs")}
    print("PASSED -- cyclic provenance graph terminates cleanly, visits each node exactly once.")

    print("\nAll plant_status.py self-tests PASSED.")
