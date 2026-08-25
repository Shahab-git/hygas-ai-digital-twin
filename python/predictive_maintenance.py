"""
Predictive maintenance v1 — catalyst activity monitoring via inverse kinetics.

Where this lives, and why: a NEW file, not an addition to kinetics.py.
kinetics.py solves the FORWARD problem (given T, GHSV, and catalyst
activity -> conversion) and is the validated source of truth for that
physics. This module solves the INVERSE problem (given an *observed*
conversion, T, and GHSV -> the catalyst activity that must be causing
it) — a diagnostic layered on top of kinetics.py, not a physics model in
its own right. That matches the existing pattern in this repo: copilot.py,
uncertainty.py, and optimizer.py all import kinetics.py/psa.py rather
than being folded into them, so each file stays one concern.

Core idea: kinetics.py's hts_conversion()/lts_conversion() already expose
a k0_scale parameter (added for uncertainty.py) — a healthy catalyst is
k0_scale=1.0, the calibrated k0_HTS/k0_LTS values. In a real plant,
catalyst activity degrades over time (fouling, poisoning, sintering —
this module doesn't attempt to distinguish which mechanism; that would
need data this project doesn't have). A live sensor reading showing lower
conversion than kinetics.py predicts at k0_scale=1.0, at the SAME T and
GHSV, implies the effective k0 has dropped below the healthy calibrated
value. This back-calculates that implied k0_scale ("activity factor") by
root-finding with scipy.optimize.brentq: conversion is monotonically
increasing in k0_scale (more active catalyst -> faster rate -> more
conversion, up to the equilibrium ceiling), so the root is unique and a
bisection-family method is a well-posed, simple choice — no need for
anything fancier than root-finding on one variable.

Thresholds below are OUR OWN reasonable defaults, explicitly NOT sourced
from any real catalyst degradation data — there isn't any in this project
yet. Replace them the moment real degradation-curve data exists.
"""
from scipy.optimize import brentq

from . import kinetics

HEALTHY_THRESHOLD = 0.95  # activity_factor > this -> "healthy"
WATCH_THRESHOLD = 0.85    # this <= activity_factor <= HEALTHY_THRESHOLD -> "watch"
                          # activity_factor < this -> "flag for maintenance"


def _status(activity_factor):
    if activity_factor > HEALTHY_THRESHOLD:
        return "healthy"
    if activity_factor >= WATCH_THRESHOLD:
        return "watch"
    return "flag for maintenance"


def _back_calculate(forward_fn, observed_X, **forward_kwargs):
    """Shared root-finder: forward_fn is kinetics.hts_conversion or
    lts_conversion, forward_kwargs holds every argument except k0_scale.
    Returns a result dict, or a dict with an "error" key if observed_X
    isn't reachable at this operating point (e.g. above the equilibrium
    ceiling, so no catalyst activity — however high — could produce it)."""
    expected_X = forward_fn(k0_scale=1.0, **forward_kwargs)

    def f(k0_scale):
        return forward_fn(k0_scale=k0_scale, **forward_kwargs) - observed_X

    if observed_X <= 0:
        return {"activity_factor": 0.0, "status": _status(0.0),
                "expected_X": expected_X, "observed_X": observed_X}

    lo, hi = 1e-4, 1.0
    if f(lo) >= 0:
        # even near-zero catalyst activity reaches (or exceeds) the
        # observed conversion -- degenerate, report minimal activity
        activity_factor = lo
    else:
        tries = 0
        while f(hi) < 0 and tries < 20:
            hi *= 2
            tries += 1
        if f(hi) < 0:
            return {"error": (
                f"Observed conversion {observed_X*100:.1f}% isn't reachable at this "
                f"T/GHSV even with an ideal, undegraded catalyst (equilibrium-limited) "
                f"-- can't back-calculate an activity factor for it."
            )}
        activity_factor = brentq(f, lo, hi, xtol=1e-8)

    return {
        "activity_factor": float(activity_factor),
        "status": _status(activity_factor),
        "expected_X": float(expected_X),
        "observed_X": float(observed_X),
    }


def back_calculate_activity_hts(observed_X, T_C, GHSV, y_CO_in=0.28, steam_to_CO=4.0):
    """observed_X: the live-sensor HTS conversion (fraction, not %).
    T_C, GHSV: the operating point the sensor reading was taken at."""
    return _back_calculate(
        kinetics.hts_conversion, observed_X,
        T_K=T_C + 273.15, GHSV=GHSV, y_CO_in=y_CO_in, steam_to_CO=steam_to_CO,
    )


def back_calculate_activity_lts(observed_X, T_C, GHSV, y_CO_in=0.07, steam_to_CO=4.0):
    """observed_X: the live-sensor LTS relative conversion (fraction, not %).
    T_C, GHSV: the operating point; y_CO_in should be the actual CO
    fraction reaching the LTS stage (i.e. after HTS conversion), matching
    how lts_conversion() is called elsewhere in this repo."""
    return _back_calculate(
        kinetics.lts_conversion, observed_X,
        T_K=T_C + 273.15, GHSV=GHSV, y_CO_in=y_CO_in, steam_to_CO=steam_to_CO,
    )


if __name__ == "__main__":
    print("Sanity check: healthy calibrated conversion fed back in ->")
    r = back_calculate_activity_hts(observed_X=0.75, T_C=350, GHSV=2000)
    print(f"  HTS: activity_factor={r['activity_factor']:.4f}  status={r['status']}  "
          f"(expect ~1.0000, healthy)")

    print("\nExample readings (HTS, T=350C, GHSV=2000, expected 75.0%) spanning all 3 zones:")
    for observed_pct in [74.0, 71.0, 65.0]:
        r = back_calculate_activity_hts(observed_X=observed_pct / 100, T_C=350, GHSV=2000)
        print(f"  observed={observed_pct:.1f}%  ->  activity_factor={r['activity_factor']:.3f}  "
              f"status={r['status']}")
