"""
Transient what-if demo (dynamics layer v0) -- READ-ONLY, no database, no network.

Runs three scenarios for 2 h at 60 s steps (each step at t = 10 min):
  1. feed rate +10 %
  2. equivalence ratio ER 0.25 -> 0.30
  3. gasifier temperature setpoint 900 -> 930 degC
writes one CSV per scenario to outputs/transient/ (and one PNG per scenario if matplotlib is
ALREADY installed -- it is not a project requirement), and prints, per scenario, the time to
63 % and 95 % of the final change of GA-001 flow, H2 production and EU-008 demand together
with the final steady-state value (the steady-state engine at the final inputs).

    python scripts/run_transient_demo.py            (from the repo root)

Time constants are ASSUMED, not validated against plant data -- see docs/dynamics_v0.md.
"""
import csv
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from python import confirmation_loop, vendor_log  # noqa: E402

# Nothing in this script may touch a database: any accidental access fails loudly here instead of
# silently reading or writing. HYGAS_ALLOW_DB_WRITES must also be unset.
def _no_database(*args, **kwargs):
    raise RuntimeError("run_transient_demo.py is database-free; a database access was attempted")


vendor_log._get_client = _no_database
confirmation_loop._get_client = _no_database
if vendor_log.db_writes_allowed():
    sys.exit("Refusing to run: HYGAS_ALLOW_DB_WRITES=1 is set. This demo never writes; unset it.")

from python import dynamics as dy  # noqa: E402
from python import fe_feed_handling as fe  # noqa: E402
from python import plant_status as ps  # noqa: E402
from python import tab1_integration  # noqa: E402

BANNER = "WHAT-IF SIMULATION. Time constants are Assumed, not validated against plant data."
OUT_DIR = os.path.join(ROOT, "outputs", "transient")
STEP_T_S = 600.0
DT_S = 60.0
DURATION_S = 7200.0

SCENARIOS = [
    {"name": "feed_plus_10pct", "title": "Feed rate +10 % at t = 10 min",
     "steps": [{"t_s": STEP_T_S, "feed_rel": 0.10}],
     "final": {"feed_kg_h": fe.FE001_DEFAULT_DELIVERY_RATE_KG_H * 1.10}},
    {"name": "er_025_to_030", "title": "ER 0.25 -> 0.30 at t = 10 min",
     "steps": [{"t_s": STEP_T_S, "ER": 0.30}],
     "final": {"ER": 0.30}},
    {"name": "T_900_to_930", "title": "Gasifier T setpoint 900 -> 930 degC at t = 10 min",
     "steps": [{"t_s": 0, "T_setpoint_C": 900.0}, {"t_s": STEP_T_S, "T_setpoint_C": 930.0}],
     "final": {"T_setpoint_C": 930.0}, "initial": {"T_setpoint_C": 900.0}},
]

QUANTITIES = [("ga001_dry_flow_nm3_h", "GA-001 dry flow", "Nm3/h"),
              ("h2_production_kg_h", "H2 production", "kg/h"),
              ("eu008_demand_kw", "EU-008 cooling demand", "kW")]


def _override(value):
    return lambda get_input: {"value": value, "status": ps.STATUS_ASSUMED, "validation_basis": ps.VALIDATION_NA,
                              "confidence_note": "demo steady-state reference input"}


def steady_state(inputs):
    """The steady-state engine at `inputs` (converged: 30 hourly cycles). Independent of the transient layer."""
    overrides = {}
    if "feed_kg_h" in inputs:
        overrides[("FE-001-INPUT", "msw_delivery_rate_kg_h")] = _override(inputs["feed_kg_h"])
    if "ER" in inputs:
        overrides[("GA-001-INPUT", "equivalence_ratio")] = _override(inputs["ER"])
    if "T_setpoint_C" in inputs:
        overrides[("GA-001-INPUT", "operating_temperature_C")] = _override(inputs["T_setpoint_C"])
    snap, _state, _engine = tab1_integration.build_live_snapshot(n_cycles=30, overrides=overrides or None)
    return {"ga001_dry_flow_nm3_h": snap[("GA-001", "Outputs")]["value"]["dry_flow_nm3_h"],
            "h2_production_kg_h": snap[("HB-012", "Compressor")]["value"]["h2_kg_h"],
            "eu008_demand_kw": snap[("EU-008", "CoolingSupply")]["value"]["demand_kw"]}


def time_to_fraction(series, column, x0, x_final, fraction, t_step):
    """Seconds after the step until `column` has covered `fraction` of (x_final - x0); linearly interpolated.
    None if never reached or the change is zero."""
    if x_final == x0:
        return None
    previous = None
    for row in series:
        if row["t_s"] < t_step:
            continue
        f = (row[column] - x0) / (x_final - x0)
        if f >= fraction:
            if previous is None:
                return row["t_s"] - t_step
            (t_a, f_a) = previous
            return t_a + (fraction - f_a) / (f - f_a) * (row["t_s"] - t_a) - t_step
        previous = (row["t_s"], f)
    return None


def write_csv(path, result):
    columns = list(result.series[0])
    with open(path, "w", newline="", encoding="utf-8") as handle:
        handle.write(f"# {BANNER}\n")
        for a in result.assumptions:
            handle.write(f"# assumed tau {a['name']} = {a['value_s']:g} s (range {a['range_s'][0]:g}-{a['range_s'][1]:g} s, {a['status']})\n")
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(result.series)


def write_png(path, result, title):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False
    t = [r["t_s"] / 60.0 for r in result.series]
    fig, axes = plt.subplots(2, 2, figsize=(11, 7), sharex=True)
    fig.suptitle(f"{title}\n{BANNER}", fontsize=10)
    axes[0][0].plot(t, result.column("ga001_dry_flow_nm3_h"), label="GA-001 dry flow (lagged)")
    axes[0][0].plot(t, result.column("ga001_dry_flow_target_nm3_h"), "--", label="steady-state target")
    axes[0][0].set_ylabel("Nm3/h")
    axes[0][1].plot(t, result.column("h2_production_kg_h"), color="tab:green")
    axes[0][1].set_ylabel("H2 production, kg/h")
    axes[1][0].plot(t, result.column("eu008_demand_kw"), color="tab:red")
    axes[1][0].set_ylabel("EU-008 demand, kW")
    axes[1][1].plot(t, result.column("T_gasifier_C"), label="T_gasifier")
    axes[1][1].plot(t, result.column("T_setpoint_C"), "--", label="setpoint")
    axes[1][1].set_ylabel("degC")
    for ax in axes[1]:
        ax.set_xlabel("time, min")
    for ax in (axes[0][0], axes[1][1]):
        ax.legend(fontsize=8)
    for ax in axes.flat:
        ax.axvline(STEP_T_S / 60.0, color="grey", lw=0.8, ls=":")
        ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return True


def main():
    print("=" * 100)
    print(BANNER)
    print("=" * 100)
    os.makedirs(OUT_DIR, exist_ok=True)
    for scenario in SCENARIOS:
        result = dy.run_transient(scenario["steps"], dt_s=DT_S, duration_s=DURATION_S)
        result.verify_honesty()
        csv_path = os.path.join(OUT_DIR, f"{scenario['name']}.csv")
        write_csv(csv_path, result)
        png_path = os.path.join(OUT_DIR, f"{scenario['name']}.png")
        png = write_png(png_path, result, scenario["title"])

        before = next(r for r in result.series if r["t_s"] == STEP_T_S)          # end of the sub-step before the step acts
        ss_final = steady_state(scenario["final"])
        print(f"\n--- {scenario['title']}  (dt = {DT_S:g} s, {DURATION_S / 3600:g} h) ---")
        print("assumed time constants: " + ", ".join(f"{a['name']} = {a['value_s']:g} s" for a in result.assumptions))
        print(f"{'quantity':24s} {'before step':>12s} {'final steady':>13s} {'change':>10s} {'t63 [s]':>9s} {'t95 [s]':>9s}")
        for column, label, unit in QUANTITIES:
            x0, xf = before[column], ss_final[column]
            change = xf - x0
            t63 = time_to_fraction(result.series, column, x0, xf, 0.632, STEP_T_S)
            t95 = time_to_fraction(result.series, column, x0, xf, 0.95, STEP_T_S)
            note = "" if abs(change) > 1e-4 * abs(x0) else "   (change < 0.01 % -- times not meaningful)"
            fmt = lambda v: "      n/a" if v is None else f"{v:9.0f}"
            print(f"{label + ' [' + unit + ']':24s} {x0:12.4f} {xf:13.4f} {change:+10.4f} {fmt(t63)} {fmt(t95)}{note}")
        print(f"CSV: {os.path.relpath(csv_path, ROOT)}" + (f" | PNG: {os.path.relpath(png_path, ROOT)}" if png else " | PNG: skipped (matplotlib not installed)"))
    print("\n" + BANNER)


if __name__ == "__main__":
    main()
