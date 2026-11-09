"""
Operating-point study (Phase 1, task P1-01) -- READ-ONLY, offline.

Question: which combinations of the levers the engine ALREADY has bring the twin's hydrogen product near DOK-ING's "about 50 kg/day"
(RFI #6, plastic waste), and what does each combination do to the other numbers? This is a SCENARIO STUDY, not a calibration:

  * nothing is tuned and no default is chosen or changed from it (the engine's defaults are untouched; every lever is set through the engine's
    normal override mechanism, as scripts/run_h2_yield_comparison.py does);
  * every lever moved is listed with its value, and whether the value lies inside its documented range;
  * all lever values are Assumed (uncertainty.py ranges and the carbon-conversion literature range), none is a DOK-ING value;
  * the ~50 kg/day is a DOK-ING statement whose basis (plastic waste, gross or net, availability) is not known: reaching it says nothing about
    whether the twin is right.

Runs the existing engine in-process (tab1_integration.build_live_snapshot) against the in-memory fake store of tests/_fakes.py: no database, no
network, the real secrets.toml is never read, HYGAS_ALLOW_DB_WRITES stays unset.

    python scripts/run_operating_point_study.py            full grid, converged (30 cycles), about 15 minutes
    python scripts/run_operating_point_study.py --quick    the two default points and the corners of the grid, about 3 minutes

Writes outputs/operating_point/operating_point_study.md and .csv (outputs/ is git-ignored).
"""
import csv
import itertools
import os
import socket
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
os.environ.pop("HYGAS_ALLOW_DB_WRITES", None)

from python import ga001_gasifier_model as ga001        # noqa: E402
from python import hb_wgs_psa_storage_chain as hbchain  # noqa: E402
from python import plant_status as ps                   # noqa: E402
from python import tab1_integration as t1               # noqa: E402
from python import uncertainty                          # noqa: E402

OUT_DIR = os.path.join(ROOT, "outputs", "operating_point")
N_CONV = 30
TARGET_KG_DAY = 50.0                 # data/dokink_rfi_answers.md RFI #6, plastic waste, basis not stated
BAND = 0.10                          # "near" = within +/-10 % of the target; a reporting convention, not a tolerance of any kind
MID = "DOK-ING midpoint (Assumed point)"
MODES = ("regasify", "heat_only")
PSA_REGISTRY_RECOVERY = 0.75         # HB-007 'H2 recovery rate (design)', Unverified (registry)

_real_getaddrinfo = socket.getaddrinfo


def _guard(host, *a, **k):
    if "supabase" in str(host).lower():
        raise RuntimeError(f"offline script refused to resolve {host!r}")
    return _real_getaddrinfo(host, *a, **k)


socket.getaddrinfo = _guard


def documented_ranges():
    """(low, point, high) per lever. ER and steam come from uncertainty.py (point +/-15 %, Assumed); carbon conversion from the literature range
    in ga001_gasifier_model (Basu 2010, Assumed) with the engine's own point as the middle value."""
    er_lo, er_hi = uncertainty.bounds("air_equivalence_ratio")
    st_lo, st_hi = uncertainty.bounds("steam_to_feed_ratio")
    c_lo, c_hi = ga001.CARBON_CONVERSION_EFFICIENCY_RANGE
    return {
        "er": (er_lo, uncertainty.ASSUMPTIONS["air_equivalence_ratio"]["point"], er_hi),
        "steam": (st_lo, uncertainty.ASSUMPTIONS["steam_to_feed_ratio"]["point"], st_hi),
        "conv": (c_lo, ga001.CARBON_CONVERSION_EFFICIENCY, c_hi),
    }


def build_grid(quick=False):
    """List of cases {mode, er, steam, conv, psa}; psa is None (model value) or PSA_REGISTRY_RECOVERY. Full grid = 2 x 3 x 3 x 3 x 2 = 108 cases."""
    r = documented_ranges()
    if quick:
        pick = lambda t: (t[0], t[2])                       # noqa: E731  corners only
        pts = [(r["er"][1], r["steam"][1], r["conv"][1], None)]     # the default point
        pts += [(e, s, c, None) for e, s, c in itertools.product(pick(r["er"]), pick(r["steam"]), pick(r["conv"]))]
        pts += [(r["er"][1], r["steam"][1], r["conv"][1], PSA_REGISTRY_RECOVERY)]
    else:
        pts = [(e, s, c, p) for e, s, c, p in itertools.product(r["er"], r["steam"], r["conv"], (None, PSA_REGISTRY_RECOVERY))]
    return [{"mode": m, "er": e, "steam": s, "conv": c, "psa": p} for m in MODES for (e, s, c, p) in pts]


def out_of_range_cases():
    """Extra cases OUTSIDE the documented ranges, labelled as such in the report (the ER values come from the existing ER sweep in
    scripts/run_h2_yield_comparison.py)."""
    r = documented_ranges()
    return [{"mode": "heat_only", "er": e, "steam": r["steam"][1], "conv": r["conv"][1], "psa": None} for e in (0.35, 0.40)]


def in_range(case):
    r = documented_ranges()
    return all(r[k][0] - 1e-9 <= case[k] <= r[k][2] + 1e-9 for k in ("er", "steam", "conv"))


def levers_moved(case):
    """How many levers differ from the engine's default (tail-gas mode regasify, ER, steam and conversion at their points, PSA model value)."""
    r = documented_ranges()
    n = int(case["mode"] != "regasify") + int(case["psa"] is not None)
    n += sum(int(abs(case[k] - r[k][1]) > 1e-12) for k in ("er", "steam", "conv"))
    return n


def near_target(h2_kg_day, target=TARGET_KG_DAY, band=BAND):
    return abs(h2_kg_day - target) <= band * target


def summarise(results):
    """results: list of dicts with 'h2_kg_day' and 'in_range'. Returns the in-range minimum and maximum and the cases near the target."""
    inr = [x for x in results if x["in_range"]]
    if not inr:
        return {"n_in_range": 0, "min": None, "max": None, "near": []}
    return {"n_in_range": len(inr), "min": min(inr, key=lambda x: x["h2_kg_day"]), "max": max(inr, key=lambda x: x["h2_kg_day"]),
            "near": [x for x in inr if near_target(x["h2_kg_day"])]}


def _const(v):
    def fn(get_input):
        return {"value": v, "status": ps.STATUS_ASSUMED, "inputs": [], "validation_basis": ps.VALIDATION_NA,
                "confidence_note": "OPERATING-POINT STUDY ONLY (override; the engine default is unchanged)."}
    return fn


def _psa_recovery(rec):
    def fn(get_input):
        r = hbchain.hb006_psa_recovery(get_input)
        r["value"] = dict(r["value"], recovery=rec)
        r["confidence_note"] = "OPERATING-POINT STUDY ONLY: recovery fixed at the registry's 75 %"
        return r
    return fn


def overrides(case):
    ov = {("GA-001-INPUT", "tail_gas_mode"): _const(case["mode"]),
          ("GA-001-INPUT", "equivalence_ratio"): _const(case["er"]),
          ("GA-001-INPUT", "steam_to_feed_ratio"): _const(case["steam"]),
          ("GA-001-INPUT", "carbon_conversion_efficiency"): _const(case["conv"])}
    if case["psa"] is not None:
        ov[("HB-006", "PSA")] = _psa_recovery(case["psa"])
    return ov


def measure(snapshot):
    """The numbers reported per case, read from a live snapshot."""
    go = snapshot[("GA-001", "Outputs")]["value"]
    psa = snapshot[("HB-006", "PSA")]["value"]
    en = snapshot[("GA-001", "EnergyBalance")]["value"]["cases"][MID]
    return {"h2_kg_day": 24.0 * float(snapshot[("HB-012", "Compressor")]["value"]["h2_kg_h"]),
            "psa_recovery_pct": 100.0 * float(psa["recovery"]), "psa_feed_h2_pct": 100.0 * float(psa["y_H2"]),
            "syngas_n2_pct": float(go["N2_mol_pct_dry"]), "syngas_h2_pct": float(go["H2_mol_pct_dry"]),
            "syngas_flow_nm3_h": float(go["dry_flow_nm3_h"]), "net_heat_kw": float(en["net_heat_kw"])}


def run_case(case, n=N_CONV):
    snap = t1.build_live_snapshot(n_cycles=n, overrides=overrides(case))[0]
    out = dict(case)
    out.update(measure(snap))
    out["in_range"] = in_range(case)
    out["levers_moved"] = levers_moved(case)
    return out


def md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c).replace("|", "/") for c in r) + " |" for r in rows]
    return "\n".join(out)


def _row(x):
    psa = "model" if x["psa"] is None else f"fixed {100 * x['psa']:.0f} %"
    return (x["mode"], f"{x['er']:.4g}", f"{x['steam']:.3g}", f"{x['conv']:.3g}", psa, f"{x['h2_kg_day']:.1f}", f"{100 * (x['h2_kg_day'] - TARGET_KG_DAY) / TARGET_KG_DAY:+.0f} %",
            f"{x['psa_recovery_pct']:.1f}", f"{x['psa_feed_h2_pct']:.1f}", f"{x['syngas_n2_pct']:.1f}", f"{x['syngas_flow_nm3_h']:.1f}", f"{x['net_heat_kw']:+.1f}",
            str(x["levers_moved"]), "yes" if x["in_range"] else "NO")


HEADERS = ("mode", "ER", "steam/feed", "carbon conv.", "PSA recovery", "H2 kg/day", "vs 50", "PSA rec. %", "PSA feed H2 %", "syngas N2 %", "syngas flow Nm3/h",
           "net heat kW (17.5 MJ/kg)", "levers moved from default", "all levers in documented range")


def main(argv):
    from _fakes import FakeSupabase, patched_supabase       # noqa: E402  (tests/ is on sys.path)
    quick = "--quick" in argv
    cases = build_grid(quick) + out_of_range_cases()
    fake = FakeSupabase()
    results = []
    with patched_supabase(fake):
        for i, c in enumerate(cases, 1):
            results.append(run_case(c))
            print(f"[{i}/{len(cases)}] {c['mode']} ER {c['er']:.4g} steam {c['steam']:.3g} conv {c['conv']:.3g} psa {c['psa']} -> {results[-1]['h2_kg_day']:.1f} kg/day", flush=True)
    assert fake.calls == [], fake.calls

    r = documented_ranges()
    inr = [x for x in results if x["in_range"]]
    s = summarise(results)
    default = next(x for x in results if x["mode"] == "regasify" and x["psa"] is None and abs(x["er"] - r["er"][1]) < 1e-12
                   and abs(x["steam"] - r["steam"][1]) < 1e-12 and abs(x["conv"] - r["conv"][1]) < 1e-12)
    L = []
    add = L.append
    add("# Operating-point study (P1-01): measured output\n")
    add(f"Offline, in-process engine, in-memory fake store, 0 database / network calls. Converged state ({N_CONV} cycles). {'QUICK grid (default point + corners).' if quick else 'Full grid.'} "
        "Every lever value below is **Assumed** (uncertainty.py point +/-15 %; carbon conversion from the literature range). Nothing is tuned, no default is changed, and "
        "this is a scenario study, not a calibration.\n")
    add("## 1. Levers and their documented ranges\n")
    add(md_table(("lever", "low", "default point", "high", "source"),
                 [("equivalence ratio (ER)", f"{r['er'][0]:.4g}", f"{r['er'][1]:.4g}", f"{r['er'][2]:.4g}", "uncertainty.ASSUMPTIONS (Assumed, point +/-15 %)"),
                  ("steam-to-feed ratio", f"{r['steam'][0]:.3g}", f"{r['steam'][1]:.3g}", f"{r['steam'][2]:.3g}", "uncertainty.ASSUMPTIONS (Assumed, point +/-15 %)"),
                  ("carbon conversion", f"{r['conv'][0]:.3g}", f"{r['conv'][1]:.3g}", f"{r['conv'][2]:.3g}", "ga001 CARBON_CONVERSION_EFFICIENCY_RANGE (Assumed, Basu 2010)"),
                  ("PSA recovery", "-", "model (about 78 %)", f"fixed {100 * PSA_REGISTRY_RECOVERY:.0f} %", "HB-007 'H2 recovery rate (design)' (Unverified (registry))"),
                  ("tail-gas mode", "-", "regasify", "heat_only", "GA-001-INPUT tail_gas_mode (Assumed)")]))
    add(f"\nDefault point, measured here: {default['h2_kg_day']:.1f} kg/day (`regasify`, all defaults), which must equal the figure in `docs/tail_gas_heat.md`. "
        f"DOK-ING's ~{TARGET_KG_DAY:g} kg/day is for plastic waste; gross or net, availability and start-up are not stated. \"Near\" below means within +/-{100 * BAND:.0f} % of {TARGET_KG_DAY:g}, a reporting convention only.\n")
    add("## 2. Result\n")
    if s["n_in_range"]:
        add(f"Over the {s['n_in_range']} cases with every lever inside its documented range, the hydrogen product runs from **{s['min']['h2_kg_day']:.1f}** "
            f"({s['min']['mode']}, ER {s['min']['er']:.4g}, steam {s['min']['steam']:.3g}, conversion {s['min']['conv']:.3g}, PSA "
            f"{'model' if s['min']['psa'] is None else 'fixed 75 %'}) to **{s['max']['h2_kg_day']:.1f}** kg/day.")
        reg_min = min((x for x in inr if x["mode"] == "regasify"), key=lambda x: x["h2_kg_day"])
        add(f"With the tail gas re-gasified (`regasify`, today's default) the in-range minimum is {reg_min['h2_kg_day']:.1f} kg/day ({100 * (reg_min['h2_kg_day'] - TARGET_KG_DAY) / TARGET_KG_DAY:+.0f} % against {TARGET_KG_DAY:g}).")
        if s["near"]:
            fewest = min(s["near"], key=lambda x: x["levers_moved"])
            add(f"\n**{len(s['near'])} of those cases are near {TARGET_KG_DAY:g} kg/day**, all of them {'in `heat_only`' if all(x['mode'] == 'heat_only' for x in s['near']) else 'in the modes listed in section 3'}; "
                f"the fewest levers moved from the default is {fewest['levers_moved']}. They are listed in section 3. Every lever value is Assumed; none is supported by a DOK-ING value, and the tail-gas mode is the lever that moves hydrogen most (G5-07 row 9, an open owner decision).\n")
        else:
            add(f"\n**No in-range case is near {TARGET_KG_DAY:g} kg/day.** With every lever inside its documented range, the twin does not reach DOK-ING's figure; reaching it needs "
                "a structural change (the gasifying agent and the tail-gas treatment, G5-07 rows 5 and 9) or a basis for the 50 that differs from the model's, not a different value of these levers.\n")
    add("## 3. Cases near the target (in documented range)\n")
    add(md_table(HEADERS, [_row(x) for x in sorted(s["near"], key=lambda x: abs(x["h2_kg_day"] - TARGET_KG_DAY))]) if s["near"] else "(none)")
    add("\n## 4. All cases\n")
    add(md_table(HEADERS, [_row(x) for x in sorted(results, key=lambda x: (x["mode"], x["psa"] is not None, x["er"], x["steam"], x["conv"]))]))
    add("\n## 5. What these numbers do not show\n")
    add("A case near 50 kg/day is **not** a better model of DOK-ING's plant. Every case keeps the registry disagreements of `docs/cross_module_disagreements.md` that do not depend on "
        "these levers (see the syngas N2 and PSA feed H2 columns: the registry expects about 10 % N2 and 55 % H2 in the PSA feed), and the net heat column shows that the heat "
        "balance still has no source for the steam raising and drying duty. The levers move several outputs at once; matching one number can worsen others. "
        "The study does not choose a default. That is a separate owner decision (P1-06).\n")
    report = "\n".join(L) + "\n"
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "operating_point_study.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(report)
    with open(os.path.join(OUT_DIR, "operating_point_study.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(("mode", "er", "steam", "conv", "psa", "h2_kg_day", "psa_recovery_pct", "psa_feed_h2_pct", "syngas_n2_pct", "syngas_flow_nm3_h", "net_heat_kw", "levers_moved", "in_range"))
        for x in results:
            w.writerow((x["mode"], x["er"], x["steam"], x["conv"], x["psa"], x["h2_kg_day"], x["psa_recovery_pct"], x["psa_feed_h2_pct"], x["syngas_n2_pct"],
                        x["syngas_flow_nm3_h"], x["net_heat_kw"], x["levers_moved"], x["in_range"]))
    sys.stdout.reconfigure(encoding="utf-8")
    print(report)
    print(f"database / network calls made: {len(fake.calls)}")
    print(f"wrote {os.path.join(OUT_DIR, 'operating_point_study.md')} and .csv")


if __name__ == "__main__":
    main(sys.argv[1:])
