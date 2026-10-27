"""
Cycle clock -- the ONE place that says how many real hours one simulation
cycle represents (audit finding 1, docs/audit_2026-10-27.md).

Why this exists: every accumulator in the plant model (FE-001 inventory,
HB-013 H2 storage, EU-010 UPS state of charge, HB-018 dispensing, EU CHP
H2 budget) multiplies a rate (per hour) by "hours per cycle". That number
used to be the module constant hb_wgs_psa_storage_chain.ASSUMED_HOURS_PER_
CYCLE = 1.0, fixed at design time on the premise that the continuous
runtime fires exactly once per hour. GitHub's scheduler is best-effort and
the real gaps were 3-6 h, so the model advanced 1 h of inventory per 3-6 h
of wall-clock time.

Contract (deliberately tiny, no engine API change):

  hours_per_cycle()          -> the dt every accumulator should use.
                                Default (nothing set): the OLD constant
                                ASSUMED_HOURS_PER_CYCLE, read lazily, so
                                offline runs, self-tests and any caller
                                that never calls set_elapsed_hours() get
                                bit-identical numbers to before.
  set_elapsed_hours(x)       -> overrides dt for the following cycle(s);
                                set_elapsed_hours(None) restores the
                                default. Called by scripts/run_continuous_
                                cycle.py with the real elapsed time.
  clamp_elapsed_hours(...)   -> pure helper implementing the documented
                                clamp rule used by the driver script.

NOT converted to continuous time here (stay per-cycle, tagged Assumed in
their own confidence_note): EU008_DAMPING (tower-water relaxation per
cycle) and every lagged_depends_on coupling (recycle loop, storage/
dispensing/fuel-cell pair, EU-008 pair). See docs/continuous_runtime_
design.md, section on the elapsed-time rule.
"""
import datetime

MIN_ELAPSED_HOURS = 0.05   # 3 minutes -- guards against a double-fire / clock skew producing dt ~ 0
MAX_ELAPSED_HOURS = 12.0   # beyond this the run is treated as a long outage, not 12+ h of smooth accumulation
DEFAULT_ELAPSED_HOURS = 1.0

_elapsed_hours = None


def hours_per_cycle():
    """dt in hours for one cycle. See module docstring."""
    if _elapsed_hours is not None:
        return _elapsed_hours
    # Lazy import: hb_wgs_psa_storage_chain imports this module, so a
    # top-level import here would be circular.
    from . import hb_wgs_psa_storage_chain as hbchain
    return hbchain.ASSUMED_HOURS_PER_CYCLE


def set_elapsed_hours(x):
    """Sets (or, with None, clears) the dt returned by hours_per_cycle().
    Rejects non-finite or non-positive values -- clamping policy belongs to
    clamp_elapsed_hours(), this setter only refuses nonsense."""
    global _elapsed_hours
    if x is None:
        _elapsed_hours = None
        return
    x = float(x)
    if not (x > 0.0) or x != x or x == float("inf"):
        raise ValueError(f"set_elapsed_hours: need a finite positive number of hours, got {x!r}")
    _elapsed_hours = x


def _parse_iso(ts):
    if ts is None:
        return None
    if isinstance(ts, datetime.datetime):
        dt = ts
    else:
        try:
            dt = datetime.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt


def compute_elapsed_hours(previous_published_at, now):
    """Pure. Returns a dict describing exactly what was decided and why:
    {elapsed_h_used, raw_elapsed_h, clamped, clamp_reason, previous_published_at, now}.

    Rule (documented in docs/continuous_runtime_design.md):
      * previous timestamp missing/unparsable (empty store) -> 1.0, clamped=False,
        reason states "no usable previous timestamp".
      * raw = (now - previous) in hours.
      * raw < 0.05 (includes zero and negative/clock skew) -> 0.05, clamped.
      * raw > 12.0 -> 12.0, clamped.
      * otherwise used as is.
    """
    now_dt = _parse_iso(now)
    prev_dt = _parse_iso(previous_published_at)
    out = {
        "previous_published_at": None if prev_dt is None else prev_dt.isoformat(),
        "now": None if now_dt is None else now_dt.isoformat(),
        "raw_elapsed_h": None, "elapsed_h_used": DEFAULT_ELAPSED_HOURS,
        "clamped": False, "clamp_reason": None,
    }
    if prev_dt is None or now_dt is None:
        out["clamp_reason"] = "no usable previous timestamp -> default 1.0 h (not a clamp)"
        return out
    raw = (now_dt - prev_dt).total_seconds() / 3600.0
    out["raw_elapsed_h"] = raw
    if raw < MIN_ELAPSED_HOURS:
        out.update(elapsed_h_used=MIN_ELAPSED_HOURS, clamped=True,
                   clamp_reason=f"raw {raw:.4f} h below minimum {MIN_ELAPSED_HOURS} h (zero/negative/clock skew)")
    elif raw > MAX_ELAPSED_HOURS:
        out.update(elapsed_h_used=MAX_ELAPSED_HOURS, clamped=True,
                   clamp_reason=f"raw {raw:.4f} h above maximum {MAX_ELAPSED_HOURS} h (long outage)")
    else:
        out["elapsed_h_used"] = raw
    return out


# ---------------------------------------------------------------------------
# RUNTIME entries published by the continuous driver (audit fixes A4 and C1).
# Registered ONLY by scripts/run_continuous_cycle.py (register_runtime_models),
# NOT by tab1_integration.build_live_snapshot(), so the offline 116-entry
# snapshot is unchanged. They use the existing public engine API
# (register_model + lagged_depends_on) -- no engine or SharedPlantState change.
# ---------------------------------------------------------------------------
from . import plant_status as ps  # noqa: E402  (after the pure helpers above on purpose)

ELAPSED_KEY = ("RUNTIME", "ElapsedHours")
COUNTER_KEY = ("RUNTIME", "CycleCounter")


def _make_elapsed_model(info):
    def runtime_elapsed_hours(get_input):
        raw = info["raw_elapsed_h"]
        return {
            "value": dict(info),
            "status": ps.STATUS_CALCULATED,
            "model": "cycle_clock.runtime_elapsed_hours",
            "inputs": [],
            "validation_basis": ps.VALIDATION_NA,
            "confidence_note": (
                f"dt actually used by the accumulators this cycle: {info['elapsed_h_used']:.4f} h = "
                f"(now {info['now']} - previous published_at {info['previous_published_at']}) / 3600 h"
                + (f", raw {raw:.4f} h" if raw is not None else "")
                + (f"; CLAMPED to [{MIN_ELAPSED_HOURS}, {MAX_ELAPSED_HOURS}] h: {info['clamp_reason']}" if info["clamped"]
                   else (f"; {info['clamp_reason']}" if info["clamp_reason"] else "; not clamped"))
                + ". Lags/damping (EU008_DAMPING, lagged couplings) stay PER-CYCLE (Assumed)."
            ),
        }
    return runtime_elapsed_hours


def runtime_cycle_counter(get_input):
    """Monotonic run counter = previous persisted value + 1 (1 on an empty
    store). Reads its own previous published value through the existing
    lagged self-dependency, the same mechanism FE-001/HB-013/EU-010 use."""
    prev = get_input(COUNTER_KEY)
    n = 1 if prev["status"] == ps.STATUS_MISSING else int(prev["value"]) + 1
    return {
        "value": n, "status": ps.STATUS_CALCULATED, "model": "cycle_clock.runtime_cycle_counter",
        "inputs": [COUNTER_KEY], "validation_basis": ps.VALIDATION_NA,
        "confidence_note": (
            "Runs of the continuous driver since this counter was first persisted (previous + 1). "
            "Replaces SharedPlantState.published_cycle, which restarts at 2 on every rehydration."
        ),
    }


def register_runtime_models(engine, elapsed_info):
    """Registers the two RUNTIME entries on `engine`. `elapsed_info` is the
    dict returned by compute_elapsed_hours()."""
    engine.register_model(ELAPSED_KEY, _make_elapsed_model(elapsed_info), unit="h")
    engine.register_model(COUNTER_KEY, runtime_cycle_counter, unit="count", lagged_depends_on=[COUNTER_KEY])
