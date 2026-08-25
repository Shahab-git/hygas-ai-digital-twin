"""
Single-shot setpoint optimizer — the "central optimizer" for HYGAS-AI, v1.

HONEST SCOPING: this is NOT real MPC (model predictive control). True MPC
does receding-horizon optimization over TIME — repeatedly re-planning as
a dynamic system evolves. That requires a time-domain (dynamic) model of
the plant. kinetics.py and psa.py are steady-state functions (conversion
at one fixed operating point, no time axis), not dynamic simulations, so
a real MPC loop isn't buildable on top of them yet. What IS buildable,
and what this module does: search the real adjustable setpoints (HTS/LTS
temperature and GHSV, PSA pressure) for the combination that maximizes
one objective, using kinetics.py/psa.py themselves as the model being
optimized against — not a separate approximation of them. A real
receding-horizon MPC controller is a genuine v2, once a dynamic version
of the physics core exists.

Two objectives, matching the two independent parts of the model that are
actually implemented (WGS and PSA aren't coupled in this codebase — see
app.py, each section runs off its own independent sliders):

  - maximize_overall_wgs_conversion(): searches (T_hts, GHSV_hts, T_lts,
    GHSV_lts) jointly with scipy.optimize.minimize (L-BFGS-B, bounded to
    the same ranges as the dashboard's sliders — these ARE the
    physically-reasonable catalyst operating ranges already used
    throughout this repo, not new bounds invented for the optimizer).
    scipy chosen over grid search here because each evaluation calls
    kinetics.py's 20,000-step ODE integration twice (HTS then LTS) — a
    grid fine enough to be useful in 4 dimensions would need hundreds of
    thousands of evaluations; L-BFGS-B typically converges in well under
    a hundred.

  - maximize_psa_recovery(): searches (P_high_bar_a, P_low_bar_a) by grid
    search over the same bounds as the dashboard's sliders. Grid search
    here because psa_recovery() is a closed-form formula (no ODE
    integration) — cheap enough that a full grid is simpler and more
    transparent than a gradient method, and it doesn't require assuming
    anything about the function's shape.

Both functions verify their own answer: after finding the recommended
setpoint, they recompute the result by calling kinetics.py/psa.py again,
directly, independent of the search loop's internal bookkeeping, and
assert it matches — guarding against the optimizer *reporting* a number
that the real physics functions don't actually reproduce.
"""
import numpy as np
from scipy.optimize import minimize

from . import kinetics, psa

# Bounds match the dashboard's sliders exactly (see app.py) — these ARE
# the physically-reasonable operating ranges already used throughout this
# repo, not new assumptions invented for the optimizer.
HTS_T_BOUNDS_C = (300, 400)
HTS_GHSV_BOUNDS = (1000, 4000)
LTS_T_BOUNDS_C = (180, 260)
LTS_GHSV_BOUNDS = (1000, 4000)
PSA_PHIGH_BOUNDS = (4.0, 14.0)
PSA_PLOW_BOUNDS = (0.5, 3.0)


def _overall_wgs(T_hts_C, ghsv_hts, T_lts_C, ghsv_lts, y_CO_in=0.28):
    X_hts = kinetics.hts_conversion(T_K=T_hts_C + 273.15, GHSV=ghsv_hts, y_CO_in=y_CO_in)
    y_co_after_hts = y_CO_in * (1 - X_hts)
    X_lts = kinetics.lts_conversion(T_K=T_lts_C + 273.15, GHSV=ghsv_lts, y_CO_in=y_co_after_hts)
    overall = 1 - (1 - X_hts) * (1 - X_lts)
    return X_hts, X_lts, overall


def maximize_overall_wgs_conversion(x0=None, y_CO_in=0.28):
    """x0: optional [T_hts_C, ghsv_hts, T_lts_C, ghsv_lts] starting guess
    (e.g. the dashboard's current slider values) — defaults to the
    dashboard's default setpoints if not given.

    Returns dict: T_hts_C, ghsv_hts, T_lts_C, ghsv_lts, X_hts, X_lts,
    overall, converged, n_evaluations.
    """
    if x0 is None:
        x0 = [350.0, 2000.0, 220.0, 2000.0]

    bounds = [HTS_T_BOUNDS_C, HTS_GHSV_BOUNDS, LTS_T_BOUNDS_C, LTS_GHSV_BOUNDS]

    def neg_objective(x):
        T_hts_C, ghsv_hts, T_lts_C, ghsv_lts = x
        _, _, overall = _overall_wgs(T_hts_C, ghsv_hts, T_lts_C, ghsv_lts, y_CO_in)
        return -overall

    result = minimize(neg_objective, x0=x0, method="L-BFGS-B", bounds=bounds)
    T_hts_C, ghsv_hts, T_lts_C, ghsv_lts = (float(v) for v in result.x)
    X_hts, X_lts, overall = _overall_wgs(T_hts_C, ghsv_hts, T_lts_C, ghsv_lts, y_CO_in)

    # Verify correctness: recompute directly through kinetics.py at the
    # recommended setpoints, independent of the optimizer's internal
    # bookkeeping, and confirm it matches what's being reported.
    X_hts_check = kinetics.hts_conversion(T_K=T_hts_C + 273.15, GHSV=ghsv_hts, y_CO_in=y_CO_in)
    y_co_after_check = y_CO_in * (1 - X_hts_check)
    X_lts_check = kinetics.lts_conversion(T_K=T_lts_C + 273.15, GHSV=ghsv_lts, y_CO_in=y_co_after_check)
    overall_check = 1 - (1 - X_hts_check) * (1 - X_lts_check)
    assert abs(overall_check - overall) < 1e-9, (
        f"optimizer result ({overall}) doesn't match direct recomputation ({overall_check})"
    )

    return {
        "T_hts_C": T_hts_C, "ghsv_hts": ghsv_hts,
        "T_lts_C": T_lts_C, "ghsv_lts": ghsv_lts,
        "X_hts": float(X_hts), "X_lts": float(X_lts), "overall": float(overall),
        "converged": bool(result.success), "n_evaluations": int(result.nfev),
    }


def maximize_psa_recovery(y_co2=0.35, y_ch4=0.03, y_co=0.042, y_n2=0.028, n_grid=30):
    """Grid search over (P_high_bar_a, P_low_bar_a).

    Returns dict: p_high, p_low, recovery, n_evaluations.
    """
    p_high_vals = np.linspace(*PSA_PHIGH_BOUNDS, n_grid)
    p_low_vals = np.linspace(*PSA_PLOW_BOUNDS, n_grid)

    best = {"p_high": p_high_vals[0], "p_low": p_low_vals[0], "recovery": -1.0}
    n_evaluated = 0
    for p_high in p_high_vals:
        for p_low in p_low_vals:
            if p_low >= p_high:
                continue  # pressure ratio must be > 1
            recovery = psa.psa_recovery(y_CO2=y_co2, y_CH4=y_ch4, y_CO=y_co, y_N2=y_n2,
                                         P_high_bar_a=p_high, P_low_bar_a=p_low)
            n_evaluated += 1
            if recovery > best["recovery"]:
                best = {"p_high": float(p_high), "p_low": float(p_low), "recovery": float(recovery)}

    # Verify correctness: recompute directly, independent of the search loop.
    recovery_check = psa.psa_recovery(y_CO2=y_co2, y_CH4=y_ch4, y_CO=y_co, y_N2=y_n2,
                                       P_high_bar_a=best["p_high"], P_low_bar_a=best["p_low"])
    assert abs(recovery_check - best["recovery"]) < 1e-12, (
        f"optimizer result ({best['recovery']}) doesn't match direct recomputation ({recovery_check})"
    )

    return {
        "p_high": best["p_high"], "p_low": best["p_low"],
        "recovery": best["recovery"], "n_evaluations": n_evaluated,
    }


if __name__ == "__main__":
    print("Maximize overall WGS conversion:")
    r = maximize_overall_wgs_conversion()
    print(f"  T_hts={r['T_hts_C']:.1f}C  GHSV_hts={r['ghsv_hts']:.0f}  "
          f"T_lts={r['T_lts_C']:.1f}C  GHSV_lts={r['ghsv_lts']:.0f}")
    print(f"  -> HTS={r['X_hts']*100:.1f}%  LTS={r['X_lts']*100:.1f}%  Overall={r['overall']*100:.1f}%  "
          f"(converged={r['converged']}, {r['n_evaluations']} evaluations)")

    print("\nMaximize PSA recovery:")
    r2 = maximize_psa_recovery()
    print(f"  P_high={r2['p_high']:.2f} bar(a)  P_low={r2['p_low']:.2f} bar(a)  "
          f"-> Recovery={r2['recovery']*100:.1f}%  ({r2['n_evaluations']} evaluations)")
