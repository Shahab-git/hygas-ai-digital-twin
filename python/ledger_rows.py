"""
Design-basis ledger rows that the parameter table did not have (task A3). Every row READS the value from the place that owns it:

  * a module constant       -> getattr on the module (the same object the engine uses);
  * a literal inside a function (a hard-coded number such as `efficiency = 0.95` in gc003_dust) -> the literal is read from the function's `ast`
                               by python/ledger_coverage.py, so a moved or renamed literal fails loudly (LookupError). Nothing is copied into a second place and no engine file is edited;
  * an entry of a dict constant (plant_heat_integration.ASSUMED, uncertainty.ASSUMPTIONS, ...) -> a path into that dict.

Status rule (no status is invented): a row with a registry counterpart (`reg` = (item id, parameter), the same physical quantity, sometimes in other units) takes the status,
origin and source_line that registry_status.resolve_row gives that registry row from the committed provenance overlay (so: Unverified (registry) unless the owner's worksheet says
otherwise). A row without a counterpart is `Assumed`, with the table's "STATUS ASSIGNED BY THIS TABLE" note: the repo carries no status tag for it, and the comment in the code that calls
it "Confirmed" is quoted in the note where there is one, never relied on. A range is given only where the repo holds one; otherwise range_low / range_high are None (Missing).

`TABLE_COVERS` says which scanned constants the 26 rows of parameter_table.build_table() already stand for. `UPGRADE` maps a tag to the question that would upgrade it; there is no entry
(None) when the repo holds no such question. Not imported by the engine, the runtime or the app.
"""
import importlib

from . import equipment_registry, ledger_anchors, ledger_coverage as lc, plant_status as ps, registry_status

_PKG = __package__ or "python"
VIA_CODE = "code only"
_ASSIGNED = "STATUS ASSIGNED BY THIS TABLE (the repo carries no status tag for this constant): "

# the questions, as references (python/ledger_questions.py): `master_open_questions:1.<n>` = item n of Section 1 of docs/master_open_questions.md, `master_open_questions:3.<n>` = item n of
# its list of specific items in Section 3; RFI2-<n> / RFI1-<n> are the questions of docs/rfi2_dokink.md and data/rfi_dokink.md (see ledger_questions.RFI_MAP)
_MQ = "master_open_questions:%s"
Q_EU008, Q_FEED, Q_COMP, Q_LHV, Q_OC, Q_AIR = (_MQ % "1.1", _MQ % "1.2", _MQ % "1.3", _MQ % "1.4", _MQ % "1.5", _MQ % "1.6")
Q_HB003, Q_HCL, Q_SPLIT, Q_MEMB, Q_LOHC = _MQ % "1.7", _MQ % "1.8", _MQ % "1.9", _MQ % "1.10", _MQ % "1.11"
Q_SIZING, Q_CYCLE, Q_POLY, Q_PEM = _MQ % "3.1", _MQ % "3.2", _MQ % "3.3", _MQ % "3.4"

# tag -> the constants of the scanned modules that an EXISTING parameter_table row stands for
_G, _GM, _U = "python/ga001_gasifier_model.py", "python/gasifier_mass_balance.py", "python/uncertainty.py"
TABLE_COVERS = {
    "GA-001.feedstock_daf_CHON": [lc.const_key(_G, n) for n in ("FEEDSTOCK_C_FRACTION", "FEEDSTOCK_H_FRACTION", "FEEDSTOCK_O_FRACTION", "FEEDSTOCK_N_FRACTION")],
    "GA-001.carbon_conversion": [lc.const_key(_G, "CARBON_CONVERSION_EFFICIENCY"), lc.const_key(_G, "CARBON_CONVERSION_EFFICIENCY_RANGE")],
    "GA-001.ch4_carbon_fraction": [lc.const_key(_G, "CH4_CARBON_FRACTION"), lc.const_key(_G, "CH4_CARBON_FRACTION_RANGE")],
    "GA-001.T_gasifier_C": [lc.const_key(_G, "GA001_OPERATING_TEMPERATURE_C")],
    "GA-001.unconverted_C_to_carbon_black": [lc.const_key(_G, "CARBON_BLACK_SPLIT_DEFAULT"), lc.const_key(_G, "CARBON_BLACK_SPLIT_RANGE")],
    "GA-001.dry_feed_kg_h": [lc.const_key(_GM, "DEFAULT_AS_RECEIVED_FEED_KG_H")],     # P1-05(c): the literal 41.67 is now DEFAULT_AS_RECEIVED_FEED_KG_H; DEFAULT_DRY_FEED_KG_H is derived from it
    "GA-001.ash_fraction": [lc.const_key(_GM, "ASH_FRACTION")],
    "GA-001.ER": [lc.const_key(_U, "ASSUMPTIONS")],
    "GA-001.steam_to_feed_kg_kg": [lc.const_key(_U, "ASSUMPTIONS")],
    "HB-006.psa_target_calibration": [lc.const_key(_U, "ASSUMPTIONS")],
    "HB-004.wgs_target_calibration": [lc.const_key(_U, "ASSUMPTIONS")],
    "HB-006.psa_K1": [lc.const_key("python/psa.py", "K1")],
    "HB-006.psa_void_loss": [lc.const_key("python/psa.py", "VOID_LOSS")],
    "HB-006.psa_selectivity": [lc.const_key("python/psa.py", "SELECTIVITY")],
}

# tag of an existing row -> the question that would upgrade it (None = the repo holds none)
UPGRADE = {
    "GA-001.ER": Q_AIR, "GA-003.air_flow_design_Nm3_h": Q_AIR, "GA-001.feedstock_daf_CHON": Q_COMP, "GA-001.ash_fraction": Q_COMP, "GA-001.dry_feed_kg_h": Q_FEED,
}

# where a code-only / dynamics row of the table is READ from (the AST-referrer search uses this name): tag -> (module, NAME)
TABLE_TOKENS = {
    "GA-001.ash_fraction": ("gasifier_mass_balance", "ASH_FRACTION"), "HB-006.psa_K1": ("psa", "K1"), "HB-006.psa_void_loss": ("psa", "VOID_LOSS"),
    "HB-006.psa_selectivity": ("psa", "SELECTIVITY"), "HB-006.psa_target_calibration": ("uncertainty", "ASSUMPTIONS"),
    "HB-004.wgs_target_calibration": ("uncertainty", "ASSUMPTIONS"),
    "EU-008.tau_cooling_water_s": ("dynamics", "TAU_SPECS"), "GA-001.tau_T_s": ("dynamics", "TAU_SPECS"), "GA-001.tau_conv_s": ("dynamics", "TAU_SPECS"),
    "GA-001.tau_gas_s": ("dynamics", "TAU_SPECS"), "HB-009.tau_rec_s": ("dynamics", "TAU_SPECS"),
}

# --- the new rows -----------------------------------------------------------------------------------------------------------------------------
# c: (tag, "c", module, NAME, unit, reg, upgrade, note)
# l: (tag, "l", module, (function, [literal, ...]), unit, reg, upgrade, note)      the literals are those of that function, read from its ast
# p: (tag, "p", module, (NAME, key, key, ...), unit, reg, upgrade, note)           one entry of a dict constant (ranges are read from the same entry where it has them)
R = []


def _c(tag, mod, name, unit, reg=None, up=None, note=""):
    R.append((tag, "c", mod, name, unit, reg, up, note))


def _l(tag, mod, fn, vals, unit, reg=None, up=None, note=""):
    R.append((tag, "l", mod, (fn, vals), unit, reg, up, note))


def _p(tag, mod, path, unit, reg=None, up=None, note=""):
    R.append((tag, "p", mod, path, unit, reg, up, note))


# GA-001 / gasification side
_c("GA-001.oxygen_carrier_to_fuel_ratio_range", "ga001_gasifier_model", "OXYGEN_CARRIER_TO_FUEL_RATIO_RANGE", "kg carrier / kg fuel", None, Q_OC,
   "The constant IS a range (low, high); oxygen_carrier_circulation_estimate (a literature estimate, not wired into the physics) uses it.")
_c("GA-001.oxygen_carrier_utilization_range", "ga001_gasifier_model", "OXYGEN_CARRIER_CONSERVATIVE_UTILIZATION_RANGE", "-", None, Q_OC, "The constant IS a range (low, high).")
_c("GA-008.nominal_kg_h_at_old_design", "ga001_carbon_accounting", "GA008_NOMINAL_KG_H_AT_OLD_DESIGN", "kg/h", None, None,
   "GA-008 'Design capacity' remark: ~1.88 kg/h nominal at the ORIGINAL 37.5 kg/h dry-feed design point; used only as a cross-check of the derived carbon black.")
_c("GA-008.old_design_dry_feed_kg_h", "ga001_carbon_accounting", "OLD_DESIGN_DRY_FEED_KG_H", "kg/h", None, Q_FEED,
   "The original dry-feed design point the 1.88 kg/h belongs to (gasifier_mass_balance.py docstring), kept for the cross-check.")
_c("GA-008.capacity_kg_h", "ga001_carbon_accounting", "GA008_CAPACITY_KG_H", "kg/h", ("GA-008", "Design capacity"), None, "GA-008 'Design capacity'; the cross-check flags a derived carbon black above it.")
_c("GA-001.carbon_black_fraction_legacy", "gasifier_mass_balance", "CARBON_BLACK_FRACTION", "mass fraction of dry feed", None, None,
   "Legacy fixed 5 % carbon black; since the carbon bookkeeping task the carbon black is DERIVED in (GA-001, CarbonAccounting), so this constant may have no live consumer (see consumers).")
_c("GA-001.inlet_moisture_fraction_static", "gasifier_mass_balance", "DEFAULT_INLET_MOISTURE_FRACTION", "mass fraction", None, Q_FEED,
   "P1-05(c): Assumed 10 % inlet moisture (DOK-ING gave 5-15 (20) %, basis not stated); the static copy of fe_feed_handling.FE005_INLET_MOISTURE_FRACTION, equality pinned by tests/test_p1_05c_feed_basis.py.")
# gas cleaning
_c("GC-005.blowdown_to_circulation_ratio", "gc_gas_cleaning_chain", "QUENCH_BLOWDOWN_TO_CIRCULATION_RATIO", "-", ("GC-005", "Blowdown rate"), None,
   "0.05 / 0.5 = registry blowdown 0.05 m3/h over water consumption 0.5 m3/h (a ratio of two GC-005 rows); reused for GC-007/008/009 as well.")
_c("GC-014.design_discharge_mbar_g", "gc_gas_cleaning_chain", "GC014_DESIGN_DISCHARGE_MBAR_G", "mbar(g)", ("GC-014", "Design discharge pressure"))
_c("GC-014.design_suction_mbar_g", "gc_gas_cleaning_chain", "GC014_DESIGN_SUCTION_MBAR_G", "mbar(g)", ("GC-014", "Design suction pressure"))
_c("GA-002.typical_pressure_mbar_g", "gc_gas_cleaning_chain", "GA002_TYPICAL_PRESSURE_MBAR_G", "mbar(g)", ("GA-001", "Operating pressure (typical)"), None,
   "100 mbar(g) is the middle of GA-002's registry range 50-150 mbar(g); used as a consistency check on GC-014's suction pressure. "
   "The registry counterpart is GA-001 'Operating pressure (typical)' (100 mbar(g), the reactor-vessel entry of the same gasifier); GA-002 holds the 50-150 mbar(g) band, "
   "whose remark takes 100 as typical (a self-reference, not independent evidence); the tag prefix GA-002 is naming only.")
_c("GC-015.ambient_temp_C", "gc_gas_cleaning_chain", "GC015_AMBIENT_TEMP_C", "degC", ("GC-005", "Water supply temperature"), None, "Lower bound of GC-015's operating-temperature range.")
_c("GC.stage_delta_p_mbar", "gc_gas_cleaning_chain", "_STAGE_DELTA_P_MBAR", "mbar", None, None,
   "Design pressure drop of GC-002, 003, 006, 007, 011, 012, summed for the GC-013 fan cross-check; the code comment calls them 'Confirmed' (registry), quoted not relied on.")
_c("GC-015.inflow_temps_C", "gc_gas_cleaning_chain", "_GC015_INFLOW_TEMPS_C", "degC", None, None,
   "Inflow temperatures of the five streams that blend in GC-015 (the GC-007/008 values are an interpolation the code comment states).")
_l("GC-001.outlet_temperature_C", "gc_gas_cleaning_chain", "gc001_temperature", [880.0], "degC", ("GC-001", "Outlet gas temperature (design)"), None,
   "Published as the GC-001 static value (status Assumed in the engine entry).")
_l("GC-003.inlet_dust_mg_nm3", "gc_gas_cleaning_chain", "gc003_dust", [2000.0], "mg/Nm3", ("GC-003", "Dust loading inlet (max)"))
_l("GC-003.efficiency", "gc_gas_cleaning_chain", "gc003_dust", [0.95], "-", ("GC-003", "Collection efficiency > 10 µm"))
_l("GC-003.outlet_temperature_C", "gc_gas_cleaning_chain", "gc003_temperature", [870.0], "degC", ("GC-003", "Inlet gas temperature"), None, "Published as the GC-003 static value.")
_l("GC-004.inlet_temperature_C", "gc_gas_cleaning_chain", "gc004_cooling_duty", [860.0], "degC", ("GC-004", "Inlet gas temperature"))
_l("GC-004.outlet_temperature_C", "gc_gas_cleaning_chain", "gc004_cooling_duty", [65.0], "degC", ("GC-004", "Outlet gas temperature (design)"))
_l("GC-005.blowdown_m3_h", "gc_gas_cleaning_chain", "gc005_blowdown", [0.05], "m3/h", ("GC-005", "Blowdown rate"))
_l("GC-006.tar_outlet_mg_nm3", "gc_gas_cleaning_chain", "gc006_tar_outlet", [500.0], "mg/Nm3", None, None, "Published as the GC-006 static value (status Assumed in the engine entry).")
_l("GC-007.tar_outlet_target_mg_nm3", "gc_gas_cleaning_chain", "gc007_tar", [50.0], "mg/Nm3", ("GC-007", "Tar outlet concentration (target)"))
_l("GC-008.h2s_inlet_ppm", "gc_gas_cleaning_chain", "gc008_h2s", [200.0], "ppm", ("GC-008", "H₂S inlet concentration (design)"))
_l("GC-008.liquid_to_gas_l_nm3", "gc_gas_cleaning_chain", "gc008_blowdown", [3.0], "L/Nm3", ("GC-008", "Liquid-to-gas ratio"))
_l("GC-009.hcl_inlet_ppm", "gc_gas_cleaning_chain", "gc009_hcl", [150.0], "ppm", ("GC-009", "Inlet HCl concentration"), Q_HCL)
_l("GC-009.hcl_outlet_target_ppm", "gc_gas_cleaning_chain", "gc009_hcl", [5.0], "ppm", ("GC-009", "Outlet HCl concentration (target)"), Q_HCL)
_l("GC-009.liquid_to_gas_l_nm3", "gc_gas_cleaning_chain", "gc009_blowdown", [2.5], "L/Nm3", ("GC-009", "Liquid-to-gas ratio"))
_l("GC-010.inlet_dust_mg_nm3", "gc_gas_cleaning_chain", "gc010_dust", [300.0], "mg/Nm3", ("GC-010", "Inlet dust loading"))
_l("GC-010.outlet_target_mg_nm3", "gc_gas_cleaning_chain", "gc010_dust", [5.0], "mg/Nm3", ("GC-010", "Outlet dust loading (design)"))
_l("GC-012.h2s_cos_outlet_target_ppm", "gc_gas_cleaning_chain", "gc012_h2s_cos_polish", [0.1], "ppm", ("GC-012", "H₂S / COS removal target"))
# WGS / PSA / storage
_c("HB-005.steam_to_co_molar_ratio", "hb_wgs_psa_storage_chain", "STEAM_TO_CO_MOLAR_RATIO", "mol/mol", ("HB-005", "Steam-to-CO ratio"), None,
   "Registry value text is '4:1' (stored mangled as 04:01:00).")
_c("HB-001.inlet_temperature_C", "hb_wgs_psa_storage_chain", "HTS_INLET_TEMPERATURE_C", "degC", ("HB-001", "Inlet temperature (design)"))
_c("HB-001.ghsv_per_h", "hb_wgs_psa_storage_chain", "HTS_GHSV", "1/h", None, None, "No registry row states a GHSV.")
_c("HB-004.ghsv_per_h", "hb_wgs_psa_storage_chain", "LTS_GHSV", "1/h", None, None, "No registry row states a GHSV.")
_c("HB-003.hot_inlet_C", "hb_wgs_psa_storage_chain", "HB003_HOT_INLET_C", "degC", ("HB-003", "Hot side inlet temperature"), Q_HB003)
_c("HB-003.hot_outlet_C", "hb_wgs_psa_storage_chain", "HB003_HOT_OUTLET_C", "degC", ("HB-003", "Hot side outlet temperature"), Q_HB003)
_c("HB-003.cold_inlet_C", "hb_wgs_psa_storage_chain", "HB003_COLD_INLET_C", "degC", ("HB-003", "Cold side inlet temperature"), Q_HB003)
_c("HB-003.cold_outlet_C", "hb_wgs_psa_storage_chain", "HB003_COLD_OUTLET_C", "degC", ("HB-003", "Cold side outlet temperature"), Q_HB003)
_c("HB-008.psa_adsorption_pressure_bar_a", "hb_wgs_psa_storage_chain", "PSA_ADSORPTION_PRESSURE_BAR_A", "bar(a)", ("HB-008", "Adsorption pressure (design)"), None, "Registry 7 bar(g) + about 1 atm.")
_c("HB-008.psa_regen_pressure_bar_a", "hb_wgs_psa_storage_chain", "PSA_REGEN_PRESSURE_BAR_A", "bar(a)", ("HB-008", "Regeneration pressure"), None, "Registry 0.2 bar(g) + about 1 atm.")
_c("HB-012.suction_bar_a", "hb_wgs_psa_storage_chain", "COMPRESSOR_SUCTION_BAR_A", "bar(a)", ("HB-012", "Inlet pressure"), None, "Registry 7 bar(g) + about 1 atm.")
_c("HB-012.discharge_bar_a", "hb_wgs_psa_storage_chain", "COMPRESSOR_DISCHARGE_BAR_A", "bar(a)", ("HB-012", "Discharge pressure (design)"), None,
   "Three layers. DOK-ING states a magnitude of 700 bar (RFI answer 8, data/dokink_rfi_answers.md:35-36: 'compression to 350/700 bar for mobility dispensing/tube trailers'), "
   "with no gauge or absolute basis. The registry designates it bar(g) (HB-012 'Discharge pressure (design)'). The gauge basis taken from that designation and the +1 bar offset "
   "(atmosphere taken as 1 bar, not 1.01325) that gives 701.0 bar(a) are this project's conversions. The Confirmed status covers the stated 700 bar magnitude only.")
_c("GA-001.agent_check_expected_n2_vol_pct", "ga001_gasifier_model", "SA005_EXPECTED_N2_VOL_PCT", "vol%", ("SA-005", "Expected N₂ concentration"), None,
   "The registry's expected N2 that the read-only agent-consistency check compares with the model's dry N2. The registry row says 10 vol% without a wet or dry basis; the check assumes none. It feeds no value.")
_c("GA-001.agent_air_o2_fraction", "ga001_gasifier_model", "AGENT_AIR_O2_FRACTION", "-", None, None,
   "O2 mole fraction of dry air, the label of the 'air' agent; the air path itself uses AIR_N2_PER_O2 (0.79 / 0.21). Assumed, no DOK-ING source.")
_c("GA-001.agent_o2_fraction", "ga001_gasifier_model", "AGENT_O2_FRACTION", "-", None, None,
   "O2 mole fraction of the oxidant of the enriched_30, enriched_50 and oxygen agents (gasifying-agent study S1a, S1b, S2). Assumed, no DOK-ING source until RFI #2 A1-A3 answer.")
_c("GA-001.agent_er_override", "ga001_gasifier_model", "AGENT_ER_OVERRIDE", "-", None, None,
   "ER the steam-only agents use (no oxidant: 0). Assumed (gasifying-agent study S4a, S4b); the 'air' and oxygen agents read the existing ER input.")
_c("GA-001.agent_steam_override", "ga001_gasifier_model", "AGENT_STEAM_OVERRIDE", "kg/kg", None, None,
   "Steam-to-feed ratio of the steam_only_0.8 agent (study S4b); the other agents read the existing steam_to_feed_ratio input. Assumed, no DOK-ING source.")
_c("HB-012.polytropic_n", "hb_wgs_psa_storage_chain", "COMPRESSOR_POLYTROPIC_N", "-", None, Q_POLY, "Literature-typical value for a well-intercooled multistage compressor, not HB-012's own data (docs/master_open_questions.md).")
_c("HB-013.storage_capacity_kg", "hb_wgs_psa_storage_chain", "H2_STORAGE_CAPACITY_KG", "kg H2", ("HB-013", "Storage capacity"))
_c("PLANT.assumed_hours_per_cycle", "hb_wgs_psa_storage_chain", "ASSUMED_HOURS_PER_CYCLE", "h", None, Q_CYCLE,
   "A modelling choice: the inventories (HB-013, FE-001, EU-010) integrate over scripts/run_continuous_cycle.py's measured elapsed time (python/cycle_clock.py); this constant is the fallback.")
_l("HB-005.steam_temperature_C", "hb_wgs_psa_storage_chain", "hb005_steam_generation", [350.0], "degC", ("HB-005", "Steam temperature"), None, "Published in the HB-005 entry as steam_temp_c.")
_l("HB-005.steam_pressure_bar_g", "hb_wgs_psa_storage_chain", "hb005_steam_generation", [5.0], "bar(g)", ("HB-005", "Steam pressure (design)"), None, "Published in the HB-005 entry as steam_pressure_bar_g.")
_l("HB-012.suction_temperature_C", "hb_wgs_psa_storage_chain", "hb012_compressor", [25.0], "degC", None, None, "Suction temperature of the polytropic power formula (the code writes 25.0 + 273.15).")
# remaining chain
_c("AI-001.illustrative_availability_fraction", "hb_remaining_chain", "AI001_ILLUSTRATIVE_AVAILABILITY_FRACTION", "-", None, None, "The name says illustrative: an example availability, not a measured one.")
_c("HB-011.rated_power_kw", "hb_remaining_chain", "HB011_RATED_POWER_KW", "kW", ("HB-011", "Rated power input"))
_c("HB-011.rated_h2_nm3_h", "hb_remaining_chain", "HB011_RATED_H2_NM3_H", "Nm3/h", ("HB-011", "H₂ production rate (rated)"), None, "Informational cross-check only (code comment).")
_c("HB-011.sec_rated_kwh_per_nm3", "hb_remaining_chain", "HB011_SEC_RATED_KWH_PER_NM3", "kWh/Nm3 H2", ("HB-011", "System efficiency"))
_c("HB-011.water_l_per_nm3", "hb_remaining_chain", "HB011_WATER_L_PER_NM3", "L/Nm3 H2", ("HB-011", "Water consumption"))
_c("HB-011.min_load_fraction", "hb_remaining_chain", "HB011_MIN_LOAD_FRACTION", "-", None, Q_PEM, "Literature-typical PEM turndown, not HB-011-specific (code comment: Assumed).")
_c("HB-011.bop_power_fraction", "hb_remaining_chain", "HB011_BOP_POWER_FRACTION", "-", None, Q_PEM, "Literature-typical balance-of-plant share, not HB-011-specific (code comment: Assumed).")
_c("HB-010.feed_flow_nm3_h", "hb_remaining_chain", "HB010_FEED_FLOW_NM3_H", "Nm3/h", ("HB-010", "Feed gas flow rate"))
_c("HB-010.h2_recovery", "hb_remaining_chain", "HB010_CONFIRMED_RECOVERY", "-", ("HB-010", "H₂ recovery rate"), Q_MEMB, "The constant's name says CONFIRMED; the resolved status of the registry row it comes from is used instead.")
_c("HB-010.permeate_purity_range", "hb_remaining_chain", "HB010_CONFIRMED_PURITY_RANGE", "-", ("HB-010", "Permeate H₂ purity"), Q_MEMB, "The constant IS a range (low, high) = registry 95-98 vol%.")
_c("HB-010.design_feed_h2_fraction", "hb_remaining_chain", "HB010_CONFIRMED_DESIGN_FEED_H2_FRACTION", "-", ("HB-010", "Feed gas H₂ partial pressure"), Q_MEMB, "0.55 = registry 4.4 bar H2 partial pressure over an 8 bar feed.")
_c("HB-010.comparable_h2_co2_selectivity", "hb_remaining_chain", "HB010_COMPARABLE_H2_CO2_SELECTIVITY", "-", None, Q_MEMB, "A literature-comparable value used as an Estimated baseline (not wired into the physics).")
_c("HB-014.loading_efficiency_wt_pct", "hb_remaining_chain", "HB014_LOADING_EFFICIENCY_WT_PCT", "wt%", ("HB-014", "H₂ loading efficiency"), Q_LOHC)
_c("HB-016.release_efficiency_wt_pct", "hb_remaining_chain", "HB016_RELEASE_EFFICIENCY_WT_PCT", "wt%", ("HB-016", "H₂ release efficiency"), Q_LOHC)
_c("HB-017.recovery_efficiency", "hb_remaining_chain", "HB017_RECOVERY_EFFICIENCY", "-", ("HB-017", "Recovery efficiency"), None, "Registry '>99 %'; the point value 0.99 is used.")
_c("HB-016.dehydrogenation_ea_range_kj_mol", "hb_remaining_chain", "HB016_DEHYDROGENATION_EA_KJ_PER_MOL_RANGE", "kJ/mol", None, Q_LOHC, "The constant IS a range (low, high); literature (Garidzirai et al. 2024 is cited next to HB016_DEHYDROGENATION_RATE_CONSTANT_PER_MIN).")
_c("HB-016.dehydrogenation_rate_constant_per_min", "hb_remaining_chain", "HB016_DEHYDROGENATION_RATE_CONSTANT_PER_MIN", "1/min", None, Q_LOHC, "First-order rate constant at 300 degC from a literature source quoted in the code comment.")
_c("HB-014.hydrogenation_ea_range_kj_mol", "hb_remaining_chain", "HB014_HYDROGENATION_EA_KJ_PER_MOL_RANGE", "kJ/mol", None, Q_LOHC, "The constant IS a range (low, high).")
_c("HB-018.max_dispense_rate_kg_h", "hb_remaining_chain", "HB018_MAX_DISPENSE_RATE_KG_H", "kg/h", ("HB-018", "Dispensing rate"), None, "Registry 1.2 kg/min = 72 kg/h.")
_l("HB-016.reference_batch_time_h", "hb_remaining_chain", "hb016_kinetics_baseline", [6.0], "h", None, Q_LOHC, "A literature batch time quoted in the code comment (Garidzirai et al. 2024's own stated real batch reaction time).")
# utilities
_c("EU-003.syngas_lhv_mj_per_nm3", "eu_utilities_chp", "SYNGAS_LHV_MJ_PER_NM3", "MJ/Nm3", ("EU-003", "Fuel gas LHV required"), None, "A static design-point figure, not the live syngas LHV.")
_c("EU-006.h2_lhv_mj_per_nm3", "eu_utilities_chp", "H2_LHV_MJ_PER_NM3", "MJ/Nm3", None, None,
   "EU-006's stated basis (10.8). Since P1-05(a) it is the single hydrogen LHV: the species table SYNGAS_SPECIES_LHV_MJ_PER_NM3 H2 entry is this constant and balance_audit.efficiency_check reads it.")
_c("EU-004.jacket_kwth_rated", "eu_utilities_chp", "EU004_JACKET_KWTH_RATED", "kWth", ("EU-004", "Jacket cooling heat recovery"))
_c("EU-004.exhaust_kwth_rated", "eu_utilities_chp", "EU004_EXHAUST_KWTH_RATED", "kWth", ("EU-004", "Exhaust heat recovery"))
_c("EU-005.exhaust_flow_nm3_h_rated", "eu_utilities_chp", "EU005_EXHAUST_FLOW_NM3_H_RATED", "Nm3/h", ("EU-005", "Exhaust flow rate"))
_c("EU-007.destruction_efficiency", "eu_utilities_chp", "EU007_DESTRUCTION_EFFICIENCY", "-", None, None, "Flare destruction efficiency; no registry row states it.")
_c("EU-008.rated_capacity_kw", "eu_utilities_chp", "EU008_RATED_CAPACITY_KW", "kWth", ("EU-008", "Cooling duty"), Q_EU008)
_c("EU-008.nominal_supply_temp_C", "eu_utilities_chp", "EU008_NOMINAL_SUPPLY_TEMP_C", "degC", ("EU-008", "Cooling water supply temperature"), Q_EU008)
_c("EU-008.fan_motor_power_kw", "eu_utilities_chp", "EU008_FAN_MOTOR_POWER_KW", "kW", ("EU-008", "Fan motor power"))
_c("EU-008.overload_penalty_C_per_unit_util", "eu_utilities_chp", "EU008_OVERLOAD_PENALTY_C_PER_UNIT_UTIL", "degC per unit utilisation", None, Q_EU008, "Code comment: Assumed, a standard order-of-magnitude figure.")
_c("EU-008.damping", "eu_utilities_chp", "EU008_DAMPING", "-", None, None, "Per-cycle damping of the tower water (code comment: Assumed).")
_c("EU-008.adequacy_derogation_span_C", "eu_utilities_chp", "EU008_ADEQUACY_DEROGATION_SPAN_C", "degC", None, Q_EU008, "Code comment: Assumed.")
_c("EU-008.sizing_margin_fraction", "eu_utilities_chp", "EU008_SIZING_MARGIN_FRACTION", "-", None, Q_SIZING, "Code comment: Assumed, a standard HVAC / process-cooling design margin (10-20 %, 15 % used).")
_c("EU-010.rated_kva", "eu_utilities_chp", "EU010_RATED_KVA", "kVA", ("EU-010", "Rated power"))
_c("EU-010.backup_hours", "eu_utilities_chp", "EU010_BACKUP_HOURS", "h", ("EU-010", "Backup duration at full load"), None, "Registry 30 min = 0.5 h.")
_c("EU-010.roundtrip_efficiency", "eu_utilities_chp", "EU010_ROUNDTRIP_EFFICIENCY", "-", None, None, "Midpoint of a registry range quoted in the code comment (about 92-96 %); no equal-value registry row was found.")
_c("EU-011.exhaust_inlet_C", "eu_utilities_chp", "EU011_EXHAUST_INLET_C", "degC", ("EU-011", "Exhaust gas inlet temperature"))
_c("EU-011.exhaust_outlet_C", "eu_utilities_chp", "EU011_EXHAUST_OUTLET_C", "degC", ("EU-011", "Exhaust gas outlet temperature"))
_c("EU-003.wgs_psa_syngas_claim_fraction", "eu_utilities_chp", "WGS_PSA_SYNGAS_CLAIM_FRACTION", "-", None, None,
   "A model choice: the WGS / PSA chain takes 100 % of the syngas, so the CHP gets none (see the app.py wording item in docs/design_basis_ledger.md).")
_l("EU-009.engineering_range_bracket_kw", "eu_utilities_chp", "_engineering_range", [5.0], "kW", None, None, "Half-width of the +/- bracket put around an engineering estimate.")
_l("EU-010.initial_soc_fraction", "eu_utilities_chp", "eu010_ups_battery", [0.5], "-", None, None, "State of charge assumed when there is no previous cycle.")
_l("EU-006.part_load_efficiency_coefficients", "chp", "chp_efficiency", [0.01, 0.06, 0.35, 0.3, 1.5, 0.55, 0.03, 0.4], "-", None, None,
   "Floor 0.01 and the part-load curve coefficients of the four CHP unit types (eta = eta_rated x (1 + a(1-x) - b(1-x)^n)); no source is named in the code.")
_c("EU-006.chp_rated_efficiency", "chp", "RATED_EFFICIENCY", "-", None, None, "Rated electrical efficiency per CHP unit type (SOFC, gas engine, microturbine, PEM fuel cell).")
# feed handling
_c("FE-001.total_capacity_t", "fe_feed_handling", "FE001_TOTAL_CAPACITY_T", "t", ("FE-001", "Total hopper capacity"))
_c("FE-001.live_capacity_t", "fe_feed_handling", "FE001_LIVE_CAPACITY_T", "t", ("FE-001", "Live capacity (usable)"))
_c("FE-001.default_delivery_rate_kg_h", "fe_feed_handling", "FE001_DEFAULT_DELIVERY_RATE_KG_H", "kg/h", ("FE-003", "Nominal feed rate"), Q_FEED,
   "41.67 kg/h = 1,000 kg/day as received; the status is that of the FE-003 'Nominal feed rate' row, which the owner's worksheet marks DOK-ING.")
_c("FE-002.removal_efficiency", "fe_feed_handling", "FE002_REMOVAL_EFFICIENCY", "-", ("FE-002", "Removal efficiency"), None, "Registry '>98'; informational in the code.")
_c("FE-003.nominal_kg_h", "fe_feed_handling", "FE003_NOMINAL_KG_H", "kg/h", ("FE-003", "Nominal feed rate"), Q_FEED,
   "Registry 0.042 t/h. DOK-ING's 1,000 kg/day (RFI answer 1, data/dokink_rfi_answers.md:11) does not state wet or dry; 'as-received (wet)' is a project decision "
   "(the module docstring of python/fe_feed_handling.py, docs/master_open_questions.md Section 1 item 2); the kg/h figure is 1,000/24 arithmetic.")
_c("FE-003.min_kg_h", "fe_feed_handling", "FE003_MIN_KG_H", "kg/h", ("FE-003", "Min feed rate"), None, "Registry 0.029 t/h.")
_c("FE-003.max_kg_h", "fe_feed_handling", "FE003_MAX_KG_H", "kg/h", ("FE-003", "Max feed rate"), None, "Registry 0.05 t/h.")
_c("FE-004.motor_kw", "fe_feed_handling", "FE004_MOTOR_KW", "kW", ("FE-004", "Drive motor power"))
_c("FE-004.throughput_t_h", "fe_feed_handling", "FE004_THROUGHPUT_T_H", "t/h", ("FE-004", "Throughput capacity"))
_c("FE-005.inlet_moisture_fraction", "fe_feed_handling", "FE005_INLET_MOISTURE_FRACTION", "-", ("FE-005", "Inlet moisture (design)"), Q_COMP,
   "Registry says '10 % moisture' with no basis stated; the code applies it as a wet (as-received) mass fraction (fe_feed_handling.fe005_moisture_balance, dry = wet x (1 - 0.10)). "
   "DOK-ING supplied a RANGE, 'Moisture 5-15(20)%' (data/dokink_rfi_answers.md:15; the '(dry basis)' label there follows the LHV), not a confirmed 10 % point value; "
   "10 % is the registry's midpoint.")
_c("FE-005.outlet_moisture_fraction", "fe_feed_handling", "FE005_OUTLET_MOISTURE_FRACTION", "-", ("FE-005", "Outlet moisture (target)"), Q_COMP, "Registry '<1 %' (stored as -1); about 1 % is used.")
_l("FE-001.initial_level_fraction", "fe_feed_handling", "fe001_inventory", [0.5], "-", None, None, "Hopper level assumed when there is no previous cycle (fraction of live capacity).")
# kinetics (WGS) and PSA defaults
_l("HB-001.hts_kinetics_activation_energy_J_mol", "kinetics", "hts_conversion", [111000], "J/mol", None, None)
_l("HB-001.hts_kinetics_k0", "kinetics", "hts_conversion", [5723100000000.0], "model units", None, None)
_l("HB-001.hts_default_operating_point", "kinetics", "hts_conversion", [623.15, 2000, 0.28, 4.0], "K, 1/h, mol fraction, mol/mol", None, None, "Function defaults T_K, GHSV, y_CO_in, steam_to_CO (the engine passes its own values).")
_l("HB-004.lts_kinetics_activation_energy_J_mol", "kinetics", "lts_conversion", [75000], "J/mol", None, None)
_l("HB-004.lts_kinetics_k0", "kinetics", "lts_conversion", [339740000000.0], "model units", None, None)
_l("HB-004.lts_default_operating_point", "kinetics", "lts_conversion", [493.15, 2000, 0.07, 4.0], "K, 1/h, mol fraction, mol/mol", None, None, "Function defaults T_K, GHSV, y_CO_in, steam_to_CO.")
_l("HB-006.psa_default_feed_and_pressure", "psa", "psa_recovery", [0.35, 0.03, 0.042, 0.028, 8.0], "mol fraction x4, bar(a)", None, None, "Function defaults y_CO2, y_CH4, y_CO, y_N2, P_high_bar_a (the engine passes its own).")
# audit and economics
_c("GA-004.air_preheat_C", "balance_audit", "GA004_AIR_PREHEAT_C", "degC", ("GA-004", "Air preheat temperature"), None, "balance_audit.py described this as a 'Confirmed static design value'; the worksheet marks the GA-004 preheat as not DOK-ING-sourced (task A3 item D).")
_c("GA-004.steam_T_C", "balance_audit", "GA004_STEAM_C", "degC", ("GA-004", "Steam temperature (design)"))
_c("FE-005.dryer_operating_C", "balance_audit", "FE005_DRYER_OPERATING_C", "degC", ("FE-005", "Operating temperature"))
_c("GC-004.quench_out_C", "balance_audit", "GC004_QUENCH_OUT_C", "degC", ("GC-004", "Outlet gas temperature (design)"))
_c("GA-008.operating_C", "balance_audit", "GA008_OPERATING_C", "degC", ("GA-008", "Operating temperature"))
_c("PLANT.solids_cp_kj_kgk", "balance_audit", "SOLIDS_CP_KJ_KGK", "kJ/(kg.K)", None, None, "Tuple (point, low, high), Assumed: no solids heat capacity exists anywhere in the repo.")
# The HHV correlation coefficients (balance_audit.feedstock_lhv_estimates) are NOT a row: they are PUBLISHED CORRELATION COEFFICIENTs in data/ledger_exceptions.json (task A3b 2.3).
_l("HB-016.consistency_verdict_ratio_lower_bound", "hb_remaining_chain", "hb016_kinetics_baseline", [0.2], "-", None, None,
   "Lower bound of `verdict = PASS if 0.2 <= ratio_to_reference <= 2.0 else PARTIAL`; the verdict is PERSISTED (HB-016|KineticsBaselineEstimate value.consistency_check.verdict and the confidence_note), so this is a parameter, not a display setting (A3b 2.4). Today ratio_to_reference = 0.43, so the verdict is PASS and the bound is not decisive. The upper bound 2.0 sits in the same expression but is not scanned (the coverage scan skips the literals 0, 1 and 2).")
_l("GC-014.consistency_tolerance_fraction", "gc_gas_cleaning_chain", "gc014_blower_pressure", [0.5], "-", None, None,
   "Fraction of the smaller pressure magnitude within which the GA-002 / GC-013 / GC-014 suction cross-check reads PASS (`tolerance = 0.5 * min(|implied suction|, |design suction|)`); the verdict is PERSISTED (GC-014|Pressure value.consistency_check.verdict and the confidence_note), so this is a parameter, not a display setting (A3b 2.4). Today gap 20 mbar > tolerance 10 mbar, so the verdict is PARTIAL and the fraction IS decisive: 1.0 would read PASS.")
_l("PLANT.audit_vent_and_knockout_temperature_C", "balance_audit", "plant_energy", [40.0], "degC", None, None, "Default vent and knock-out temperatures of the plant energy audit (parameters vent_temp_c, knockout_temp_c).")
_l("PLANT.audit_quench_inlet_temperature_C", "balance_audit", "plant_energy", [860.0], "degC", ("GC-004", "Inlet gas temperature"), None, "A second hard-coded copy of the GC-004 inlet temperature (gc_gas_cleaning_chain gc004_cooling_duty holds the first).")
_l("PLANT.audit_lts_steam_temperature_C", "balance_audit", "plant_energy", [220.0], "degC", ("HB-004", "Inlet temperature (design)"), None, "Unreacted steam leaves the LTS at >= its 220 degC inlet (code comment).")
_c("CIRC.ash_price_eur_per_kg", "circularity", "ASH_PRICE_EUR_PER_KG", "EUR/kg", None, None, "An economic assumption of the circularity estimate; no source in the repo.")
_c("CIRC.carbon_black_price_eur_per_kg", "circularity", "CARBON_BLACK_PRICE_EUR_PER_KG", "EUR/kg", None, None, "An economic assumption of the circularity estimate; no source in the repo.")
_c("CIRC.carbon_black_fraction_engine_derived", "circularity", "ENGINE_CARBON_BLACK_FRACTION_OF_DRY_FEED", "mass fraction of dry feed", None, None, "P1-05(d): the engine's DERIVED carbon black (GA-001 CarbonAccounting: unconverted carbon x split, converged, default feed and tail-gas mode) pinned as a fraction for the static modules; replaces the legacy 5 % rule there; tests/test_p1_05d_carbon_black.py fails on drift.")
# uncertainty
_c("UNC.uncertainty_fraction", "uncertainty", "UNCERTAINTY_FRACTION", "-", None, None, "The +/-15 % band width the code calls 'our own assumed default'.")
_p("UNC.feed_sulfur_ppm", "uncertainty", ("ASSUMPTIONS", "feed_sulfur_ppm", "point"), "ppm", None, None, "wired_in=False: used by the Monte Carlo bookkeeping only.")
_p("UNC.feed_chlorine_ppm", "uncertainty", ("ASSUMPTIONS", "feed_chlorine_ppm", "point"), "ppm", None, None, "wired_in=False: used by the Monte Carlo bookkeeping only.")
_l("UNC.monte_carlo_hts_lts_defaults", "uncertainty", "run_monte_carlo", [350, 2000, 220, 8.0, 0.35], "degC, 1/h, degC, bar(a), mol fraction", None, None, "Defaults hts_T_C, hts_GHSV, lts_T_C, psa_p_high, psa_y_co2 (plus the second 2000 = lts_GHSV).")
_l("UNC.monte_carlo_base_points", "uncertainty", "run_monte_carlo", [4.0, 0.28], "mol/mol, mol fraction", None, None, "Base steam-to-CO (4.0) and CO fraction (0.28) that the sampled steam ratio and ER scale.")
# plant heat integration (its Assumed inputs: every entry already carries value / low / high / status)
for _n, _u in (("recovery_gas_cooler", "-"), ("recovery_wgs", "-"), ("recovery_ash", "-"), ("recovery_flue", "-"), ("delta_t_min_k", "K"), ("excess_air_ratio", "-"),
               ("stack_temperature_c", "degC"), ("ash_discharge_temperature_c", "degC"), ("carbon_black_final_c", "degC"), ("gas_cooler_outlet_c", "degC")):
    _p("PLANT.heat_%s" % _n, "plant_heat_integration", ("ASSUMED", _n, "value"), _u, None, None, "Read-only heat-integration inventory input (docs/plant_heat_integration.md); the basis is in the module.")
# ga001_energy_balance: the report's Assumed inputs
for _i, _n, _u in ((0, "feed_temperature_C", "degC"), (1, "tail_gas_recycle_temperature_C", "degC"), (2, "air_preheat_temperature_C", "degC"), (3, "steam_temperature_C", "degC"), (4, "solids_cp_kj_kgk", "kJ/(kg.K)")):
    _p("PLANT.energy_balance_%s" % _n, "ga001_energy_balance", ("ASSUMED_INPUTS", _i, "value"), _u, None, None, "An Assumed input of the read-only (GA-001, EnergyBalance) report; the module says none of them feeds any model.")
# reference feeds
_c("REFERENCE.dokink_bands", "reference_feeds", "BANDS", "mass-% / MJ/kg", None, Q_COMP,
   "The DOK-ING-stated bands (data/dokink_rfi_answers.md:15-17) a reference feed is compared with; the module keeps them as a band (Assumed (DOK-ING-stated band, kept as a band)).")
_c("REFERENCE.blend_m1_mass_fractions", "reference_feeds", "BLEND_M1", "mass fraction", None, None, "The literature-informed plastic blend M1 of docs/reference_feeds.md; not used by the engine.")
_l("REFERENCE.model_composition_ash_default", "reference_feeds", "model_composition", [0.1], "mass fraction", None, Q_COMP, "Default ash content of the model composition derived from a reference feed (the same 10 % as gasifier_mass_balance.ASH_FRACTION).")


# --- reading the value ------------------------------------------------------------------------------------------------------------------------

def _module(name):
    return importlib.import_module(f"{_PKG}.{name}")


def _walk(obj, path):
    for k in path:
        obj = obj[k]
    return obj


def _scan_index(file, cache, sources=None):
    if file not in cache:
        cache[file] = {i["key"]: i for i in lc.scan_source(file, lc._read(file, sources))}
    return cache[file]


def _registry_status(reg):
    item_id, parameter = reg
    for item in equipment_registry.load_registry():
        if item["id"] == item_id:
            for p in item["parameters"]:
                if p["parameter"] == parameter:
                    return registry_status.resolve_row(registry_status.SOURCE_REGISTRY, item_id, p), p
    raise LookupError(f"registry {item_id} has no parameter {parameter!r}")


# --- status borrowing (task A3b 2.8) ---------------------------------------------------------------------------------------------------------------
# A row with a registry counterpart `reg` may BORROW that registry row's resolved status (and its origin / source_line) only when the engine constant and the registry row are the SAME
# quantity in the SAME basis. BORROW says so per row: tag -> (factor, offset, rel_tol, statement); the code value must equal factor * registry value + offset within rel_tol
# (tests/test_design_basis_ledger.py checks this numerically wherever the registry text is a number; a leading '<' or '~' is read as the number). NOT_BORROWED lists the rows that have a
# registry row nearby but are not the same quantity / basis: they are Assumed (status_via = own) and the reason is in the row's note. Every row with a `reg` is in exactly one of the two.
_S = (1.0, 0.0, 1e-9, "same quantity, same unit, same basis")
_PCT = (0.01, 0.0, 1e-9, "registry states a percentage, the code a fraction: code = registry / 100")
_BARG = (1.0, 1.0, 1e-9, "code is absolute, registry is gauge: bar(a) = bar(g) + 1 bar (atmospheric pressure taken as 1 bar, not 1.01325)")
_LIM = (1.0, 0.0, 1e-9, "registry states the TARGET as an upper limit ('<x'); the code uses the limit value x as the target")
BORROW = {tag: _S for tag in (
    "GA-008.capacity_kg_h", "GC-014.design_discharge_mbar_g", "GC-014.design_suction_mbar_g", "GA-002.typical_pressure_mbar_g", "GC-001.outlet_temperature_C", "GC-004.inlet_temperature_C",
    "GC-004.outlet_temperature_C", "GC-005.blowdown_m3_h", "GC-008.h2s_inlet_ppm", "GC-008.liquid_to_gas_l_nm3", "GC-009.hcl_inlet_ppm", "GC-009.liquid_to_gas_l_nm3", "GC-010.inlet_dust_mg_nm3",
    "HB-001.inlet_temperature_C", "HB-003.hot_inlet_C", "HB-003.hot_outlet_C", "HB-003.cold_inlet_C", "HB-003.cold_outlet_C", "HB-013.storage_capacity_kg", "HB-005.steam_temperature_C",
    "HB-005.steam_pressure_bar_g", "HB-011.rated_power_kw", "HB-011.rated_h2_nm3_h", "HB-011.sec_rated_kwh_per_nm3", "HB-010.feed_flow_nm3_h", "HB-014.loading_efficiency_wt_pct",
    "HB-016.release_efficiency_wt_pct", "EU-004.jacket_kwth_rated", "EU-004.exhaust_kwth_rated", "EU-005.exhaust_flow_nm3_h_rated", "EU-008.rated_capacity_kw", "EU-008.nominal_supply_temp_C",
    "EU-008.fan_motor_power_kw", "EU-010.rated_kva", "EU-011.exhaust_inlet_C", "EU-011.exhaust_outlet_C", "FE-001.total_capacity_t", "FE-001.live_capacity_t", "FE-004.motor_kw",
    "FE-004.throughput_t_h", "GA-004.air_preheat_C", "GA-004.steam_T_C", "FE-005.dryer_operating_C", "GC-004.quench_out_C", "GA-008.operating_C", "PLANT.audit_quench_inlet_temperature_C")}
BORROW.update({
    "GC-007.tar_outlet_target_mg_nm3": _LIM, "GC-009.hcl_outlet_target_ppm": _LIM, "GC-010.outlet_target_mg_nm3": _LIM, "GC-012.h2s_cos_outlet_target_ppm": _LIM,
    "HB-008.psa_adsorption_pressure_bar_a": _BARG, "HB-008.psa_regen_pressure_bar_a": _BARG, "HB-012.suction_bar_a": _BARG, "HB-012.discharge_bar_a": _BARG,
    "HB-010.h2_recovery": _PCT, "HB-010.permeate_purity_range": (0.01, 0.0, 1e-9, "registry states vol%, the code a mole fraction (ideal gas: vol% = mol%): code = registry / 100, both ends of the range"),
    "FE-005.inlet_moisture_fraction": _PCT,
    "HB-011.water_l_per_nm3": (1.0, 0.0, 1e-9, "registry states '~1' (approximate); the code uses 1.0"),
    "HB-018.max_dispense_rate_kg_h": (60.0, 0.0, 1e-9, "kg/min x 60 = kg/h"),
    "EU-010.backup_hours": (1.0 / 60.0, 0.0, 1e-9, "min / 60 = h"),
    "FE-003.min_kg_h": (1000.0, 0.0, 1e-9, "t/h x 1000 = kg/h"), "FE-003.max_kg_h": (1000.0, 0.0, 1e-9, "t/h x 1000 = kg/h"),
    "FE-003.nominal_kg_h": (1000.0, 0.0, 0.01, "t/h x 1000 = kg/h; the registry's 0.042 t/h is the code's 41.67 kg/h (= 1,000 kg/day / 24 h, DOK-ING RFI answer 1) rounded to two significant digits (0.8 %)"),
})
NOT_BORROWED = {
    "GA-001.ash_fraction": "ASH_FRACTION is a mass fraction of dry feed; the nearest registry row, GA-005 'Ash discharge rate (design)' = '10 % of feed', is the bed-drain discharge rate, its basis is not in the value, and its remark says it was set to match this model value: not the same quantity in the same basis (the table row itself is Assumed)",
    "GC-005.blowdown_to_circulation_ratio": "a ratio (0.05 m3/h / 0.5 m3/h, code comment) derived from two registry rows; the row GC-005 'Blowdown rate' is only its numerator",
    "GC-015.ambient_temp_C": "the lower bound of GC-015's operating range; GC-005 'Water supply temperature' (20 degC) is a different quantity that happens to have the same number",
    "GC-003.inlet_dust_mg_nm3": "registry GC-003 'Dust loading inlet (max)' (2 g/Nm3) is a MAXIMUM; the code uses it as the inlet loading: not the same basis",
    "GC-003.efficiency": "registry GC-003 states '>95 %' (a lower bound); the code uses 0.95 as the efficiency itself: a bound used as a point value",
    "GC-003.outlet_temperature_C": "the code publishes the cyclone INLET temperature (870 degC) as its outlet; registry GC-003 'Inlet gas temperature' is not the outlet temperature",
    "FE-002.removal_efficiency": "registry FE-002 states '>98' (a lower bound); the code uses 0.98 as the efficiency itself: a bound used as a point value",
    "HB-017.recovery_efficiency": "registry HB-017 states '>99 %' (a lower bound); the code uses 0.99 as the efficiency itself: a bound used as a point value",
    "HB-005.steam_to_co_molar_ratio": "the registry text of HB-005 'Steam-to-CO ratio' is '04:01:00' (it reads as a time, not a ratio), so equality with 4.0 mol/mol cannot be shown",
    "HB-010.design_feed_h2_fraction": "a mole fraction; the registry row states the H2 PARTIAL PRESSURE (4.4 bar = '55% H2 content (HB-006) x ~8 bar(a)', its remark), so the 55 % is an input of that row's value, not its value",
    "EU-003.syngas_lhv_mj_per_nm3": "registry EU-003 'Fuel gas LHV required' is a requirement of the engine; the code uses 9.8 as a static syngas LHV: not the same quantity",
    "FE-001.default_delivery_rate_kg_h": "the delivery rate INTO the hopper (a model choice, set equal to the feeder's nominal rate); registry FE-003 'Nominal feed rate' is the rate OUT of it",
    "FE-005.outlet_moisture_fraction": "the registry text of FE-005 'Outlet moisture (target)' is '-1 % moisture' (a negative number); equality with 1 % cannot be shown",
    "GA-001.agent_check_expected_n2_vol_pct": "the registry row SA-005 'Expected N2 concentration' says '10 vol%' without a wet or dry basis, and the model's N2 is the dry mole fraction: the same number, but the basis is not shown to be the same",
    "PLANT.audit_lts_steam_temperature_C": "the code takes the LTS INLET temperature as a lower bound of the (not stated) LTS outlet steam temperature: not the same quantity",
}
# why each refused row was refused, in a few words (shown in the ledger doc; tests/test_design_basis_ledger.py checks that every refusal has one)
REFUSAL_KIND = {
    "GA-001.ash_fraction": "different quantity and basis", "GC-005.blowdown_to_circulation_ratio": "different quantity (derived ratio)", "GC-015.ambient_temp_C": "different quantity",
    "GC-003.inlet_dust_mg_nm3": "different basis (maximum against design)", "GC-003.efficiency": "bound used as a point value", "GC-003.outlet_temperature_C": "different quantity (inlet against outlet)",
    "FE-002.removal_efficiency": "bound used as a point value", "HB-017.recovery_efficiency": "bound used as a point value", "HB-005.steam_to_co_molar_ratio": "registry text unreadable, no conversion can be shown",
    "HB-010.design_feed_h2_fraction": "different quantity (mole fraction against partial pressure)", "EU-003.syngas_lhv_mj_per_nm3": "different quantity (requirement against value)",
    "FE-001.default_delivery_rate_kg_h": "different quantity (delivery into the hopper against feed out of it) and basis not stated",
    "FE-005.outlet_moisture_fraction": "registry text unreadable, no conversion can be shown", "PLANT.audit_lts_steam_temperature_C": "different quantity (inlet against outlet)",
    "GA-001.agent_check_expected_n2_vol_pct": "basis not stated (wet or dry)",
}


def quantity_class(text):
    """'design' / 'operating' / None from the words in a row's tag, constant name or registry parameter. Design pressure and typical or operating pressure are different quantities (A3c 3): a borrowing
    whose two sides fall in different classes is refused."""
    s = text.lower()
    if "design" in s:
        return "design"
    if "typical" in s or "operating" in s:
        return "operating"
    return None


def crosses_design_and_operating(row_text, registry_parameter):
    """True when one side is a design quantity and the other a typical or operating one (A3c 3): such a pair is never the same quantity."""
    a, b = quantity_class(row_text), quantity_class(registry_parameter)
    return a is not None and b is not None and a != b


VIA_OWN = "own"
VIA_REG = "registry counterpart: %s/%s"


def build_rows(sources=None):
    """`sources` = {relative file: source text} replaces a file for the ast reads (tests change a constant in a copy and expect a loud LookupError). The new rows as dicts with the parameter-table columns (tag .. note) plus `covers` (scan keys), `reg`, `upgrade_question` and `reader` (module, name) for the consumer search."""
    cache, out = {}, []
    for tag, kind, mod, ref, unit, reg, up, note in R:
        file = lc.rel_path(mod)
        idx = _scan_index(file, cache, sources)
        lo = hi = None
        if kind == "c":
            it = idx.get(lc.const_key(file, ref))
            if it is None:
                raise LookupError(f"{tag}: {file} has no scanned constant {ref}")
            value = getattr(_module(mod), ref)
            if isinstance(value, tuple) and len(value) == 2 and ref.endswith("_RANGE") or ref in ("HB010_CONFIRMED_PURITY_RANGE",):
                lo, hi = value
            elif ref == "SOLIDS_CP_KJ_KGK":
                lo, hi = value[1], value[2]
            covers, line, source = [it["key"]], it["line"], f"module constant {mod}.{ref}"
            reader = (mod, ref)
            anchor, aflags = f"{mod}:{ref}", set()
        elif kind == "l":
            fn, vals = ref
            keys, found, line = [], [], None
            for v in vals:
                k = lc.lit_key(file, fn, v)
                it = idx.get(k)
                if it is None:
                    raise LookupError(f"{tag}: {file} {fn}() has no numeric literal {v!r}")
                keys.append(k)
                found.append(eval(it["value"]))                                  # the repr of a number read from the source by ast
                line = it["line"] if line is None else min(line, it["line"])
            value = found[0] if len(found) == 1 else found
            covers, source = keys, f"literal {vals if len(vals) > 1 else vals[0]} inside {mod}.{fn}() (read from its ast)"
            reader = (mod, fn)
            anchor, aflags = ledger_anchors.literal_anchor(file, lc._read(file, sources), fn, vals)
        else:
            name = ref[0]
            it = idx.get(lc.const_key(file, name))
            if it is None:
                raise LookupError(f"{tag}: {file} has no scanned constant {name}")
            obj = getattr(_module(mod), name)
            value = _walk(obj, ref[1:])
            entry = _walk(obj, ref[1:-1])
            if isinstance(entry, dict) and "low" in entry and "high" in entry:
                lo, hi = entry["low"], entry["high"]
            elif isinstance(entry, dict) and isinstance(entry.get("range"), (list, tuple)):
                lo, hi = entry["range"]
            if mod == "uncertainty":
                lo, hi = _module("uncertainty").bounds(ref[1])
            covers, line, source = [it["key"]], it["line"], f"module constant {mod}.{name}" + "".join(f"[{k!r}]" for k in ref[1:])
            reader = (mod, name)
            anchor, aflags = ledger_anchors.path_anchor(mod, name, ref[1:], obj), set()
        if reg and tag in NOT_BORROWED:
            res, p = _registry_status(reg)
            status, res, via = ps.STATUS_ASSUMED, None, VIA_OWN
            tail = _ASSIGNED + f"not borrowed from the nearby registry row {reg[0]} '{reg[1]}' (registry value {p['value']} {p['unit']}): {NOT_BORROWED[tag]}."
        elif reg:
            if tag not in BORROW:
                raise LookupError(f"{tag}: has a registry counterpart {reg} but is neither in BORROW (same quantity, same basis) nor in NOT_BORROWED")
            res, p = _registry_status(reg)
            status, via = res["status"], VIA_REG % reg
            tail = (f"Value read from the code; status, origin and source_line are those of its registry counterpart {reg[0]} '{reg[1]}' (registry value {p['value']} {p['unit']}; "
                    f"{BORROW[tag][3]}): {res['reason']}")
        else:
            status, res, via = ps.STATUS_ASSUMED, None, VIA_OWN
            tail = _ASSIGNED + "no registry row states this quantity, or the code holds it as a model choice."
        out.append({"tag": tag, "value": value, "unit": unit, "status": status, "source": source, "range_low": lo, "range_high": hi, "overridable_via": VIA_CODE,
                    "file_line": f"{file}:{line}", "note": (note + " " if note else "") + tail, "covers": covers, "reg": reg, "reg_res": res, "upgrade_question": [up] if up else [], "reader": reader, "kind": kind, "status_via": via, "anchor": anchor, "anchor_flags": aflags})
    return out


def table_covers_keys():
    return sorted({k for ks in TABLE_COVERS.values() for k in ks})


def covered_keys(rows=None):
    """Every scanned constant some ledger row stands for: the existing table rows (TABLE_COVERS) and the rows built here."""
    rows = rows if rows is not None else build_rows()
    return sorted(set(table_covers_keys()) | {k for r in rows for k in r["covers"]})
