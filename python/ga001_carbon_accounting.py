"""
(GA-001, CarbonAccounting) -- the single carbon bookkeeping of GA-001 (carbon-bookkeeping task, item B). A leaf: nothing depends on it.

Before: GA-001 sent `conversion` (0.90) of the fuel carbon to the gas and the other 10 % had no stream, while the carbon-black flow came from an
independent constant (5 % of dry feed, gasifier_mass_balance.py, derived from GA-008's 1.88 kg/h at the old 37.5 kg/h design point). The two disagreed
(+0.138 kg/h at the default).

Now: the carbon conversion is the single governing value.
    unconverted carbon  = (1 - conversion) x (feed carbon + recycled carbon)          [ga001.unconverted_carbon_fraction; the same function the
                                                                                      C check of verify_atom_balance uses]
    carbon black        = unconverted carbon x split                                   [split: ("GA-001-INPUT","unconverted_carbon_to_carbon_black"),
                                                                                      Assumed 1.0, range 0.5-1.0]
    remainder           = unconverted carbon x (1 - split)                             [destination Missing: bed-drain carry-over / cyclone catch /
                                                                                      fly ash split is not known; published, not discarded]
The recycled carbon is whatever GA-001 itself received (lagged HB-009 tail gas in `regasify`, none in `heat_only`), read exactly as GA-001 reads it.

The old 5 % constant and the GA-008 datasheet figure stay as a CROSS-CHECK only (`datasheet_cross_check`): it feeds nothing. A consistency check of
the gas side is published too: carbon in - carbon in the published gas - unconverted carbon (zero to rounding).

Ash is untouched (same constant on both sides). Water, sulphur, chlorine and tar sinks, the fly-ash / bottom-ash split and the cycle-1 bootstrap are out
of scope and listed as Missing.
"""
from . import balance_audit as ba
from . import gasifier_mass_balance as gmb
from . import ga001_energy_balance as eb
from . import ga001_gasifier_model as ga001
from . import plant_status as ps

KEY = ("GA-001", "CarbonAccounting")
DEPENDS_ON = list(eb.DEPENDS_ON[:-1]) + [ga001.CARBON_BLACK_SPLIT_KEY]       # GA-001 Outputs, 7 inputs, tail_gas_mode, FE-005 (HB-005 is not needed here), the split
LAGGED = [("HB-009", "TailGas")]

# GA-008 datasheet / registry values (data/equipment_registry.json, read when this task was written; the file is not edited or read at run time)
GA008_NOMINAL_KG_H_AT_OLD_DESIGN = 1.88         # GA-008 "Design capacity" remark: "~1.88 kg/h nominal (2.25 kg/h at 120% turndown) already used in the mass/energy balance"
OLD_DESIGN_DRY_FEED_KG_H = 37.5                 # the original design point that figure belongs to (gasifier_mass_balance.py docstring)
GA008_CAPACITY_KG_H = 3.0                       # GA-008 "Design capacity"
MISSING_TERMS = [
    "the split of the unconverted carbon between carbon black, bed-drain carry-over, cyclone catch and fly ash (no DOK-ING data)",
    "carbon content of the carbon-black stream (taken as pure carbon; GA-008 states product ash < 1 wt %)",
    "fly ash vs bottom ash split of the 10 % ash, tar, and the water / sulphur / chlorine sinks (out of scope of this task)",
    "the cycle-1 bootstrap: on cycle 1 GA-001 uses the 41.67 kg/h wet figure as dry feed (out of scope, unchanged)",
]


def carbon_accounting(get_input):
    view = eb._View(get_input)
    split = ga001.check_carbon_black_split(get_input(ga001.CARBON_BLACK_SPLIT_KEY)["value"])
    d = ba.ga001_terms(view, view, derived_carbon_black=False)
    inp = d["inputs"]
    k = ba.ATOMIC_MASS["C"] / 1000.0                                  # kg per mol C
    conv = float(inp["carbon_conversion_efficiency"])
    unconv_frac = ga001.unconverted_carbon_fraction(conv)
    c_feed, c_rec = d["feed_atoms"]["C"], d["recycle_atoms"]["C"]
    c_in = c_feed + c_rec
    unconv_feed, unconv_rec = unconv_frac * c_feed * k, unconv_frac * c_rec * k
    unconv = unconv_feed + unconv_rec
    cb = unconv * split
    remainder = unconv * (1.0 - split)
    gas = ba.gas_species_mol_h(view["GA-001", "Outputs"]["value"])
    c_gas = gas["CO"] + gas["CO2"] + gas["CH4"]
    gas_side = (c_in - c_gas) * k                                      # carbon that is in the fuel atoms but not in the published gas
    f = float(inp["dry_feed_rate_kg_h"])
    datasheet = gmb.byproduct_mass_flows(f)["carbon_black_kg_h"]       # the old rule: 5 % of the dry feed
    at_old_design = GA008_NOMINAL_KG_H_AT_OLD_DESIGN * f / OLD_DESIGN_DRY_FEED_KG_H
    ratio = (cb / datasheet) if datasheet else None
    within = cb <= GA008_CAPACITY_KG_H
    status_line = (f"derived {cb:.3f} kg/h against datasheet rule {datasheet:.3f} kg/h (5 % of {f:.2f} kg/h dry feed; GA-008's {GA008_NOMINAL_KG_H_AT_OLD_DESIGN} kg/h at the old "
                   f"{OLD_DESIGN_DRY_FEED_KG_H} kg/h design point scales to {at_old_design:.3f}); GA-008 capacity {GA008_CAPACITY_KG_H} kg/h "
                   f"{'not exceeded' if within else 'EXCEEDED -- registry not changed'}")
    value = {
        "governing_parameter": "carbon_conversion_efficiency", "carbon_conversion_efficiency": conv, "unconverted_carbon_fraction": unconv_frac,
        "carbon_in_kg_h": c_in * k, "carbon_in_from_feed_kg_h": c_feed * k, "carbon_in_from_recycle_kg_h": c_rec * k,
        "tail_gas_mode": ga001._tail_gas_mode(get_input),
        "unconverted_carbon_kg_h": unconv, "unconverted_from_feed_kg_h": unconv_feed, "unconverted_from_recycle_kg_h": unconv_rec,
        "unconverted_carbon_formula": "(1 - conversion) x (feed carbon + recycled carbon); recycled CO/CH4 carbon is cut by the same conversion because GA-001 works per mol of the combined fuel carbon",
        "carbon_black_split": split, "carbon_black_split_status": ps.STATUS_ASSUMED, "carbon_black_split_range": list(ga001.CARBON_BLACK_SPLIT_RANGE),
        "carbon_black_kg_h": cb, "carbon_black_status": ps.STATUS_CALCULATED,
        "remainder_kg_h": remainder, "remainder_destination_status": ps.STATUS_MISSING,
        "remainder_note": "unconverted carbon not taken as carbon black; its split between bed-drain carry-over, cyclone catch and fly ash is Missing (0 here only because the Assumed split is 1.0)",
        "gas_side_check": {"carbon_in_minus_gas_carbon_kg_h": gas_side, "difference_to_unconverted_kg_h": gas_side - unconv,
                           "note": "zero to rounding: the published gas carries exactly the converted carbon"},
        "datasheet_cross_check": {
            "feeds_nothing": True, "datasheet_rule_kg_h": datasheet, "datasheet_rule": "CARBON_BLACK_FRACTION 0.05 x dry feed (gasifier_mass_balance.py)",
            "ga008_nominal_at_old_design_scaled_kg_h": at_old_design, "ratio_derived_over_datasheet": ratio,
            "ga008_capacity_kg_h": GA008_CAPACITY_KG_H, "ga008_capacity_exceeded": not within, "status_line": status_line,
        },
        "missing_terms": list(MISSING_TERMS),
    }
    return {
        "value": ba_native(value), "status": ps.STATUS_CALCULATED, "model": "ga001_carbon_accounting.carbon_accounting",
        "inputs": list(DEPENDS_ON) + list(LAGGED), "validation_basis": ps.VALIDATION_ENGINEERING_CORRELATION,
        "confidence_note": (
            "Unconverted carbon = (1 - conversion) x all fuel-carbon atoms (recycle included), Calculated from the GA-001 inputs; carbon black = unconverted x the Assumed "
            f"split ({split}, range {ga001.CARBON_BLACK_SPLIT_RANGE}); the remainder's destination is Missing. The 5 % datasheet rule is a cross-check only. {status_line}."
        ),
    }


def ba_native(x):
    return eb._native(x)


def register(engine):
    engine.register_model(KEY, carbon_accounting, unit="kg/h dict", depends_on=list(DEPENDS_ON), lagged_depends_on=list(LAGGED))
