"""
Literature trend check (step 2 of the validation plan) -- READ-ONLY, offline.

Runs the existing engine in-process (tab1_integration.build_live_snapshot, the UI's own entry point) against the in-memory fake store of
tests/_fakes.py: no database, no network, the real secrets.toml is never read, HYGAS_ALLOW_DB_WRITES stays unset. GA-001's inputs are varied
through the engine's normal override mechanism (build_live_snapshot(overrides={key: fn}), the same pattern tab1_integration's own perturbation
tests use), so GA-001 is not edited.

Three sweeps over the ranges of the published studies (python/literature_reference.py):
  ER 0.20 / 0.25 / 0.30 / 0.40; gasifier temperature 750 / 800 / 850 / 900 / 950 degC; steam-to-feed ratio 0.2 .. 1.5 (model definition:
  kg steam per kg DRY feed, ga001_gasifier_model.py:752; the published ratios' basis is not stated, see docs/literature_reference.md).
Each point is run converged (30 cycles, tail-gas recycle settled) and with no recycle (1 cycle) so the direction can be seen with and without it.
Then the DIRECTION (not the magnitude) of each stated trend is compared with the model: AGREES / DISAGREES / NOT TESTABLE, with the reason.
Nothing is tuned: a row that disagrees is the finding.

    python scripts/run_literature_trend_check.py            (from the repo root)

Writes outputs/literature/trend_check.md and trend_check.csv (outputs/ is git-ignored).
"""
import csv
import os
import socket
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

os.environ.pop("HYGAS_ALLOW_DB_WRITES", None)

from _fakes import FakeSupabase, patched_supabase       # noqa: E402
from python import ga001_gasifier_model as ga001        # noqa: E402
from python import literature_reference as lr           # noqa: E402
from python import plant_status as ps                   # noqa: E402
from python import tab1_integration as t1               # noqa: E402
from python import uncertainty                          # noqa: E402

OUT_DIR = os.path.join(ROOT, "outputs", "literature")
N_CONV, N_ONE = 30, 1
EPS_PP = 0.05          # a change smaller than this many percentage points (dry mol %) is reported as "no effect"

_real_getaddrinfo = socket.getaddrinfo


def _guard(host, *a, **k):
    if "supabase" in str(host).lower():
        raise RuntimeError(f"offline script refused to resolve {host!r}")
    return _real_getaddrinfo(host, *a, **k)


socket.getaddrinfo = _guard

SWEEPS = [
    ("ER", ("GA-001-INPUT", "equivalence_ratio"), [0.20, 0.25, 0.30, 0.40]),
    ("temperature degC", ("GA-001-INPUT", "operating_temperature_C"), [750.0, 800.0, 850.0, 900.0, 950.0]),
    ("steam/feed kg/kg dry", ("GA-001-INPUT", "steam_to_feed_ratio"), [0.2, 0.4, 0.5, 0.8, 1.0, 1.2, 1.5]),
]
SPECIES = ("H2", "CO", "CO2", "CH4", "N2")
COLS = ("sweep", "value", "cycles", "H2 % dry", "CO % dry", "CO2 % dry", "CH4 % dry", "N2 % dry", "dry flow Nm3/h", "H2O % wet", "LHV dry MJ/Nm3",
        "H2 in gas mol/h", "H2 product kg/h", "note")


def _const(v):
    def fn(get_input):
        return {"value": v, "status": ps.STATUS_ASSUMED, "inputs": [], "validation_basis": ps.VALIDATION_NA,
                "confidence_note": "LITERATURE TREND CHECK ONLY (same pattern as tab1_integration's perturbation tests)."}
    return fn


def run_point(name, key, value, n):
    try:
        snap, _s, _e = t1.build_live_snapshot(n_cycles=n, overrides={key: _const(value)})
    except ValueError as exc:                            # solve_product_gas refuses (no physical root / negative moles): report, do not clamp
        return {"sweep": name, "value": value, "cycles": n, "error": str(exc)[:160]}
    g = snap[("GA-001", "Outputs")]["value"]
    row = {"sweep": name, "value": value, "cycles": n, "dry_flow": g["dry_flow_nm3_h"], "h2o_wet": g["H2O_mol_pct_wet"],
           "lhv": snap[("SA-006", "Reading")]["value"], "h2_kg_h": snap[("HB-012", "Compressor")]["value"]["h2_kg_h"],
           "recycle": g["recycle_active"]}
    for s in SPECIES:
        row[s] = g[f"{s}_mol_pct_dry"]
    row["H2_mol_h"] = g["dry_flow_nm3_h"] * g["H2_mol_pct_dry"] / 100.0 / ga001.NM3_PER_MOL
    return row


def fmt_row(r):
    if "error" in r:
        return (r["sweep"], r["value"], r["cycles"], "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "MODEL REFUSES: " + r["error"])
    return (r["sweep"], f"{r['value']:g}", r["cycles"], *(f"{r[s]:.2f}" for s in SPECIES), f"{r['dry_flow']:.2f}", f"{r['h2o_wet']:.2f}",
            f"{r['lhv']:.3f}", f"{r['H2_mol_h']:.1f}", f"{r['h2_kg_h']:.4f}", "recycle active" if r["recycle"] else "no recycle")


def md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c).replace("|", "/") for c in r) + " |" for r in rows]
    return "\n".join(out)


def direction(delta):
    return "up" if delta > EPS_PP else "down" if delta < -EPS_PP else "no effect"


def compare(points, lo_value, hi_value, expect, species_flow=False):
    """expect = {species: 'up'|'down'} for hi_value relative to lo_value. Returns (verdict, reason, detail) for one state (converged / no recycle)."""
    by = {p["value"]: p for p in points if "error" not in p}
    if lo_value not in by or hi_value not in by:
        return "NOT TESTABLE", f"the model gave no result at {lo_value if lo_value not in by else hi_value}", {}
    detail, parts, wrong = {}, [], 0
    for sp, want in expect.items():
        d = by[hi_value][sp] - by[lo_value][sp]
        got = direction(d)
        detail[sp] = (round(d, 3), got)
        ok = got == want
        wrong += 0 if ok else 1
        parts.append(f"{sp}: stated {want}, model {got} ({d:+.2f} pp) {'ok' if ok else 'DIFFERS'}")
    return ("AGREES" if not wrong else "DISAGREES"), "; ".join(parts), detail


def main():
    fake = FakeSupabase()
    results = {}
    with patched_supabase(fake):
        for name, key, values in SWEEPS:
            for n in (N_CONV, N_ONE):
                results[(name, n)] = [run_point(name, key, v, n) for v in values]
    assert fake.calls == [], fake.calls

    L = []
    add = L.append
    add("# Literature trend check -- measured output\n")
    add(f"Offline, in-process engine, in-memory fake store, {len(fake.calls)} database / network calls. Dry mol % at the GA-001 outlet (= GC-013); LHV is SA-006's dry "
        "composition-weighted LHV; H2 product is HB-012 (PSA product). Cold-gas efficiency: **not shown, the repo computes none** (only the partial H2-energy / "
        "feed-LHV `overall_efficiency` in Tab 1); no new definition was added. Converged = 30 cycles (tail-gas recycle settled); no recycle = 1 cycle "
        "(GA-001 then uses the 41.67 kg/h placeholder feed, so absolute values differ; only the direction is compared).\n")
    csv_rows = [COLS]
    for name, key, values in SWEEPS:
        add(f"## Sweep: {name}\n")
        rows = []
        for n in (N_CONV, N_ONE):
            for r in results[(name, n)]:
                rows.append(fmt_row(r))
                csv_rows.append(fmt_row(r))
        add(md_table(COLS, rows))
        add("")

    # ---- direction comparison
    add("## Direction comparison (published trend vs model)\n")
    add(f"Threshold: a change below {EPS_PP} percentage points of dry mol % counts as 'no effect'. AGREES needs every named species to move the stated way; "
        "magnitude is not compared. The published page states directions only (no concentrations).\n")
    vtt = {t["id"]: t for k, t in lr.trends() if k == "vtt_sewage_sludge_parametric"}
    cmp_rows = []
    t = vtt["T_up"]
    expect = {**{s: "up" for s in t["raises"]}, **{s: "down" for s in t["lowers"]}}
    for n in (N_CONV, N_ONE):
        v, why, _ = compare(results[("temperature degC", n)], 750.0, 950.0, expect)
        cmp_rows.append(("higher temperature raises H2 and CO, lowers CO2 and CH4 (VTT sludge study)", "750 -> 950 degC", "converged" if n == N_CONV else "no recycle", v, why))
    t = vtt["steam_up"]
    for lo, hi in ((0.5, 1.5), (0.2, 1.5)):
        for n in (N_CONV, N_ONE):
            v, why, _ = compare(results[("steam/feed kg/kg dry", n)], lo, hi, {"H2": "up"})
            cmp_rows.append(("higher steam ratio raises H2 (VTT sludge study)", f"{lo:g} -> {hi:g} kg/kg", "converged" if n == N_CONV else "no recycle", v, why))
    for n in (N_CONV, N_ONE):
        v, why, _ = compare(results[("ER", n)], 0.20, 0.40, {"H2": "down", "CO": "down"})     # going UP in ER lowers H2 and CO <=> lower ER gives more
        cmp_rows.append(("lower ER (0.2 against 0.4) gives more H2 and CO (VTT sludge study)", "ER 0.40 vs 0.20", "converged" if n == N_CONV else "no recycle", v,
                         why.replace("stated down", "stated lower at 0.40 than at 0.20")))
    add(md_table(("published trend", "model compared", "state", "verdict", "reason"), cmp_rows))

    # ---- plain comparisons
    n_c = ga001.elemental_atomic_ratios(ga001.FEEDSTOCK_C_FRACTION, ga001.FEEDSTOCK_H_FRACTION, ga001.FEEDSTOCK_O_FRACTION, ga001.FEEDSTOCK_N_FRACTION,
                                        ga001.ASH_FRACTION)[3]
    default_ratio = uncertainty.ASSUMPTIONS["steam_to_feed_ratio"]["point"]
    sc_mol = default_ratio / n_c * 1000.0 / ga001.M_H2O
    base = {p["value"]: p for p in results[("ER", N_CONV)] if "error" not in p}[0.25]
    add("\n## Plain comparisons (no trend claimed)\n")
    plain = [
        ("steam ratio default vs published steam/fuel 0.5-1.5 (VTT, basis unstated)", f"model {default_ratio} kg steam / kg dry feed", "published 0.5, 1.0, 1.5 (kg/kg assumed; the page states no basis)",
         f"the default is below the lowest published value by {0.5 - default_ratio:g} kg/kg; the three published values were run (sweep above)"),
        ("steam ratio default vs published steam-to-carbon 0.7-1.13 (Parrillo, unit unstated)", f"model {sc_mol:.3f} mol steam / mol feed carbon (= {default_ratio} kg/kg x conversion)",
         "published 0.7-1.13", "if the page's ratio is mol/mol the default is below the range; if it is kg/kg it cannot be compared; unit not stated, so no verdict"),
        ("ER default vs published ER", f"model {uncertainty.ASSUMPTIONS['air_equivalence_ratio']['point']}", "Parrillo 0.22-0.25; MDPI 0.25; Bates 0-0.157; VTT 0.2-0.4; SRF best 0.4",
         "inside Parrillo's range (at its upper end) and equal to the MDPI value"),
        ("temperature default vs published", f"model {ga001.GA001_OPERATING_TEMPERATURE_C:g} degC", "VTT 650-850; Bates 750-850; MDPI 861-902; SRF best 900; CLG fuel reactor 850-980",
         "above every bubbling-bed lab range; inside the CLG fuel-reactor range"),
        ("dry LHV", f"model {base['lhv']:.2f} MJ/Nm3 (dry, H2+CO+CH4)", "MDPI up to 9.32; SRF 14.43 (basis not stated)", "model is below both; different feeds, agents and bases, no verdict"),
        ("CH4", f"model {base['CH4']:.2f} vol % dry", "CLG pilot 5-10 vol %", "different configuration; CH4 in the model is a fixed 5 % of converted carbon, not a result"),
        ("PSA recovery", "model 0.79 (HB-006)", "vendor page: up to 90 %", "within the vendor maximum; vendor marketing"),
    ]
    add(md_table(("quantity", "model", "published", "comment"), plain))
    add("\n## Not testable here\n")
    add(md_table(("published item", "verdict", "reason"), [
        ("cold-gas efficiency 59.3 -> 68.6 % (MDPI), 67.31 % (SRF), > 50 % (CLG)", "NOT TESTABLE", "the repo computes no cold-gas efficiency; adding a definition is outside this task"),
        ("tar -94.5 % with olivine; naphthalene 108-122 ppm; CLG 'almost no tar'", "NOT TESTABLE", "GA-001 tar is permanently Missing (ga001_gasifier_model.py:842)"),
        ("transient > 1 h (char inventory); devolatilisation seconds; char minutes to hours", "NOT TESTABLE", "steady-state check only; the dynamics layer is a separate, Assumed model"),
        ("H2 + CO 72.53 % (SRF)", "NOT TESTABLE", "the basis of the percentage is not stated"),
    ]))
    report = "\n".join(L) + "\n"
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "trend_check.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(report)
    with open(os.path.join(OUT_DIR, "trend_check.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerows(csv_rows)
        w.writerow([])
        w.writerow(("published trend", "model compared", "state", "verdict", "reason"))
        w.writerows(cmp_rows)
    sys.stdout.reconfigure(encoding="utf-8")
    print(report)
    print(f"database / network calls made: {len(fake.calls)}")
    print(f"wrote {os.path.join(OUT_DIR, 'trend_check.md')} and trend_check.csv")


if __name__ == "__main__":
    main()
