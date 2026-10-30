"""
Gasifying-agent comparison (task 3 of 3) -- READ-ONLY, offline. It changes nothing and ranks nothing.

What the model does today: GA-001 always gets AIR (O2 = ER x stoichiometric, N2 = O2 x 0.79/0.21, ga001_gasifier_model.py `solve_product_gas`) plus steam, and 99.3 % of its
product-gas N2 comes from that air. The registry also says "steam-blown, Fe2O3/Fe3O4 chemical looping oxygen carrier" (GA-001) and the registry's Expected composition has N2 10 %.
This script runs the SAME engine, feed, temperature (950 degC), conversion (0.90) and dry feed (37.5 kg/h) under other oxidants and reports what each would give.

How a scenario is run without editing GA-001: N2 is inert in `solve_product_gas` (it does not enter the water-gas-shift equilibrium or any element equation that fixes the other species), so the
solver's H2, CO, CO2, CH4, H2O for a given O2 amount are the same whatever carries that O2. The scenario therefore replaces the engine model ("GA-001","Outputs") (the engine's normal
override) by a wrapper that calls the UNCHANGED ga001_model and swaps only the N2 that came with the oxidant: N2 = fuel N2 + O2 x (1-f)/f, with f the O2 fraction of the oxidant
(f = 0.21 air, 0.30 / 0.50 enriched, 1.0 pure O2 or carrier oxygen). The corrected gas then flows through the real gas cleaning, WGS, PSA and tail-gas loop. Steam-only is the solver with
ER = 0 (an existing input). Energy uses balance_audit.gasifier_energy and heat_demands, with only the oxidant's sensible heat replaced.

    python scripts/run_agent_comparison.py          (from the repo root, about 3 minutes)

Writes outputs/agents/agent_comparison.md and .csv (outputs/ is git-ignored). Nothing is tuned: ER, steam ratio, conversion, temperature are the defaults except where a scenario names them.
"""
import csv
import os
import socket
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
if os.environ.get("HYGAS_ALLOW_DB_WRITES") == "1":
    sys.exit("Refusing to run: HYGAS_ALLOW_DB_WRITES=1 is set. This script never writes; unset it.")

from _fakes import FakeSupabase, patched_supabase       # noqa: E402
from python import balance_audit as ba                  # noqa: E402
from python import ga001_gasifier_model as ga001        # noqa: E402
from python import plant_status as ps                   # noqa: E402
from python import tab1_integration as t1               # noqa: E402

OUT_DIR = os.path.join(ROOT, "outputs", "agents")
N_CONV = 30
MODES = ("regasify", "heat_only")
AIR_O2_FRACTION = 0.21
REGISTRY_EXPECTED = {"H2": 32.5, "CO": 28.0, "CO2": 22.0, "CH4": 8.0, "N2": 10.0}      # SA-001 32-33 (midpoint), SA-002 28, SA-003 22, SA-004 8, SA-005 10 vol %
SPECIES = ("H2", "CO", "CO2", "CH4", "N2")
MID_LHV = 17.5                                                                         # DOK-ING midpoint (Assumed point) of the Confirmed 15-20 MJ/kg dry range

_real_getaddrinfo = socket.getaddrinfo


def _guard(host, *a, **k):
    if "supabase" in str(host).lower():
        raise RuntimeError(f"offline script refused to resolve {host!r}")
    return _real_getaddrinfo(host, *a, **k)


socket.getaddrinfo = _guard


def _const(v):
    def fn(get_input):
        return {"value": v, "status": ps.STATUS_ASSUMED, "inputs": [], "validation_basis": ps.VALIDATION_NA,
                "confidence_note": "AGENT COMPARISON ONLY (same pattern as tab1_integration's perturbation tests)."}
    return fn


# --- scenarios ------------------------------------------------------------------------------------------------------------
# o2_fraction: O2 share of the oxidant (None = the engine's own air path, untouched). er / steam: inputs left at the default when None.
SCENARIOS = [
    {"id": "S0", "name": "current: air ER 0.25 + steam 0.4", "o2_fraction": None, "er": None, "steam": None, "oxidant": "air"},
    {"id": "S1a", "name": "O2-enriched air, 30 % O2 + steam 0.4", "o2_fraction": 0.30, "er": None, "steam": None, "oxidant": "gas"},
    {"id": "S1b", "name": "O2-enriched air, 50 % O2 + steam 0.4", "o2_fraction": 0.50, "er": None, "steam": None, "oxidant": "gas"},
    {"id": "S2", "name": "oxygen-blown + steam 0.4 (same O2 as S0)", "o2_fraction": 1.0, "er": None, "steam": None, "oxidant": "gas"},
    {"id": "S3", "name": "chemical-looping equivalent (carrier oxygen = S0's O2, no N2, + steam 0.4)", "o2_fraction": 1.0, "er": None, "steam": None, "oxidant": "carrier"},
    {"id": "S4a", "name": "steam only (allothermal), steam 0.4", "o2_fraction": None, "er": 0.0, "steam": None, "oxidant": "none"},
    {"id": "S4b", "name": "steam only (allothermal), steam 0.8", "o2_fraction": None, "er": 0.0, "steam": 0.8, "oxidant": "none"},
]
ENRICHMENT_RANGE = (0.21, 1.0)           # Assumed: the O2 fraction of an enriched oxidant can lie anywhere between air and pure O2


# --- the wrapper (replaces the engine model ("GA-001","Outputs"); calls the unchanged ga001_model) --------------------------
def swap_oxidant_n2(out, fuel_n2_mol_h, o2_fraction):
    """Returns `out` (a GA-001 Outputs value) with the N2 that came with the oxidant replaced: N2 = fuel N2 + O2 x (1-f)/f. O2 is recovered from the air N2 the unchanged model
    put in (air N2 = O2 x 0.79/0.21). At f = 0.21 the result equals `out` (to rounding)."""
    nm3 = ga001.NM3_PER_MOL
    dry, wet = out["dry_flow_nm3_h"], out["wet_flow_nm3_h"]
    mol = {s: dry * out[f"{s}_mol_pct_dry"] / 100.0 / nm3 for s in SPECIES}
    h2o = (wet - dry) / nm3
    air_ratio = 0.79 / 0.21
    o2 = (mol["N2"] - fuel_n2_mol_h) / air_ratio
    ratio = air_ratio if o2_fraction == AIR_O2_FRACTION else (1.0 - o2_fraction) / o2_fraction
    mol["N2"] = fuel_n2_mol_h + o2 * ratio
    dry_n = sum(mol.values())
    wet_n = dry_n + h2o
    new = dict(out)
    new.update({"dry_flow_nm3_h": dry_n * nm3, "wet_flow_nm3_h": wet_n * nm3, "H2O_mol_pct_wet": 100.0 * h2o / wet_n})
    for s in SPECIES:
        new[f"{s}_mol_pct_dry"] = 100.0 * mol[s] / dry_n
    return new


def make_wrapper(o2_fraction):
    def fn(get_input):
        res = ga001.ga001_model(get_input)
        comp = get_input(("GA-001-INPUT", "feedstock_composition"))["value"]
        f = get_input(("GA-001-INPUT", "dry_feed_rate_kg_h"))["value"]
        fuel_n2 = (1.0 - ga001.ASH_FRACTION) * comp["N"] * f * 1000.0 / ga001.M_N / 2.0         # recycle brings no N (ga001 _RECYCLE_SPECIES_ATOMS)
        res = dict(res)
        res["value"] = swap_oxidant_n2(res["value"], fuel_n2, o2_fraction)
        res["confidence_note"] = res.get("confidence_note", "") + f" AGENT COMPARISON: oxidant N2 swapped for an O2 fraction of {o2_fraction}."
        return res
    return fn


def overrides_for(sc, mode):
    ov = {("GA-001-INPUT", "tail_gas_mode"): _const(mode)}
    if sc["er"] is not None:
        ov[("GA-001-INPUT", "equivalence_ratio")] = _const(sc["er"])
    if sc["steam"] is not None:
        ov[("GA-001-INPUT", "steam_to_feed_ratio")] = _const(sc["steam"])
    if sc["o2_fraction"] is not None:
        ov[("GA-001", "Outputs")] = make_wrapper(sc["o2_fraction"])
    return ov


# --- scenario quantities ------------------------------------------------------------------------------------------------------
def oxidant_moles(snapshot, previous, sc):
    """(O2, N2) mol/h of the oxidant that enters GA-001 in the scenario, from the closure audit's own air formula (O2) and the scenario's fraction."""
    d = ba.ga001_terms(snapshot, previous)
    o2 = d["air_o2_mol_h"]
    if sc["oxidant"] == "none":
        return 0.0, 0.0
    if sc["o2_fraction"] is None:
        return o2, d["air_n2_mol_h"]
    ratio = 0.79 / 0.21 if sc["o2_fraction"] == AIR_O2_FRACTION else (1.0 - sc["o2_fraction"]) / sc["o2_fraction"]
    return o2, o2 * ratio


def scenario_closure(snapshot, previous, sc):
    """C, H, O, N closure of the GA-001 control volume and of the gasification loop with the SCENARIO's oxidant N2 in the inflow (the audit's air N2 term is replaced)."""
    o2, n2 = oxidant_moles(snapshot, previous, sc)
    out = {}
    for label, terms in (("ga001", ba.ga001_terms(snapshot, previous)["terms"]), ("loop", ba.plant_terms(snapshot, previous, "loop")["terms"])):
        terms = [ba.make_term("oxidant N2 (scenario)", "in", {"N2": n2}, status=ps.STATUS_CALCULATED, source="scenario") if t["name"] == "air N2" else t for t in terms]
        terms = [ba.make_term("oxidant O2 (scenario)", "in", {"O2": o2}, status=ps.STATUS_CALCULATED, source="scenario") if t["name"] == "air O2" else t for t in terms]
        rows = ba.closure(terms)["rows"]
        out[label] = {e: rows[e]["rel"] for e in ("C", "H", "O", "N")}
        out[label + "_C_kg_h"] = rows["C"]["residual_kg_h"]
    return out


def scenario_energy(snapshot, previous, sc, lhv):
    """Gasifier duty and net heat at feed LHV `lhv` (MJ/kg dry). Reuses balance_audit.gasifier_energy (its air-sensible term is the S0 air) and heat_demands; only the oxidant's
    sensible heat is replaced: air/enriched/O2 are taken at the GA-004 200 degC (Assumed); carrier oxygen and steam-only have no gas-phase oxidant; the carrier's own heat terms are Missing."""
    g = ba.gasifier_energy(snapshot, previous, lhv)
    d = ba.ga001_terms(snapshot, previous)
    air_sens_s0 = g["in"][2]["kw"]
    o2, n2 = oxidant_moles(snapshot, previous, sc)
    sens = 0.0 if sc["oxidant"] in ("carrier", "none") else ba._sens_kw({"O2": o2, "N2": n2}, ba.GA004_AIR_PREHEAT_C)
    duty = g["implied_heat_duty_kw"] + air_sens_s0 - sens
    n_gs = d["terms"][4]["species"]["H2O"]
    hb005 = snapshot[("HB-005", "Steam")]["value"]["steam_kg_h"]
    evap = snapshot[("FE-005", "MoistureBalance")]["value"]["water_evaporated_kg_h"]
    demands = ba.heat_demands(n_gs, hb005, 0.0 if sc["oxidant"] in ("carrier", "none") else o2, 0.0 if sc["oxidant"] in ("carrier", "none") else n2, evap)
    return {"duty": duty, "demand": sum(t["kw"] for t in demands), "steam_kw": demands[0]["kw"] + demands[1]["kw"], "air_kw": demands[2]["kw"], "dry_kw": demands[3]["kw"],
            "cge_incl_recycle": g["cold_gas_efficiency_incl_recycle"], "cge_net": g["cold_gas_efficiency_net_of_recycle"], "feed_kw": g["in"][0]["kw"], "gas_chem_kw": g["out"][0]["kw"]}


def run_scenario(sc, mode, with_closure=True):
    ov = overrides_for(sc, mode)
    try:
        snap = t1.build_live_snapshot(n_cycles=N_CONV, overrides=ov)[0]
        prev = t1.build_live_snapshot(n_cycles=N_CONV - 1, overrides=ov)[0]
    except ValueError as exc:
        return {"sc": sc, "mode": mode, "error": str(exc)[:200]}
    g = snap[("GA-001", "Outputs")]["value"]
    eb = snap[("GA-001", "EnergyBalance")]["value"]
    tail = snap[("HB-009", "TailGas")]["value"]
    tail_used = eb["tail_gas"]["chemical_kw"] if mode == "heat_only" else 0.0
    r = {"sc": sc, "mode": mode, "pct": {s: g[f"{s}_mol_pct_dry"] for s in SPECIES}, "dry_flow": g["dry_flow_nm3_h"], "lhv": snap[("SA-006", "Reading")]["value"],
         "h2_kg_day": snap[("HB-012", "Compressor")]["value"]["h2_kg_h"] * 24.0, "cb": snap[("GA-001", "CarbonAccounting")]["value"]["carbon_black_kg_h"],
         "psa_feed": tail["tail_flow_nm3_h"] + tail["product_flow_nm3_h"], "psa_recovery": snap[("HB-006", "PSA")]["value"]["recovery"],
         "tail_available": eb["tail_gas"]["chemical_kw"], "tail_used": tail_used, "dev": {s: g[f"{s}_mol_pct_dry"] - REGISTRY_EXPECTED[s] for s in SPECIES}}
    r["energy"] = {lhv: scenario_energy(snap, prev, sc, lhv) for lhv in (15.0, MID_LHV, 20.0)}
    for lhv, e in r["energy"].items():
        e["net"] = tail_used - e["duty"] - e["demand"]
    if with_closure:
        r["closure"] = scenario_closure(snap, prev, sc)
    return r


def md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c).replace("|", "/") for c in r) + " |" for r in rows]
    return "\n".join(out)


# --- which scenario is consistent with which source statement (A1): facts about the SOURCES, not a ranking ---------------------
SOURCE_STATEMENTS = [
    ("GA-001 'Gasifier technology type': \"Bubbling Fluidized Bed (BFB), steam-blown, Fe2O3/Fe3O4 chemical looping oxygen carrier\" (registry)", "S3 (carrier oxygen, steam); S4 (steam-blown)", "S0, S1, S2 use gas-phase oxidant; the model's own S0 is air-blown"),
    ("GA-003 'Primary air flow rate (design)' 60 Nm3/h, 'Air-to-fuel equivalence ratio (ER)' 0.25, 'Steam flow rate (design)' 15 kg/h (registry)", "S0, S1 (an air or air-based oxidant)", "S2, S3, S4 have no air flow"),
    ("GA-003 ER remark: \"Partial oxidation for autothermal heat; majority of gasification still driven by steam reactions per DOK-ING's steam-blown spec\"", "S0, S1, S2 (partial oxidation + steam)", "S3 (oxygen from the carrier, not partial oxidation by gas), S4 (no oxidation)"),
    ("GA-004 'Air preheat temperature' 200 degC (registry)", "S0, S1 (air or enriched air)", "S2, S3, S4"),
    ("SA-005 'Expected N2 concentration' 10 vol %, 'Measurement principle': by difference; SA-001..004 expected H2 32-33, CO 28, CO2 22, CH4 8 (registry; 'Matches the value already used in the mass/energy balance dashboard')", "none reproduces the full set (see the deviation table); N2 near 10 % needs an oxidant N2 share far below air's", "see section 3 of the output"),
    ("RFI answers (data/dokink_rfi_answers.md)", "silent: no statement on air, steam, oxygen, carrier", "-"),
    ("Registry equipment inventory", "S0 (GA-003 air injection exists)", "S2: no air-separation / O2 unit is registered; S3: no air reactor, cyclone loop or carrier handling unit is registered"),
]


def main():
    fake = FakeSupabase()
    results = []
    with patched_supabase(fake):
        for sc in SCENARIOS:
            for mode in MODES:
                if sc["id"] == "S3":                        # same gas as S2 by construction (same oxygen, no N2): run for the closure and the energy treatment, composition identical
                    results.append(run_scenario(sc, mode))
                else:
                    results.append(run_scenario(sc, mode))
    assert fake.calls == [], fake.calls

    L, add = [], None
    add = L.append
    csv_rows = [("scenario", "mode", "quantity", "value", "unit")]
    add("# Gasifying-agent comparison -- measured output (no ranking, no recommendation)\n")
    add("Offline, in-process engine, in-memory fake store, 0 database / network calls. Same feed (default stand-in), 950 degC, conversion 0.90, 37.5 kg/h dry feed, 30 cycles. "
        "Scenarios override only ('GA-001','Outputs') (N2 swap, see the script docstring) or the ER / steam-ratio inputs. Energy at the DOK-ING midpoint LHV 17.5 MJ/kg (range 15 .. 20 in brackets). "
        "Oxidant preheat 200 degC (GA-004, Assumed). Missing in S2: the O2 source and its energy cost. Missing in S3: the air reactor, the carrier circulation, the carrier's oxygen-transfer enthalpy and sensible heat; "
        "its fuel-side gas is S2's by construction (the same oxygen amount, no N2). S4: the implied duty would have to be supplied externally (no source in the model).\n")

    add("## 1. Gas, hydrogen and load\n")
    rows = []
    for r in results:
        sc = r["sc"]
        if "error" in r:
            rows.append((sc["id"], r["mode"], "MODEL REFUSES: " + r["error"], "", "", "", "", "", ""))
            continue
        p = r["pct"]
        rows.append((sc["id"] + " " + sc["name"][:38], r["mode"], f"{p['H2']:.1f}/{p['CO']:.1f}/{p['CO2']:.1f}/{p['CH4']:.1f}/{p['N2']:.1f}", f"{r['dry_flow']:.1f}", f"{r['lhv']:.2f}",
                     f"{r['h2_kg_day']:.1f}", f"{r['cb']:.2f}", f"{r['psa_feed']:.1f}", f"{p['N2'] - 10.0:+.1f}"))
        for k in ("h2_kg_day", "lhv", "dry_flow"):
            csv_rows.append((sc["id"], r["mode"], k, r[k], ""))
        csv_rows.append((sc["id"], r["mode"], "N2_dry_pct", p["N2"], "%"))
    add(md_table(("scenario", "mode", "dry mol % H2/CO/CO2/CH4/N2", "dry flow Nm3/h", "LHV MJ/Nm3 (dry)", "H2 kg/day", "carbon black kg/h", "PSA feed Nm3/h", "N2 vs registry 10 % (pp)"), rows))

    add("\n## 2. Heat balance (kW; + surplus / - deficit; implied gasifier duty + = heat must be added)\n")
    rows = []
    for r in results:
        if "error" in r:
            continue
        e15, e17, e20 = (r["energy"][k] for k in (15.0, MID_LHV, 20.0))
        rows.append((r["sc"]["id"], r["mode"], f"{e17['duty']:+.1f} ({e15['duty']:+.1f} .. {e20['duty']:+.1f})", f"{e17['demand']:.1f}", f"{r['tail_used']:.1f}",
                     f"{e17['net']:+.1f} ({e15['net']:+.1f} .. {e20['net']:+.1f})", f"{e17['cge_incl_recycle']:.2f} / {e17['cge_net']:.2f}"))
        csv_rows.append((r["sc"]["id"], r["mode"], "net_heat_kw_mid", e17["net"], "kW"))
        csv_rows.append((r["sc"]["id"], r["mode"], "gasifier_duty_kw_mid", e17["duty"], "kW"))
    add(md_table(("scenario", "mode", "implied gasifier duty at 17.5 (15 .. 20)", "heat demand total (steam + preheat + drying)", "tail-gas heat used", "NET at 17.5 (15 .. 20)",
                  "cold-gas efficiency incl. / net of recycle (existing balance_audit definition)"), rows))
    add("\nS3's oxidant sensible heat is zero (no gas-phase oxidant) and the carrier's heat transfer is Missing, so its duty is the duty the circulating solids would have to bring from the air reactor, "
        "an unknown not modelled. S4's duty is the heat an external source must supply at 950 degC.\n")

    add("## 3. Registry 'Expected' composition: deviation of each scenario (pp, dry mol %; model minus expected H2 32.5 / CO 28 / CO2 22 / CH4 8 / N2 10)\n")
    rows = []
    for r in results:
        if "error" in r or r["mode"] != "regasify":
            continue
        d = r["dev"]
        rows.append((r["sc"]["id"], *(f"{d[s]:+.1f}" for s in SPECIES), f"{max(abs(v) for v in d.values()):.1f}"))
    add(md_table(("scenario (regasify)", "H2", "CO", "CO2", "CH4", "N2", "largest |deviation|"), rows))
    add("\nThe expected set sums to 100.5 (H2 given as 32-33); it implies, by the nitrogen balance, an air ER of about 0.04 for this feed (docs/gasifying_agent_study.md section 2). No scenario here is tuned to it.\n")

    add("## 4. Closure (GA-001 control volume and gasification loop, scenario oxidant in the inflow)\n")
    rows = []
    for r in results:
        if "error" in r:
            continue
        c = r["closure"]
        rows.append((r["sc"]["id"], r["mode"], *(f"{max(abs(c['ga001'][e]), abs(c['loop'][e])):.1e}" for e in ("C", "H", "O", "N"))))
    add(md_table(("scenario", "mode", "C max |rel|", "H max |rel|", "O max |rel|", "N max |rel|"), rows))

    add("\n## 5. Which scenario is consistent with which source statement (facts about the sources; not a ranking)\n")
    add(md_table(("source statement", "consistent with", "not consistent with"), SOURCE_STATEMENTS))
    report = "\n".join(L) + "\n"
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "agent_comparison.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(report)
    with open(os.path.join(OUT_DIR, "agent_comparison.csv"), "w", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerows(csv_rows)
    sys.stdout.reconfigure(encoding="utf-8")
    print(report)
    print(f"database / network calls made: {len(fake.calls)}")


if __name__ == "__main__":
    main()
