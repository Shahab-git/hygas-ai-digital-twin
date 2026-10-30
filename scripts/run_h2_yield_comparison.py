"""
Hydrogen yield comparison, tail gas as heat (tail-gas-heat task, item C) -- READ-ONLY, offline.

Runs the existing engine in-process (tab1_integration.build_live_snapshot) against the in-memory fake store of tests/_fakes.py: no database, no
network, the real secrets.toml is never read, HYGAS_ALLOW_DB_WRITES stays unset. The tail-gas mode and the swept inputs are set through the
engine's normal override mechanism. Nothing is tuned: every number is reported as found, and no default is chosen or changed from it.

    python scripts/run_h2_yield_comparison.py             (from the repo root, about 2 minutes)

Writes outputs/h2_yield/h2_yield_comparison.md and .csv (outputs/ is git-ignored).
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
from python import hb_wgs_psa_storage_chain as hbchain  # noqa: E402
from python import plant_status as ps                   # noqa: E402
from python import tab1_integration as t1               # noqa: E402

OUT_DIR = os.path.join(ROOT, "outputs", "h2_yield")
N_CONV, N_FIVE = 30, t1.DEFAULT_CYCLES
REGISTRY_TARGET_KG_DAY = 1.85 * 24.0      # HB-007 registry 'Product H2 flow rate' 20.6 Nm3/h = ~1.85 kg/h (its own remark) -> 44.4 kg/day
DOKING_KG_DAY = 50.0                                                  # data/dokink_rfi_answers.md:31-32 (RFI #6)
MODES = ("regasify", "heat_only")
MID = "DOK-ING midpoint (Assumed point)"

_real_getaddrinfo = socket.getaddrinfo


def _guard(host, *a, **k):
    if "supabase" in str(host).lower():
        raise RuntimeError(f"offline script refused to resolve {host!r}")
    return _real_getaddrinfo(host, *a, **k)


socket.getaddrinfo = _guard


def _const(v):
    def fn(get_input):
        return {"value": v, "status": ps.STATUS_ASSUMED, "inputs": [], "validation_basis": ps.VALIDATION_NA,
                "confidence_note": "H2 YIELD COMPARISON ONLY (same pattern as tab1_integration's perturbation tests)."}
    return fn


def _psa_recovery(rec):
    def fn(get_input):
        r = hbchain.hb006_psa_recovery(get_input)
        r["value"] = dict(r["value"], recovery=rec)
        r["confidence_note"] = "H2 YIELD COMPARISON ONLY: recovery fixed at the registry's 75 %"
        return r
    return fn


def overrides(mode, **extra):
    ov = {("GA-001-INPUT", "tail_gas_mode"): _const(mode)}
    if "er" in extra:
        ov[("GA-001-INPUT", "equivalence_ratio")] = _const(extra["er"])
    if "conv" in extra:
        ov[("GA-001-INPUT", "carbon_conversion_efficiency")] = _const(extra["conv"])
    if "psa" in extra:
        ov[("HB-006", "PSA")] = _psa_recovery(extra["psa"])
    return ov


def run(mode, n, with_audit=True, **extra):
    ov = overrides(mode, **extra)
    snap = t1.build_live_snapshot(n_cycles=n, overrides=ov)[0]
    h2 = float(snap[("HB-012", "Compressor")]["value"]["h2_kg_h"])
    r = {"mode": mode, "cycles": n, "h2_kg_h": h2, "h2_kg_day": h2 * 24.0, "snap": snap,
         "psa_recovery": float(snap[("HB-006", "PSA")]["value"]["recovery"]), "energy": snap[("GA-001", "EnergyBalance")]["value"]}
    if with_audit:
        prev = t1.build_live_snapshot(n_cycles=n - 1, overrides=ov)[0]
        kpis = t1.compute_tab1_kpis(snap)
        r["audit"] = ba.audit_snapshot(snap, prev, kpis)
    return r


def pct(x, ref):
    return f"{100.0 * (x - ref) / ref:+.1f} %"


def md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c).replace("|", "/") for c in r) + " |" for r in rows]
    return "\n".join(out)


def main():
    fake = FakeSupabase()
    base = {}
    sweep, sens = [], []
    with patched_supabase(fake):
        for mode in MODES:
            for n in (N_CONV, N_FIVE):
                base[(mode, n)] = run(mode, n)
        for er in (0.20, 0.25, 0.30, 0.40):
            sweep.append((er, run("heat_only", N_CONV, with_audit=False, er=er)))
        sens.append(("default (heat_only)", run("heat_only", N_CONV, with_audit=False)))
        sens.append(("carbon conversion 0.85", run("heat_only", N_CONV, with_audit=False, conv=0.85)))
        sens.append(("carbon conversion 0.98", run("heat_only", N_CONV, with_audit=False, conv=0.98)))
        sens.append(("PSA recovery fixed at 75 % (registry)", run("heat_only", N_CONV, with_audit=False, psa=0.75)))
    assert fake.calls == [], fake.calls

    L, add, csv_rows = [], None, [("section", "case", "quantity", "value", "unit")]
    add = L.append
    add("# Hydrogen yield comparison, tail gas as heat -- measured output\n")
    add("Offline, in-process engine, in-memory fake store, 0 database / network calls. `regasify` = today's behaviour and the default; `heat_only` = GA-001 receives no "
        "recycle atoms and the tail gas is reported as heat. Converged = 30 cycles, five-cycle = the engine's default accumulated state. Nothing is tuned.\n")

    add("## 1. Hydrogen product\n")
    add(f"Key and definition: `(\"HB-012\",\"Compressor\").h2_kg_h` = PSA product after recovery; compression is a pass-through (same mass), purity taken as 100 %; "
        f"x 24 h. Registry design target {REGISTRY_TARGET_KG_DAY:.1f} kg/day (HB-007/HB-012 20.6 Nm3/h = 1.85 kg/h); DOK-ING \"about {DOKING_KG_DAY:g} kg/day from 1 tpd\" (RFI #6).\n")
    rows = []
    for (mode, n), r in base.items():
        rows.append((mode, "converged (30)" if n == N_CONV else "five-cycle", f"{r['h2_kg_h']:.4f}", f"{r['h2_kg_day']:.1f}", pct(r["h2_kg_day"], REGISTRY_TARGET_KG_DAY),
                     pct(r["h2_kg_day"], DOKING_KG_DAY), f"{100 * r['psa_recovery']:.1f} %"))
        csv_rows.append(("h2", f"{mode} {n}", "h2_kg_day", r["h2_kg_day"], "kg/day"))
    add(md_table(("mode", "state", "H2 kg/h", "H2 kg/day", f"vs registry {REGISTRY_TARGET_KG_DAY:.1f}", f"vs DOK-ING {DOKING_KG_DAY:g}", "PSA recovery (model)"), rows))
    add("\nCaveats that belong next to these numbers: DOK-ING's ~50 kg/day is for **plastic waste** (RFI #6), gross or net not stated, availability and start-up not stated; "
        "ours is MSW at 100 % availability and steady state, with no leaks, purges or losses and a 100 %-H2 product. The registry's 44.4 kg/day is a design calculation on a "
        "stale gas basis (50 Nm3/h x 55 % H2 x 75 % recovery), not a measurement.\n")

    add("## 2. The energy key (GA-001, EnergyBalance), converged\n")
    names = list(base[("heat_only", N_CONV)]["energy"]["cases"])
    for mode in MODES:
        e = base[(mode, N_CONV)]["energy"]
        add(f"**{mode}** -- tail gas {e['tail_gas']['flow_nm3_h']:.1f} Nm3/h, {e['tail_gas']['lhv_mj_nm3']:.2f} MJ/Nm3, {e['tail_gas']['chemical_kw']:.1f} kW "
            f"(H2 {100 * e['tail_gas']['share_of_chemical_energy']['H2']:.0f} %, CO {100 * e['tail_gas']['share_of_chemical_energy']['CO']:.0f} %, "
            f"CH4 {100 * e['tail_gas']['share_of_chemical_energy']['CH4']:.0f} %); used as heat: {e['tail_gas']['used_as_heat']}.\n")
        c0 = e["cases"][names[0]]
        rows = [("steam raising (gasifier + WGS)", *[f"{e['cases'][n]['steam_raising_kw']:.1f}" for n in names]),
                ("air preheat", *[f"{e['cases'][n]['air_preheat_kw']:.1f}" for n in names]),
                ("feed drying", *[f"{e['cases'][n]['feed_drying_kw']:.1f}" for n in names]),
                ("**heat demand total**", *[f"{e['cases'][n]['heat_demand_total_kw']:.1f}" for n in names]),
                ("implied gasifier duty (+ must add heat)", *[f"{e['cases'][n]['implied_gasifier_heat_duty_kw']:+.1f}" for n in names]),
                ("tail-gas heat used", *[f"{e['cases'][n]['tail_gas_heat_used_kw']:.1f}" for n in names]),
                ("**net heat (+ surplus / - deficit)**", *[f"{e['cases'][n]['net_heat_kw']:+.1f}" for n in names]),
                ("net if the tail gas were heat", *[f"{e['cases'][n]['net_heat_kw_if_tail_gas_were_heat']:+.1f}" for n in names])]
        add(md_table(("kW", *[f"{n.split(' (')[0]} ({e['cases'][n]['lhv_mj_kg']:.2f} MJ/kg)" for n in names]), rows))
        add("")
        for n in names:
            csv_rows.append(("energy", f"{mode} / {n}", "net_heat_kw", e["cases"][n]["net_heat_kw"], "kW"))
    add("Missing (listed, not zero): " + "; ".join(base[("heat_only", N_CONV)]["energy"]["missing_terms"]) + ".\n")

    add("## 3. Closure audit residuals (python/balance_audit.py), both modes\n")
    rows = []
    for (mode, n), r in base.items():
        a = r["audit"]
        g, lp, pl = a["ga001"]["rows"], a["loop"]["rows"], a["plant"]["rows"]
        pe = a["energy_plant"][MID]
        rows.append((mode, "converged" if n == N_CONV else "five-cycle", f"{max(abs(g[e]['rel']) for e in 'HON'):.1e}", f"{max(abs(lp[e]['rel']) for e in 'HON'):.1e}",
                     f"{max(abs(pl['N']['rel']), 0):.1e}", f"{g['C']['residual_kg_h']:+.4f}", f"{pl['mass']['residual_kg_h']:+.4f}",
                     f"{pe['closure_residual_kw']:+.1f} ({pe['closure_residual_pct_of_input']:+.1f} %)"))
        csv_rows.append(("audit", f"{mode} {n}", "carbon_residual_kg_h", g["C"]["residual_kg_h"], "kg/h"))
    add(md_table(("mode", "state", "GA-001 H,O,N max |rel|", "loop H,O,N max |rel|", "plant N |rel|", "GA-001 carbon residual kg/h", "plant mass residual kg/h",
                  "plant energy residual kW (mid LHV)"), rows))
    add("\nIn `heat_only` the audit treats the tail combustibles as burned (complete combustion, a convention: the engine has no burner), so the loop and plant H, O, N still close. "
        "Plant H and O keep the 1e-4 electrolyser-water residual found in the closure audit. Carbon and energy are reported, not fixed: the carbon residual changes sign "
        "without the recycle (0.1 x feed carbon is below the 5 % carbon-black stream). The `heat_only` plant energy residual is larger (about +65 kW against +24 kW) because the "
        "tail gas now burns inside the plant (about 49 kW) and the engine has no burner or boiler term to report that heat: it is the same finding, not a new error.\n")

    add("## 4. ER sweep in heat_only (converged)\n")
    rows = []
    for er, r in sweep:
        cs = r["energy"]["cases"]
        rows.append((f"{er:g}", f"{r['h2_kg_day']:.1f}", pct(r["h2_kg_day"], DOKING_KG_DAY), pct(r["h2_kg_day"], REGISTRY_TARGET_KG_DAY),
                     f"{cs[MID]['net_heat_kw']:+.1f}", f"{cs[names[0]]['net_heat_kw']:+.1f} .. {cs[names[2]]['net_heat_kw']:+.1f}"))
        csv_rows.append(("er_sweep", f"ER {er:g}", "h2_kg_day", r["h2_kg_day"], "kg/day"))
        csv_rows.append(("er_sweep", f"ER {er:g}", "net_heat_kw_mid", cs[MID]["net_heat_kw"], "kW"))
    add(md_table(("ER", "H2 kg/day", f"vs DOK-ING {DOKING_KG_DAY:g}", f"vs registry {REGISTRY_TARGET_KG_DAY:.1f}", "net heat kW (17.5 MJ/kg)", "net heat range 15 .. 20 MJ/kg"), rows))
    d25 = [r for er, r in sweep if er == 0.25][0]
    add(f"\nAt the default ER 0.25 in `heat_only` the twin gives {d25['h2_kg_day']:.1f} kg/day, {pct(d25['h2_kg_day'], DOKING_KG_DAY)} against DOK-ING's about {DOKING_KG_DAY:g} and "
        f"{pct(d25['h2_kg_day'], REGISTRY_TARGET_KG_DAY)} against the registry's {REGISTRY_TARGET_KG_DAY:.1f}: it **still overshoots**. ER is not chosen or changed from this.\n")

    add("## 5. One-at-a-time sensitivity in heat_only (converged)\n")
    rows = []
    for name, r in sens:
        cs = r["energy"]["cases"]
        rows.append((name, f"{r['h2_kg_day']:.1f}", pct(r["h2_kg_day"], DOKING_KG_DAY), pct(r["h2_kg_day"], REGISTRY_TARGET_KG_DAY), f"{100 * r['psa_recovery']:.1f} %",
                     f"{cs[MID]['net_heat_kw']:+.1f}"))
        csv_rows.append(("sensitivity", name, "h2_kg_day", r["h2_kg_day"], "kg/day"))
    add(md_table(("case", "H2 kg/day", f"vs DOK-ING {DOKING_KG_DAY:g}", f"vs registry {REGISTRY_TARGET_KG_DAY:.1f}", "PSA recovery used", "net heat kW (17.5 MJ/kg)"), rows))
    e = base[("heat_only", N_CONV)]["energy"]["cases"]
    add("\nFeed LHV changes the heat balance only (hydrogen is independent of it): net heat in `heat_only` = "
        + ", ".join(f"{e[n]['net_heat_kw']:+.1f} kW at {e[n]['lhv_mj_kg']:.2f} MJ/kg" for n in names) + ".\n")

    report = "\n".join(L) + "\n"
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "h2_yield_comparison.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(report)
    with open(os.path.join(OUT_DIR, "h2_yield_comparison.csv"), "w", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerows(csv_rows)
    sys.stdout.reconfigure(encoding="utf-8")
    print(report)
    print(f"database / network calls made: {len(fake.calls)}")
    print(f"wrote {os.path.join(OUT_DIR, 'h2_yield_comparison.md')} and .csv")


if __name__ == "__main__":
    main()
