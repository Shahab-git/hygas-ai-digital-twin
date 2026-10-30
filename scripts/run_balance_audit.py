"""
Mass and energy closure audit -- READ-ONLY, offline.

Runs the existing engine in-process (tab1_integration.build_live_snapshot, the same entry point the UI uses) against the
in-memory fake store in tests/_fakes.py, so no database and no network are touched and the real secrets.toml is never read.
HYGAS_ALLOW_DB_WRITES stays unset. Prints the tables of parts A, B and C, and writes

    outputs/balance/balance_audit.md   (the full report)
    outputs/balance/balance_audit.csv  (one row per case / control volume / quantity)

and, only with --write-baseline, docs/balance_audit_baseline.json (the measured residuals, with the date and the commit; NOT a
CI gate -- a later task decides the tolerances).

    python scripts/run_balance_audit.py                    (from the repo root)
    python scripts/run_balance_audit.py --write-baseline

Nothing here fixes, plugs or tunes anything: a residual is a finding.
"""
import argparse
import csv
import datetime
import json
import os
import socket
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

os.environ.pop("HYGAS_ALLOW_DB_WRITES", None)           # stays unset: nothing here writes anywhere

from _fakes import FakeSupabase, patched_supabase       # noqa: E402
from python import balance_audit as ba                  # noqa: E402
from python import balance_audit_inventory as inv       # noqa: E402
from python import design_basis                         # noqa: E402
from python import ga001_gasifier_model as ga001        # noqa: E402
from python import plant_status as ps                   # noqa: E402
from python import tab1_integration as t1               # noqa: E402

OUT_DIR = os.path.join(ROOT, "outputs", "balance")
BASELINE = os.path.join(ROOT, "docs", "balance_audit_baseline.json")
N_FIVE = t1.DEFAULT_CYCLES                              # the default accumulated state (5)
N_CONV = 40                                             # the tail-gas recycle has converged (change < 1e-12 by cycle ~25)

_real_getaddrinfo = socket.getaddrinfo


def _guarded_getaddrinfo(host, *args, **kwargs):
    if "supabase" in str(host).lower():
        raise RuntimeError(f"run_balance_audit.py is offline; refused to resolve {host!r}")
    return _real_getaddrinfo(host, *args, **kwargs)


socket.getaddrinfo = _guarded_getaddrinfo


def _const(value):
    def fn(get_input):
        return {"value": value, "status": ps.STATUS_ASSUMED, "inputs": [], "validation_basis": ps.VALIDATION_NA,
                "confidence_note": "AUDIT SENSITIVITY CASE ONLY (same pattern as tab1_integration's perturbation tests)."}
    return fn


BASE_WET = 41.67        # fe_feed_handling.FE001_DEFAULT_DELIVERY_RATE_KG_H
BASE_DRY = 37.503       # FE-005 dry solids at the default (0.9 x 41.67)
CASES = [
    ("default", {}),
    ("ER 0.2125", {("GA-001-INPUT", "equivalence_ratio"): _const(0.2125)}),
    ("ER 0.2875", {("GA-001-INPUT", "equivalence_ratio"): _const(0.2875)}),
    ("feed -30 % at FE-001", {("FE-001-INPUT", "msw_delivery_rate_kg_h"): _const(BASE_WET * 0.7)}),
    ("feed +30 % at FE-001 (FE-003 clips to 50 kg/h = +20 %)", {("FE-001-INPUT", "msw_delivery_rate_kg_h"): _const(BASE_WET * 1.3)}),
    ("dry feed -30 % at GA-001", {("GA-001-INPUT", "dry_feed_rate_kg_h"): _const(BASE_DRY * 0.7)}),
    ("dry feed +30 % at GA-001", {("GA-001-INPUT", "dry_feed_rate_kg_h"): _const(BASE_DRY * 1.3)}),
    # carbon-bookkeeping task: the conversion sweep and the other tail-gas mode
    ("carbon conversion 0.85", {("GA-001-INPUT", "carbon_conversion_efficiency"): _const(0.85)}),
    ("carbon conversion 0.98", {("GA-001-INPUT", "carbon_conversion_efficiency"): _const(0.98)}),
    ("tail_gas_mode heat_only", {("GA-001-INPUT", "tail_gas_mode"): _const("heat_only")}),
]


def _git_commit():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except Exception:                                    # noqa: BLE001 -- the audit does not depend on git
        return "unknown"


def run_all(n_conv=N_CONV):
    fake = FakeSupabase()
    results = {}
    with patched_supabase(fake):
        for name, overrides in CASES:
            results[name] = {}
            for n in (N_FIVE, n_conv):
                snap, _s, _e = t1.build_live_snapshot(n_cycles=n, overrides=overrides or None)
                prev, _s2, _e2 = t1.build_live_snapshot(n_cycles=n - 1, overrides=overrides or None)
                kpis = t1.compute_tab1_kpis(snap)
                results[name][n] = {"snapshot": snap, "previous": prev, "audit": ba.audit_snapshot(snap, prev, kpis), "kpis": kpis}
    assert fake.calls == [], f"database access attempted: {fake.calls}"
    return results, fake


# --------------------------------------------------------------------------------------------------------------------------
# formatting
# --------------------------------------------------------------------------------------------------------------------------

def md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c).replace("|", "/").replace("\n", " ") for c in r) + " |")
    return "\n".join(out)


def ref_s(ref):
    f, ln, _ = ref
    return f"{f}:{ln}" if ln else f


def fmt(x, nd=4):
    if x is None:
        return "-"
    if isinstance(x, float):
        if x != 0 and abs(x) < 1e-3:
            return f"{x:.2e}"
        return f"{x:.{nd}f}"
    return str(x)


def balance_rows(label, bal):
    rows = []
    for key in ("C", "H", "O", "N", "ash", "mass"):
        r = bal["rows"][key]
        rows.append((label, key, fmt(r["in_kg_h"]), fmt(r["out_kg_h"]), f"{r['residual_kg_h']:+.4e}", f"{r['rel_pct']:+.4g}",
                     r["verdict"], "; ".join(r["missing_terms"]) if r["missing_terms"] else "-"))
    return rows


BAL_HEAD = ("control volume", "quantity", "in kg/h", "out kg/h", "residual kg/h", "% of inflow", "verdict", "Missing terms listed")


def terms_table(bal):
    rows = [(t["direction"], t["name"], t["status"], fmt(t["mass_kg_h"], 5) if t["mass_kg_h"] is not None else "MISSING", t["source"]) for t in bal["terms"]]
    return md_table(("dir", "term", "status", "mass kg/h", "source"), rows)


def build_report(results, n_conv, commit, started):
    L = []
    add = L.append
    base5 = results["default"][N_FIVE]
    base = results["default"][n_conv]
    snap, prev = base["snapshot"], base["previous"]

    add("# Mass and energy closure audit -- measured output\n")
    add(f"Generated {started} at commit `{commit}`. Offline: in-memory fake store, no database, no network, real secrets.toml never read; `HYGAS_ALLOW_DB_WRITES` unset.")
    add(f"States: **{N_FIVE}-cycle** = the engine's default accumulated state (tail-gas recycle still converging); **{n_conv}-cycle** = recycle converged. "
        "Nothing was fixed, plugged or tuned: every residual is a finding.\n")

    # ---------------- A
    add("## A. Inventory\n")
    add("### A1. GA-001 streams\n")
    add(md_table(("stream", "dir", "what the model uses", "status", "file:line", "closed by construction?"),
                 [(s[0], s[1], s[2], s[3], ref_s(s[4]), s[5]) for s in inv.GA001_STREAMS]))
    add("")
    for n in inv.GA001_CLOSURE_NOTES:
        add(f"- {n}")
    add("\n### A2. Every other unit\n")
    add(md_table(("unit", "streams in", "streams out", "conserved?", "file:line", "note"),
                 [(u[0], u[1], u[2], u[3], ref_s(u[4]), u[5]) for u in inv.UNIT_TABLE]))
    add("\n### A3. Mass or energy that appears or disappears without a stream (live values, converged state)\n")
    add(md_table(("item", "value", "unit", "status", "file:line", "effect"),
                 [(r[0], fmt(r[1]), r[2], r[3], ref_s(r[4]), r[5]) for r in inv.unaccounted_items(snap)]))
    add("\nHard-coded efficiencies, losses and constants:\n")
    add(md_table(("what", "value", "file:line", "effect"), [(h[0], h[1], ref_s(h[2]), h[3]) for h in inv.REGISTRY_HARD_CODES]))
    add("\n### A4. Feedstock composition\n")
    comp_entry = snap[("GA-001-INPUT", "feedstock_composition")]
    add(f"Default composition (`_input_feedstock_composition`, ga001_gasifier_model.py:549): dry ash-free mass fractions C/H/O/N = "
        f"{comp_entry['value']} -- status **{comp_entry['status']}**, validation basis `{comp_entry['validation_basis']}` (literature stand-in, not DOK-ING data).")
    add("\n`feedstock_composition_dokink_cross_check()` output, verbatim:\n")
    add("```json\n" + json.dumps(ga001.feedstock_composition_dokink_cross_check(), indent=1) + "\n```")
    add("\n`design_basis.get_feedstock_composition_ranges()` (DOK-ING Confirmed, RFI #2), verbatim:\n")
    add("```json\n" + json.dumps(design_basis.get_feedstock_composition_ranges(), indent=1) + "\n```")
    est = ba.feedstock_lhv_estimates()
    d = est["dry_wt_pct"]
    add(f"\nAgreement with DOK-ING's stated figures:\n")
    add(md_table(("DOK-ING stated", "this model", "agrees?", "comment"), [
        ("moisture about 10 % (5-15 %)", "FE-005 inlet 10 %, outlet 1 %", "yes", "moisture is not part of the composition; handled by FE-005"),
        ("ash about 10 % dry (5-15 %)", "10.0 % of dry feed", "yes", "Confirmed registry constant (GA-005)"),
        ("carbon at least 45 %", f"{d['C']:.1f} % of the dry feed incl. ash (50 % of the ash-free fuel)",
         "marginal", "the cross-check compares the ASH-FREE 50 % with the floor; on a dry-with-ash basis C is exactly 45.0 %, at the floor, not above it. DOK-ING gave no basis"),
        ("hydrogen at least 5 %", f"{d['H']:.1f} % of the dry feed incl. ash (6 % ash-free)", "yes", "passes on both bases"),
        ("dry LHV 15-20 MJ/kg", f"{est['range_MJ_kg'][0]:.2f}-{est['range_MJ_kg'][1]:.2f} MJ/kg (Dulong / Channiwala-Parikh from this composition, Estimated)",
         "borderline", "the Dulong estimate sits just below 15; the cross-check function does not test LHV at all"),
        ("oxygen, nitrogen", "O 43 %, N 1 % of the ash-free fuel", "cannot be checked", "DOK-ING gave neither"),
    ]))
    add("\nLHV estimate detail:\n```json\n" + json.dumps(est, indent=1, default=str) + "\n```")

    # ---------------- B
    add("\n## B. Mass balances\n")
    add("Verdicts: closes to numerical precision (< 1e-6 relative) / closes to a stated tolerance (< 0.1 % of inflow) / does not close / cannot be evaluated (Missing term). "
        "A row flagged with Missing terms is INCOMPLETE even when the modelled terms close: the listed terms are never treated as zero.\n")
    for n, title in ((n_conv, f"converged ({n_conv} cycles)"), (N_FIVE, f"default five-cycle state")):
        a = results["default"][n]["audit"]
        add(f"### B1/B2. Default inputs, {title}\n")
        rows = []
        rows += balance_rows("GA-001 (recycle = external feed)", a["ga001"])
        rows += balance_rows("gasification loop (recycle INSIDE)", a["loop"])
        rows += balance_rows("whole plant (wet MSW in, H2 out)", a["plant"])
        add(md_table(BAL_HEAD, rows))
        c = a["ga001_carbon"]
        add(f"\nCarbon detail (GA-001): total C {c['C_total_kg_h']:.4f} kg/h; in the gas {c['C_in_gas_kg_h']:.4f}; not in the gas {c['C_not_in_gas_kg_h']:.4f} "
            f"(= (1-0.90) x total C, of which {c['unconverted_share_of_recycle_C_kg_h']:.4f} is recycled CO/CH4 carbon); carbon-black stream {c['carbon_black_C_kg_h']:.4f}; "
            f"**unassigned carbon {c['unassigned_C_kg_h']:+.4f} kg/h**. Recycle cross-check (carbon implied by the published gas vs feed + recycle read): "
            f"relative difference {a['ga001_recycle_cross_check']['rel_diff']:.2e}.")
        s = a["storage"]
        add(f"HB-013 storage this cycle: level {s['previous_level_kg']:.4f} -> {s['level_kg']:.4f} kg, inflow {s['inflow_kg']:.4f}, outflow {s['outflow_kg']:.4f}; "
            f"expected without the clamp {s['expected_level_without_clamp_kg']:+.4f}; **H2 created (+) / destroyed (-) by the clamp: {s['h2_created_by_clamp_kg']:+.4f} kg** "
            f"({100 * s['rel_of_inflow']:.2f} % of the cycle's inflow) -- {s['verdict']}. FE-003 clipped surplus: {a['clipped_surplus_kg_h']:.3f} kg/h.\n")
    add("### Terms of the converged default balances\n")
    add("**GA-001 (recycle external):**\n")
    add(terms_table(base["audit"]["ga001"]))
    add("\n**Whole plant:**\n")
    add(terms_table(base["audit"]["plant"]))
    add("\n### B3. Does the residual depend on operation? (converged state, then five-cycle state)\n")
    rows = []
    for name, _ in CASES:
        for n in (n_conv, N_FIVE):
            a = results[name][n]["audit"]
            if a["missing_inputs"]:
                rows.append((name, n, "-", "-", "-", "-", "-", "-", f"cannot be evaluated: {a['missing_inputs']}"))
                continue
            g, lp, pl = a["ga001"]["rows"], a["loop"]["rows"], a["plant"]["rows"]
            rows.append((name, n, f"{g['C']['residual_kg_h']:+.4f} ({g['C']['rel_pct']:+.2f} %)", f"{g['H']['rel']:.1e}", f"{g['O']['rel']:.1e}", f"{g['N']['rel']:.1e}",
                         f"{lp['mass']['residual_kg_h']:+.4f}", f"{pl['mass']['residual_kg_h']:+.4f} ({pl['mass']['rel_pct']:+.3f} %)",
                         f"{a['storage']['h2_created_by_clamp_kg']:+.3f}"))
    add(md_table(("case", "cycles", "GA-001 C residual kg/h (% of C in)", "GA H rel", "GA O rel", "GA N rel", "loop mass residual kg/h", "plant mass residual kg/h (%)", "H2 created by storage clamp kg"), rows))

    # ---------------- C
    add("\n## C. Energy balances (kW; converged default state)\n")
    add("Basis: lower heating value + sensible heat above 25 degC, water VAPOUR at 25 degC = 0 (so liquid water is -44.0 kJ/mol). "
        "Constants: standard enthalpies of formation H2O(g) -241.826, H2O(l) -285.830, CO -110.525, CO2 -393.509, CH4 -74.873 kJ/mol (NIST-JANAF/CRC); "
        "the repo's own mean cp (gc_gas_cleaning_chain.py:106) and liquid-water cp (hb_wgs_psa_storage_chain.py:94). Feed LHV is evaluated at DOK-ING's Confirmed 15-20 MJ/kg dry "
        "(ends and midpoint) and at the model composition's own correlation estimate.\n")
    a = base["audit"]
    add("### C2. GA-001 energy (GA-001 computes NO heat duty: temperature enters only the WGS Keq, ga001_gasifier_model.py:314,230)\n")
    names = list(a["energy_gasifier"])
    first = a["energy_gasifier"][names[0]]
    add(md_table(("term", "dir") + tuple(f"{n.split(' (')[0]} kW" for n in names), (
        [(t["name"], "in") + tuple(fmt(a["energy_gasifier"][n]["in"][i]["kw"], 3) for n in names) for i, t in enumerate(first["in"])] +
        [(t["name"], "out") + tuple(fmt(a["energy_gasifier"][n]["out"][i]["kw"], 3) for n in names) for i, t in enumerate(first["out"])] +
        [("**sum in**", "") + tuple(fmt(a["energy_gasifier"][n]["sum_in_kw"], 3) for n in names),
         ("**sum out**", "") + tuple(fmt(a["energy_gasifier"][n]["sum_out_kw"], 3) for n in names),
         ("**implied heat duty (+ = gasifier must ADD heat)** -- Calculated, not part of the engine", "") + tuple(f"{a['energy_gasifier'][n]['implied_heat_duty_kw']:+.2f}" for n in names),
         ("implied duty, % of feed energy", "") + tuple(f"{a['energy_gasifier'][n]['implied_heat_duty_pct_of_feed']:+.1f}" for n in names),
         ("adiabatic temperature at the published composition, degC", "") + tuple(f"{a['energy_gasifier'][n]['adiabatic_temperature_c_fixed_composition']:.0f}" for n in names),
         ("cold-gas efficiency incl. recycle", "") + tuple(f"{a['energy_gasifier'][n]['cold_gas_efficiency_incl_recycle']:.3f}" for n in names),
         ("cold-gas efficiency net of recycle", "") + tuple(f"{a['energy_gasifier'][n]['cold_gas_efficiency_net_of_recycle']:.3f}" for n in names)])))
    add("\nMissing terms (listed, not zero): " + "; ".join(first["missing_terms"]) + ".\n")
    add("### C1. Whole-plant energy (boundary crossings; internal heat recovery cancels)\n")
    pn = list(a["energy_plant"])
    pf = a["energy_plant"][pn[0]]
    add(md_table(("term", "dir") + tuple(f"{n.split(' (')[0]} kW" for n in pn), (
        [(t["name"], "in") + tuple(fmt(a["energy_plant"][n]["in"][i]["kw"], 3) for n in pn) for i, t in enumerate(pf["in"])] +
        [(t["name"], "out") + tuple(fmt(a["energy_plant"][n]["out"][i]["kw"], 3) for n in pn) for i, t in enumerate(pf["out"])] +
        [("**sum in**", "") + tuple(fmt(a["energy_plant"][n]["sum_in_kw"], 3) for n in pn),
         ("**known energy out (non-heat)**", "") + tuple(fmt(a["energy_plant"][n]["sum_out_known_kw"], 3) for n in pn),
         ("**heat the balance says must be rejected** (in - known out)", "") + tuple(f"{a['energy_plant'][n]['implied_heat_rejected_kw']:.2f}" for n in pn),
         ("heat rejection the engine reports (GC-004 sensible + HB-012 power)", "") + tuple(f"{a['energy_plant'][n]['engine_reported_rejection_kw']:.2f}" for n in pn),
         ("**closure residual = balance - engine, kW**", "") + tuple(f"{a['energy_plant'][n]['closure_residual_kw']:+.2f}" for n in pn),
         ("closure residual, % of energy input", "") + tuple(f"{a['energy_plant'][n]['closure_residual_pct_of_input']:+.1f}" for n in pn)])))
    mid = a["energy_plant"][pn[1]]
    add("\nHeat rejection the engine omits (computed from the same constants, Calculated / Estimated; midpoint LHV):\n")
    add(md_table(("item", "kW", "status", "basis"), [(t["name"], fmt(t["kw"], 2), t["status"], t["source"]) for t in mid["residual_candidates_not_in_engine"]]
                 + [("**sum of the omitted rejections**", fmt(mid["candidates_sum_kw"], 2), "", "")]))
    add(f"\nThe omitted rejections ({mid['candidates_sum_kw']:.1f} kW) exceed the closure residual ({mid['closure_residual_kw']:+.1f} kW) by "
        f"{mid['candidates_sum_kw'] - mid['closure_residual_kw']:.1f} kW: they can only all be real if a heat INPUT of that size exists that the engine has no term for. "
        "The steam and drying duties below are the candidate:\n")
    add(md_table(("internal heat demand with no source in the engine", "kW", "status", "basis"),
                 [(t["name"], fmt(t["kw"], 2), t["status"], t["source"]) for t in mid["internal_heat_demands_not_sourced_in_engine"]]
                 + [("**sum**", fmt(mid["internal_heat_demand_sum_kw"], 2), "", f"the engine routes only HB-003's {mid['eu008_includes_hb003_cold_side_kw']:.1f} kW to feedwater")]))
    add("\nMissing plant-energy terms (listed, not zero): " + "; ".join(mid["missing_terms"]) + ".\n")
    e = a["efficiencies"]
    add("### C3. Efficiencies as reported vs as the balance implies\n")
    add(md_table(("quantity", "twin reports", "re-derived from its formula", "balance-implied", "formula / comment"), [
        ("H2 conversion efficiency (Integrated Plant Status)", f"{e['reported_overall_efficiency_pct_range'][0]:.1f}-{e['reported_overall_efficiency_pct_range'][1]:.1f} %",
         f"{e['re_derived_pct_range'][0]:.1f}-{e['re_derived_pct_range'][1]:.1f} %", f"{e['balance_implied_pct_range_feed_only'][0]:.1f}-{e['balance_implied_pct_range_feed_only'][1]:.1f} % (feed only)",
         e["reported_formula"]),
        ("same, with the electricity the plant uses in the denominator", "not reported", "-", f"{e['balance_implied_pct_range_incl_electricity'][0]:.1f}-{e['balance_implied_pct_range_incl_electricity'][1]:.1f} % ({e['electricity_counted_kw']:.1f} kW)",
         "the reported figure ignores electricity (and steam raising)"),
        ("H2 LHV used (kW)", f"{e['h2_kw_engine_basis']:.3f} (10.8 MJ/Nm3, EU-006)", "-", f"{e['h2_kw_balance_basis']:.3f} (241.826 kJ/mol)", f"difference {e['h2_lhv_basis_difference_pct']:+.2f} %"),
        ("H2 yield per kg dry feed", f"{e['reported_h2_yield_kg_per_kg_dry']:.4f}", "-", f"{e['h2_yield_fraction_of_maximum'] * 100:.1f} % of the stoichiometric maximum {e['h2_yield_stoichiometric_maximum_kg_per_kg_dry']:.4f}",
         e["h2_yield_formula"] + "; maximum: " + e["h2_yield_maximum_formula"]),
        ("cold-gas efficiency (GA-001)", "not reported", "-", f"{mid['lhv_mj_kg']:.1f} MJ/kg: " + ", ".join(f"{a['energy_gasifier'][n]['cold_gas_efficiency_incl_recycle']:.2f}" for n in names) + " (incl. recycle)",
         first["cold_gas_efficiency_formula"]),
    ]))
    add("\nmajor_losses as the twin lists them (tab1_integration.py:271-289): "
        + json.dumps({k: round(v, 3) for k, v in base["kpis"]["major_losses"]["value"].items()})
        + ". Its `cooling_tower_heat_rejected_kw` already contains the quench sensible duty and the compressor power, so the list double-counts if added.\n")
    return "\n".join(L) + "\n"


def csv_rows(results, n_conv, commit):
    rows = [("case", "cycles", "control_volume", "quantity", "unit", "in", "out", "residual", "rel_pct_of_inflow", "verdict", "complete", "commit")]
    for name, _ in CASES:
        for n in (n_conv, N_FIVE):
            a = results[name][n]["audit"]
            if a["missing_inputs"]:
                rows.append((name, n, "all", "all", "", "", "", "", "", f"cannot be evaluated: {a['missing_inputs']}", False, commit))
                continue
            for cv in ("ga001", "loop", "plant"):
                for q, r in a[cv]["rows"].items():
                    rows.append((name, n, cv, q, "kg/h", r["in_kg_h"], r["out_kg_h"], r["residual_kg_h"], r["rel_pct"], r["verdict"], r["complete"], commit))
            s = a["storage"]
            rows.append((name, n, "storage", "h2_created_by_clamp", "kg/cycle", s["inflow_kg"], s["outflow_kg"], s["h2_created_by_clamp_kg"], 100 * s["rel_of_inflow"], s["verdict"], True, commit))
            if "energy_plant" in a:
                for lname, e in a["energy_plant"].items():
                    rows.append((name, n, "plant energy", lname, "kW", e["sum_in_kw"], e["sum_out_known_kw"], e["closure_residual_kw"], e["closure_residual_pct_of_input"], "does not close" if abs(e["closure_residual_pct_of_input"]) > 0.1 else "closes", False, commit))
                for lname, e in a["energy_gasifier"].items():
                    rows.append((name, n, "GA-001 energy", lname, "kW", e["sum_in_kw"], e["sum_out_kw"], e["implied_heat_duty_kw"], e["implied_heat_duty_pct_of_feed"], "implied duty (Calculated, not part of the engine)", False, commit))
    return rows


def baseline_json(results, n_conv, commit, started):
    out = {"date": started, "commit": commit, "note": "Measured residuals, NOT a CI gate: a later task decides the tolerances. Regenerate with scripts/run_balance_audit.py --write-baseline.",
           "tolerances_used_for_verdicts": {"numerical": ba.TOL_NUMERICAL, "stated": ba.TOL_STATED}, "cases": {}}
    for name, _ in CASES:
        out["cases"][name] = {}
        for n in (n_conv, N_FIVE):
            a = results[name][n]["audit"]
            entry = {"missing_inputs": [list(k) for k in a["missing_inputs"]]}
            if not a["missing_inputs"]:
                for cv in ("ga001", "loop", "plant"):
                    entry[cv] = {q: {"residual_kg_h": r["residual_kg_h"], "rel": r["rel"], "verdict": r["verdict"]} for q, r in a[cv]["rows"].items()}
                entry["ga001_unassigned_carbon_kg_h"] = a["ga001_carbon"]["unassigned_C_kg_h"]
                entry["storage_h2_created_by_clamp_kg"] = a["storage"]["h2_created_by_clamp_kg"]
                if "energy_plant" in a:
                    entry["plant_energy_closure_residual_kw"] = {k: e["closure_residual_kw"] for k, e in a["energy_plant"].items()}
                    entry["ga001_implied_heat_duty_kw"] = {k: e["implied_heat_duty_kw"] for k, e in a["energy_gasifier"].items()}
            out["cases"][name][str(n)] = entry
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-baseline", action="store_true")
    ap.add_argument("--cycles", type=int, default=N_CONV)
    args = ap.parse_args()
    started = datetime.date.today().isoformat()
    commit = _git_commit()
    results, fake = run_all(args.cycles)
    report = build_report(results, args.cycles, commit, started)
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "balance_audit.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(report)
    with open(os.path.join(OUT_DIR, "balance_audit.csv"), "w", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerows(csv_rows(results, args.cycles, commit))
    if args.write_baseline:
        with open(BASELINE, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(baseline_json(results, args.cycles, commit, started), fh, indent=1)
            fh.write("\n")
    sys.stdout.reconfigure(encoding="utf-8")
    print(report)
    print(f"database / network calls made: {len(fake.calls)}")
    print(f"wrote {os.path.join(OUT_DIR, 'balance_audit.md')} and balance_audit.csv" + (f" and {BASELINE}" if args.write_baseline else ""))


if __name__ == "__main__":
    main()
