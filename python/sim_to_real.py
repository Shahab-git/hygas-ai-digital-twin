"""
Sim-to-real transfer v1 — the HTS PINN meets synthetic "real-world" imperfection.

HONEST SCOPING, stated here and in the app.py UI exactly like
multi_agent_negotiation.py's "hypothetical, not real facilities"
disclaimer: this repo has no real plant or real sensors to transfer to.
"Real world" in this module means SYNTHETIC — kinetics.py's own true
conversion values, deliberately corrupted with two illustrative,
explicitly-labeled imperfections that a real deployment would face:

  (a) Gaussian noise on the conversion measurement itself (a gas
      analyser / GC reading is never exact) — magnitude is an assumed
      default, not a measured instrument spec, and is exposed as a
      slider in app.py so it's clearly adjustable, not a fixed truth.
  (b) A systematic temperature-sensor calibration offset — a
      thermocouple reading consistently a few degrees off true process
      temperature is a common, realistic failure mode, but the specific
      degrees-off value here is an assumed illustrative default, not a
      documented sensor spec from this project.

Nothing here claims to validate against DOK-ING's actual plant. It
demonstrates the MECHANISM of sim-to-real domain-gap evaluation and
adaptation using this repo's own already-validated simulation physics
(kinetics.py) as the "simulation" side, and synthetic corruption as a
stand-in for "reality" — a first version of the idea, not a claim that
this project has real-world validation data.

THE MECHANICS:
  1. Take the simulation-trained PINN from pinn_kinetics.py (its own
     train() routine, reused unchanged — not duplicated here).
  2. Generate a noisy/shifted "real-world" test set: for each sampled
     (T_true, GHSV), kinetics.py's true conversion X_true, a sensor
     temperature reading T_sensor = T_true + calibration offset, and an
     observed conversion reading X_observed = X_true + Gaussian noise.
  3. Evaluate the PURE simulation-trained PINN by feeding it what a real
     deployment would actually have — the sensor's (biased) T reading —
     and comparing its prediction to what a real deployment would
     actually have to validate against — the sensor's (noisy) conversion
     reading. Both imperfections flow into this one number: the domain
     gap. (There is no oracle "true" value available in a genuine
     deployment; using X_observed as the comparison target, not X_true,
     is deliberate and is what makes this a fair proxy for a real
     evaluation.)
  4. Adapt: fine-tune the simulation-trained PINN on a SMALL number of
     these same noisy/shifted points (via pinn_kinetics.fine_tune —
     the exact same physics-residual + boundary-condition loss terms,
     just warm-started and given noisy real-world labeled data instead
     of clean simulation output). Re-evaluate on the same held-out set.

HONEST LIMITATION: this only tests robustness to the two imperfections
modeled here (measurement noise + a temperature calibration bias). Real
sensor failure modes are far richer (drift over time, non-Gaussian
outliers, cross-sensor correlation, GHSV/flow-meter error, etc.) — this
is a first, deliberately narrow version of the idea, not a general
robustness certification.
"""
import numpy as np

from . import kinetics
from . import pinn_kinetics as pk

# --- Illustrative default imperfection magnitudes — assumed, not measured ---
DEFAULT_NOISE_STD = 0.02          # ~2 percentage points of conversion: a plausible online gas-analyser repeatability
DEFAULT_CALIB_OFFSET_C = 4.0      # a thermocouple reading ~4C off true process temperature — a common, not extreme, drift


def generate_real_world_set(n_points, noise_std, calib_offset_C, seed=None):
    """Synthetic stand-in for 'real-world' data: kinetics.py's true values,
    corrupted with sensor noise on the conversion reading and a systematic
    offset on the temperature reading. seed=None draws fresh randomness
    each call (the default for anything meant to run live in the UI)."""
    rng = np.random.default_rng(seed)
    T_true_C = rng.uniform(pk.T_MIN_C, pk.T_MAX_C, n_points)
    GHSV = rng.uniform(pk.GHSV_MIN, pk.GHSV_MAX, n_points)
    X_true = np.array([kinetics.hts_conversion(T_K=t + 273.15, GHSV=g) for t, g in zip(T_true_C, GHSV)])

    T_sensor_C = T_true_C + calib_offset_C
    X_observed = np.clip(X_true + rng.normal(0.0, noise_std, n_points), 0.0, 1.0)

    return {
        "T_true_C": T_true_C, "T_sensor_C": T_sensor_C, "GHSV": GHSV,
        "X_true": X_true, "X_observed": X_observed,
    }


def evaluate_domain_gap(flat_weights, real_world_set):
    """Feeds the model what a real deployment would actually have (the
    sensor's biased T reading) and compares its prediction to what a real
    deployment would actually have to check against (the sensor's noisy
    conversion reading) — not the unavailable oracle X_true. This is why
    both the noise slider and the calibration-offset slider move this
    number: noise adds directly to the comparison target's variance, and
    the offset shifts the model's input away from the physical regime it
    was actually trained to predict at."""
    preds = pk.predict(flat_weights, real_world_set["T_sensor_C"], real_world_set["GHSV"])
    errors = np.abs(preds - real_world_set["X_observed"])
    return {"predictions": preds, "errors": errors, "mean_error": float(errors.mean()), "max_error": float(errors.max())}


def adapt(flat_weights, n_adapt=8, noise_std=DEFAULT_NOISE_STD, calib_offset_C=DEFAULT_CALIB_OFFSET_C,
          seed=None, maxiter=300):
    """The actual transfer step: fine-tunes the simulation-trained PINN on
    a small number of noisy/shifted 'real-world' points, using
    pinn_kinetics.fine_tune — the identical physics-residual and boundary-
    condition loss terms already validated in pinn_kinetics.py, just
    warm-started from the simulation weights and given the sensor's
    (biased T, noisy X) readings as the labeled-data term instead of clean
    simulation output."""
    adapt_set = generate_real_world_set(n_adapt, noise_std, calib_offset_C, seed=seed)
    T_data_K = adapt_set["T_sensor_C"] + 273.15  # fine-tune on what the sensor actually reports, not the true T
    tau_data = 1.0 / adapt_set["GHSV"]
    X_data = adapt_set["X_observed"]

    fine_tune_seed = None if seed is None else seed + 1
    flat_adapted, final_loss = pk.fine_tune(flat_weights, T_data_K, tau_data, X_data, seed=fine_tune_seed, maxiter=maxiter)
    return flat_adapted, final_loss, adapt_set


def run_transfer_experiment(flat_sim=None, noise_std=DEFAULT_NOISE_STD, calib_offset_C=DEFAULT_CALIB_OFFSET_C,
                             n_adapt=8, n_eval=40, train_seed=7, eval_seed=None, adapt_seed=None, maxiter=300):
    """Full pipeline: (1) obtain the simulation-trained PINN (trained fresh
    if flat_sim isn't supplied — pass an already-trained one from app.py to
    avoid re-training on every UI interaction, since re-training with a
    fixed train_seed is deterministic and reusing it doesn't make anything
    stale), (2) evaluate its domain gap on a FRESH noisy/shifted real-world
    set with zero adaptation, (3) fine-tune it on a few noisy points and
    re-evaluate on the SAME held-out eval set. eval_seed/adapt_seed default
    to None, drawing genuinely fresh randomness each call — no fixed demo
    numbers, no caching of the noisy data itself."""
    if flat_sim is None:
        flat_sim, _, _ = pk.train(seed=train_seed)

    real_world_eval = generate_real_world_set(n_eval, noise_std, calib_offset_C, seed=eval_seed)
    pre = evaluate_domain_gap(flat_sim, real_world_eval)

    flat_adapted, adapt_final_loss, adapt_set = adapt(
        flat_sim, n_adapt=n_adapt, noise_std=noise_std, calib_offset_C=calib_offset_C,
        seed=adapt_seed, maxiter=maxiter,
    )
    post = evaluate_domain_gap(flat_adapted, real_world_eval)

    gap_closed_fraction = 1.0 - (post["mean_error"] / pre["mean_error"]) if pre["mean_error"] > 0 else float("nan")

    return {
        "noise_std": noise_std, "calib_offset_C": calib_offset_C,
        "flat_sim": flat_sim, "flat_adapted": flat_adapted,
        "real_world_eval": real_world_eval, "adapt_set": adapt_set,
        "pre": pre, "post": post, "gap_closed_fraction": gap_closed_fraction,
    }


if __name__ == "__main__":
    print("Sanity check (step 5): does pre-adaptation error genuinely respond")
    print("to the noise/offset sliders, or is it a fixed number?\n")
    flat_sim, _, _ = pk.train(seed=7)
    for noise_std, offset in [(0.0, 0.0), (0.02, 0.0), (0.0, 4.0), (0.02, 4.0), (0.05, 8.0)]:
        result = run_transfer_experiment(flat_sim=flat_sim, noise_std=noise_std, calib_offset_C=offset,
                                          eval_seed=42, adapt_seed=99)
        print(f"  noise_std={noise_std:.3f}  offset={offset:5.1f}C  ->  "
              f"pre={result['pre']['mean_error']:.4f}  post={result['post']['mean_error']:.4f}  "
              f"gap closed={result['gap_closed_fraction'] * 100:5.1f}%")

    print("\nFreshness check: two runs with IDENTICAL params but no fixed eval/adapt")
    print("seed should draw different noisy data and get different numbers:")
    r1 = run_transfer_experiment(flat_sim=flat_sim, noise_std=0.02, calib_offset_C=4.0)
    r2 = run_transfer_experiment(flat_sim=flat_sim, noise_std=0.02, calib_offset_C=4.0)
    print(f"  run 1: pre={r1['pre']['mean_error']:.4f}  post={r1['post']['mean_error']:.4f}")
    print(f"  run 2: pre={r2['pre']['mean_error']:.4f}  post={r2['post']['mean_error']:.4f}")
    print(f"  different: {r1['pre']['mean_error'] != r2['pre']['mean_error']}")
