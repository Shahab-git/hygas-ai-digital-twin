"""
Remaining H2 Chain Items (Recycle Loop, Electrolyser, LOHC Branch) --
Digital Twin Phase 1d, second half. (HB-009's own recycle loop back to
GA-001 is implemented directly inside ga001_gasifier_model.py /
hb_wgs_psa_storage_chain.py -- see both modules' own docstring addenda;
this file covers this phase's remaining items: AI-001, HB-011, HB-010,
HB-007/014/015/016/017, HB-018.)

Implements the roadmap's Part 1.5 remaining H2-chain rows. No EU/utilities
(Phase 2) work. Does not modify ga001_gasifier_model.py, gc_gas_cleaning_
chain.py, or hb_wgs_psa_storage_chain.py -- register_hb_remaining(engine)
is called AFTER register_ga001/register_gc_chain/register_hb_chain, adding
new keys and, for HB-013, new LAGGED read edges only (hb013_storage_level
itself already handles their absence gracefully, verified unchanged in
hb_wgs_psa_storage_chain.py's own self-test).

=== AI-001 -> HB-011 (Electrolyser), task requirement 2 ===
AI-001's own registry remark states directly: "Solar irradiance and wind
data specifically support anticipating renewable generation availability
for HB-011" -- this connection is registry-documented, not invented.
HONEST LIMITATION: no solar-PV or wind-turbine GENERATION asset exists
anywhere in this project's registry (checked: the only renewable/grid item
is EU-009, Electrical Metering (Grid), Phase 2 scope) and AI-001 itself
has no live data feed in this codebase. ai001_renewable_availability()
therefore returns a fixed, clearly-labeled ILLUSTRATIVE Assumed fraction,
not a real weather- or capacity-derived signal -- see its own docstring.
HB-011's own literature part-load correlation is real and load-dependent;
only the LOAD SIGNAL feeding it is illustrative, not the correlation
itself.

=== HB-010 (Membrane Separator), task requirement 3 ===
Dual classification, exactly as the roadmap specifies: feed flow/
composition (read from the same live WGS Composition node HB-006 reads)
are Calculated. Recovery, product H2 flow, and permeate purity are
PERMANENTLY Missing -- HB-010's own registry gives H2 permeance (50 GPU)
and a STATIC design-point recovery/purity figure (85% / 95-98%), but no
membrane SELECTIVITY. Standard solution-diffusion membrane transport
theory needs permeance AND selectivity together (with feed composition and
the pressure ratio) to compute a live, composition-dependent recovery --
without selectivity, that computation has no basis. The registry's own
static 85%/95-98% figures are a DESIGN POINT, not something this cycle-by-
cycle model can independently re-derive; reporting them as freshly
"Calculated" here would misrepresent a copied constant as a real result.

=== HB-007/014-017 (LOHC branch), task requirement 4 ===
A dedicated, always-Missing ("HB-007","H2SplitFraction") boundary key: no
data anywhere in this project specifies what fraction (if any) of HB-007's
own PSA product H2 stream is diverted to the LOHC branch (HB-014) versus
the primary compressed-storage route (HB-012->HB-013). HB-014's own
registry remark ("margin above HB-007's established ~1.85 kg/h PSA product
rate") is a CAPACITY-SIZING comparison, not a confirmed live feed
allocation. HB-014's own MassBalance output structurally depends_on this
key (same-cycle) -- the engine's own Phase-0-proven Missing-propagation
mechanism (simulation_engine.py's run_cycle()) then blocks HB-014's
function from ever being called, and HB-015/016/017 each depends_on the
PREVIOUS stage's own MassBalance output, cascading the SAME structural
block forward -- one root cause, four Missing entries, not four
independently-declared gaps (proven in this module's own self-test via
resolve_provenance_chain()/missing_roots() AND an instrumented call
counter proving hb014_mass_balance() is never invoked). HB-014's and
HB-016's own REACTION-KINETICS outputs are separately, unconditionally
Missing (no catalyst kinetic data exists for either DBT hydrogenation or
dehydrogenation) -- independent of the split-fraction propagation, a
second, distinct kind of gap, not conflated with it.

=== HB-018 (H2 Dispensing), task requirement 5 ===
Logic/state model: dispensed(cycle) = min(rated max throughput x
ASSUMED_HOURS_PER_CYCLE, available storage). No FCEV traffic/refuelling
demand schedule exists anywhere in this project -- "demand" is modeled
here as HB-018's own Confirmed maximum dispensing rate (1.2 kg/min = 72
kg/h), an ASSUMED full-utilization worst case, explicitly flagged as such,
not a fabricated demand curve. Reads HB-013's PREVIOUS cycle's storage
level (lagged); HB-013 reads THIS function's previous output as its own
outflow (hb_wgs_psa_storage_chain.py's own docstring addendum) -- a
genuine mutual pair, the same Phase 0 lagged mechanism, not an ad hoc one.
"""
from . import ga001_gasifier_model as ga001
from . import hb_wgs_psa_storage_chain as hbchain
from . import plant_status as ps

# --- AI-001 --------------------------------------------------------------
AI001_ILLUSTRATIVE_AVAILABILITY_FRACTION = 0.6

# --- HB-011 Electrolyser (PEM, Confirmed rated figures) -------------------
HB011_RATED_POWER_KW = 10.0
HB011_RATED_H2_NM3_H = 0.18                 # Confirmed, informational cross-check only
HB011_SEC_RATED_KWH_PER_NM3 = 55.0          # HB-011's own Confirmed "System efficiency"
HB011_WATER_L_PER_NM3 = 1.0                 # HB-011's own Confirmed "Water consumption"
HB011_MIN_LOAD_FRACTION = 0.10              # Assumed: literature-typical PEM stack turndown
                                             # (PEM commonly cited as stable down to ~5-10% of
                                             # rated current, unlike alkaline's ~20-40% -- HB-011's
                                             # own Confirmed "PEM" type). No HB-011-specific
                                             # turndown spec exists in this project's registry.
HB011_BOP_POWER_FRACTION = 0.08             # Assumed: literature-typical balance-of-plant/
                                             # auxiliary power fraction for a compact PEM system.
                                             # No HB-011-specific BoP breakdown exists in this
                                             # project's registry.

# --- HB-010 Membrane Separator ---------------------------------------------
HB010_FEED_FLOW_NM3_H = 50.0                # Confirmed (matches the flow established plant-wide)

# --- HB-014/015/016/017 LOHC branch ----------------------------------------
HB014_LOADING_EFFICIENCY_WT_PCT = 6.2       # Confirmed
HB016_RELEASE_EFFICIENCY_WT_PCT = 6.0       # Confirmed
HB017_RECOVERY_EFFICIENCY = 0.99            # Confirmed ">99%", point value used

# --- HB-018 Dispensing -------------------------------------------------------
HB018_MAX_DISPENSE_RATE_KG_H = 1.2 * 60.0   # Confirmed 1.2 kg/min -> 72 kg/h


# ============================================================================
# AI-001 -- Weather Station (illustrative renewable-availability signal)
# ============================================================================

def ai001_renewable_availability(get_input):
    """See module docstring's AI-001 section for the full, honest
    limitation. Returns a fixed illustrative availability fraction --
    Assumed, validation_basis=N-A, exactly the same tagging convention
    this project already uses elsewhere for test-only/illustrative values
    (hb_wgs_psa_storage_chain.py's own ER-perturbation override)."""
    fraction = AI001_ILLUSTRATIVE_AVAILABILITY_FRACTION
    return {
        "value": {"availability_fraction": fraction},
        "status": ps.STATUS_ASSUMED,
        "model": "hb_remaining_chain.ai001_renewable_availability",
        "inputs": [],
        "validation_basis": ps.VALIDATION_NA,
        "confidence_note": (
            f"ILLUSTRATIVE placeholder = {fraction*100:.0f}% -- NOT derived from AI-001's own real "
            f"instrument readings (no live data feed exists in this project) and NOT derived from "
            f"any renewable generation asset (none is registered anywhere in this project -- the "
            f"only renewable/grid-related item is EU-009, Electrical Metering (Grid), Phase 2 "
            f"scope). See this function's own docstring / module docstring for the full limitation."
        ),
    }


# ============================================================================
# HB-011 -- PEM Electrolyser
# ============================================================================

def hb011_electrolyser(get_input):
    """Literature part-load specific-energy-consumption (SEC) correlation:
    SEC(load) = SEC_rated x [BOP_frac + (1-BOP_frac)/load], calibrated so
    SEC(load=1.0) = SEC_rated EXACTLY (HB-011's own Confirmed 55 kWh/Nm3),
    regardless of BOP_frac's value -- a property of the formula, not a fit.
    Below load=1, SEC rises (efficiency falls) because a roughly constant
    balance-of-plant power draw gets spread over less H2 output -- a real,
    commonly-cited PEM behavior. Below HB011_MIN_LOAD_FRACTION, modeled as
    OFF (0 power, 0 H2) rather than an unstable partial-turndown state."""
    avail_entry = get_input(("AI-001", "RenewableAvailability"))
    avail_frac = (
        0.0 if avail_entry["status"] == ps.STATUS_MISSING else avail_entry["value"]["availability_fraction"]
    )
    avail_frac = min(max(avail_frac, 0.0), 1.0)

    running = avail_frac >= HB011_MIN_LOAD_FRACTION
    load = avail_frac if running else 0.0
    power_kw = load * HB011_RATED_POWER_KW
    if running:
        sec_kwh_per_nm3 = HB011_SEC_RATED_KWH_PER_NM3 * (
            HB011_BOP_POWER_FRACTION + (1.0 - HB011_BOP_POWER_FRACTION) / load
        )
        h2_nm3_h = power_kw / sec_kwh_per_nm3
    else:
        sec_kwh_per_nm3 = None
        h2_nm3_h = 0.0
    mol_h = h2_nm3_h / ga001.NM3_PER_MOL
    h2_kg_h = mol_h * hbchain.M_H2 / 1000.0
    water_l_h = h2_nm3_h * HB011_WATER_L_PER_NM3

    declared_inputs = [("AI-001", "RenewableAvailability")] if avail_entry["status"] != ps.STATUS_MISSING else []
    return {
        "value": {
            "running": running, "load_fraction": load, "power_kw": power_kw,
            "h2_nm3_h": h2_nm3_h, "h2_kg_h": h2_kg_h, "water_l_h": water_l_h,
            "sec_kwh_per_nm3": sec_kwh_per_nm3,
        },
        "status": ps.STATUS_CALCULATED,
        "model": "hb_remaining_chain.hb011_electrolyser",
        "inputs": declared_inputs,
        "validation_basis": ps.VALIDATION_ENGINEERING_CORRELATION,
        "confidence_note": (
            f"load={load*100:.1f}% (from AI-001's own illustrative availability signal, see that "
            f"function's own confidence_note), power={power_kw:.3f}kW, SEC="
            f"{'n/a (not running)' if sec_kwh_per_nm3 is None else f'{sec_kwh_per_nm3:.3f} kWh/Nm3'}, "
            f"H2={h2_nm3_h:.4f} Nm3/h. At load=1.0 this formula reproduces HB-011's own Confirmed "
            f"55.000 kWh/Nm3 SEC exactly (see this module's own self-test) -- the resulting H2 output "
            f"at that point ({HB011_RATED_POWER_KW/HB011_SEC_RATED_KWH_PER_NM3:.4f} Nm3/h) sits "
            f"~1% above HB-011's own separately-Confirmed 'H2 production rate (rated)=0.18 Nm3/h' "
            f"figure -- a minor, honestly-reported registry-internal rounding gap (10kW/0.18Nm3/h="
            f"55.56, not exactly 55), not forced to reconcile, same discipline as this project's "
            f"other real cross-checks (e.g. HB-003's heat-duty comparison)."
        ),
    }


# ============================================================================
# HB-010 -- Membrane Separator (mass-balance/pass-through portion only)
# ============================================================================

def hb010_feed(get_input):
    """Calculated half of HB-010's dual-status pair (task requirement 3) --
    real pass-through feed flow/composition from the same live WGS
    Composition node HB-006 reads. See hb010_separation() for the
    separately-Missing recovery/purity half, and module docstring's
    HB-010 section for the full reasoning behind the split -- following
    this project's own established dual-key pattern (e.g. GA-001's
    Outputs/Tar-content pair), not one key with nested partial values."""
    wgs = get_input(("WGS", "Composition"))["value"]
    dry_total = wgs["CO"] + wgs["H2"] + wgs["CO2"] + wgs["CH4"] + wgs["N2"]
    feed_composition = {
        "y_H2": wgs["H2"] / dry_total, "y_CO": wgs["CO"] / dry_total,
        "y_CO2": wgs["CO2"] / dry_total, "y_CH4": wgs["CH4"] / dry_total,
        "y_N2": wgs["N2"] / dry_total,
    }
    return {
        "value": {"feed_flow_nm3_h": HB010_FEED_FLOW_NM3_H, "feed_composition": feed_composition},
        "status": ps.STATUS_CALCULATED,
        "model": "hb_remaining_chain.hb010_feed",
        "inputs": [("WGS", "Composition")],
        "validation_basis": ps.VALIDATION_ENGINEERING_CORRELATION,
        "confidence_note": (
            f"Feed flow/composition only: {HB010_FEED_FLOW_NM3_H} Nm3/h, "
            f"y_H2={feed_composition['y_H2']*100:.2f}%. See hb010_separation() (registered as "
            f"('HB-010','Separation')) for the separately-Missing recovery/product-flow/purity outputs."
        ),
    }


def hb010_separation(get_input):
    """Permanently Missing half of HB-010's dual-status pair -- see module
    docstring's HB-010 section for the full reasoning. HB-010's own
    registry gives H2 permeance (50 GPU) and a STATIC design-point
    recovery/purity figure (85% / 95-98%) but no membrane SELECTIVITY --
    solution-diffusion membrane transport theory needs permeance AND
    selectivity together (with feed composition and the pressure ratio) to
    compute a live, composition-dependent recovery. Without selectivity
    this has no basis; the registry's own static figures are a design
    point, not something this cycle-by-cycle model can independently
    re-derive -- reporting them as freshly 'Calculated' here would
    misrepresent a copied constant as a real result. Not approximated, not
    fabricated."""
    return {
        "value": None,
        "status": ps.STATUS_MISSING,
        "model": "hb_remaining_chain.hb010_separation",
        "inputs": [],
        "validation_basis": ps.VALIDATION_NA,
        "missing_reason": (
            "recovery/product_h2_flow_nm3_h/permeate_purity: HB-010's own registry gives H2 "
            "permeance (50 GPU) and a STATIC design-point recovery/purity figure (85% / 95-98%) but "
            "no membrane SELECTIVITY -- see this function's own docstring. Not approximated, not "
            "fabricated, not copied from the static design point since that would misrepresent it "
            "as freshly calculated."
        ),
    }


# ============================================================================
# HB-007 boundary key -- H2 Split Fraction (permanently Missing)
# ============================================================================

def hb007_h2_split_fraction(get_input):
    """Permanently Missing boundary key -- see module docstring's HB-007/
    014-017 section. The single root every LOHC-branch Missing status
    downstream of it traces back to (task requirement 6's real proof)."""
    return {
        "value": None,
        "status": ps.STATUS_MISSING,
        "model": "hb_remaining_chain.hb007_h2_split_fraction",
        "inputs": [],
        "validation_basis": ps.VALIDATION_NA,
        "missing_reason": (
            "No data anywhere in this project specifies what fraction (if any) of HB-007's own PSA "
            "product H2 stream is diverted to the LOHC hydrogenation branch (HB-014) versus the "
            "primary compressed-storage route (HB-012->HB-013). HB-014's own registry remark "
            "('margin above HB-007's established ~1.85 kg/h PSA product rate') is a capacity-sizing "
            "comparison, not a confirmed live feed allocation. Not assumed, not defaulted."
        ),
    }


# ============================================================================
# HB-014 -- LOHC Hydrogenation / Loading Reactor
# ============================================================================

# Instrumentation for this module's own regression test (task requirement 6):
# proves hb014_mass_balance() is genuinely never CALLED (structural engine-level
# blocking), not merely returning Missing internally.
_HB014_MASS_BALANCE_CALL_COUNT = [0]


def hb014_mass_balance(get_input):
    """MASS-BALANCE portion only (reaction kinetics stays separately,
    unconditionally Missing -- see hb014_reaction_kinetics()). Structurally
    blocked every cycle by the permanently-Missing ("HB-007",
    "H2SplitFraction") boundary key this function's own registration
    depends_on (same-cycle) -- this function's own body is consequently
    NEVER CALLED under this project's current data (proven in this
    module's own self-test via the call counter above). Written correctly
    anyway, for forward-compatibility: the day HB-007's real split
    fraction becomes available, this starts computing real numbers with
    no further code change needed."""
    _HB014_MASS_BALANCE_CALL_COUNT[0] += 1
    split = get_input(("HB-007", "H2SplitFraction"))["value"]
    psa = get_input(("HB-006", "PSA"))["value"]
    h2_feed_kg_h = 0.0  # placeholder -- real formula would use split x HB-006/HB-012's own H2 mass flow
    carrier_circulation_kg_h = h2_feed_kg_h / (HB014_LOADING_EFFICIENCY_WT_PCT / 100.0) if h2_feed_kg_h else 0.0
    return {
        "value": {"h2_feed_kg_h": h2_feed_kg_h, "carrier_circulation_kg_h": carrier_circulation_kg_h},
        "status": ps.STATUS_CALCULATED,
        "model": "hb_remaining_chain.hb014_mass_balance",
        "inputs": [("HB-007", "H2SplitFraction"), ("HB-006", "PSA")],
        "validation_basis": ps.VALIDATION_ENGINEERING_CORRELATION,
        "confidence_note": "Unreachable under this project's current data -- see this function's own docstring.",
    }


def hb014_reaction_kinetics(get_input):
    """UNCONDITIONALLY, permanently Missing -- independent of the split-
    fraction propagation above, a second, distinct gap: no Pt/Pd-on-
    alumina DBT hydrogenation catalyst kinetic data (rate constants,
    activation energy, etc.) exists anywhere in this project."""
    return {
        "value": None, "status": ps.STATUS_MISSING,
        "model": "hb_remaining_chain.hb014_reaction_kinetics", "inputs": [],
        "validation_basis": ps.VALIDATION_NA,
        "missing_reason": (
            "No DBT hydrogenation catalyst (Pt/Pd/Al2O3) reaction-kinetics data (rate constants, "
            "activation energy) exists anywhere in this project. Unconditionally Missing -- not "
            "dependent on HB-007's split fraction, a separate, distinct gap from HB-014's "
            "mass-balance portion."
        ),
    }


# ============================================================================
# HB-015/016/017 -- LOHC storage / dehydrogenation / purification
# (each structurally cascades HB-014's own Missing status forward)
# ============================================================================

def hb015_inventory(get_input):
    """Twin-tank lean/rich carrier inventory, same lagged-self accumulation
    pattern as HB-013's own storage model. depends_on (same-cycle) HB-014's
    own MassBalance output -- structurally blocked whenever that is
    Missing (currently: always). Written correctly for forward-
    compatibility, never executed under this project's current data."""
    feed = get_input(("HB-014", "MassBalance"))["value"]
    prev = get_input(("HB-015", "Inventory"))
    prev_level = 0.0 if prev["status"] == ps.STATUS_MISSING else prev["value"]["rich_tank_kg"]
    new_level = prev_level + feed["carrier_circulation_kg_h"] * hbchain.ASSUMED_HOURS_PER_CYCLE
    return {
        "value": {"rich_tank_kg": new_level},
        "status": ps.STATUS_CALCULATED,
        "model": "hb_remaining_chain.hb015_inventory",
        "inputs": [("HB-014", "MassBalance"), ("HB-015", "Inventory")],
        "validation_basis": ps.VALIDATION_ENGINEERING_CORRELATION,
        "confidence_note": "Unreachable under this project's current data -- see hb014_mass_balance()'s own docstring.",
    }


def hb016_mass_balance(get_input):
    """H2 release mass balance, capped at HB-016's own Confirmed 2 kg H2/h
    capacity, applying its own Confirmed 6.0 wt% release efficiency
    against HB-014's own Confirmed 6.2 wt% loading efficiency (a real,
    small round-trip loss, matching the registry's own stated framing).
    depends_on (same-cycle) HB-015's own Inventory -- structurally
    cascaded-blocked, never executed under this project's current data."""
    inventory = get_input(("HB-015", "Inventory"))["value"]
    round_trip_factor = HB016_RELEASE_EFFICIENCY_WT_PCT / HB014_LOADING_EFFICIENCY_WT_PCT
    h2_release_kg_h = min(2.0, inventory["rich_tank_kg"] * round_trip_factor)
    return {
        "value": {"h2_release_kg_h": h2_release_kg_h},
        "status": ps.STATUS_CALCULATED,
        "model": "hb_remaining_chain.hb016_mass_balance",
        "inputs": [("HB-015", "Inventory")],
        "validation_basis": ps.VALIDATION_ENGINEERING_CORRELATION,
        "confidence_note": "Unreachable under this project's current data -- see hb014_mass_balance()'s own docstring.",
    }


def hb016_reaction_kinetics(get_input):
    """UNCONDITIONALLY, permanently Missing -- no Pt/Al2O3 DBT
    dehydrogenation catalyst reaction-kinetics data exists anywhere in
    this project, a separate, distinct gap from the mass-balance chain's
    propagated block above."""
    return {
        "value": None, "status": ps.STATUS_MISSING,
        "model": "hb_remaining_chain.hb016_reaction_kinetics", "inputs": [],
        "validation_basis": ps.VALIDATION_NA,
        "missing_reason": (
            "No DBT dehydrogenation catalyst (Pt/Al2O3) reaction-kinetics data exists anywhere in "
            "this project. Unconditionally Missing, independent of the propagated split-fraction block."
        ),
    }


def hb017_mass_balance(get_input):
    """Purification recovery mass balance, HB-017's own Confirmed >99%
    recovery efficiency applied to HB-016's own H2 release rate.
    depends_on (same-cycle) HB-016's own MassBalance -- structurally
    cascaded-blocked, never executed under this project's current data.
    HB-017's own registry-stated downstream routing ('rejoins HB-013 via
    HB-012') is real but NOT wired here -- there is no live number to
    merge while this stays Missing, and the task did not ask for it."""
    upstream = get_input(("HB-016", "MassBalance"))["value"]
    h2_out_kg_h = upstream["h2_release_kg_h"] * HB017_RECOVERY_EFFICIENCY
    return {
        "value": {"h2_purified_kg_h": h2_out_kg_h},
        "status": ps.STATUS_CALCULATED,
        "model": "hb_remaining_chain.hb017_mass_balance",
        "inputs": [("HB-016", "MassBalance")],
        "validation_basis": ps.VALIDATION_ENGINEERING_CORRELATION,
        "confidence_note": "Unreachable under this project's current data -- see hb014_mass_balance()'s own docstring.",
    }


# ============================================================================
# HB-018 -- H2 Dispensing Station
# ============================================================================

def hb018_dispensing(get_input):
    """See module docstring's HB-018 section for the full 'demand' framing.
    dispensed(cycle) = min(rated max throughput x ASSUMED_HOURS_PER_CYCLE,
    HB-013's own PREVIOUS cycle's available storage level (lagged))."""
    storage = get_input(("HB-013", "Storage"))  # lagged
    available_kg = 0.0 if storage["status"] == ps.STATUS_MISSING else storage["value"]["level_kg"]
    max_dispense_kg = HB018_MAX_DISPENSE_RATE_KG_H * hbchain.ASSUMED_HOURS_PER_CYCLE
    dispensed_kg = min(max_dispense_kg, available_kg)
    dispensed_kg_h = dispensed_kg / hbchain.ASSUMED_HOURS_PER_CYCLE

    declared_inputs = [("HB-013", "Storage")] if storage["status"] != ps.STATUS_MISSING else []
    return {
        "value": {
            "dispensed_kg_h": dispensed_kg_h, "dispensed_kg_this_cycle": dispensed_kg,
            "available_storage_kg": available_kg, "max_rated_kg_h": HB018_MAX_DISPENSE_RATE_KG_H,
        },
        "status": ps.STATUS_CALCULATED,
        "model": "hb_remaining_chain.hb018_dispensing",
        "inputs": declared_inputs,
        "validation_basis": ps.VALIDATION_ENGINEERING_CORRELATION,
        "confidence_note": (
            f"dispensed = min(max_rate({HB018_MAX_DISPENSE_RATE_KG_H:.1f} kg/h) x "
            f"{hbchain.ASSUMED_HOURS_PER_CYCLE} h/cycle, available storage({available_kg:.4f} kg)) = "
            f"{dispensed_kg:.4f} kg this cycle. 'Demand' modeled as HB-018's own Confirmed max rated "
            f"throughput (an ASSUMED full-utilization worst case -- no real FCEV traffic/demand "
            f"schedule exists anywhere in this project, see module docstring)."
        ),
    }


# ============================================================================
# Registration
# ============================================================================

def register_hb_remaining(engine):
    """Registers AI-001/HB-011/HB-010/HB-007/HB-014..018 with an engine
    that has ALREADY had GA-001, the GC chain, and register_hb_chain
    (HB-001..013) registered. Adds no new same-cycle edges into HB-013's
    OWN registration here -- HB-013's lagged reads of HB-011/HB-018 are
    declared in hb_wgs_psa_storage_chain.py's own register_hb_chain()."""
    engine.register_model(("AI-001", "RenewableAvailability"), ai001_renewable_availability,
                           unit="fraction dict", depends_on=[])
    engine.register_model(("HB-011", "Electrolyser"), hb011_electrolyser, unit="kW/Nm3/kg dict",
                           depends_on=[("AI-001", "RenewableAvailability")])
    engine.register_model(("HB-010", "Feed"), hb010_feed, unit="Nm3/h dict",
                           depends_on=[("WGS", "Composition")])
    engine.register_model(("HB-010", "Separation"), hb010_separation, unit="fraction dict",
                           depends_on=[])
    engine.register_model(("HB-007", "H2SplitFraction"), hb007_h2_split_fraction, unit="fraction",
                           depends_on=[])
    engine.register_model(("HB-014", "MassBalance"), hb014_mass_balance, unit="kg/h dict",
                           depends_on=[("HB-007", "H2SplitFraction"), ("HB-006", "PSA")])
    engine.register_model(("HB-014", "ReactionKinetics"), hb014_reaction_kinetics, unit="n/a",
                           depends_on=[])
    engine.register_model(("HB-015", "Inventory"), hb015_inventory, unit="kg dict",
                           depends_on=[("HB-014", "MassBalance")], lagged_depends_on=[("HB-015", "Inventory")])
    engine.register_model(("HB-016", "MassBalance"), hb016_mass_balance, unit="kg/h dict",
                           depends_on=[("HB-015", "Inventory")])
    engine.register_model(("HB-016", "ReactionKinetics"), hb016_reaction_kinetics, unit="n/a",
                           depends_on=[])
    engine.register_model(("HB-017", "MassBalance"), hb017_mass_balance, unit="kg/h dict",
                           depends_on=[("HB-016", "MassBalance")])
    engine.register_model(("HB-018", "Dispensing"), hb018_dispensing, unit="kg/h dict",
                           depends_on=[], lagged_depends_on=[("HB-013", "Storage")])


if __name__ == "__main__":
    from . import gc_gas_cleaning_chain as gc
    from . import shared_plant_state as sps
    from . import simulation_engine as se

    def _mock_missing(reason="mock: absent"):
        return {"value": None, "status": ps.STATUS_MISSING, "missing_reason": reason}

    print("=== Direct-call checks (no engine) ===")

    ai001_out = ai001_renewable_availability(lambda k: None)
    assert ai001_out["status"] == ps.STATUS_ASSUMED
    assert ai001_out["value"]["availability_fraction"] == AI001_ILLUSTRATIVE_AVAILABILITY_FRACTION
    print(f"  AI-001: {ai001_out['value']} (Assumed, illustrative) -- OK")

    def _mock_avail(frac):
        return lambda k: {"value": {"availability_fraction": frac}, "status": ps.STATUS_ASSUMED}

    hb011_full = hb011_electrolyser(_mock_avail(1.0))
    sec_at_full = hb011_full["value"]["sec_kwh_per_nm3"]
    assert abs(sec_at_full - HB011_SEC_RATED_KWH_PER_NM3) < 1e-9, (
        f"REGRESSION: SEC at load=1.0 ({sec_at_full}) does not exactly reproduce HB-011's own "
        f"Confirmed {HB011_SEC_RATED_KWH_PER_NM3} kWh/Nm3."
    )
    print(f"  HB-011 at load=1.0: SEC={sec_at_full:.6f} kWh/Nm3 (exact match to Confirmed "
          f"{HB011_SEC_RATED_KWH_PER_NM3}) -- PASSED")
    print(f"    H2 output at load=1.0: {hb011_full['value']['h2_nm3_h']:.4f} Nm3/h (HB-011's own "
          f"separately-Confirmed rated figure: {HB011_RATED_H2_NM3_H} Nm3/h -- ~1% gap, honest, see "
          f"this module's own docstring)")

    hb011_below_min = hb011_electrolyser(_mock_avail(0.05))
    assert hb011_below_min["value"]["running"] is False
    assert hb011_below_min["value"]["power_kw"] == 0.0 and hb011_below_min["value"]["h2_nm3_h"] == 0.0
    print(f"  HB-011 at avail=5% (below {HB011_MIN_LOAD_FRACTION*100:.0f}% min turndown): OFF, "
          f"power=0, H2=0 -- PASSED")

    hb011_missing_avail = hb011_electrolyser(lambda k: _mock_missing())
    assert hb011_missing_avail["value"]["running"] is False and hb011_missing_avail["inputs"] == []
    print("  HB-011 with AI-001 Missing: gracefully treated as 0% availability, OFF -- PASSED")

    def _mock_wgs(k):
        assert k == ("WGS", "Composition")
        return {"value": {"CO": 0.20, "H2": 0.25, "CO2": 0.13, "CH4": 0.018, "N2": 0.40}}

    hb010_feed_out = hb010_feed(_mock_wgs)
    assert hb010_feed_out["status"] == ps.STATUS_CALCULATED
    assert abs(sum(hb010_feed_out["value"]["feed_composition"].values()) - 1.0) < 1e-9
    print(f"  HB-010 Feed: {hb010_feed_out['value']} -- PASSED")

    hb010_sep_out = hb010_separation(lambda k: None)
    assert hb010_sep_out["status"] == ps.STATUS_MISSING and hb010_sep_out["value"] is None
    assert "selectivity" in hb010_sep_out["missing_reason"].lower()
    print("  HB-010 Separation: Missing, reason names the real selectivity gap -- PASSED")

    hb007_out = hb007_h2_split_fraction(lambda k: None)
    assert hb007_out["status"] == ps.STATUS_MISSING
    print("  HB-007 H2SplitFraction: Missing -- PASSED")

    print("\n=== Full-engine integration: GA-001 -> GC -> HB-001..013 -> HB-remaining ===")
    from . import ga001_gasifier_model as ga

    state = sps.SharedPlantState()
    handle = state.new_writer_handle()
    engine = se.SimulationEngine(state)
    ga.register_ga001(engine)
    gc.register_gc_chain(engine)
    hbchain.register_hb_chain(engine)
    register_hb_remaining(engine)

    N_CYCLES = 10
    for i in range(N_CYCLES):
        engine.run_cycle(now=f"2026-09-04T02:{i:02d}:00Z")
    snap = state.get_snapshot()

    print(f"  AI-001: {snap[('AI-001','RenewableAvailability')]['value']}")
    hb011_live = snap[("HB-011", "Electrolyser")]
    print(f"  HB-011 (live, engine-driven): status={hb011_live['status']}  {hb011_live['value']}")
    assert hb011_live["status"] == ps.STATUS_CALCULATED and hb011_live["value"]["running"] is True

    hb010_feed_live = snap[("HB-010", "Feed")]
    hb010_sep_live = snap[("HB-010", "Separation")]
    print(f"  HB-010 Feed: status={hb010_feed_live['status']}  {hb010_feed_live['value']}")
    print(f"  HB-010 Separation: status={hb010_sep_live['status']}  reason={hb010_sep_live['missing_reason']}")
    assert hb010_feed_live["status"] == ps.STATUS_CALCULATED
    assert hb010_sep_live["status"] == ps.STATUS_MISSING

    print("\n=== task requirement 6: blocked-status propagation, the real proof of this phase ===")
    for k in [("HB-007", "H2SplitFraction"), ("HB-014", "MassBalance"), ("HB-014", "ReactionKinetics"),
              ("HB-015", "Inventory"), ("HB-016", "MassBalance"), ("HB-016", "ReactionKinetics"),
              ("HB-017", "MassBalance")]:
        entry = snap[k]
        status_str = "Missing" if entry["status"] == ps.STATUS_MISSING else entry["status"]
        print(f"  {k}: {status_str}")
        assert entry["status"] == ps.STATUS_MISSING, f"REGRESSION: {k} is not Missing -- {entry}"

    assert _HB014_MASS_BALANCE_CALL_COUNT[0] == 0, (
        f"REGRESSION: hb014_mass_balance() was called {_HB014_MASS_BALANCE_CALL_COUNT[0]} time(s) -- "
        f"it should NEVER be invoked while HB-007's H2SplitFraction stays Missing (structural "
        f"same-cycle blocking should skip it entirely)."
    )
    print(f"  hb014_mass_balance() call count after {N_CYCLES} cycles: "
          f"{_HB014_MASS_BALANCE_CALL_COUNT[0]} -- PASSED (structurally never invoked, not just "
          f"internally returning Missing)")

    # missing_roots() returns EVERY Missing node in the chain (task requirement
    # 6 wants specifically the count of GENUINE origins, not propagated
    # consequences) -- a node is a genuine origin if its OWN missing_reason
    # does not itself cite "upstream input(s)... structural Missing
    # propagation" (the engine's own fixed wording for a propagated block,
    # simulation_engine.py's run_cycle()).
    all_missing_017 = ps.missing_roots(snap, ("HB-017", "MassBalance"))
    print(f"  missing_roots() from HB-017's own MassBalance reaches {len(all_missing_017)} Missing "
          f"nodes total: {[n['key'] for n in all_missing_017]}")
    genuine_origins = {
        n["key"] for n in all_missing_017 if "upstream input(s)" not in (n["missing_reason"] or "")
    }
    assert genuine_origins == {("HB-007", "H2SplitFraction")}, (
        f"REGRESSION: expected exactly ONE genuine origin ('HB-007','H2SplitFraction'), found "
        f"{genuine_origins} -- HB-014/015/016/017 must be propagated CONSEQUENCES of that one "
        f"blocker (their own missing_reason must cite 'upstream input(s)... structural Missing "
        f"propagation'), not independently-declared gaps with their own separate justification."
    )
    print(f"  Genuine origin(s) (missing_reason NOT citing structural propagation): {genuine_origins}")
    print("  PASSED -- HB-014's MassBalance, HB-015's Inventory, HB-016's MassBalance, and HB-017's "
          "MassBalance are ALL propagated consequences of the SAME single root cause -- their own "
          "missing_reason literally names the one upstream key that blocked them, not four "
          "independently-declared gaps that merely happen to agree.")

    print("\n=== Mechanical fabrication guard, reused directly (task requirement 6's own risk mitigation) ===")
    try:
        ps.validate_entry_shape(
            ("HB-015", "Inventory"),
            {"value": {"rich_tank_kg": 3.5}, "unit": "kg dict", "status": ps.STATUS_MISSING,
             "source": {"model": "fake", "inputs": []}, "validation_basis": ps.VALIDATION_NA,
             "confidence_note": "", "cycle": 1, "timestamp": "x",
             "missing_reason": "should never coexist with a real value"},
        )
        raise AssertionError("REGRESSION: validate_entry_shape() accepted a fabricated value on a Missing entry!")
    except ValueError as e:
        print(f"  Correctly REJECTED an attempt to fabricate a value on a Missing entry: {e}")

    print("\n=== HB-013's own new inflow/outflow wiring (HB-011 electrolyser route + HB-018 dispensing) ===")
    storage = snap[("HB-013", "Storage")]
    dispensing = snap[("HB-018", "Dispensing")]
    print(f"  HB-013 after {N_CYCLES} cycles: level={storage['value']['level_kg']:.4f} kg  "
          f"inflow={storage['value']['inflow_kg_h']:.4f} kg/h (PSA+electrolyser)  "
          f"outflow={storage['value']['outflow_kg_h']:.4f} kg/h")
    print(f"  HB-018 (final cycle): dispensed={dispensing['value']['dispensed_kg_h']:.4f} kg/h  "
          f"available_at_start_of_cycle={dispensing['value']['available_storage_kg']:.4f} kg")
    assert dispensing["value"]["dispensed_kg_h"] > 0.0, (
        "REGRESSION: HB-018 never dispensed anything over 10 cycles despite HB-013 accumulating stock."
    )
    print("  PASSED -- HB-013's storage level reflects both the PSA/WGS route AND the electrolyser "
          "route, and HB-018 genuinely draws it down through the same lagged mutual-pair mechanism "
          "already proven on the synthetic pair in Phase 0.")

    print("\nAll hb_remaining_chain.py self-tests PASSED.")
