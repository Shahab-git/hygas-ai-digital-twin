"""
Calibration core, step 2 (task CAL-2): track slowly drifting Assumed GA-001 inputs from a stream of gas-train measurements with an extended Kalman filter (EKF).

STATUS: a TWIN EXPERIMENT tool, proven on SYNTHETIC data only. The "measurements" in every test are the unchanged engine's own output at a known (moving) parameter path plus seeded noise, so the loop
is proven but NOTHING here is validation against DOK-ING data (none exists). Nothing in the engine, the runtime or the app imports this module; no parameter of the model is changed.

What it does
  The state is the vector of the four calibration parameters of python/calibration.py (ER, steam_to_feed, carbon_conversion, ch4_carbon_fraction). The process model is a RANDOM WALK: between two
  measurement times each parameter may move by a Gaussian step whose standard deviation is `drift_fraction` x its prior range (Assumed, a tuning number, not a physical law). The measurement model is
  the engine itself (calibration.forward) evaluated at the predicted state; its sensitivity H is the finite-difference Jacobian of calibration.py, computed ONCE at the nominal point (a "chord" EKF)
  or re-computed at the current estimate every `relinearise_every` steps (costs 5 engine runs each time). The update is the Joseph form; the estimate is clipped to the prior bounds (a stated heuristic).
  `track(...)` runs the filter on a measurement list; `drift_experiment(...)` synthesises measurements from a truth PATH, runs the filter and a static (never updated) twin side by side and reports
  the parameter and observable errors of both and the normalised innovation squared (NIS) consistency check.

SIMPLIFICATIONS, stated: (1) the measurements are one quasi-steady value per time step (the engine is quasi-steady), so this tracks DRIFT, not dynamics; (2) the random-walk size, the initial
covariance and the noise sigmas are ASSUMED; (3) the Jacobian is frozen unless asked otherwise, so a large excursion from the nominal point is linearised badly (the NIS check shows it); (4) clipping to
the bounds is a heuristic and biases the estimate near a bound; (5) the four parameters are only weakly separable with the six assumed observables (see docs/calibration_core_step1.md), so the filter
tracks the COMBINATIONS the data constrain and the others wander inside their prior: a good observable fit is not proof the parameters are right.
"""
import numpy as np

from . import calibration as cal

DRIFT_FRACTION = 0.02          # Assumed: per-step random-walk standard deviation as a fraction of each parameter's prior range
P0_FRACTION = 0.5              # Assumed: initial standard deviation as a fraction of each parameter's prior range (roughly "uniform over the range")
STATUS = "Calculated on synthetic data; NOT validation against DOK-ING data (none exists); nothing is calibrated in the model"


def _specs():
    return cal.parameter_specs()


def track(measurements, sigma=None, start=None, drift_fraction=DRIFT_FRACTION, p0_fraction=P0_FRACTION, observables=cal.OBSERVABLE_NAMES, relinearise_every=None):
    """Run the EKF over `measurements` (list of {observable: value}); returns a dict with per-step estimates, standard deviations, innovations and NIS.
    `start` is {parameter: value} (default the nominal values)."""
    specs = _specs()
    names = [s["name"] for s in specs]
    lo = np.array([s["low"] for s in specs], float)
    hi = np.array([s["high"] for s in specs], float)
    rng = hi - lo
    x = np.array([(start or {}).get(n, s["nominal"]) for n, s in zip(names, specs)], float)
    P = np.diag((p0_fraction * rng) ** 2)
    Q = np.diag((drift_fraction * rng) ** 2)
    sg = {o: (sigma or cal.SIGMA)[o] for o in observables}
    R = np.diag([sg[o] ** 2 for o in observables])
    J = None
    steps = []
    for k, meas in enumerate(measurements):
        missing = [o for o in observables if o not in meas]
        if missing:
            raise KeyError(f"measurement {k} lacks observable(s): {missing}")
        y = np.array([meas[o] for o in observables], float)
        P = P + Q                                                   # predict: random walk, state unchanged, covariance grows
        if J is None or (relinearise_every and k % relinearise_every == 0):
            J = cal._jacobian({n: float(v) for n, v in zip(names, x)}, specs, observables)[1]
        pred = cal._vector(cal.forward({n: float(v) for n, v in zip(names, x)}), observables)
        nu = y - pred                                               # innovation
        S = J @ P @ J.T + R
        K = P @ J.T @ np.linalg.inv(S)
        nis = float(nu @ np.linalg.solve(S, nu))
        x_new = np.clip(x + K @ nu, lo, hi)                         # heuristic clipping to the prior bounds
        I_KH = np.eye(len(x)) - K @ J
        P = I_KH @ P @ I_KH.T + K @ R @ K.T                         # Joseph form
        x = x_new
        steps.append({"k": k, "estimate": {n: float(v) for n, v in zip(names, x)}, "std": {n: float(np.sqrt(P[i, i])) for i, n in enumerate(names)},
                      "innovation": nu.tolist(), "nis": nis})
    return {"steps": steps, "parameters": names, "observables": list(observables), "n_observables": len(observables), "status": STATUS,
            "drift_fraction": drift_fraction, "p0_fraction": p0_fraction}


def drift_experiment(truth_path, noise_seed=0, noise_scale=1.0, sigma=None, observables=cal.OBSERVABLE_NAMES, **kw):
    """`truth_path`: list of {parameter: value} (missing names = nominal), one per time step. Synthesises noisy measurements from the engine, runs the EKF and a static twin (nominal
    parameters, never updated), returns both errors. The measurements are the engine's own output: this proves the loop, not the physics."""
    specs = _specs()
    names = [s["name"] for s in specs]
    nominal = {s["name"]: s["nominal"] for s in specs}
    path = [{n: p.get(n, nominal[n]) for n in names} for p in truth_path]
    sg = {o: (sigma or cal.SIGMA)[o] for o in observables}
    rng = np.random.default_rng(noise_seed)
    clean = [cal.forward(p) for p in path]
    meas = [{o: c[o] + noise_scale * sg[o] * float(rng.standard_normal()) for o in observables} for c in clean]
    rep = track(meas, sigma=sg, observables=observables, **kw)
    static = cal.forward(nominal)
    rep["truth_path"] = path
    rep["measurements"] = meas
    for st, p, c in zip(rep["steps"], path, clean):
        st["param_error"] = {n: st["estimate"][n] - p[n] for n in names}
        st["static_param_error"] = {n: nominal[n] - p[n] for n in names}
        est_obs = cal.forward(st["estimate"])
        st["obs_error"] = {o: est_obs[o] - c[o] for o in observables}
        st["static_obs_error"] = {o: static[o] - c[o] for o in observables}
    return rep


def summarise(rep, last=4):
    """Mean absolute parameter error and root-mean-square observable error (in noise sigmas) over the last `last` steps, filter vs static twin, plus the mean NIS (expected: the number of observables)."""
    st = rep["steps"][-last:]
    names, obs = rep["parameters"], rep["observables"]
    sg = cal.SIGMA
    out = {"mean_nis": float(np.mean([s["nis"] for s in rep["steps"]])), "expected_nis": rep["n_observables"], "parameters": {}, "obs_rmse_sigma": {}}
    for n in names:
        out["parameters"][n] = {"filter_abs_error": float(np.mean([abs(s["param_error"][n]) for s in st])), "static_abs_error": float(np.mean([abs(s["static_param_error"][n]) for s in st]))}
    for lab, key in (("filter", "obs_error"), ("static", "static_obs_error")):
        out["obs_rmse_sigma"][lab] = float(np.sqrt(np.mean([(s[key][o] / sg[o]) ** 2 for s in st for o in obs])))
    return out
