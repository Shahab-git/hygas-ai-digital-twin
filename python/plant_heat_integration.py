"""
("PLANT", "HeatIntegration") -- a READ-ONLY heat source / heat sink inventory (heat-integration task, stage 1).

What it is: where the heat the plant itself releases could come from, what the heat demands are, at which temperature level each is needed, and what is left
to buy. A pure function of already-published state; a LEAF: nothing depends on it, nothing reads it, it feeds nothing back (no temperature, conversion, flow,
composition or hydrogen output changes). It adds no boiler, burner, heat exchanger or stack to the engine and couples nothing.

What it is NOT: part of the physics. The model still has no boiler, no heat recovery and no stack; this key only says how much heat there would be to recover and
what it could serve. Every constant is named and tagged: repo constants are reused (python/balance_audit.py, python/ga001_energy_balance.py), standard thermodynamic
constants carry their value and source, everything else is `Assumed` with a range. Unknown terms are `Missing`, never zero.

Basis (kW, same as (GA-001, EnergyBalance)): lower heating value + sensible heat above 25 degC, water vapour at 25 degC = 0 (balance_audit.py).

SINKS (kW needed):
  * the four demands of (GA-001, EnergyBalance), unchanged in total: gasifier steam raising, WGS steam raising, air preheat, feed drying;
  * WGS feed reheat (clean gas from the SA-011 temperature to the HB-001 inlet temperature), the only other process heat with stated temperatures and a published flow;
  * the implied gasifier duty of the LHV case, when positive (it is a SOURCE when negative: the gasifier would have to shed heat);
  * Missing, not zero: HB-016 dehydrogenation heat (its branch is structurally blocked in the engine; the registry states 19 kW), PSA preheat (no source in the repo).
  Each steam demand is split over three temperature bands (heating the liquid to saturation, evaporation, superheat) in proportion to named constants, so it can be matched
  against sources band by band; the split changes no total.

SOURCES (kW available inside the plant), each with the temperature interval over which it is released:
  1 PSA tail-gas chemical energy (reported in both modes; it is COUNTED only through source 5, in `heat_only`, because in `regasify` it is gasifier feed);
  2 sensible heat of the wet product gas cooled from the gasifier temperature to the cleaning-train inlet temperature (Assumed range);
  3 WGS reaction heat (exothermic, the standard reaction enthalpy from balance_audit's enthalpies of formation, for the CO the published HTS / LTS conversions convert);
  4 sensible heat of the ash and the carbon black (low grade);
  5 flue gas after burning the tail gas (Assumed excess air, Assumed stack temperature): the same energy as source 1, released between the adiabatic flame
    temperature and the stack temperature; the heat left in the flue gas at the stack is reported as the stack loss;
  6 the implied gasifier duty when negative.

MATCHING: heat released at temperature T can serve a need at temperature t only if T >= t + dT_min (Assumed). Needs are served from the hottest need down, each from the
COLDEST source heat that qualifies, so hot heat is kept for hot needs. Heat that exists but cannot be delivered because of its temperature level is reported as
`temperature_level_mismatch_kw`, not counted. The supplementary fuel is the unmet need at 100 % burner efficiency (no efficiency is modelled), also as kg/day of hydrogen from
the product stream at its lower heating value, as a cost figure: it is not applied anywhere.
"""
import bisect

from . import balance_audit as ba
from . import ga001_energy_balance as eb
from . import ga001_gasifier_model as ga001
from . import hb_wgs_psa_storage_chain as hbchain
from . import plant_status as ps

KEY = ("PLANT", "HeatIntegration")
# every key (GA-001 inputs, tail_gas_mode, FE-005, HB-005) that balance_audit.gasifier_energy / (GA-001, EnergyBalance) read, plus what this key reads itself; the new key is a LEAF, so
# these are edges INTO it only: no existing model gains a dependency
# It does NOT depend on the (GA-001, EnergyBalance) entry: it calls ga001_energy_balance.energy_balance on the same inputs (the one function, so the four demands cannot drift),
# which keeps (GA-001, EnergyBalance) a leaf that nothing depends on.
DEPENDS_ON = list(dict.fromkeys(list(eb.DEPENDS_ON) + [("GA-001", "CarbonAccounting"), ("GC-013", "Gas"), ("WGS", "Composition"), ("HB-001", "HTS"), ("HB-004", "LTS"), ("SA-011", "Reading")]))
LAGGED = list(eb.LAGGED)

# --- constants -----------------------------------------------------------------------------------------------------------------------------
# Standard steam-table values at 6 bar absolute (= HB-005's 5 bar(g), balance_audit.heat_demands uses the same 350 degC / 5 bar(g)): Estimated (quoted from steam tables, not
# looked up by the code).
STEAM_6BAR = {"t_sat_c": 158.83, "h_fg_kj_kg": 2085.8, "status": ps.STATUS_ESTIMATED, "source": "standard steam tables, saturated water at 6 bar absolute (5 bar(g))"}
# WGS: CO + H2O(g) -> CO2 + H2, from the standard enthalpies of formation already named in balance_audit.py (NIST-JANAF / CRC)
DH_WGS_KJ_MOL = ba.HF_KJ_MOL["CO2"] + ba.HF_KJ_MOL["H2"] - ba.HF_KJ_MOL["CO"] - ba.HF_KJ_MOL["H2O_g"]          # -41.158 kJ/mol at 25 degC (exothermic)
HTS_LEVEL_C = hbchain.HTS_INLET_TEMPERATURE_C          # 350 degC, HB-001 inlet (hb_wgs_psa_storage_chain.py:100); the heat is released in the bed at or above it
LTS_LEVEL_C = hbchain.HB003_HOT_OUTLET_C               # 220 degC, HB-004 inlet (hb_wgs_psa_storage_chain.py:107)
STEAM_LEVEL_C = ba.GA004_STEAM_C                       # 350 degC
AIR_LEVEL_C = ba.GA004_AIR_PREHEAT_C                   # 200 degC
DRYER_LEVEL_C = ba.FE005_DRYER_OPERATING_C             # 100 degC
CARBON_BLACK_COLLECTION_C = ba.GA008_OPERATING_C       # 180 degC (GA-008 registry operating temperature)
H2_LHV_KWH_PER_KG = ba.LHV_KJ_MOL["H2"] / hbchain.M_H2 * 1000.0 / 3600.0         # kJ/mol / (g/mol) -> MJ/kg -> kWh/kg: 241.826 / 2.016 / 3.6 = 33.32 kWh/kg

# Assumed, each with a range (never tuned; the report script shows one-at-a-time sensitivities)
ASSUMED = {
    "recovery_gas_cooler": {"value": 0.7, "low": 0.5, "high": 0.9, "unit": "-", "status": ps.STATUS_ASSUMED, "basis": "share of the product-gas sensible heat a waste-heat cooler could recover; no cooler in the engine (GC-004 is a water-spray quench)"},
    "recovery_wgs": {"value": 0.7, "low": 0.5, "high": 0.9, "unit": "-", "status": ps.STATUS_ASSUMED, "basis": "share of the WGS reaction heat recoverable (HB-003 does a gas/water exchange today)"},
    "recovery_ash": {"value": 0.5, "low": 0.25, "high": 0.75, "unit": "-", "status": ps.STATUS_ASSUMED, "basis": "low-grade solids heat; GA-005 cools the ash with a water jacket today"},
    "recovery_flue": {"value": 0.8, "low": 0.6, "high": 0.9, "unit": "-", "status": ps.STATUS_ASSUMED, "basis": "share of the flue-gas heat between the flame and the stack temperature a boiler could recover"},
    "delta_t_min_k": {"value": 20.0, "low": 10.0, "high": 40.0, "unit": "K", "status": ps.STATUS_ASSUMED, "basis": "minimum temperature difference between a source and the need it serves"},
    "excess_air_ratio": {"value": 1.2, "low": 1.1, "high": 1.5, "unit": "-", "status": ps.STATUS_ASSUMED, "basis": "combustion air / stoichiometric air for burning the tail gas"},
    "stack_temperature_c": {"value": 180.0, "low": 120.0, "high": 250.0, "unit": "degC", "status": ps.STATUS_ASSUMED, "basis": "flue-gas temperature leaving the heat recovery; no stack in the engine"},
    "ash_discharge_temperature_c": {"value": 150.0, "low": 100.0, "high": 300.0, "unit": "degC", "status": ps.STATUS_ASSUMED, "basis": "GA-006 registry 'Char temperature at inlet' 150 degC (resolved status: Unverified (registry)); ash leaves the bed at the gasifier temperature"},
    "carbon_black_final_c": {"value": 60.0, "low": 25.0, "high": 100.0, "unit": "degC", "status": ps.STATUS_ASSUMED, "basis": "temperature the carbon black is cooled to before packaging; it is collected at 180 degC (GA-008 registry)"},
    "gas_cooler_outlet_c": {"value": ba.GC004_QUENCH_OUT_C, "low": ba.GC004_QUENCH_OUT_C, "high": 300.0, "unit": "degC", "status": ps.STATUS_ASSUMED,
                            "basis": "cleaning-train inlet temperature: the 65 degC GC-004 quench outlet (gc_gas_cleaning_chain.py:295, hard-coded 860 -> 65); the range top is a dry cooler that stops above the tar condensation range"},
}
MISSING_SINKS = [
    {"name": "HB-016 dehydrogenation heat", "status": ps.STATUS_MISSING, "note": "the LOHC branch is structurally blocked in the engine (HB-007's split fraction is Missing); the registry states 19 kW (Calculated there, resolved status Unverified (registry))"},
    {"name": "PSA / WGS preheat other than the clean-gas reheat above", "status": ps.STATUS_MISSING, "note": "no source for it exists in the repo"},
]
MISSING_TERMS = [
    "stack losses beyond the Assumed stack temperature (acid dew point, partial recovery); the burner / boiler efficiency (the supplementary fuel is gross)",
    "radiation and heat loss from the gasifier, ducts and vessels (no loss model)",
    "tar chemical and sensible energy (GA-001 tar is Missing)",
    "start-up heat (the plant is quasi-steady per cycle)",
    "heat or electricity for an air-separation unit when the gasifying agent is not air (no ASU model; docs/gasifying_agent_study.md)",
    "latent heat of condensing the water vapour in the raw gas (its dew point is not modelled; it falls below about 100 degC and is low grade)",
    "heat to bring the cold start / make-up water to 25 degC, cooling-water pumping and fan power",
]


# --- heat release / need profiles ----------------------------------------------------------------------------------------------------------------

def _uniform(kw, t_lo, t_hi, max_bins=200):
    """kW spread evenly over the temperature interval (a constant-cp stream cooled or heated linearly): [(T midpoint, kW)]."""
    if kw == 0.0:
        return []
    if t_hi - t_lo < 1.0:
        return [(0.5 * (t_lo + t_hi), kw)]
    n = int(min(max_bins, max(1, round(t_hi - t_lo))))
    w = (t_hi - t_lo) / n
    return [(t_lo + (i + 0.5) * w, kw / n) for i in range(n)]


def match(supply, need, dt_min):
    """Greedy level matching. supply: [(source, T, kW)], need: [(sink, band, T, kW)]. A need at T is served by supply at T' >= T + dt_min, the COLDEST qualifying first,
    hottest need first. Returns (allocation {(sink, source): kW}, unmet {sink: kW}, unused {source: kW}). Energy is conserved: sum(allocation) + sum(unmet) = sum(need)."""
    pool = sorted(([t, s, kw] for s, t, kw in supply if kw > 0.0), key=lambda x: x[0])
    temps = [p[0] for p in pool]
    alloc, unmet = {}, {}
    for sink, _band, t_need, kw in sorted(need, key=lambda x: -x[2]):
        left = kw
        i = bisect.bisect_left(temps, t_need + dt_min - 1e-9)
        while left > 1e-15 and i < len(pool):
            if pool[i][2] > 1e-15:
                x = min(pool[i][2], left)
                pool[i][2] -= x
                left -= x
                alloc[(sink, pool[i][1])] = alloc.get((sink, pool[i][1]), 0.0) + x
            i += 1
        if left > 1e-15:
            unmet[sink] = unmet.get(sink, 0.0) + left
    unused = {}
    for _t, s, kw in pool:
        unused[s] = unused.get(s, 0.0) + kw
    return alloc, unmet, unused


# --- the inventory -------------------------------------------------------------------------------------------------------------------------------

def _src(name, kw, t_hi, t_lo, status, note, recovery_key=None, counted=True, grade=None, recoverable=True):
    """One source. A Missing source has kw None (never zero) and is never counted."""
    return {"name": name, "kw_available": None if kw is None else float(kw), "t_high_c": float(t_hi), "t_low_c": float(t_lo), "status": status, "note": note, "recovery_key": recovery_key,
            "counted": counted, "grade": grade, "recoverable_in_principle": recoverable}


def _flue(tail_species, lam, t_stack_c):
    """Burn the tail gas with lam x stoichiometric air at 25 degC: (chemical kW, flue-gas mol/h by species, adiabatic temperature degC, kW released between flame and stack,
    stack loss kW). Closes by construction: released + stack loss = chemical energy (LHV basis, water as vapour)."""
    n = {s: tail_species.get(s, 0.0) / ba.NM3_PER_MOL for s in ("H2", "CO", "CH4", "CO2", "N2")}
    chem = ba._lhv_kw({s: n[s] for s in ("H2", "CO", "CH4")})
    o2_stoich = 0.5 * n["H2"] + 0.5 * n["CO"] + 2.0 * n["CH4"]
    flue = {"CO2": n["CO2"] + n["CO"] + n["CH4"], "H2O": n["H2"] + 2.0 * n["CH4"], "N2": n["N2"] + o2_stoich * lam * ga001.AIR_N2_PER_O2, "O2": (lam - 1.0) * o2_stoich}
    cp_sum = sum(v * ba.CP_J_MOLK[s] for s, v in flue.items())                    # J/K per hour
    if chem <= 0.0 or cp_sum <= 0.0:
        return 0.0, flue, None, 0.0, 0.0
    t_ad = ba.T_REF_C + chem / (cp_sum / 1000.0 * ba.KW_PER_KJ_H)
    loss = ba._sens_kw(flue, t_stack_c)
    return chem, flue, t_ad, chem - loss, loss


def compute(get, assumptions=None, lhv_cases=None, demands=None, duty_fn=None):
    """The whole inventory from published state. `get(key)` returns an entry dict or None (= Missing). `assumptions` overrides ASSUMED values by name; `lhv_cases` is
    {name: MJ/kg dry} (default: DOK-ING's range, as (GA-001, EnergyBalance)). `demands` replaces the four EnergyBalance demands (a list of {name, kw}, same names as
    balance_audit.heat_demands) and `duty_fn(lhv) -> (kW, status)` replaces the implied gasifier duty: both exist only so the report script can run the gasifying-agent scenarios
    (docs/gasifying_agent_study.md) whose oxidant differs from the engine's air; the engine key uses neither. Returns the value dict of the key, or a dict with `missing_reason`
    when a required input is Missing."""
    A = {k: dict(v) for k, v in ASSUMED.items()}
    for k, v in (assumptions or {}).items():
        A[k]["value"] = float(v)
    a = {k: v["value"] for k, v in A.items()}
    view = eb._View(lambda k: ({"status": ps.STATUS_MISSING} if get(k) is None else get(k)))
    need_keys = [("GA-001", "Outputs"), ("GA-001-INPUT", "operating_temperature_C"), ("GA-001-INPUT", "dry_feed_rate_kg_h"), ("GC-013", "Gas"),
                 ("WGS", "Composition"), ("HB-001", "HTS"), ("HB-004", "LTS")]
    absent = [k for k in need_keys if get(k) is None]
    if absent:
        return {"missing_reason": f"required published state is Missing: {absent}"}
    eb_entry = eb.energy_balance(lambda k: get(k) or {"value": None, "unit": None, "status": ps.STATUS_MISSING, "missing_reason": f"{k} is Missing"})
    ebv = eb_entry["value"]
    if ebv is None:
        return {"missing_reason": eb_entry.get("missing_reason") or "ga001_energy_balance.energy_balance has no value"}
    mode = ebv["tail_gas_mode"]
    t_gas = float(get(("GA-001-INPUT", "operating_temperature_C"))["value"])
    out = get(("GA-001", "Outputs"))["value"]
    gc013 = get(("GC-013", "Gas"))["value"]
    wgs = get(("WGS", "Composition"))["value"]
    hts, lts = get(("HB-001", "HTS"))["value"], get(("HB-004", "LTS"))["value"]
    feed_kg_h = float(get(("GA-001-INPUT", "dry_feed_rate_kg_h"))["value"])
    sa011 = get(("SA-011", "Reading"))
    t_clean_in = float(sa011["value"]) if sa011 is not None else None

    # ---- sinks --------------------------------------------------------------------------------------------------------------------------------
    dem = {d["name"]: d for d in (demands if demands is not None else ebv["heat_demands"])}
    d_gs = next(d for n, d in dem.items() if n.startswith("raise gasifier steam"))
    d_ws = next(d for n, d in dem.items() if n.startswith("raise WGS steam"))
    d_air = next(d for n, d in dem.items() if n.startswith("preheat air"))
    d_dry = next(d for n, d in dem.items() if n.startswith("evaporate feed moisture"))
    t_sat = STEAM_6BAR["t_sat_c"]
    q_liq = ba.CP_LIQUID_WATER_J_MOLK / 1000.0 * (t_sat - ba.T_REF_C)
    q_lat = STEAM_6BAR["h_fg_kj_kg"] * ba.M_H2O_ENGINE / 1000.0
    q_sh = ba.CP_J_MOLK["H2O"] / 1000.0 * (STEAM_LEVEL_C - t_sat)
    tot = q_liq + q_lat + q_sh
    split = {"liquid heating": q_liq / tot, "evaporation": q_lat / tot, "superheat": q_sh / tot}

    def steam_bands(d):
        return ([(d["name"], "liquid heating", t, kw) for t, kw in _uniform(d["kw"] * split["liquid heating"], ba.T_REF_C, t_sat)] +
                [(d["name"], "evaporation", t_sat, d["kw"] * split["evaporation"])] +
                [(d["name"], "superheat", t, kw) for t, kw in _uniform(d["kw"] * split["superheat"], t_sat, STEAM_LEVEL_C)])

    sinks = [{"name": d_gs["name"], "kw": d_gs["kw"], "t_high_c": STEAM_LEVEL_C, "status": ps.STATUS_ESTIMATED, "origin": "(GA-001, EnergyBalance)", "bands": steam_bands(d_gs)},
             {"name": d_ws["name"], "kw": d_ws["kw"], "t_high_c": STEAM_LEVEL_C, "status": ps.STATUS_ESTIMATED, "origin": "(GA-001, EnergyBalance)", "bands": steam_bands(d_ws)},
             {"name": d_air["name"], "kw": d_air["kw"], "t_high_c": AIR_LEVEL_C, "status": ps.STATUS_ESTIMATED, "origin": "(GA-001, EnergyBalance)",
              "bands": [(d_air["name"], "sensible", t, kw) for t, kw in _uniform(d_air["kw"], ba.T_REF_C, AIR_LEVEL_C)]},
             {"name": d_dry["name"], "kw": d_dry["kw"], "t_high_c": DRYER_LEVEL_C, "status": ps.STATUS_ESTIMATED, "origin": "(GA-001, EnergyBalance)",
              "bands": [(d_dry["name"], "evaporation", DRYER_LEVEL_C, d_dry["kw"])]}]
    n_dry_total = float(gc013["dry_flow_nm3_h"]) / ba.NM3_PER_MOL
    fracs = {"H2": gc013["H2_mol_pct_dry"], "CO": gc013["CO_mol_pct_dry"], "CO2": gc013["CO2_mol_pct_dry"], "CH4": gc013["CH4_mol_pct_dry"], "N2": gc013["N2_mol_pct_dry"]}
    clean = {s: n_dry_total * p / 100.0 for s, p in fracs.items()}
    if t_clean_in is not None and t_clean_in < HTS_LEVEL_C:
        reheat_kw = ba._sens_kw(clean, HTS_LEVEL_C) - ba._sens_kw(clean, t_clean_in)
        sinks.append({"name": f"WGS feed reheat: clean gas {t_clean_in:.0f} -> {HTS_LEVEL_C:.0f} degC (HB-001 inlet)", "kw": reheat_kw, "t_high_c": HTS_LEVEL_C,
                      "status": ps.STATUS_ESTIMATED, "origin": "GC-013 gas flow and composition; SA-011 temperature (Assumed static point); HB-001 inlet temperature",
                      "bands": [("WGS feed reheat", "sensible", t, kw) for t, kw in _uniform(reheat_kw, t_clean_in, HTS_LEVEL_C)]})
    base_demand = sum(s["kw"] for s in sinks)
    energy_balance_demand = sum(s["kw"] for s in sinks[:4])

    # ---- sources that do not depend on the LHV case ---------------------------------------------------------------------------------------------
    gas_dry = {s: float(out["dry_flow_nm3_h"]) / ba.NM3_PER_MOL * float(out[f"{s}_mol_pct_dry"]) / 100.0 for s in ("H2", "CO", "CO2", "CH4", "N2")}
    gas_wet = dict(gas_dry, H2O=(float(out["wet_flow_nm3_h"]) - float(out["dry_flow_nm3_h"])) / ba.NM3_PER_MOL)
    t_out = a["gas_cooler_outlet_c"]
    sources = []
    gas_kw = ba._sens_kw(gas_wet, t_gas) - ba._sens_kw(gas_wet, t_out) if t_gas > t_out else 0.0
    sources.append(_src("product-gas sensible heat (wet gas, gasifier temperature -> cleaning-train inlet)", gas_kw, t_gas, t_out, ps.STATUS_CALCULATED,
                        f"n x mean cp (balance_audit.CP_J_MOLK) x ({t_gas:.0f} - {t_out:.0f}) K; the engine's GC-004 is a direct water-spray quench that hands this heat to the quench water", "recovery_gas_cooler"))
    co_total = float(wgs["co_consumed_total"]) * float(gc013["dry_flow_nm3_h"]) / ba.NM3_PER_MOL
    co_hts = float(hts["y_CO_in"]) * float(hts["X_hts"]) * float(gc013["dry_flow_nm3_h"]) / ba.NM3_PER_MOL
    co_lts = max(co_total - co_hts, 0.0)
    wgs_hts_kw, wgs_lts_kw = -DH_WGS_KJ_MOL * co_hts * ba.KW_PER_KJ_H, -DH_WGS_KJ_MOL * co_lts * ba.KW_PER_KJ_H
    sources.append(_src("WGS reaction heat, HTS stage", wgs_hts_kw, HTS_LEVEL_C, HTS_LEVEL_C, ps.STATUS_CALCULATED,
                        f"{co_hts:.1f} mol/h CO converted x {-DH_WGS_KJ_MOL:.3f} kJ/mol (standard enthalpies of formation); released at the HB-001 bed temperature", "recovery_wgs"))
    sources.append(_src("WGS reaction heat, LTS stage", wgs_lts_kw, LTS_LEVEL_C, LTS_LEVEL_C, ps.STATUS_CALCULATED,
                        f"{co_lts:.1f} mol/h CO converted; released at the HB-004 inlet temperature (the bed runs hotter, so this level is conservative)", "recovery_wgs"))
    ash_kg_h = feed_kg_h * ga001.ASH_FRACTION
    cb = get(("GA-001", "CarbonAccounting"))
    cb_kg_h = float(cb["value"]["carbon_black_kg_h"]) if cb is not None and cb["value"] is not None else None
    cp_s = ba.SOLIDS_CP_KJ_KGK[0]
    ash_kw = max(0.0, ash_kg_h * cp_s * (t_gas - a["ash_discharge_temperature_c"]) * ba.KW_PER_KJ_H)         # cooling cannot release heat when the discharge is hotter than the bed
    sources.append(_src("ash sensible heat (bed temperature -> discharge)", ash_kw, t_gas, a["ash_discharge_temperature_c"], ps.STATUS_ASSUMED,
                        f"{ash_kg_h:.2f} kg/h x cp {cp_s} kJ/kg.K (Assumed, no solids cp in the repo) x temperature drop; the ash fraction is the code's 10 %", "recovery_ash", grade="low"))
    if cb_kg_h is None:
        sources.append(_src("carbon-black sensible heat", None, CARBON_BLACK_COLLECTION_C, a["carbon_black_final_c"], ps.STATUS_MISSING, "(GA-001, CarbonAccounting) is Missing: no carbon-black flow, so no heat is stated",
                            "recovery_ash", counted=False, grade="low"))
    else:
        sources.append(_src("carbon-black sensible heat (collection -> packaging)", max(0.0, cb_kg_h * cp_s * (CARBON_BLACK_COLLECTION_C - a["carbon_black_final_c"]) * ba.KW_PER_KJ_H),
                            CARBON_BLACK_COLLECTION_C, a["carbon_black_final_c"], ps.STATUS_ASSUMED, f"{cb_kg_h:.3f} kg/h from (GA-001, CarbonAccounting) x cp {cp_s} (Assumed)", "recovery_ash", grade="low"))
    tail_species = (ebv.get("tail_gas") or {}).get("species_nm3_h") or {}
    chem, flue, t_ad, flue_kw, stack_loss = _flue(tail_species, a["excess_air_ratio"], a["stack_temperature_c"])
    burn_counted = mode == "heat_only"
    sources.append(_src("PSA tail-gas chemical energy (LHV)", chem, t_ad if t_ad else a["stack_temperature_c"], a["stack_temperature_c"], ps.STATUS_CALCULATED,
                        "(GA-001, EnergyBalance).tail_gas.chemical_kw; REPORTED ONLY: it is counted through the flue-gas source below, never twice", None, counted=False))
    sources.append(_src("flue gas from burning the tail gas (flame -> stack)", flue_kw, t_ad if t_ad else a["stack_temperature_c"], a["stack_temperature_c"], ps.STATUS_ASSUMED,
                        (f"lambda {a['excess_air_ratio']}, stack {a['stack_temperature_c']:.0f} degC (both Assumed); adiabatic flame {t_ad:.0f} degC; stack loss {stack_loss:.2f} kW" if t_ad else "no combustible tail gas published"),
                        "recovery_flue", counted=burn_counted))
    sources[-1]["stack_loss_kw"] = stack_loss
    sources[-1]["adiabatic_temperature_c"] = t_ad
    sources[-1]["counted_reason"] = ("tail_gas_mode = heat_only: the tail gas is heat" if burn_counted else "tail_gas_mode = regasify: the tail gas is gasifier feed, so it is NOT heat; shown for what burning it instead would release")

    # ---- per LHV case: the gasifier duty is the only term that depends on the feed LHV -----------------------------------------------------
    cases_in = lhv_cases if lhv_cases is not None else ba.lhv_cases()
    cases = {}
    for cname, lhv in cases_in.items():
        if duty_fn is None:
            g = ba.gasifier_energy(view, view, lhv)
            duty, duty_status = float(g["implied_heat_duty_kw"]), g["status"]
        else:
            duty, duty_status = duty_fn(lhv)
            duty = float(duty)
        s_case = [dict(s) for s in sources]
        sinks_case = list(sinks)
        if duty > 0.0:
            sinks_case = sinks_case + [{"name": "implied gasifier heat duty (must be added)", "kw": duty, "t_high_c": t_gas, "status": duty_status, "origin": "balance_audit.gasifier_energy",
                                        "bands": [("implied gasifier heat duty", "at gasifier temperature", t_gas, duty)]}]
        elif duty < 0.0:
            s_case = s_case + [_src("implied gasifier surplus (heat the gasifier would have to shed)", -duty, t_gas, t_gas, duty_status, "balance_audit.gasifier_energy; released at the gasifier temperature", "recovery_gas_cooler")]
        supply = []
        rec = {}
        for s in s_case:
            r = a[s["recovery_key"]] if s["recovery_key"] else 0.0
            s["kw_recovered"] = s["kw_available"] * r if s["counted"] and s["recoverable_in_principle"] and s["kw_available"] is not None else 0.0
            s["recovery_fraction"] = r if s["recovery_key"] else None
            rec[s["name"]] = s["kw_recovered"]
            if s["kw_recovered"] > 0.0:
                for t, kw in _uniform(s["kw_recovered"], min(s["t_low_c"], s["t_high_c"]), max(s["t_low_c"], s["t_high_c"])):
                    supply.append((s["name"], t, kw))
        need = [b for sk in sinks_case for b in sk["bands"]]
        alloc, unmet, unused = match(supply, need, a["delta_t_min_k"])
        demand_total = sum(sk["kw"] for sk in sinks_case)
        supply_total = sum(rec.values())
        matched = sum(alloc.values())
        unmet_total = sum(unmet.values())
        unused_total = sum(unused.values())
        mismatch = min(unmet_total, unused_total)
        net_energy = supply_total - demand_total
        fuel_kw = unmet_total
        by_source = {n: {"kw_recovered": rec[n], "kw_matched": sum(v for (sk, so), v in alloc.items() if so == n), "kw_unused_level_or_surplus": unused.get(n, 0.0)} for n in rec}
        bkey = lambda sk: sk["bands"][0][0] if sk["bands"] else sk["name"]            # a zero-kW sink (for example no air in a steam-only case) has no bands
        by_sink = {sk["name"]: {"kw_needed": sk["kw"], "t_high_c": sk["t_high_c"], "kw_matched": sum(v for (k2, so), v in alloc.items() if k2 == bkey(sk)),
                                "kw_unmet": unmet.get(bkey(sk), 0.0)} for sk in sinks_case}
        cases[cname] = {
            "lhv_mj_kg": float(lhv), "implied_gasifier_heat_duty_kw": duty, "demand_total_kw": demand_total, "source_recovered_counted_kw": supply_total,
            "net_energy_basis_kw": net_energy, "net_reading": "surplus" if net_energy >= 0 else "deficit",
            "matched_kw": matched, "unmet_kw": unmet_total, "unused_source_kw": unused_total,
            "temperature_level_mismatch_kw": mismatch, "mismatch_share_of_unmet": (mismatch / unmet_total if unmet_total > 0 else None),
            "supplementary_fuel_kw": fuel_kw, "supplementary_fuel_as_h2_kg_day": fuel_kw * 24.0 / H2_LHV_KWH_PER_KG,
            "by_source": by_source, "by_sink": by_sink,
        }
    srcs = [{k: v for k, v in s.items() if k != "kw_recovered"} for s in sources]
    return {
        "basis": "kW, LHV + sensible heat above 25 degC (balance_audit.py); levels in degC; + surplus / - deficit; a pure function of published state",
        "tail_gas_mode": mode, "report_only": "nothing reads this entry; it adds no boiler, burner, exchanger or stack and changes no temperature, conversion, flow, composition or hydrogen",
        "sinks": [{k: v for k, v in s.items() if k != "bands"} for s in sinks], "steam_band_split": split, "steam_band_status": ps.STATUS_ESTIMATED,
        "energy_balance_demand_kw": energy_balance_demand, "additional_process_heat_kw": base_demand - energy_balance_demand,
        "missing_sinks": list(MISSING_SINKS), "sources": srcs, "assumed_inputs": [dict(name=k, **v) for k, v in A.items()],
        "constants": {"steam_6bar": STEAM_6BAR, "dh_wgs_kj_mol": {"value": DH_WGS_KJ_MOL, "status": ps.STATUS_CALCULATED, "source": "balance_audit.HF_KJ_MOL (NIST-JANAF / CRC)"},
                      "h2_lhv_kwh_per_kg": {"value": H2_LHV_KWH_PER_KG, "status": ps.STATUS_CALCULATED, "source": "balance_audit.LHV_KJ_MOL['H2'] / hb_wgs_psa_storage_chain.M_H2"},
                      "levels_c": {"steam": STEAM_LEVEL_C, "air": AIR_LEVEL_C, "dryer": DRYER_LEVEL_C, "hts": HTS_LEVEL_C, "lts": LTS_LEVEL_C},
                      "solids_cp_kj_kgk": {"value": cp_s, "status": ps.STATUS_ASSUMED, "range": [ba.SOLIDS_CP_KJ_KGK[1], ba.SOLIDS_CP_KJ_KGK[2]]}},
        "cases": cases, "missing_terms": list(MISSING_TERMS),
    }


def _native(x):
    return eb._native(x)


def heat_integration(get_input):
    def get(key):
        e = get_input(key)
        return None if e is None or e["status"] == ps.STATUS_MISSING else e
    value = compute(get)
    if "missing_reason" in value:
        return {"value": None, "status": ps.STATUS_MISSING, "missing_reason": value["missing_reason"]}
    return {
        "value": _native(value), "status": ps.STATUS_CALCULATED, "model": "plant_heat_integration.heat_integration",
        "inputs": list(DEPENDS_ON) + list(LAGGED), "validation_basis": ps.VALIDATION_ENGINEERING_CORRELATION,
        "confidence_note": (
            "READ-ONLY inventory, not a coupling. Sources and sinks are Calculated from published state and named constants (python/balance_audit.py; standard enthalpies and steam-table "
            "values stated); recovery fractions, minimum approach, excess air, stack and ash temperatures are Assumed with ranges and none is tuned. Heat is matched to needs by "
            "temperature level; heat that cannot serve a need for lack of level is reported as a mismatch, not counted. Stack losses beyond the Assumed, heat loss, tar, start-up heat, "
            f"ASU heat and the burner efficiency are Missing, not zero. The model has no boiler, no heat recovery and no stack. tail_gas_mode = {value['tail_gas_mode']}."),
    }


def register(engine):
    engine.register_model(KEY, heat_integration, unit="kW dict", depends_on=list(DEPENDS_ON), lagged_depends_on=list(LAGGED))
