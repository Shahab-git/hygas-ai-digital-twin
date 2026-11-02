"""
Plant heat integration, stage 1 -- READ-ONLY, offline report. It changes nothing and chooses nothing.

Runs the unchanged engine (in-process, in-memory fake store, no database, no network) and evaluates the read-only inventory python/plant_heat_integration.py:
  1  the inventory (sinks, sources with their temperature levels, recovery, matching) for the default feed in both tail_gas_modes, converged (30 cycles);
  2  the heat balance at feed LHV 15, 17.5 and 20 MJ/kg dry (DOK-ING's range, Assumed midpoint);
  3  the five-cycle state against the converged state;
  4  cotton and polyethylene from the reference-feeds layer (each at its own LHV);
  5  the gasifying-agent scenarios S0 (air), S2 (oxygen-blown) and S4a (steam only) of docs/gasifying_agent_study.md (that study's override mechanism; GA-001 is not edited);
  6  one-at-a-time sensitivities of every Assumed constant (low and high of its range).
The Assumed values (recovery fractions, minimum approach, excess air, stack and ash temperatures) are the defaults of plant_heat_integration.ASSUMED. They are NOT chosen or tuned from
any result here; section 6 shows how far each one moves the answer.

    python scripts/run_heat_integration_report.py        (from the repo root, about 2 minutes)

Writes outputs/heat/heat_integration.md and .csv (outputs/ is git-ignored).
"""
import csv
import importlib.util
import os
import socket
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
if os.environ.get("HYGAS_ALLOW_DB_WRITES") == "1":
    sys.exit("Refusing to run: HYGAS_ALLOW_DB_WRITES=1 is set. This script never writes to a database; unset it.")

from _fakes import FakeSupabase, patched_supabase       # noqa: E402
from python import balance_audit as ba                  # noqa: E402
from python import plant_heat_integration as phi        # noqa: E402
from python import plant_status as ps                   # noqa: E402
from python import tab1_integration as t1               # noqa: E402

OUT_DIR = os.path.join(ROOT, "outputs", "heat")
N_CONV, N_SHORT = 30, 5
MODES = ("regasify", "heat_only")
LOW, MID, HIGH = "DOK-ING low (Confirmed range end)", "DOK-ING midpoint (Assumed point)", "DOK-ING high (Confirmed range end)"
FAKE = FakeSupabase()

_real_getaddrinfo = socket.getaddrinfo


def _guard(host, *a, **k):
    if "supabase" in str(host).lower():
        raise RuntimeError(f"offline script refused to resolve {host!r}")
    return _real_getaddrinfo(host, *a, **k)


socket.getaddrinfo = _guard


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def snapshot(overrides, n):
    with patched_supabase(FAKE):
        return t1.build_live_snapshot(n_cycles=n, overrides=overrides)[0]


def getter(snap):
    return lambda k: (snap[k] if k in snap and snap[k]["status"] != ps.STATUS_MISSING else None)


def md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    return "\n".join(out + ["| " + " | ".join(str(c).replace("|", "/") for c in r) + " |" for r in rows])


def f1(x):
    return "Missing" if x is None else f"{x:.1f}"


def case_row(label, mode, c):
    share = "-" if c["mismatch_share_of_unmet"] is None else f"{c['mismatch_share_of_unmet'] * 100:.0f} %"
    return [label, mode, f1(c["lhv_mj_kg"]), f1(c["demand_total_kw"]), f1(c["source_recovered_counted_kw"]), f1(c["net_energy_basis_kw"]), f1(c["matched_kw"]), f1(c["unmet_kw"]),
            f1(c["temperature_level_mismatch_kw"]), share, f1(c["supplementary_fuel_kw"]), f1(c["supplementary_fuel_as_h2_kg_day"])]


CASE_HEAD = ["case", "mode", "feed LHV MJ/kg", "demand kW", "recovered (counted) kW", "net, energy basis kW", "matched by level kW", "unmet kW (= supplementary fuel kW)",
             "level mismatch kW", "mismatch share of unmet", "supplementary fuel kW", "= H2 kg/day"]


def main():
    feeds = _load("run_feed_comparison", "scripts/run_feed_comparison.py")
    agents = _load("run_agent_comparison", "scripts/run_agent_comparison.py")
    const = feeds._const
    md, csv_rows = [], []

    def add(*lines):
        md.extend(lines)

    add("# Plant heat integration, stage 1 -- measured output (read-only; nothing is applied)", "",
        "Engine: unchanged, in-process, in-memory fake store (0 database / network calls). Basis: kW, LHV + sensible heat above 25 degC. `net, energy basis` = recovered counted sources - demand "
        "(levels ignored); `unmet` = demand that matching by temperature level could not serve; `level mismatch` = recovered heat that exists but cannot serve what is unmet for lack of "
        "level. The supplementary fuel is the unmet kW at 100 % burner efficiency (no efficiency is modelled), also as kg/day of hydrogen at its lower heating value, as a cost figure, NOT applied. "
        "Nothing here is tuned: the Assumed constants are the module defaults (section 6 shows how each moves the answer).", "")

    base = {}
    for mode in MODES:
        base[mode] = {"conv": snapshot({("GA-001-INPUT", "tail_gas_mode"): const(mode)}, N_CONV), "short": snapshot({("GA-001-INPUT", "tail_gas_mode"): const(mode)}, N_SHORT)}

    # 1 inventory ---------------------------------------------------------------------------------------------------------------------------
    add("## 1. Inventory: default feed, converged (30 cycles), DOK-ING midpoint LHV 17.5 MJ/kg", "")
    for mode in MODES:
        v = base[mode]["conv"][("PLANT", "HeatIntegration")]["value"]
        c = v["cases"][MID]
        add(f"### tail_gas_mode = {mode}", "", "Sinks (kW needed, delivery temperature):", "")
        add(md_table(["sink", "kW", "highest level degC", "status", "origin"], [[s["name"], f1(s["kw"]), f"{s['t_high_c']:.0f}", s["status"], s["origin"]] for s in v["sinks"]]), "")
        add(f"Steam demands are split over three temperature bands in proportion to named constants: " + ", ".join(f"{k} {x * 100:.1f} %" for k, x in v["steam_band_split"].items()) + " (Estimated). "
            f"EnergyBalance demand {f1(v['energy_balance_demand_kw'])} kW + additional process heat {f1(v['additional_process_heat_kw'])} kW. "
            "Missing sinks: " + "; ".join(m["name"] for m in v["missing_sinks"]) + ".", "")
        add("Sources (kW available, interval, recovery, recovered, matched, unused):", "")
        rows = []
        rec_of = {x["name"]: x["value"] for x in v["assumed_inputs"]}
        for s in v["sources"]:
            b = c["by_source"].get(s["name"], {})
            rows.append([s["name"], f1(s["kw_available"]), f"{s['t_low_c']:.0f} .. {s['t_high_c']:.0f}", "-" if not s["recovery_key"] else f"{rec_of[s['recovery_key']]:.2f}",
                         "yes" if s["counted"] else "no", f1(b.get("kw_recovered")), f1(b.get("kw_matched")), f1(b.get("kw_unused_level_or_surplus")), s["status"], s["grade"] or "-"])
        add(md_table(["source", "available kW", "released between degC", "recovery", "counted", "recovered kW", "matched kW", "unused kW", "status", "grade"], rows), "")
        flue = next(s for s in v["sources"] if s["name"].startswith("flue gas"))
        add(f"Flue gas: {flue['counted_reason']}. Stack loss {f1(flue.get('stack_loss_kw'))} kW; adiabatic flame {flue.get('adiabatic_temperature_c') and round(flue['adiabatic_temperature_c'])} degC.", "")
        add("Per sink (mid LHV): " + "; ".join(f"{n}: needed {f1(x['kw_needed'])}, matched {f1(x['kw_matched'])}, unmet {f1(x['kw_unmet'])}" for n, x in c["by_sink"].items()), "")

    # 2 LHV range ---------------------------------------------------------------------------------------------------------------------------
    rows = []
    for mode in MODES:
        cs = base[mode]["conv"][("PLANT", "HeatIntegration")]["value"]["cases"]
        for nm in (LOW, MID, HIGH):
            rows.append(case_row("default feed, converged", mode, cs[nm]))
            csv_rows.append(["lhv", "default feed, converged", mode] + rows[-1][2:])
    add("## 2. Heat balance over DOK-ING's feed LHV range (15 / 17.5 / 20 MJ/kg dry)", "", md_table(CASE_HEAD, rows), "")

    # 3 converged vs five cycles ------------------------------------------------------------------------------------------------------------
    rows = []
    for mode in MODES:
        for st in ("short", "conv"):
            c = base[mode][st][("PLANT", "HeatIntegration")]["value"]["cases"][MID]
            rows.append(case_row(f"default feed, {N_SHORT if st == 'short' else N_CONV} cycles", mode, c))
            csv_rows.append(["state", rows[-1][0], mode] + rows[-1][2:])
    add("## 3. Five-cycle state against the converged state (midpoint LHV)", "", md_table(CASE_HEAD, rows), "")

    # 4 feeds -------------------------------------------------------------------------------------------------------------------------------
    rows = []
    for feed in feeds.FEEDS:
        if feed["key"] not in ("default", "zhou_cotton", "zhou_pe"):
            continue
        for mode in MODES:
            ov = {("GA-001-INPUT", "tail_gas_mode"): const(mode)}
            if feed["comp"] is not None:
                ov[("GA-001-INPUT", "feedstock_composition")] = const(feed["comp"])
            snap = snapshot(ov, N_CONV)
            v = phi.compute(getter(snap), lhv_cases={"own LHV": feed["lhv_model_dry"]})
            if "missing_reason" in v:
                rows.append([feed["label"], mode, "Missing"] + [""] * 9)
                continue
            rows.append(case_row(feed["label"], mode, v["cases"]["own LHV"]))
            csv_rows.append(["feed", feed["label"], mode] + rows[-1][2:])
    add("## 4. Reference feeds at their own LHV (docs/reference_feeds.md; the feed energy is the feed's own LHV x 0.9)", "", md_table(CASE_HEAD, rows), "")

    # 5 agents ------------------------------------------------------------------------------------------------------------------------------
    rows = []
    for sc in agents.SCENARIOS:
        if sc["id"] not in ("S0", "S2", "S4a"):
            continue
        for mode in MODES:
            ov = agents.overrides_for(sc, mode)
            snap, prev = snapshot(ov, N_CONV), snapshot(ov, N_CONV - 1)
            d = ba.ga001_terms(snap, prev)
            o2, n2 = agents.oxidant_moles(snap, prev, sc)
            gasless = sc["oxidant"] in ("carrier", "none")
            demands = ba.heat_demands(d["terms"][4]["species"]["H2O"], snap[("HB-005", "Steam")]["value"]["steam_kg_h"], 0.0 if gasless else o2, 0.0 if gasless else n2,
                                      snap[("FE-005", "MoistureBalance")]["value"]["water_evaporated_kg_h"])
            v = phi.compute(getter(snap), lhv_cases={"mid": agents.MID_LHV}, demands=demands, duty_fn=lambda lhv, snap=snap, prev=prev, sc=sc: (agents.scenario_energy(snap, prev, sc, lhv)["duty"], ps.STATUS_CALCULATED))
            if "missing_reason" in v:
                rows.append([f"{sc['id']} {sc['name']}", mode, "Missing"] + [""] * 9)
                continue
            rows.append(case_row(f"{sc['id']} {sc['name']}", mode, v["cases"]["mid"]))
            csv_rows.append(["agent", rows[-1][0], mode] + rows[-1][2:])
    add("## 5. Gasifying-agent scenarios (midpoint LHV; the oxidant's sensible heat is replaced as in docs/gasifying_agent_study.md)", "",
        "Missing in S2: heat or electricity for the air-separation unit; S4a: the heat that supplies the allothermal duty is the `implied gasifier heat duty` sink at the gasifier temperature. "
        "S2 and S4a gas compositions come from the study's override of the oxidant N2 (GA-001 is not edited).", "", md_table(CASE_HEAD, rows), "")

    # 6 sensitivities -----------------------------------------------------------------------------------------------------------------------
    rows = []
    for mode in MODES:
        get = getter(base[mode]["conv"])
        ref = phi.compute(get)["cases"][MID]
        for name, spec in phi.ASSUMED.items():
            for tag, val in (("low", spec["low"]), ("high", spec["high"])):
                c = phi.compute(get, assumptions={name: val})["cases"][MID]
                rows.append([mode, name, f"{spec['value']:g}", f"{tag} {val:g}", f1(c["unmet_kw"]), f"{c['unmet_kw'] - ref['unmet_kw']:+.1f}", f1(c["supplementary_fuel_as_h2_kg_day"]),
                             f1(c["temperature_level_mismatch_kw"])])
                csv_rows.append(["sensitivity", name, mode, tag, val, c["unmet_kw"], c["unmet_kw"] - ref["unmet_kw"]])
    add("## 6. One-at-a-time sensitivities of the Assumed constants (default feed, converged, midpoint LHV; unmet kW at the module default is the reference)", "",
        md_table(["mode", "constant", "default", "set to", "unmet kW", "change vs default kW", "= H2 kg/day", "level mismatch kW"], rows), "",
        "## 7. Missing terms (not zero)", "", "\n".join(f"- {t}" for t in phi.MISSING_TERMS), "")

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "heat_integration.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(md) + "\n")
    with open(os.path.join(OUT_DIR, "heat_integration.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["section", "label", "mode", "c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8", "c9", "c10"])
        w.writerows(csv_rows)
    print("\n".join(md))
    print(f"\nwrote {os.path.join(OUT_DIR, 'heat_integration.md')} and .csv; database calls through the in-memory fake: {len(FAKE.calls)}")


if __name__ == "__main__":
    main()
