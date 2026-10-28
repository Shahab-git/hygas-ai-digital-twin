"""
Dynamics layer v0.1 -- a transient WHAT-IF simulation on top of the steady-state engine.

WHAT THIS IS: a thin wrapper that calls the existing steady-state engine as a black box once
per sub-step (dt of seconds/minutes instead of one hour) and adds first-order states between
the engine's steady-state answer and what the rest of the plant sees:

  T_gasifier  -- lag from the temperature SETPOINT to the temperature GA-001 actually uses.
  tau_conv    -- fuel conversion / bed inventory lag (minutes): acts on the dry FEED RATE
                 entering the reaction zone (the solids inventory). It does NOT act on ER.
  tau_gas     -- gas-phase transport and mixing lag (tens of seconds): acts on GA-001's
                 OUTPUT flow and composition, whatever caused the change.
  tau_rec     -- TRANSPORT DELAY of the PSA tail gas recycled to GA-001 (HB-009 -> GA-001). The
                 engine reads that tail gas one CYCLE late; here it is read tau_rec SECONDS late
                 (a buffer of past HB-009 values, linearly interpolated), supplied through the
                 get_input handed to ga001_model -- no engine or model file is touched. The delay
                 cannot be shorter than one sub-step (the current sub-step's tail gas does not exist
                 yet), so the effective delay is max(tau_rec, dt). 0 keeps the engine's one-cycle lag.

Which input change goes through which lag (v0.1):
  feed step -> tau_conv (fuel inventory) then tau_gas (gas transport)   [both]
  ER step   -> tau_gas only                                             [no tau_conv]
  T step    -> T_gasifier, then tau_gas                                 [no tau_conv]
ER skips tau_conv because air acts on the gas-phase reactions (partial oxidation, burn-out of the
volatiles) within seconds to tens of seconds; the 1200 s tau_conv maps the SOLIDS inventory of the
bed (residence time), which a change of air flow does not have to refill. This is a STRUCTURAL
ASSUMPTION, not something the model derives -- the steady-state model has no ER-dependent
conversion (carbon conversion is a fixed 0.90), so it can neither confirm nor refute it. Temperature
acts on the gas through the water-gas-shift equilibrium, a gas-phase effect, so it skips tau_conv too.
Consequence: ER_effective (the ER GA-001 sees) equals the raw ER; only the gas lag delays the ER response.

WHAT THIS IS NOT:
  * GC, HB, EU and SA models are NOT given any inertia. They follow the (lagged) GA-001
    output algebraically, exactly as they do in the hourly runtime.
  * No physics equation, Confirmed value, SharedPlantState, simulation_engine API or the
    hourly runtime (scripts/run_continuous_cycle.py) is modified. GA-001's own equations are
    called unchanged (ga001_gasifier_model.ga001_model); inputs are replaced through the
    engine's public promote_to_measurement() and through a wrapped get_input handed to ga001_model.
  * Nothing here is Measured or Confirmed. Every time constant is ASSUMED (see TAU_SPECS: value,
    range, reasoning, and the question that would replace it).
  * No database, no network, no credentials: everything runs in-process.

EQUATIONS (all exact, stable at any dt):

  one lag             x <- target + (x - target) * exp(-dt / tau)
  cascade (conv->gas) The conversion state x1 follows its input exactly. Inside a sub-step every
                      conv-lagged input moves along the SAME exponential, so GA-001's response
                      y(s) to them is y0 + (y1 - y0) * phi(s), phi(s) = (1 - exp(-s/tau_c)) / (1 - exp(-dt/tau_c)),
                      with y0 / y1 = the steady-state model evaluated at the sub-step's start / end
                      conversion state. The gas state then solves  dx/dt = (y(s) - x) / tau_g  exactly:
                          x(dt) = y0 + (x0 - y0) e^(-dt/tau_g) + (y1 - y0) * psi
                          psi   = [ (1 - e^(-dt/tau_g)) - (e^(-dt/tau_c) - e^(-dt/tau_g)) / (1 - tau_g/tau_c) ] / (1 - e^(-dt/tau_c))
                      (limit dt*e^(-dt/tau)/tau when tau_g = tau_c). This is the exact two-lag cascade for a
                      response that is linear in the conv-lagged inputs; the model's non-linearity inside one
                      sub-step is neglected (second order in the sub-step's input change).
  EU-008 damping      damping(dt) = exp(-dt/tau_e) = 0.5 ** (dt / 1 h), tau_e = 1 h / ln 2; exactly 0.5 at 1 h.

Per sub-step order: (1) scenario inputs fixed; (2) T_gasifier relaxed toward the setpoint; (3)
cycle clock set to dt (always reset in a finally); (4) the engine runs ONE cycle; inside it the
GA-001 wrapper advances tau_conv on the feed and tau_gas on the outputs; (5) the row is recorded
at the END of the sub-step, so everything in a row belongs to the same instant.

PER-CYCLE LAGS THAT CHANGE MEANING AT A SHORT STEP (reported, NOT fixed, see docs/dynamics_v0.md):
the engine's lagged_depends_on couplings are one CYCLE long. At dt = 60 s they become 60 s delays.
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
    "Only T_gasifier, tau_conv and tau_gas have inertia. GC, HB, EU and SA models are algebraic and follow the "
    "lagged GA-001 output with no lag of their own.",
    "The engine's one-cycle lagged couplings (FE-005->GA-001 feed read, HB-013/HB-018/EU-006, EU-008 pair, ...) are "
    "per-CYCLE: at a short dt they become dt-long delays. They are not fixed in v0.1.",
    "Feed and ER steps act instantly on the plant inputs; no actuator or conveyor dynamics.",
    "Gasifier temperature enters GA-001 only through the water-gas-shift equilibrium constant (no energy "
    "balance, no T-dependent carbon conversion or tar), so T steps move the outputs only weakly.",
)


@dataclass(frozen=True)
class TauSpec:
    name: str
    default_s: float
    range_s: tuple
    status: str            # always "Assumed" in v0.x
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
    "tau_conv": TauSpec(
        "tau_conv", 1200.0, (600.0, 2400.0), ps.STATUS_ASSUMED,
        "fuel conversion / bed inventory lag acting on the dry feed rate entering the reaction zone (not on ER)",
        "Mapping ASSUMED: data/equipment_registry.json (GA-001) gives 'Residence time (design)' = 20 min, described as "
        "the SOLIDS residence time in the bed ('typical for MSW/biomass gasification conversion at this scale'). A "
        "bubbling bed is well mixed in its solids, so it behaves like a CSTR, and a CSTR's inventory answers a change in "
        "its input with a first-order lag equal to its mean residence time: 20 min = 1200 s. The 20 min is a datasheet "
        "design figure; the CSTR mapping is the assumption. Range = a factor of 2 either side (600-2400 s) because "
        "real beds have dead zones and plug-flow regions that shorten the effective time and a carbon inventory that can "
        "lengthen it. ER does NOT go through this lag: air acts on the gas-phase reactions within seconds to tens of "
        "seconds, so an ER step is delayed by tau_gas only. That routing is a structural assumption, not "
        "model-derived (the steady model has no ER-dependent conversion).",
        "Bed solids inventory (kg) and fuel feed rate (to give the real solids turnover time), and the measured "
        "response of the gas composition to a feed-rate step."),
    "tau_gas": TauSpec(
        "tau_gas", 30.0, (8.0, 120.0), ps.STATUS_ASSUMED,
        "gas-phase transport and mixing lag of GA-001's outlet flow and composition",
        "Lower bound DERIVED from the registry geometry (GA-001: ID 600 mm, total height 4000 mm incl. bed and "
        "freeboard -> 1.131 m3; audited flow 125.9 Nm3/h wet = 513 m3/h actual at 950 degC and 1.11 bar -> 0.1426 m3/s): a "
        "whole-vessel plug-flow gas residence time of 7.9 s (superficial velocity 0.50 m/s, consistent with the "
        "registry's 0.5-1.5 m/s remark). That ignores solids volume, so it is a minimum. Mixing allowance, ENGINEERING "
        "PLACEHOLDER (no source): gas back-mixing in a bubbling bed (bubble/emulsion exchange), freeboard recirculation "
        "and the outlet duct to GC-001 (its volume is Missing) are taken as a factor ~4 on the plug-flow time -> 30 s; "
        "the range runs from no allowance (8 s) to a factor ~15 (120 s). Applies to every cause of a change.",
        "Freeboard and outlet-duct volumes (to give the real gas residence time), and the measured outlet-gas response "
        "to a feed or ER step."),
    "tau_rec": TauSpec(
        "tau_rec", 60.0, (10.0, 140.0), ps.STATUS_ASSUMED,
        "transport delay of the PSA tail gas recycled from HB-009 to GA-001 (replaces the engine's one-cycle lag)",
        "Derived from the registry, placeholder for the mixing model: data/equipment_registry.json (HB-009) gives a 'Tail "
        "gas buffer tank volume' = 1 m3 'ahead of the gasifier feed'. Residence time V/Q at the audited tail flow "
        "(84.3 Nm3/h, ~0.2 bar(g), 25-60 degC) is 42-47 s; at the registry's design tail flow (29.4 Nm3/h) it is 120-134 s. "
        "Default 60 s lies between them (rounded to one minute); the range's lower end, 10 s, is an ENGINEERING PLACEHOLDER "
        "(no source) for piping alone with the buffer bypassed. A well-mixed 1 m3 tank would act as a first-order lag "
        "rather than a pure delay; v0.1 models a delay, as requested. Not shorter than one sub-step (max(tau_rec, dt)).",
        "Real tail-gas path from the PSA to the gasifier: buffer-tank volume and whether it is bypassed, blower flow, pipe "
        "length, and the actual tail-gas flow and temperature."),
    "EU008_cooling_water": TauSpec(
        "EU008_cooling_water", 3600.0 / math.log(2.0), (1800.0, 14400.0), ps.STATUS_ASSUMED,
        "EU-008 tower-water relaxation, the per-cycle damping EU008_DAMPING = 0.5 converted to continuous time",
        "Derived, not new: the existing model relaxes the supply temperature by a factor 0.5 per 1 h cycle "
        "(EU008_DAMPING, itself Assumed, 'represents the tower water's own thermal mass'). tau_e = 1 h / ln 2 = "
        "5193.7 s makes exp(-dt/tau_e) equal 0.5 exactly at dt = 1 h, so hourly numbers are unchanged. The range is an "
        "ENGINEERING PLACEHOLDER (no source) for the basin thermal mass. 0 disables the conversion (damping stays "
        "0.5 per sub-step).",
        "Cooling-tower basin water volume and circulation rate (to compute the real thermal time constant)."),
}

_GA_LAGGED_KEYS = ("dry_flow_nm3_h", "wet_flow_nm3_h", "H2_mol_pct_dry", "CO_mol_pct_dry", "CO2_mol_pct_dry",
                   "CH4_mol_pct_dry", "N2_mol_pct_dry", "H2O_mol_pct_wet")
_FEED_KEY = ("GA-001-INPUT", "dry_feed_rate_kg_h")
_ER_KEY = ("GA-001-INPUT", "equivalence_ratio")
_T_KEY = ("GA-001-INPUT", "operating_temperature_C")
_MOISTURE_KEY = ("FE-005", "MoistureBalance")
_TAIL_KEY = ("HB-009", "TailGas")

SERIES_UNITS = {
    "t_s": "s", "T_setpoint_C": "degC", "T_gasifier_C": "degC", "feed_kg_h": "kg/h (as received)", "ER": "-",
    "ga001_dry_feed_raw_kg_h": "kg/h dry (what GA-001's feed input reads)", "ga001_dry_feed_effective_kg_h": "kg/h dry (after tau_conv)",
    "ga001_ER_effective": "- (equals the raw ER: ER is not lagged by tau_conv)",
    "ga001_dry_flow_nm3_h": "Nm3/h", "ga001_dry_flow_target_nm3_h": "Nm3/h (steady-state target at the raw inputs)",
    "ga001_dry_flow_y0_nm3_h": "Nm3/h (model at the sub-step's start state)", "ga001_dry_flow_y1_nm3_h": "Nm3/h (model at the sub-step's end state)",
    "H2_pct_dry": "mol% dry", "CO_pct_dry": "mol% dry", "CO2_pct_dry": "mol% dry", "CH4_pct_dry": "mol% dry",
    "N2_pct_dry": "mol% dry", "lhv_mj_nm3": "MJ/Nm3", "h2_production_kg_h": "kg/h",
    "hb013_storage_kg": "kg", "hb013_inflow_kg_h": "kg/h", "hb013_outflow_kg_h": "kg/h",
    "eu008_demand_kw": "kW", "eu008_supply_temp_c": "degC", "eu010_soc_kwh": "kWh", "ai004_eu009_state": "state",
    "recycle_delay_s": "s (effective delay of the HB-009 tail gas read by GA-001)",
    "probe_conv": "fraction (unit step through tau_conv)", "probe_gas": "fraction (unit step through tau_gas)",
    "probe_cascade": "fraction (unit step through tau_conv then tau_gas)",
}


def relax(x, target, dt_s, tau_s):
    """Exact exponential update of a first-order state. tau_s <= 0 means no lag."""
    if tau_s <= 0.0:
        return target
    return target + (x - target) * math.exp(-dt_s / tau_s)


def cascade_psi(dt_s, tau_conv_s, tau_gas_s):
    """psi of the exact cascade update (module docstring). 0 < psi < 1 - exp(-dt/tau_gas)."""
    e_c = math.exp(-dt_s / tau_conv_s)
    e_g = math.exp(-dt_s / tau_gas_s)
    if abs(tau_gas_s - tau_conv_s) <= 1e-9 * max(tau_gas_s, tau_conv_s):
        cross = dt_s * e_c / tau_conv_s
    else:
        cross = (e_c - e_g) / (1.0 - tau_gas_s / tau_conv_s)
    return ((1.0 - e_g) - cross) / (-math.expm1(-dt_s / tau_conv_s))


def gas_stage(x0, y0, y1, dt_s, tau_gas_s, tau_shape_s=None):
    """Advance the gas-phase lag one sub-step. x0 = gas state at the start, y0 / y1 = the steady-state model's
    answer at the start / end conv state, tau_shape_s = the time constant of the exponential along which the
    inputs moved this sub-step (None or <= 0: the input is taken to move linearly; y1 == y0: constant)."""
    if tau_gas_s <= 0.0:
        return y1
    if y1 == y0:
        return relax(x0, y1, dt_s, tau_gas_s)
    if tau_shape_s is None or tau_shape_s <= 0.0:
        # the input moves LINEARLY across the sub-step (e.g. the delayed recycle): exact for a ramp
        e_g = math.exp(-dt_s / tau_gas_s)
        slope_tau = (y1 - y0) * tau_gas_s / dt_s
        return y1 - slope_tau + (x0 - y0 + slope_tau) * e_g
    return y0 + (x0 - y0) * math.exp(-dt_s / tau_gas_s) + (y1 - y0) * cascade_psi(dt_s, tau_shape_s, tau_gas_s)


def cascade_step_response(t_s, tau_conv_s, tau_gas_s):
    """Exact analytic response of two first-order lags in series to a unit step at t = 0:
    1 - (tau1 e^(-t/tau1) - tau2 e^(-t/tau2)) / (tau1 - tau2); the equal-tau limit is 1 - (1 + t/tau) e^(-t/tau)."""
    if abs(tau_conv_s - tau_gas_s) <= 1e-9 * max(tau_conv_s, tau_gas_s):
        return 1.0 - (1.0 + t_s / tau_conv_s) * math.exp(-t_s / tau_conv_s)
    return 1.0 - (tau_conv_s * math.exp(-t_s / tau_conv_s) - tau_gas_s * math.exp(-t_s / tau_gas_s)) / (tau_conv_s - tau_gas_s)


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


def _interp_leaves(a, b, w):
    """Linear interpolation of the numeric leaves of two identically shaped values (dicts recursed)."""
    if isinstance(a, dict):
        return {k: (_interp_leaves(a[k], b[k], w) if k in b else a[k]) for k in a}
    if isinstance(a, bool) or not isinstance(a, (int, float)) or isinstance(b, bool) or not isinstance(b, (int, float)):
        return a
    return a + (b - a) * w


def delayed_entry(buffer, t_query_s, tol_s):
    """The published HB-009 tail-gas entry as it was at time t_query_s. `buffer` = [(t_s, entry), ...] in time order.
    Exactly on a node -> that node's entry object UNCHANGED (this is what makes one cycle at dt = 1 h bit-identical to the
    engine's own lagged read); before the first node -> the first; at/after the last -> the last (delay clamps to one
    sub-step); otherwise linear interpolation of the numeric values. Returns (entry, interpolated: bool)."""
    if not buffer:
        return None, False
    if t_query_s <= buffer[0][0] + tol_s:
        return buffer[0][1], False
    if t_query_s >= buffer[-1][0] - tol_s:
        return buffer[-1][1], False
    for (ta, ea), (tb, eb) in zip(buffer, buffer[1:]):
        if ta <= t_query_s <= tb:
            if abs(t_query_s - ta) <= tol_s:
                return ea, False
            if abs(t_query_s - tb) <= tol_s:
                return eb, False
            w = (t_query_s - ta) / (tb - ta)
            out = dict(ea)
            out["value"] = _interp_leaves(ea["value"], eb["value"], w)
            return out, True
    return buffer[-1][1], False


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
        self.t_prev_c = self.t_state_c
        self.t_override_active = False
        # warm-up bookkeeping (initial conditions of the lags)
        self.warm_feed = None
        self.warm_er = None
        self.warm_out = None
        # conv / gas states
        self.feed_eff = None
        self.er_eff = None
        self.ga_state = None
        # recycle delay: published HB-009 tail-gas entries with their end-of-sub-step times
        self.tail_buffer = []
        self.t_end_s = 0.0
        self.recycle_interpolated = False
        self.recycle_delay_s = None
        # per-sub-step diagnostics for the series
        self.diag = {}
        self.used_taus = set()

    def relax(self, name, x, target):
        tau = self.taus[name]
        if tau > 0.0:
            self.used_taus.add(name)
        return relax(x, target, self.dt_s, tau)


def _input_reader(ctx, attr, note):
    def reader(get_input):
        return {"value": getattr(ctx, attr), "status": ps.STATUS_ASSUMED, "validation_basis": ps.VALIDATION_NA,
                "confidence_note": f"dynamics-v0.1 scenario input: {note} (Assumed what-if value, not Measured)."}
    return reader


def _substituted(get_input, ctx, feed, er, t_c, raw_feed, t_ref_s=None):
    """A get_input for ga001_model with the conv-lagged feed/ER and the given temperature substituted."""
    ratio = (feed / raw_feed) if raw_feed else 1.0
    t_ref = ctx.t_end_s if t_ref_s is None else t_ref_s      # time the recycled tail gas is referred to

    def gi(key):
        if key == _FEED_KEY:
            entry = dict(get_input(key))
            entry["value"] = feed
            return entry
        if key == _ER_KEY:
            entry = dict(get_input(key))
            entry["value"] = er
            return entry
        if key == _T_KEY:
            entry = dict(get_input(key))
            entry["value"] = t_c
            return entry
        if key == _TAIL_KEY and ctx.dynamics_on and ctx.taus["tau_rec"] > 0.0:
            entry, interpolated = delayed_entry(ctx.tail_buffer, t_ref - ctx.taus["tau_rec"], 1e-9 * max(ctx.dt_s, 1.0))
            if entry is not None:
                ctx.used_taus.add("tau_rec")
                if t_ref_s is None:        # only the published (end-state) call decides whether the result is altered
                    ctx.recycle_interpolated = ctx.recycle_interpolated or interpolated
                ctx.recycle_delay_s = max(ctx.taus["tau_rec"], ctx.dt_s)
                return entry
            return get_input(key)
        if key == _MOISTURE_KEY:
            entry = get_input(key)
            if entry["status"] != ps.STATUS_MISSING and ratio != 1.0:
                entry = dict(entry)
                value = dict(entry["value"])
                value["residual_water_kg_h"] = value["residual_water_kg_h"] * ratio   # feed-linked: scales with the fuel
                entry["value"] = value
            return entry
        return get_input(key)
    return gi


def _ga001_dynamic_model(ctx):
    def ga001_dynamic(get_input):
        tau = ctx.taus
        if not ctx.dynamics_on:
            result = ga001.ga001_model(get_input)
            ctx.warm_feed = get_input(_FEED_KEY)["value"]
            ctx.warm_er = get_input(_ER_KEY)["value"]
            ctx.warm_out = {k: result["value"][k] for k in _GA_LAGGED_KEYS}
            return result

        ctx.recycle_interpolated = False
        feed_raw = get_input(_FEED_KEY)["value"]
        er_raw = get_input(_ER_KEY)["value"]
        t_end = get_input(_T_KEY)["value"]            # the T_gasifier-lagged value (the engine override)
        t_start = ctx.t_prev_c if ctx.t_override_active else t_end

        # --- conversion / bed-inventory lag on the INPUTS of the reaction zone ------------------------------
        if tau["tau_conv"] > 0.0:
            if ctx.feed_eff is None:        # no warm-up (identity runs): start from the first input values
                ctx.feed_eff = ctx.warm_feed if ctx.warm_feed is not None else feed_raw
            f0 = ctx.feed_eff
            f1 = ctx.relax("tau_conv", f0, feed_raw)
            ctx.feed_eff = f1
        else:
            f0 = f1 = feed_raw
        e0 = e1 = er_raw                    # ER bypasses tau_conv: a new ER holds for the whole sub-step
        ctx.er_eff = er_raw

        # --- steady-state model at the sub-step's end state (the published answer's target) and start state ----
        y1_value = ga001.ga001_model(_substituted(get_input, ctx, f1, e1, t_end, feed_raw))
        if (f0, e0, t_start) == (f1, e1, t_end) and tau["tau_rec"] <= 0.0:
            y0_value = y1_value
        else:   # the recycled tail gas is referred to the sub-step's START time here, to its END time in y1
            y0_value = ga001.ga001_model(_substituted(get_input, ctx, f0, e0, t_start, feed_raw, t_ref_s=ctx.t_end_s - ctx.dt_s))
        y1, y0 = y1_value["value"], y0_value["value"]

        # --- gas-phase lag on the OUTPUTS: exact cascade along the exponential the inputs moved on ----------
        conv_moved = tau["tau_conv"] > 0.0 and f0 != f1
        if conv_moved:
            shape = tau["tau_conv"]
        elif ctx.t_override_active and tau["T_gasifier"] > 0.0 and t_start != t_end:
            shape = tau["T_gasifier"]
        else:
            shape = None
        if ctx.ga_state is None:
            ctx.ga_state = dict(ctx.warm_out) if ctx.warm_out is not None else {k: y0[k] for k in _GA_LAGGED_KEYS}
        if tau["tau_gas"] > 0.0:
            ctx.used_taus.add("tau_gas")
        for key in _GA_LAGGED_KEYS:
            ctx.ga_state[key] = gas_stage(ctx.ga_state[key], y0[key], y1[key], ctx.dt_s, tau["tau_gas"], shape)

        # unlagged steady-state target at the RAW inputs (what a steady-state run would give right now)
        raw_target = ga001.ga001_model(_substituted(get_input, ctx, feed_raw, er_raw, ctx.t_setpoint_c, feed_raw))["value"]
        ctx.diag = {"feed_raw": feed_raw, "feed_eff": f1, "er_eff": e1, "y0": y0["dry_flow_nm3_h"], "y1": y1["dry_flow_nm3_h"],
                    "target": raw_target["dry_flow_nm3_h"]}

        lagged = dict(y1)
        lagged.update(ctx.ga_state)
        out = dict(y1_value)
        out["value"] = lagged
        if tau["tau_conv"] > 0.0 or tau["tau_gas"] > 0.0 or ctx.recycle_interpolated:
            out["confidence_note"] = (
                y1_value.get("confidence_note", "") +
                f" [dynamics-v0.1: tau_conv={tau['tau_conv']:g} s on the feed, tau_gas={tau['tau_gas']:g} s on outputs, "
                f"tau_rec={tau['tau_rec']:g} s tail-gas delay (all Assumed); steady-state target dry flow "
                f"{raw_target['dry_flow_nm3_h']:.4f} Nm3/h.]")
        return out
    return ga001_dynamic


def _register_all(engine):
    for register in (fe.register_fe_chain, ga001.register_ga001, gc.register_gc_chain, hbchain.register_hb_chain,
                     hbrem.register_hb_remaining, eu.register_eu_chain, sa.register_sa_sensors, ai.register_ai_layer):
        register(engine)


def _row(ctx, t_s, snap):
    o = snap[("GA-001", "Outputs")]["value"]
    hb013 = snap[("HB-013", "Storage")]["value"]
    d = ctx.diag
    return {
        "t_s": t_s, "T_setpoint_C": ctx.t_setpoint_c, "T_gasifier_C": ctx.t_state_c,
        "feed_kg_h": ctx.feed_kg_h, "ER": ctx.er,
        "ga001_dry_feed_raw_kg_h": d.get("feed_raw"), "ga001_dry_feed_effective_kg_h": d.get("feed_eff"),
        "ga001_ER_effective": d.get("er_eff"),
        "ga001_dry_flow_nm3_h": float(o["dry_flow_nm3_h"]),
        "ga001_dry_flow_target_nm3_h": float(d.get("target", o["dry_flow_nm3_h"])),
        "ga001_dry_flow_y0_nm3_h": d.get("y0"), "ga001_dry_flow_y1_nm3_h": d.get("y1"),
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
        "recycle_delay_s": ctx.recycle_delay_s,
        "probe_conv": ctx.probe["conv"], "probe_gas": ctx.probe["gas"], "probe_cascade": ctx.probe["cascade"],
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
    Row 0 is that steady state at t = 0; each further row is the END of a sub-step.
    The series also carries a LAG PROBE: a unit step at the first scenario step after t = 0 pushed through tau_conv,
    tau_gas and the cascade with the very same update functions, so the time constants can be read (and tested)
    without the plant's own feedback loops."""
    taus = resolve_taus(taus)
    steps = _normalise_scenario(scenario)
    if dt_s <= 0 or duration_s <= 0:
        raise ValueError("dt_s and duration_s must be positive")
    n_steps = int(round(duration_s / dt_s))

    state = sps.SharedPlantState()
    engine = se.SimulationEngine(state)
    _register_all(engine)
    ctx = _Context(taus, dt_s)
    ctx.probe = {"conv": 0.0, "gas": 0.0, "cascade": 0.0}
    probe_state = {"conv": 0.0, "gas": 0.0, "cascade": 0.0}
    probe_t_step = next((s["t_s"] for s in steps if s["t_s"] > 0.0), None)

    touched = {k for s in steps for k in s if k != "t_s"}
    if touched & {"feed_kg_h", "feed_rel"}:
        engine.promote_to_measurement(("FE-001-INPUT", "msw_delivery_rate_kg_h"), _input_reader(ctx, "feed_kg_h", "MSW delivery rate (kg/h as received)"))
    if "ER" in touched:
        engine.promote_to_measurement(_ER_KEY, _input_reader(ctx, "er", "air equivalence ratio"))
    if "T_setpoint_C" in touched:
        ctx.t_override_active = True
        engine.promote_to_measurement(_T_KEY, _input_reader(ctx, "t_state_c", "gasifier temperature after the T_gasifier lag"))
    if taus["tau_conv"] > 0.0 or taus["tau_gas"] > 0.0 or taus["tau_rec"] > 0.0:
        engine.promote_to_measurement(("GA-001", "Outputs"), _ga001_dynamic_model(ctx))

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
    ctx.t_state_c = ctx.t_prev_c = ctx.t_setpoint_c
    try:
        # ---- warm-up: 1 h cycles, dynamics off, initial inputs --------------------------------------
        cycle_clock.set_elapsed_hours(1.0)
        for _ in range(warmup_cycles):
            engine.run_cycle(now=synthetic_timestamp(cycle_index))
            cycle_index += 1
        if warmup_cycles:
            series.append(_row(ctx, 0.0, state.get_snapshot()))
            ctx.tail_buffer.append((0.0, state.get_snapshot()[_TAIL_KEY]))      # steady-state tail gas at t = 0
        ctx.dynamics_on = True

        # ---- transient ------------------------------------------------------------------------------
        for k in range(n_steps):
            t_start = k * dt_s
            while applied < len(steps) and steps[applied]["t_s"] <= t_start + 1e-9:
                apply_step(steps[applied])
                applied += 1
            ctx.t_prev_c = ctx.t_state_c
            ctx.t_state_c = ctx.relax("T_gasifier", ctx.t_state_c, ctx.t_setpoint_c)
            # lag probe: unit step from the first scenario step on (the same update functions as the plant)
            if probe_t_step is not None and t_start + 1e-9 >= probe_t_step:
                c0 = probe_state["conv"]
                c1 = relax(c0, 1.0, dt_s, taus["tau_conv"])
                probe_state["conv"] = c1
                probe_state["gas"] = relax(probe_state["gas"], 1.0, dt_s, taus["tau_gas"])
                probe_state["cascade"] = gas_stage(probe_state["cascade"], c0, c1, dt_s, taus["tau_gas"],
                                                    taus["tau_conv"] if taus["tau_conv"] > 0.0 and c1 != c0 else None)
                ctx.probe = dict(probe_state)
            cycle_clock.set_elapsed_hours(dt_s / 3600.0)
            if taus["EU008_cooling_water"] > 0.0:
                ctx.used_taus.add("EU008_cooling_water")
                eu.EU008_DAMPING = eu008_damping_for_dt(dt_s, taus["EU008_cooling_water"])
            ctx.t_end_s = (k + 1) * dt_s
            engine.run_cycle(now=synthetic_timestamp(cycle_index))
            cycle_index += 1
            snapshot = state.get_snapshot()
            if snapshot[_TAIL_KEY]["status"] != ps.STATUS_MISSING:
                ctx.tail_buffer.append((ctx.t_end_s, snapshot[_TAIL_KEY]))
            series.append(_row(ctx, ctx.t_end_s, snapshot))
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
