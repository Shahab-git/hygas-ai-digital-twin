"""
Feed Handling Fully Live -- Digital Twin Phase 3.

Implements the roadmap's Part 1.1 / Part 4: FE-001 through FE-008, and the
real connection point -- FE-003's confirmed feed rate and FE-005's
calculated outlet moisture become GA-001's real live inputs, replacing the
manual placeholder used throughout Phases 1-2 (ga001_gasifier_model.py's
own _input_dry_feed_rate(), see that module's own PHASE 3 ADDENDUM). No
other Phase (GC/HB/EU) file is touched.

=== THE RESOLVED WET/DRY FEED-RATE BASIS FINDING (confirmed by the user
before implementation) ===
A real, pre-existing internal inconsistency, found while wiring FE-003 to
GA-001: CLAUDE.md's own recorded recalibration decision treats DOK-ING's
confirmed 41.67 kg/h (1,000 kg/day, RFI #1) as the DRY feed rate GA-001
uses directly. But equipment_engineering_estimates.py's own EXISTING FE-007
static fill treats that SAME 41.67 kg/h as the AS-RECEIVED (WET, ~10%
moisture) rate, deriving a dry mass of 37.5 kg/h (41.67 x 0.90) and a
post-drying wet mass of ~37.9 kg/h (37.5 / 0.99) via a standard wet/dry
moisture-basis mass-balance conversion.

RESOLVED (user decision): 41.67 kg/h is FE-003's own confirmed AS-RECEIVED
(wet) feed rate. FE-005's own moisture mass balance converts it to dry
solids (~37.5 kg/h), which is what actually reaches GA-001's own
dry_feed_rate_kg_h input -- a genuine ~10% change from the Phase 1-2
placeholder's own (misapplied) 41.67 kg/h dry figure, matching
equipment_engineering_estimates.py's own existing FE-007 static fill
almost exactly (a real, unforced cross-check, verified in this module's
own self-test). CLAUDE.md's "Current feed-rate basis" note is updated
alongside this file to reflect the refinement.

=== The reconstructed real physical equipment order (task requirement 1)
===
FE-001 (Hopper) -> FE-002 (Magnetic/Eddy separator) -> FE-003 (Weighing
Conveyor) -> FE-004 (Shredder) -> FE-005 (Dryer) -> FE-006 (Moisture
Analyser) -> FE-007 (Ram Feeder) -> FE-008 (Air-lock/Rotary Valve) ->
GA-001. Cross-validated across several of these items' OWN remarks, which
contain a REAL, PRE-EXISTING pattern of shifted/mislabeled cross-
references (not fixed at the source -- data/equipment_registry.json is
off-limits, same discipline as every prior phase's own found mislabels):
  - FE-002's own remark calls FE-003 "the Shredder" -- FE-003 is the
    Weighing Conveyor; FE-004 is the actual Shredder/Size Reducer.
  - FE-003's own remark describes its connecting run as "between FE-008
    and FE-003" -- a literal self-reference, garbled; the real sequence
    (FE-002 -> FE-003 -> FE-004) is used instead, not over-interpreted.
  - FE-006's own remark says it "reads material right as it leaves FE-007,
    before FE-005" -- physically backwards (a moisture analyser reading
    material as it leaves a RAM FEEDER, before a DRYER, makes no sense);
    almost certainly means "leaves FE-005 [the dryer], before FE-007 [the
    ram feeder]," which this module wires.
  - FE-007's own remark says its feed plug "works with FE-006 downstream
    to hold reactor pressure" -- FE-006 is the Moisture Analyser, not a
    valve; almost certainly FE-008 (the Air-lock/Rotary Valve).
  - FE-008's own remark says its own seal "works with FE-005's compacted
    plug" -- FE-005 is the Dryer, with no plug feature; FE-007's own data
    is the one that actually describes "a compacted feed plug," almost
    certainly the intended reference.

=== Task requirement 2 -- what does NOT change ===
Feed elemental composition (ga001_gasifier_model.py's own
_input_feedstock_composition()) stays Assumed, completely untouched by
this phase -- FE has no composition-analysis equipment anywhere in this
project's registry (no proximate/ultimate analysis instrument), so this
gap does not close here. Only feed RATE and MOISTURE go live.

=== Task requirement 3 -- FE-002's dual status ===
("FE-002","MassBalance") is genuinely live (Calculated); ("FE-002",
"TrampMetalReject") stays permanently Missing -- no feedstock tramp-metal
loading data exists anywhere in this project, same discipline as every
other permanently-blocked output (HB-010's Separation, GA-001's Tar
content, etc.).

=== Task requirement 5 -- the getter-discipline proof ===
ga001_gasifier_model.py's own ga001_model() function body needed ZERO
changes to accept FE-005's live dry-solids mass as its feed rate -- it
still only ever calls get_input(("GA-001-INPUT","dry_feed_rate_kg_h"))
["value"], unaware of which function produced it. Only
_input_dry_feed_rate()'s OWN body (already explicitly documented, since
Phase 1a, as a temporary placeholder standing in for exactly this) and
register_ga001()'s OWN registration (adding one lagged_depends_on edge)
changed -- proving the getter-discipline (roadmap Part 8.3) works exactly
as designed.
"""
from . import hb_wgs_psa_storage_chain as hbchain
from . import plant_status as ps

# --- FE-001 Hopper (Confirmed figures) --------------------------------------
FE001_TOTAL_CAPACITY_T = 2.0
FE001_LIVE_CAPACITY_T = 1.7
FE001_DEFAULT_DELIVERY_RATE_KG_H = 41.67  # Confirmed, DOK-ING RFI #1, 1,000 kg/day AS-RECEIVED

# --- FE-002 Magnetic & Eddy Current Separator (Confirmed) -------------------
FE002_REMOVAL_EFFICIENCY = 0.98  # informational; a polishing duty, negligible mass removed

# --- FE-003 Weighing Conveyor (Confirmed) -----------------------------------
FE003_NOMINAL_KG_H = 41.67
FE003_MIN_KG_H = 29.0
FE003_MAX_KG_H = 50.0

# --- FE-004 Shredder / Size Reducer (both Confirmed, ratio matches
# equipment_engineering_estimates.py's own existing FE-004 static fill exactly) --
FE004_MOTOR_KW = 15.0
FE004_THROUGHPUT_T_H = 0.1
FE004_SPECIFIC_ENERGY_KWH_PER_T = FE004_MOTOR_KW / FE004_THROUGHPUT_T_H  # = 150.0

# --- FE-005 Feed Dryer (both Confirmed) -------------------------------------
FE005_INLET_MOISTURE_FRACTION = 0.10
FE005_OUTLET_MOISTURE_FRACTION = 0.01  # FE-005's own Confirmed "<1%" target, taken as ~1%,
                                         # same treatment as the existing FE-007 static fill


# ============================================================================
# FE-001 -- MSW Receiving Hopper
# ============================================================================

def fe001_msw_delivery_rate(get_input):
    """The perturbable INPUT for this phase's own propagation test (task
    requirement 4) -- represents the plant's current average MSW intake
    rate. Defaults to FE-003's own Confirmed nominal AS-RECEIVED rate
    (41.67 kg/h, DOK-ING RFI #1, 1,000 kg/day) -- the SAME number the
    Phase 1-2 placeholder used, now correctly understood as the WET,
    as-received basis (see module docstring)."""
    return {
        "value": FE001_DEFAULT_DELIVERY_RATE_KG_H, "status": ps.STATUS_ASSUMED,
        "inputs": [], "validation_basis": ps.VALIDATION_NA,
        "confidence_note": (
            f"DOK-ING's own confirmed nominal AS-RECEIVED delivery rate (RFI #1, 1,000 kg/day = "
            f"{FE001_DEFAULT_DELIVERY_RATE_KG_H} kg/h). The perturbable knob this phase's own "
            f"self-test uses to prove end-to-end propagation."
        ),
    }


def fe001_inventory(get_input):
    """Inventory mass balance (task requirement 1): level(cycle N) =
    level(cycle N-1) + (delivery - FE-003's own Confirmed nominal design
    discharge) x ASSUMED_HOURS_PER_CYCLE, clamped to [0, FE-001's own
    Confirmed live capacity]. Lagged self-dependency, the same Phase 0
    mechanism as HB-013's own inventory.

    STATED SIMPLIFICATION, not hidden: the material that actually feeds
    FE-002 onward each cycle is the delivery rate DIRECTLY (fe002_mass_
    balance() reads it from this entry) -- this level is a real, live
    buffer/utilization indicator against FE-003's own Confirmed nominal
    throughput, not (in this phase) a hard physical constraint that caps
    what the shredder/dryer/gasifier train can actually process. Bootstraps
    at 50% full -- a stated, neutral starting assumption, same convention
    as EU-010's own 50% SOC bootstrap (eu_utilities_chp.py)."""
    delivery_rate_kg_h = get_input(("FE-001-INPUT", "msw_delivery_rate_kg_h"))["value"]
    prev = get_input(("FE-001", "Inventory"))  # lagged, self
    prev_level_t = FE001_LIVE_CAPACITY_T * 0.5 if prev["status"] == ps.STATUS_MISSING else prev["value"]["level_t"]
    net_t = (delivery_rate_kg_h - FE003_NOMINAL_KG_H) / 1000.0 * hbchain.ASSUMED_HOURS_PER_CYCLE
    new_level_t = min(max(prev_level_t + net_t, 0.0), FE001_LIVE_CAPACITY_T)
    return {
        "value": {
            "level_t": new_level_t, "delivery_rate_kg_h": delivery_rate_kg_h,
            "fraction_full": new_level_t / FE001_LIVE_CAPACITY_T,
        },
        "status": ps.STATUS_CALCULATED, "model": "fe_feed_handling.fe001_inventory",
        "inputs": [("FE-001-INPUT", "msw_delivery_rate_kg_h"), ("FE-001", "Inventory")],
        "validation_basis": ps.VALIDATION_ENGINEERING_CORRELATION,
        "confidence_note": (
            f"level = prev({prev_level_t:.4f} t) + (delivery({delivery_rate_kg_h:.3f} kg/h) - "
            f"FE-003's own Confirmed nominal({FE003_NOMINAL_KG_H} kg/h)) x "
            f"{hbchain.ASSUMED_HOURS_PER_CYCLE} h/cycle, clamped to [0, {FE001_LIVE_CAPACITY_T}t] "
            f"(FE-001's own Confirmed live capacity). See this function's own docstring for the "
            f"stated simplification (delivery feeds FE-002 onward directly, not this level)."
        ),
    }


# ============================================================================
# FE-002 -- Magnetic & Eddy Current Separator (dual status)
# ============================================================================

def fe002_mass_balance(get_input):
    """Calculated half of FE-002's dual-status pair (task requirement 3) --
    mass pass-through of FE-001's own live delivery rate. A polishing duty
    (FE-002's own Confirmed >98% removal efficiency applies to trace
    tramp-metal content only) -- negligible mass removed, not modeled as
    a separate mass-balance term."""
    inventory = get_input(("FE-001", "Inventory"))["value"]
    outlet_kg_h = inventory["delivery_rate_kg_h"]
    return {
        "value": {"outlet_kg_h": outlet_kg_h},
        "status": ps.STATUS_CALCULATED, "model": "fe_feed_handling.fe002_mass_balance",
        "inputs": [("FE-001", "Inventory")], "validation_basis": ps.VALIDATION_ENGINEERING_CORRELATION,
        "confidence_note": f"Mass pass-through: {outlet_kg_h:.3f} kg/h (polishing duty, negligible mass removed).",
    }


def fe002_tramp_metal_reject(get_input):
    """Permanently Missing half of FE-002's dual-status pair -- see module
    docstring's task requirement 3 section. No feedstock tramp-metal
    loading data exists anywhere in this project."""
    return {
        "value": None, "status": ps.STATUS_MISSING,
        "model": "fe_feed_handling.fe002_tramp_metal_reject", "inputs": [],
        "validation_basis": ps.VALIDATION_NA,
        "missing_reason": (
            "No feedstock tramp-metal (ferrous/non-ferrous) loading data exists anywhere in this "
            "project -- FE-002's own Confirmed '>98% removal efficiency' describes the SEPARATOR's "
            "own performance spec, not the actual metal content of DOK-ING's feedstock, which is "
            "unconfirmed. Not approximated, not fabricated."
        ),
    }


# ============================================================================
# FE-003 -- Weighing Conveyor
# ============================================================================

def fe003_weighing(get_input):
    """The item this task's own item 2 calls "FE-003's confirmed feed
    rate" -- clipped to FE-003's own Confirmed min/max operating range
    (29-50 kg/h), the real equipment-throughput constraint. STATED
    LIMITATION: if the raw delivery ever falls outside this range, this
    simplified chain does not model where the resulting surplus/deficit
    mass goes (not exercised by this phase's own baseline or perturbation
    test, both of which stay within FE-003's own confirmed range)."""
    inlet_kg_h = get_input(("FE-002", "MassBalance"))["value"]["outlet_kg_h"]
    confirmed_kg_h = min(max(inlet_kg_h, FE003_MIN_KG_H), FE003_MAX_KG_H)
    clipped = confirmed_kg_h != inlet_kg_h
    return {
        "value": {"confirmed_wet_feed_kg_h": confirmed_kg_h, "clipped": clipped},
        "status": ps.STATUS_CALCULATED, "model": "fe_feed_handling.fe003_weighing",
        "inputs": [("FE-002", "MassBalance")], "validation_basis": ps.VALIDATION_ENGINEERING_CORRELATION,
        "confidence_note": (
            f"confirmed={confirmed_kg_h:.3f} kg/h (inlet={inlet_kg_h:.3f}), clipped to FE-003's own "
            f"Confirmed [{FE003_MIN_KG_H},{FE003_MAX_KG_H}] kg/h range"
            f"{' -- CLIPPED this cycle' if clipped else ''}. This IS the AS-RECEIVED (WET) feed "
            f"rate -- see module docstring's resolved wet/dry basis finding."
        ),
    }


# ============================================================================
# FE-004 -- Shredder / Size Reducer
# ============================================================================

def fe004_shredder_power(get_input):
    """Power/throughput calc (task requirement 1), cross-verified against
    equipment_engineering_estimates.py's own existing static fill: specific
    energy = Drive motor power (15kW, Confirmed) / Throughput capacity
    (0.1 t/h, Confirmed) = 150 kWh/t EXACTLY, by construction (the same
    ratio of the same two Confirmed nameplate figures the static fill
    itself used) -- not independently re-derived, verified identical in
    this module's own self-test. Live power draw scales with FE-003's own
    live throughput. Mass pass-through -- shredding doesn't change mass."""
    rate_kg_h = get_input(("FE-003", "Weighing"))["value"]["confirmed_wet_feed_kg_h"]
    throughput_t_h = rate_kg_h / 1000.0
    power_kw = FE004_SPECIFIC_ENERGY_KWH_PER_T * throughput_t_h
    return {
        "value": {
            "outlet_kg_h": rate_kg_h, "specific_energy_kwh_per_t": FE004_SPECIFIC_ENERGY_KWH_PER_T,
            "power_kw": power_kw,
        },
        "status": ps.STATUS_CALCULATED, "model": "fe_feed_handling.fe004_shredder_power",
        "inputs": [("FE-003", "Weighing")], "validation_basis": ps.VALIDATION_ENGINEERING_CORRELATION,
        "confidence_note": (
            f"specific_energy = {FE004_MOTOR_KW}kW / {FE004_THROUGHPUT_T_H}t/h = "
            f"{FE004_SPECIFIC_ENERGY_KWH_PER_T:.1f} kWh/t (EXACT match to "
            f"equipment_engineering_estimates.py's own existing FE-004 static fill). Live power = "
            f"{power_kw:.3f} kW at {throughput_t_h:.4f} t/h actual throughput."
        ),
    }


# ============================================================================
# FE-005 -- Feed Dryer (Rotary/Belt)
# ============================================================================

def fe005_moisture_balance(get_input):
    """Moisture mass balance (task requirement 1), cross-verified against
    equipment_engineering_estimates.py's own existing FE-007 static fill
    (~37.5 kg/h dry, ~37.9 kg/h post-drying wet): standard wet/dry
    moisture-basis conversion using FE-005's own Confirmed inlet (10%) and
    outlet (~1%) moisture. THE REAL CONNECTION POINT (task requirement 2):
    dry_solids_kg_h becomes GA-001's own live dry_feed_rate_kg_h input
    (via ga001_gasifier_model.py's own _input_dry_feed_rate(), lagged);
    residual_water_kg_h becomes an additional live water/steam input to
    GA-001's own atom balance (via _moisture_water_moles(), also lagged).
    Feed elemental COMPOSITION is untouched by this -- still Assumed, see
    module docstring."""
    wet_inlet_kg_h = get_input(("FE-004", "ShredderPower"))["value"]["outlet_kg_h"]
    dry_solids_kg_h = wet_inlet_kg_h * (1.0 - FE005_INLET_MOISTURE_FRACTION)
    outlet_wet_kg_h = dry_solids_kg_h / (1.0 - FE005_OUTLET_MOISTURE_FRACTION)
    residual_water_kg_h = outlet_wet_kg_h - dry_solids_kg_h
    water_evaporated_kg_h = wet_inlet_kg_h - outlet_wet_kg_h
    return {
        "value": {
            "dry_solids_kg_h": dry_solids_kg_h, "outlet_wet_kg_h": outlet_wet_kg_h,
            "outlet_moisture_fraction": FE005_OUTLET_MOISTURE_FRACTION,
            "residual_water_kg_h": residual_water_kg_h, "water_evaporated_kg_h": water_evaporated_kg_h,
        },
        "status": ps.STATUS_CALCULATED, "model": "fe_feed_handling.fe005_moisture_balance",
        "inputs": [("FE-004", "ShredderPower")], "validation_basis": ps.VALIDATION_ENGINEERING_CORRELATION,
        "confidence_note": (
            f"dry_solids = {wet_inlet_kg_h:.3f} x (1-{FE005_INLET_MOISTURE_FRACTION}) = "
            f"{dry_solids_kg_h:.3f} kg/h (equipment_engineering_estimates.py's own existing "
            f"FE-007 static fill: ~37.5 kg/h). outlet_wet = dry_solids / "
            f"(1-{FE005_OUTLET_MOISTURE_FRACTION}) = {outlet_wet_kg_h:.3f} kg/h (static fill: "
            f"~37.9 kg/h). residual_water={residual_water_kg_h:.4f} kg/h (folds into GA-001's "
            f"own water/steam pool). water_evaporated={water_evaporated_kg_h:.3f} kg/h."
        ),
    }


# ============================================================================
# FE-006 -- Moisture Analyser
# ============================================================================

def fe006_moisture_reading(get_input):
    """Pass-through reading of FE-005's own outlet moisture (real
    installation position, corrected mislabel -- see module docstring)."""
    moisture = get_input(("FE-005", "MoistureBalance"))["value"]
    return {
        "value": {"moisture_fraction": moisture["outlet_moisture_fraction"]},
        "status": ps.STATUS_CALCULATED, "model": "fe_feed_handling.fe006_moisture_reading",
        "inputs": [("FE-005", "MoistureBalance")], "validation_basis": ps.VALIDATION_ENGINEERING_CORRELATION,
        "confidence_note": f"Reads FE-005's own outlet moisture: {moisture['outlet_moisture_fraction']*100:.2f}%.",
    }


# ============================================================================
# FE-007 -- Feed Screw / Ram Feeder
# ============================================================================

def fe007_ram_feeder(get_input):
    """Pass-through of FE-005's own post-drying wet mass (real physical
    order -- see module docstring's corrected mislabel note)."""
    moisture = get_input(("FE-005", "MoistureBalance"))["value"]
    feed_rate_kg_h = moisture["outlet_wet_kg_h"]
    return {
        "value": {"feed_rate_kg_h": feed_rate_kg_h},
        "status": ps.STATUS_CALCULATED, "model": "fe_feed_handling.fe007_ram_feeder",
        "inputs": [("FE-005", "MoistureBalance")], "validation_basis": ps.VALIDATION_ENGINEERING_CORRELATION,
        "confidence_note": (
            f"Pass-through of FE-005's own post-drying wet mass: {feed_rate_kg_h:.3f} kg/h "
            f"(equipment_engineering_estimates.py's own existing FE-007 static fill: ~37.9 kg/h)."
        ),
    }


# ============================================================================
# FE-008 -- Air-lock / Rotary Valve
# ============================================================================

def fe008_airlock(get_input):
    """Pass-through of FE-007's own feed rate -- FE-008's own registry
    remark ('no further moisture change') matches the existing FE-008
    static fill's own reasoning exactly."""
    fe007 = get_input(("FE-007", "RamFeeder"))["value"]
    feed_rate_kg_h = fe007["feed_rate_kg_h"]
    return {
        "value": {"feed_rate_kg_h": feed_rate_kg_h},
        "status": ps.STATUS_CALCULATED, "model": "fe_feed_handling.fe008_airlock",
        "inputs": [("FE-007", "RamFeeder")], "validation_basis": ps.VALIDATION_ENGINEERING_CORRELATION,
        "confidence_note": f"Pass-through, no further moisture change: {feed_rate_kg_h:.3f} kg/h -> GA-001.",
    }


# ============================================================================
# Registration
# ============================================================================

def register_fe_chain(engine):
    """Registers FE-001..008 with an engine. Order-independent relative to
    register_ga001() (only ga001_gasifier_model.py's own registration
    declares a lagged read of ("FE-005","MoistureBalance") -- see that
    module's own docstring addendum); call this alongside it in any order."""
    engine.register_model(("FE-001-INPUT", "msw_delivery_rate_kg_h"), fe001_msw_delivery_rate, unit="kg/h")
    engine.register_model(
        ("FE-001", "Inventory"), fe001_inventory, unit="t dict",
        depends_on=[("FE-001-INPUT", "msw_delivery_rate_kg_h")], lagged_depends_on=[("FE-001", "Inventory")],
    )
    engine.register_model(("FE-002", "MassBalance"), fe002_mass_balance, unit="kg/h dict",
                           depends_on=[("FE-001", "Inventory")])
    engine.register_model(("FE-002", "TrampMetalReject"), fe002_tramp_metal_reject, unit="kg/h", depends_on=[])
    engine.register_model(("FE-003", "Weighing"), fe003_weighing, unit="kg/h dict",
                           depends_on=[("FE-002", "MassBalance")])
    engine.register_model(("FE-004", "ShredderPower"), fe004_shredder_power, unit="kg/h + kW dict",
                           depends_on=[("FE-003", "Weighing")])
    engine.register_model(("FE-005", "MoistureBalance"), fe005_moisture_balance, unit="kg/h dict",
                           depends_on=[("FE-004", "ShredderPower")])
    engine.register_model(("FE-006", "MoistureReading"), fe006_moisture_reading, unit="fraction dict",
                           depends_on=[("FE-005", "MoistureBalance")])
    engine.register_model(("FE-007", "RamFeeder"), fe007_ram_feeder, unit="kg/h dict",
                           depends_on=[("FE-005", "MoistureBalance")])
    engine.register_model(("FE-008", "Airlock"), fe008_airlock, unit="kg/h dict",
                           depends_on=[("FE-007", "RamFeeder")])


if __name__ == "__main__":
    from . import eu_utilities_chp as eu
    from . import ga001_gasifier_model as ga001
    from . import gc_gas_cleaning_chain as gc
    from . import hb_remaining_chain as hbrem
    from . import shared_plant_state as sps
    from . import simulation_engine as se

    print("=== Task requirement 1: cross-checks against existing static fills, direct call ===")

    def _mock_shredder_out(rate_kg_h):
        return lambda k: {"value": {"outlet_kg_h": rate_kg_h}}

    fe005_direct = fe005_moisture_balance(_mock_shredder_out(FE003_NOMINAL_KG_H))
    dry_solids = fe005_direct["value"]["dry_solids_kg_h"]
    outlet_wet = fe005_direct["value"]["outlet_wet_kg_h"]
    assert abs(dry_solids - 37.503) < 0.01, f"REGRESSION: dry_solids={dry_solids}, expected ~37.5"
    assert abs(outlet_wet - 37.881) < 0.01, f"REGRESSION: outlet_wet={outlet_wet}, expected ~37.9"
    print(f"  FE-005 at nominal {FE003_NOMINAL_KG_H} kg/h wet inlet: dry_solids={dry_solids:.3f} kg/h "
          f"(equipment_engineering_estimates.py's own existing FE-007 static fill: ~37.5 kg/h), "
          f"outlet_wet={outlet_wet:.3f} kg/h (static fill: ~37.9 kg/h) -- PASSED, matches almost exactly.")

    assert FE004_SPECIFIC_ENERGY_KWH_PER_T == 150.0, (
        f"REGRESSION: FE-004 specific energy = {FE004_SPECIFIC_ENERGY_KWH_PER_T}, expected exactly 150.0."
    )
    print(f"  FE-004 specific energy = {FE004_SPECIFIC_ENERGY_KWH_PER_T} kWh/t -- EXACT match to "
          f"equipment_engineering_estimates.py's own existing FE-004 static fill -- PASSED.")

    fe002_reject = fe002_tramp_metal_reject(lambda k: None)
    assert fe002_reject["status"] == ps.STATUS_MISSING
    print("  FE-002 TrampMetalReject: Missing (dual status, task requirement 3) -- PASSED.")

    print("\n=== FE-003 clip behavior (regression check) ===")
    over = fe003_weighing(lambda k: {"value": {"outlet_kg_h": 60.0}})
    under = fe003_weighing(lambda k: {"value": {"outlet_kg_h": 20.0}})
    assert over["value"]["confirmed_wet_feed_kg_h"] == FE003_MAX_KG_H and over["value"]["clipped"]
    assert under["value"]["confirmed_wet_feed_kg_h"] == FE003_MIN_KG_H and under["value"]["clipped"]
    print(f"  60 kg/h inlet -> clipped to max {FE003_MAX_KG_H} kg/h; 20 kg/h inlet -> clipped to "
          f"min {FE003_MIN_KG_H} kg/h -- PASSED.")

    def _build_full_engine():
        state = sps.SharedPlantState()
        handle = state.new_writer_handle()
        engine = se.SimulationEngine(state)
        ga001.register_ga001(engine)
        gc.register_gc_chain(engine)
        hbchain.register_hb_chain(engine)
        hbrem.register_hb_remaining(engine)
        eu.register_eu_chain(engine)
        register_fe_chain(engine)
        return state, handle, engine

    print("\n=== Task requirement 5: the getter-discipline proof ===")
    print("  ga001_gasifier_model.py's own self-test (run separately, no FE registered) already "
          "proved byte-for-byte IDENTICAL output to pre-Phase-3 when FE-005 is absent -- ga001_model()'s "
          "own body never changed. Now proving the LIVE side: with FE registered, GA-001's own feed "
          "rate genuinely comes from FE-005, with zero changes to ga001_model() itself.")
    state0, handle0, engine0 = _build_full_engine()
    for i in range(3):
        engine0.run_cycle(now=f"2026-09-07T00:{i:02d}:00Z")
    snap0 = state0.get_snapshot()
    feed_rate_entry = snap0[("GA-001-INPUT", "dry_feed_rate_kg_h")]
    print(f"  GA-001-INPUT/dry_feed_rate_kg_h after 3 cycles: {feed_rate_entry['value']:.3f} kg/h "
          f"(model={feed_rate_entry['source']['model']})")
    assert abs(feed_rate_entry["value"] - 37.503) < 0.05, (
        f"REGRESSION: GA-001's own live feed rate ({feed_rate_entry['value']}) doesn't match "
        f"FE-005's own computed dry solids (~37.503 kg/h)."
    )
    assert "fe005" in feed_rate_entry["source"]["model"].lower(), (
        f"REGRESSION: GA-001's own feed-rate entry doesn't credit FE-005 as its real source "
        f"({feed_rate_entry['source']['model']!r})."
    )
    print("  PASSED -- GA-001's own dry_feed_rate_kg_h is now genuinely LIVE from FE-005, ~37.5 kg/h "
          "(down from the Phase 1-2 placeholder's 41.67 kg/h), with ga001_model()'s own body "
          "untouched -- only the SOURCE of the value changed (this module's own docstring has the "
          "full getter-discipline argument).")

    ga_out = snap0[("GA-001", "Outputs")]["value"]
    print(f"  GA-001/Outputs (live, FE-driven): dry_flow={ga_out['dry_flow_nm3_h']:.3f} Nm3/h, "
          f"H2%={ga_out['H2_mol_pct_dry']:.3f}%")

    print("\n=== Task requirement 4: the biggest single propagation test in this project so far ===")
    NEW_DELIVERY_RATE = 45.0  # kg/h, a real, deliberate change, still within FE-003's own
                               # Confirmed [29,50] kg/h range (no clipping confound)

    def _perturbed_delivery(get_input, _v=NEW_DELIVERY_RATE):
        return {"value": _v, "status": ps.STATUS_ASSUMED, "inputs": [], "validation_basis": ps.VALIDATION_NA,
                "confidence_note": "PERTURBATION TEST ONLY."}

    state1, handle1, engine1 = _build_full_engine()
    N_SETTLE = 5
    for i in range(N_SETTLE):
        engine1.run_cycle(now=f"2026-09-07T01:{i:02d}:00Z")
    baseline = state1.get_snapshot()

    engine1._models[("FE-001-INPUT", "msw_delivery_rate_kg_h")]["fn"] = _perturbed_delivery
    N_AFTER = 4  # >= 2 needed: cycle 1 updates FE-001..008 (same-cycle chain), cycle 2 is when
                  # GA-001 first reads FE-005's now-updated value (lagged) and the rest of the
                  # chain (GC/HB/EU) catches up the same cycle -- run a couple more for margin.
    for i in range(N_AFTER):
        engine1.run_cycle(now=f"2026-09-07T02:{i:02d}:00Z")
    perturbed = state1.get_snapshot()

    def _v(snap, key, *path):
        val = snap[key]["value"]
        for p in path:
            val = val[p]
        return val

    print(f"  MSW delivery rate: {FE001_DEFAULT_DELIVERY_RATE_KG_H} kg/h -> {NEW_DELIVERY_RATE} kg/h")
    rows = [
        ("FE-005 dry_solids_kg_h", ("FE-005", "MoistureBalance"), "dry_solids_kg_h"),
        ("GA-001 dry_feed_rate_kg_h", ("GA-001-INPUT", "dry_feed_rate_kg_h")),
        ("GA-001 dry_flow_nm3_h", ("GA-001", "Outputs"), "dry_flow_nm3_h"),
        ("GC-013 dry_flow_nm3_h", ("GC-013", "Gas"), "dry_flow_nm3_h"),
        ("HB-013 level_kg", ("HB-013", "Storage"), "level_kg"),
        ("EU-009 net_kw", ("EU-009", "GridBalance"), "net_kw"),
    ]
    all_changed = True
    for label, key, *path in rows:
        before = _v(baseline, key, *path)
        after = _v(perturbed, key, *path)
        changed = abs(before - after) > 1e-9
        all_changed = all_changed and changed
        print(f"  {label}: {before:.4f} -> {after:.4f}  ({'CHANGED' if changed else 'unchanged'})")
    assert all_changed, (
        "REGRESSION: the FE-001 delivery-rate perturbation did not reach every stage of the chain "
        "(GA-001 -> GC-013 -> HB-013 -> EU-009) -- see the per-row breakdown printed above."
    )
    print("  PASSED -- a change at FE-001 visibly, measurably reaches GA-001's live output, then "
          "GC-013, HB-013's storage level, and EU-009's electrical balance: real end-to-end "
          "propagation through every phase built so far, in one pass.")

    print("\nAll fe_feed_handling.py self-tests PASSED.")
