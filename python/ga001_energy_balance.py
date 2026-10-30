"""
(GA-001, EnergyBalance) -- a READ-ONLY energy report registered next to GA-001 (tail-gas-heat task, item B).

What it is: the closure audit's gasifier energy balance (python/balance_audit.py, reused, not duplicated) published as an engine entry in BOTH
tail-gas modes, plus the heat demands that have no source in the engine and the tail gas's chemical energy as a heat source. It is a leaf:
nothing depends on it, it feeds nothing back (no temperature, conversion, flow or composition changes), it adds no boiler and no heat integration.
It only reports the net heat deficit (-) or surplus (+) in kW.

What it is NOT: part of the physics. GA-001 still computes no heat duty. The "implied gasifier heat duty" is the amount the gasifier would
have to add (+) or remove (-) to leave at its stated temperature, from enthalpies built from the named constants in balance_audit.py
(`Calculated, not part of the engine`).

Reads only already-published state: GA-001's inputs and outputs, FE-005 and HB-005 of the same cycle, and HB-009's tail gas LAGGED (the tail
gas GA-001 itself read). No new edge into any existing model; the dependency graph of the existing models is unchanged except that GA-001
Outputs now also depends on the (leaf) tail_gas_mode input.

Net heat, per feed-LHV case (kW, + surplus / - deficit):
    net = tail-gas heat used - implied gasifier duty - (steam raising + air preheat + feed drying)
where "tail-gas heat used" is the tail gas's lower heating value in heat_only mode and 0 in regasify mode (there it is gasifier feed, not heat).
`net_heat_kw_if_tail_gas_were_heat` is published as well so the two modes can be compared from one snapshot.
Burner / boiler efficiency is not modelled: the tail-gas heat is the gross LHV. Missing terms are listed, never zero.
"""
from . import balance_audit as ba
from . import ga001_gasifier_model as ga001
from . import plant_status as ps

KEY = ("GA-001", "EnergyBalance")
_INPUT_KEYS = [("GA-001-INPUT", k) for k in ("dry_feed_rate_kg_h", "equivalence_ratio", "steam_to_feed_ratio", "carbon_conversion_efficiency",
                                              "ch4_carbon_fraction", "feedstock_composition", "operating_temperature_C")]
DEPENDS_ON = [("GA-001", "Outputs")] + _INPUT_KEYS + [ga001.TAIL_GAS_MODE_KEY, ("FE-005", "MoistureBalance"), ("HB-005", "Steam")]
LAGGED = [("HB-009", "TailGas")]

# Assumed inputs of this report, with the range they could take (none of them feeds any model)
ASSUMED_INPUTS = [
    {"name": "feed temperature entering GA-001 (degC)", "value": ba.T_REF_C, "range": [25.0, ba.FE005_DRYER_OPERATING_C], "status": ps.STATUS_ASSUMED,
     "basis": "ambient; upper end = FE-005 registry operating temperature 100 degC. Not used: feed sensible heat stays Missing."},
    {"name": "tail-gas / recycle temperature (degC)", "value": ba.T_REF_C, "range": [25.0, ba.GC004_QUENCH_OUT_C], "status": ps.STATUS_ASSUMED,
     "basis": "ambient; upper end = the 65 degC GC-004 quench outlet (gc_gas_cleaning_chain.py:295). Not used: its sensible heat stays Missing."},
    {"name": "air preheat temperature (degC)", "value": ba.GA004_AIR_PREHEAT_C, "range": [ba.GA004_AIR_PREHEAT_C, ba.GA004_AIR_PREHEAT_C], "status": ps.STATUS_ASSUMED,
     "basis": "GA-004 registry 'Air preheat temperature' (a single design value, no range stated)"},
    {"name": "steam temperature (degC)", "value": ba.GA004_STEAM_C, "range": [ba.GA004_STEAM_C, ba.GA004_STEAM_C], "status": ps.STATUS_ASSUMED,
     "basis": "GA-004 registry 'Steam temperature (design)' (a single design value, no range stated)"},
    {"name": "mean cp of ash and char (kJ/kg.K)", "value": ba.SOLIDS_CP_KJ_KGK[0], "range": [ba.SOLIDS_CP_KJ_KGK[1], ba.SOLIDS_CP_KJ_KGK[2]], "status": ps.STATUS_ASSUMED,
     "basis": "no solids cp exists in the repo"},
]
MISSING_TERMS = [
    "tar chemical and sensible energy (GA-001 tar is Missing)",
    "heat loss through the 150 mm refractory and shell (no loss model)",
    "feed and recycle sensible heat (temperatures not stated; see ASSUMED_INPUTS ranges)",
    "burner / boiler efficiency and flue-gas losses for the tail-gas heat (no boiler in the engine): the tail-gas heat below is the gross LHV",
    "where the demanded heat is actually sourced (boiler fuel, heat recovery): not modelled",
]


class _View:
    """Makes a get_input look like the {key: entry} snapshot dict that balance_audit's functions read. A key the engine reports as Missing is absent."""

    def __init__(self, get_input):
        self._gi = get_input

    def get(self, key, default=None):
        e = self._gi(key)
        return default if e is None or e["status"] == ps.STATUS_MISSING else e

    def __getitem__(self, key):
        e = self.get(key)
        if e is None:
            raise KeyError(key)
        return e


def _native(x):
    if isinstance(x, dict):
        return {k: _native(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_native(v) for v in x]
    if hasattr(x, "item") and not isinstance(x, (bool, str)):
        return x.item()
    return x


def _terms(rows):
    return [{"name": r["name"], "kw": float(r["kw"]), "status": r["status"], "source": r["source"]} for r in rows]


def energy_balance(get_input):
    view = _View(get_input)
    mode = ga001._tail_gas_mode(get_input)
    lhv_range = ba.dokink_lhv_range()
    if lhv_range is None:
        return {"value": None, "status": ps.STATUS_MISSING, "missing_reason": "DOK-ING's feedstock LHV range (RFI #2) is not confirmed in design_basis.py; no feed energy can be stated"}
    inp = ba.ga001_inputs(view, view)
    ga = ba.ga001_terms(view, view)
    tail = view.get(("HB-009", "TailGas"))
    tail_species = {}
    if tail is not None and "species_nm3_h" in tail["value"]:
        tail_species = {s: float(tail["value"]["species_nm3_h"][s]) for s in ("H2", "CO", "CH4", "CO2", "N2") if s in tail["value"]["species_nm3_h"]}
    combustibles = {s: tail_species.get(s, 0.0) / ba.NM3_PER_MOL for s in ("H2", "CO", "CH4")}
    tail_kw = {s: ba._lhv_kw({s: n}) for s, n in combustibles.items()}
    tail_total_kw = sum(tail_kw.values())
    flow = sum(tail_species.values())
    tail_used_kw = tail_total_kw if mode == "heat_only" else 0.0
    fe5 = view["FE-005", "MoistureBalance"]["value"] if view.get(("FE-005", "MoistureBalance")) else None
    hb005 = view.get(("HB-005", "Steam"))
    n_gs = ga["terms"][4]["species"]["H2O"]            # "gasifier steam", ba.ga001_terms order
    demands = ba.heat_demands(n_gs, float(hb005["value"]["steam_kg_h"]), ga["air_o2_mol_h"], ga["air_n2_mol_h"], float(fe5["water_evaporated_kg_h"]))
    steam_kw = demands[0]["kw"] + demands[1]["kw"]
    air_kw, dry_kw = demands[2]["kw"], demands[3]["kw"]
    demand_kw = steam_kw + air_kw + dry_kw

    cases = {}
    for name, lhv in ba.lhv_cases().items():
        g = ba.gasifier_energy(view, view, lhv)
        duty = g["implied_heat_duty_kw"]
        net = tail_used_kw - duty - demand_kw
        net_heat = tail_total_kw - duty - demand_kw
        cases[name] = {
            "lhv_mj_kg": float(lhv),
            "feed_chemical_kw": g["in"][0]["kw"], "feed_sensible_kw": None,
            "feed_sensible_status": ps.STATUS_MISSING,
            "product_gas_chemical_kw": g["out"][0]["kw"], "product_gas_sensible_kw": g["out"][1]["kw"],
            "implied_gasifier_heat_duty_kw": duty, "implied_gasifier_heat_duty_status": g["status"],
            "gasifier_in": _terms(g["in"]), "gasifier_out": _terms(g["out"]),
            "adiabatic_temperature_c_fixed_composition": g["adiabatic_temperature_c_fixed_composition"],
            "steam_raising_kw": steam_kw, "air_preheat_kw": air_kw, "feed_drying_kw": dry_kw, "heat_demand_total_kw": demand_kw,
            "tail_gas_heat_available_kw": tail_total_kw, "tail_gas_heat_used_kw": tail_used_kw,
            "net_heat_kw": net, "net_heat_kw_if_tail_gas_were_heat": net_heat,
            "net_reading": ("surplus" if net >= 0 else "deficit"),
        }
    value = {
        "basis": "LHV + sensible heat above 25 degC, water vapour at 25 degC = 0; constants named in python/balance_audit.py; net_heat_kw: + surplus, - deficit",
        "tail_gas_mode": mode, "report_only": "nothing in the engine reads this entry; it changes no temperature, conversion, flow or composition",
        "heat_demands": _terms(demands), "heat_demand_status": ps.STATUS_ESTIMATED,
        "tail_gas": {"source": "HB-009 TailGas of the previous cycle (lagged: the tail gas GA-001 itself read)", "flow_nm3_h": flow,
                     "species_nm3_h": tail_species, "chemical_kw": tail_total_kw,
                     "lhv_mj_nm3": (tail_total_kw * 3.6 / flow) if flow else None,
                     "chemical_kw_by_species": tail_kw,
                     "share_of_chemical_energy": {s: (v / tail_total_kw if tail_total_kw else None) for s, v in tail_kw.items()},
                     "used_as_heat": mode == "heat_only", "status": ps.STATUS_CALCULATED},
        "cases": cases, "assumed_inputs": ASSUMED_INPUTS, "missing_terms": list(MISSING_TERMS),
    }
    return {
        "value": _native(value), "status": ps.STATUS_CALCULATED, "model": "ga001_energy_balance.energy_balance",
        "inputs": list(DEPENDS_ON) + list(LAGGED), "validation_basis": ps.VALIDATION_ENGINEERING_CORRELATION,
        "confidence_note": (
            "READ-ONLY report, not a coupling. Every arithmetic term is Calculated from named constants (python/balance_audit.py: standard enthalpies of "
            "formation, the repo's mean cp); assumed temperatures and solids cp are listed with ranges; tar, heat loss, feed/recycle sensible heat and burner "
            "efficiency are Missing, not zero. GA-001 itself computes no heat duty: the implied duty is 'Calculated, not part of the engine'. "
            f"tail_gas_mode = {mode}."
        ),
    }


def register(engine):
    engine.register_model(KEY, energy_balance, unit="kW dict", depends_on=list(DEPENDS_ON), lagged_depends_on=list(LAGGED))
