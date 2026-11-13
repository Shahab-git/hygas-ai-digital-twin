"""
Calibration core, step 1 (task CAL-1): fit Assumed GA-001 inputs to gas-train measurements and report what the data can and cannot identify.

STATUS: a TWIN EXPERIMENT tool, proven on SYNTHETIC data only. The "measurements" in every test are the unchanged engine's own output at a known parameter set plus seeded noise, so the loop is
proven (the truth is recovered, the confounding is exposed) but NOTHING here is validation against DOK-ING data: none exists. No parameter of the model is changed; nothing in the engine, the runtime, the
app or the uncertainty module imports this module. It is the first, small part of the step the data-replacement layer's section 7 left open ("which Assumed parameters are identifiable first").

What it does
  forward(params)       the engine's GA-001 gas outputs for a dict of Assumed inputs (the engine's own override mechanism, in-process, against the in-memory fake store: offline, no database).
  jacobian_report(...)  sensitivities of the observables to the parameters at a point, scaled by the observation noise and by the parameter range: singular values, condition number, the parameter
                        correlation implied by the information matrix, a per-parameter standard error and a verdict.
  fit(...)              bounded least squares (scipy.optimize.least_squares, trust-region reflective) of the parameters to a measurement set; returns the estimate, its covariance, the correlation matrix
                        and the same verdicts.
  twin_experiment(...)  synthesise measurements at a known truth with seeded Gaussian noise, fit from the nominal start, report the recovery.

Parameters (engine inputs only; bounds are the repo's own ranges from python/parameter_table.py, which are Assumed): GA-001.ER, GA-001.steam_to_feed_kg_kg, GA-001.carbon_conversion,
GA-001.ch4_carbon_fraction. Observables (the gas-train analysers and flow meter of the registry): H2, CO, CO2, CH4, N2 (mol % dry) and the dry gas flow (Nm3/h).

SIMPLIFICATIONS, stated: (1) the observation noise sigmas below are ASSUMED sensor accuracies, not DOK-ING's; (2) the model is quasi-steady, so the observables are one value per run (a time series would have
to be averaged to one steady point first); (3) the forward model uses the default `heat_only` tail-gas mode and 2 cycles (the GA-001 gas is identical to 20 cycles in that mode; measured, and guarded by a test); (4) the verdict
threshold is a stated heuristic, not a statistical test; (5) the Jacobian is by finite differences of a deterministic algebraic model.
"""
import numpy as np
from scipy.optimize import least_squares

from . import parameter_table as pt
from . import plant_status as ps

N_CYCLES = 2                        # GA-001's gas is identical to its 20-cycle value in heat_only mode from cycle 2 on (measured; a test guards it)
STATUS = "Calculated on synthetic data; NOT validation against DOK-ING data (none exists); nothing is calibrated in the model"

# (name, engine key, parameter_table tag): the four Assumed engine inputs the gas train can in principle constrain (docs/data_replacement_layer.md section 5, identifiability map)
PARAMETERS = (
    ("ER", "equivalence_ratio", "GA-001.ER"),
    ("steam_to_feed", "steam_to_feed_ratio", "GA-001.steam_to_feed_kg_kg"),
    ("carbon_conversion", "carbon_conversion_efficiency", "GA-001.carbon_conversion"),
    ("ch4_carbon_fraction", "ch4_carbon_fraction", "GA-001.ch4_carbon_fraction"),
)
# observable -> (key in the GA-001 Outputs entry, ASSUMED 1-sigma noise, unit). Gas analysers +/-0.5 mol % absolute, flow meter +/-2 % of ~80 Nm3/h: Assumed, not DOK-ING's.
OBSERVABLES = (
    ("H2_mol_pct_dry", 0.5, "mol% dry"), ("CO_mol_pct_dry", 0.5, "mol% dry"), ("CO2_mol_pct_dry", 0.5, "mol% dry"),
    ("CH4_mol_pct_dry", 0.2, "mol% dry"), ("N2_mol_pct_dry", 0.5, "mol% dry"), ("dry_flow_nm3_h", 1.6, "Nm3/h"),
)
OBSERVABLE_NAMES = tuple(o[0] for o in OBSERVABLES)
SIGMA = {o[0]: o[1] for o in OBSERVABLES}
VERDICT_OK = 0.25                   # heuristic: identifiable when the 1-sigma standard error is below 25 % of the parameter's prior range (Assumed threshold)


def _rows():
    by_tag = {}
    for row in pt.build_table():
        if row["overridable_via"] == pt.VIA_ENGINE and row["tag"] in {p[2] for p in PARAMETERS} and row["range_low"] not in (None, "Missing"):
            by_tag[row["tag"]] = row
    return by_tag


def parameter_specs():
    """[{name, engine_key, tag, nominal, low, high}] from the parameter table (the repo's own values and ranges; nothing copied)."""
    rows = _rows()
    out = []
    for name, key, tag in PARAMETERS:
        r = rows[tag]
        out.append({"name": name, "engine_key": key, "tag": tag, "nominal": float(r["value"]), "low": float(r["range_low"]), "high": float(r["range_high"])})
    return out


def _constant_input(value):
    def fn(get_input):
        return {"value": value, "status": ps.STATUS_ASSUMED, "inputs": [], "validation_basis": ps.VALIDATION_NA, "confidence_note": "calibration run (synthetic twin experiment)"}
    return fn


def forward(params, n_cycles=N_CYCLES):
    """{observable: value} from the unchanged engine for {parameter name: value} (missing names keep the engine default). Offline: in-memory store, no database or network."""
    import sys
    import os
    tests_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests")
    if tests_dir not in sys.path:
        sys.path.insert(0, tests_dir)
    from _fakes import FakeSupabase, patched_supabase
    from . import cycle_clock
    from . import tab1_integration as t1
    keys = {name: key for name, key, _ in PARAMETERS}
    unknown = set(params) - set(keys)
    if unknown:
        raise KeyError(f"unknown calibration parameter(s): {sorted(unknown)}")
    ov = {("GA-001-INPUT", keys[n]): _constant_input(float(v)) for n, v in params.items()}
    cycle_clock.set_elapsed_hours(None)
    with patched_supabase(FakeSupabase()):
        snap = t1.build_live_snapshot(n_cycles=n_cycles, overrides=ov or None)[0]
    out = snap[("GA-001", "Outputs")]["value"]
    return {name: float(out[name]) for name in OBSERVABLE_NAMES}


def _vector(d, names):
    return np.array([d[n] for n in names], float)


def _analyse(J, sig, specs):
    """Scaled-Jacobian diagnostics. J: (n_obs, n_par) sensitivities d obs / d param; sig: (n_obs,). Returns the dict shared by jacobian_report and fit."""
    Jw = J / sig[:, None]
    info = Jw.T @ Jw
    sv = np.linalg.svd(Jw, compute_uv=False)
    cond = float(sv[0] / sv[-1]) if sv[-1] > 0 else float("inf")
    cov = np.linalg.pinv(info) if np.linalg.matrix_rank(info) == info.shape[0] else None
    names = [s["name"] for s in specs]
    rng = np.array([s["high"] - s["low"] for s in specs], float)
    res = {"singular_values": sv.tolist(), "condition_number": cond, "rank": int(np.linalg.matrix_rank(Jw)), "n_parameters": len(specs), "parameters": {}, "correlation": None}
    if cov is not None:
        se = np.sqrt(np.diag(cov))
        d = np.sqrt(np.diag(cov))
        corr = cov / np.outer(d, d)
        res["correlation"] = {a: {b: float(corr[i, j]) for j, b in enumerate(names)} for i, a in enumerate(names)}
        for i, n in enumerate(names):
            frac = float(se[i] / rng[i])
            res["parameters"][n] = {"standard_error": float(se[i]), "se_over_prior_range": frac, "verdict": "identifiable" if frac < VERDICT_OK else "weakly identifiable"}
    else:
        for n in names:
            res["parameters"][n] = {"standard_error": float("inf"), "se_over_prior_range": float("inf"), "verdict": "not identifiable (information matrix is singular)"}
    return res


def _jacobian(point, specs, observables, rel_step=1e-3):
    names = [s["name"] for s in specs]
    f0 = _vector(forward(point), observables)
    J = np.zeros((len(observables), len(specs)))
    for j, s in enumerate(specs):
        h = rel_step * (s["high"] - s["low"])
        p = dict(point)
        p[s["name"]] = point[s["name"]] + h
        J[:, j] = (_vector(forward(p), observables) - f0) / h
    return f0, J


def jacobian_report(point=None, observables=OBSERVABLE_NAMES, sigma=None):
    """Identifiability at `point` (default the engine's nominal values) with no data: what the observables CAN constrain given their assumed noise."""
    specs = parameter_specs()
    pt0 = {s["name"]: s["nominal"] for s in specs} if point is None else dict(point)
    sig = np.array([(sigma or SIGMA)[o] for o in observables], float)
    f0, J = _jacobian(pt0, specs, observables)
    rep = _analyse(J, sig, specs)
    rep.update({"point": pt0, "observables": list(observables), "jacobian": J.tolist(), "model_at_point": f0.tolist(), "status": STATUS})
    return rep


def fit(measured, sigma=None, start=None, observables=OBSERVABLE_NAMES, max_nfev=40):
    """Bounded least squares of the four parameters to `measured` ({observable: value}). Returns the estimate, the residuals, the covariance diagnostics (as jacobian_report) and the cost."""
    specs = parameter_specs()
    names = [s["name"] for s in specs]
    lo = np.array([s["low"] for s in specs]); hi = np.array([s["high"] for s in specs])
    x0 = np.array([(start or {}).get(s["name"], s["nominal"]) for s in specs], float)
    sig = np.array([(sigma or SIGMA)[o] for o in observables], float)
    y = _vector(measured, observables)
    scale = hi - lo

    def resid(x):
        return (_vector(forward(dict(zip(names, x))), observables) - y) / sig

    sol = least_squares(resid, x0, bounds=(lo, hi), x_scale=scale, diff_step=1e-3, max_nfev=max_nfev)
    est = dict(zip(names, sol.x.tolist()))
    f_hat, J = _jacobian(est, specs, observables)
    rep = _analyse(J, sig, specs)
    rep.update({"estimate": est, "start": dict(zip(names, x0.tolist())), "cost": float(sol.cost), "chi2": float(2 * sol.cost), "n_obs": len(observables), "n_evaluations": int(sol.nfev),
                "residuals_sigma": dict(zip(observables, ((f_hat - y) / sig).tolist())), "at_bound": [n for n, v, a, b in zip(names, sol.x, lo, hi) if min(v - a, b - v) < 1e-9 * (b - a)],
                "converged": bool(sol.success), "status": STATUS})
    return rep


def twin_experiment(truth, noise_seed=0, noise_scale=1.0, sigma=None, observables=OBSERVABLE_NAMES, start=None, max_nfev=40):
    """Synthesise measurements at `truth` ({parameter: value}) with Gaussian noise (seeded; noise_scale 0 = noise-free), fit from the nominal (or `start`), report the recovery.
    The measurements are the engine's own output: this proves the loop, not the physics."""
    specs = parameter_specs()
    sg = {o: (sigma or SIGMA)[o] for o in observables}
    clean = forward({s["name"]: truth.get(s["name"], s["nominal"]) for s in specs})
    rng = np.random.default_rng(noise_seed)
    measured = {o: clean[o] + noise_scale * sg[o] * float(rng.standard_normal()) for o in observables}
    rep = fit(measured, sigma=sg, start=start, observables=observables, max_nfev=max_nfev)
    full_truth = {s["name"]: truth.get(s["name"], s["nominal"]) for s in specs}
    rep["truth"] = full_truth
    rep["error"] = {n: rep["estimate"][n] - full_truth[n] for n in full_truth}
    rep["error_in_sigma"] = {n: (rep["error"][n] / rep["parameters"][n]["standard_error"] if rep["parameters"][n]["standard_error"] not in (0.0, float("inf")) else float("nan")) for n in full_truth}
    rep["measured"] = measured
    return rep


def leave_one_observable_out(report=None):
    """What each instrument is worth: for every observable, the identifiability when ONLY that observable is dropped (no new engine runs: the rows of the stored Jacobian are reused).
    Returns {removed observable: {parameter: se_over_prior_range, ...,'condition_number'}}, plus 'none removed' for reference. A per-instrument value table for the data request to DOK-ING;
    it holds for THIS model at THIS point with the ASSUMED noise levels."""
    rep = report or jacobian_report()
    specs = parameter_specs()
    J = np.array(rep["jacobian"], float)
    obs = rep["observables"]
    out = {}
    for label, keep in [("none removed", list(range(len(obs))))] + [(o, [i for i in range(len(obs)) if i != k]) for k, o in enumerate(obs)]:
        sig = np.array([SIGMA[obs[i]] for i in keep], float)
        a = _analyse(J[keep, :], sig, specs)
        out[label] = {**{n: p["se_over_prior_range"] for n, p in a["parameters"].items()}, "condition_number": a["condition_number"], "rank": a["rank"]}
    return out
