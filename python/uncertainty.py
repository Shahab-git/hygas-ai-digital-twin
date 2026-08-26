"""
Monte Carlo uncertainty propagation for the six design-basis assumptions
DOK-ING has not yet confirmed (see CLAUDE.md, "Six design-basis parameters
remain unconfirmed"):

  1. Steam-to-feed ratio       (point value 0.4)
  2. Air equivalence ratio     (point value 0.25)
  3. Feed sulfur / H2S         (point value 200 ppm)
  4. Feed chlorine / HCl       (point value 150 ppm)
  5. WGS conversion target     (point value ~85% overall)
  6. PSA recovery target       (point value ~75%)

This reflects uncertainty in UNCONFIRMED DESIGN ASSUMPTIONS, not
measurement noise or numerical/model error — kinetics.py and psa.py's
own math is deterministic and already validated exactly against their
design targets (see their own __main__ self-checks). What's uncertain
here is whether the assumed *inputs* to that math (steam ratio, air
ratio, feed contaminant levels, and the calibration behind the ~85%/~75%
targets themselves) are actually correct, since DOK-ING hasn't confirmed
them yet.

Uncertainty range: point value +/- 15%. This is OUR OWN assumed default
for a genuinely unconfirmed design parameter — it is NOT sourced from any
DOK-ING document, datasheet, or literature value. Replace it the moment
DOK-ING confirms tighter (or looser) real bounds.

Distribution: UNIFORM over [point*(1-frac), point*(1+frac)], not normal.
Reasoning: a normal distribution implies we have grounds to believe values
cluster near the point estimate more than near the edges of the band —
we don't have that information; +/-15% is an assumed bound, not a
calibrated standard deviation. Uniform is the more honest "we only know
the bound, not the shape" choice absent better information.

Mapping six assumptions onto the existing kinetics.py/psa.py functions
(no duplicate physics — this module only calls the existing public
functions with sampled arguments):

  - Steam-to-feed ratio  -> kinetics.hts_conversion/lts_conversion's
    `steam_to_CO` argument, scaled proportionally to the sampled ratio's
    deviation from its 0.4 point value. Simplification, stated plainly:
    no gasifier module exists yet in this repo to compute the exact
    WGS-inlet steam:CO ratio from a given steam-to-feed mass ratio, so
    the existing steam_to_CO input is scaled by the same fractional
    deviation as a stand-in until that module exists.

  - Air equivalence ratio -> kinetics.hts_conversion's `y_CO_in` argument,
    scaled INVERSELY to the sampled ratio (more air -> more combustion/
    dilution -> lower CO fraction reaching the WGS stage). Same
    no-gasifier-yet simplification as above.

  - WGS conversion target -> `k0_scale` on both hts_conversion and
    lts_conversion (shared sample per run, since CLAUDE.md lists this as
    one assumption, not two). Encodes: the ~85% design target isn't
    independently confirmed by DOK-ING either, and the catalyst kinetic
    parameters (Ea, k0) that were calibrated to reproduce it exactly
    inherit that same uncertainty.

  - PSA recovery target -> `k1_scale` on psa.psa_recovery, same
    reasoning as above (K1 is documented in psa.py as "calibrated to the
    established 75% design-point recovery").

  - Feed sulfur (H2S) and feed chlorine (HCl) -> sampled and reported
    (so all six assumptions' ranges are defined and visible), but NOT
    wired into kinetics.py/psa.py: neither module models catalyst
    poisoning or corrosion, so there is no real quantitative pathway from
    ppm-level contaminants to conversion/recovery in this repo yet.
    Inventing a numeric sensitivity coefficient for that pathway would be
    fabricating physics that isn't actually modeled here — flagged
    honestly instead, both here and in the app.py UI.
"""
import random

import numpy as np

from . import kinetics, psa

UNCERTAINTY_FRACTION = 0.15  # our own assumed default, see module docstring

ASSUMPTIONS = {
    "steam_to_feed_ratio": {
        "point": 0.4, "fraction": UNCERTAINTY_FRACTION,
        "label": "Steam-to-feed ratio", "wired_in": True,
        "confirmed_low": None, "confirmed_high": None,
    },
    "air_equivalence_ratio": {
        "point": 0.25, "fraction": UNCERTAINTY_FRACTION,
        "label": "Air equivalence ratio", "wired_in": True,
        "confirmed_low": None, "confirmed_high": None,
    },
    "feed_sulfur_ppm": {
        "point": 200, "fraction": UNCERTAINTY_FRACTION,
        "label": "Feed sulfur / H2S (ppm)", "wired_in": False,
        "confirmed_low": None, "confirmed_high": None,
    },
    "feed_chlorine_ppm": {
        "point": 150, "fraction": UNCERTAINTY_FRACTION,
        "label": "Feed chlorine / HCl (ppm)", "wired_in": False,
        "confirmed_low": None, "confirmed_high": None,
    },
    "wgs_target_calibration": {
        "point": 1.0, "fraction": UNCERTAINTY_FRACTION,
        "label": "WGS conversion target calibration (~85%)", "wired_in": True,
        "confirmed_low": None, "confirmed_high": None,
    },
    "psa_target_calibration": {
        "point": 1.0, "fraction": UNCERTAINTY_FRACTION,
        "label": "PSA recovery target calibration (~75%)", "wired_in": True,
        "confirmed_low": None, "confirmed_high": None,
    },
}


def bounds(name):
    """The (lo, hi) sampling range actually used for one assumption: the
    CONFIRMED range if confirmation_loop.py has recorded one (see
    set_confirmed below), otherwise the default point +/-fraction band.
    Public, since compliance.py reads this too — a confirmed assumption
    should show as such in the compliance checklist automatically, not
    just in the Monte Carlo."""
    cfg = ASSUMPTIONS[name]
    if cfg["confirmed_low"] is not None and cfg["confirmed_high"] is not None:
        return cfg["confirmed_low"], cfg["confirmed_high"]
    return cfg["point"] * (1 - cfg["fraction"]), cfg["point"] * (1 + cfg["fraction"])


def is_confirmed(name):
    cfg = ASSUMPTIONS[name]
    return cfg["confirmed_low"] is not None and cfg["confirmed_high"] is not None


def set_confirmed(name, low, high):
    """Marks an assumption as confirmed with a real range. From this call
    on, run_monte_carlo() samples [low, high] instead of the default
    +/-15% band for this one assumption — called by
    confirmation_loop.py.record_confirmation(), not meant to be called
    directly elsewhere."""
    if name not in ASSUMPTIONS:
        raise KeyError(name)
    if low >= high:
        raise ValueError("low must be < high")
    ASSUMPTIONS[name]["confirmed_low"] = low
    ASSUMPTIONS[name]["confirmed_high"] = high


def clear_confirmed(name):
    ASSUMPTIONS[name]["confirmed_low"] = None
    ASSUMPTIONS[name]["confirmed_high"] = None


def _sample_uniform(point, fraction, rng):
    return rng.uniform(point * (1 - fraction), point * (1 + fraction))


def run_monte_carlo(n_runs=1000, seed=42,
                     hts_T_C=350, hts_GHSV=2000,
                     lts_T_C=220, lts_GHSV=2000,
                     psa_p_high=8.0, psa_p_low=1.0, psa_y_co2=0.35,
                     fractions=None):
    """Runs n_runs Monte Carlo samples of the six unconfirmed assumptions
    through the existing kinetics.py/psa.py functions.

    Operating conditions (temperatures, GHSV, PSA pressures/composition)
    are held fixed at the given values (default: the dashboard's default
    slider positions) — only the six DOK-ING-unconfirmed assumptions are
    varied. That isolates the effect of assumption uncertainty from
    operator-controlled setpoint choices.

    fractions: optional dict overriding each assumption's `fraction`
    (keyed the same as ASSUMPTIONS) — used to sanity-check that a wider
    input band produces a wider output interval.

    Returns a dict of lists: hts, lts, overall, psa_recovery.
    """
    fractions = fractions or {}
    rng = random.Random(seed)

    results = {"hts": [], "lts": [], "overall": [], "psa_recovery": []}

    for _ in range(n_runs):
        sampled = {}
        for name, cfg in ASSUMPTIONS.items():
            if name in fractions:
                # explicit override (e.g. the widen/narrow sanity check) —
                # always relative to the point value, ignoring confirmed status.
                sampled[name] = _sample_uniform(cfg["point"], fractions[name], rng)
            else:
                lo, hi = bounds(name)  # confirmed range if set, else default point +/-fraction
                sampled[name] = rng.uniform(lo, hi)

        steam_to_CO = 4.0 * (sampled["steam_to_feed_ratio"] / ASSUMPTIONS["steam_to_feed_ratio"]["point"])
        y_CO_in = 0.28 * (ASSUMPTIONS["air_equivalence_ratio"]["point"] / sampled["air_equivalence_ratio"])
        k0_scale = sampled["wgs_target_calibration"]
        k1_scale = sampled["psa_target_calibration"]

        X_hts = kinetics.hts_conversion(
            T_K=hts_T_C + 273.15, GHSV=hts_GHSV, y_CO_in=y_CO_in,
            steam_to_CO=steam_to_CO, k0_scale=k0_scale,
        )
        y_co_after_hts = y_CO_in * (1 - X_hts)
        X_lts = kinetics.lts_conversion(
            T_K=lts_T_C + 273.15, GHSV=lts_GHSV, y_CO_in=y_co_after_hts,
            steam_to_CO=steam_to_CO, k0_scale=k0_scale,
        )
        overall = 1 - (1 - X_hts) * (1 - X_lts)

        recovery = psa.psa_recovery(
            y_CO2=psa_y_co2, P_high_bar_a=psa_p_high, P_low_bar_a=psa_p_low, k1_scale=k1_scale,
        )

        results["hts"].append(X_hts)
        results["lts"].append(X_lts)
        results["overall"].append(overall)
        results["psa_recovery"].append(recovery)

    return results


def summarize(samples):
    """mean and 90% CI (5th-95th percentile) for one output distribution."""
    arr = np.array(samples)
    return {
        "mean": float(np.mean(arr)),
        "p5": float(np.percentile(arr, 5)),
        "p95": float(np.percentile(arr, 95)),
    }


if __name__ == "__main__":
    results = run_monte_carlo(n_runs=1000)
    for key, target in [("hts", 0.75), ("lts", 0.40), ("overall", 0.85), ("psa_recovery", 0.75)]:
        s = summarize(results[key])
        print(f"{key}: mean={s['mean']*100:.1f}%  90% CI=[{s['p5']*100:.1f}%, {s['p95']*100:.1f}%]  "
              f"(point-value target: {target*100:.1f}%)")
