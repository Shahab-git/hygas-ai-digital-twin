"""
Heat balance and hydrogen yield across feeds (reference-feeds task, item C) -- READ-ONLY, offline.

Runs the existing engine in-process (tab1_integration.build_live_snapshot) against the in-memory fake store of tests/_fakes.py: no database, no network, the
real secrets.toml is never read, HYGAS_ALLOW_DB_WRITES stays unset. The feed enters ONLY through the engine's normal input mechanism: the override
("GA-001-INPUT","feedstock_composition") with dry ash-free C/H/O/N fractions (python/reference_feeds.model_composition). Nothing in the engine is edited, no default is
changed or tuned, ER stays at the model's 0.25 except in the labelled ER sweep.

What the engine cannot take (so it is dropped or the feed is NOT TESTABLE): the ash fraction is a module constant (0.10), not an input, so EVERY feed here runs with 10 % ash;
sulphur and chlorine are not carried (dropped); only C, H, O, N exist. The feed energy of a run is the feed's own LHV (daf, from the literature HHV) x (1 - 0.10).

    python scripts/run_feed_comparison.py             (from the repo root, about 4 minutes)

Writes outputs/feeds/feed_comparison.md and .csv (outputs/ is git-ignored).
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
from python import balance_audit as ba                  # noqa: E402
from python import ga001_gasifier_model as ga001        # noqa: E402
from python import plant_status as ps                   # noqa: E402
from python import reference_feeds as rf                # noqa: E402
from python import tab1_integration as t1               # noqa: E402

OUT_DIR = os.path.join(ROOT, "outputs", "feeds")
N_CONV = 30
MODES = ("regasify", "heat_only")

_real_getaddrinfo = socket.getaddrinfo


def _guard(host, *a, **k):
    if "supabase" in str(host).lower():
        raise RuntimeError(f"offline script refused to resolve {host!r}")
    return _real_getaddrinfo(host, *a, **k)


socket.getaddrinfo = _guard


def _const(v):
    def fn(get_input):
        return {"value": v, "status": ps.STATUS_ASSUMED, "inputs": [], "validation_basis": ps.VALIDATION_NA,
                "confidence_note": "FEED COMPARISON ONLY: composition from python/reference_feeds.py (literature-informed Assumed), not DOK-ING data."}
    return fn


# --- the feeds -----------------------------------------------------------------------------------------------------
def _feed_from(key, label):
    mc = rf.model_composition(key)
    return {"label": label, "key": key, "comp": mc["composition_daf"], "lhv_model_dry": mc["LHV_model_dry_MJ_kg"], "lhv_daf": mc["LHV_daf_MJ_kg"],
            "dropped": mc["dropped_daf_pct"], "unaccounted": mc["unaccounted_daf_pct"], "bands": rf.bands_for(key)}


def _blend_feed():
    b = rf.blend()
    mc = rf.model_composition({"C": b["C_daf_pct"], "H": b["H_daf_pct"], "O": b["O_daf_pct"], "N": b["N_daf_pct"], "Cl": b["Cl_daf_pct"], "LHV_daf_MJ_kg": b["LHV_daf_MJ_kg"]})
    bands = rf.check_bands({"C_dry_pct": b["C_dry_pct"], "H_dry_pct": b["H_dry_pct"], "VM_dry_pct": None, "ash_dry_pct": b["ash_dry_pct"], "LHV_dry_MJ_kg": b["LHV_dry_MJ_kg"]})
    return {"label": "blend M1 (illustrative: 40 PE / 25 PP / 15 PS / 10 PET / 10 PVC)", "key": "blend_M1", "comp": mc["composition_daf"], "lhv_model_dry": mc["LHV_model_dry_MJ_kg"],
            "lhv_daf": mc["LHV_daf_MJ_kg"], "dropped": mc["dropped_daf_pct"], "unaccounted": mc["unaccounted_daf_pct"], "bands": bands}


def _default_feed():
    est = ba.feedstock_lhv_estimates()
    lhv_dry = 0.5 * sum(est["range_MJ_kg"])                          # model composition, dry (ash 10 % included), Estimated
    d = est["dry_wt_pct"]
    return {"label": "default stand-in (C/H/O/N 0.50/0.06/0.43/0.01 daf, ash 0.10)", "key": "default", "comp": None, "lhv_model_dry": lhv_dry, "lhv_daf": lhv_dry / 0.9,
            "dropped": {}, "unaccounted": 0.0,
            "bands": rf.check_bands({"C_dry_pct": d["C"], "H_dry_pct": d["H"], "VM_dry_pct": None, "ash_dry_pct": d["ash"], "LHV_dry_MJ_kg": lhv_dry})}


FEEDS = [_default_feed(), _feed_from("zhou_cotton", "cotton"), _feed_from("zhou_wool", "wool"), _feed_from("zhou_pe", "polyethylene (PE)"),
         _feed_from("zhou_pp", "polypropylene (PP)"), _feed_from("zhou_ps", "polystyrene (PS)"), _feed_from("zhou_pet", "PET"), _blend_feed()]
NOT_TESTABLE = [
    ("RDF (Teerawattana)", f"ash {rf.derived('teerawattana_rdf')['ash_dry_pct']:.1f} % dry against the engine's fixed 10 % (ash is a module constant, not an input); S 0.12 % and Cl 0.73 % would be dropped; "
                           "the feed would be a different fuel, not RDF"),
    ("sewage sludge SS1 / SS2 (Werle)", "ash 36.5 / 44.2 % against the fixed 10 %; the page's O is 'by difference' and apparently includes the ash, so no dry ash-free C/H/O/N exists to enter; "
                                        "S 1.7-1.8 % and N 3.6-4.9 % dry (N is carried, S is not)"),
    ("PVC alone", "Cl 55.18 % daf would be dropped, leaving C+H+O+N = 44.5 % of the mass: not the same material (PVC enters only inside blend M1, where 5.2 % of the dry mass, the Cl, is dropped)"),
    ("wood, Chalmers thesis, Moliner et al.", "no values (Missing / NOT VERIFIED)"),
]


def run(feed, mode, er=None, with_audit=True):
    ov = {("GA-001-INPUT", "tail_gas_mode"): _const(mode)}
    if feed["comp"] is not None:
        ov[("GA-001-INPUT", "feedstock_composition")] = _const(feed["comp"])
    if er is not None:
        ov[("GA-001-INPUT", "equivalence_ratio")] = _const(er)
    try:
        snap = t1.build_live_snapshot(n_cycles=N_CONV, overrides=ov)[0]
        prev = t1.build_live_snapshot(n_cycles=N_CONV - 1, overrides=ov)[0]
    except ValueError as exc:
        return {"feed": feed, "mode": mode, "error": str(exc)[:200]}
    g = snap[("GA-001", "Outputs")]["value"]
    dry_feed = float(snap[("FE-005", "MoistureBalance")]["value"]["dry_solids_kg_h"])
    h2 = float(snap[("HB-012", "Compressor")]["value"]["h2_kg_h"])
    eb = snap[("GA-001", "EnergyBalance")]["value"]
    acc = snap[("GA-001", "CarbonAccounting")]["value"]
    ge = ba.gasifier_energy(snap, prev, feed["lhv_model_dry"])
    demand = eb["cases"][next(iter(eb["cases"]))]["heat_demand_total_kw"]
    tail_used = eb["tail_gas"]["chemical_kw"] if mode == "heat_only" else 0.0
    duty = ge["implied_heat_duty_kw"]
    r = {"feed": feed, "mode": mode, "er": er, "dry_feed": dry_feed, "h2_kg_h": h2, "h2_kg_day": h2 * 24.0, "h2_per_kg_dry": h2 / dry_feed, "h2_per_kg_combustible": h2 / (dry_feed * 0.9),
         "pct": {s: g[f"{s}_mol_pct_dry"] for s in ("H2", "CO", "CO2", "CH4", "N2")}, "dry_flow": g["dry_flow_nm3_h"], "lhv_gas": snap[("SA-006", "Reading")]["value"],
         "feed_kw": ge["in"][0]["kw"], "gas_chem_kw": ge["out"][0]["kw"], "duty": duty, "demand": demand, "tail_available": eb["tail_gas"]["chemical_kw"], "tail_used": tail_used,
         "net": tail_used - duty - demand, "net_if_tail_heat": eb["tail_gas"]["chemical_kw"] - duty - demand,
         "steam_kw": eb["cases"][next(iter(eb["cases"]))]["steam_raising_kw"], "cb_kg_h": acc["carbon_black_kg_h"], "cb_cap_exceeded": acc["datasheet_cross_check"]["ga008_capacity_exceeded"],
         "unconv_recycle": acc["unconverted_from_recycle_kg_h"]}
    if with_audit:
        a = ba.audit_snapshot(snap, prev)
        rows = a["ga001"]["rows"]
        r.update({"c_res": rows["C"]["residual_kg_h"], "c_verdict": rows["C"]["verdict"], "h_rel": abs(rows["H"]["rel"]), "o_rel": abs(rows["O"]["rel"]), "n_rel": abs(rows["N"]["rel"]),
                  "ash_verdict": rows["ash"]["verdict"], "loop_hon": max(abs(a["loop"]["rows"][e]["rel"]) for e in "HON")})
    return r


def md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c).replace("|", "/") for c in r) + " |" for r in rows]
    return "\n".join(out)


def band_s(b):
    short = {"C_dry_pct": "C", "H_dry_pct": "H", "VM_dry_pct": "VM", "ash_dry_pct": "ash", "LHV_dry_MJ_kg": "LHV"}
    return ", ".join(f"{short[k]} {'ok' if v[1] == 'satisfied' else 'FAILS' if v[1] == 'fails' else 'n/t'}" for k, v in b.items())


def main():
    fake = FakeSupabase()
    results, sweep = [], []
    with patched_supabase(fake):
        for feed in FEEDS:
            for mode in MODES:
                results.append(run(feed, mode))
        for feed in (FEEDS[3], FEEDS[1]):                                # PE and cotton only
            for er in (0.20, 0.25, 0.30):
                for mode in MODES:
                    sweep.append(run(feed, mode, er=er, with_audit=False))
    assert fake.calls == [], fake.calls

    L, add = [], None
    add = L.append
    csv_rows = [("section", "feed", "mode", "ER", "quantity", "value", "unit")]
    add("# Heat balance and hydrogen yield across feeds -- measured output\n")
    add("Offline, in-process engine, in-memory fake store, 0 database / network calls. 30 cycles (converged). The feed enters only through the normal input "
        "(`GA-001-INPUT feedstock_composition`, dry ash-free C/H/O/N from `python/reference_feeds.py`, literature-informed Assumed). **The engine's ash fraction is fixed at 10 % for every feed** "
        "(a module constant, not an input), S and Cl are not carried (dropped), the feed mass rate is the model's (37.50 kg/h dry), ER is 0.25. The feed energy is the feed's own LHV "
        "(daf, calculated from the literature HHV) x 0.9. Nothing was tuned.\n")

    add("## 1. Feeds, what was dropped, DOK-ING band compliance (dry-basis numbers)\n")
    rows = []
    for f in FEEDS:
        comp = "default" if f["comp"] is None else ", ".join(f"{k} {100 * v:.1f}" for k, v in f["comp"].items())
        drop = "-" if not f["dropped"] or not any(f["dropped"].values()) else ", ".join(f"{k} {v:.2f} % daf" for k, v in f["dropped"].items() if v)
        rows.append((f["label"], comp, drop, f"{f['unaccounted']:.2f}", f"{f['lhv_daf']:.2f}", f"{f['lhv_model_dry']:.2f}", band_s(f["bands"])))
    add(md_table(("feed", "model composition (daf %, renormalised)", "dropped", "unreported daf %", "LHV daf MJ/kg", "feed energy in the model, MJ/kg dry (x 0.9)", "DOK-ING bands (ok / FAILS / n/t = not testable)"), rows))
    add("\nBands: C > 45, H > 5, VM > 65, ash 5-15 %, LHV 15-20 MJ/kg dry (`data/dokink_rfi_answers.md:15-17`). The default stand-in's C is exactly 45.0 % dry (the floor, not above it); "
        "plastics and textiles are too clean for the 5-15 % ash band and mostly above the LHV band; the H floor says nothing about an upper limit (PE/PP are at about 14 %).\n")

    add("## 2. Hydrogen, gas and carbon\n")
    rows = []
    for r in results:
        f = r["feed"]
        if "error" in r:
            rows.append((f["label"][:34], r["mode"], "MODEL REFUSES: " + r["error"], "", "", "", "", "", "", ""))
            continue
        p = r["pct"]
        rows.append((f["label"][:34], r["mode"], f"{r['h2_kg_day']:.1f}", f"{r['h2_per_kg_dry']:.4f}", f"{r['h2_per_kg_combustible']:.4f}",
                     f"{p['H2']:.1f}/{p['CO']:.1f}/{p['CO2']:.1f}/{p['CH4']:.1f}/{p['N2']:.1f}", f"{r['dry_flow']:.1f}", f"{r['lhv_gas']:.2f}",
                     f"{r['cb_kg_h']:.2f}" + (" EXCEEDS 3" if r["cb_cap_exceeded"] else ""), f"{r['c_res']:+.0e} ({r['c_verdict'].split(' (')[0]})"))
        csv_rows.append(("h2", f["label"], r["mode"], "0.25", "h2_kg_day", r["h2_kg_day"], "kg/day"))
    add(md_table(("feed", "mode", "H2 kg/day", "kg H2 / kg dry feed", "kg H2 / kg combustible", "gas dry mol % H2/CO/CO2/CH4/N2", "dry gas Nm3/h", "gas LHV MJ/Nm3", "carbon black kg/h (GA-008 cap 3)", "GA-001 carbon residual"), rows))
    add("\nReference: DOK-ING about 50 kg/day (plastic waste, gross or net unstated); registry 44.4 kg/day. Per kg dry feed those are 0.0556 and 0.0493 kg/kg on the model's 37.5 kg/h dry feed.\n")

    add("## 3. Heat balance (kW; feed-specific LHV; `(GA-001, EnergyBalance)` terms)\n")
    rows = []
    for r in results:
        f = r["feed"]
        if "error" in r:
            continue
        rows.append((f["label"][:34], r["mode"], f"{r['feed_kw']:.1f}", f"{r['gas_chem_kw']:.1f}", f"{r['duty']:+.1f}", f"{r['steam_kw']:.1f}", f"{r['demand']:.1f}", f"{r['tail_used']:.1f}",
                     f"{r['net']:+.1f}", f"{r['net_if_tail_heat']:+.1f}"))
        csv_rows.append(("heat", f["label"], r["mode"], "0.25", "net_heat_kw", r["net"], "kW"))
    add(md_table(("feed", "mode", "feed chem. kW", "gas chem. kW", "gasifier duty kW (+ add heat)", "steam raising kW", "heat demand total kW", "tail-gas heat used kW", "NET kW (+ surplus / - deficit)", "net if tail gas were heat"), rows))

    add("\n## 4. Closure checks (closure audit functions)\n")
    rows = []
    for r in results:
        if "error" in r:
            continue
        rows.append((r["feed"]["label"][:34], r["mode"], f"{max(r['h_rel'], r['o_rel'], r['n_rel']):.1e}", f"{r['loop_hon']:.1e}", r["ash_verdict"].split(" (")[0],
                     f"{r['c_res']:+.1e}", f"{r['unconv_recycle']:.3f}"))
    add(md_table(("feed", "mode", "GA-001 H,O,N max |rel|", "loop H,O,N max |rel|", "ash", "GA-001 carbon residual kg/h", "unconverted carbon from the recycle kg/h"), rows))

    add("\n## 5. ER sweep for PE and cotton only (0.20 / 0.25 / 0.30; reported, not chosen)\n")
    rows = []
    for r in sweep:
        if "error" in r:
            rows.append((r["feed"]["label"], r["mode"], r["er"], "MODEL REFUSES: " + r["error"], "", ""))
            continue
        rows.append((r["feed"]["label"], r["mode"], f"{r['er']:g}", f"{r['h2_kg_day']:.1f}", f"{r['net']:+.1f}", f"{r['pct']['H2']:.1f}/{r['pct']['CO']:.1f}/{r['pct']['N2']:.1f}"))
        csv_rows.append(("er_sweep", r["feed"]["label"], r["mode"], r["er"], "h2_kg_day", r["h2_kg_day"], "kg/day"))
    add(md_table(("feed", "mode", "ER", "H2 kg/day", "net heat kW", "gas dry mol % H2/CO/N2"), rows))

    add("\n## 6. NOT TESTABLE through the engine's inputs\n")
    add(md_table(("feed", "reason"), NOT_TESTABLE))
    report = "\n".join(L) + "\n"
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "feed_comparison.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(report)
    with open(os.path.join(OUT_DIR, "feed_comparison.csv"), "w", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerows(csv_rows)
    sys.stdout.reconfigure(encoding="utf-8")
    print(report)
    print(f"database / network calls made: {len(fake.calls)}")


if __name__ == "__main__":
    main()
