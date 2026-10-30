"""
Stream inventory for the mass and energy closure audit (part A) -- pure data plus one read-only helper.

Every row cites `file:line` AS OF THE COMMIT THE AUDIT WAS RUN AT. tests/test_balance_audit.py checks that each cited line still
contains its quoted snippet, so a later edit that moves the code fails loudly and the inventory has to be refreshed rather than
silently going stale.

`ref` = (file under python/ or data/, 1-based line, snippet that must appear on that line).
Status uses the project's five tags (Measured / Calculated / Estimated / Assumed / Missing).
Conserved: "Y" = by construction, "explicit" = an explicit balance check exists, "partly", "N" = not at all, "n/a".
"""
from . import plant_status as ps

G = "ga001_gasifier_model.py"
FE = "fe_feed_handling.py"
GC = "gc_gas_cleaning_chain.py"
HB = "hb_wgs_psa_storage_chain.py"
HR = "hb_remaining_chain.py"
EU = "eu_utilities_chp.py"
MB = "gasifier_mass_balance.py"
TI = "tab1_integration.py"

# --- A1: GA-001 streams ------------------------------------------------------------------------------------------------
GA001_STREAMS = [
    # (stream, direction, what the model uses, status, ref, closed by construction?)
    ("dry feed rate", "in", "GA-001-INPUT dry_feed_rate_kg_h = FE-005 dry solids (37.503 kg/h at 41.67 wet); on cycle 1 the 41.67 kg/h placeholder (a WET figure used as dry)",
     "Calculated (cycle 1: Assumed)", (G, 393, "def _input_dry_feed_rate"), "input"),
    ("feed C/H/O/N (dry, ash-free: 0.50/0.06/0.43/0.01)", "in", "literature stand-in (Tchobanoglous et al.), cross-checked against DOK-ING floors only",
     "Assumed", (G, 193, "FEEDSTOCK_C_FRACTION = 0.50"), "input"),
    ("feed ash (10 % of dry feed)", "in", "ASH_FRACTION, GA-005 registry 'Ash discharge rate 10 % of feed'", "Confirmed registry value (tag Assumed in the engine)",
     (MB, 61, "ASH_FRACTION = 0.10"), "not used by the gas closure; carried by the byproduct module only"),
    ("feed S, Cl, trace", "in", "no S/Cl in the composition; GC-008/GC-009 inlets are fixed 200 / 150 ppm", "Missing", (GC, 413, "def gc008_h2s"), "no"),
    ("residual moisture in the dry feed", "in", "FE-005 residual_water_kg_h (0.379 kg/h), read one cycle late, added to the steam pool", "Calculated",
     (G, 706, "def _moisture_water_moles"), "Y (H, O)"),
    ("gasifying air", "in", "not a stream: O2 = ER x (1 + x/4 - y/2) per mol C, N2 = O2 x 0.79/0.21 (no argon); ER 0.25", "Assumed (ER)", (G, 301, "n2_from_air = o2_actual"), "Y (O, N)"),
    ("gasifier steam", "in", "steam_to_feed_ratio 0.4 kg/kg dry feed = 15.0 kg/h; GA-003 registry 15 kg/h at 37.5 kg/h", "Assumed", (G, 761, "steam_mol_per_molc = (steam_ratio"), "Y (H, O)"),
    ("oxygen-carrier (Fe2O3/Fe3O4) oxygen", "in", "NOT in the model: the circulation estimate is standalone and 'does NOT feed back into ga001_model()'", "Missing (as a stream)",
     (G, 971, "def oxygen_carrier_circulation_estimate"), "n/a"),
    ("bed material / carrier inventory, make-up, attrition", "in/out", "not modelled", "Missing", (G, 971, "def oxygen_carrier_circulation_estimate"), "n/a"),
    ("tail-gas recycle (HB-009 H2, CO, CH4)", "in", "previous cycle's tail gas atoms added to the fuel atoms; CO2 and N2 deliberately not recycled", "Calculated",
     (G, 669, "def _recycle_atom_moles"), "Y (H, O); C only at the 0.90 conversion"),
    ("product gas, dry flow + composition (H2, CO, CO2, CH4, N2)", "out", "dry_flow_nm3_h and mol % from the WGS-equilibrium closure", "Calculated", (G, 802, "result_value = {"), "Y (H, O, N)"),
    ("product gas, water", "out", "wet_flow_nm3_h and H2O_mol_pct_wet", "Calculated", (G, 804, "\"wet_flow_nm3_h\""), "Y (H, O)"),
    ("unconverted carbon / char", "out", "(1 - 0.90) x total C does not appear in the gas (also applied to the recycled CO and CH4 carbon); since the carbon-bookkeeping task it is "
     "published as (GA-001, CarbonAccounting).unconverted_carbon_kg_h", "Calculated (conversion 0.90 Assumed)", (G, 303, "carbon_gas = carbon_conv_eff"), "Y (published, carbon closes)"),
    ("ash", "out", "10 % of dry feed from the byproduct module, independent of the gas closure", "Assumed", (MB, 65, "def byproduct_mass_flows"), "by an independent constant"),
    ("carbon black", "out", "DERIVED: unconverted carbon x the Assumed split (1.0) in (GA-001, CarbonAccounting); the old 5 % of dry feed (CARBON_BLACK_FRACTION) and GA-008's 1.88 kg/h "
     "are a cross-check only; the static byproduct_mass_flows() used by the app cards and circularity still uses the 5 % rule", "Calculated (split Assumed)", (MB, 62, "CARBON_BLACK_FRACTION = 0.05"),
     "Y (tied to the gas closure)"),
    ("tar", "out", "permanently Missing", "Missing", (G, 851, "def ga001_tar_content"), "N"),
    ("fly ash / dust leaving with the gas", "out", "GC-001 Dust Missing; GC-003 inlet fixed 2 g/Nm3", "Missing", (GC, 132, "def gc001_particulate"), "N"),
]

GA001_CLOSURE_NOTES = [
    "solve_product_gas conserves H, O and N exactly by construction (ga001_gasifier_model.py:299-330). Carbon is conserved only on the gas side: "
    "0.90 of the carbon (including the recycled carbon) goes to CO + CO2 + CH4 and the other 10 % has no stream.",
    "verify_atom_balance (ga001_gasifier_model.py:333) tests H and O only: `ok` uses h_check and o_check; the carbon check is returned in `detail` "
    "but never compared, and nitrogen is not tested at all.",
]

# --- A2: every other unit ----------------------------------------------------------------------------------------------
UNIT_TABLE = [
    # (unit, streams in, streams out, conserved, ref, note)
    ("FE-001 receiving hopper", "MSW delivery 41.67 kg/h (Assumed)", "same rate; hopper level", "Y (pass-through)", (FE, 135, "def fe001_inventory"), ""),
    ("FE-002 magnet / eddy current", "FE-001 flow", "same flow; tramp-metal reject Missing", "partly", (FE, 194, "def fe002_tramp_metal_reject"), "reject taken as negligible, not subtracted"),
    ("FE-003 weighing conveyor", "FE-002 flow", "flow clipped to 29-50 kg/h", "partly (N when clipped)", (FE, 215, "def fe003_weighing"), "surplus mass above 50 kg/h goes nowhere"),
    ("FE-004 shredder", "FE-003 flow", "same flow; 150 kWh/t electricity", "Y (mass); electricity computed", (FE, 243, "def fe004_shredder_power"), "power not summed in EU-009"),
    ("FE-005 dryer", "wet feed (10 % water)", "dry solids + 1 % residual water to GA-001; evaporated water 3.79 kg/h", "Y (mass, explicit)", (FE, 275, "def fe005_moisture_balance"),
     "no dryer heat duty; evaporated water has no destination"),
    ("FE-006 / FE-007 / FE-008", "FE-005 outlet", "pass-through 37.88 kg/h", "Y (pass-through)", (FE, 331, "def fe007_ram_feeder"), "GA-001 takes the dry mass and the water separately"),
    ("GA-001 gasifier", "see A1", "see A1", "H, O, N Y; C partly; ash by constant; energy N", (G, 727, "def ga001_model"), "no heat duty computed"),
    ("GC-001 / GC-003 cyclones", "GA-001 gas", "same gas (copied)", "Y (copy)", (GC, 152, "def gc001_gas_passthrough"), "dust: GC-001 Missing, GC-003 fixed 2 g/Nm3 and 95 %"),
    ("GC-004 quench", "GA-001 wet gas", "dry gas + condensate (wet - dry)", "Y (water, by construction)", (GC, 256, "def gc004_condensed_water"), "duty = sensible heat of the dry gas only"),
    ("GC-005 quench water", "-", "blowdown 0.05 m3/h (fixed)", "N", (GC, 312, "def gc005_blowdown"), "no make-up stream, no circulation balance"),
    ("GC-006 / GC-007 tar removal", "tar 500 mg/Nm3 (fixed)", "tar 50 mg/Nm3; blowdown", "N", (GC, 364, "def gc007_tar"), "not tied to GA-001 tar (Missing); removed tar goes nowhere"),
    ("GC-008 H2S / GC-009 HCl scrubbers", "200 ppm / 150 ppm (fixed)", "1 ppm / 5 ppm; blowdowns", "N", (GC, 413, "def gc008_h2s"), "S and Cl appear from nowhere"),
    ("GC-010 bag filter / GC-012 carbon filter", "fixed dust, H2S", "fixed efficiencies", "N", (GC, 508, "def gc010_dust"), ""),
    ("GC-013 fan / GC-014 blower", "gas", "same gas; hydraulic power", "Y (copy); power from dP", (GC, 574, "def gc013_gas_final"), "dP and power are design values"),
    ("GC-015 condensate tank", "GC-004 condensate + blowdowns", "total m3/h", "N (a sum)", (GC, 713, "def gc015_condensate"), "adds process condensate to utility blowdowns"),
    ("HB-001 / HB-004 WGS (HTS, LTS)", "GC-013 gas + steam 4 x CO", "CO -> CO2 + H2; unreacted steam", "explicit (C and O, 1e-9)", (HB, 275, "def verify_wgs_atom_balance"), "unreacted steam has no destination"),
    ("HB-005 steam generator", "CO mol/h x 4", "steam 70.9 kg/h", "Y", (HB, 177, "def hb005_steam_generation"), "no fuel / heat input to raise it"),
    ("HB-003 heat exchanger", "gas 400 -> 220 degC; water 20 -> 150 degC", "duties 7.4 / 10.7 kW", "N (two-sided duties differ)", (HB, 208, "def hb003_heat_exchanger"), "reported, not forced equal"),
    ("HB-006 / HB-009 PSA + tail gas", "WGS gas", "H2 product (taken as 100 % H2) + tail gas", "Y (species split)", (HB, 380, "def hb009_tail_gas"), "purity 99.97 % not modelled"),
    ("HB-010 membrane", "constant 50 Nm3/h", "separation Missing", "N", (HR, 339, "def hb010_feed"), "flow is a design constant, not taken from the PSA/WGS flow"),
    ("HB-011 electrolyser", "10 kW x 0.6 availability; water 1 L/Nm3", "H2 0.068 Nm3/h", "partly", (HR, 279, "def hb011_electrolyser"), "O2 not published; excess water; SEC 88.7 kWh/Nm3"),
    ("HB-012 compressor", "PSA H2", "same H2; polytropic power", "Y (pass-through)", (HB, 452, "def hb012_compressor"), "n = 1.3 Assumed"),
    ("HB-013 H2 storage", "PSA + electrolyser H2", "lagged dispensing + fuel cell; level", "N when clamped", (HB, 487, "def hb013_storage_level"), "clamp to [0, 50] kg creates / destroys H2"),
    ("HB-014..017 LOHC", "-", "-", "Missing", (HR, 605, "def hb014_mass_balance"), "mass balances Missing"),
    ("HB-018 dispensing", "HB-013 level (lagged)", "min(72 kg/h, level)", "partly", (HR, 981, "def hb018_dispensing"), "lagged, so it oscillates against HB-013"),
    ("EU-CHP dispatch / EU-002..006", "syngas budget (0 after WGS/PSA claim), H2 budget", "electrical, thermal kW", "partly (energy split explicit)", (EU, 299, "def eu_chp_dispatch"), "CHP receives no syngas by design"),
    ("EU-007 flare", "tail gas CO2 + N2", "vented", "Y", (EU, 464, "def eu007_flare"), "98 % destruction applies to 0 combustible"),
    ("EU-008 cooling tower", "GC-004 + HB-003 cold side + HB-012", "demand 52 kW", "N (a sum, not a balance)", (EU, 510, "def eu008_cooling_supply"), "HB-003 cold side is recovered, not rejected"),
    ("EU-009 electrical metering", "HB-012 + HB-011 + GC-013 fan + EU-008 fan", "consumption kW", "N (a sum)", (EU, 733, "def eu009_grid_balance"), "omits FE-004 and all other nameplate loads"),
    ("EU-010 UPS", "EU-009 net", "state of charge", "explicit (Coulomb counting)", (EU, 775, "def eu010_ups_battery"), ""),
    ("EU-011..013 heat recovery", "EU-005 exhaust, EU-004", "kWth", "Y (sums)", (EU, 813, "def eu011_heat_recovery"), "zero while the CHP units idle"),
    ("oxygen carrier (chemical looping)", "-", "-", "n/a (standalone estimate)", (G, 971, "def oxygen_carrier_circulation_estimate"), "no stream enters or leaves the balance"),
]

REGISTRY_HARD_CODES = [
    # (what, value, file:line ref, effect)
    ("carbon conversion efficiency", "0.90 (range 0.85-0.98), Assumed", (G, 217, "CARBON_CONVERSION_EFFICIENCY = 0.90"), "sets the unconverted carbon; independent of temperature"),
    ("CH4 carbon fraction", "0.05, Assumed", (G, 224, "CH4_CARBON_FRACTION = 0.05"), "CH4 is not an equilibrium result"),
    ("ash fraction", "0.10 of dry feed, Confirmed registry value", (MB, 61, "ASH_FRACTION = 0.10"), "a constant, not tied to the composition"),
    ("carbon-black fraction", "0.05 of dry feed", (MB, 62, "CARBON_BLACK_FRACTION = 0.05"), "cross-check only since the carbon-bookkeeping task; still drives the static byproduct_mass_flows()"),
    ("gasifier operating temperature", "950 degC, registry value", (G, 230, "GA001_OPERATING_TEMPERATURE_C = 950.0"), "enters only the WGS Keq"),
    ("steam-to-CO ratio in the WGS", "4.0 mol/mol", (HB, 98, "STEAM_TO_CO_MOLAR_RATIO = 4.0"), "sets the steam raised and the water knocked out"),
    ("quench inlet / outlet temperature", "860 / 65 degC", (GC, 295, "T_in, T_out = 860.0, 65.0"), "duty excludes latent heat"),
    ("mean heat capacities", "H2 29.3, CO 30.5, CO2 46.5, CH4 55.0, N2 30.6, H2O 37.5 J/mol.K", (GC, 106, "CP_MEAN_J_MOLK"), "one mean over 300-1200 K for every temperature"),
    ("compressor polytropic exponent", "1.3, Assumed", (HB, 122, "COMPRESSOR_POLYTROPIC_N = 1.3"), "sets 8.7 kW"),
    ("PSA product purity", "100 % H2 (design target 99.97 %)", (HB, 384, "PSA product modeled as ~pure H2"), "impurities ignored"),
    ("electrolyser SEC and balance of plant", "55 kWh/Nm3 H2 rated, BoP 8 %", (HR, 169, "HB011_SEC_RATED_KWH_PER_NM3 = 55.0"), "LHV of H2 is 3.0 kWh/Nm3: this is 5.5 % efficient (unit suspect)"),
    ("flare destruction efficiency", "0.98", (EU, 177, "EU007_DESTRUCTION_EFFICIENCY = 0.98"), "applied to zero combustible"),
    ("UPS round-trip efficiency", "0.94", (EU, 207, "EU010_ROUNDTRIP_EFFICIENCY = 0.94"), "charge side only"),
    ("WGS/PSA claim on syngas", "1.0", (EU, 231, "WGS_PSA_SYNGAS_CLAIM_FRACTION = 1.0"), "CHP fuel budget is 0"),
    ("gas-train fan power", "hydraulic power only (efficiency not applied)", (GC, 594, "def gc013_fan_power"), "lower bound of electrical load"),
    ("heat loss from any vessel or pipe", "none anywhere", (G, 727, "def ga001_model"), "no heat-loss term exists in the repo"),
]


def check_refs():
    """Every (file, line, snippet) above must still hold. Returns the list of broken references (empty = all good)."""
    import os
    root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
    refs = [r[4] for r in GA001_STREAMS] + [r[4] for r in UNIT_TABLE] + [r[2] for r in REGISTRY_HARD_CODES]
    broken = []
    cache = {}
    for fname, line, snippet in refs:
        if fname not in cache:
            with open(os.path.join(root, fname), encoding="utf-8") as fh:
                cache[fname] = fh.read().splitlines()
        lines = cache[fname]
        if not (1 <= line <= len(lines)) or snippet not in lines[line - 1]:
            broken.append((fname, line, snippet))
    return broken


# --- A3: mass or energy that appears or disappears without a stream ------------------------------------------------------
def unaccounted_items(snapshot):
    """Live values (from the snapshot) of every place where mass or energy enters or leaves without a matching stream.
    Rows: (item, value, unit, status, ref, effect)."""
    def v(key, field=None):
        e = snapshot.get(key)
        if e is None or e["status"] == ps.STATUS_MISSING:
            return None
        return e["value"] if field is None else e["value"][field]

    dry_nm3 = v(("GC-013", "Gas"), "dry_flow_nm3_h")
    fe5 = v(("FE-005", "MoistureBalance"))
    hb009 = v(("HB-009", "TailGas"))
    wgs = v(("WGS", "Composition"))
    rows = []
    rows.append(("ash leaving as bottom ash (10 % of dry feed)", 0.10 * fe5["dry_solids_kg_h"], "kg/h", "Assumed", (MB, 61, "ASH_FRACTION = 0.10"), "carries no C/H/O/N; closed by an independent constant"))
    rows.append(("fly ash implied by GC-003's fixed 2 g/Nm3 inlet", 2.0 * dry_nm3 / 1000.0, "kg/h", "Assumed", (GC, 206, "inlet_mg_nm3 = 2000.0"), "not subtracted from the 10 % bottom ash"))
    cb_entry = snapshot.get(("GA-001", "CarbonAccounting"))
    if cb_entry is not None and cb_entry["status"] != ps.STATUS_MISSING:
        rows.append(("carbon black, derived from the unconverted carbon", cb_entry["value"]["carbon_black_kg_h"], "kg/h", "Calculated", (MB, 62, "CARBON_BLACK_FRACTION = 0.05"),
                     "the 5 % datasheet rule is now a cross-check; the app cards and circularity still show the 5 % rule"))
    rows.append(("carbon black by the 5 % datasheet rule (cross-check)", 0.05 * fe5["dry_solids_kg_h"], "kg/h", "Assumed", (MB, 62, "CARBON_BLACK_FRACTION = 0.05"), "not used by the gas closure"))
    rows.append(("tar mass removed by GC-006/GC-007 (500 -> 50 mg/Nm3)", (500.0 - 50.0) * dry_nm3 / 1.0e6, "kg/h", "Assumed", (GC, 364, "def gc007_tar"), "tar that GA-001 does not produce (Missing) is removed here"))
    rows.append(("H2S entering GC-008 (200 ppm of the dry gas), as sulfur", 200e-6 * dry_nm3 / 0.022414 * 32.06 / 1000.0, "kg S/h", "Assumed", (GC, 413, "def gc008_h2s"), "no sulfur in the feed composition: S appears from nowhere"))
    rows.append(("HCl entering GC-009 (150 ppm of the dry gas), as chlorine", 150e-6 * dry_nm3 / 0.022414 * 35.45 / 1000.0, "kg Cl/h", "Assumed", (GC, 463, "def gc009_hcl"), "no chlorine in the feed composition"))
    rows.append(("quench-loop blowdown GC-005 (fixed 0.05 m3/h)", 50.0, "kg/h", "Assumed", (GC, 312, "def gc005_blowdown"), "leaves with no make-up stream"))
    rows.append(("GC-007/008/009 blowdowns (scaled to gas flow)", 1000.0 * (v(("GC-007", "Blowdown")) + v(("GC-008", "Blowdown")) + v(("GC-009", "Blowdown"))), "kg/h", "Assumed", (GC, 389, "def gc007_blowdown"), "no make-up stream"))
    rows.append(("WGS unreacted steam knocked out", wgs["H2O"] * dry_nm3 / 0.022414 * 18.015 / 1000.0, "kg/h", "Calculated", (HB, 270, "\"H2O\": max(y_H2O_in"), "no condensate stream, no unit, no heat rejection"))
    rows.append(("WGS steam raised (HB-005)", v(("HB-005", "Steam"), "steam_kg_h"), "kg/h", "Calculated", (HB, 189, "steam_kg_h = steam_mol_h"), "feedwater source and boiler energy not modelled"))
    rows.append(("gasifier steam (GA-003 / GA-004)", 0.4 * fe5["dry_solids_kg_h"], "kg/h", "Assumed", (G, 761, "steam_mol_per_molc = (steam_ratio"), "source and energy of this steam not modelled"))
    rows.append(("dryer vapour (FE-005)", fe5["water_evaporated_kg_h"], "kg/h", "Calculated", (FE, 291, "water_evaporated_kg_h = wet_inlet"), "no destination, no heat duty"))
    rows.append(("tail-gas CO2 + N2 vented", (hb009["species_nm3_h"]["CO2"] * 44.0095 + hb009["species_nm3_h"]["N2"] * 28.0134) / 22.414, "kg/h", "Calculated", (EU, 485, "inert_nm3_h = species.get"), "a real exit stream (EU-007)"))
    rows.append(("HB-013 clamp at 0 kg (storage would go negative)", None, "kg per cycle", "Calculated", (HB, 537, "new_level = min(max(prev_level"), "creates H2; see storage_inventory_check"))
    rows.append(("HB-010 membrane feed (constant, not taken from the plant flow)", 50.0, "Nm3/h", "Assumed", (HR, 182, "HB010_FEED_FLOW_NM3_H = 50.0"), "not deducted from the PSA/WGS gas"))
    rows.append(("FE-004 shredder electricity not in EU-009", v(("FE-004", "ShredderPower"), "power_kw"), "kW", "Calculated", (FE, 243, "def fe004_shredder_power"), "electrical load missing from the plant sum"))
    rows.append(("registry nameplate loads in no sum (FE-003 .37, FE-005 5, FE-007 5.5, FE-008 .75, GA-005 1.1, GA-006 .55, HB-009 .5)", 13.77, "kW rated", "Confirmed nameplate", ("equipment_registry.json", 0, ""), "utilisation not stated"))
    rows.append(("EU-008 'cooling demand' counts HB-003 cold side as a cooling load", v(("HB-003", "HeatExchanger"), "Q_cold_side_kW"), "kW", "Calculated", (EU, 520, "demand_kw = gc004_duty_kw"), "heat that is recovered to the feedwater, not rejected"))
    rows.append(("GC-004 duty omits condensation latent heat", None, "kW", "Calculated", (GC, 282, "def gc004_cooling_duty"), "see plant_energy candidates"))
    return rows
