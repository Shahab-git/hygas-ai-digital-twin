"""The DOK-ING RFI2 basis (the DEFAULT of the engine since 2026-11-25) and the earlier model basis as a SWITCHABLE what-if.

CLASS: simulated scenario on the unchanged quasi-steady engine; every number derived here is Assumed. DOK-ING's replies themselves are in
data/dokink_rfi_answers.md (RFI 2); only what they state is Confirmed there.

What RFI2 says (verbatim in data/dokink_rfi_answers.md): no gasifying agent is added (0 Nm3/h air, 0 kg/h steam), no oxygen-carrier loop, no air
reactor, the tubular reactor is heated externally by electric heaters, the feed is not dried (up to 15 % moisture), and 40 to 50 % of the
41.67 kg/h feed leaves as carbon black / char.

How the engine maps that (each step a simplification, none a DOK-ING figure):
  1. No agent: GA-001's gasifying_agent default is 'none_external_heat' (ER 0, steam 0, no oxidant), so the only water is the feed moisture.
  2. No dryer: fe_feed_handling.FE005_DRYING_ACTIVE is False, so ALL feed moisture (10 %, Assumed; RFI2 allows up to 15 %) reaches GA-001 as water.
  3. Char: carbon conversion is derived so that the unconverted carbon plus the ash equals the char share of the as-received feed (45 %, the
     midpoint of 40 to 50 %): conversion = 1 - (char_kg_h - ash_kg_h) / carbon_in_kg_h = 0.111. Char is treated as carbon plus ash only
     (real char also holds H and O); the conversion is clamped at 0 when the char share exceeds carbon plus ash.
  4. External electric heat: not modelled (the duty stays Missing). RFI2 #6 gives about 100 kW electrical in total for heating AND propulsion.
The engine has no pyrolysis or tar chemistry: it is an equilibrium solver with a carbon-conversion cap, so the gas composition is an
equilibrium estimate, not a pyrolysis-gas prediction.

This module: run('rfi2' | 'model') runs the engine on either basis. 'rfi2' with the default char share and moisture is the plain default
engine; other values use engine overrides. 'model' restores the earlier basis (air at ER 0.25, feed dried to 1 %, conversion 0.90).

Numeric check (comment, project convention): with the default char share (0.45) the derived carbon conversion is 0.111 and the 10-cycle engine
gives about 13.5 kg/day hydrogen and 2.5 % dry N2 (tests/test_rfi2_basis.py).
"""
from . import fe_feed_handling as fe
from . import ga001_gasifier_model as ga
from . import plant_status as ps
from . import tab1_integration as t1

CHAR_FRACTION_DEFAULT = 0.45         # Assumed: midpoint of RFI2 #8 (40 to 50 % of the as-received feed)
CHAR_FRACTION_RANGE = (0.40, 0.50)
MOISTURE_DEFAULT = 0.10              # Assumed: RFI2 #5 says up to 15 %; 10 % is the existing project assumption
MOISTURE_RANGE = (0.05, 0.15)
AGENT_KEY = ga.GASIFYING_AGENT_KEY
AGENT = ga.GASIFYING_AGENT_DEFAULT   # "none_external_heat"
STEAM_KEY = ("GA-001-INPUT", "steam_to_feed_ratio")
CONV_KEY = ("GA-001-INPUT", "carbon_conversion_efficiency")
FE005_KEY = ("FE-005", "MoistureBalance")
FEED_KEY = ("FE-001-INPUT", "msw_delivery_rate_kg_h")


def _const(value, note):
    def fn(get_input):
        return {"value": value, "status": ps.STATUS_ASSUMED, "inputs": [], "validation_basis": ps.VALIDATION_NA, "confidence_note": note}
    return fn


def derived_carbon_conversion(char_fraction, moisture, feed_kg_h=fe.FE001_DEFAULT_DELIVERY_RATE_KG_H):
    """(conversion, note). Char = carbon_unconverted + ash, so conversion = 1 - (char - ash) / carbon_in, clamped to [0, 1]."""
    dry = feed_kg_h * (1.0 - moisture)
    ash = dry * ga.ASH_FRACTION
    carbon_in = dry * (1.0 - ga.ASH_FRACTION) * ga.FEEDSTOCK_C_FRACTION
    char = char_fraction * feed_kg_h
    conv = 1.0 - (char - ash) / carbon_in
    clamped = min(1.0, max(0.0, conv))
    note = (f"derived from RFI2 #8: char {char_fraction:.0%} of {feed_kg_h:.2f} kg/h = {char:.2f} kg/h, ash {ash:.2f} kg/h, carbon fed {carbon_in:.2f} kg/h"
            + ("; the char share exceeds carbon plus ash, clamped to 0" if conv < 0 else ""))
    return clamped, note


def _no_dryer(moisture):
    def fn(get_input):
        wet = get_input(("FE-004", "ShredderPower"))["value"]["outlet_kg_h"]
        dry = wet * (1.0 - moisture)
        return {"value": {"dry_solids_kg_h": dry, "outlet_wet_kg_h": wet, "outlet_moisture_fraction": moisture,
                          "residual_water_kg_h": wet - dry, "water_evaporated_kg_h": 0.0},
                "status": ps.STATUS_ASSUMED, "model": "rfi2_basis.no_dryer", "inputs": [("FE-004", "ShredderPower")],
                "validation_basis": ps.VALIDATION_NA,
                "confidence_note": f"RFI2 #5: the feed is not dried; all {moisture:.0%} moisture (Assumed, RFI2 allows up to 15 %) reaches the reactor."}
    return fn


def overrides(char_fraction=CHAR_FRACTION_DEFAULT, moisture=MOISTURE_DEFAULT):
    """Engine overrides of the RFI2 basis (a dict for tab1_integration.build_live_snapshot / build_engine)."""
    conv, note = derived_carbon_conversion(char_fraction, moisture)
    return {AGENT_KEY: _const(AGENT, "RFI2 #1-#4: no gasifying agent (ER 0, no oxidant)."),
            STEAM_KEY: _const(0.0, "RFI2 #4: 0 kg/h injected steam."),
            CONV_KEY: _const(conv, "Carbon conversion " + note),
            FE005_KEY: _no_dryer(moisture)}


def _dryer(moisture=0.10, outlet=fe.FE005_OUTLET_MOISTURE_FRACTION):
    def fn(get_input):
        wet = get_input(("FE-004", "ShredderPower"))["value"]["outlet_kg_h"]
        dry = wet * (1.0 - moisture)
        outlet_wet = dry / (1.0 - outlet)
        return {"value": {"dry_solids_kg_h": dry, "outlet_wet_kg_h": outlet_wet, "outlet_moisture_fraction": outlet,
                          "residual_water_kg_h": outlet_wet - dry, "water_evaporated_kg_h": wet - outlet_wet},
                "status": ps.STATUS_ASSUMED, "model": "rfi2_basis.earlier_dryer", "inputs": [("FE-004", "ShredderPower")],
                "validation_basis": ps.VALIDATION_NA,
                "confidence_note": "Earlier model basis: the feed is dried from 10 % to the registry's <1 % target (contradicted by DOK-ING RFI2 #5)."}
    return fn


def model_overrides():
    """Engine overrides that restore the earlier (pre-RFI2) basis: air at ER 0.25, feed dried to about 1 %, carbon conversion 0.90."""
    return {AGENT_KEY: _const(ga.AIR_AGENT, "Earlier model basis: air-blown (contradicted by DOK-ING RFI2 #1-#4)."),
            CONV_KEY: _const(ga.CARBON_CONVERSION_EFFICIENCY, "Earlier model basis: literature-typical air/steam-blown conversion."),
            FE005_KEY: _dryer()}


def run(basis, n_cycles=10, char_fraction=CHAR_FRACTION_DEFAULT, moisture=MOISTURE_DEFAULT):
    """Snapshot after n_cycles. basis: 'model' (the earlier basis) or 'rfi2' (the default engine; overrides only for a non-default char share or moisture)."""
    if basis not in ("model", "rfi2"):
        raise ValueError(f"basis {basis!r} is not 'model' or 'rfi2'")
    if basis == "model":
        ov = model_overrides()
    elif abs(char_fraction - CHAR_FRACTION_DEFAULT) < 1e-12 and abs(moisture - MOISTURE_DEFAULT) < 1e-12:
        ov = None
    else:
        ov = overrides(char_fraction, moisture)
    snap, _s, _e = t1.build_live_snapshot(n_cycles, overrides=ov)
    return snap


def kpis(snap):
    """Plain numbers of one snapshot for the side-by-side table (None where Missing)."""
    k = t1.compute_tab1_kpis(snap)
    h2 = k["total_h2_production"]
    out = snap[("GA-001", "Outputs")]["value"]
    ca = snap.get(("GA-001", "CarbonAccounting"))
    psa = snap.get(("HB-006", "PSA"))
    cool = snap.get(("EU-008", "CoolingSupply"))
    f = lambda v: None if v is None else float(v)
    return {
        "Hydrogen (kg/day)": None if h2.get("status") == "Missing" or h2.get("value") is None else float(h2["value"]) * 24.0,
        "Raw syngas, dry (Nm3/h)": f(out["dry_flow_nm3_h"]),
        "H2 (mol% dry)": f(out["H2_mol_pct_dry"]), "CO (mol% dry)": f(out["CO_mol_pct_dry"]), "CO2 (mol% dry)": f(out["CO2_mol_pct_dry"]),
        "CH4 (mol% dry)": f(out["CH4_mol_pct_dry"]), "N2 (mol% dry)": f(out["N2_mol_pct_dry"]),
        "Carbon black / char carbon (kg/h)": f(ca["value"]["carbon_black_kg_h"]) if ca and ca.get("status") != "Missing" else None,
        "PSA recovery": f(psa["value"]["recovery"]) if psa and psa.get("status") != "Missing" else None,
        "Cooling demand EU-008 (kW)": f(cool["value"]["demand_kw"]) if cool and cool.get("status") != "Missing" else None,
    }


def compare(n_cycles=10, char_fraction=CHAR_FRACTION_DEFAULT, moisture=MOISTURE_DEFAULT):
    """{'model': kpis, 'rfi2': kpis} of the two bases."""
    return {"model": kpis(run("model", n_cycles)), "rfi2": kpis(run("rfi2", n_cycles, char_fraction, moisture))}
