"""
Closure audit of scenario snapshots (task A5) -- READ-ONLY. Pure functions over published snapshots; no engine edit, no balancing term, no tolerance.

balance_audit.audit_snapshot() can be called on ANY snapshot unchanged, including those of the gasifying-agent scenarios (scripts/run_agent_comparison.py) and the
reference feeds (python/reference_feeds.py + scripts/run_feed_comparison.py): none of them needs an engine edit, and no blocking Missing input appears. But the stock audit
re-derives the oxidant as AIR (N2 = O2 x 0.79 / 0.21). In the scenarios that swap the oxidant's N2 (O2-enriched air, pure oxygen, carrier oxygen) that inflow is simply not the
scenario's, so the stock N and mass rows show an artefact (relative N residual 0.99 for pure oxygen), not a model residual. `audit_case` therefore reports BOTH: the stock rows
(unedited) and the rows with the scenario's own oxidant terms substituted for the audit's air terms, which is what the gasifying-agent study already did for its closure columns.
The substitution replaces two inflow terms (air O2, air N2) by the scenario's O2 and N2; nothing is added to make a case pass.

Energy: the gasifier's implied heat duty is balance_audit.gasifier_energy with only the oxidant's sensible heat replaced (the method of run_agent_comparison.scenario_energy);
the plant energy residual is balance_audit.plant_energy unchanged (air enters at ambient and is not a boundary energy term). The Missing terms are listed per case, never zero.
"""
from . import balance_audit as ba
from . import balance_closure_kind as bck
from . import plant_status as ps

AIR_O2_FRACTION = 0.21
OXIDANT_AIR, OXIDANT_GAS, OXIDANT_CARRIER, OXIDANT_NONE = "air", "gas", "carrier", "none"

# Energy terms that exist for a scenario's oxidant or heat supply but are not in the engine (listed, never zero)
SCENARIO_MISSING_TERMS = {
    OXIDANT_AIR: [],
    OXIDANT_GAS: ["heat or electricity for the air-separation / oxygen-enrichment unit (no ASU model; no such unit is in the registry)"],
    OXIDANT_CARRIER: ["heat and circulation power of the oxygen-carrier loop (air reactor, cyclone, carrier heat balance, make-up): the carrier's own heat terms are Missing"],
    OXIDANT_NONE: ["the heat supply of the allothermal duty (the implied gasifier duty has no source in the engine)"],
}


def oxidant_moles(snapshot, previous, oxidant, o2_fraction):
    """(O2, N2) mol/h of the oxidant that enters GA-001 in the scenario: the audit's own air-O2 formula and the scenario's O2 fraction (None = the engine's own air path)."""
    d = ba.ga001_terms(snapshot, previous)
    o2 = d["air_o2_mol_h"]
    if oxidant == OXIDANT_NONE:
        return 0.0, 0.0
    if o2_fraction is None:
        return o2, d["air_n2_mol_h"]
    ratio = 0.79 / 0.21 if o2_fraction == AIR_O2_FRACTION else (1.0 - o2_fraction) / o2_fraction
    return o2, o2 * ratio


def with_oxidant(terms, o2, n2):
    """The term list with the audit's air O2 / air N2 inflow replaced by the scenario's oxidant O2 / N2 (the only change)."""
    out = []
    for t in terms:
        if t["name"] == "air N2":
            t = ba.make_term("oxidant N2 (scenario)", "in", {"N2": n2}, status=ps.STATUS_CALCULATED, source="scenario oxidant N2 (python/balance_scenarios.py)")
        elif t["name"] == "air O2":
            t = ba.make_term("oxidant O2 (scenario)", "in", {"O2": o2}, status=ps.STATUS_CALCULATED, source="scenario oxidant O2 (python/balance_scenarios.py)")
        out.append(t)
    return out


def _row_view(r):
    keys = ("in_kg_h", "out_kg_h", "residual_kg_h", "rel", "rel_pct", "verdict", "complete", "missing_terms", "closure_kind", "closure_why", "closure_refs")
    return {k: r[k] for k in keys if k in r}


def scenario_rows(snapshot, previous, o2, n2):
    """The GA-001, loop and plant closure rows with the scenario's oxidant substituted for the audit's air terms. Raises ba.AuditInputMissing like the stock audit."""
    out = {}
    for cv, terms in (("ga001", ba.ga001_terms(snapshot, previous)["terms"]), ("loop", ba.plant_terms(snapshot, previous, "loop")["terms"]),
                      ("plant", ba.plant_terms(snapshot, previous, "plant")["terms"])):
        out[cv] = bck.annotate_rows(cv, ba.closure(with_oxidant(terms, o2, n2))["rows"])
    return out


def _gasifier_duty_adjusted(snapshot, previous, lhv, oxidant, o2, n2):
    """Implied gasifier duty with only the oxidant's sensible heat replaced (carrier oxygen and steam-only have no gas-phase oxidant)."""
    g = ba.gasifier_energy(snapshot, previous, lhv)
    air_sens_stock = g["in"][2]["kw"]
    sens = 0.0 if oxidant in (OXIDANT_CARRIER, OXIDANT_NONE) else ba._sens_kw({"O2": o2, "N2": n2}, ba.GA004_AIR_PREHEAT_C)
    duty = g["implied_heat_duty_kw"] + air_sens_stock - sens
    return g, duty


def audit_case(snapshot, previous, kpis, oxidant=OXIDANT_AIR, o2_fraction=None, lhv_cases=None):
    """One case. `lhv_cases` = {label: MJ/kg dry}; default ba.lhv_cases() (DOK-ING 15 / 17.5 / 20 MJ/kg and the model composition's own estimate).

    Returns {"missing_inputs": [...], "oxidant": {...}, "rows": {cv: {quantity: row}}, "stock_rows": {...} (only when the oxidant was substituted),
    "storage": {...}, "energy_gasifier": {label: {...}}, "energy_plant": {label: {...}}, "energy_missing_terms": {...}}. Nothing is skipped silently: a blocking
    Missing input is returned in `missing_inputs` and the case carries no rows."""
    lhvs = lhv_cases if lhv_cases is not None else ba.lhv_cases()
    stock = ba.audit_snapshot(snapshot, previous, None)
    res = {"missing_inputs": [list(k) for k in stock["missing_inputs"]], "oxidant": {"kind": oxidant, "o2_fraction": o2_fraction}}
    if stock["missing_inputs"]:
        return res
    substituted = oxidant in (OXIDANT_GAS, OXIDANT_CARRIER) and o2_fraction is not None
    o2, n2 = oxidant_moles(snapshot, previous, oxidant, o2_fraction)
    res["oxidant"].update({"o2_mol_h": o2, "n2_mol_h": n2, "substituted_for_the_audit_air_terms": substituted})
    stock_rows = {cv: {q: _row_view(r) for q, r in stock[cv]["rows"].items()} for cv in ("ga001", "loop", "plant")}
    if substituted:
        res["rows"] = {cv: {q: _row_view(r) for q, r in rows.items()} for cv, rows in scenario_rows(snapshot, previous, o2, n2).items()}
        res["stock_rows"] = stock_rows
    else:
        res["rows"] = stock_rows
    res["ash_note"] = "ash closes on ASH_FRACTION x dry feed on both sides (a constant, not an input)"
    res["storage"] = {k: stock["storage"][k] for k in ("h2_created_by_clamp_kg", "rel_of_inflow", "verdict", "closure_kind", "closure_why", "closure_refs")}
    res["carbon"] = {"unassigned_C_kg_h": stock["ga001_carbon"]["unassigned_C_kg_h"]}
    gas, plant, missing_g, missing_p = {}, {}, None, None
    try:
        for label, lhv in lhvs.items():
            g, duty = _gasifier_duty_adjusted(snapshot, previous, lhv, oxidant, o2, n2)
            gas[label] = {"lhv_mj_kg": lhv, "implied_heat_duty_kw": duty, "implied_heat_duty_stock_air_kw": g["implied_heat_duty_kw"],
                          "implied_heat_duty_pct_of_feed": 100.0 * duty / g["in"][0]["kw"], **bck.info("energy_gasifier", "implied_heat_duty")}
            missing_g = g["missing_terms"]
            p = ba.plant_energy(snapshot, previous, lhv)
            plant[label] = {"lhv_mj_kg": lhv, "sum_in_kw": p["sum_in_kw"], "sum_out_known_kw": p["sum_out_known_kw"], "implied_heat_rejected_kw": p["implied_heat_rejected_kw"],
                            "engine_reported_rejection_kw": p["engine_reported_rejection_kw"], "closure_residual_kw": p["closure_residual_kw"],
                            "closure_residual_pct_of_input": p["closure_residual_pct_of_input"], "candidates_sum_kw": p["candidates_sum_kw"],
                            "unexplained_after_candidates_kw": p["unexplained_after_candidates_kw"], **bck.info("energy_plant", "closure_residual")}
            missing_p = p["missing_terms"]
    except ba.AuditInputMissing as exc:
        res["missing_inputs"].append(list(exc.args[0]))
    res["energy_gasifier"], res["energy_plant"] = gas, plant
    res["energy_missing_terms"] = {"gasifier": missing_g or [], "plant": missing_p or [], "scenario": list(SCENARIO_MISSING_TERMS[oxidant]),
                                   "not_in_either_balance": ["stack and flue-gas losses beyond the Assumed ones (python/plant_heat_integration.py); start-up heat",
                                                             "heat of the oxidant supply (ASU) where the oxidant is not air"]}
    return res


def baseline_entry(case):
    """The numbers of one case-state in the shape of docs/balance_audit_baseline.json (residual, relative residual, verdict, plus the closure kind)."""
    entry = {"missing_inputs": case["missing_inputs"]}
    if case["missing_inputs"] and "rows" not in case:
        return entry
    for cv, rows in case["rows"].items():
        entry[cv] = {q: {"residual_kg_h": r["residual_kg_h"], "rel": r["rel"], "verdict": r["verdict"], "closure_kind": r.get("closure_kind")} for q, r in rows.items()}
    if "stock_rows" in case:
        entry["stock_audit_N_and_mass_rel"] = {cv: {q: case["stock_rows"][cv][q]["rel"] for q in ("N", "mass")} for cv in case["stock_rows"]}
    entry["ga001_unassigned_carbon_kg_h"] = case["carbon"]["unassigned_C_kg_h"]
    entry["storage_h2_created_by_clamp_kg"] = case["storage"]["h2_created_by_clamp_kg"]
    entry["plant_energy_closure_residual_kw"] = {k: e["closure_residual_kw"] for k, e in case["energy_plant"].items()}
    entry["ga001_implied_heat_duty_kw"] = {k: e["implied_heat_duty_kw"] for k, e in case["energy_gasifier"].items()}
    return entry


def drift(committed, fresh, rel=1e-9, abs_=1e-12, path=""):
    """Paths at which two baseline entries differ: structure, strings and booleans exactly, numbers within `rel` (and `abs_` near zero). Empty list = no drift."""
    import math
    if isinstance(committed, bool) or isinstance(fresh, bool) or isinstance(committed, str) or isinstance(fresh, str) or committed is None or fresh is None:
        return [] if committed == fresh else [path]
    if isinstance(committed, dict) and isinstance(fresh, dict):
        if set(committed) != set(fresh):
            return [path + "/<keys>"]
        return [p for k in committed for p in drift(committed[k], fresh[k], rel, abs_, f"{path}/{k}")]
    if isinstance(committed, (list, tuple)) and isinstance(fresh, (list, tuple)):
        if len(committed) != len(fresh):
            return [path + "/<len>"]
        return [p for i, (a, b) in enumerate(zip(committed, fresh)) for p in drift(a, b, rel, abs_, f"{path}[{i}]")]
    if isinstance(committed, (int, float)) and isinstance(fresh, (int, float)):
        return [] if (math.isclose(committed, fresh, rel_tol=rel, abs_tol=abs_) or (math.isnan(committed) and math.isnan(fresh))) else [path]
    return [path]
