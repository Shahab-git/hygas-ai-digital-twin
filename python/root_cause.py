"""
Root-cause diagnosis agent v1 — the natural extension of
predictive_maintenance.py: that module says WHETHER something looks
degraded (activity factor + healthy/watch/flag status); this reasons
about WHY, using only what the model already knows.

SCOPE, stated explicitly like copilot.py's v1: this is rule-based
reasoning over numbers that kinetics.py, uncertainty.py, and
predictive_maintenance.py already compute — comparing a back-calculated
activity factor against a corner-case band and reading off whichever
explanation the comparison favors. It is NOT a new inference engine, not
a statistical or Bayesian model, and does not claim to know the TRUE
cause of any given reading — only which of the available explanations
the numbers make more or less plausible.

Three candidate explanations for a watch/flag reading:

  1. Genuine catalyst degradation — the activity factor taken at face
     value (predictive_maintenance.py's own interpretation).

  2. Sensor/reading inconsistency — checked using kinetics.py's own
     bounds via predictive_maintenance.py's root-finder: if NO catalyst
     activity, however high, could reproduce the observed conversion at
     the stated T/GHSV (beyond the equilibrium ceiling), that's direct
     evidence the READING itself is the problem, not the catalyst.

  3. Unconfirmed design-basis assumptions — whether steam-to-feed ratio
     (and, for HTS, air equivalence ratio) uncertainty ALONE —
     uncertainty.py's own ±15% ranges, propagated through kinetics.py
     the same way uncertainty.py itself propagates them — could produce
     an apparent activity factor this low even with a PERFECTLY HEALTHY
     catalyst (true k0_scale = 1.0). This is a real "aliasing" effect:
     predictive_maintenance.py's back-calculation assumes any conversion
     shortfall is caused by k0 alone, but a shortfall could equally come
     from steam ratio or air ratio being different from their assumed
     point values — which back-calculation would misread as a lower
     activity factor even though the catalyst itself is fine.

Scoping note on which assumptions are checked per stage: this mirrors
uncertainty.py's OWN wiring exactly, not a new mapping invented here —
steam_to_feed_ratio affects both HTS and LTS (steam_to_CO is shared),
air_equivalence_ratio affects only HTS's y_CO_in (uncertainty.py never
wires it into LTS directly — LTS's y_CO_in there is *derived* from HTS's
own uncertain output, not independently varied). So the HTS band uses
both assumptions; the LTS band uses steam_to_feed_ratio only, holding
y_CO_in fixed at whatever value is actually feeding that stage.
"""
from . import kinetics, predictive_maintenance, uncertainty

DEGRADATION = "Genuine catalyst degradation"
SENSOR_ISSUE = "Sensor/reading inconsistency"
ASSUMPTION_UNCERTAINTY = "Unconfirmed design-basis assumptions"


def _steam_to_CO_bounds():
    cfg = uncertainty.ASSUMPTIONS["steam_to_feed_ratio"]
    lo = 4.0 * ((cfg["point"] * (1 - cfg["fraction"])) / cfg["point"])
    hi = 4.0 * ((cfg["point"] * (1 + cfg["fraction"])) / cfg["point"])
    return lo, hi


def _y_co_in_bounds(nominal_y_co_in):
    cfg = uncertainty.ASSUMPTIONS["air_equivalence_ratio"]
    air_lo = cfg["point"] * (1 - cfg["fraction"])
    air_hi = cfg["point"] * (1 + cfg["fraction"])
    # y_CO_in scales INVERSELY with air ratio (more air -> more dilution),
    # matching uncertainty.py's own mapping exactly.
    y_at_air_lo = nominal_y_co_in * (cfg["point"] / air_lo)
    y_at_air_hi = nominal_y_co_in * (cfg["point"] / air_hi)
    return min(y_at_air_lo, y_at_air_hi), max(y_at_air_lo, y_at_air_hi)


def _assumption_only_band_hts(T_C, GHSV, nominal_y_co_in=0.28):
    steam_lo, steam_hi = _steam_to_CO_bounds()
    y_lo, y_hi = _y_co_in_bounds(nominal_y_co_in)

    # Both steam_to_CO and y_CO_in push conversion the SAME direction
    # (higher -> more conversion), so the corners give the true min/max —
    # no need for a full grid.
    X_worst = kinetics.hts_conversion(T_K=T_C + 273.15, GHSV=GHSV, y_CO_in=y_lo, steam_to_CO=steam_lo)
    X_best = kinetics.hts_conversion(T_K=T_C + 273.15, GHSV=GHSV, y_CO_in=y_hi, steam_to_CO=steam_hi)

    a_worst = predictive_maintenance.back_calculate_activity_hts(X_worst, T_C, GHSV)
    a_best = predictive_maintenance.back_calculate_activity_hts(X_best, T_C, GHSV)

    return {
        "activity_lo": a_worst["activity_factor"],
        "activity_hi": a_best["activity_factor"],
        "assumptions_used": ["steam-to-feed ratio", "air equivalence ratio"],
    }


def _assumption_only_band_lts(T_C, GHSV, y_CO_in):
    steam_lo, steam_hi = _steam_to_CO_bounds()

    X_worst = kinetics.lts_conversion(T_K=T_C + 273.15, GHSV=GHSV, y_CO_in=y_CO_in, steam_to_CO=steam_lo)
    X_best = kinetics.lts_conversion(T_K=T_C + 273.15, GHSV=GHSV, y_CO_in=y_CO_in, steam_to_CO=steam_hi)

    a_worst = predictive_maintenance.back_calculate_activity_lts(X_worst, T_C, GHSV, y_CO_in=y_CO_in)
    a_best = predictive_maintenance.back_calculate_activity_lts(X_best, T_C, GHSV, y_CO_in=y_CO_in)

    return {
        "activity_lo": a_worst["activity_factor"],
        "activity_hi": a_best["activity_factor"],
        "assumptions_used": ["steam-to-feed ratio"],
    }


# Activity factors outside this range would require essentially no active
# catalyst at all (near 0) or catalyst several times more active than
# calibrated healthy (implausible for a real fixed catalyst bed) — a soft
# extra sensor-consistency signal, distinct from kinetics.py's hard
# equilibrium-ceiling check. Our own reasonable default, not derived from
# any real sensor spec.
_PLAUSIBLE_ACTIVITY_RANGE = (0.05, 3.0)


def diagnose(stage, observed_X, T_C, GHSV, y_CO_in=None):
    """stage: "HTS" or "LTS". observed_X: the live-sensor reading
    (fraction, not %). T_C, GHSV: the operating point. y_CO_in: required
    for LTS (the feed composition actually reaching that stage) — unused
    for HTS, which uses kinetics.py's own default (0.28).

    Returns a dict: stage, observed_X, activity_factor (or None if the
    reading isn't physically achievable at all), assumption_band, and a
    ranked list of explanations, each with a label and full reasoning
    text — not just a verdict.
    """
    if stage == "HTS":
        pm_result = predictive_maintenance.back_calculate_activity_hts(observed_X, T_C, GHSV)
        band = _assumption_only_band_hts(T_C, GHSV)
    elif stage == "LTS":
        if y_CO_in is None:
            raise ValueError("y_CO_in is required to diagnose the LTS stage")
        pm_result = predictive_maintenance.back_calculate_activity_lts(observed_X, T_C, GHSV, y_CO_in=y_CO_in)
        band = _assumption_only_band_lts(T_C, GHSV, y_CO_in)
    else:
        raise ValueError(f"stage must be 'HTS' or 'LTS', got {stage!r}")

    band_lo = min(band["activity_lo"], band["activity_hi"])
    band_hi = max(band["activity_lo"], band["activity_hi"])
    assumptions_str = " and ".join(band["assumptions_used"])

    # Check 2 first: is the reading physically achievable at all, using
    # kinetics.py's own equilibrium/kinetic bounds (via
    # predictive_maintenance.py's root-finder)?
    if "error" in pm_result:
        return {
            "stage": stage, "observed_X": observed_X, "activity_factor": None,
            "assumption_band": {"lo": band_lo, "hi": band_hi, "assumptions_used": band["assumptions_used"]},
            "explanations": [{
                "label": SENSOR_ISSUE, "rank": 1, "plausible": True,
                "reasoning": (
                    f"{pm_result['error']} No catalyst activity level, however high, could produce this "
                    f"reading at T={T_C:.0f}°C, GHSV={GHSV:.0f} — this points directly at the reading "
                    f"itself (sensor fault, wrong operating point recorded, unit/decimal error), not the "
                    f"catalyst. Genuine degradation and design-assumption uncertainty are both ruled out: "
                    f"neither can push conversion ABOVE what kinetics.py's own equilibrium ceiling allows."
                ),
            }],
        }

    activity_factor = pm_result["activity_factor"]
    within_band = band_lo <= activity_factor <= band_hi
    extreme_activity = not (_PLAUSIBLE_ACTIVITY_RANGE[0] <= activity_factor <= _PLAUSIBLE_ACTIVITY_RANGE[1])

    explanations = []

    if within_band:
        explanations.append({
            "label": ASSUMPTION_UNCERTAINTY, "rank": 1, "plausible": True,
            "reasoning": (
                f"Activity factor {activity_factor:.3f} falls WITHIN [{band_lo:.3f}, {band_hi:.3f}] — the "
                f"range that {assumptions_str} uncertainty ALONE (uncertainty.py's own ±15% bands, "
                f"propagated through kinetics.py exactly as uncertainty.py itself does it) could produce "
                f"at these operating conditions, even with a perfectly healthy catalyst (true activity "
                f"factor exactly 1.0). This reading does not require invoking real catalyst degradation "
                f"to explain — it could simply mean the assumed steam/air ratios are off from their "
                f"point values, which DOK-ING hasn't confirmed either way yet."
            ),
        })
        explanations.append({
            "label": DEGRADATION, "rank": 2, "plausible": True,
            "reasoning": (
                f"Still possible — being inside the assumption-only band doesn't rule out real "
                f"degradation, it just means this single reading can't distinguish it from unconfirmed "
                f"design-assumption uncertainty. A trend across multiple readings (activity factor "
                f"falling over time, not just one low snapshot) would be much stronger evidence of "
                f"actual catalyst wear than this one number."
            ),
        })
    else:
        gap = (band_lo - activity_factor) if activity_factor < band_lo else (activity_factor - band_hi)
        direction = "below" if activity_factor < band_lo else "above"
        explanations.append({
            "label": DEGRADATION, "rank": 1, "plausible": True,
            "reasoning": (
                f"Activity factor {activity_factor:.3f} is {direction} [{band_lo:.3f}, {band_hi:.3f}] — "
                f"the range that {assumptions_str} uncertainty alone could produce at these operating "
                f"conditions, even at the most extreme ends of their assumed ±15% bands with a perfectly "
                f"healthy catalyst. That leaves a gap of {gap:.3f} that design-assumption uncertainty "
                f"cannot plausibly account for on its own — genuine catalyst degradation is the more "
                f"likely explanation for this reading."
            ),
        })
        explanations.append({
            "label": ASSUMPTION_UNCERTAINTY, "rank": 2, "plausible": False,
            "reasoning": (
                f"Could still be a contributing factor alongside real degradation, but cannot account "
                f"for the full {gap:.3f} gap on its own — the numbers don't support this as the sole "
                f"explanation here."
            ),
        })

    sensor_reasoning = (
        f"The reading was physically achievable at T={T_C:.0f}°C, GHSV={GHSV:.0f} — "
        f"predictive_maintenance.py successfully back-calculated a finite activity factor rather than "
        f"failing to bracket a root, so kinetics.py's equilibrium ceiling doesn't rule this out."
    )
    if extreme_activity:
        sensor_reasoning += (
            f" That said, {activity_factor:.3f} is outside what we'd consider a plausible activity "
            f"factor range for a real catalyst bed ({_PLAUSIBLE_ACTIVITY_RANGE[0]:.2f}–"
            f"{_PLAUSIBLE_ACTIVITY_RANGE[1]:.2f}, our own reasonable default, not a sensor spec) — worth "
            f"double-checking the reading itself before acting on either explanation above."
        )
    explanations.append({
        "label": SENSOR_ISSUE, "rank": 3 if not extreme_activity else 0,
        "plausible": extreme_activity, "reasoning": sensor_reasoning,
    })

    # rank 0 (an implausibly extreme activity factor) sorts first when it
    # occurs; otherwise plain rank order (1, 2, 3) applies.
    ordered = sorted(explanations, key=lambda e: (e["rank"] != 0, e["rank"]))

    return {
        "stage": stage, "observed_X": observed_X, "activity_factor": activity_factor,
        "assumption_band": {"lo": band_lo, "hi": band_hi, "assumptions_used": band["assumptions_used"]},
        "explanations": ordered,
    }


if __name__ == "__main__":
    print("Case A: small drop, likely explainable by assumption uncertainty alone")
    result_a = diagnose("HTS", observed_X=0.72, T_C=350, GHSV=2000)
    print(f"  observed=72.0%  activity_factor={result_a['activity_factor']:.3f}  "
          f"band=[{result_a['assumption_band']['lo']:.3f}, {result_a['assumption_band']['hi']:.3f}]")
    for e in result_a["explanations"]:
        print(f"  [{e['label']}] {e['reasoning']}")

    print("\nCase B: large drop, clearly beyond assumption uncertainty")
    result_b = diagnose("HTS", observed_X=0.45, T_C=350, GHSV=2000)
    print(f"  observed=45.0%  activity_factor={result_b['activity_factor']:.3f}  "
          f"band=[{result_b['assumption_band']['lo']:.3f}, {result_b['assumption_band']['hi']:.3f}]")
    for e in result_b["explanations"]:
        print(f"  [{e['label']}] {e['reasoning']}")
