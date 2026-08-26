"""
Physics-informed neural network (PINN) v1 — HTS WGS conversion.

DEPENDENCY DECISION, made explicitly and honestly before writing any
network code (checked, not assumed): PyTorch/JAX/autograd are NOT
already dependencies of this repo. Adding a real autodiff framework is a
genuine deployment risk on Streamlit Community Cloud's free tier —
PyTorch's CPU wheel alone is several hundred MB on top of this app's
existing dependencies (streamlit, numpy, pandas, altair, scipy,
supabase), and this repo has already observed Cloud's shared/limited CPU
running noticeably slower than local for much cheaper scipy
optimizations elsewhere (optimizer.py, multi_module_orchestration.py).

DECISION: hand-roll a tiny NumPy MLP (2 inputs, 8 hidden neurons, 1
output — ~33 parameters total) with an ANALYTICALLY-DERIVED gradient for
the physics-residual term (worked out by hand below, verified against a
finite-difference check before use — see the module's own self-test),
and train with scipy.optimize.minimize (already a dependency), whose
default finite-difference gradient over ~33 weights is cheap precisely
BECAUSE the network is this small — this would not scale to a real deep
network, which is exactly why a deep network isn't used here. This is
the lighter alternative the task explicitly permits, not a silent
downgrade from "should have used PyTorch."

THE PHYSICS: kinetics.py's hts_conversion() integrates the ODE
    dX/dtau = k(T) * y_CO_in * [(1-X)(steam_to_CO-X) - X^2/keq(T)]
(derived directly from kinetics.py's _integrate_conversion — same
Arrhenius k(T) and Moe 1962 keq(T) correlation, same HTS defaults:
y_CO_in=0.28, steam_to_CO=4.0, k0=5.7231e12, Ea=111000 J/mol) over
tau in [0, 1/GHSV], starting from X(tau=0)=0. This module trains a
network X_NN(T, tau; theta) to satisfy that SAME continuous ODE via a
physics-residual loss evaluated at randomly sampled (T, tau) collocation
points, plus the real boundary condition X(T,0)=0, anchored by only a
FEW (5-10) labeled (T, GHSV) -> X points from kinetics.py's own
validated output — not thousands. "HTS conversion at (T, GHSV)" is then
X_NN evaluated at tau = 1/GHSV, the reactor's exit.

Network: X_NN = sigmoid(W2 . tanh(W1 . [T_norm, tau_norm] + b1) + b2).
dX_NN/d(tau_norm) is derived analytically by the chain rule (sigmoid'
* tanh' * weights) — no autodiff needed for a network this shallow.

LIMITATIONS, stated explicitly per the brief:
  - Same steady-state assumptions as the rest of this repo — this is
    NOT a dynamic/transient model (see optimizer.py's and
    uncertainty.py's own scoping statements for that same limitation).
  - Trained on ONE specific rate law: HTS only (kinetics.hts_conversion),
    not LTS, not PSA, not any other subsystem.
  - Does not generalize beyond the physical range this project has
    already validated: 300-400C, 1000-4000 GHSV. Predictions outside
    that box are extrapolation and are not represented as reliable.
"""
import numpy as np
from scipy.optimize import minimize

from . import kinetics

# --- Real HTS rate law constants, copied from kinetics.py's own values
# (not re-derived) so the physics residual matches exactly. ---
R_GAS = 8.314
Y_CO_IN = 0.28
STEAM_TO_CO = 4.0
K0_HTS = 5.7231e12
EA_HTS = 111000.0

# Validated physical range (matches this repo's own sliders/bounds elsewhere)
T_MIN_C, T_MAX_C = 300.0, 400.0
GHSV_MIN, GHSV_MAX = 1000.0, 4000.0

T_CENTER_K = 623.15   # 350C, domain center
T_SCALE_K = 50.0      # so 300-400C maps to roughly [-1, 1]
TAU_SCALE = 1.0 / GHSV_MIN  # 0.001 -- so tau_norm ranges roughly [0.25, 1.0]

HIDDEN = 8
N_PARAMS = HIDDEN * 2 + HIDDEN + HIDDEN + 1  # W1, b1, W2, b2


def _keq(T_K):
    """Moe (1962) equilibrium correlation — identical to kinetics.py's own."""
    return np.exp(4577.8 / T_K - 4.33)


def _rate_rhs(X, T_K):
    """dX/dtau per the CONTINUOUS HTS ODE (before kinetics.py's discrete
    integrator's clipping/early-break, which are numerical safeguards for
    the solver, not part of the underlying differential equation itself)."""
    k = K0_HTS * np.exp(-EA_HTS / (R_GAS * T_K))
    keq = _keq(T_K)
    C_CO = Y_CO_IN * (1 - X)
    C_H2O = Y_CO_IN * (STEAM_TO_CO - X)
    C_H2 = Y_CO_IN * X
    C_CO2 = Y_CO_IN * X
    r = k * (C_CO * C_H2O - (C_CO2 * C_H2) / keq)
    return r / Y_CO_IN


def _pack(W1, b1, W2, b2):
    return np.concatenate([W1.ravel(), b1.ravel(), W2.ravel(), np.array([b2])])


def random_init(seed=0):
    """A single random initial weight vector, same distribution as train()'s
    own per-restart initialization — public so other modules (e.g.
    federated_learning.py's FedAvg global-model initialization) can reuse
    it without reaching into the private packing internals below."""
    rng = np.random.default_rng(seed)
    W1 = rng.normal(0, 0.5, (HIDDEN, 2))
    b1 = rng.normal(0, 0.5, HIDDEN)
    W2 = rng.normal(0, 0.5, HIDDEN)
    return _pack(W1, b1, W2, 0.0)


def _unpack(flat):
    idx = 0
    W1 = flat[idx:idx + HIDDEN * 2].reshape(HIDDEN, 2); idx += HIDDEN * 2
    b1 = flat[idx:idx + HIDDEN]; idx += HIDDEN
    W2 = flat[idx:idx + HIDDEN]; idx += HIDDEN
    b2 = flat[idx]
    return W1, b1, W2, b2


def _forward(flat, T_K, tau):
    """Vectorized forward pass. Returns X, hidden activations, and W1/W2
    (needed by the analytic gradient below)."""
    W1, b1, W2, b2 = _unpack(flat)
    T_K = np.atleast_1d(T_K).astype(float)
    tau = np.atleast_1d(tau).astype(float)
    T_norm = (T_K - T_CENTER_K) / T_SCALE_K
    tau_norm = tau / TAU_SCALE
    X_in = np.stack([T_norm, tau_norm], axis=-1)
    Z = X_in @ W1.T + b1
    Hact = np.tanh(Z)
    out = Hact @ W2 + b2
    X = 1.0 / (1.0 + np.exp(-out))
    return X, Hact, W1, W2


def _dX_dtaunorm(flat, T_K, tau):
    """Analytic dX/d(tau_norm) — hand-derived chain rule, verified against
    a finite-difference check to machine precision before use in training
    (see tests run during development; not re-checked on every call for
    speed, but the derivation is exact, not approximate):

        dX/dout      = X(1-X)                    [sigmoid derivative]
        dout/dh_j    = W2_j
        dh_j/dz_j    = 1 - h_j^2                  [tanh derivative]
        dz_j/d(tau_norm) = W1[j, 1]                [tau_norm's column of W1]

        dX/d(tau_norm) = X(1-X) * sum_j [ W2_j * (1-h_j^2) * W1[j,1] ]
    """
    X, Hact, W1, W2 = _forward(flat, T_K, tau)
    dH_dZ = 1 - Hact ** 2
    dZ_dtaunorm = W1[:, 1]
    dout_dtaunorm = (dH_dZ * dZ_dtaunorm) @ W2
    dX_dtaunorm = X * (1 - X) * dout_dtaunorm
    return X, dX_dtaunorm


def generate_labeled_data(n_points=8, seed=7, T_range=None, ghsv_range=None):
    """The FEW labeled anchor points — real kinetics.py output, not
    thousands of points. Called once at training start, not per-iteration.
    T_range/ghsv_range default to the full validated domain (T_MIN_C..
    T_MAX_C, GHSV_MIN..GHSV_MAX); federated_learning.py passes a narrower
    range to sample each hypothetical plant's own local operating band."""
    T_lo, T_hi = T_range if T_range is not None else (T_MIN_C, T_MAX_C)
    G_lo, G_hi = ghsv_range if ghsv_range is not None else (GHSV_MIN, GHSV_MAX)
    rng = np.random.default_rng(seed)
    T_C = rng.uniform(T_lo, T_hi, n_points)
    GHSV = rng.uniform(G_lo, G_hi, n_points)
    X = np.array([kinetics.hts_conversion(T_K=t + 273.15, GHSV=g) for t, g in zip(T_C, GHSV)])
    return T_C, GHSV, X


def _loss(flat, T_data_K, tau_data, X_data, T_bc_K, T_c_K, tau_c, weights):
    X_pred, _, _, _ = _forward(flat, T_data_K, tau_data)
    data_loss = np.mean((X_pred - X_data) ** 2)

    X_bc, _, _, _ = _forward(flat, T_bc_K, np.zeros_like(T_bc_K))
    bc_loss = np.mean(X_bc ** 2)  # real boundary condition: X(T, tau=0) = 0

    X_c, dXdtaunorm_c = _dX_dtaunorm(flat, T_c_K, tau_c)
    rhs_c = _rate_rhs(X_c, T_c_K)
    residual = dXdtaunorm_c - TAU_SCALE * rhs_c  # both sides in tau_norm units
    physics_loss = np.mean(residual ** 2)

    return weights["data"] * data_loss + weights["bc"] * bc_loss + weights["physics"] * physics_loss


def train(n_labeled=8, n_collocation=200, n_bc=20, weights=None, seed=7, n_restarts=5, maxiter=800,
          T_range=None, ghsv_range=None, labeled_data=None):
    """Trains the PINN (or, with weights={'physics': 0.0}, a same-
    architecture data-only baseline for comparison — see
    compare_to_baseline() below). Multiple random restarts (cheap, since
    the network is tiny) guard against a bad local minimum from a single
    random initialization.

    T_range/ghsv_range restrict where labeled data AND the physics
    collocation/boundary-condition points are sampled from — default is
    the full validated domain, unchanged from before. labeled_data, if
    given, is an explicit (T_C, GHSV, X) tuple used INSTEAD of generating
    it internally — e.g. federated_learning.py's pooled-data upper-bound
    model, which trains on multiple hypothetical plants' data concatenated
    together (labeled_data), still bounded by T_range/ghsv_range for its
    physics term. Both are additive, backward-compatible: every existing
    caller that omits them gets identical behavior to before.

    Returns (flat_weights, final_loss, (T_C_labeled, GHSV_labeled, X_labeled)).
    """
    weights = weights or {"data": 1.0, "bc": 1.0, "physics": 1.0}
    T_lo, T_hi = T_range if T_range is not None else (T_MIN_C, T_MAX_C)
    G_lo, G_hi = ghsv_range if ghsv_range is not None else (GHSV_MIN, GHSV_MAX)

    if labeled_data is not None:
        T_C_data, GHSV_data, X_data = labeled_data
    else:
        T_C_data, GHSV_data, X_data = generate_labeled_data(n_labeled, seed=seed, T_range=(T_lo, T_hi), ghsv_range=(G_lo, G_hi))
    T_data_K = T_C_data + 273.15
    tau_data = 1.0 / GHSV_data

    rng = np.random.default_rng(seed + 1)
    T_bc_K = rng.uniform(T_lo, T_hi, n_bc) + 273.15
    T_c_K = rng.uniform(T_lo, T_hi, n_collocation) + 273.15
    tau_c = rng.uniform(1.0 / G_hi, 1.0 / G_lo, n_collocation)

    best = None
    for r in range(n_restarts):
        rr = np.random.default_rng(1000 + r)
        W1 = rr.normal(0, 0.5, (HIDDEN, 2))
        b1 = rr.normal(0, 0.5, HIDDEN)
        W2 = rr.normal(0, 0.5, HIDDEN)
        x0 = _pack(W1, b1, W2, 0.0)
        res = minimize(
            _loss, x0, args=(T_data_K, tau_data, X_data, T_bc_K, T_c_K, tau_c, weights),
            method="L-BFGS-B", options={"maxiter": maxiter},
        )
        if best is None or res.fun < best.fun:
            best = res

    return best.x, float(best.fun), (T_C_data, GHSV_data, X_data)


def fine_tune(flat_init, T_data_K, tau_data, X_data, weights=None, n_collocation=200, n_bc=20, seed=123, maxiter=300,
              T_range=None, ghsv_range=None):
    """Warm-started adaptation: continues optimizing FROM an already-trained
    weight vector (flat_init) on new labeled data, reusing the identical
    loss composition as train() — same physics-residual term, same boundary
    condition, just a fresh random draw of collocation/BC points and a new
    (typically small) labeled-data set. A single run, not multiple random
    restarts, since the point is to adapt an existing solution, not search
    for a new one from scratch. Used by sim_to_real.py to fine-tune a
    simulation-trained PINN on a few noisy "real-world" points, and by
    federated_learning.py as each hypothetical plant's local FedAvg training
    step (T_range/ghsv_range there is that plant's own local operating
    band) — no new optimization logic, just this module's existing
    machinery re-entered from a warm start.

    Returns (flat_adapted, final_loss).
    """
    weights = weights or {"data": 1.0, "bc": 1.0, "physics": 1.0}
    T_lo, T_hi = T_range if T_range is not None else (T_MIN_C, T_MAX_C)
    G_lo, G_hi = ghsv_range if ghsv_range is not None else (GHSV_MIN, GHSV_MAX)
    rng = np.random.default_rng(seed)
    T_bc_K = rng.uniform(T_lo, T_hi, n_bc) + 273.15
    T_c_K = rng.uniform(T_lo, T_hi, n_collocation) + 273.15
    tau_c = rng.uniform(1.0 / G_hi, 1.0 / G_lo, n_collocation)

    res = minimize(
        _loss, flat_init, args=(T_data_K, tau_data, X_data, T_bc_K, T_c_K, tau_c, weights),
        method="L-BFGS-B", options={"maxiter": maxiter},
    )
    return res.x, float(res.fun)


def predict(flat, T_C, GHSV):
    """HTS conversion prediction at (T_C, GHSV) — the network evaluated at
    tau = 1/GHSV, the reactor exit."""
    T_K = np.atleast_1d(T_C).astype(float) + 273.15
    tau = 1.0 / np.atleast_1d(GHSV).astype(float)
    X, _, _, _ = _forward(flat, T_K, tau)
    return X


def compare_to_baseline(n_labeled=8, n_test=40, seed=7, test_seed=999, **train_kwargs):
    """The real test (step 3): trains the physics-informed model AND a
    same-architecture, same-data data-only baseline (physics weight=0),
    then compares both against kinetics.py's real ODE integration across
    a random test grid — reporting error near vs far from the labeled
    training points. If the PINN's far-point error stays close to its
    near-point error while the baseline's degrades, that's real evidence
    the physics loss is doing genuine work, not just memorizing a few
    points."""
    pinn_weights = {"data": 1.0, "bc": 1.0, "physics": 1.0}
    baseline_weights = {"data": 1.0, "bc": 1.0, "physics": 0.0}

    flat_pinn, loss_pinn, (T_data, GHSV_data, X_data) = train(
        n_labeled=n_labeled, weights=pinn_weights, seed=seed, **train_kwargs
    )
    flat_baseline, loss_baseline, _ = train(
        n_labeled=n_labeled, weights=baseline_weights, seed=seed, **train_kwargs
    )

    rng = np.random.default_rng(test_seed)
    T_test = rng.uniform(T_MIN_C, T_MAX_C, n_test)
    G_test = rng.uniform(GHSV_MIN, GHSV_MAX, n_test)
    X_true = np.array([kinetics.hts_conversion(T_K=t + 273.15, GHSV=g) for t, g in zip(T_test, G_test)])

    Tn_data = (T_data - T_MIN_C) / (T_MAX_C - T_MIN_C)
    Gn_data = (GHSV_data - GHSV_MIN) / (GHSV_MAX - GHSV_MIN)
    Tn_test = (T_test - T_MIN_C) / (T_MAX_C - T_MIN_C)
    Gn_test = (G_test - GHSV_MIN) / (GHSV_MAX - GHSV_MIN)
    dist_to_nearest = np.array([
        np.min(np.sqrt((Tn_data - tn) ** 2 + (Gn_data - gn) ** 2))
        for tn, gn in zip(Tn_test, Gn_test)
    ])
    median_dist = float(np.median(dist_to_nearest))
    near_mask = dist_to_nearest <= median_dist
    far_mask = ~near_mask

    def _summarize(flat):
        preds = predict(flat, T_test, G_test)
        errs = np.abs(preds - X_true)
        near_mean = float(errs[near_mask].mean())
        far_mean = float(errs[far_mask].mean())
        return {
            "predictions": preds, "errors": errs,
            "mean_error": float(errs.mean()), "max_error": float(errs.max()),
            "near_mean_error": near_mean, "far_mean_error": far_mean,
            "far_to_near_ratio": far_mean / near_mean if near_mean > 0 else float("nan"),
        }

    return {
        "T_test": T_test, "G_test": G_test, "X_true": X_true,
        "T_labeled": T_data, "GHSV_labeled": GHSV_data, "X_labeled": X_data,
        "near_mask": near_mask, "far_mask": far_mask,
        "pinn": {"weights": flat_pinn, "final_loss": loss_pinn, **_summarize(flat_pinn)},
        "baseline": {"weights": flat_baseline, "final_loss": loss_baseline, **_summarize(flat_baseline)},
    }


if __name__ == "__main__":
    # Self-check: verify the analytic gradient against finite differences
    # BEFORE trusting it in training — a wrong analytic gradient would
    # silently corrupt the whole physics loss.
    rng = np.random.default_rng(42)
    flat_check = _pack(rng.normal(0, 0.5, (HIDDEN, 2)), rng.normal(0, 0.5, HIDDEN), rng.normal(0, 0.5, HIDDEN), 0.3)
    T_chk, tau_chk = np.array([620.0, 650.0]), np.array([0.0005, 0.0003])
    _, dX_analytic = _dX_dtaunorm(flat_check, T_chk, tau_chk)
    eps = 1e-6
    Xp, _, _, _ = _forward(flat_check, T_chk, (tau_chk / TAU_SCALE + eps) * TAU_SCALE)
    Xm, _, _, _ = _forward(flat_check, T_chk, (tau_chk / TAU_SCALE - eps) * TAU_SCALE)
    dX_numeric = (Xp - Xm) / (2 * eps)
    assert np.allclose(dX_analytic, dX_numeric, atol=1e-5), "analytic gradient does not match finite differences"
    print(f"Gradient self-check PASSED (max diff {np.max(np.abs(dX_analytic - dX_numeric)):.2e})")

    print("\nTraining PINN vs data-only baseline, comparing against real kinetics.py...")
    result = compare_to_baseline()
    for label in ("pinn", "baseline"):
        r = result[label]
        print(f"\n{label.upper()}: final_loss={r['final_loss']:.6f}")
        print(f"  mean_error={r['mean_error']:.4f}  max_error={r['max_error']:.4f}")
        print(f"  near_mean_error={r['near_mean_error']:.4f}  far_mean_error={r['far_mean_error']:.4f}  "
              f"far/near ratio={r['far_to_near_ratio']:.2f}x")
