"""
Dynamics layer v0 -- a transient WHAT-IF simulation on top of the steady-state engine.

WHAT THIS IS: a thin wrapper that calls the existing steady-state engine as a black box once
per sub-step (dt of seconds/minutes instead of one hour) and adds exactly TWO first-order
states between the engine's steady-state answer and what the rest of the plant sees:

  T_gasifier  -- lag from the temperature SETPOINT to the temperature GA-001 actually uses.
  GasHoldup   -- lag of GA-001's outlet flow and composition behind GA-001's own steady-state
                 result (a well-mixed-bed / residence-time effect).

WHAT THIS IS NOT:
  * GC, HB, EU and SA models are NOT given any inertia. They follow the (lagged) GA-001
    output algebraically, exactly as they do in the hourly runtime. Only T_gasifier and
    GasHoldup have inertia in v0 -- anything else you see changing slowly is an existing
    per-cycle lag or an inventory (see docs/dynamics_v0.md).
  * No physics equation, Confirmed value, SharedPlantState, simulation_engine API or the
    hourly runtime (scripts/run_continuous_cycle.py) is modified. GA-001's own equations are
    called unchanged (ga001_gasifier_model.ga001_model); inputs are replaced through the
    engine's existing public promote_to_measurement().
  * Nothing here is Measured or Confirmed. Every time constant is tagged ASSUMED (see
    TAU_SPECS: value, range, reasoning, and the question that would replace it). Results are
    "what-if" curves, not validated against plant data.
  * No database, no network, no credentials: everything runs in-process with synthetic
    timestamps.

EQUATIONS (exact exponential update, stable at any dt; a state moves toward its target):

    dx/dt = (x_target - x) / tau        ->        x <- x_target + (x - x_target) * exp(-dt / tau)

tau <= 0 means "no lag" (x <- x_target), which is how the layer is switched off. Per sub-step
the order is: (1) scenario inputs for the step are fixed, (2) T_gasifier is relaxed toward the
setpoint, (3) the cycle clock is set to dt (cycle_clock.set_elapsed_hours, always reset in a
finally), (4) the engine runs ONE cycle with the lagged T_gasifier, (5) inside that cycle the
GasHoldup wrapper relaxes GA-001's outputs toward the steady-state target it just computed,
(6) the row is recorded at the END of the sub-step. Everything in a row therefore belongs to the
same instant.

PER-CYCLE LAGS THAT CHANGE MEANING AT A SHORT STEP (reported, NOT fixed -- see docs/dynamics_v0.md):
the engine's lagged_depends_on couplings are one CYCLE long, not one second long. At dt = 60 s
the FE-005 -> GA-001 feed read, the GA-001 <-> HB-009 recycle, the HB-013 / HB-018 / EU-006 loop
and the EU-008 pair each become a 60 s delay (or a 60 s loop gain). Only EU008_DAMPING is
converted here, by the identity-preserving rule  damping(dt) = exp(-dt / tau_e) = 2**(-dt/1h),
tau_e = 1 h / ln 2, which is exactly 0.5 at dt = 1 h.
"""
import copy
import math
from dataclasses import dataclass

from . import cycle_clock
from . import eu_utilities_chp as eu
from . import fe_feed_handling as fe
from . import ga001_gasifier_model as ga001
from . import gc_gas_cleaning_chain as gc
from . import hb_remaining_chain as hbrem
from . import hb_wgs_psa_storage_chain as hbchain
from . import plant_status as ps
from . import sa_virtual_sensors as sa
from . import shared_plant_state as sps
from . import simulation_engine as se
from . import uncertainty
from . import ai_automation_layer as ai

RESULT_STATUS = ("What-if simulation with ASSUMED time constants -- not Measured, not Confirmed, "
                 "not validated against plant data.")
LIMITS = (
    "Only T_gasifier and GasHoldup have inertia. GC, HB, EU and SA models are algebraic and follow the "
    "lagged GA-001 output with no lag of their own.",
    "The engine's one-cycle lagged couplings (FE-005->GA-001, GA-001<->HB-009 recycle, HB-013/HB-018/EU-006, "
    "EU-008 pair) are per-CYCLE: at a short dt they become dt-long delays. They are not fixed in v0.",
    "Feed and ER steps act instantly on the plant inputs; no actuator or conveyor dynamics.",
    "Gasifier temperature enters GA-001 only through the water-gas-shift equilibrium constant (no energy "
    "balance, no T-dependent carbon conversion or tar), so T steps move the outputs only weakly.",
)


@dataclass(frozen=True)
class TauSpec:
    name: str
    default_s: float
    range_s: tuple
    status: str            # always "Assumed" in v0
    what: str
    reasoning: str
    question_for_doking: str


TAU_SPECS = {
    "T_gasifier": TauSpec(
        "T_gasifier", 120.0, (30.0, 600.0), ps.STATUS_ASSUMED,
        "lag from the gasifier temperature setpoint to the temperature GA-001 uses",
        "ENGINEERING PLACEHOLDER, no source. data/equipment_registry.json (GA-001, 'Operating temperature "
        "(typical)') says the 950 degC matches 'the Simulink thermal-lag model', but that model is not in this "
        "repository and no lag value is documented anywhere in it, so 120 s is only the figure proposed in earlier "
        "work. The range 30-600 s brackets a hot, well-insulated fluidised bed responding to a setpoint change "
        "(seconds to minutes) without including the hours-long thermal soak of the 150 mm refractory lining, which "
        "this single lag does not represent.",
        "What is the real step response of the bed/outlet temperature to a setpoint or air-flow change (time to 63 % "
        "and 95 %), and what is the heating actuator (burner, preheated air, electric)?"),
    "GasHoldup": TauSpec(
        "GasHoldup", 1200.0, (8.0, 1200.0), ps.STATUS_ASSUMED,
        "lag of GA-001's outlet flow and composition behind its steady-state result",
        "Residence-time argument, ASSUMED mapping. Registry geometry (GA-001: ID 600 mm, height 4000 mm incl. bed and "
        "freeboard) gives a vessel volume of 1.131 m3, i.e. a whole-vessel GAS residence time of only ~8 s at the "
        "audited flow (513 m3/h actual at 950 degC, 1.11 bar) -- the lower end of the range, negligible next to a 60 s "
        "step. A bubbling bed is well mixed in its SOLIDS, and the registry's 'Residence time (design)' = 20 min is "
        "the solids residence time; a well-mixed (CSTR) inventory responds to a change in fuel input with a first-order "
        "lag equal to its residence time, so the default is 1200 s. That is the UPPER end: it is physically right for "
        "FEED steps (fuel inventory turnover) and too slow for ER/air steps (gas-phase, seconds). v0 has one tau for "
        "all causes. The 20 min value is a DOK-ING datasheet design figure ('typical ... at this scale'); the CSTR "
        "mapping itself is the assumption.",
        "Bed solids inventory (kg) and fuel feed rate to give the real solids turnover time, plus any measured "
        "outlet-gas response to a feed step; separately, the freeboard gas residence time."),
    "EU008_cooling_water": TauSpec(
        "EU008_cooling_water", 3600.0 / math.log(2.0), (1800.0, 14400.0), ps.STATUS_ASSUMED,
        "EU-008 tower-water relaxation, the per-cycle damping EU008_DAMPING = 0.5 converted to continuous time",
        "Derived, not new: the existing model relaxes the supply temperature by a factor 0.5 per 1 h cycle "
        "(EU008_DAMPING, itself Assumed, 'represents the tower water's own thermal mass'). tau_e = 1 h / ln 2 = "
        "5193 s makes exp(-dt/tau_e) equal 0.5 exactly at dt = 1 h, so hourly numbers are unchanged. The range is an "
        "ENGINEERING PLACEHOLDER (no source) for the basin thermal mass. 0 disables the conversion (damping stays "
        "0.5 per sub-step).",
        "Cooling-tower basin water volume and circulation rate (to compute the real thermal time constant)."),
}

_GA_LAGGED_KEYS = ("dry_flow_nm3_h", "wet_flow_nm3_h", "H2_mol_pct_dry", "CO_mol_pct_dry", "CO2_mol_pct_dry",
                   "CH4_mol_pct_dry", "N2_mol_pct_dry", "H2O_mol_pct_wet")

SERIES_UNITS = {
    "t_s": "s", "T_setpoint_C": "degC", "T_gasifier_C": "degC", "feed_kg_h": "kg/h (as received)", "ER": "-",
    "ga001_dry_flow_nm3_h": "Nm3/h", "ga001_dry_flow_target_nm3_h": "Nm3/h (steady-state target)",
    "H2_pct_dry": "mol% dry", "CO_pct_dry": "mol% dry", "CO2_pct_dry": "mol% dry", "CH4_pct_dry": "mol% dry",
    "N2_pct_dry": "mol% dry", "lhv_mj_nm3": "MJ/Nm3", "h2_production_kg_h": "kg/h",
    "hb013_storage_kg": "kg", "hb013_inflow_kg_h": "kg/h", "hb013_outflow_kg_h": "kg/h",
    "eu008_demand_kw": "kW", "eu008_supply_temp_c": "degC", "eu010_soc_kwh": "kWh", "ai004_eu009_state": "state",
}


def relax(x, target, dt_s, tau_s):
    """Exact exponential update of a first-order state. tau_s <= 0 means no lag."""
    if tau_s <= 0.0:
        return target
    return target + (x - target) * math.exp(-dt_s / tau_s)


def eu008_damping_for_dt(dt_s, tau_e_s):
    """Per-sub-step damping factor exp(-dt/tau_e), written as 0.5 ** (dt / half-life) with half-life = tau_e * ln 2
    so that the DEFAULT tau_e (= 1 h / ln 2, i.e. half-life exactly 3600 s) gives exactly 0.5 at dt = 3600 s -- the
    identity that keeps hourly numbers bit-identical. tau_e <= 0 keeps the old per-cycle 0.5."""
    if tau_e_s <= 0.0:
        return 0.5
    half_life_s = 3600.0 if tau_e_s == TAU_SPECS["EU008_cooling_water"].default_s else tau_e_s * math.log(2.0)
    return 0.5 ** (dt_s / half_life_s)


def synthetic_timestamp(i):
    """Same synthetic label tab1_integration.build_live_snapshot() uses for cycle i (NOT wall-clock time)."""
    return f"2026-09-10T{(i // 60) % 24:02d}:{i % 60:02d}:00Z"


def resolve_taus(taus=None):
    """{name: seconds}. None -> the Assumed defaults. Unknown names are rejected (every tau used must be
    one that is listed in TAU_SPECS and therefore in result.assumptions)."""
    out = {name: spec.default_s for name, spec in TAU_SPECS.items()}
    for name, value in (taus or {}).items():
        if name not in TAU_SPECS:
            raise ValueError(f"unknown time constant {name!r}; known: {sorted(TAU_SPECS)}")
        if value < 0:
            raise ValueError(f"time constant {name} must be >= 0 (0 = off), got {value}")
        out[name] = float(value)
    return out


def _normalise_scenario(scenario):
    allowed = {"t_s", "feed_kg_h", "feed_rel", "ER", "T_setpoint_C"}
    steps = []
    for raw in scenario or []:
        extra = set(raw) - allowed
        if extra:
            raise ValueError(f"unknown scenario key(s) {sorted(extra)}; allowed: {sorted(allowed)}")
        if "t_s" not in raw:
            raise ValueError("every scenario step needs t_s")
        if "feed_kg_h" in raw and "feed_rel" in raw:
            raise ValueError("give feed_kg_h (absolute) OR feed_rel (relative to the base feed), not both")
        steps.append(dict(raw))
    return sorted(steps, key=lambda s: s["t_s"])


class TransientResult:
    """Time series + the honesty metadata. `series` is a list of dicts (one per sub-step, plus t = 0)."""

    def __init__(self, series, assumptions, used_taus, meta, final_snapshot):
        self.series = series
        self.assumptions = assumptions
        self.used_taus = sorted(used_taus)
        self.meta = meta
        self.final_snapshot = final_snapshot
        self.status = RESULT_STATUS
        self.limits = LIMITS
        self.units = dict(SERIES_UNITS)

    def column(self, name):
        return [row[name] for row in self.series]

    def verify_honesty(self):
        """Raises if a time constant was used without being listed as an Assumed assumption."""
        listed = {a["name"] for a in self.assumptions}
        unlisted = set(self.used_taus) - listed
        if unlisted:
            raise AssertionError(f"time constant(s) used but not listed as assumptions: {sorted(unlisted)}")
        bad = [a["name"] for a in self.assumptions if a["status"] != ps.STATUS_ASSUMED]
        if bad:
            raise AssertionError(f"time constant(s) not tagged Assumed: {bad}")
        return True

    def to_dataframe(self):
        import pandas as pd  # optional; pandas is already a project requirement
        return pd.DataFrame(self.series)


class _Context:
    """Mutable run state shared by the engine overrides (closures read it at call time)."""

    def __init__(self, taus, dt_s):
        self.taus = taus
        self.dt_s = dt_s
        self.dynamics_on = False       # False during warm-up: every wrapper is a pass-through
        self.feed_kg_h = fe.FE001_DEFAULT_DELIVERY_RATE_KG_H
        self.er = uncertainty.ASSUMPTIONS["air_equivalence_ratio"]["point"]
        self.t_setpoint_c = ga001.GA001_OPERATING_TEMPERATURE_C
        self.t_state_c = ga001.GA001_OPERATING_TEMPERATURE_C
        self.ga_state = None
        self.ga_last_target = None
        self.ga_target_now = None
        self.used_taus = set()

    def relax(self, name, x, target):
        tau = self.taus[name]
        if tau > 0.0:
            self.used_taus.add(name)
        return relax(x, target, self.dt_s, tau)


def _input_reader(ctx, attr, note):
    def reader(get_input):
        return {"value": getattr(ctx, attr), "status": ps.STATUS_ASSUMED, "validation_basis": ps.VALIDATION_NA,
                "confidence_note": f"dynamics-v0 scenario input: {note} (Assumed what-if value, not Measured)."}
    return reader


def _ga001_holdup_model(ctx):
    def ga001_with_holdup(get_input):
        result = ga001.ga001_model(get_input)          # GA-001's own equations, unchanged: the steady-state TARGET
        target = result["value"]
        ctx.ga_target_now = target
        if not ctx.dynamics_on or ctx.taus["GasHoldup"] <= 0.0:
            ctx.ga_last_target = {k: target[k] for k in _GA_LAGGED_KEYS}
            return result
        if ctx.ga_state is None:                        # first dynamic sub-step starts from the steady state
            ctx.ga_state = dict(ctx.ga_last_target)
        for key in _GA_LAGGED_KEYS:
            ctx.ga_state[key] = ctx.relax("GasHoldup", ctx.ga_state[key], target[key])
        lagged = dict(target)
        lagged.update(ctx.ga_state)
        out = dict(result)
        out["value"] = lagged
        out["confidence_note"] = (
            result.get("confidence_note", "") +
            f" [dynamics-v0 GasHoldup: outputs lagged behind this steady-state target with tau_g = {ctx.taus['GasHoldup']:g} s "
            f"(Assumed); target dry flow {target['dry_flow_nm3_h']:.4f} Nm3/h.]")
        return out
    return ga001_with_holdup


def _register_all(engine):
    for register in (fe.register_fe_chain, ga001.register_ga001, gc.register_gc_chain, hbchain.register_hb_chain,
                     hbrem.register_hb_remaining, eu.register_eu_chain, sa.register_sa_sensors, ai.register_ai_layer):
        register(engine)


def _row(ctx, t_s, snap):
    o = snap[("GA-001", "Outputs")]["value"]
    hb013 = snap[("HB-013", "Storage")]["value"]
    target = ctx.ga_target_now or o
    return {
        "t_s": t_s, "T_setpoint_C": ctx.t_setpoint_c, "T_gasifier_C": ctx.t_state_c,
        "feed_kg_h": ctx.feed_kg_h, "ER": ctx.er,
        "ga001_dry_flow_nm3_h": float(o["dry_flow_nm3_h"]), "ga001_dry_flow_target_nm3_h": float(target["dry_flow_nm3_h"]),
        "H2_pct_dry": float(o["H2_mol_pct_dry"]), "CO_pct_dry": float(o["CO_mol_pct_dry"]),
        "CO2_pct_dry": float(o["CO2_mol_pct_dry"]), "CH4_pct_dry": float(o["CH4_mol_pct_dry"]),
        "N2_pct_dry": float(o["N2_mol_pct_dry"]),
        "lhv_mj_nm3": float(snap[("SA-006", "Reading")]["value"]),
        "h2_production_kg_h": float(snap[("HB-012", "Compressor")]["value"]["h2_kg_h"]),
        "hb013_storage_kg": float(hb013["level_kg"]), "hb013_inflow_kg_h": float(hb013["inflow_kg_h"]),
        "hb013_outflow_kg_h": float(hb013["outflow_kg_h"]),
        "eu008_demand_kw": float(snap[("EU-008", "CoolingSupply")]["value"]["demand_kw"]),
        "eu008_supply_temp_c": float(snap[("EU-008", "CoolingSupply")]["value"]["supply_temp_c"]),
        "eu010_soc_kwh": float(snap[("EU-010", "UPS")]["value"]["soc_kwh"]),
        "ai004_eu009_state": snap[("AI-004", "EU-009-State")]["value"],
    }


def run_transient(scenario=None, dt_s=60.0, duration_s=7200.0, taus=None, warmup_cycles=24):
    """Runs a what-if transient and returns a TransientResult.

    scenario: list of timed step changes, each {"t_s": 600, <one or more of> "feed_kg_h": 45.8 (absolute, as
      received) | "feed_rel": 0.10 (+10 % of the base feed), "ER": 0.30, "T_setpoint_C": 920}. A step applies from the
      first sub-step that STARTS at or after t_s. Steps with t_s <= 0 are INITIAL CONDITIONS: they are applied before the
      warm-up, so the starting steady state (row 0) already has them (e.g. {"t_s": 0, "T_setpoint_C": 900}).
    dt_s / duration_s: sub-step and total length in seconds. taus: {name: seconds} overrides of TAU_SPECS (0 = off).
    warmup_cycles: engine cycles of 1 h with dynamics off, run first so every recycle/damped state starts from the
      steady state of the initial inputs (0 = no warm-up; used by the dt = 1 h identity test).
    Row 0 is that steady state at t = 0; each further row is the END of a sub-step."""
    taus = resolve_taus(taus)
    steps = _normalise_scenario(scenario)
    if dt_s <= 0 or duration_s <= 0:
        raise ValueError("dt_s and duration_s must be positive")
    n_steps = int(round(duration_s / dt_s))

    state = sps.SharedPlantState()
    engine = se.SimulationEngine(state)
    _register_all(engine)
    ctx = _Context(taus, dt_s)

    touched = {k for s in steps for k in s if k != "t_s"}
    if touched & {"feed_kg_h", "feed_rel"}:
        engine.promote_to_measurement(("FE-001-INPUT", "msw_delivery_rate_kg_h"), _input_reader(ctx, "feed_kg_h", "MSW delivery rate (kg/h as received)"))
    if "ER" in touched:
        engine.promote_to_measurement(("GA-001-INPUT", "equivalence_ratio"), _input_reader(ctx, "er", "air equivalence ratio"))
    if "T_setpoint_C" in touched:
        engine.promote_to_measurement(("GA-001-INPUT", "operating_temperature_C"), _input_reader(ctx, "t_state_c", "gasifier temperature after the T_gasifier lag"))
    if taus["GasHoldup"] > 0.0:
        engine.promote_to_measurement(("GA-001", "Outputs"), _ga001_holdup_model(ctx))

    base_feed = ctx.feed_kg_h
    saved_damping = eu.EU008_DAMPING
    series = []
    cycle_index = 0

    def apply_step(step):
        if "feed_kg_h" in step:
            ctx.feed_kg_h = float(step["feed_kg_h"])
        if "feed_rel" in step:
            ctx.feed_kg_h = base_feed * (1.0 + float(step["feed_rel"]))
        if "ER" in step:
            ctx.er = float(step["ER"])
        if "T_setpoint_C" in step:
            ctx.t_setpoint_c = float(step["T_setpoint_C"])

    applied = 0
    while applied < len(steps) and steps[applied]["t_s"] <= 0.0:      # initial conditions
        apply_step(steps[applied])
        applied += 1
    ctx.t_state_c = ctx.t_setpoint_c
    try:
        # ---- warm-up: 1 h cycles, dynamics off, initial inputs --------------------------------------
        cycle_clock.set_elapsed_hours(1.0)
        for _ in range(warmup_cycles):
            engine.run_cycle(now=synthetic_timestamp(cycle_index))
            cycle_index += 1
        if warmup_cycles:
            series.append(_row(ctx, 0.0, state.get_snapshot()))
        ctx.dynamics_on = True

        # ---- transient ------------------------------------------------------------------------------
        for k in range(n_steps):
            t_start = k * dt_s
            while applied < len(steps) and steps[applied]["t_s"] <= t_start + 1e-9:
                apply_step(steps[applied])
                applied += 1
            ctx.t_state_c = ctx.relax("T_gasifier", ctx.t_state_c, ctx.t_setpoint_c)
            cycle_clock.set_elapsed_hours(dt_s / 3600.0)
            if taus["EU008_cooling_water"] > 0.0:
                ctx.used_taus.add("EU008_cooling_water")
                eu.EU008_DAMPING = eu008_damping_for_dt(dt_s, taus["EU008_cooling_water"])
            engine.run_cycle(now=synthetic_timestamp(cycle_index))
            cycle_index += 1
            series.append(_row(ctx, (k + 1) * dt_s, state.get_snapshot()))
    finally:
        cycle_clock.set_elapsed_hours(None)
        eu.EU008_DAMPING = saved_damping

    assumptions = [
        {"name": spec.name, "value_s": taus[name], "default_s": spec.default_s, "range_s": spec.range_s,
         "status": spec.status, "what": spec.what, "reasoning": spec.reasoning,
         "question_for_doking": spec.question_for_doking, "enabled": taus[name] > 0.0}
        for name, spec in TAU_SPECS.items()
    ]
    meta = {"dt_s": dt_s, "duration_s": duration_s, "n_steps": n_steps, "warmup_cycles": warmup_cycles,
            "scenario": copy.deepcopy(steps), "timestamps": "synthetic cycle-index labels (same scheme as build_live_snapshot)"}
    return TransientResult(series, assumptions, ctx.used_taus, meta, state.get_snapshot())
