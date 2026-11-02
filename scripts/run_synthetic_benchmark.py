"""
Synthetic benchmark for ONE method: predictive_maintenance's inverse-kinetics catalyst activity (task A10). Offline, seeded, read-only.

What it does: take the twin's own HTS conversion (kinetics.hts_conversion) at one operating point with a KNOWN activity factor trajectory (the pre-exponential factor scaled by `k0_scale`),
add Gaussian noise to the conversion at stated levels, run python/predictive_maintenance.back_calculate_activity_hts on the noisy reading, and report how far the recovered activity is from the
known one: mean absolute error (MAE) and bias (mean of recovered - true), per noise level and per seed.

THIS MEASURES THE CODE, NOT ANY PLANT. The "plant" here is the same forward model the method inverts, so zero noise must recover the truth to numerical tolerance (it does: that is the code check),
and what the noise levels show is how the inverse amplifies a reading error. The noise levels are illustrative test inputs chosen for the benchmark, NOT instrument specifications; no
plant data, no DOK-ING data and no threshold of the readiness gate is involved.

    python scripts/run_synthetic_benchmark.py          (from the repo root, about 1 minute)

Writes outputs/benchmark/synthetic_benchmark.md and .csv (outputs/ is git-ignored). The other modules have no benchmark yet (NO_BENCHMARK below); none was added.
"""
import csv
import os
import sys

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from python import kinetics                          # noqa: E402
from python import predictive_maintenance as pm      # noqa: E402

OUT_DIR = os.path.join(ROOT, "outputs", "benchmark")
# the benchmark's stated setup (illustrative test inputs, not instrument specifications)
T_C, GHSV, Y_CO_IN, STEAM_TO_CO = 350.0, 2000.0, 0.28, 4.0          # the HTS design point of kinetics.py
TRUE_ACTIVITY = tuple(np.linspace(1.0, 0.6, 21))                     # a catalyst that loses 40 % of its activity linearly over 20 steps
NOISE_LEVELS = (0.0, 0.002, 0.005, 0.01, 0.02)                        # standard deviation of the added noise on the conversion, as a fraction (0.01 = 1 percentage point)
SEEDS = (0, 1, 2, 3, 4)

NO_BENCHMARK = {
    "copilot": "rule-based; there is no recovered quantity to compare with a known truth",
    "optimizer": "its result is a setpoint; the 'true optimum' of the same forward model is the model's own, so a recovery benchmark would test scipy, not the method",
    "root_cause": "rule-based ranking of explanations; no ground-truth cause exists even in the twin",
    "pinn_kinetics": "has its own check against kinetics.py (its self-test); a recovery-error benchmark over seeds and training sets is a separate task",
    "federated_learning": "hypothetical plants; the comparison is already inside the module (federated versus single-plant versus pooled)",
    "multi_agent_negotiation": "illustration; a deterministic allocation with no estimated quantity",
    "multi_module_orchestration": "illustration; a deterministic optimisation over hypothetical modules",
    "sim_to_real": "already injects synthetic noise and offset and reports the gap (its own experiment); not repeated here",
    "time_series_sim": "a generator, not an estimator",
    "tda_analysis": "detection on a simulated trajectory has its own demonstration; a detection-rate benchmark needs a defined anomaly protocol",
    "novelty_audit": "coverage count; no estimated quantity",
    "safety_flags": "fixed comparisons with cited thresholds; no estimated quantity",
    "regulatory_drafting": "a template; no estimated quantity",
    "performance_guarantee": "Monte Carlo of Assumed ranges; no known truth to recover",
    "sa_virtual_sensors": "reads the twin's own value; recovery error is zero by construction",
    "ai_automation_layer": "architecture items; no estimated quantity",
    "uncertainty": "propagates Assumed ranges; no known truth to recover",
    "operator_setpoints": "a request mechanism; no estimated quantity",
}


def true_conversion(activity, t_c=T_C, ghsv=GHSV):
    return kinetics.hts_conversion(T_K=t_c + 273.15, GHSV=ghsv, y_CO_in=Y_CO_IN, steam_to_CO=STEAM_TO_CO, k0_scale=activity)


def run_benchmark(activities=TRUE_ACTIVITY, noise_levels=NOISE_LEVELS, seeds=SEEDS):
    """{"rows": [per (noise, seed) dict], "summary": [per noise dict]}. Reproducible: the noise comes from numpy's default_rng(seed) and nothing else is random."""
    truth_x = [true_conversion(a) for a in activities]
    rows = []
    for sigma in noise_levels:
        for seed in seeds:
            rng = np.random.default_rng(seed)
            noise = rng.normal(0.0, 1.0, len(activities)) * sigma           # drawn even for sigma = 0 so the stream is the same for every level
            errs, unreachable = [], 0
            for a, x, e in zip(activities, truth_x, noise):
                observed = float(min(max(x + e, 0.0), 1.0))
                r = pm.back_calculate_activity_hts(observed, T_C, GHSV, y_CO_in=Y_CO_IN, steam_to_CO=STEAM_TO_CO)
                if "error" in r:
                    unreachable += 1
                    continue
                errs.append(r["activity_factor"] - a)
            errs = np.array(errs)
            rows.append({"noise_sigma": sigma, "seed": seed, "n_steps": len(activities), "n_unreachable": unreachable,
                         "mae": float(np.mean(np.abs(errs))) if errs.size else float("nan"), "bias": float(np.mean(errs)) if errs.size else float("nan"),
                         "max_abs_error": float(np.max(np.abs(errs))) if errs.size else float("nan")})
    summary = []
    for sigma in noise_levels:
        sel = [r for r in rows if r["noise_sigma"] == sigma]
        summary.append({"noise_sigma": sigma, "mae_mean": float(np.mean([r["mae"] for r in sel])), "mae_sd_over_seeds": float(np.std([r["mae"] for r in sel])),
                        "bias_mean": float(np.mean([r["bias"] for r in sel])), "n_unreachable_total": int(sum(r["n_unreachable"] for r in sel)), "n_seeds": len(sel)})
    return {"rows": rows, "summary": summary, "truth_conversion": truth_x}


def render(result):
    L = ["# Synthetic benchmark: predictive_maintenance (inverse-kinetics catalyst activity)\n",
         "**This measures the code, not any plant.** The 'plant' is the forward model the method inverts; no plant data, no DOK-ING data and no readiness-gate threshold is involved. The noise levels are "
         "illustrative test inputs, not instrument specifications.\n",
         f"Setup: HTS at T = {T_C:.0f} degC, GHSV = {GHSV:.0f}, y_CO_in = {Y_CO_IN}, steam/CO = {STEAM_TO_CO}; true activity factor (k0_scale) falls linearly from "
         f"{TRUE_ACTIVITY[0]:.2f} to {TRUE_ACTIVITY[-1]:.2f} in {len(TRUE_ACTIVITY) - 1} steps; Gaussian noise (sigma as a fraction of conversion) on the conversion reading; seeds {list(SEEDS)}. "
         "Recovery error = recovered activity - true activity; MAE = mean absolute error over the steps; bias = mean signed error. A reading the inverse cannot reach "
         "(above the equilibrium ceiling) is counted as unreachable and left out of the error.\n",
         "## Summary per noise level (mean over seeds)\n",
         "| noise sigma | MAE | MAE sd over seeds | bias | unreachable readings |", "|---|---|---|---|---|"]
    for s in result["summary"]:
        L.append(f"| {s['noise_sigma']:.3f} | {s['mae_mean']:.2e} | {s['mae_sd_over_seeds']:.2e} | {s['bias_mean']:+.2e} | {s['n_unreachable_total']} |")
    L += ["", "## Per noise level and seed\n", "| noise sigma | seed | MAE | bias | max abs error | unreachable |", "|---|---|---|---|---|---|"]
    for r in result["rows"]:
        L.append(f"| {r['noise_sigma']:.3f} | {r['seed']} | {r['mae']:.2e} | {r['bias']:+.2e} | {r['max_abs_error']:.2e} | {r['n_unreachable']} |")
    L += ["", "## Modules with no benchmark yet\n", "| module | reason |", "|---|---|"] + [f"| {m} | {why} |" for m, why in NO_BENCHMARK.items()]
    return "\n".join(L) + "\n"


def main():
    result = run_benchmark()
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "synthetic_benchmark.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(render(result))
    with open(os.path.join(OUT_DIR, "synthetic_benchmark.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(result["rows"][0]))
        w.writeheader()
        w.writerows(result["rows"])
    sys.stdout.reconfigure(encoding="utf-8")
    print(render(result))
    print(f"wrote {os.path.join(OUT_DIR, 'synthetic_benchmark.md')} and .csv")


if __name__ == "__main__":
    main()
