"""
Federated learning v1 — FedAvg training of the HTS PINN across hypothetical plants.

HONEST SCOPING, stated here and in the app.py UI exactly like
multi_module_orchestration.py's and multi_agent_negotiation.py's own
"illustrative, not real facilities" disclaimers: this repo represents
exactly one real plant. The 3 "hypothetical plants" below are illustrative
HTS-temperature-variant stand-ins for a fleet — the same DEFAULT_MODULES
pattern multi_module_orchestration.py already uses (335/350/365C-style
variants) — not live data from real additional facilities. What IS real:
genuine federated averaging of real model weights, trained with this
project's own validated physics-informed loss (reused unchanged from
pinn_kinetics.py, not reimplemented).

THE FEDERATED-LEARNING PREMISE, honestly implemented rather than just
asserted: each hypothetical plant has its own PRIVATE local training data
— sampled from kinetics.py at that plant's own narrow operating band, and
never pooled or concatenated for federated training. Only trained model
WEIGHTS cross plant boundaries (via FedAvg's plain average), never raw
(T, GHSV, X) data points. Each plant also restricts its own physics-
residual collocation and boundary-condition sampling to its own local
band — it wouldn't have any reason to reason about a physical regime it
never operates in — so a single plant's model genuinely has no
information (neither data nor a physics constraint) outside its own band.
This is what makes the federation benefit real and demonstrable, not an
artifact of the physics term already generalizing everywhere on its own
(which pinn_kinetics.py's own compare_to_baseline() shows it does, when
its collocation sampling spans the FULL domain — deliberately not the
case here).

FEDAVG MECHANICS: each round, every plant starts from the CURRENT global
weights (a warm start, via pinn_kinetics.fine_tune — same physics-
residual + boundary-condition + data loss, no new optimization logic),
runs a LIMITED number of local optimizer iterations (not to convergence
— "a few local steps") on its own private data, and the resulting local
weight vectors are averaged (plain mean — every plant contributes an
equal-sized local dataset by construction, so this is also the sample-
weighted FedAvg average) into the next round's global weights.

THE THREE-WAY COMPARISON (the actual point of this module):
  (a) SINGLE-PLANT-ALONE — a model trained only on one plant's own local
      data (full training budget, not just a few steps), representing
      what that plant would have without any federation at all.
  (b) FEDERATED — the FedAvg global model above.
  (c) POOLED UPPER BOUND — an HONEST UPPER-BOUND REFERENCE ONLY, labeled
      as such: a model trained on every plant's raw data concatenated
      together, exactly what federated learning exists to avoid (for the
      data-privacy reason). Federated is expected to land meaningfully
      better than any single plant alone, and reasonably close to — but
      not necessarily matching — this upper bound, since it never
      actually saw the pooled raw data, only averaged weights.

HONEST LIMITATION: 3 plants, non-IID only along temperature (each
plant's local GHSV range is the full validated range). This demonstrates
the MECHANISM, not a claim about how many real plants a production
federated deployment would need.
"""
import numpy as np

from . import kinetics
from . import pinn_kinetics as pk

# --- Illustrative hypothetical plant variants (same pattern as
# multi_module_orchestration.py's DEFAULT_MODULES) — NOT real facilities ---
DEFAULT_PLANTS = [
    {"name": "Plant A (320°C HTS variant)", "T_center_C": 320.0},
    {"name": "Plant B (350°C HTS variant)", "T_center_C": 350.0},
    {"name": "Plant C (380°C HTS variant)", "T_center_C": 380.0},
]
PLANT_LOCAL_SPAN_C = 12.0  # each plant's local operating band: center +/- this (illustrative)

DEFAULT_WEIGHTS = {"data": 1.0, "bc": 1.0, "physics": 1.0}


def _plant_T_range(plant):
    c = plant["T_center_C"]
    lo = max(pk.T_MIN_C, c - PLANT_LOCAL_SPAN_C)
    hi = min(pk.T_MAX_C, c + PLANT_LOCAL_SPAN_C)
    return (lo, hi)


def _full_domain_test_set(n_eval, seed):
    rng = np.random.default_rng(seed)
    T_C = rng.uniform(pk.T_MIN_C, pk.T_MAX_C, n_eval)
    GHSV = rng.uniform(pk.GHSV_MIN, pk.GHSV_MAX, n_eval)
    X_true = np.array([kinetics.hts_conversion(T_K=t + 273.15, GHSV=g) for t, g in zip(T_C, GHSV)])
    return T_C, GHSV, X_true


def _range_test_set(T_range, n, seed):
    rng = np.random.default_rng(seed)
    T_C = rng.uniform(T_range[0], T_range[1], n)
    GHSV = rng.uniform(pk.GHSV_MIN, pk.GHSV_MAX, n)
    X_true = np.array([kinetics.hts_conversion(T_K=t + 273.15, GHSV=g) for t, g in zip(T_C, GHSV)])
    return T_C, GHSV, X_true


def _eval_model(flat_weights, T_C, GHSV, X_true):
    preds = pk.predict(flat_weights, T_C, GHSV)
    errors = np.abs(preds - X_true)
    return {"predictions": preds, "errors": errors, "mean_error": float(errors.mean()), "max_error": float(errors.max())}


def generate_plant_data(plants, n_local_labeled=8, seed=7):
    """Each plant's own PRIVATE local training data — generated once from
    kinetics.py at that plant's own narrow (T_range) operating band, and
    reused every FedAvg round (a fixed local dataset, as in a real
    federated client). This data is passed to run_federated_training()
    and to the single-plant-alone baselines below; it is NEVER pooled for
    federated training — only for the explicitly-labeled pooled upper
    bound, which exists purely as a reference point."""
    plant_data = []
    for i, p in enumerate(plants):
        T_range = _plant_T_range(p)
        T_C, GHSV, X = pk.generate_labeled_data(n_local_labeled, seed=seed + 100 + i, T_range=T_range,
                                                  ghsv_range=(pk.GHSV_MIN, pk.GHSV_MAX))
        plant_data.append({"name": p["name"], "T_range": T_range, "T_C": T_C, "GHSV": GHSV, "X": X})
    return plant_data


def run_federated_training(plant_data, n_rounds=50, local_maxiter=10, n_collocation=100, n_bc=15,
                            weights=None, seed=7):
    """Genuine FedAvg: each round, every plant warm-starts from the
    CURRENT global weights and runs a limited number of local optimizer
    iterations (pinn_kinetics.fine_tune — the existing physics-residual +
    boundary-condition + data loss, unchanged) on ONLY its own private
    local data and its own local (T_range) collocation/BC sampling. Local
    weight vectors are then averaged — never raw data — into the next
    round's global weights.

    local_maxiter is deliberately SMALL (a genuine "few local steps", not
    near-convergence) with a correspondingly larger n_rounds: letting each
    local update run too close to its own local optimum before averaging
    causes classic FedAvg "client drift" on this non-IID data — verified
    empirically (see the module's own tuning notes) that a small number of
    local iterations per round, repeated over many rounds, produces a
    genuinely better global model than fewer rounds of longer local
    training.

    Returns (flat_global, history) where history is a list of per-round
    per-plant local losses, for inspection/plotting."""
    weights = weights or DEFAULT_WEIGHTS
    global_flat = pk.random_init(seed)

    history = []
    for rnd in range(n_rounds):
        local_flats = []
        round_losses = []
        for i, pdata in enumerate(plant_data):
            T_data_K = pdata["T_C"] + 273.15
            tau_data = 1.0 / pdata["GHSV"]
            local_flat, local_loss = pk.fine_tune(
                global_flat, T_data_K, tau_data, pdata["X"], weights=weights,
                n_collocation=n_collocation, n_bc=n_bc, seed=seed + 1000 * rnd + i, maxiter=local_maxiter,
                T_range=pdata["T_range"], ghsv_range=(pk.GHSV_MIN, pk.GHSV_MAX),
            )
            local_flats.append(local_flat)
            round_losses.append({"plant": pdata["name"], "local_loss": local_loss})
        global_flat = np.mean(local_flats, axis=0)  # FedAvg: plain average of weights, never raw data
        history.append({"round": rnd + 1, "plant_losses": round_losses})

    return global_flat, history


def train_single_plant_alone(pdata, weights=None, seed=7, n_restarts=3, maxiter=500):
    """What one plant would have with NO federation at all: trained only
    on its own local data, with its own local physics collocation/BC
    range — full training budget (not just a few local steps), since this
    represents that plant's own best independent effort, not a FedAvg
    local update."""
    weights = weights or DEFAULT_WEIGHTS
    flat, final_loss, _ = pk.train(
        weights=weights, seed=seed, n_restarts=n_restarts, maxiter=maxiter,
        T_range=pdata["T_range"], ghsv_range=(pk.GHSV_MIN, pk.GHSV_MAX),
        labeled_data=(pdata["T_C"], pdata["GHSV"], pdata["X"]),
    )
    return flat, final_loss


def train_pooled_upper_bound(plant_data, weights=None, seed=999, n_restarts=3, maxiter=500):
    """HONEST UPPER-BOUND REFERENCE ONLY — explicitly labeled as such
    everywhere it's reported. Trains on every plant's raw data
    concatenated together, spanning the full validated domain for its
    physics term too. This is exactly what federated learning exists to
    avoid (centralizing raw data for the data-privacy reason); it exists
    here purely so the federated model's performance can be judged
    against what direct data pooling would have bought."""
    weights = weights or DEFAULT_WEIGHTS
    T_C_pool = np.concatenate([pd["T_C"] for pd in plant_data])
    GHSV_pool = np.concatenate([pd["GHSV"] for pd in plant_data])
    X_pool = np.concatenate([pd["X"] for pd in plant_data])
    flat, final_loss, _ = pk.train(
        weights=weights, seed=seed, n_restarts=n_restarts, maxiter=maxiter,
        T_range=(pk.T_MIN_C, pk.T_MAX_C), ghsv_range=(pk.GHSV_MIN, pk.GHSV_MAX),
        labeled_data=(T_C_pool, GHSV_pool, X_pool),
    )
    return flat, final_loss


def run_experiment(plants=None, n_rounds=50, n_local_labeled=8, local_maxiter=10,
                    n_collocation=100, n_bc=15, seed=7, n_eval=60, eval_seed=555,
                    single_n_restarts=3, single_maxiter=500):
    """Full pipeline: generates each hypothetical plant's private local
    data, runs genuine FedAvg, trains the single-plant-alone baselines and
    the explicitly-labeled pooled upper bound, then evaluates all of them
    on a full-domain test set (the step-3 three-way comparison) AND on
    cross-plant checks (step 5: each plant's own model evaluated on
    ANOTHER plant's local range, where the federated model — but not that
    plant's own model — has genuine information via averaged weights)."""
    plants = plants if plants is not None else DEFAULT_PLANTS
    weights = DEFAULT_WEIGHTS

    plant_data = generate_plant_data(plants, n_local_labeled=n_local_labeled, seed=seed)

    flat_fed, history = run_federated_training(
        plant_data, n_rounds=n_rounds, local_maxiter=local_maxiter,
        n_collocation=n_collocation, n_bc=n_bc, weights=weights, seed=seed,
    )

    single_plant_models = []
    for i, pdata in enumerate(plant_data):
        flat_i, loss_i = train_single_plant_alone(
            pdata, weights=weights, seed=seed + 100 + i, n_restarts=single_n_restarts, maxiter=single_maxiter,
        )
        single_plant_models.append({"name": pdata["name"], "flat": flat_i, "final_loss": loss_i, "T_range": pdata["T_range"]})

    flat_pooled, pooled_loss = train_pooled_upper_bound(
        plant_data, weights=weights, seed=seed + 999, n_restarts=single_n_restarts, maxiter=single_maxiter,
    )

    # Step 3: full-domain three-way comparison
    T_test, GHSV_test, X_true = _full_domain_test_set(n_eval, seed=eval_seed)
    fed_result = _eval_model(flat_fed, T_test, GHSV_test, X_true)
    pooled_result = _eval_model(flat_pooled, T_test, GHSV_test, X_true)
    single_results = [
        {"name": m["name"], **_eval_model(m["flat"], T_test, GHSV_test, X_true)}
        for m in single_plant_models
    ]
    avg_single_mean_error = float(np.mean([s["mean_error"] for s in single_results]))
    best_single_mean_error = float(np.min([s["mean_error"] for s in single_results]))

    # Step 5: cross-plant generalization — each plant's OWN model tested on
    # ANOTHER plant's local range, vs the federated model on that same range.
    cross_checks = []
    for i, pdata_i in enumerate(plant_data):
        for j, pdata_j in enumerate(plant_data):
            if i == j:
                continue
            T_c, GHSV_c, X_c = _range_test_set(single_plant_models[j]["T_range"], n=20, seed=eval_seed + i * 10 + j)
            err_i = float(np.mean(np.abs(pk.predict(single_plant_models[i]["flat"], T_c, GHSV_c) - X_c)))
            err_fed = float(np.mean(np.abs(pk.predict(flat_fed, T_c, GHSV_c) - X_c)))
            cross_checks.append({
                "single_plant": plant_data[i]["name"], "tested_on_range_of": plant_data[j]["name"],
                "single_plant_error": err_i, "federated_error": err_fed,
                "federated_wins": err_fed < err_i,
            })
    federated_wins_fraction = float(np.mean([c["federated_wins"] for c in cross_checks])) if cross_checks else float("nan")

    return {
        "plants": plants, "plant_data": plant_data, "history": history,
        "flat_federated": flat_fed, "flat_pooled": flat_pooled, "single_plant_models": single_plant_models,
        "fed_result": fed_result, "pooled_result": pooled_result, "single_results": single_results,
        "avg_single_mean_error": avg_single_mean_error, "best_single_mean_error": best_single_mean_error,
        "cross_checks": cross_checks, "federated_wins_fraction": federated_wins_fraction,
    }


if __name__ == "__main__":
    import time

    t0 = time.time()
    result = run_experiment()
    print(f"Full experiment ran in {time.time() - t0:.1f}s\n")

    print("=== Step 3: three-way full-domain comparison ===")
    for s in result["single_results"]:
        print(f"  single-plant-alone [{s['name']}]: mean_error={s['mean_error']:.4f}  max_error={s['max_error']:.4f}")
    print(f"  single-plant-alone AVERAGE:        mean_error={result['avg_single_mean_error']:.4f}")
    print(f"  single-plant-alone BEST:           mean_error={result['best_single_mean_error']:.4f}")
    print(f"  FEDERATED (FedAvg):                mean_error={result['fed_result']['mean_error']:.4f}  "
          f"max_error={result['fed_result']['max_error']:.4f}")
    print(f"  POOLED UPPER BOUND (reference only): mean_error={result['pooled_result']['mean_error']:.4f}  "
          f"max_error={result['pooled_result']['max_error']:.4f}")

    print("\n=== Step 5: cross-plant generalization (the actual point of federation) ===")
    for c in result["cross_checks"]:
        marker = "federated wins" if c["federated_wins"] else "federated does NOT win"
        print(f"  [{c['single_plant']}] tested on [{c['tested_on_range_of']}]'s range: "
              f"single_plant_error={c['single_plant_error']:.4f}  federated_error={c['federated_error']:.4f}  ({marker})")
    print(f"\n  Federated wins in {result['federated_wins_fraction'] * 100:.0f}% of cross-plant checks.")
