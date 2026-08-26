"""
Performance guarantee pricing v1 — PSA recovery threshold guarantees,
priced from uncertainty.py's real Monte Carlo distribution.

THE ACTUAL PROBLEM: if DOK-ING (or SMITH2) wanted to offer a performance
guarantee — "we guarantee >=X% PSA recovery, or pay a penalty" — the
honest price of that guarantee should depend on the REAL probability of
missing the threshold, not a gut-feel number. This is genuinely analogous
to real-options pricing (a payout that depends on where a stochastic
outcome lands relative to a strike), just simpler: uncertainty.py's own
Monte Carlo already simulates the actual outcome distribution by running
the real kinetics.py/psa.py physics through the six DOK-ING-unconfirmed
assumptions, so pricing here means directly evaluating breach probability
and expected payout against that REAL simulated distribution — no
Black-Scholes-style closed-form formula is needed or used, because we
already have the actual distribution via simulation, not just a mean and
a volatility to plug into one.

HONEST SCOPING, stated here and in the app.py UI: this is an
ILLUSTRATIVE PRICING FRAMEWORK using this project's own model uncertainty
distribution — it is NOT a real actuarial or insurance-grade guarantee.
Real guarantee terms need actual legal and financial structuring (credit
risk, counterparty terms, measurement/verification protocol, force
majeure, etc.), none of which exists here. What IS real: the breach
probability and expected cost below are computed directly from
uncertainty.py's genuine Monte Carlo propagation of the six real
unconfirmed design assumptions through the real kinetics.py/psa.py
physics — not invented numbers.

THE PENALTY RATE is OUR OWN assumed placeholder — same honesty pattern as
circularity.py's ash/carbon-black market prices: not sourced from any
real DOK-ING contract, guarantee, or market data. It exists so the
pricing MECHANISM can be demonstrated on a concrete number; replace it
the moment a real penalty structure exists.

MECHANICS: reuses uncertainty.run_monte_carlo() unchanged — that function
already returns every individual sample (results["psa_recovery"] is a
list of n_runs draws), not just the mean/90% CI that app.py's Uncertainty
Analysis section displays. This module just uses those raw samples
directly to estimate breach probability (fraction of samples below the
guaranteed threshold) and expected cost (the probability-weighted average
penalty across ALL samples, zero for the ones that don't breach — that
average IS the honest expected cost, not a point estimate built from the
mean recovery alone). Because run_monte_carlo() reads uncertainty.py's
live bounds()/is_confirmed() state, every call here automatically
reflects whatever confirmation_loop.py has (or hasn't) confirmed — no
separate copy of that state exists in this module.
"""
import numpy as np

from . import uncertainty

# --- Our own assumed placeholder — NOT sourced from any real guarantee/contract ---
DEFAULT_PENALTY_EUR_PER_POINT = 5000.0  # EUR per 1 percentage-point of recovery shortfall below threshold
DEFAULT_THRESHOLD = 0.735  # illustrative guarantee level, chosen to sit inside the real MC distribution's actual support (~71.7-78.3% under the default +/-15% psa_target_calibration band) so breach probability is a genuine, non-trivial number
DEFAULT_N_RUNS = 500  # kinetics.py's ODE integration makes each MC sample non-trivial (~20ms) — 500 keeps this responsive as a UI button while still resolving breach probabilities to a percent or so


def compute_distribution(n_runs=DEFAULT_N_RUNS, seed=42, **mc_kwargs):
    """The full PSA recovery outcome distribution — uncertainty.py's real
    Monte Carlo machinery, unchanged, just exposed as a numpy array
    instead of only the mean/90% CI app.py's Uncertainty Analysis section
    shows. Reflects the CURRENT confirmed/unconfirmed state of
    uncertainty.ASSUMPTIONS live, since run_monte_carlo() reads bounds()
    internally."""
    results = uncertainty.run_monte_carlo(n_runs=n_runs, seed=seed, **mc_kwargs)
    return np.array(results["psa_recovery"])


def price_guarantee(threshold, penalty_eur_per_point=DEFAULT_PENALTY_EUR_PER_POINT,
                     samples=None, n_runs=DEFAULT_N_RUNS, seed=42, **mc_kwargs):
    """The actual pricing calculation.

    threshold: the guaranteed recovery fraction (e.g. 0.70 for '>=70%').
    penalty_eur_per_point: EUR charged per percentage-point of shortfall
      below threshold, for every sample that breaches — see
      DEFAULT_PENALTY_EUR_PER_POINT for the honesty statement.
    samples: reuse an already-computed distribution (e.g. for a clean
      apples-to-apples comparison across thresholds — see
      sweep_thresholds()) instead of running a fresh Monte Carlo.

    breach_probability: fraction of MC samples landing below threshold —
      the actual empirical probability from the model's real uncertainty
      distribution, not a guessed number.
    expected_cost: the probability-weighted average penalty across ALL
      samples (0 for non-breaching ones) — the honest expected cost of
      offering this guarantee. This is exactly np.mean() of the per-
      sample penalty array, which IS the Monte Carlo estimate of
      E[penalty] = P(breach) * E[penalty | breach] — computed directly,
      not as a separate point estimate built off the mean recovery alone.
    """
    if samples is None:
        samples = compute_distribution(n_runs=n_runs, seed=seed, **mc_kwargs)
    samples = np.asarray(samples)

    breach_mask = samples < threshold
    breach_probability = float(np.mean(breach_mask))

    shortfall_points = np.clip(threshold - samples, 0.0, None) * 100.0  # percentage points; 0 where not breaching
    penalty_per_sample = shortfall_points * penalty_eur_per_point
    expected_cost = float(np.mean(penalty_per_sample))  # probability-weighted average across ALL samples

    has_breach = breach_probability > 0
    mean_shortfall_points_given_breach = float(shortfall_points[breach_mask].mean()) if has_breach else 0.0
    expected_cost_given_breach = float(penalty_per_sample[breach_mask].mean()) if has_breach else 0.0

    return {
        "threshold": threshold, "penalty_eur_per_point": penalty_eur_per_point, "n_samples": len(samples),
        "breach_probability": breach_probability, "expected_cost": expected_cost,
        "mean_shortfall_points_given_breach": mean_shortfall_points_given_breach,
        "expected_cost_given_breach": expected_cost_given_breach,
        "mean_recovery": float(samples.mean()), "p5_recovery": float(np.percentile(samples, 5)),
        "p95_recovery": float(np.percentile(samples, 95)),
        "samples": samples, "breach_mask": breach_mask,
    }


def sweep_thresholds(thresholds, penalty_eur_per_point=DEFAULT_PENALTY_EUR_PER_POINT,
                      n_runs=DEFAULT_N_RUNS, seed=42, **mc_kwargs):
    """Prices the SAME underlying Monte Carlo sample set at multiple
    thresholds — the samples are drawn once and reused, so only the
    threshold changes between rows, making a clean check that a harder
    (higher) threshold monotonically raises breach probability and
    expected cost, not an artifact of comparing across different random
    draws."""
    samples = compute_distribution(n_runs=n_runs, seed=seed, **mc_kwargs)
    return [price_guarantee(t, penalty_eur_per_point, samples=samples) for t in thresholds]


def price_with_confirmation_scenario(assumption_name, confirmed_low, confirmed_high, threshold,
                                      penalty_eur_per_point=DEFAULT_PENALTY_EUR_PER_POINT,
                                      n_runs=DEFAULT_N_RUNS, seed=42, **mc_kwargs):
    """Prices the SAME guarantee before and after temporarily applying a
    hypothetical confirmed range to one assumption, via uncertainty.py's
    real set_confirmed()/clear_confirmed() — the same functions
    confirmation_loop.py calls when DOK-ING actually confirms a value —
    then restores whatever confirmation state existed before this call,
    so using this has no lasting side effect on the live app's
    uncertainty state.

    Does NOT assume confirmation makes the guarantee cheaper: a narrower
    confirmed range that happens to land on the less favorable side of
    the old default midpoint can make breach probability and expected
    cost go UP, not down. This reports whatever the Monte Carlo
    distribution actually produces, in both directions.
    """
    prior_low = uncertainty.ASSUMPTIONS[assumption_name]["confirmed_low"]
    prior_high = uncertainty.ASSUMPTIONS[assumption_name]["confirmed_high"]

    before = price_guarantee(threshold, penalty_eur_per_point, n_runs=n_runs, seed=seed, **mc_kwargs)
    try:
        uncertainty.set_confirmed(assumption_name, confirmed_low, confirmed_high)
        after = price_guarantee(threshold, penalty_eur_per_point, n_runs=n_runs, seed=seed, **mc_kwargs)
    finally:
        if prior_low is not None and prior_high is not None:
            uncertainty.set_confirmed(assumption_name, prior_low, prior_high)
        else:
            uncertainty.clear_confirmed(assumption_name)

    return {"assumption": assumption_name, "confirmed_range": (confirmed_low, confirmed_high),
            "before": before, "after": after}


if __name__ == "__main__":
    print("=== Step 3a: does a harder threshold raise breach probability and expected cost? ===")
    thresholds = [0.72, 0.735, 0.75, 0.765, 0.78]
    results = sweep_thresholds(thresholds)
    prev_p, prev_cost = -1.0, -1.0
    for t, r in zip(thresholds, results):
        print(f"  threshold={t * 100:4.0f}%  breach_prob={r['breach_probability'] * 100:5.1f}%  "
              f"expected_cost=EUR{r['expected_cost']:>8,.0f}")
        assert r["breach_probability"] >= prev_p - 1e-9, "breach probability should not decrease as threshold rises"
        assert r["expected_cost"] >= prev_cost - 1e-9, "expected cost should not decrease as threshold rises"
        prev_p, prev_cost = r["breach_probability"], r["expected_cost"]
    print("  Monotonicity check PASSED.\n")

    print("=== Step 3b: does a narrower confirmed range always make it cheaper? (no — see below) ===")
    threshold_demo = DEFAULT_THRESHOLD
    print(f"  Guarantee: >= {threshold_demo * 100:.0f}% PSA recovery, EUR{DEFAULT_PENALTY_EUR_PER_POINT:,.0f}/point shortfall\n")

    favorable = price_with_confirmation_scenario("psa_target_calibration", 0.90, 1.00, threshold_demo)
    print("  Scenario A — confirmed range [0.90, 1.00] (narrower than default [0.85, 1.15], "
          "centered BELOW the old 1.0 midpoint => less purge loss => favorable):")
    print(f"    before: breach_prob={favorable['before']['breach_probability'] * 100:5.1f}%  "
          f"expected_cost=EUR{favorable['before']['expected_cost']:>8,.0f}")
    print(f"    after:  breach_prob={favorable['after']['breach_probability'] * 100:5.1f}%  "
          f"expected_cost=EUR{favorable['after']['expected_cost']:>8,.0f}")

    unfavorable = price_with_confirmation_scenario("psa_target_calibration", 1.05, 1.15, threshold_demo)
    print("\n  Scenario B — confirmed range [1.05, 1.15] (also narrower than default, but centered "
          "ABOVE the old 1.0 midpoint => more purge loss => UNfavorable):")
    print(f"    before: breach_prob={unfavorable['before']['breach_probability'] * 100:5.1f}%  "
          f"expected_cost=EUR{unfavorable['before']['expected_cost']:>8,.0f}")
    print(f"    after:  breach_prob={unfavorable['after']['breach_probability'] * 100:5.1f}%  "
          f"expected_cost=EUR{unfavorable['after']['expected_cost']:>8,.0f}")
    print("\n  Confirmed uncertainty.ASSUMPTIONS state was restored after each scenario "
          f"(is_confirmed('psa_target_calibration') = {uncertainty.is_confirmed('psa_target_calibration')}).")
