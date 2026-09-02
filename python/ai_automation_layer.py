"""
Automation & Instrumentation, fully live -- Digital Twin Phase 4, Part B.

Implements the roadmap's Part 10: AI-001 through AI-015, per the
engineering plan's own Section 2.7 table. As established there, this tab
is structurally different from FE/GA/GC/HB/EU: most of its items are not
process equipment at all, but descriptions of the very control/data
architecture this project's own Central Simulation Engine already IS.
Forcing physics or engineering-calc models onto them would misrepresent
what they are -- this module gives each item its real, honest
architectural role instead: state-machine executor (AI-004), cross-tab
aggregator (AI-007), operational-state log (AI-011), connectivity-only
infrastructure state (AI-005/006/008/009/010), or a relabeling of
already-real code onto its own equipment identity (AI-012/013/014/015).

=== AI-001 (Weather Station) -- task requirement 4 ===
Already built in Phase 1d as hb_remaining_chain.ai001_renewable_
availability(), registered as ("AI-001","RenewableAvailability"). NO new
build here -- this module's own self-test only confirms it is already
live when hb_remaining_chain.register_hb_remaining() has been called.

=== AI-002 (Camera) -- task requirement 5 ===
TWO separate, simultaneously-visible entries, never collapsed into one:
("AI-002","ContaminationDetection") -- the REAL function (image-based
contamination detection) -- permanently Missing, no real vision pipeline
exists or is reachable in this project (engineering plan Section 10,
limitation 6: Streamlit Community Cloud's free tier cannot host a vision
model, and no labeled training data exists). ("AI-002","ContaminationFlag")
-- Calculated, a single scenario-injectable boolean, settable ONLY via an
explicit test/scenario override (this module's own self-test demonstrates
the override mechanism directly) -- never a real vision pipeline, and
never presented as one.

=== AI-003 (Bed Pressure-Drop Sensor) -- task requirement 6 ===
No live bed-hydrodynamics model exists anywhere in this project (GA-001's
own model is a stoichiometric+WGS-equilibrium composition model, not a
fluidized-bed hydrodynamics one) -- reads GA-002's own Confirmed
"Operating pressure range (50-150 mbar(g))" midpoint directly, the SAME
"Confirmed design constant as live placeholder" treatment already
established for SA-011/SA-012 (sa_virtual_sensors.py) and GC-001/GC-003's
own temperature functions.

=== AI-004 (PLC) -- task requirement 7 ===
The real state-machine executor for the Tier-1 core chain (GA-001, GC-013,
HB-006, HB-013, EU-009): OFF (no feed), FAULT (a stated interlock
condition -- Missing status, or an already-computed real cross-check
exceeding its own equipment rating, e.g. GC-013's hydraulic power over its
1.5kW motor, HB-012's power over its 10kW motor, EU-008's utilization over
150%), STARTING (the very first published cycle only -- this project's
own steady-state-snapshot architecture has no real startup TRAJECTORY to
model, engineering plan Section 10 limitation 2 -- STARTING is a real,
stated, one-cycle bootstrap convention, not fabricated dynamics), RUNNING
(every other case). Lagged self-read of its own previous state is what
lets it tell cycle 1 (STARTING) from every later cycle (RUNNING).

=== AI-005/006/008/009/010 -- task requirement 8 ===
Exactly one function each, all built from the SAME small factory:
Online/Offline/Degraded, Assumed (no real network/health monitoring
integration exists in this project to derive this live), defaulting to
Online. No throughput model, no fabricated operational result beyond that
one state.

=== AI-007 (SCADA) -- task requirement 9 ===
The real cross-tab aggregation point: collects THIS cycle's live state
(same-cycle reads, never lagged/stale) from FE, GA, GC, HB, EU, SA, and
AI-004 into one queryable structure -- exactly the role a real plant's
SCADA server plays, not an independent calculation of its own.

=== AI-011 (Time-Series DB) -- task requirement 10 ===
Reuses vendor_log.py's own proven Supabase client pattern directly
(vendor_log._get_client(), not duplicated) to persist each cycle's key
results to a NEW table (digital_twin_cycle_log, DDL added to
data/supabase_schema.sql). Write failures (e.g. the table not yet created
in this Supabase project) are caught and reported as a real, Calculated
"logged: False" result -- Missing would misrepresent "we don't know" when
this project DOES know exactly what happened and why.

=== AI-012/013 -- task requirement 11 ===
Pure relabeling, per the roadmap's own explicit "not a separate thing to
build" framing -- no new code beyond identifying which already-real
modules each equipment ID names. AI-012 = optimizer.py/dispatch_ga.py
(the narrower MPC/RL-specific subset). AI-013 = the engineering plan's own
Section 2.8 "AI-013" bullet's exact 11-module list (uncertainty.py,
optimizer.py, predictive_maintenance.py, root_cause.py, pinn_kinetics.py,
sim_to_real.py, federated_learning.py, time_series_sim.py, tda_analysis.py,
copilot.py, multi_module_orchestration.py) -- a CONSUMER of the Shared
Plant State, never a producer (Decisions log, decision 3; Section 6.0).
verify_ai013_read_only() is the REAL enforcement check task requirement 14
asks for: a mechanical scan of all 11 files' own source text for any use
of shared_plant_state.py's writer-only API (new_writer_handle, set_entry,
publish_cycle, begin_cycle, discard_cycle, WriterHandle) -- not a
code-review claim.

=== AI-014 (Orchestration) -- task requirement 12 ===
Low-content, per the roadmap: this project models exactly one real
gasifier train, so AI-014's real operational content is minimal --
reports that plainly rather than fabricating fleet-coordination logic for
a fleet that doesn't exist.

=== AI-015 (RFNBO Monitor) -- task requirement 13 ===
Relabeling of compliance.py's/regulatory_drafting.py's existing content,
conditional on HB-011's own live `running` flag (hb_remaining_chain.py,
Phase 1d) -- not applicable when HB-011 isn't running this cycle, exactly
matching HB-011's own Auxiliary/Optional status and AI-015's own registry
scope statement.
"""
import datetime
import pathlib

from . import compliance
from . import plant_status as ps
from . import vendor_log


# ============================================================================
# AI-002 -- Camera / Vision System
# ============================================================================

def get_ai002_contamination_detection(get_input):
    """The REAL function -- permanently Missing. See module docstring."""
    return {
        "value": None, "status": ps.STATUS_MISSING,
        "model": "ai_automation_layer.get_ai002_contamination_detection", "inputs": [],
        "validation_basis": ps.VALIDATION_NA,
        "missing_reason": (
            "No real image-based contamination-detection pipeline exists or is reachable in this "
            "project -- no vision-model hosting is feasible on this deployment target, and no "
            "labeled training data for 'non-conforming MSW material' exists anywhere in this "
            "project (engineering plan Section 10, limitation 6). Not approximated, not fabricated."
        ),
    }


_AI002_SCENARIO_FLAG = [False]  # module-level state the scenario harness below flips


def get_ai002_contamination_flag(get_input):
    """The scenario-injectable placeholder -- Calculated, but its own value
    is set ONLY by set_ai002_scenario_flag() below (a real test/scenario
    harness, called from OUTSIDE the engine, never a live vision result).
    Shown side by side with get_ai002_contamination_detection()'s own
    permanent Missing -- never collapsed into one status that would
    misrepresent this as working computer vision."""
    return {
        "value": _AI002_SCENARIO_FLAG[0], "status": ps.STATUS_CALCULATED,
        "model": "ai_automation_layer.get_ai002_contamination_flag", "inputs": [],
        "validation_basis": ps.VALIDATION_NA,
        "confidence_note": (
            f"Scenario-injectable flag (currently {_AI002_SCENARIO_FLAG[0]}), settable ONLY via "
            f"set_ai002_scenario_flag() from an explicit test/scenario harness -- NOT a real vision "
            f"pipeline result. See ('AI-002','ContaminationDetection') for the permanently-Missing "
            f"real function this stands in for."
        ),
    }


def set_ai002_scenario_flag(value):
    """The explicit test/scenario harness task requirement 5 asks for --
    the ONLY way get_ai002_contamination_flag()'s own value ever changes."""
    _AI002_SCENARIO_FLAG[0] = bool(value)


# ============================================================================
# AI-003 -- Bed Pressure-Drop Sensor
# ============================================================================

AI003_CONFIRMED_BED_DP_MBAR = 50.0  # midpoint of GA-002's own Confirmed 50-150 mbar(g) range


def get_ai003_bed_pressure_drop(get_input):
    """See module docstring -- no live bed-hydrodynamics model exists;
    reads GA-002's own Confirmed operating-range midpoint directly."""
    return {
        "value": AI003_CONFIRMED_BED_DP_MBAR, "status": ps.STATUS_ASSUMED,
        "inputs": [], "validation_basis": ps.VALIDATION_NA,
        "confidence_note": (
            "GA-002's own Confirmed 'Operating pressure range' (50-150 mbar(g)) midpoint, read "
            "directly -- no live bed-hydrodynamics model exists anywhere in this project (module "
            "docstring), same 'Confirmed design constant as live placeholder' treatment as "
            "SA-011/SA-012."
        ),
    }


# ============================================================================
# AI-004 -- PLC (Main Control), the state-machine executor
# ============================================================================

AI004_TIER1_ITEMS = ("GA-001", "GC-013", "HB-006", "HB-013", "EU-009")

# Each Tier-1 item gets its OWN registered key with its OWN same-cycle
# depends_on, deliberately NOT one combined key depending on all of them --
# found necessary while building this: a single combined key would let ONE
# item's genuine Missing (e.g. a forced GA-001 fault) structurally block
# ai004_plant_state ENTIRELY (Phase 0's own same-cycle hard-blocking rule),
# hiding every OTHER item's real state behind an opaque, undifferentiated
# Missing -- defeating the whole diagnostic point of a PLC state machine.
# Splitting per item means: a genuinely Missing upstream source correctly,
# structurally makes THAT item's own state Missing too (still fully
# traceable via missing_reason -- itself a legitimate, honest diagnostic
# result, arguably more so than a hand-wavy "FAULT" string), while
# STRUCTURALLY UNRELATED items keep reporting their own real state, not a
# stale or blanked-out one -- no ad hoc lagging/staleness introduced.


def _plc_state(get_input, key, off, fault):
    """Shared per-item state logic: STARTING (this item's own first-ever
    published cycle -- checked FIRST, since on cycle 1 EVERY lagged cross-
    tab read this item's own FAULT/OFF checks depend on is itself absent/
    Missing by construction, nothing having published before cycle 1 --
    that is a genuine bootstrap condition, not a real fault, so it must not
    be misread as one) > OFF (no feed) > FAULT (a stated real interlock,
    from real PREVIOUS-cycle data now that cycle 1's bootstrap case is
    ruled out) > RUNNING. Lagged self-read, own key -- the SAME synthetic-
    pair-proven Phase 0 mechanism, reused here for a state machine rather
    than a physical quantity."""
    prev = get_input(key)  # lagged, self
    if prev["status"] == ps.STATUS_MISSING:
        return "STARTING"
    if off:
        return "OFF"
    if fault:
        return "FAULT"
    return "RUNNING"


def get_ai004_ga001_state(get_input):
    fe_in = get_input(("FE-001-INPUT", "msw_delivery_rate_kg_h"))
    feed_rate = 0.0 if fe_in["status"] == ps.STATUS_MISSING else fe_in["value"]
    ga_out = get_input(("GA-001", "Outputs"))
    state = _plc_state(get_input, ("AI-004", "GA-001-State"), feed_rate <= 0.0, ga_out["status"] == ps.STATUS_MISSING)
    return _plc_result(state, "get_ai004_ga001_state",
                        [("FE-001-INPUT", "msw_delivery_rate_kg_h"), ("GA-001", "Outputs"), ("AI-004", "GA-001-State")],
                        "OFF=no feed; FAULT=GA-001 Outputs Missing; else STARTING(cycle 1)/RUNNING.")


def get_ai004_gc013_state(get_input):
    fe_in = get_input(("FE-001-INPUT", "msw_delivery_rate_kg_h"))
    feed_rate = 0.0 if fe_in["status"] == ps.STATUS_MISSING else fe_in["value"]
    gc_out = get_input(("GC-013", "Gas"))
    gc_fan = get_input(("GC-013", "Fan power"))
    overloaded = gc_fan["status"] != ps.STATUS_MISSING and gc_fan["value"]["hydraulic_power_w"] / 1000.0 > 1.5
    fault = gc_out["status"] == ps.STATUS_MISSING or overloaded
    state = _plc_state(get_input, ("AI-004", "GC-013-State"), feed_rate <= 0.0, fault)
    return _plc_result(state, "get_ai004_gc013_state",
                        [("FE-001-INPUT", "msw_delivery_rate_kg_h"), ("GC-013", "Gas"), ("GC-013", "Fan power"),
                         ("AI-004", "GC-013-State")],
                        "OFF=no feed; FAULT=GC-013 Gas Missing OR hydraulic power >1.5kW motor rating; "
                        "else STARTING(cycle 1)/RUNNING.")


def get_ai004_hb006_state(get_input):
    fe_in = get_input(("FE-001-INPUT", "msw_delivery_rate_kg_h"))
    feed_rate = 0.0 if fe_in["status"] == ps.STATUS_MISSING else fe_in["value"]
    hb006 = get_input(("HB-006", "PSA"))
    hb012 = get_input(("HB-012", "Compressor"))
    overloaded = hb012["status"] != ps.STATUS_MISSING and hb012["value"]["power_kW"] > 10.0
    fault = hb006["status"] == ps.STATUS_MISSING or overloaded
    state = _plc_state(get_input, ("AI-004", "HB-006-State"), feed_rate <= 0.0, fault)
    return _plc_result(state, "get_ai004_hb006_state",
                        [("FE-001-INPUT", "msw_delivery_rate_kg_h"), ("HB-006", "PSA"), ("HB-012", "Compressor"),
                         ("AI-004", "HB-006-State")],
                        "OFF=no feed; FAULT=HB-006 PSA Missing OR HB-012 power >10kW motor rating; "
                        "else STARTING(cycle 1)/RUNNING.")


def get_ai004_hb013_state(get_input):
    hb013 = get_input(("HB-013", "Storage"))
    state = _plc_state(get_input, ("AI-004", "HB-013-State"), False, hb013["status"] == ps.STATUS_MISSING)
    return _plc_result(state, "get_ai004_hb013_state", [("HB-013", "Storage"), ("AI-004", "HB-013-State")],
                        "FAULT=HB-013 Storage Missing; else STARTING(cycle 1)/RUNNING (never OFF -- storage "
                        "has no feed-rate gate of its own).")


def get_ai004_eu009_state(get_input):
    eu009 = get_input(("EU-009", "GridBalance"))
    eu008 = get_input(("EU-008", "CoolingSupply"))
    overloaded = eu008["status"] != ps.STATUS_MISSING and eu008["value"]["utilization"] > 1.5
    fault = eu009["status"] == ps.STATUS_MISSING or overloaded
    state = _plc_state(get_input, ("AI-004", "EU-009-State"), False, fault)
    return _plc_result(state, "get_ai004_eu009_state",
                        [("EU-009", "GridBalance"), ("EU-008", "CoolingSupply"), ("AI-004", "EU-009-State")],
                        "FAULT=EU-009 GridBalance Missing OR EU-008 cooling utilization >150%; else "
                        "STARTING(cycle 1)/RUNNING.")


def _plc_result(state, fn_name, declared_inputs, rule_text):
    return {
        "value": state, "status": ps.STATUS_CALCULATED, "model": f"ai_automation_layer.{fn_name}",
        "inputs": declared_inputs, "validation_basis": ps.VALIDATION_ENGINEERING_CORRELATION,
        "confidence_note": f"State={state}. Rule: {rule_text}",
    }


# ============================================================================
# AI-005/006/008/009/010 -- connectivity-only infrastructure
# ============================================================================

_CONNECTIVITY_ITEMS = {
    "AI-005": "OPC-UA Gateway", "AI-006": "MQTT Broker", "AI-008": "Edge Computing Server",
    "AI-009": "Cybersecurity Firewall (ICS)", "AI-010": "Cloud IoT Hub",
}
_connectivity_overrides = {}  # {item_id: state} -- test/scenario harness only, see set_connectivity_override()


def set_connectivity_override(item_id, state):
    """Test/scenario harness (task requirement 8's own self-test uses this
    to demonstrate Degraded/Offline) -- the ONLY way any of these 5 states
    ever differs from the default 'Online'."""
    assert state in ("Online", "Offline", "Degraded"), f"Invalid connectivity state {state!r}"
    _connectivity_overrides[item_id] = state


def clear_connectivity_overrides():
    _connectivity_overrides.clear()


def _make_connectivity_fn(item_id, name):
    def fn(get_input):
        state = _connectivity_overrides.get(item_id, "Online")
        return {
            "value": state, "status": ps.STATUS_ASSUMED, "inputs": [], "validation_basis": ps.VALIDATION_NA,
            "confidence_note": (
                f"{item_id} ({name}): stated default connectivity assumption -- no real network/"
                f"health monitoring integration exists in this project to derive this live. No "
                f"throughput model, no fabricated result beyond this one Online/Offline/Degraded "
                f"state (task requirement 8)."
            ),
        }
    fn.__name__ = f"get_{item_id.lower().replace('-', '')}_connectivity_state"
    return fn


get_ai005_connectivity_state = _make_connectivity_fn("AI-005", _CONNECTIVITY_ITEMS["AI-005"])
get_ai006_connectivity_state = _make_connectivity_fn("AI-006", _CONNECTIVITY_ITEMS["AI-006"])
get_ai008_connectivity_state = _make_connectivity_fn("AI-008", _CONNECTIVITY_ITEMS["AI-008"])
get_ai009_connectivity_state = _make_connectivity_fn("AI-009", _CONNECTIVITY_ITEMS["AI-009"])
get_ai010_connectivity_state = _make_connectivity_fn("AI-010", _CONNECTIVITY_ITEMS["AI-010"])


# ============================================================================
# AI-007 -- DCS/SCADA Server, cross-tab aggregation
# ============================================================================

def get_ai007_scada_snapshot(get_input):
    """The real cross-tab aggregation point -- see module docstring."""
    fe = get_input(("FE-001", "Inventory"))
    ga = get_input(("GA-001", "Outputs"))
    gc = get_input(("GC-013", "Gas"))
    hb = get_input(("HB-013", "Storage"))
    eu = get_input(("EU-009", "GridBalance"))
    sa = get_input(("SA-001", "Reading"))
    ai004_ga001 = get_input(("AI-004", "GA-001-State"))
    ai004_eu009 = get_input(("AI-004", "EU-009-State"))

    def _val(entry):
        return None if entry["status"] == ps.STATUS_MISSING else entry["value"]

    snapshot = {
        "FE": _val(fe), "GA": _val(ga), "GC": _val(gc), "HB": _val(hb), "EU": _val(eu),
        "SA": _val(sa), "AI004": {"GA-001": _val(ai004_ga001), "EU-009": _val(ai004_eu009)},
    }
    return {
        "value": snapshot, "status": ps.STATUS_CALCULATED, "model": "ai_automation_layer.get_ai007_scada_snapshot",
        "inputs": [("FE-001", "Inventory"), ("GA-001", "Outputs"), ("GC-013", "Gas"), ("HB-013", "Storage"),
                   ("EU-009", "GridBalance"), ("SA-001", "Reading"), ("AI-004", "GA-001-State"),
                   ("AI-004", "EU-009-State")],
        "validation_basis": ps.VALIDATION_ENGINEERING_CORRELATION,
        "confidence_note": (
            "Cross-tab aggregation of THIS cycle's own live state (same-cycle reads, never lagged) "
            "from FE/GA/GC/HB/EU/SA/AI-004 -- the real role a plant SCADA server plays, not an "
            "independent calculation."
        ),
    }


# ============================================================================
# AI-011 -- Time-Series Database, the operational-state log
# ============================================================================

_TS_TABLE = "digital_twin_cycle_log"


def log_cycle_to_timeseries_db(summary):
    """Reuses vendor_log.py's own proven Supabase client (_get_client()),
    not duplicated. Inserts one row into digital_twin_cycle_log (DDL:
    data/supabase_schema.sql). Raises on failure -- the caller
    (get_ai011_logging_status) is what turns that into an honest,
    Calculated 'logged: False' result rather than crashing the cycle."""
    payload = {"logged_at": datetime.datetime.now(datetime.timezone.utc).isoformat(), **summary}
    resp = vendor_log._get_client().table(_TS_TABLE).insert(payload).execute()
    return resp.data[0]


def get_ai011_logging_status(get_input):
    ga = get_input(("GA-001", "Outputs"))
    gc = get_input(("GC-013", "Gas"))
    hb = get_input(("HB-013", "Storage"))
    eu = get_input(("EU-009", "GridBalance"))

    def _num(entry, field):
        return None if entry["status"] == ps.STATUS_MISSING else entry["value"][field]

    summary = {
        "ga_dry_flow_nm3_h": _num(ga, "dry_flow_nm3_h"), "gc_h2_pct": _num(gc, "H2_mol_pct_dry"),
        "hb_storage_kg": _num(hb, "level_kg"), "eu_net_kw": _num(eu, "net_kw"),
    }
    try:
        row = log_cycle_to_timeseries_db(summary)
        value = {"logged": True, "row_id": row.get("id"), "summary": summary}
        note = f"Persisted to Supabase table '{_TS_TABLE}' (row id {row.get('id')})."
    except Exception as exc:
        value = {"logged": False, "error": str(exc), "summary": summary}
        note = (
            f"Write to Supabase table '{_TS_TABLE}' failed: {exc} -- reported as a real, known "
            f"result (Calculated 'logged: False'), not hidden as Missing (this project DOES know "
            f"what happened and why). See data/supabase_schema.sql for the required DDL."
        )
    return {
        "value": value, "status": ps.STATUS_CALCULATED, "model": "ai_automation_layer.get_ai011_logging_status",
        "inputs": [("GA-001", "Outputs"), ("GC-013", "Gas"), ("HB-013", "Storage"), ("EU-009", "GridBalance")],
        "validation_basis": ps.VALIDATION_ENGINEERING_CORRELATION, "confidence_note": note,
    }


# ============================================================================
# AI-012/013 -- relabeling only (task requirement 11)
# ============================================================================

AI012_REAL_MODULES = ("optimizer.py", "dispatch_ga.py")
AI013_REAL_MODULES = (
    "uncertainty.py", "optimizer.py", "predictive_maintenance.py", "root_cause.py", "pinn_kinetics.py",
    "sim_to_real.py", "federated_learning.py", "time_series_sim.py", "tda_analysis.py", "copilot.py",
    "multi_module_orchestration.py",
)


def get_ai012_identity(get_input):
    return {
        "value": {"real_modules": list(AI012_REAL_MODULES), "role": "MPC/RL model server -- the narrower subset of AI-013"},
        "status": ps.STATUS_CALCULATED, "model": "ai_automation_layer.get_ai012_identity", "inputs": [],
        "validation_basis": ps.VALIDATION_NA,
        "confidence_note": "Pure relabeling, no new code -- optimizer.py/dispatch_ga.py ARE AI-012.",
    }


def get_ai013_identity(get_input):
    return {
        "value": {
            "real_modules": list(AI013_REAL_MODULES),
            "role": "AI/Optimization/Intelligence Layer -- a CONSUMER of the Shared Plant State, never a producer",
        },
        "status": ps.STATUS_CALCULATED, "model": "ai_automation_layer.get_ai013_identity", "inputs": [],
        "validation_basis": ps.VALIDATION_NA,
        "confidence_note": (
            "Pure relabeling, per the roadmap's own explicit 'not a separate thing to build' framing "
            "-- see verify_ai013_read_only() for the real, mechanical read-only enforcement check."
        ),
    }


_WRITE_API_MARKERS = (
    "new_writer_handle", "set_entry(", "publish_cycle(", "begin_cycle(", "discard_cycle(", "WriterHandle",
)


def verify_ai013_read_only():
    """Task requirement 14's real enforcement check -- NOT a code-review
    claim. Scans each of AI-013's own 11 real module files' source text for
    any use of shared_plant_state.py's writer-only API. Returns
    (all_clear: bool, violations: list[(module, marker)])."""
    base = pathlib.Path(__file__).resolve().parent
    violations = []
    for mod in AI013_REAL_MODULES:
        path = base / mod
        if not path.exists():
            violations.append((mod, "FILE NOT FOUND"))
            continue
        text = path.read_text(encoding="utf-8")
        for marker in _WRITE_API_MARKERS:
            if marker in text:
                violations.append((mod, marker))
    return (len(violations) == 0, violations)


# ============================================================================
# AI-014 -- Multi-Module Orchestration Controller
# ============================================================================

def get_ai014_orchestration_state(get_input):
    """Low-content, per the roadmap -- see module docstring."""
    return {
        "value": {
            "active_modules": 1, "max_modules_supported": 25, "orchestration_active": False,
            "note": "Single-gasifier-train plant -- no fleet coordination active.",
        },
        "status": ps.STATUS_CALCULATED, "model": "ai_automation_layer.get_ai014_orchestration_state", "inputs": [],
        "validation_basis": ps.VALIDATION_NA,
        "confidence_note": "multi_module_orchestration.py exists for a hypothetical multi-train scenario; "
                            "this ONE real plant has exactly 1 active module.",
    }


# ============================================================================
# AI-015 -- RFNBO Compliance & Guarantee-of-Origin Monitor
# ============================================================================

def get_ai015_rfnbo_status(get_input):
    """Conditional on HB-011's own live `running` flag -- see module
    docstring."""
    hb011 = get_input(("HB-011", "Electrolyser"))
    running = hb011["status"] != ps.STATUS_MISSING and hb011["value"]["running"]
    if not running:
        return {
            "value": {"applicable": False, "reason": "HB-011 (Electrolyser) not running this cycle"},
            "status": ps.STATUS_CALCULATED, "model": "ai_automation_layer.get_ai015_rfnbo_status",
            "inputs": [("HB-011", "Electrolyser")], "validation_basis": ps.VALIDATION_NA,
            "confidence_note": "Not applicable -- HB-011 inactive, matching its own Auxiliary/Optional status.",
        }
    checklist = compliance.build_checklist()
    summary = compliance.summarize_checklist(checklist)
    return {
        "value": {"applicable": True, "checklist_summary": summary},
        "status": ps.STATUS_CALCULATED, "model": "ai_automation_layer.get_ai015_rfnbo_status",
        "inputs": [("HB-011", "Electrolyser")], "validation_basis": ps.VALIDATION_NA,
        "confidence_note": "Relabeling of compliance.py's/regulatory_drafting.py's existing content, HB-011 active this cycle.",
    }


# ============================================================================
# Registration
# ============================================================================

def register_ai_layer(engine):
    """Registers AI-002/003/004/005/006/007/008/009/010/011/012/013/014/015
    with an engine that has ALREADY had FE/GA/GC/HB(+remaining)/EU/SA
    registered. AI-001 is NOT re-registered here -- already live since
    Phase 1d (hb_remaining_chain.register_hb_remaining())."""
    engine.register_model(("AI-002", "ContaminationDetection"), get_ai002_contamination_detection, unit="bool", depends_on=[])
    engine.register_model(("AI-002", "ContaminationFlag"), get_ai002_contamination_flag, unit="bool", depends_on=[])
    engine.register_model(("AI-003", "BedPressureDrop"), get_ai003_bed_pressure_drop, unit="mbar", depends_on=[])
    # All of AI-004's own cross-tab reads (not just its self-history) are LAGGED, not
    # same-cycle -- found necessary while building this: a same-cycle depends_on on
    # e.g. ("GA-001","Outputs") means the ENGINE's own structural blocking (Phase 0)
    # would auto-write Missing for get_ai004_ga001_state WITHOUT ever calling it,
    # whenever GA-001 itself is Missing -- precisely the one case a diagnostic state
    # machine most needs to actually RUN and report FAULT. Lagged reads never hard-
    # block, so the function body genuinely executes and can report FAULT on exactly
    # this condition. Real, stated consequence: AI-004 detects a fault one cycle after
    # it occurs -- a defensible, honest abstraction for a monitoring/diagnostic layer
    # (distinct from a PROCESS model, which genuinely needs same-cycle physics),
    # consistent with how any real polling-based PLC/SCADA display already has some
    # finite scan-to-alarm latency.
    engine.register_model(
        ("AI-004", "GA-001-State"), get_ai004_ga001_state, unit="state", depends_on=[],
        lagged_depends_on=[("FE-001-INPUT", "msw_delivery_rate_kg_h"), ("GA-001", "Outputs"), ("AI-004", "GA-001-State")],
    )
    engine.register_model(
        ("AI-004", "GC-013-State"), get_ai004_gc013_state, unit="state", depends_on=[],
        lagged_depends_on=[("FE-001-INPUT", "msw_delivery_rate_kg_h"), ("GC-013", "Gas"), ("GC-013", "Fan power"),
                            ("AI-004", "GC-013-State")],
    )
    engine.register_model(
        ("AI-004", "HB-006-State"), get_ai004_hb006_state, unit="state", depends_on=[],
        lagged_depends_on=[("FE-001-INPUT", "msw_delivery_rate_kg_h"), ("HB-006", "PSA"), ("HB-012", "Compressor"),
                            ("AI-004", "HB-006-State")],
    )
    engine.register_model(
        ("AI-004", "HB-013-State"), get_ai004_hb013_state, unit="state", depends_on=[],
        lagged_depends_on=[("HB-013", "Storage"), ("AI-004", "HB-013-State")],
    )
    engine.register_model(
        ("AI-004", "EU-009-State"), get_ai004_eu009_state, unit="state", depends_on=[],
        lagged_depends_on=[("EU-009", "GridBalance"), ("EU-008", "CoolingSupply"), ("AI-004", "EU-009-State")],
    )
    engine.register_model(("AI-005", "Connectivity"), get_ai005_connectivity_state, unit="state", depends_on=[])
    engine.register_model(("AI-006", "Connectivity"), get_ai006_connectivity_state, unit="state", depends_on=[])
    engine.register_model(
        ("AI-007", "ScadaSnapshot"), get_ai007_scada_snapshot, unit="dict",
        depends_on=[("FE-001", "Inventory"), ("GA-001", "Outputs"), ("GC-013", "Gas"), ("HB-013", "Storage"),
                    ("EU-009", "GridBalance"), ("SA-001", "Reading"), ("AI-004", "GA-001-State"),
                    ("AI-004", "EU-009-State")],
    )
    engine.register_model(("AI-008", "Connectivity"), get_ai008_connectivity_state, unit="state", depends_on=[])
    engine.register_model(("AI-009", "Connectivity"), get_ai009_connectivity_state, unit="state", depends_on=[])
    engine.register_model(("AI-010", "Connectivity"), get_ai010_connectivity_state, unit="state", depends_on=[])
    engine.register_model(
        ("AI-011", "LoggingStatus"), get_ai011_logging_status, unit="dict",
        depends_on=[("GA-001", "Outputs"), ("GC-013", "Gas"), ("HB-013", "Storage"), ("EU-009", "GridBalance")],
    )
    engine.register_model(("AI-012", "Identity"), get_ai012_identity, unit="dict", depends_on=[])
    engine.register_model(("AI-013", "Identity"), get_ai013_identity, unit="dict", depends_on=[])
    engine.register_model(("AI-014", "OrchestrationState"), get_ai014_orchestration_state, unit="dict", depends_on=[])
    engine.register_model(("AI-015", "RfnboStatus"), get_ai015_rfnbo_status, unit="dict", depends_on=[("HB-011", "Electrolyser")])


if __name__ == "__main__":
    from . import eu_utilities_chp as eu
    from . import fe_feed_handling as fe
    from . import ga001_gasifier_model as ga001
    from . import gc_gas_cleaning_chain as gc
    from . import hb_remaining_chain as hbrem
    from . import hb_wgs_psa_storage_chain as hbchain
    from . import sa_virtual_sensors as sa
    from . import shared_plant_state as sps
    from . import simulation_engine as se

    def _build_engine():
        state = sps.SharedPlantState()
        handle = state.new_writer_handle()
        engine = se.SimulationEngine(state)
        fe.register_fe_chain(engine)
        ga001.register_ga001(engine)
        gc.register_gc_chain(engine)
        hbchain.register_hb_chain(engine)
        hbrem.register_hb_remaining(engine)
        eu.register_eu_chain(engine)
        sa.register_sa_sensors(engine)
        register_ai_layer(engine)
        return state, handle, engine

    clear_connectivity_overrides()
    set_ai002_scenario_flag(False)

    print("=== Task requirement 4: AI-001 already live since Phase 1d, confirm/relabel only ===")
    state0, handle0, engine0 = _build_engine()
    for i in range(3):
        engine0.run_cycle(now=f"2026-09-09T00:{i:02d}:00Z")
    snap = state0.get_snapshot()
    ai001 = snap[("AI-001", "RenewableAvailability")]
    assert ai001["status"] != ps.STATUS_MISSING
    print(f"  AI-001: status={ai001['status']}  model={ai001['source']['model']} -- already live, no new build here -- PASSED.")

    print("\n=== Task requirement 5: AI-002 both statuses shown together, no fabricated vision ===")
    contamination = snap[("AI-002", "ContaminationDetection")]
    flag = snap[("AI-002", "ContaminationFlag")]
    assert contamination["status"] == ps.STATUS_MISSING and flag["status"] == ps.STATUS_CALCULATED
    assert flag["value"] is False
    print(f"  ContaminationDetection: status={contamination['status']} (the real function, permanently blocked)")
    print(f"  ContaminationFlag: status={flag['status']}, value={flag['value']} (scenario-injectable only)")
    set_ai002_scenario_flag(True)
    state0b, handle0b, engine0b = _build_engine()
    engine0b.run_cycle(now="2026-09-09T00:10:00Z")
    flag2 = state0b.get_entry(("AI-002", "ContaminationFlag"))
    assert flag2["value"] is True
    print(f"  After set_ai002_scenario_flag(True): value={flag2['value']} -- the harness works, and only the "
          f"harness can change it -- PASSED.")
    set_ai002_scenario_flag(False)

    print("\n=== Task requirement 6: AI-003 virtual bed-pressure reading ===")
    ai003 = snap[("AI-003", "BedPressureDrop")]
    assert ai003["status"] == ps.STATUS_ASSUMED and ai003["value"] == AI003_CONFIRMED_BED_DP_MBAR
    print(f"  AI-003: {ai003['value']} mbar, status={ai003['status']} -- PASSED.")

    print("\n=== Task requirement 8: AI-005/006/008/009/010 connectivity-only, no fabricated result ===")
    for item_id in _CONNECTIVITY_ITEMS:
        entry = snap[(item_id, "Connectivity")]
        assert entry["value"] == "Online" and entry["status"] == ps.STATUS_ASSUMED
        print(f"  {item_id}: {entry['value']}")
    set_connectivity_override("AI-006", "Degraded")
    state0c, handle0c, engine0c = _build_engine()
    engine0c.run_cycle(now="2026-09-09T00:20:00Z")
    degraded = state0c.get_entry(("AI-006", "Connectivity"))
    assert degraded["value"] == "Degraded"
    print(f"  AI-006 after set_connectivity_override('AI-006','Degraded'): {degraded['value']} -- harness "
          f"works, no throughput model fabricated beyond the state itself -- PASSED.")
    clear_connectivity_overrides()

    def _ai004_states(snapshot):
        out = {}
        for item in AI004_TIER1_ITEMS:
            entry = snapshot[("AI-004", f"{item}-State")]
            out[item] = entry["value"] if entry["status"] != ps.STATUS_MISSING else "MISSING"
        return out

    print("\n=== Task requirement 9 / 14: AI-007 aggregation reflects every tab's REAL live state ===")
    scada = snap[("AI-007", "ScadaSnapshot")]["value"]
    assert scada["GA"]["dry_flow_nm3_h"] == snap[("GA-001", "Outputs")]["value"]["dry_flow_nm3_h"]
    assert scada["GC"]["H2_mol_pct_dry"] == snap[("GC-013", "Gas")]["value"]["H2_mol_pct_dry"]
    assert scada["HB"]["level_kg"] == snap[("HB-013", "Storage")]["value"]["level_kg"]
    assert scada["EU"]["net_kw"] == snap[("EU-009", "GridBalance")]["value"]["net_kw"]
    assert scada["FE"]["level_t"] == snap[("FE-001", "Inventory")]["value"]["level_t"]
    assert scada["AI004"]["GA-001"] == snap[("AI-004", "GA-001-State")]["value"]
    assert scada["AI004"]["EU-009"] == snap[("AI-004", "EU-009-State")]["value"]
    print(f"  AI-007 snapshot's own GA/GC/HB/EU/FE/AI004 fields match the SAME cycle's own direct "
          f"entries exactly, not stale/partial -- PASSED.")

    print("\n=== Task requirement 7: AI-004 PLC state machine, baseline healthy ===")
    ai004_states = _ai004_states(snap)
    print(f"  Baseline (cycle 3): {ai004_states}")
    for item, state in ai004_states.items():
        if item == "EU-009":
            # HONEST FINDING, not a bug: EU-008's own real cooling demand is ~289% of its
            # Confirmed capacity at this exact baseline (the "Cooling Tower Resizing Estimate"
            # task) -- EU-009's own FAULT interlock (EU-008 utilization > 150%) correctly picks
            # this up. AI-004 giving real, useful visibility into an already-known real condition,
            # not a regression.
            assert state == "FAULT", f"EXPECTED EU-009 FAULT (EU-008 is genuinely overloaded at this baseline), got {state}."
            print(f"  EU-009: FAULT -- correctly reflects EU-008's own already-established real "
                  f"cooling-capacity overload (~289% utilization), not a bug in AI-004.")
        else:
            assert state == "RUNNING", f"REGRESSION: {item} not RUNNING at a healthy baseline (state={state})."
    print("  GA-001/GC-013/HB-006/HB-013 RUNNING; EU-009 correctly FAULT (real, pre-existing "
          "overload) -- PASSED.")

    state1, handle1, engine1 = _build_engine()
    engine1.run_cycle(now="2026-09-09T01:00:00Z")
    first_cycle_states = _ai004_states(state1.get_snapshot())
    print(f"  Cycle 1 (fresh engine): {first_cycle_states}")
    # STARTING wins unconditionally on cycle 1: AI-004's own cross-tab reads are ALL
    # lagged (see register_ai_layer()'s own comment), so on the very first cycle every
    # one of them is genuinely absent (nothing has EVER published before cycle 1) --
    # a real bootstrap condition, correctly distinguished from an active fault, not
    # evaluated against FAULT/OFF at all until real prior-cycle data exists.
    for item, state in first_cycle_states.items():
        assert state == "STARTING", f"REGRESSION: {item} not STARTING on cycle 1 (state={state})."
    print("  All 5 Tier-1 items STARTING on the first-ever published cycle (even EU-009, whose "
          "own EU-008 overload data doesn't exist yet either) -- PASSED.")

    print("\n=== Task requirement 14: AI-004 responds to a REAL forced fault condition ===")
    state2, handle2, engine2 = _build_engine()
    for i in range(3):
        engine2.run_cycle(now=f"2026-09-09T02:{i:02d}:00Z")

    def _forced_missing_ga001(get_input):
        return {"value": None, "status": ps.STATUS_MISSING, "inputs": [],
                "validation_basis": ps.VALIDATION_NA, "missing_reason": "PERTURBATION TEST ONLY -- forced fault."}

    engine2._models[("GA-001", "Outputs")]["fn"] = _forced_missing_ga001
    engine2.run_cycle(now="2026-09-09T02:10:00Z")  # cycle N: GA-001 and everything genuinely,
                                                     # structurally downstream of it (GC-013 -> WGS
                                                     # -> HB-006/009/012 -> HB-013) really does go
                                                     # Missing THIS cycle -- same-cycle propagation,
                                                     # unrelated to AI-004's own lag.
    pre_lag_snap = state2.get_snapshot()
    assert pre_lag_snap[("GA-001", "Outputs")]["status"] == ps.STATUS_MISSING
    assert pre_lag_snap[("HB-013", "Storage")]["status"] == ps.STATUS_MISSING
    print(f"  Cycle N (forced): real GA-001 Outputs status={pre_lag_snap[('GA-001','Outputs')]['status']}, "
          f"real HB-013 Storage status={pre_lag_snap[('HB-013','Storage')]['status']} -- the whole "
          f"downstream chain genuinely, structurally fails together, same-cycle (Phase 0's own "
          f"mechanism, unrelated to AI-004's own lag).")
    print(f"  AI-004 THIS cycle (still lagging the healthy cycle N-1): {_ai004_states(pre_lag_snap)}")

    engine2.run_cycle(now="2026-09-09T02:20:00Z")  # cycle N+1: AI-004's own lagged reads now
                                                     # catch up to cycle N's real fault.
    fault_snap = state2.get_snapshot()
    fault_states = _ai004_states(fault_snap)
    print(f"  Cycle N+1 (AI-004 catches up): {fault_states}")
    for item in AI004_TIER1_ITEMS:
        assert fault_states[item] == "FAULT", (
            f"REGRESSION: {item}'s own AI-004 state should be FAULT one cycle after GA-001's forced "
            f"Missing (every Tier-1 item here is genuinely, structurally downstream of GA-001 in the "
            f"real chain), got {fault_states[item]}."
        )
    print("  PASSED -- every Tier-1 item's own AI-004 state correctly, genuinely reports FAULT once "
          "its lagged read catches up to the real forced fault -- not silently staying RUNNING, and "
          "each one's own function actually EXECUTED (a real diagnostic verdict, not a structural "
          "blackout) because these reads are lagged, not same-cycle hard-blocking.")

    print("\n=== Task requirement 10: AI-011 time-series logging ===")
    ai011 = snap[("AI-011", "LoggingStatus")]["value"]
    print(f"  logged={ai011['logged']}", f"error={ai011.get('error')}" if not ai011["logged"] else f"row_id={ai011.get('row_id')}")
    print("  (If 'logged=False': the digital_twin_cycle_log table hasn't been created in this "
          "Supabase project yet -- run data/supabase_schema.sql's new DDL to enable persistence. "
          "Either way this is a real, known, Calculated result, not hidden.)")

    print("\n=== Task requirement 11: AI-012/013 relabeling only ===")
    ai012 = snap[("AI-012", "Identity")]["value"]
    ai013 = snap[("AI-013", "Identity")]["value"]
    print(f"  AI-012 real_modules: {ai012['real_modules']}")
    print(f"  AI-013 real_modules: {ai013['real_modules']}")
    assert set(AI012_REAL_MODULES) <= set(AI013_REAL_MODULES) | {"dispatch_ga.py"}

    print("\n=== Task requirement 14: AI-013 read-only enforcement -- REAL mechanical check ===")
    all_clear, violations = verify_ai013_read_only()
    print(f"  Scanned {len(AI013_REAL_MODULES)} files for shared_plant_state.py's writer-only API "
          f"({', '.join(_WRITE_API_MARKERS)}).")
    if not all_clear:
        print(f"  VIOLATIONS: {violations}")
    assert all_clear, f"REGRESSION: AI-013's own real modules are NOT read-only: {violations}"
    print("  PASSED -- none of AI-013's 11 real modules reference SharedPlantState's writer-only "
          "API anywhere in their own source text -- a mechanical enforcement check, not a "
          "code-review claim.")

    print("\n=== Task requirement 12: AI-014, low-content for a single-train plant ===")
    ai014 = snap[("AI-014", "OrchestrationState")]["value"]
    assert ai014["active_modules"] == 1 and ai014["orchestration_active"] is False
    print(f"  {ai014} -- PASSED.")

    print("\n=== Task requirement 13: AI-015, conditional on HB-011 ===")
    ai015 = snap[("AI-015", "RfnboStatus")]["value"]
    hb011_live = snap[("HB-011", "Electrolyser")]["value"]
    print(f"  HB-011 running={hb011_live['running']}  AI-015 applicable={ai015['applicable']}")
    assert ai015["applicable"] == hb011_live["running"]
    print("  PASSED -- AI-015's own applicability tracks HB-011's real live running flag exactly.")

    print("\nAll ai_automation_layer.py self-tests PASSED.")
