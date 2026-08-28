"""
Engineering-estimate overlay v3 — PILOTED on FE-001 through FE-008's 21
remaining "Missing Data — Required" gaps first (reviewed and approved),
EXTENDED to GA-001 through GA-010's 29 remaining gaps (reviewed and
approved), now EXTENDED AGAIN to GC-001 through GC-015's 38 remaining
gaps under the identical rule set, no relaxation. Extending to the
remaining three sections (SA, HB, EU, AI) is still a separate, later
task.

WHY THIS EXISTS, per the real, authorized basis stated in the task:
DOK-ING has confirmed they cannot answer some outstanding questions at
this stage, and has authorized proceeding with engineering estimates —
correlations, literature values, comparable installed systems — clearly
distinguished from confirmed data, to be calibrated once the real plant
exists. This is standard FEED-stage practice, and this project already
does it in scattered form: the ER=0.25 air equivalence ratio and 200/150
ppm feed sulfur/chlorine figures (python/uncertainty.py), and the
compressor motor power / drive power estimates already in the equipment
registry itself, are all exactly this kind of thing, just not
previously given a distinct, honest STATUS label of their own.

HARD RULE, same discipline as equipment_rfi_fills.py before it, made
stricter here rather than looser: a gap gets filled ONLY where a real,
STATABLE, DEFENSIBLE basis exists — a named engineering correlation
(e.g. a standard mass-balance conversion), a cited literature source
(a real, standard, checkable reference), or a comparable, actually-
existing installed-equipment-class practice (e.g. "mechanical material-
handling equipment in this class universally operates at ambient
conditions, per standard industrial practice"). NEVER a plausible-
sounding number invented to look complete. Every filled row states its
actual basis in its own remarks — not just a number, "why, citable and
checkable" (task requirement 2). Where no genuine basis exists, the gap
stays "Missing Data — Required" — task requirement 3 is explicit this
is not "fill everything that can technically be filled", it's "fill
only where real engineering justification exists". Of FE's 21 gaps,
7 get a genuine estimate; 14 stay missing. Of GA's 29 gaps, 10 get a
genuine estimate; 19 stay missing. Of GC's 38 gaps, only 7 get a
genuine estimate; 31 stay missing — GC is mostly specific vendor
equipment-performance specs with no literature basis, so a notably
lower fill rate than FE/GA is the CORRECT, honest outcome here, not a
gap in effort — see REPORT below for the per-gap reasoning on every
single one, filled and declined alike, all three sections.

GA-SPECIFIC DISCIPLINE, per the task's explicit instruction: GA's
fills are checked first, and preferentially, for the STRONGEST kind of
estimate — a value computable from GA's OWN already-confirmed numbers
(feed rate, ash/carbon-black mass fractions) via a real mass/energy
balance, rather than looked up externally, since that's internally
consistent with data already confirmed in this project rather than an
outside guess. Every GA mass-flow fill below is computed live from
gasifier_mass_balance.py's own byproduct_mass_flows() (not a separate
hardcoded number), so it can never silently drift out of sync with
that module's own DOK-ING-recalibrated feed rate. Two conflation traps
were watched for specifically and avoided (see GA REPORT below for the
full reasoning): (1) the ALREADY-KNOWN one from equipment_rfi_fills.py
— RFI #2's "Carbon >45%" is FEEDSTOCK ELEMENTAL carbon content, a
fundamentally different metric from gasifier_mass_balance.py's 5%
CARBON-BLACK BYPRODUCT YIELD fraction; no GA fill below uses the RFI's
elemental-carbon figure for anything carbon-black-related. (2) Two
NEW, analogous traps found and avoided in this extension: GA-008's own
stated ">95% collection efficiency" means GA-010's inbound carbon
black is NOT the same figure as the raw carbon-black generation rate
(GA-010's Inputs fill applies the efficiency, doesn't assume 100%
recovery); and GA-009's own stated "Portland cement (5-10% by mass)"
stabilization additive means the aggregate PRODUCT mass is NOT the
same figure as the raw ash mass feeding it (GA-009's Performance
Indicators fill states a mass YIELD factor above 100%, not an
assumed-equal pass-through).

GC-SPECIFIC DISCIPLINE (task requirements 3-5): same "own already-
confirmed numbers first" priority applied to GC's gas-cleaning train.
The train's own real gas-flow chain (GC-001/GC-003 confirm 50 Nm3/h
upstream of the quench tower; GC-009/GC-013 independently confirm the
SAME 50 Nm3/h downstream of it) is used to fill two items that had NO
gas-flow figure of their own (GC-006, GC-012) via cross-item
interpolation between two ALREADY-CONFIRMED bracketing points — never
by re-deriving or asserting anything about the quench tower itself.
Two exact-calculation fills come from a SINGLE item's own confirmed
inlet/outlet concentrations (GC-007 tar removal efficiency, GC-010
dust removal efficiency), the same "derived from confirmed inputs"
pattern as FE-004's specific energy. One fill (GC-008 Operating
Conditions) interpolates a missing temperature between two sequential
scrubbers' own confirmed values. A "compute-then-verify" catch (task
requirement 4) is reported explicitly: GC-004's Outputs (post-quench
gas flow) was checked and DECLINED — unlike the cyclones' trace-
particulate removal or GC-006's trace-tar removal, the quench tower's
own confirmed remarks state a real, non-trivial gas-volume change
("~70% contraction" cooling from 860 to 65 degC) and it is the very
step that generates the condensate GC-015 collects — assuming its
outlet gas flow equals its inlet would rest on an unstated, physically
unsound assumption this project has no confirmed water-vapor/
condensation data to actually calculate, so it stays Missing Data -
Required rather than presenting a number built on that assumption.
Two apparent MISLABELED cross-references were found in the pre-
existing registry remarks while checking for exactly the adjacent-
stage conflation risk task requirement 5 warns about, and are reported
here rather than silently used or silently ignored: GC-007's own
remark attributes its 0.5 g/Nm3 tar inlet figure to "GC-008's bulk
packed-bed removal", but GC-008 is the H2S wet scrubber — GC-006 (the
actual packed-bed tar adsorber) is almost certainly the intended
reference; and GC-012's own remark compares its <0.1 ppm H2S/COS
target against "GC-006's <1 ppm H2S target", but GC-006 is the tar
removal unit — GC-008 (the actual H2S scrubber, whose own confirmed
target is <1 ppm) is almost certainly intended. data/
equipment_registry.json is off-limits to edit (DOK-ING's own static
extract), so neither is fixed here, but no GC fill below relies on
either mislabeled reference — both are flagged, not propagated.

STATUS, DISTINCT FROM BOTH "Confirmed" AND "Missing Data — Required"
(task requirement 1): every row added here carries
"status": equipment_datasheet.STATUS_ESTIMATE
("Engineering Estimate (Not Vendor/DOK-ING Confirmed)") — a third,
genuine status equipment_datasheet.py's own summarize()/slot_status()
now understands natively (see that module's own docstring for the
three-way logic), reported SEPARATELY from Confirmed in the honest
completion percentage, never blended into it (task requirement 4).

PROVENANCE, same "source" field convention as equipment_rfi_fills.py:
every row's "source" names which round it came from (FE pilot, GA
extension, or GC extension) and its basis type, distinct in app.py's UI
from both "Equipment Datasheet" (vendor data) and "DOK-ING RFI
(design_basis.py Q#)" (DOK-ING's real answers) rows.

Does NOT modify data/equipment_registry.json (off-limits, DOK-ING's own
static datasheet extract), equipment_datasheet.py's build_datasheet()
(stays pure, registry-only), or gasifier_mass_balance.py (read from,
never written to — GA's mass-balance-derived fills call its
byproduct_mass_flows() directly rather than re-deriving or hardcoding
the same numbers). apply_estimates() is a separate overlay, deep-
copying its input, exactly the equipment_rfi_fills.py pattern — and
composes with it: app.py applies RFI fills first, then estimates, on
the same datasheets dict, since both only ever touch buckets that were
genuinely empty of real data.

REPORT (task requirement 5 — every one of FE's 21 gaps, filled and
declined, with the actual reasoning):

FILLED — 7 of 21:

  FE-002 (Magnetic & Eddy Current Separator) Operating Conditions:
    Ambient temperature, matching FE-001's own confirmed site ambient
    range (-20 to +50 degC). Basis: comparable-installed-system
    practice — magnetic/eddy-current separation is a purely mechanical/
    electromagnetic process with no heating or cooling unit operation
    involved; no vendor in this equipment class publishes a distinct
    "operating temperature" spec beyond ambient rating, because there
    isn't one to publish. Same-site reasoning: FE-002 sits in the same
    feed-handling area as FE-001, immediately downstream, before any
    heating stage (FE-005) — no reason to assume a different ambient
    range.

  FE-003 (Weighing Conveyor) Operating Conditions: same ambient basis
    and same reasoning as FE-002 — mechanical belt conveying, no
    process heating/cooling, same feed-handling area.

  FE-004 (Shredder / Size Reducer) Operating Conditions: ambient, with
    an honest caveat this item's own remarks don't get for FE-002/003 —
    shredding generates SOME frictional/cutting heat, but this is not a
    controlled process setpoint the way FE-005's dryer temperature is;
    standard practice for two-shaft waste shredders is no active
    thermal control, operating at ambient plus an uncontrolled, minor
    temperature rise.

  FE-004 Performance Indicators: specific energy consumption, 150
    kWh/tonne — an EXACT calculation from this item's own two already-
    CONFIRMED real values (Drive motor power = 15 kW; Throughput
    capacity = 0.1 t/h; 15 / 0.1 = 150), not an independent guess,
    still flagged Estimate rather than Confirmed since DOK-ING/vendor
    has not itself stated a specific-energy figure. Compared against a
    published range: coarse/primary MSW and mixed-waste shredding is
    commonly cited in solid-waste engineering references (e.g.
    Tchobanoglous, Theisen & Vigil, "Integrated Solid Waste Management",
    a standard reference in this field) in the rough range of 10-40
    kWh/tonne at commercial scale. FE-004's derived 150 kWh/tonne sits
    well above that range — reported honestly as consistent with this
    being a small (0.1 t/h), pilot-scale unit, where fixed motor
    overhead dominates specific energy far more than it would at
    commercial throughput, not treated as an error or hidden.

  FE-005 (Feed Dryer) Performance Indicators: typical convective/belt
    dryer thermal efficiency, 50-75%. Basis: a general equipment-class
    range from standard industrial drying literature (e.g. Mujumdar,
    "Handbook of Industrial Drying", a standard reference for this
    equipment type) for convective belt dryers on biomass/solid-waste-
    type duty. Explicitly NOT calculated from FE-005's own specific
    duty — no stated evaporation/heat-duty figure exists in this
    item's own data to calculate from — a general equipment-class
    range only, stated as such, not dressed up as item-specific.

  FE-007 (Feed Screw / Ram Feeder) Outputs: ~37.9 kg/h post-drying feed
    rate. Basis: a named, standard engineering method — wet/dry
    moisture-basis mass-balance conversion — applied to this item's own
    confirmed inputs: the confirmed 41.67 kg/h as-received feed rate
    (DOK-ING RFI Q1, applied upstream at FE-001/GA-001), and FE-005's
    own confirmed inlet moisture (10%) and outlet moisture target
    (<1%, taken as ~1%). Dry-solids mass = 41.67 x (1 - 0.10) =
    37.5 kg/h; post-drying wet mass at ~1% moisture = 37.5 / (1 - 0.01)
    = ~37.9 kg/h. This is a calculation from confirmed inputs via a
    standard, named method, not an independent literature/vendor
    figure — flagged Estimate because DOK-ING has not itself stated
    this specific post-drying flow rate, only the inputs it's
    calculated from.

  FE-008 (Air-lock / Rotary Valve) Outputs: the same ~37.9 kg/h
    post-drying feed rate, same basis as FE-007 — FE-008 is the next
    conveying stage immediately after FE-007, with no further moisture
    change between them, so the same post-drying mass-balance figure
    applies directly.

DECLINED — 14 of 21, with the actual reason (not silently skipped):

  FE-001 Outputs: a receiving hopper's discharge rate for heterogeneous
    MSW is NOT amenable to a standard bulk-solids orifice-flow
    correlation (e.g. Beverloo) the way free-flowing granular solids
    are — MSW bridges/arches, which is explicitly why this item's own
    900x900mm opening is oversized to avoid it (per this item's own
    remarks). The actual discharge rate is a CONTROLLED process
    variable (set by FE-003's downstream metering), not a physical
    correlation output. No defensible estimate exists.
  FE-001 Performance Indicators: this item's own "Live capacity
    (usable)" (1.7 t of 2 t total, 85%) already IS this item's real
    utilization figure, just classified into Parameters by the keyword
    rule, not Performance Indicators — no genuinely NEW, additional
    figure to estimate beyond what's already on file.
  FE-002 Outputs: the actual reject rate (residual tramp metal in an
    already-post-MRF stream) would be a trace fraction with no
    published "typical residual tramp-metal content in post-MRF waste"
    figure this module can cite with any real confidence — too
    source-dependent to state a defensible number.
  FE-002 Measurements: instrument accuracy/calibration is fundamentally
    a VENDOR product spec (already correctly routed to Vendor in
    python/equipment_request_routing.py) — no correlation or literature
    value substitutes for a specific instrument's own delivered
    accuracy before that instrument is selected.
  FE-003 Outputs: a conveyor's own throughput already equals its
    already-confirmed Inputs figure (Nominal feed rate) — no distinct
    NEW Outputs quantity exists to estimate.
  FE-003 Performance Indicators: weighing accuracy is already captured
    (Measurements, real registry data) — no additional, genuinely new
    PI concept for a weighing conveyor beyond that.
  FE-004 Measurements: same vendor-instrument reasoning as FE-002.
  FE-005 Measurements: same vendor-instrument reasoning (moisture-
    sensor accuracy is FE-006's domain anyway, a separate item).
  FE-006 (Moisture Analyser) Inputs and Outputs: this is a non-contact
    optical sensor mounted above a conveyor — it has no physical
    material stream of its own to characterize (structurally not
    applicable, not just undocumented; already established this way in
    python/equipment_rfi_fills.py's own reasoning for this same item).
    No engineering estimate can manufacture a material flow rate for
    equipment that doesn't have one.
  FE-006 Performance Indicators: would just restate this item's own
    already-populated Measurements (accuracy, response time) under a
    different category label — not new information.
  FE-007 Performance Indicators: no genuine additional basis beyond
    what's now in this item's own Outputs.
  FE-008 Measurements: same vendor-instrument reasoning as FE-002/004.
  FE-008 Performance Indicators: same reasoning as FE-007 — nothing
    additional beyond Outputs.

GA REPORT (extension — every one of GA's 29 gaps, filled and declined):

FILLED — 10 of 29:

  GA-005 (Bed Drain / Ash Discharge System) Operating Conditions:
    ~150 degC ash discharge outlet temperature. Basis: CROSS-ITEM
    derivation from this project's own already-confirmed data, not an
    external lookup — GA-006's own confirmed "Char temperature at
    inlet" Parameter (150 degC) explicitly states this figure is the
    ash temperature AFTER GA-005's water-jacketed cooling ("Already
    cooled by GA-005's water-jacketed screw housing"). Since GA-005's
    discharge feeds GA-006's inlet directly (same physical ash stream,
    sequential equipment, no intermediate step), GA-005's own outlet
    operating temperature is the same 150 degC figure GA-006's own data
    already states.

  GA-006 (Char / Ash Conveyor) Outputs: ~4.167 kg/h ash mass flow rate
    to GA-007. Basis: standard mass-balance pass-through — GA-006 is a
    pure mechanical relay (drag chain conveyor) with no separation or
    mass-loss step of its own between GA-005 and GA-007, so mass in =
    mass out. Value = GA-005's own confirmed "10% of feed" ash
    discharge fraction applied to the project's confirmed 41.67 kg/h
    dry feed rate (DOK-ING RFI Q1, gasifier_mass_balance.py) — computed
    live via that module's own byproduct_mass_flows(), not a separate
    hardcoded figure.

  GA-006 Operating Conditions: ~150 degC. Basis: derived from THIS
    item's own two already-confirmed facts — its confirmed "Char
    temperature at inlet" (150 degC) and its own stated remark ("No
    active cooling needed — primary cooling already done at GA-005"),
    which together imply negligible further temperature change across
    the short 4m enclosed run. A synthesis of two existing facts into a
    new quantified claim, not a bare restatement of the inlet figure
    under a different category label.

  GA-007 (Char Collection Bin) Inputs: ~4.167 kg/h ash mass inflow
    rate. Basis: same mass-balance pass-through as GA-006's Outputs —
    GA-007 receives the identical ash stream from GA-006 with no
    intermediate processing step.

  GA-007 Outputs: ~4.167 kg/h ash mass outflow rate to GA-008/GA-009.
    Basis: mass conservation through a buffer vessel on a TIME-AVERAGED
    basis — GA-007's own data states no separation or loss mechanism
    (it is explicitly a buffer/storage bin, "several days' buffer"),
    so its long-run average outflow equals its average inflow, a
    standard steady-state mass-balance principle for buffer/silo
    equipment, not a claim about any single instant.

  GA-008 (Carbon Black Recovery & Classification Unit) Inputs: ~2.084
    kg/h carbon-black-laden fines inflow rate. Basis: the project's own
    established 5% CARBON_BLACK_FRACTION (gasifier_mass_balance.py)
    applied to the confirmed 41.67 kg/h dry feed rate, computed live
    via byproduct_mass_flows() — the same relationship this item's OWN
    registry remarks already reference for its design-capacity margin
    ("~1.88 kg/h nominal... already used in the mass/energy balance"),
    so this is not a new external estimate, just the same internally-
    consistent project figure applied to this item's own missing
    Inputs slot. DELIBERATELY did NOT use RFI #2's "Carbon >45%" figure
    here — that is FEEDSTOCK ELEMENTAL carbon content, a fundamentally
    different metric from this 5% CARBON-BLACK BYPRODUCT YIELD
    fraction (the exact conflation trap equipment_rfi_fills.py already
    identified and avoided; re-confirmed avoided here).

  GA-009 (Ash Aggregate Processing & Packaging Unit) Operating
    Conditions: Ambient. Basis: comparable-installed-system practice —
    this item's own stated process ("Crushing, cement/lime
    stabilization, and screening to size") is standard construction-
    materials practice; cement/lime stabilization is inherently an
    ambient-temperature curing process (no industrial cement
    stabilization process operates at elevated temperature), and
    crushing/screening are unheated mechanical operations — no heating
    or cooling duty is stated or physically implied anywhere in this
    item's own data.

  GA-009 Performance Indicators: aggregate product mass yield, 105-110%
    of input ash mass. Basis: mass-balance calculation from this item's
    OWN confirmed "Leachate stabilization additive = Portland cement
    (5-10% by mass)" Parameter, applied to the confirmed ash mass rate
    (gasifier_mass_balance.py, same as above) — product mass = ash mass
    x (1 + 0.05 to 0.10). DELIBERATELY does NOT assume the aggregate
    product mass equals the raw ash input mass — that would be the
    direct analogue of the RFI carbon-content conflation trap (ignoring
    a real, stated additive/transformation step), so the added cement/
    lime mass is explicitly accounted for rather than assumed away.

  GA-010 (Carbon Black Packaging & Storage Silo) Inputs: >=1.98 kg/h
    recovered carbon-black inflow rate from GA-008. Basis: GA-008's OWN
    confirmed Performance Indicator ("Collection efficiency = >95%")
    applied to the raw carbon-black generation rate (2.084 kg/h, same
    gasifier_mass_balance.py figure as GA-008's own Inputs fill above)
    — GA-010 receives what GA-008 actually RECOVERS, not the raw pre-
    separation fines figure. DELIBERATELY does NOT assume 100% recovery
    from GA-008 to GA-010 — that would be exactly the same category of
    unstated-assumption error as the two conflation traps above, just
    at the recovery-efficiency step instead of the elemental-carbon or
    stabilization-additive step.

  GA-010 Operating Conditions: Ambient (N2-blanketed, inert atmosphere).
    Basis: comparable-installed-system practice — this item's own data
    already states "Vertical silo, N2-blanketed" storage and "Inert gas
    blanketing = Yes"; standard industrial practice for combustible
    fine-particulate storage is ambient-temperature storage under inert
    atmosphere, where the inert gas addresses ignition risk, not
    thermal control — no heating/cooling duty is stated or implied.

DECLINED — 19 of 29, with the actual reason:

  GA-001 (Gasifier Vessel, Reactor) Outputs: no gas-phase gasifier
    model exists anywhere in this project (gasifier_mass_balance.py's
    own docstring: "no gasifier module at all yet... the gasifier
    itself isn't implemented in either language" — that's specifically
    about the GAS-PHASE syngas yield/composition, distinct from that
    same file's solid-phase ash/carbon-black split, which IS used
    above). Syngas yield/composition from air-steam MSW gasification is
    not a simple mass-fraction correlation the way the solid byproducts
    are — it needs a real thermodynamic/kinetic gasifier model this
    project doesn't have. No defensible estimate exists; same
    conclusion equipment_rfi_fills.py already reached checking the same
    gap against real RFI data.

  GA-002 (Gasifier Vessel, Pressure) Inputs, Outputs, Performance
    Indicators: GA-002 is a pressure-containment/instrumentation sub-
    item describing the SAME physical reactor GA-001 already covers —
    it has no distinct material feed or product stream of its own to
    characterize (structurally not a fit, the same reasoning already
    established for FE-006 in equipment_rfi_fills.py, not just
    undocumented). No defensible Performance Indicator exists either —
    its only numeric KPI-like concept (transmitter accuracy) is already
    captured under Measurements.

  GA-003 (Air/Steam Injection, Flow) Outputs: GA-003 is a pass-through
    injection system — the air/steam it receives as its own confirmed
    Inputs is the SAME stream it delivers onward into the reactor, with
    no transformation of its own. Filling Outputs would just restate
    the already-confirmed Inputs figures in different units/combined
    form, not genuinely new information — the same "recategorizing
    existing data, not adding new information" reasoning
    equipment_rfi_fills.py already applied to HB-008/HB-012.

  GA-003 Operating Conditions: this item's own air-preheat/steam-
    temperature/pressure figures are already fully stated as DESIGN
    values under Parameters. Unlike GA-001 (which has BOTH an explicit
    Design temperature AND a separately confirmed "Operating
    temperature (typical)" — a real, stated design-vs-operating
    margin), GA-003 has no separate confirmed "typical operating point"
    distinct from its design value anywhere. Assuming operating=design
    here would be an unstated assumption this project doesn't make
    elsewhere for equipment that DOES have both figures on record —
    declined rather than force the assumption.

  GA-003 Performance Indicators: no defensible correlation or
    literature figure exists for air/steam injection flow-system
    performance beyond what's already captured (ER=0.25 in Parameters,
    flow-meter specs in Measurements).

  GA-004 (Air/Steam Injection, Temp) Inputs, Outputs: same structural
    reasoning as GA-002 — GA-004 is a temperature/pressure sub-item of
    the SAME physical injection system GA-003 already covers with its
    own confirmed Inputs (air/steam flow rates); no distinct material
    stream of its own.

  GA-004 Operating Conditions: same design-vs-operating reasoning as
    GA-003 — only design values exist for this item, no separately
    confirmed operating point to distinguish from design.

  GA-004 Performance Indicators: no defensible correlation exists.

  GA-005 Performance Indicators: CHECKED, not just skipped — a specific
    conveying-energy figure was computed (Drive motor power 1.1 kW /
    ash mass rate 4.167 kg/h = ~264 kWh/tonne) and cross-checked against
    typical bulk-material-handling literature (e.g. CEMA-type screw/
    conveyor specific-energy guidance), which puts short-run bulk
    conveying at a few kWh/tonne, one to two orders of magnitude below
    the computed figure. Unlike FE-004's specific-energy fill (which
    landed inside its literature comparison range, just at the high end
    for a small unit), this number FAILS its own literature cross-
    check — strong evidence the confirmed motor power is torque/jam-
    margin sized, not matched to continuous duty at this small ash
    flow. Presenting it as a specific-energy Performance Indicator
    would be misleading, not a genuine equipment-performance metric —
    declined on that basis, not overlooked.

  GA-006 Performance Indicators: same conveying-energy check as GA-005
    (Drive motor power 0.55 kW / 4.167 kg/h = ~132 kWh/tonne) — same
    literature-mismatch conclusion, same decline reasoning.

  GA-007 Operating Conditions: no defensible quantifiable basis. This
    item's own data states insulation "retains residual warmth" over a
    multi-day buffer residence, but quantifying the actual temperature
    after days of passive heat loss would require real thermal data
    (bin surface area, insulation R-value, ambient temperature) this
    project doesn't have — an actual heat-loss calculation, not a
    correlation or comparable-system estimate, is out of scope for this
    module's discipline.

  GA-007 Performance Indicators: no throughput/efficiency concept
    applies to a passive buffer bin beyond what's already stated
    qualitatively ("several days' buffer" — no numeric residence time
    is even on file to build a KPI from).

  GA-008 Measurements: instrument spec (particle-size/dust/flow sensor)
    is fundamentally a VENDOR product spec — same reasoning as FE's
    Measurements declines; no correlation or literature value
    substitutes for a specific instrument's own delivered spec before
    one is selected.

  GA-009 Measurements: same vendor-instrument reasoning — no literature
    figure exists for a specific leachate-compliance or process sensor
    before a vendor/model is chosen.

  GA-010 Measurements: same vendor-instrument reasoning as GA-008/009.

  GA-010 Performance Indicators: no defensible KPI beyond what's
    already stated (product grade target, moisture content) — a
    storage/loadout system has no additional literature-derivable
    efficiency or recovery-rate concept to estimate.

GC REPORT (extension — every one of GC's 38 gaps, filled and declined).
GC is mostly specific equipment-performance specs (cut sizes, removal
efficiencies, instrument accuracies) that only exist once a vendor/
model is chosen — a notably lower fill rate than FE/GA is the correct,
honest outcome, not a shortfall in effort:

FILLED — 7 of 38:

  GC-006 (Tar Removal Unit) Inputs and Outputs: ~50 Nm3/h gas flow
    rate, both directions. Basis: cross-item interpolation between two
    ALREADY-CONFIRMED bracketing points in this exact train — GC-003's
    own confirmed 50 Nm3/h (upstream, pre-quench) and GC-009's/
    GC-013's own confirmed 50 Nm3/h (downstream, post-quench) — GC-009
    and GC-013 EACH independently state this figure "matches the [flow
    rate/gas flow] established through the rest/entire gas cleaning
    train," so this is the project's own already-established
    convention for the whole downstream segment GC-006 sits inside of,
    not a number this module invented. Physically supported further by
    GC-006 being isothermal (its own confirmed Operating temperature
    matches GC-004's quench outlet exactly) and removing only a trace
    tar mass fraction — no meaningful gas-volume change of its own,
    unlike the quench tower (see GC-004 DECLINED below).

  GC-007 (Wet Scrubber, Tar) Performance Indicators: tar removal
    efficiency, >=90%. Basis: EXACT calculation from this item's own
    two already-CONFIRMED values — Tar inlet concentration (design,
    0.5 g/Nm3 = 500 mg/Nm3) and Tar outlet concentration (target,
    <50 mg/Nm3): (500-50)/500 = 90%, stated as a floor since the
    outlet figure is itself an upper-bound target, not a point value.
    Same "derived from this item's own confirmed inputs" pattern as
    FE-004's specific energy. Consistent with published wet-scrubber
    tar-polishing performance (single-stage water/venturi scrubbers
    commonly cited in gasification tar-removal literature in the
    80-95% range for a polishing duty following bulk upstream removal)
    — the derived 90%+ sits inside that range, not flagged as an
    outlier the way FE-004's was.

  GC-008 (Wet Scrubber, H2S) Operating Conditions: ~55-60 degC. Basis:
    interpolation between two ALREADY-CONFIRMED bracketing values on
    either side of this item in the train sequence (tar scrubber ->
    H2S scrubber -> HCl scrubber, per the three items' own names) —
    GC-007's own confirmed 60 degC operating temperature (immediately
    upstream) and GC-009's own confirmed 55 degC operating temperature
    (immediately downstream), which GC-009's own remark explicitly
    describes as continuing "the gradual cooling trend" already
    documented at every other stage in this train. A range, not a
    false-precision point value, since this is an interpolation
    between two real values, not a direct measurement or calculation.

  GC-010 (Bag Filter, Dust) Performance Indicators: dust removal
    efficiency, >=98.3%. Basis: EXACT calculation from this item's own
    two already-CONFIRMED values — Inlet dust loading (300 mg/Nm3) and
    Outlet dust loading (design, <5 mg/Nm3): (300-5)/300 = 98.33%,
    stated as a floor for the same upper-bound-target reason as
    GC-007. Consistent with published pulse-jet/PTFE-membrane baghouse
    filtration literature, which commonly cites >99% removal at this
    equipment class — this item's derived 98.3%+ sits just below that
    typical high end, plausible given its comparatively generous
    <5 mg/Nm3 outlet target (not an ultra-tight <1 mg/Nm3 spec).

  GC-012 (Activated Carbon Filter) Inputs and Outputs: ~50 Nm3/h gas
    flow rate, both directions. Basis: same cross-item interpolation
    as GC-006 — GC-012 sits between the bag filter (GC-010/GC-011) and
    the blower (GC-013), both fully downstream of the quench tower,
    bracketed on the flow-confirmed side by GC-009's and GC-013's own
    stated figures without needing to touch the quench-tower question
    at all.

DECLINED — 31 of 38, with the actual reason (not silently skipped):

  GC-001 (Primary Cyclone, Temp) Outputs: this item's own confirmed
    Inputs ALREADY states "Design gas flow rate = 50 Nm3/h" — an
    Outputs value restating the identical figure for the identical
    item (cyclones don't meaningfully change gas volume by removing
    trace particulate) would be recategorizing existing data, not
    genuinely new information, the same discipline the FE pilot
    already applied to FE-003's Outputs (a conveyor's throughput
    equals its own confirmed Inputs). GC-001 Operating Conditions: no
    separately confirmed "typical operating" point distinct from this
    item's own DESIGN temperature values exists — unlike GA-001, which
    has both a Design temperature AND a separately confirmed Operating
    temperature (typical), establishing a real margin; assuming
    operating=design here would be the same unstated assumption
    already declined for GA-003/GA-004. GC-001 Performance Indicators:
    the collection-efficiency figure for THIS physical cyclone is
    already Confirmed, just attributed to GC-002 (the ΔP/instrument
    sub-item of the same equipment) — no distinct new PI exists for
    GC-001 itself.

  GC-002 (Primary Cyclone, ΔP) Inputs, Outputs: GC-002 is the pressure-
    instrumentation sub-item of the SAME physical cyclone GC-001
    already covers with its own confirmed Inputs — no distinct
    material stream of its own (structurally not a fit, the same
    reasoning already applied to GA-002/GA-004).

  GC-003 (Secondary Cyclone) Outputs: same recategorization reasoning
    as GC-001 — this item's own confirmed Inputs already states
    "Design gas flow rate = 50 Nm3/h." GC-003 Measurements: vendor-
    only instrument spec (temperature/pressure sensor), no correlation
    or literature figure substitutes for a specific instrument before
    one is selected. GC-003 Operating Conditions: same "no separately
    confirmed operating-vs-design point" reasoning as GC-001 — this
    item's own inlet gas temperature (870 degC) is already Confirmed
    under Inputs; restating it under Operating Conditions would be the
    same recategorization the FE pilot's HB-008 precedent already
    declines.

  GC-004 (Quench Tower, Temp) Outputs: CHECKED with an actual physical
    argument, not just skipped — see the GC-SPECIFIC DISCIPLINE section
    above for the full compute-then-verify reasoning (task requirement
    4). Unlike the cyclones or GC-006, the quench tower's own confirmed
    remarks state a real, non-trivial gas-volume change from cooling
    ("~70% contraction"), and this is the exact stage that generates
    the condensate GC-015 collects — a genuine compositional/molar-flow
    change, not a units artifact, that this project has no confirmed
    water-vapor data to actually calculate. GC-004 Operating
    Conditions: same no-separate-operating-point reasoning as GC-001/
    GC-003. GC-004 Performance Indicators: no standard, checkable
    "quench efficiency" metric exists the way collection/removal
    efficiency does for filters/scrubbers — a real one (e.g. approach
    to adiabatic saturation temperature) would need wet-bulb data this
    project doesn't have.

  GC-005 (Quench Tower, Water) Inputs, Outputs: this item's own
    Parameters ALREADY state "Water consumption (design) = 0.5 m3/h"
    and "Blowdown rate = 0.05 m3/h" — filling Inputs/Outputs with the
    identical already-Confirmed figures for the identical item would
    be recategorization, not new information, same FE-003/GC-001
    precedent. GC-005 Performance Indicators: no defensible KPI exists
    for a passive quench-water supply subsystem beyond what's already
    stated.

  GC-006 Measurements: vendor-only instrument spec (no tar-breakthrough
    sensor type stated anywhere to estimate from). GC-006 Performance
    Indicators: CHECKED, not skipped — this item has no confirmed
    INLET tar concentration of its own to compute a removal efficiency
    from (only its approximate OUTLET, inferred from GC-007's confirmed
    Inputs — see the MISLABELED cross-reference flagged in the GC-
    SPECIFIC DISCIPLINE section above); estimating a raw inlet tar
    loading from external literature would be too wide-ranging (raw
    MSW-gasification tar loadings commonly cited across 1-100+ g/Nm3
    depending on gasifier type/temperature) to state with any real
    confidence for this specific project — declined rather than
    guessed.

  GC-009 (HCl Scrubber) Measurements: vendor-only instrument spec (HCl
    analyser type/model not yet selected).

  GC-011 (Bag Filter, ΔP) Inputs, Outputs: same structural reasoning as
    GC-002/GC-014 — GC-011 is the pressure-drop/cleaning-cycle sub-item
    of the SAME physical bag filter GC-010 already covers with its own
    confirmed Inputs/Outputs (dust loading); no distinct material
    stream of its own. GC-011 Performance Indicators: the dust-removal-
    efficiency figure for THIS physical bag filter is filled above,
    correctly attributed to GC-010 (which holds the actual inlet/
    outlet dust-loading data) — no distinct new PI exists for GC-011
    itself.

  GC-012 Performance Indicators: CHECKED, not skipped — same reasoning
    as GC-006's decline: no confirmed INLET H2S/COS concentration
    exists for this item to compute a removal efficiency from, only an
    OUTLET target (see the second MISLABELED cross-reference flagged in
    the GC-SPECIFIC DISCIPLINE section above).

  GC-013 (Gas Blower, Flow) Outputs: same recategorization reasoning as
    GC-001/GC-003/GC-005 — this item's own confirmed Inputs already
    states the design/min/max gas flow rates; a blower doesn't consume
    or generate gas, so an Outputs figure would restate the identical
    already-Confirmed numbers for the identical item. GC-013 Operating
    Conditions: no separately confirmed operating-vs-design point.
    GC-013 Performance Indicators: no defensible KPI beyond the flow/
    pressure figures already stated.

  GC-014 (Gas Blower, Pressure) Inputs, Outputs: same structural
    reasoning as GC-002/GC-011 — pressure-instrumentation sub-item of
    the SAME physical blower GC-013 already covers. GC-014 Operating
    Conditions: no separately confirmed operating-vs-design point.
    GC-014 Performance Indicators: no defensible KPI.

  GC-015 (Condensate Tank) Outputs: this item's own Inputs already
    states "Pump flow rate = 0.5 m3/h" (the discharge-pump rate, swept
    into Inputs by the same keyword-classification quirk that affects
    a few other items across this project, not something in scope to
    fix here) — filling Outputs with the identical figure would be the
    same recategorization already declined elsewhere. GC-015 Operating
    Conditions: no defensible basis — this tank collects a MIXTURE of
    several different blowdown streams (GC-005 quench blowdown plus
    scrubber blowdowns) at different confirmed temperatures, in
    unstated relative proportions; computing a meaningful mixed
    temperature would need flow-weighting data this project doesn't
    have. GC-015 Performance Indicators: no efficiency/recovery-rate
    concept applies to a passive buffer tank.
"""
import copy

from . import equipment_datasheet
from . import gasifier_mass_balance

_Q = equipment_datasheet
_GA_FLOWS = gasifier_mass_balance.byproduct_mass_flows()
_GA_ASH_KG_H = _GA_FLOWS["ash_kg_h"]
_GA_CARBON_BLACK_KG_H = _GA_FLOWS["carbon_black_kg_h"]
_GA_RECOVERED_CARBON_BLACK_KG_H = 0.95 * _GA_CARBON_BLACK_KG_H  # GA-008's own confirmed ">95%" collection-efficiency floor


def _source(basis_label):
    return f"Engineering estimate (FE-001..FE-008 pilot) — {basis_label}"


def _source_ga(basis_label):
    return f"Engineering estimate (GA-001..GA-010 extension) — {basis_label}"


def _source_gc(basis_label):
    return f"Engineering estimate (GC-001..GC-015 extension) — {basis_label}"


_GC_TRAIN_GAS_FLOW_NM3_H = 50  # GC-003's/GC-009's/GC-013's own independently confirmed design gas flow rate, held constant across the whole downstream train per those items' own remarks


# {item_id: {category: [ {parameter, value, unit, remarks, status, source} ]}}
# Every row targets a category verified genuinely empty of real data in
# the self-test below (same hard safety check as equipment_rfi_fills.py
# — refuses to overwrite real vendor/DOK-ING data with an estimate).
ESTIMATE_FILLS = {
    "FE-002": {
        "Operating Conditions": [
            {
                "parameter": "Estimated operating temperature",
                "value": "-20 to +50", "unit": "°C",
                "remarks": (
                    "Comparable-installed-system basis: magnetic/eddy-current separation is a "
                    "purely mechanical/electromagnetic process with no heating or cooling unit "
                    "operation involved — standard industrial practice for this equipment class "
                    "is ambient-only operation (no vendor publishes a distinct operating-"
                    "temperature spec because there isn't one). Matches FE-001's own confirmed "
                    "site ambient range — same feed-handling area, upstream of any heating stage."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source("comparable-installed-system practice (ambient-only mechanical equipment)"),
            },
        ],
    },
    "FE-003": {
        "Operating Conditions": [
            {
                "parameter": "Estimated operating temperature",
                "value": "-20 to +50", "unit": "°C",
                "remarks": (
                    "Comparable-installed-system basis: mechanical belt conveying, same as "
                    "FE-002 — no process heating/cooling, no controlled operating temperature. "
                    "Matches FE-001's/FE-002's confirmed site ambient range, same feed-handling "
                    "area upstream of any heating stage."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source("comparable-installed-system practice (ambient-only mechanical equipment)"),
            },
        ],
    },
    "FE-004": {
        "Operating Conditions": [
            {
                "parameter": "Estimated operating temperature",
                "value": "-20 to +50 (plus minor frictional/cutting heat rise, uncontrolled)", "unit": "°C",
                "remarks": (
                    "Comparable-installed-system basis: standard practice for two-shaft MSW/"
                    "mixed-waste shredders is no active thermal control — operation at ambient "
                    "plus an uncontrolled, minor frictional/cutting heat rise, unlike FE-005's "
                    "dryer, which has an actual controlled process temperature. Base ambient "
                    "range matches FE-001/FE-002/FE-003's confirmed site conditions."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source("comparable-installed-system practice (unheated mechanical shredding equipment)"),
            },
        ],
        "Performance Indicators": [
            {
                "parameter": "Estimated specific energy consumption",
                "value": "150", "unit": "kWh/tonne",
                "remarks": (
                    "Exact calculation from this item's own two already-CONFIRMED real values: "
                    "Drive motor power (15 kW) / Throughput capacity (0.1 t/h) = 150 kWh/t — not "
                    "an independent guess, but flagged Estimate since no vendor/DOK-ING source "
                    "states a specific-energy figure directly. For context: coarse/primary MSW "
                    "and mixed-waste shredding is commonly cited in solid-waste engineering "
                    "references (e.g. Tchobanoglous, Theisen & Vigil, \"Integrated Solid Waste "
                    "Management\") in the rough range of 10-40 kWh/tonne at commercial scale — "
                    "this item's derived 150 kWh/t sits well above that, consistent with FE-004 "
                    "being a small, pilot-scale (0.1 t/h) unit where fixed motor overhead "
                    "dominates specific energy far more than at commercial throughput, not "
                    "treated as an error."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source("calculated from this item's own confirmed motor power and throughput, compared against published literature range"),
            },
        ],
    },
    "FE-005": {
        "Performance Indicators": [
            {
                "parameter": "Typical thermal efficiency (equipment class)",
                "value": "50-75", "unit": "%",
                "remarks": (
                    "General equipment-class range from standard industrial drying literature "
                    "(e.g. Mujumdar, \"Handbook of Industrial Drying\") for convective belt "
                    "dryers on biomass/solid-waste-type duty. Explicitly NOT calculated from "
                    "this item's own specific duty — no stated evaporation/heat-duty figure "
                    "exists in this item's own data to calculate from — a general equipment-"
                    "class range only, not dressed up as item-specific."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source("published literature range for the equipment class (convective belt dryers)"),
            },
        ],
    },
    "FE-007": {
        "Outputs": [
            {
                "parameter": "Estimated post-drying feed rate",
                "value": "~37.9", "unit": "kg/h",
                "remarks": (
                    "Standard, named engineering method: wet/dry moisture-basis mass-balance "
                    "conversion, applied to this item's own confirmed inputs. Dry-solids mass = "
                    "41.67 kg/h (confirmed as-received feed rate, DOK-ING RFI Q1) x (1 - 0.10) "
                    "(FE-005's confirmed inlet moisture) = 37.5 kg/h. Post-drying wet mass at "
                    "FE-005's confirmed outlet moisture target (<1%, taken as ~1%) = "
                    "37.5 / (1 - 0.01) = ~37.9 kg/h. A calculation from confirmed inputs via a "
                    "standard method, not an independent literature/vendor figure — flagged "
                    "Estimate since DOK-ING has not itself stated this specific post-drying rate, "
                    "only the inputs it's calculated from."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source("standard moisture-basis mass-balance conversion from this item's own confirmed inputs"),
            },
        ],
    },
    "FE-008": {
        "Outputs": [
            {
                "parameter": "Estimated post-drying feed rate",
                "value": "~37.9", "unit": "kg/h",
                "remarks": (
                    "Same basis and figure as FE-007's own estimated post-drying feed rate — "
                    "FE-008 is the next conveying stage immediately after FE-007, with no "
                    "further moisture change between them, so the same mass-balance result "
                    "applies directly."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source("standard moisture-basis mass-balance conversion, same as FE-007"),
            },
        ],
    },
    "GA-005": {
        "Operating Conditions": [
            {
                "parameter": "Estimated ash discharge outlet temperature",
                "value": "~150", "unit": "°C",
                "remarks": (
                    "Cross-item derivation from this project's own already-confirmed data: "
                    "GA-006's own confirmed 'Char temperature at inlet' Parameter (150°C) "
                    "explicitly states this figure is the ash temperature AFTER GA-005's water-"
                    "jacketed cooling ('Already cooled by GA-005's water-jacketed screw housing'). "
                    "Since GA-005's discharge feeds GA-006's inlet directly — same physical ash "
                    "stream, sequential equipment, no intermediate step — GA-005's own outlet "
                    "operating temperature is the same 150°C figure."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source_ga("cross-item derivation from GA-006's own confirmed inlet temperature and stated cooling-completion remark"),
            },
        ],
    },
    "GA-006": {
        "Outputs": [
            {
                "parameter": "Estimated ash mass flow rate (to GA-007)",
                "value": f"~{_GA_ASH_KG_H:.3f}", "unit": "kg/h",
                "remarks": (
                    f"Standard mass-balance pass-through: GA-006 is a pure mechanical relay (drag "
                    f"chain conveyor) with no separation or mass-loss step of its own between "
                    f"GA-005 and GA-007, so mass in = mass out. Value = GA-005's own confirmed "
                    f"'10% of feed' ash discharge fraction applied to the project's confirmed "
                    f"41.67 kg/h dry feed rate (DOK-ING RFI Q1) — computed live via "
                    f"gasifier_mass_balance.py's own byproduct_mass_flows() ({_GA_ASH_KG_H:.4f} "
                    f"kg/h), not a separately hardcoded figure."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source_ga("mass-balance pass-through of GA-005's confirmed ash discharge fraction, computed live via gasifier_mass_balance.py"),
            },
        ],
        "Operating Conditions": [
            {
                "parameter": "Estimated conveyor operating temperature",
                "value": "~150", "unit": "°C",
                "remarks": (
                    "Derived from this item's own two already-confirmed facts: its confirmed "
                    "'Char temperature at inlet' (150°C) and its own stated remark ('No active "
                    "cooling needed — primary cooling already done at GA-005'), which together "
                    "imply negligible further temperature change across the short 4m enclosed run "
                    "— a synthesis of two existing facts into a new quantified claim, not a bare "
                    "restatement of the inlet figure under a different category label."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source_ga("derived from this item's own confirmed inlet temperature and stated 'no active cooling' remark"),
            },
        ],
    },
    "GA-007": {
        "Inputs": [
            {
                "parameter": "Estimated ash mass inflow rate (from GA-006)",
                "value": f"~{_GA_ASH_KG_H:.3f}", "unit": "kg/h",
                "remarks": (
                    "Same mass-balance pass-through as GA-006's estimated Outputs — GA-007 "
                    "receives the identical ash stream from GA-006 with no intermediate "
                    "processing step."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source_ga("mass-balance pass-through, same basis as GA-006's estimated Outputs"),
            },
        ],
        "Outputs": [
            {
                "parameter": "Estimated ash mass outflow rate (to GA-008/GA-009)",
                "value": f"~{_GA_ASH_KG_H:.3f}", "unit": "kg/h",
                "remarks": (
                    "Mass conservation through a buffer vessel on a TIME-AVERAGED basis — GA-007's "
                    "own data states no separation or loss mechanism (it is explicitly a buffer/"
                    "storage bin, 'several days' buffer'), so its long-run average outflow equals "
                    "its average inflow — a standard steady-state mass-balance principle for "
                    "buffer/silo equipment, not a claim about any single instant."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source_ga("time-averaged mass-balance conservation through a buffer vessel with no stated separation/loss mechanism"),
            },
        ],
    },
    "GA-008": {
        "Inputs": [
            {
                "parameter": "Estimated carbon-black-laden fines inflow rate",
                "value": f"~{_GA_CARBON_BLACK_KG_H:.3f}", "unit": "kg/h",
                "remarks": (
                    f"The project's own established 5% carbon-black byproduct-yield fraction "
                    f"(gasifier_mass_balance.py CARBON_BLACK_FRACTION) applied to the confirmed "
                    f"41.67 kg/h dry feed rate, computed live via byproduct_mass_flows() "
                    f"({_GA_CARBON_BLACK_KG_H:.4f} kg/h) — the same relationship this item's OWN "
                    f"registry remarks already reference for its design-capacity margin ('~1.88 "
                    f"kg/h nominal... already used in the mass/energy balance'), so this is not a "
                    f"new external estimate, just the same internally-consistent project figure "
                    f"applied to this item's own missing Inputs slot. DELIBERATELY did NOT use "
                    f"RFI #2's 'Carbon >45%' figure here — that is FEEDSTOCK ELEMENTAL carbon "
                    f"content, a fundamentally different metric from this 5% CARBON-BLACK "
                    f"BYPRODUCT YIELD fraction (the exact conflation trap "
                    f"equipment_rfi_fills.py already identified and avoided; re-confirmed avoided "
                    f"here)."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source_ga("carbon-black mass-balance fraction computed live via gasifier_mass_balance.py, deliberately NOT the RFI's unrelated feedstock elemental-carbon figure"),
            },
        ],
    },
    "GA-009": {
        "Operating Conditions": [
            {
                "parameter": "Estimated processing temperature",
                "value": "Ambient", "unit": "",
                "remarks": (
                    "Comparable-installed-system basis: this item's own stated process "
                    "('Crushing, cement/lime stabilization, and screening to size') is standard "
                    "construction-materials practice — cement/lime stabilization is inherently an "
                    "ambient-temperature curing process (no industrial cement stabilization "
                    "process operates at elevated temperature), and crushing/screening are "
                    "unheated mechanical operations. No heating or cooling duty is stated or "
                    "physically implied anywhere in this item's own data."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source_ga("comparable-installed-system practice (ambient-temperature cement/lime stabilization and aggregate processing)"),
            },
        ],
        "Performance Indicators": [
            {
                "parameter": "Estimated aggregate product mass yield (vs. input ash mass)",
                "value": "105-110", "unit": "%",
                "remarks": (
                    "Mass-balance calculation from this item's OWN confirmed 'Leachate "
                    "stabilization additive = Portland cement (5-10% by mass)' Parameter, applied "
                    "to the confirmed ash mass rate (gasifier_mass_balance.py, same basis as "
                    "GA-006/GA-007's estimated ash flows) — product mass = ash mass x (1 + 0.05 to "
                    "0.10). DELIBERATELY does NOT assume the aggregate product mass equals the raw "
                    "ash input mass — that would be the direct analogue of the RFI carbon-content "
                    "conflation trap (ignoring a real, stated additive/transformation step), so the "
                    "added cement/lime mass is explicitly accounted for rather than assumed away."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source_ga("mass-balance yield calculation from this item's own confirmed stabilization-additive fraction, explicitly not assuming output equals input ash mass"),
            },
        ],
    },
    "GA-010": {
        "Inputs": [
            {
                "parameter": "Estimated recovered carbon-black inflow rate (from GA-008)",
                "value": f">={_GA_RECOVERED_CARBON_BLACK_KG_H:.2f}", "unit": "kg/h",
                "remarks": (
                    f"GA-008's OWN confirmed Performance Indicator ('Collection efficiency = "
                    f">95%') applied to the raw carbon-black generation rate "
                    f"({_GA_CARBON_BLACK_KG_H:.4f} kg/h, same gasifier_mass_balance.py figure as "
                    f"GA-008's own estimated Inputs) — GA-010 receives what GA-008 actually "
                    f"RECOVERS, not the raw pre-separation fines figure. DELIBERATELY does NOT "
                    f"assume 100% recovery from GA-008 to GA-010 — that would be exactly the same "
                    f"category of unstated-assumption error as the elemental-carbon and "
                    f"stabilization-additive conflation traps above, just at the recovery-"
                    f"efficiency step instead."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source_ga("mass-balance calculation applying GA-008's own confirmed >95% collection efficiency to the raw carbon-black generation rate, deliberately not assuming 100% recovery"),
            },
        ],
        "Operating Conditions": [
            {
                "parameter": "Estimated storage temperature",
                "value": "Ambient (N2-blanketed, inert atmosphere)", "unit": "",
                "remarks": (
                    "Comparable-installed-system basis: this item's own data already states "
                    "'Vertical silo, N2-blanketed' storage and 'Inert gas blanketing = Yes' — "
                    "standard industrial practice for combustible fine-particulate storage is "
                    "ambient-temperature storage under inert atmosphere, where the inert gas "
                    "addresses ignition risk, not thermal control. No heating/cooling duty is "
                    "stated or implied."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source_ga("comparable-installed-system practice (ambient-temperature inert-blanketed storage for combustible fine particulate)"),
            },
        ],
    },
    "GC-006": {
        "Inputs": [
            {
                "parameter": "Estimated inlet gas flow rate",
                "value": f"~{_GC_TRAIN_GAS_FLOW_NM3_H}", "unit": "Nm³/h",
                "remarks": (
                    "Cross-item interpolation between two ALREADY-CONFIRMED bracketing points in "
                    "this exact train: GC-003's own confirmed 50 Nm³/h (upstream, pre-quench) and "
                    "GC-009's/GC-013's own confirmed 50 Nm³/h (downstream, post-quench), which "
                    "GC-009 and GC-013 EACH independently state 'matches the flow rate established "
                    "through the rest/entire gas cleaning train' — the project's own already-"
                    "established convention for the whole downstream segment GC-006 sits inside "
                    "of. Supported further by GC-006 being isothermal (its own confirmed Operating "
                    "temperature matches GC-004's quench outlet exactly) and removing only a trace "
                    "tar mass fraction — no meaningful gas-volume change of its own, unlike the "
                    "quench tower itself (see GC-004, deliberately declined for this reason)."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source_gc("cross-item interpolation between GC-003's and GC-009's/GC-013's own confirmed downstream gas flow figures"),
            },
        ],
        "Outputs": [
            {
                "parameter": "Estimated outlet gas flow rate",
                "value": f"~{_GC_TRAIN_GAS_FLOW_NM3_H}", "unit": "Nm³/h",
                "remarks": (
                    "Same basis as this item's own estimated Inputs — isothermal, trace-tar-"
                    "removal-only operation with no meaningful gas-volume change, consistent with "
                    "the project's own already-confirmed downstream train gas flow (GC-009, "
                    "GC-013)."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source_gc("cross-item interpolation, same basis as this item's estimated Inputs"),
            },
        ],
    },
    "GC-007": {
        "Performance Indicators": [
            {
                "parameter": "Estimated tar removal efficiency",
                "value": ">=90", "unit": "%",
                "remarks": (
                    "Exact calculation from this item's own two already-CONFIRMED values: Tar "
                    "inlet concentration (design, 0.5 g/Nm³ = 500 mg/Nm³) and Tar outlet "
                    "concentration (target, <50 mg/Nm³): (500-50)/500 = 90%, stated as a floor "
                    "since the outlet figure is itself an upper-bound target, not a point value. "
                    "Not an independent guess, flagged Estimate since no vendor/DOK-ING source "
                    "states this removal-efficiency figure directly. For context: single-stage "
                    "wet/venturi scrubbers used for tar polishing (following bulk upstream "
                    "removal) are commonly cited in gasification tar-removal literature in the "
                    "80-95% range for this duty — this item's derived 90%+ sits inside that range."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source_gc("calculated from this item's own confirmed inlet/outlet tar concentrations, compared against published literature range"),
            },
        ],
    },
    "GC-008": {
        "Operating Conditions": [
            {
                "parameter": "Estimated operating temperature",
                "value": "55-60", "unit": "°C",
                "remarks": (
                    "Interpolation between two ALREADY-CONFIRMED bracketing values on either side "
                    "of this item in the train sequence (tar scrubber -> H2S scrubber -> HCl "
                    "scrubber, per the three items' own names): GC-007's own confirmed 60°C "
                    "operating temperature (immediately upstream) and GC-009's own confirmed 55°C "
                    "operating temperature (immediately downstream), which GC-009's own remark "
                    "explicitly describes as continuing 'the gradual cooling trend' documented at "
                    "every other stage in this train. A range, not a false-precision point value, "
                    "since this is an interpolation between two real values, not a direct "
                    "measurement or calculation."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source_gc("interpolation between GC-007's and GC-009's own confirmed operating temperatures, bracketing this item in the train sequence"),
            },
        ],
    },
    "GC-010": {
        "Performance Indicators": [
            {
                "parameter": "Estimated dust removal efficiency",
                "value": ">=98.3", "unit": "%",
                "remarks": (
                    "Exact calculation from this item's own two already-CONFIRMED values: Inlet "
                    "dust loading (300 mg/Nm³) and Outlet dust loading (design, <5 mg/Nm³): "
                    "(300-5)/300 = 98.33%, stated as a floor for the same upper-bound-target "
                    "reason as GC-007. For context: pulse-jet, PTFE-membrane baghouse filtration "
                    "is commonly cited in industrial filtration literature as achieving >99% "
                    "removal at this equipment class — this item's derived 98.3%+ sits just below "
                    "that typical high end, plausible given its comparatively generous <5 mg/Nm³ "
                    "outlet target (not an ultra-tight <1 mg/Nm³ spec)."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source_gc("calculated from this item's own confirmed inlet/outlet dust loading, compared against published literature range"),
            },
        ],
    },
    "GC-012": {
        "Inputs": [
            {
                "parameter": "Estimated inlet gas flow rate",
                "value": f"~{_GC_TRAIN_GAS_FLOW_NM3_H}", "unit": "Nm³/h",
                "remarks": (
                    "Same cross-item interpolation basis as GC-006's estimated Inputs/Outputs — "
                    "GC-012 sits between the bag filter (GC-010/GC-011) and the blower (GC-013), "
                    "both fully downstream of the quench tower, bracketed on the flow-confirmed "
                    "side by GC-009's and GC-013's own stated 50 Nm³/h figures without needing to "
                    "touch the quench-tower question at all."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source_gc("cross-item interpolation between GC-009's and GC-013's own confirmed downstream gas flow figures"),
            },
        ],
        "Outputs": [
            {
                "parameter": "Estimated outlet gas flow rate",
                "value": f"~{_GC_TRAIN_GAS_FLOW_NM3_H}", "unit": "Nm³/h",
                "remarks": (
                    "Same basis as this item's own estimated Inputs — trace-species (H2S/COS) "
                    "polishing removal only, no meaningful gas-volume change."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source_gc("cross-item interpolation, same basis as this item's estimated Inputs"),
            },
        ],
    },
}


def apply_estimates(datasheets):
    """Returns a NEW datasheets dict (deep-copied — input never
    mutated) with ESTIMATE_FILLS' rows appended into the named (item_id,
    category) buckets. Same safety check as equipment_rfi_fills.py:
    raises if a target bucket already has real data in it — this module
    must only ever fill genuinely empty slots, never sit on top of or
    contradict confirmed data."""
    out = copy.deepcopy(datasheets)
    for item_id, categories in ESTIMATE_FILLS.items():
        if item_id not in out:
            raise KeyError(f"ESTIMATE_FILLS references {item_id}, which isn't in the given datasheets.")
        sheet = out[item_id]["datasheet"]
        for category, rows in categories.items():
            if category not in sheet:
                raise KeyError(f"ESTIMATE_FILLS[{item_id!r}] references unknown category {category!r}.")
            if sheet[category]:
                raise ValueError(
                    f"REGRESSION GUARD: {item_id}'s {category} already has "
                    f"{len(sheet[category])} real row(s) — refusing to append an estimate on "
                    f"top of it. ESTIMATE_FILLS must only target genuinely empty categories."
                )
            sheet[category] = list(rows)
    return out


def count_estimates():
    """Returns (n_rows, n_slots, n_items)."""
    n_rows = sum(len(rows) for cats in ESTIMATE_FILLS.values() for rows in cats.values())
    n_slots = sum(len(cats) for cats in ESTIMATE_FILLS.values())
    n_items = len(ESTIMATE_FILLS)
    return n_rows, n_slots, n_items


if __name__ == "__main__":
    from . import equipment_rfi_fills

    print("=== Regression guard: every ESTIMATE_FILLS target category is genuinely empty beforehand ===")
    base = equipment_rfi_fills.apply_rfi_fills(equipment_datasheet.build_all_datasheets())
    for item_id, categories in ESTIMATE_FILLS.items():
        for category in categories:
            rows = base[item_id]["datasheet"][category]
            status = "OK (empty)" if not rows else f"FAIL ({len(rows)} real row(s) already there)"
            print(f"  {item_id} / {category}: {status}")
            assert not rows, f"REGRESSION: {item_id}'s {category} is NOT empty -- ESTIMATE_FILLS would overwrite real data."
    print("PASSED -- every targeted slot was genuinely 'Missing Data - Required' before this overlay.")

    print("\n=== apply_estimates() correctness ===")
    filled = apply_estimates(base)
    assert base is not filled, "REGRESSION: apply_estimates() returned the same object -- must be a copy."
    for item_id, categories in ESTIMATE_FILLS.items():
        for category in categories:
            assert not base[item_id]["datasheet"][category], (
                f"REGRESSION: apply_estimates() mutated the INPUT datasheets dict at {item_id}/{category}."
            )
    print("PASSED -- input datasheets dict is untouched; apply_estimates() returns a genuine copy.")

    n_rows, n_slots, n_items = count_estimates()
    print(f"\nRows added: {n_rows}")
    print(f"Distinct (item, category) slots newly estimated: {n_slots}")
    print(f"Distinct items touched: {n_items}")
    assert n_rows == 24, f"REGRESSION: expected 24 rows (7 FE + 10 GA + 7 GC), counted {n_rows}."
    assert n_slots == 24, f"REGRESSION: expected 24 newly-estimated slots, counted {n_slots}."
    assert n_items == 17, f"REGRESSION: expected 17 items touched (6 FE + 6 GA + 5 GC), counted {n_items}."

    print("\n=== Every added row carries status=STATUS_ESTIMATE, distinct from Confirmed ===")
    for item_id, categories in ESTIMATE_FILLS.items():
        for category, rows in categories.items():
            for row in rows:
                assert row["status"] == equipment_datasheet.STATUS_ESTIMATE, (
                    f"REGRESSION: {item_id}/{category} row has status {row.get('status')!r}, expected STATUS_ESTIMATE."
                )
                assert row["source"].startswith("Engineering estimate"), (
                    f"REGRESSION: {item_id}/{category} row's source doesn't identify it as an engineering estimate."
                )
                assert row["remarks"] and len(row["remarks"]) > 40, (
                    f"REGRESSION: {item_id}/{category} row has no substantive stated basis in its remarks."
                )
    print(f"PASSED -- every one of the {n_rows} rows is tagged STATUS_ESTIMATE with a real, substantive basis stated.")

    print("\n=== GA-specific check: no carbon-black fill uses RFI #2's feedstock elemental-carbon figure ===")
    for item_id, category in (("GA-008", "Inputs"), ("GA-010", "Inputs")):
        for row in ESTIMATE_FILLS[item_id][category]:
            assert "45" not in row["value"], (
                f"REGRESSION: {item_id}/{category}'s VALUE looks like it used RFI #2's elemental-carbon figure (>45%), not the carbon-black-yield fraction."
            )
            assert "DELIBERATELY" in row["remarks"], (
                f"REGRESSION: {item_id}/{category} doesn't explicitly document that it checked for and avoided the carbon-content conflation trap."
            )
    print("PASSED -- GA-008/GA-010's carbon-black fills use only the 5% carbon-black-yield fraction, never RFI #2's unrelated elemental-carbon figure, and explicitly document the check.")

    print("\n=== GA-specific check: GA-009's/GA-010's mass-balance fills explicitly account for, not ignore, a real transformation step ===")
    for item_id, category in (("GA-009", "Performance Indicators"), ("GA-010", "Inputs")):
        for row in ESTIMATE_FILLS[item_id][category]:
            assert "DELIBERATELY" in row["remarks"] and "NOT" in row["remarks"], (
                f"REGRESSION: {item_id}/{category} doesn't explicitly document avoiding an assume-equal-pass-through error."
            )
    print("PASSED -- GA-009's cement-additive step and GA-010's collection-efficiency step are both explicitly accounted for, never assumed away.")

    print("\n=== GC-specific check: the declined quench-tower gas flow (GC-004 Outputs) was never actually filled ===")
    assert "GC-004" not in ESTIMATE_FILLS, (
        "REGRESSION: GC-004 appears in ESTIMATE_FILLS -- the module docstring explicitly declines its Outputs "
        "(post-quench gas flow) as physically unsound to assert without confirmed condensation data; it must stay Missing."
    )
    print("PASSED -- GC-004 (Quench Tower, Temp) has no fill of any kind, exactly as declined in the GC REPORT.")

    print("\n=== GC-specific check: GC-006's/GC-012's estimated gas flow matches the train's own confirmed downstream figure exactly ===")
    for item_id in ("GC-006", "GC-012"):
        for category in ("Inputs", "Outputs"):
            for row in ESTIMATE_FILLS[item_id][category]:
                assert str(_GC_TRAIN_GAS_FLOW_NM3_H) in row["value"], (
                    f"REGRESSION: {item_id}/{category}'s value doesn't match the train's confirmed 50 Nm3/h figure."
                )
    print(f"PASSED -- GC-006's and GC-012's estimated gas flows both use the exact same {_GC_TRAIN_GAS_FLOW_NM3_H} Nm3/h "
          f"the train's own GC-003/GC-009/GC-013 already confirm, not a separately invented number.")

    print("\n=== Task requirement 4: three-way honest totals, verified live (not blended) ===")
    before = equipment_datasheet.summarize(base)
    after = equipment_datasheet.summarize(filled)
    print(f"Confirmed slots: {before['confirmed_category_slots']} -> {after['confirmed_category_slots']} "
          f"(should be UNCHANGED -- estimates don't touch confirmed data)")
    print(f"Estimate slots:  {before['estimated_category_slots']} -> {after['estimated_category_slots']} "
          f"(+{after['estimated_category_slots'] - before['estimated_category_slots']})")
    print(f"Missing slots:   {before['missing_category_slots']} -> {after['missing_category_slots']} "
          f"(-{before['missing_category_slots'] - after['missing_category_slots']})")
    assert after["confirmed_category_slots"] == before["confirmed_category_slots"], (
        "REGRESSION: confirmed_category_slots changed -- estimates must never touch confirmed data."
    )
    assert after["estimated_category_slots"] - before["estimated_category_slots"] == n_slots
    assert before["missing_category_slots"] - after["missing_category_slots"] == n_slots
    assert before["missing_category_slots"] == 284, f"REGRESSION: expected 284 missing before this overlay, got {before['missing_category_slots']}."
    assert after["missing_category_slots"] == 284 - n_slots
    print(f"PASSED -- {n_slots} slots moved from Missing to Estimate (284 -> {after['missing_category_slots']}), "
          f"Confirmed slots genuinely unchanged, not blended together.")

    print("\n=== Task requirement 8 (this extension): FE's and GA's numbers, regression-verified unchanged ===")
    fe_after = equipment_datasheet.summarize(filled, ids=equipment_datasheet.FE_IDS)
    print(f"FE: {fe_after['confirmed_category_slots']} Confirmed, "
          f"{fe_after['estimated_category_slots']} Engineering Estimate, "
          f"{fe_after['missing_category_slots']} Missing (of {fe_after['total_category_slots']} total slots)")
    assert fe_after["confirmed_category_slots"] == 27, f"REGRESSION: expected 27 Confirmed FE slots, got {fe_after['confirmed_category_slots']}."
    assert fe_after["estimated_category_slots"] == 7, f"REGRESSION: expected 7 Estimate FE slots, got {fe_after['estimated_category_slots']}."
    assert fe_after["missing_category_slots"] == 14, f"REGRESSION: expected 14 Missing FE slots, got {fe_after['missing_category_slots']}."
    print("PASSED -- FE's pilot numbers are unchanged by this GC extension: 27 Confirmed + 7 Engineering Estimate + 14 Missing = 48.")

    ga_after = equipment_datasheet.summarize(filled, ids=equipment_datasheet.GA_IDS)
    print(f"GA: {ga_after['confirmed_category_slots']} Confirmed, "
          f"{ga_after['estimated_category_slots']} Engineering Estimate, "
          f"{ga_after['missing_category_slots']} Missing (of {ga_after['total_category_slots']} total slots)")
    assert ga_after["confirmed_category_slots"] == 31, f"REGRESSION: expected 31 Confirmed GA slots, got {ga_after['confirmed_category_slots']}."
    assert ga_after["estimated_category_slots"] == 10, f"REGRESSION: expected 10 Estimate GA slots, got {ga_after['estimated_category_slots']}."
    assert ga_after["missing_category_slots"] == 19, f"REGRESSION: expected 19 Missing GA slots, got {ga_after['missing_category_slots']}."
    print("PASSED -- GA's extension numbers are unchanged by this GC extension: 31 Confirmed + 10 Engineering Estimate + 19 Missing = 60.")

    print("\n=== GC-specific honest breakdown (this extension) ===")
    gc_after = equipment_datasheet.summarize(filled, ids=equipment_datasheet.GC_IDS)
    print(f"GC: {gc_after['confirmed_category_slots']} Confirmed, "
          f"{gc_after['estimated_category_slots']} Engineering Estimate, "
          f"{gc_after['missing_category_slots']} Missing (of {gc_after['total_category_slots']} total slots)")
    assert gc_after["confirmed_category_slots"] == 52, f"REGRESSION: expected 52 Confirmed GC slots, got {gc_after['confirmed_category_slots']}."
    assert gc_after["estimated_category_slots"] == 7, f"REGRESSION: expected 7 Estimate GC slots, got {gc_after['estimated_category_slots']}."
    assert gc_after["missing_category_slots"] == 31, f"REGRESSION: expected 31 Missing GC slots, got {gc_after['missing_category_slots']}."
    print("PASSED -- GC: 52 Confirmed + 7 Engineering Estimate + 31 Missing = 90 total slots, matches exactly.")

    print("\n=== Regression check: every OTHER section (SA, HB, EU, AI) is untouched by this overlay ===")
    for label, ids in [
        ("SA", equipment_datasheet.SA_IDS), ("HB", equipment_datasheet.HB_IDS),
        ("EU", equipment_datasheet.EU_IDS), ("AI", equipment_datasheet.AI_IDS),
    ]:
        b = equipment_datasheet.summarize(base, ids=ids)
        f = equipment_datasheet.summarize(filled, ids=ids)
        print(f"  {label}: {b} == {f}: {b == f}")
        assert b == f, f"REGRESSION: {label} section changed, but only FE, GA, and GC are targeted so far."
    print("PASSED -- SA, HB, EU, and AI are byte-for-byte identical to the pre-overlay data.")

# (touch: force fresh Streamlit Cloud rebuild after adding GC-001..GC-015 estimates, 2026-08-28)
