"""
Transient what-if demo (dynamics layer v0.1) -- READ-ONLY, no database, no network.

Runs three scenarios for 2 h at 60 s steps (each step at t = 10 min):
  1. feed rate +10 %
  2. equivalence ratio ER 0.25 -> 0.30
  3. gasifier temperature setpoint 900 -> 930 degC
writes one CSV per scenario to outputs/transient/ (and one PNG per scenario if matplotlib is
ALREADY installed -- it is not a project requirement), prints, per scenario, the time to
63 % and 95 % of the final change of GA-001 flow, H2 production and EU-008 demand together
with the final steady-state value (the steady-state engine at the final inputs), and writes ONE
self-contained results page, outputs/transient/index.html (no external scripts, fonts or
images; the charts are embedded as base64 PNGs). Double-click that file to read the results.

    python scripts/run_transient_demo.py            (from the repo root)

Time constants are ASSUMED, not validated against plant data -- see docs/dynamics_v0.md.
"""
import base64
import csv
import html
import io
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


def render_png(result, title):
    """PNG bytes, or None if matplotlib is not installed."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None
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
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=100)
    plt.close(fig)
    return buffer.getvalue()


def sign_changes(values):
    return sum(1 for i in range(2, len(values)) if (values[i] - values[i - 1]) * (values[i - 1] - values[i - 2]) < 0)


def findings_html(runs, quiet):
    """The three findings, with their numbers taken from THIS run (not typed in)."""
    er = runs["er_025_to_030"]
    feed = runs["feed_plus_10pct"]
    temp = runs["T_900_to_930"]
    flow0, flow_f = er["before"]["ga001_dry_flow_nm3_h"], er["steady"]["ga001_dry_flow_nm3_h"]
    peak_er = max(r["ga001_dry_flow_nm3_h"] for r in er["result"].series if r["t_s"] >= STEP_T_S)
    target_peak = max(r["ga001_dry_flow_target_nm3_h"] for r in er["result"].series if r["t_s"] >= STEP_T_S)
    levels = quiet.column("hb013_storage_kg")
    out = quiet.column("hb013_outflow_kg_h")[1:]
    t_flow = temp["rows"]["ga001_dry_flow_nm3_h"]
    t_h2 = temp["rows"]["h2_production_kg_h"]
    paragraphs = [
        ("Recycle loop shapes the response.",
         f"GA-001 reads the PSA tail gas that HB-009 recycles to it. In v0.1 that read is a {next(x for x in er['result'].assumptions if x['name'] == 'tau_rec')['value_s']:g} s transport "
         f"delay (tau_rec, Assumed) instead of the engine's one-cycle lag. The steady-state target still jumps before it settles: in the ER step it "
         f"peaks at {100 * (target_peak - flow0) / (flow_f - flow0):.0f} % of its final change, while the lagged flow peaks at "
         f"{100 * (peak_er - flow0) / (flow_f - flow0):.1f} %. The feed step is also slowed by one more per-cycle lag, the FE-005 to GA-001 "
         f"feed read, which is still one sub-step ({DT_S:g} s) long."),
        ("Hydrogen storage chatters without any disturbance.",
         f"In a quiet {len(levels) - 1}-step run at {DT_S:g} s with no scenario, HB-013's level changed direction {sign_changes(levels)} times "
         f"(level {min(levels):.3f}-{max(levels):.3f} kg, outflow {min(out):.1f}-{max(out):.1f} kg/h). Cause, established in separate trials that switched each part off (docs/dynamics_v0.md): HB-018 dispenses the whole previous-cycle stock each step, and EU-006's H2 budget is stored energy divided by dt, "
         f"so both swing when the stock is small. Not fixed in v0.1; treat HB-013, EU-010 and anything derived from them as non-physical in a transient."),
        ("Gasifier temperature barely moves the outputs.",
         f"GA-001 uses temperature only in the water-gas-shift equilibrium constant (no energy balance, carbon conversion fixed at 0.90, tar Missing). "
         f"For T 900 to 930 degC the dry flow changes {t_flow['change']:+.3f} Nm3/h ({100 * t_flow['change'] / t_flow['before']:+.2f} %) and H2 production "
         f"{t_h2['change']:+.4f} kg/h ({100 * t_h2['change'] / t_h2['before']:+.3f} %). The thermal lag is nearly decorative until that changes."),
    ]
    return "".join(f"<p><b>{html.escape(h)}</b> {html.escape(t)}</p>" for h, t in paragraphs)


def build_index_html(runs, quiet, taus_assumptions):
    def esc(x):
        return html.escape(str(x))

    css = ("body{font-family:Arial,Helvetica,sans-serif;max-width:1100px;margin:24px auto;padding:0 16px;color:#111;}"
           ".banner{background:#B91C1C;color:#fff;padding:12px 16px;font-weight:bold;border-radius:6px;}"
           "h1{font-size:1.5rem}h2{margin-top:32px;border-bottom:1px solid #ccc;padding-bottom:4px}"
           "table{border-collapse:collapse;margin:8px 0;font-size:0.9rem}th,td{border:1px solid #bbb;padding:4px 10px;text-align:right}"
           "th{background:#eee}td:first-child,th:first-child{text-align:left}"
           "td.l{text-align:left}img{max-width:100%;border:1px solid #ccc;margin:8px 0}small{color:#555}")
    parts = [f"<!doctype html><html><head><meta charset='utf-8'><title>Transient what-if results</title><style>{css}</style></head><body>",
             f"<div class='banner'>{esc(BANNER)}</div>",
             "<h1>Dynamics layer v0.1 -- transient what-if results</h1>",
             f"<p>Three scenarios, {DURATION_S / 3600:g} h at {DT_S:g} s steps, each step at t = {STEP_T_S / 60:g} min. "
             "Only T_gasifier, tau_conv and tau_gas have inertia (plus the tau_rec recycle delay and the EU-008 damping conversion); GC, HB, EU and SA are algebraic. "
             "Nothing here is Measured or Confirmed.</p>",
             "<h2>Findings</h2>", findings_html(runs, quiet),
             "<h2>Assumed time constants</h2><table><tr><th>name</th><th>value [s]</th><th>range [s]</th><th>status</th><th>question for DOK-ING</th></tr>"]
    for a in taus_assumptions:
        parts.append(f"<tr><td>{esc(a['name'])}</td><td>{a['value_s']:g}</td><td>{a['range_s'][0]:g} - {a['range_s'][1]:g}</td>"
                     f"<td>{esc(a['status'])}</td><td class='l'>{esc(a['question_for_doking'])}</td></tr>")
    parts.append("</table>")
    for scenario in SCENARIOS:
        run = runs[scenario["name"]]
        parts.append(f"<h2>{esc(scenario['title'])}</h2>")
        if run["png"]:
            parts.append(f"<img alt='{esc(scenario['title'])}' src='data:image/png;base64,{base64.b64encode(run['png']).decode('ascii')}'>")
        else:
            parts.append("<p><small>Chart skipped: matplotlib is not installed in this Python.</small></p>")
        parts.append("<table><tr><th>quantity</th><th>before step</th><th>final steady state</th><th>change</th><th>t63 [s]</th><th>t95 [s]</th></tr>")
        for column, label, unit in QUANTITIES:
            r = run["rows"][column]
            fmt = lambda v: "n/a" if v is None else f"{v:.0f}"
            note = "" if abs(r["change"]) > 1e-4 * abs(r["before"]) else " <small>(change &lt; 0.01 %: times not meaningful)</small>"
            parts.append(f"<tr><td>{esc(label)} [{esc(unit)}]{note}</td><td>{r['before']:.4f}</td><td>{r['final']:.4f}</td>"
                         f"<td>{r['change']:+.4f}</td><td>{fmt(r['t63'])}</td><td>{fmt(r['t95'])}</td></tr>")
        parts.append("</table>")
    parts.append(f"<p><small>{esc(BANNER)} Times are seconds after the step, measured against the steady-state engine at the final inputs.</small></p></body></html>")
    return "".join(parts)


def main():
    print("=" * 100)
    print(BANNER)
    print("=" * 100)
    os.makedirs(OUT_DIR, exist_ok=True)
    runs = {}
    assumptions = None
    for scenario in SCENARIOS:
        result = dy.run_transient(scenario["steps"], dt_s=DT_S, duration_s=DURATION_S)
        result.verify_honesty()
        assumptions = result.assumptions
        csv_path = os.path.join(OUT_DIR, f"{scenario['name']}.csv")
        write_csv(csv_path, result)
        png = render_png(result, scenario["title"])
        png_path = os.path.join(OUT_DIR, f"{scenario['name']}.png")
        if png:
            with open(png_path, "wb") as handle:
                handle.write(png)

        before = next(r for r in result.series if r["t_s"] == STEP_T_S)          # end of the sub-step before the step acts
        ss_final = steady_state(scenario["final"])
        rows = {}
        print(f"\n--- {scenario['title']}  (dt = {DT_S:g} s, {DURATION_S / 3600:g} h) ---")
        print("assumed time constants: " + ", ".join(f"{a['name']} = {a['value_s']:g} s" for a in result.assumptions))
        print(f"{'quantity':24s} {'before step':>12s} {'final steady':>13s} {'change':>10s} {'t63 [s]':>9s} {'t95 [s]':>9s}")
        for column, label, unit in QUANTITIES:
            x0, xf = before[column], ss_final[column]
            change = xf - x0
            t63 = time_to_fraction(result.series, column, x0, xf, 0.632, STEP_T_S)
            t95 = time_to_fraction(result.series, column, x0, xf, 0.95, STEP_T_S)
            rows[column] = {"before": x0, "final": xf, "change": change, "t63": t63, "t95": t95}
            note = "" if abs(change) > 1e-4 * abs(x0) else "   (change < 0.01 % -- times not meaningful)"
            fmt = lambda v: "      n/a" if v is None else f"{v:9.0f}"
            print(f"{label + ' [' + unit + ']':24s} {x0:12.4f} {xf:13.4f} {change:+10.4f} {fmt(t63)} {fmt(t95)}{note}")
        runs[scenario["name"]] = {"result": result, "rows": rows, "before": before, "steady": ss_final, "png": png}
        print(f"CSV: {os.path.relpath(csv_path, ROOT)}" + (f" | PNG: {os.path.relpath(png_path, ROOT)}" if png else " | PNG: skipped (matplotlib not installed)"))

    print("\nQuiet run (no scenario, 1 h at 60 s) for the storage finding ...")
    quiet = dy.run_transient([], dt_s=DT_S, duration_s=3600.0)
    index_path = os.path.join(OUT_DIR, "index.html")
    with open(index_path, "w", encoding="utf-8") as handle:
        handle.write(build_index_html(runs, quiet, assumptions))
    print("\n" + BANNER)
    print(f"\nRESULTS PAGE (double-click to open): {os.path.abspath(index_path)}")


if __name__ == "__main__":
    main()
