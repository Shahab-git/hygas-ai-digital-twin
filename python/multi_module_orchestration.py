"""
Multi-module orchestration v1.

DISTINCT FROM multi_agent_negotiation.py, deliberately, per the brief:
that module handles competing hypothetical PLANTS negotiating over one
shared, scarce resource (grid export capacity) — a division-of-scarcity
problem. This module coordinates operational state ACROSS MODULES OF THE
SAME PLANT — distributing one shared H2 output TARGET across cooperating
parallel WGS trains to hit it at minimum total feed throughput, and
handling one module going offline by re-optimizing the rest. Different
problem shape: negotiation there divides a fixed scarce pool among
competing claims; orchestration here finds the cheapest way to jointly
meet one shared goal. This module reuses multi_agent_negotiation.py's
illustrative-multi-instance PATTERN (2-3 hypothetical variants, honestly
labeled), not its allocation logic.

HONEST SCOPING, same spirit as multi_agent_negotiation.py: this repo
represents exactly one real plant. The 3 "modules" below are
ILLUSTRATIVE hypothetical parallel WGS trains — not real separate plant
modules, and there's no real per-module capacity spec in this project.
Built on kinetics.py's real physics, not invented numbers.

Module model: each module is a WGS train identical in TECHNOLOGY to the
real plant's (the same kinetics.py hts_conversion/lts_conversion
functions), differentiated by HTS operating temperature — 335C / 350C /
365C, illustrative variants within kinetics.py's own realistic 300-400C
bound — which genuinely changes each module's conversion-vs-load curve
via kinetics.py's real Arrhenius/equilibrium behavior (confirmed
numerically before writing this: at every GHSV tested, 365C module
converts more than 350C converts more than 335C — not an invented
number). A module's real k0_scale ("activity factor", reusing
kinetics.py's own parameter and predictive_maintenance.py's own
healthy/watch/flag thresholds) further scales its achievable efficiency
— a module whose activity factor falls to predictive_maintenance's FLAG
territory (<0.85) is automatically excluded from the allocation pool, no
separate threshold redefined here.

"Throughput" and "H2 output" are expressed directly in GHSV-equivalent
relative units (output = GHSV x overall WGS conversion at that GHSV) —
stated explicitly as a relative/illustrative basis, not tied to a real
kg/h mass balance, since no real per-module capacity spec exists in this
project (unlike circularity.py's single-train MSW feed rate, which is a
real, sourced number for the ONE real train this repo actually models).

Coordination problem: given a target total H2 output, allocate GHSV
(load) across the AVAILABLE (non-offline) modules to hit that target at
MINIMUM total throughput — i.e. prefer higher-conversion-efficiency
modules and loads, not an even split. Solved with scipy.optimize.minimize
(SLSQP, the one scipy method that handles inequality constraints
directly) — chosen over a hand-rolled water-filling algorithm because
each module's own efficiency-vs-load curve has diminishing returns
(confirmed numerically), so the true optimum isn't a simple greedy
merit-order fill the way multi_agent_negotiation.py's flat-efficiency
problem was; a general constrained solver is the simpler correct choice
here, not the more complex one.
"""
from scipy.optimize import minimize

from . import kinetics, predictive_maintenance

GHSV_MAX = 4000.0  # matches kinetics.py's own realistic bound, used elsewhere in this repo's sliders

# Illustrative hypothetical modules — NOT real separate plant modules.
# T_hts_C variants are within kinetics.py's own 300-400C realistic range.
DEFAULT_MODULES = [
    {"name": "Module A (baseline, 350°C)", "T_hts_C": 350.0, "ghsv_max": GHSV_MAX, "activity_factor": 1.0},
    {"name": "Module B (higher-temp variant, 365°C)", "T_hts_C": 365.0, "ghsv_max": GHSV_MAX, "activity_factor": 1.0},
    {"name": "Module C (lower-temp variant, 335°C)", "T_hts_C": 335.0, "ghsv_max": GHSV_MAX, "activity_factor": 1.0},
]


def module_status(activity_factor):
    """Reuses predictive_maintenance.py's own thresholds — not redefined here."""
    if activity_factor > predictive_maintenance.HEALTHY_THRESHOLD:
        return "healthy"
    if activity_factor >= predictive_maintenance.WATCH_THRESHOLD:
        return "watch"
    return "flag for maintenance"


def _module_output(ghsv, T_hts_C, activity_factor, T_lts_C=220.0, lts_ghsv=2000.0):
    """H2 output at this module's chosen GHSV: throughput (=GHSV) x overall
    WGS conversion at that GHSV — real kinetics.py physics, chained HTS
    then LTS the same way the rest of this app does it."""
    if ghsv <= 0:
        return 0.0
    X_hts = kinetics.hts_conversion(T_K=T_hts_C + 273.15, GHSV=ghsv, k0_scale=activity_factor)
    y_after_hts = 0.28 * (1 - X_hts)
    X_lts = kinetics.lts_conversion(
        T_K=T_lts_C + 273.15, GHSV=lts_ghsv, y_CO_in=y_after_hts, k0_scale=activity_factor,
    )
    overall = 1 - (1 - X_hts) * (1 - X_lts)
    return ghsv * overall


def orchestrate(target_output, modules=None, offline_module_names=None):
    """target_output: desired total H2 output (GHSV-equivalent relative
    units — see module docstring).
    modules: optional list of module dicts (defaults to DEFAULT_MODULES).
    offline_module_names: optional list of module names to force offline
    (simulates scheduled maintenance) — on top of the automatic
    activity-factor-based exclusion.

    Returns a dict: feasible (bool), target_output, total_output,
    total_throughput, modules (per-module result: name, status,
    available, ghsv, output, share_of_target), and reason (set when
    infeasible)."""
    modules = modules if modules is not None else DEFAULT_MODULES
    offline_module_names = set(offline_module_names or [])

    module_info = []
    for m in modules:
        status = module_status(m["activity_factor"])
        forced_offline = m["name"] in offline_module_names
        available = status != "flag for maintenance" and not forced_offline
        module_info.append({**m, "status": status, "forced_offline": forced_offline, "available": available})

    available_modules = [m for m in module_info if m["available"]]

    if not available_modules:
        return {
            "feasible": False, "target_output": target_output, "total_output": 0.0,
            "total_throughput": 0.0, "modules": module_info,
            "reason": "No modules available — all are offline (forced or flagged for maintenance).",
        }

    max_achievable = sum(_module_output(m["ghsv_max"], m["T_hts_C"], m["activity_factor"]) for m in available_modules)
    if max_achievable < target_output:
        for m in module_info:
            m["ghsv"] = m["ghsv_max"] if m["available"] else 0.0
            m["output"] = _module_output(m["ghsv"], m["T_hts_C"], m["activity_factor"]) if m["available"] else 0.0
        return {
            "feasible": False, "target_output": target_output, "total_output": max_achievable,
            "total_throughput": sum(m["ghsv"] for m in module_info), "modules": module_info,
            "reason": (
                f"Target ({target_output:.0f}) exceeds the maximum combined output achievable with the "
                f"currently available modules ({max_achievable:.0f}, all at full load). Not achievable "
                f"until more capacity comes online — reported honestly, not silently clipped to a "
                f"plausible-looking smaller number."
            ),
        }

    n = len(available_modules)

    def neg_output_sum_minus_throughput(x):
        # scipy minimizes; we minimize total throughput directly and use a
        # constraint (not a penalty) for the output target — see below.
        return sum(x)

    def output_constraint(x):
        total = sum(
            _module_output(ghsv, m["T_hts_C"], m["activity_factor"])
            for ghsv, m in zip(x, available_modules)
        )
        return total - target_output  # must be >= 0

    bounds = [(0.0, m["ghsv_max"]) for m in available_modules]
    x0 = [target_output / n] * n  # even split as the starting guess only — not the answer
    x0 = [min(v, b[1]) for v, b in zip(x0, bounds)]

    result = minimize(
        neg_output_sum_minus_throughput, x0=x0, method="SLSQP", bounds=bounds,
        constraints=[{"type": "ineq", "fun": output_constraint}],
    )

    ghsv_by_name = dict(zip([m["name"] for m in available_modules], result.x))
    total_output = 0.0
    total_throughput = 0.0
    for m in module_info:
        ghsv = float(ghsv_by_name.get(m["name"], 0.0))
        output = _module_output(ghsv, m["T_hts_C"], m["activity_factor"]) if m["available"] else 0.0
        m["ghsv"] = ghsv
        m["output"] = output
        m["share_of_target"] = output / target_output if target_output > 0 else 0.0
        total_output += output
        total_throughput += ghsv

    return {
        "feasible": True, "target_output": target_output, "total_output": total_output,
        "total_throughput": total_throughput, "modules": module_info,
        "converged": bool(result.success), "n_evaluations": int(result.nfev),
    }


if __name__ == "__main__":
    print("=== All 3 modules available, target=2500 ===")
    r = orchestrate(target_output=2500.0)
    print(f"feasible={r['feasible']}  total_output={r['total_output']:.1f}  "
          f"total_throughput={r['total_throughput']:.1f}")
    for m in r["modules"]:
        print(f"  {m['name']}: GHSV={m['ghsv']:.0f}  output={m['output']:.1f}  "
              f"({m['share_of_target']*100:.1f}% of target)")

    print("\n=== Module B (365°C, the most efficient) taken offline, same target=2500 ===")
    r2 = orchestrate(target_output=2500.0, offline_module_names=["Module B (higher-temp variant, 365°C)"])
    print(f"feasible={r2['feasible']}  total_output={r2['total_output']:.1f}  "
          f"total_throughput={r2['total_throughput']:.1f}")
    for m in r2["modules"]:
        avail = "available" if m["available"] else "OFFLINE"
        print(f"  {m['name']} [{avail}]: GHSV={m['ghsv']:.0f}  output={m['output']:.1f}")

    print("\n=== Infeasible case: only 1 module available, target too high ===")
    r3 = orchestrate(
        target_output=9000.0,
        offline_module_names=["Module B (higher-temp variant, 365°C)", "Module C (lower-temp variant, 335°C)"],
    )
    print(f"feasible={r3['feasible']}")
    print(f"reason: {r3.get('reason')}")
