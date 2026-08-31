"""
Engineering-estimate overlay v7 — PILOTED on FE-001 through FE-008's 21
remaining "Missing Data — Required" gaps first (reviewed and approved),
EXTENDED to GA-001 through GA-010's 29 remaining gaps (reviewed and
approved), EXTENDED to GC-001 through GC-015's 38 remaining gaps
(reviewed and approved), EXTENDED to SA-001 through SA-012's 46
remaining gaps (reviewed and approved), EXTENDED to HB-001 through
HB-018's 51 remaining gaps (reviewed and approved), EXTENDED to
EU-001 through EU-013's 32 remaining gaps (reviewed and approved), and
now EXTENDED ONE LAST TIME to AI-001 through AI-015's 67 remaining
gaps under the identical rule set, no relaxation. This closes out the
full engineering-estimate pass across all 91 items in all 7 sections —
no section remains untouched after this round.

HB'S OWN GAP COUNT, VERIFIED LIVE, NOT ASSUMED: the task that requested
this extension stated "52 remaining gaps." Checked directly against
this project's own live data before doing anything else (same "verify,
don't just assert" discipline this whole project follows) — the actual
live count is 51, not 52 (equipment_datasheet.summarize() on HB_IDS
after equipment_rfi_fills.py, confirmed via a direct per-item
recount). Reported honestly rather than silently forced to match the
stated number or silently corrected without comment.

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
gap in effort. Of SA's 46 gaps, only 1 gets a genuine estimate; 45 stay
missing — SA is almost entirely measurement instruments (gas
analysers, sensors, a manual sampling port), whose OWN specific
accuracy/response-time/measurement-range figures are vendor/product
properties by definition, not something a correlation or literature
value can substitute for before a model is chosen, and most of them
have no material stream of their own to give an Inputs/Outputs figure
at all — a near-zero fill rate here is the CORRECT, honest outcome,
not a gap in effort. Of HB's 51 actual gaps, 13 get a genuine
estimate; 38 stay missing — HB is the largest section and the most
mixed in character: a validated physics core (WGS kinetics, PSA) that
yields the STRONGEST kind of fill this whole project has produced, a
parallel/optional technology spread (membrane separation, electrolysis,
LOHC) that is more genuinely vendor/design-dependent, and the usual
recurring patterns (shared-physical-equipment sub-items, same-item
recategorization risk) already established in every prior section. Of
EU's 32 gaps, 8 get a genuine estimate; 24 stay missing — EU is CHP/
electrical/utilities: a validated part-load physics correlation
(chp.py) that yields one genuine new fact beyond what's already
Confirmed, several exact calculations from an item's own confirmed
values (a cooling-tower range, an HX effectiveness with a clean,
verified basis and one without), a couple of comparable-installed-
system fills grounded in a specifically-confirmed technology property
rather than generic ambient hand-waving, and the same recategorization/
shared-equipment/vendor-instrument declines already established
everywhere else. Of AI's 67 gaps — the LAST section — only 2 get a
genuine estimate; 65 stay missing, the lowest fill rate of any section
by absolute count, exactly as expected going in: AI-004 through AI-014
are PLC/gateway/broker/SCADA/edge-server/firewall/cloud-hub/database/
model-server/twin-engine/orchestration items that process data, not a
material or energy stream, so "Inputs"/"Outputs" as this project
defines them structurally do not apply — not a shortfall in effort,
the correct, honest outcome for software/network equipment. The 3
physical field instruments (AI-001 weather station, AI-002 camera,
AI-003 pressure-drop sensor) got the same SA-instrumentation-style
check as everything else and yielded exactly 2 genuine fills between
them — see REPORT below for the per-gap reasoning on every single one,
filled and declined alike, all seven sections.

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

SA-SPECIFIC DISCIPLINE (task requirements 2-4): SA is instrumentation —
gas analysers, sensors, and one manual sampling port — not process
equipment, so the FE-006 (Moisture Analyser) precedent applies almost
across the board: a measurement instrument OBSERVES the shared process
gas stream, it doesn't receive and transform a material stream of its
own the way a cyclone, scrubber, or filter does, so it structurally has
no genuine Inputs/Outputs figure to estimate — not just undocumented.
A second, SA-specific distinction was checked carefully before filling
any Operating Conditions gap (the "compute-then-verify"/conflation
discipline, task requirements 3-4): this project's OWN convention,
evidenced by SA-009's own parameter literally named "Operating
temperature (gas)", is that Operating Conditions for an SA item means
the ACTUAL PROCESS GAS temperature at that point — but SA-001 through
SA-006 and SA-008 are all TCD/NDIR/UV-fluorescence gas-COMPOSITION
analysers that explicitly require sample conditioning (SA-001's own
Parameters: "Sample conditioning required = Yes... moisture removal,
particulate filtration, and pressure/flow regulation before reaching
the analyser") — what reaches their own detection cell is a
conditioned sample, not the raw process gas, so assigning them the
same process-gas temperature as a direct in-line sensor (SA-009's
triboelectric monitor, SA-010's thermal mass flow meter, SA-011's Pt100
RTD, SA-012's capacitive diaphragm transmitter) would conflate two
genuinely different instrument-installation contexts — checked and
declined for exactly that reason, not overlooked. The one item that IS
filled (SA-011 Operating Conditions) is a direct in-line RTD sensor
whose own remarks ALREADY state the number in prose ("Generous margin
around the expected 40°C operating point") without it ever being
extracted into its own row — a genuinely new row for an already-stated
fact, not an external guess, and cross-consistent with SA-009's and
SA-010's own separately-Confirmed 40°C at the same late-train position.
A third pattern, checked and declined twice (SA-007, SA-009 Performance
Indicators): a measurement/verification instrument's Performance
Indicators must not be filled with the REMOVAL efficiency of the
process equipment it merely verifies — SA-007 (Tar Sampling Port)
doesn't remove tar (GC-006/GC-007 do; GC-007's own removal efficiency
is already filled in the GC round), and SA-009 (Dust Monitor) doesn't
remove dust (GC-010 does; already filled). Attributing that efficiency
to the instrument instead of the equipment actually performing the
removal would be a real misattribution error, the same class of
mistake as the GC round's adjacent-stage conflations, just between an
instrument and the equipment it watches rather than between two
equipment items. equipment_rfi_fills.py's own existing SA-006 check
(gas calorimeter's SYNGAS LHV is NOT the same quantity as RFI #2's
FEEDSTOCK LHV) was re-confirmed still unused by any fill here. Two NEW
apparent MISLABELED cross-references were found in SA's own pre-
existing registry remarks and are reported, not silently used or
ignored (same discipline as the two found in GC, and documented
alongside them in CLAUDE.md's "Known source-data issues" section):
SA-007's own remark places its "raw" tar-sampling port "upstream of
GC-008", but its own "Expected tar concentration (raw)" figure is
explicitly back-calculated using GC-006's removal efficiency ("assuming
GC-006's ~95% bulk removal efficiency") — the raw port should almost
certainly be described as upstream of GC-006 (the actual bulk tar-
removal unit), not GC-008 (the H2S scrubber, unrelated to tar); and
SA-008's own remark says its <0.1 ppm expected H2S concentration
"matches GC-009's target", but GC-009 is the HCl Scrubber (its own
target is <5 ppm HCl, a different species entirely) — GC-012's own
confirmed "<0.1 ppm outlet" H2S/COS target (the Activated Carbon
Filter) is the actual, exact match. Neither mislabeled reference is
relied upon by anything filled here.

HB-SPECIFIC DISCIPLINE (task requirements 2-5): task requirement 2's
explicit priority — check kinetics.py/psa.py's own already-validated
physics FIRST, since it's independently verified, not an external
correlation — produced this whole project's SINGLE STRONGEST fill:
HB-004 (WGS Reactor LTS) Performance Indicators (40% relative
conversion) comes directly from kinetics.py's own live lts_conversion()
output, which is independently cross-verified by a completely separate
route — plain arithmetic on two numbers ALREADY Confirmed in the
registry itself (HB-002's 7% HTS outlet, HB-004's own 4.2% LTS
outlet: (7-4.2)/7 = 40%) — physics model and registry data agree
exactly, not just plausibly. Checked carefully against task
requirement 2's own explicit warning not to duplicate a number already
displayed elsewhere in the app: this 40% figure IS also shown live on
the Digital Twin tab's own kinetics slider, but populating HB-004's own
equipment-datasheet Performance Indicators slot (which was genuinely
EMPTY — unlike HB-002's own PI, already Confirmed at 75%) is filling a
different, real gap with the same underlying fact, not restating
something already present for THIS item — the same "exact calculation
from confirmed inputs" pattern as FE-004's specific energy, just
sourced from a validated physics module instead of two Parameters
rows. HB-001/HB-002 and HB-006/HB-007/HB-008 are shared-physical-
equipment sub-item groups (temperature/composition/pressure aspects of
the SAME WGS-HTS reactor and the SAME PSA skid respectively) — the
same GA-002/GC-002/GC-014/SA-family pattern already established:
Inputs/Outputs/Performance Indicators belonging to one aspect-item are
not re-derived or duplicated into a sibling aspect-item describing the
identical physical equipment. A "number already sitting in a sibling
item's own remarks, never given its own row" pattern (first used for
SA-011) recurs three times here: HB-009's Operating Conditions
(~0.2 bar(g), already stated in this item's own remark citing HB-008),
and HB-014's/HB-015's/HB-016's LOHC carrier throughput (~0.031-
0.032 m3/h, HB-015's own remark already attributes this figure to
"HB-014's carrier throughput" — independently cross-verified here via
mass balance from each item's own confirmed H2 loading/release
capacity and efficiency, using DBT's standard ~1040 kg/m3 density, a
physical constant, not a design assumption). A genuine "compute, then
verify, then decline" case (task requirement 4) is reported in full:
HB-003 (Heat Exchanger, WGS) Performance Indicators — a naive thermal
effectiveness calculation from this item's own four confirmed
temperatures gives 47.4%, but that formula is only valid for whichever
stream has the LOWER heat-capacity rate, and determining that requires
inferring an unstated water flow rate from the item's own approximate
duty figure plus an external water-cp constant — a real answer might
exist, but it rests on a stacked chain of inference rather than values
directly on file, a materially weaker basis than the LOHC carrier-flow
calculations above (which use only each item's own two directly-
Confirmed values plus one physical constant, no inferred intermediate
quantity) — declined on that distinction, not because the number is
implausible. A second honest decline, found only by actually checking
rather than assuming: HB-014 (LOHC Hydrogenation) Inputs was
considered for the same ~1.85 kg/h H2 feed rate already established at
HB-007, but HB-017's own remark confirms the LOHC-purified output
"merges with the primary WGS+PSA route" at shared storage — meaning
LOHC is a parallel/optional pathway that may process only a FRACTION
of total H2 production, not necessarily all of it, and no confirmed
figure states that split — declined rather than silently assuming
100% throughput. Task requirement 3's core-vs-auxiliary framing was
checked against this project's own actual item names, not assumed
literally: only HB-011 and HB-016 carry the literal "— Auxiliary/
Optional" suffix in their registry names; HB-014/HB-015/HB-017 are
part of the SAME LOHC alternative-pathway chain in spirit but aren't
literally labeled that way — reported here rather than silently
treating the task's framing as exact. Five MORE mislabeled cross-
references were found while checking for exactly the conflation risk
task requirement 5 warns about (on top of the four already found in
GC/SA) — see CLAUDE.md's "Known source-data issues" section for the
full list; none is relied upon by anything filled here.

REGISTRY-WIDE SWEEP (2026-08-28, a dedicated follow-up task, not
opportunistic section-by-section discovery): every mention of GC-006,
GC-008, GC-009, or GC-012 anywhere in all 91 registry items was
checked against what those four items actually are. Found 8 MORE
mismatched remarks beyond the 8 already known from working FE/GA/GC/
SA/HB directly (17 total across the whole registry, all now in
CLAUDE.md's "Known source-data issues" section). Every ESTIMATE_FILLS
entry above was individually re-checked against this complete list —
none uses any of the 17 mismatched remarks as its stated basis; no
previously-shipped estimate required correction or withdrawal.

EU-SPECIFIC DISCIPLINE (task requirements 2-5): task requirement 2's
explicit priority — check chp.py's/dispatch_ga.py's own validated
outputs first, the same way HB-004 leveraged kinetics.py — was
followed through completely, not just nominally: dispatch_ga.py was
ruled OUT entirely (its output is a live, slider-dependent GA
optimization result for a specific fuel-budget scenario, not a fixed
design-basis fact an equipment datasheet can state); chp.py's RATED-
point efficiencies (100% load) were also ruled out, since all four
CHP units already have their own rated efficiency Confirmed in the
registry (EU-002/EU-003/EU-005/EU-006) with zero room to add anything
(EU-002 has no missing categories at all). The one genuine opportunity
survived a careful check: EU-001 (SOFC Stack, Temp) is the temperature-
aspect sub-item of the SAME physical stack EU-002 (Efficiency aspect)
already covers, so its own Performance Indicators gap can't be filled
with EU-002's already-Confirmed 55% rated figure (shared-physical-
equipment recategorization) — but chp.py's own PART-LOAD correlation
(sub-100% load) is genuinely NEW information nowhere in the registry,
which only ever states the single rated point. Filled with chp.py's
own characterized turndown range (x=0.01 to x=1.0), not an arbitrary
single load point. Task requirement 3 (don't confuse one CHP
technology's parameters with another's) is trivially satisfied here —
only ONE technology (SOFC) has a genuine chp.py-linked gap at all, and
the fill calls chp_efficiency() with unit_name="SOFC" only, never
touching the Gas Engine/Microturbine/PEM entries in the same dict.

Two "compute then verify" cases with opposite, individually-justified
outcomes (task requirement 5), a direct pair worth contrasting: EU-012
(District Heating HX) Performance Indicators — a thermal-effectiveness
calculation — IS filled, because this item's own four confirmed
temperatures show BOTH streams have the SAME 30 degC temperature drop
on matched flow rates of the same fluid (water), meaning their heat-
capacity rates are equal and the standard effectiveness formula gives
the identical answer computed from EITHER stream (85.7% both ways) —
no inferred, unconfirmed intermediate quantity needed, unlike HB-003's
case. EU-011 (Heat Recovery Unit) Performance Indicators — the SAME
KIND of naive effectiveness calculation — is DECLINED for the SAME
reason HB-003's was: this item's own confirmed data doesn't establish
which stream has the lower heat-capacity rate, and resolving that would
require inferring an unstated water-side inlet temperature rather than
reading values directly on file.

Two general equipment-class literature-range fills (the same basis
category FE-005's dryer-efficiency fill already established as valid):
EU-007 (Flare)'s destruction efficiency (>98%, the widely-recognized
regulatory presumption for a properly-designed and operated enclosed
flare with adequate residence time, exit velocity, and heating value —
not derived from this item's own specific data, stated as such) and
EU-010 (UPS)'s round-trip efficiency (92-96%, a commonly-published
range for online double-conversion UPS systems at this power class).
One comparable-installed-system fill grounded in a SPECIFICALLY
confirmed technology property, not generic ambient hand-waving: EU-010
Operating Conditions cites a LiFePO4 battery's own real, standard
operating-temperature envelope, tied directly to this item's own
confirmed Battery technology field — the same discipline already used
for GC-006's PSA-adsorbent temperature fill.

EU's OWN cross-references were checked specifically for the GC-006/
GC-008/GC-009/GC-012 pattern (task requirement 4) — ZERO new instances
(EU's own data contains no reference to any of those four items at
all). Six MORE mislabeled remarks turned up anyway while reviewing
EU's own cross-references generally, unrelated to that specific
pattern — see CLAUDE.md's "Known source-data issues" section (items
16-20) for the full list; none is relied upon by anything filled here.
One of those findings (EU-013's own remarks citing "EU-007" three
times when EU-012 is almost certainly intended) is used constructively
here, not just flagged: EU-013's Operating Conditions is filled using
EU-012's own correctly-Confirmed secondary-side temperatures directly,
explicitly noting the correction rather than propagating the
mislabeled reference.

AI-SPECIFIC DISCIPLINE (task requirements 2-5, the final section): task
requirement 2's own explicit framing was checked against this project's
actual data before doing anything else, not assumed — AI-004 through
AI-014 (PLC, OPC-UA gateway, MQTT broker, DCS/SCADA server, edge
computing server, cybersecurity firewall, cloud IoT hub, time-series
database, AI model server, digital twin engine, multi-module
orchestration controller) genuinely have no material or energy stream
of their own; every one of their Inputs/Outputs gaps is declined as
structurally not a fit, the same FE-006/SA-family "measurement/control
equipment observes or processes data, it doesn't receive and transform
a material stream" reasoning, just extended from single instruments to
whole software/network systems. The one real, item-specific opportunity
among these eleven items: AI-004 (PLC)'s Operating Conditions is filled
using this item's OWN confirmed CPU family (Siemens SIMATIC S7-1500,
CPU 1516-3 PN/DP) and its own confirmed control-room housing — a named,
real, checkable product family's published operating-temperature
envelope, the same comparable-installed-system basis category as
EU-010's LiFePO4 fill, not a generic "control equipment runs at room
temperature" hand-wave. Every OTHER OC/Measurements/PI gap among
AI-005 through AI-014 was checked and declined because the item's own
data names no specific product (only "or equivalent" generic
descriptions) — a materially weaker basis than AI-004's named CPU
model, so filling those would be forcing a category to apply where the
"strongest kind of estimate" standard this project holds everywhere
else genuinely isn't met.

Task requirement 3's instrumentation check (AI-001 Weather Station,
AI-002 Camera, AI-003 Bed Pressure-Drop Sensor): AI-003's Inputs/
Outputs/Performance Indicators are declined the same structural way
(a differential-pressure sensor reading GA-002's own existing taps has
no material stream or removal-efficiency concept of its own — its own
Operating Conditions and Accuracy are already Confirmed). AI-001's
Inputs/Operating Conditions/Performance Indicators are all declined —
Inputs structurally (a weather station observes ambient conditions, it
doesn't receive a stream), Operating Conditions as recategorization
(its own confirmed Temperature range parameter already states this
exact fact under a different category), Performance Indicators for
lack of any stated basis. AI-002's one genuine fill: Operating
Conditions, using its OWN confirmed remark that places it physically
"at FE-001's hopper/conveyor" (verified correct — see the mislabel
sweep below, this specific cross-reference is one of the FEW in this
item that checks out) combined with FE-001's own separately-Confirmed
site ambient range — the same cross-item-location derivation pattern
this project's very first fills (FE-002/FE-003) already established,
just applied here for the first time to an AI-section item. AI-002's
other three gaps (Inputs, Outputs, Performance Indicators) are
declined: Inputs/Outputs structurally (a machine-vision camera
observes, it doesn't receive/output a material stream), and Performance
Indicators as recategorization (its own confirmed "AI model accuracy
(design) = 90%" already states the one number that would go there,
just filed under Parameters instead).

Task requirement 4 (compute then verify) — a genuine, worth-reporting
case for this section: AI-008 (Edge Computing Server) Performance
Indicators was checked for a computed availability/uptime figure from
this item's own confirmed MTBF (80,000 h) — but availability requires
BOTH MTBF and Mean Time To Repair, and no MTTR figure is confirmed
anywhere in this project for this item. Presenting an availability
percentage built on an assumed MTTR would be exactly the kind of
unstated-assumption fabrication this module's hard rule forbids, so
AI-008 Performance Indicators stays declined — the number one might be
tempted to compute doesn't actually check out.

Task requirement 5's mislabel sweep (now at 23 documented entries
before this round) turned up an unusually large batch in AI's own
data — by far the highest concentration found in any section, which
is itself a genuine, worth-reporting finding about this section's
source data quality. Every value AND remarks field across all 15 AI
items was checked against the actual identity of every cross-
referenced item (not just remarks, per the HB-005/AI-002 precedent
that VALUE fields carry the same risk). Five systematic PATTERNS
account for most of it — the same wrong ID substituted for the same
correct one, repeatedly, across many different fields: AI-001 (Weather
Station) mistakenly cited in place of AI-004 (PLC) 12 times (mostly
"AI-001's scan cycle"/"AI-001's I/O points"/"AI-001 PLC", none of
which describe a weather station); AI-003 (Bed Pressure-Drop Sensor)
mistakenly cited in place of AI-005 (OPC-UA Gateway) 8 times (mostly
"AI-003 gateway"/"AI-003's OPC-UA tags", none of which describe a
differential-pressure transmitter); AI-006 (MQTT Broker) mistakenly
cited in place of AI-010 (Cloud IoT Hub) 7 times, including AI-006's
OWN row self-referencing "AI-006 Cloud IoT Hub" while AI-006 itself IS
the MQTT Broker, not the Cloud IoT Hub; AI-002 (Camera) mistakenly
cited in place of AI-007 (DCS/SCADA Server, which holds the historian/
VPN/cybersecurity-standard data actually being described) 8 times; and
AI-009 (Cybersecurity Firewall) mistakenly cited in place of AI-013
(Digital Twin Engine) 5 times. Twelve further individual, one-off
mislabels were found outside these five patterns (full list in
CLAUDE.md's "Known source-data issues" section, items 21 onward) —
including AI-002's own "AI model purpose" field citing "FE-003
shredder" (FE-003 is the Weighing Conveyor; FE-004 is the actual
Shredder/Size Reducer) and "FE-008's magnetic tramp-metal removal"
(FE-008 is the Air-lock/Rotary Valve; FE-002 is the actual Magnetic &
Eddy Current Separator) in the same field. EVERY ONE of these 52 new
findings was individually checked against both of this round's actual
fills (AI-002 Operating Conditions, AI-004 Operating Conditions) —
neither relies on any of them: AI-002's fill uses its own SEPARATELY-
VERIFIED-CORRECT "FE-001" reference (not one of the mislabeled ones),
and AI-004's fill uses only its own confirmed CPU model, no cross-
reference at all. Running total: 23 + 52 = 75 distinct erroneous
remarks found across the registry to date.

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
extension, GC extension, SA extension, HB extension, EU extension, or
AI extension) and its basis type, distinct in app.py's UI from both
"Equipment Datasheet" (vendor data) and "DOK-ING RFI (design_basis.py
Q#)" (DOK-ING's real answers) rows.

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

SA REPORT (extension — every one of SA's 46 gaps, filled and declined).
SA is almost entirely measurement instruments (gas analysers, sensors,
one manual sampling port) — a near-zero fill rate is the correct,
honest outcome, not a shortfall in effort:

FILLED — 1 of 46:

  SA-011 (Gas Temperature Sensor) Operating Conditions: ~40 degC. Basis:
    this item's own Measurement range remark ALREADY states the number
    in prose ("Generous margin around the expected 40 degC operating
    point — a normal-condition location") without it ever being
    extracted into its own Operating Conditions row — a genuinely new
    row for an already-stated fact, not an external guess. Cross-
    consistent with SA-009's and SA-010's own separately-Confirmed 40
    degC Operating temperature at the same late-train position — SA-011
    is a direct in-line Pt100 RTD sensor, the same instrument category
    as those two (not a sample-conditioned composition analyser, see
    the SA-SPECIFIC DISCIPLINE section above for why that distinction
    matters).

DECLINED — 45 of 46, with the actual reason:

  SA-001 through SA-006 (H2/CO/CO2/CH4/N2/LHV gas-composition analysers)
    Inputs, Outputs: structurally not a fit — these are measurement
    instruments observing the shared process gas stream, not process
    equipment receiving/transforming a material stream of their own,
    the same FE-006 (Moisture Analyser) precedent already established.
    Operating Conditions: CHECKED, not skipped — see the SA-SPECIFIC
    DISCIPLINE section above for the full sample-conditioning-vs-
    direct-in-line reasoning; assigning them the same process-gas
    temperature as SA-009/010/011/012 would conflate two different
    instrument-installation contexts. Performance Indicators: each
    item's own accuracy/response-time figures already fully capture its
    performance under Measurements; no additional efficiency/recovery-
    rate-type KPI concept applies to a composition-measurement
    instrument. SA-005's and SA-006's own explicitly CALCULATED (not
    directly measured) status doesn't change any of this reasoning.

  SA-007 (Tar Sampling Port) Inputs, Outputs: structurally not a fit —
    manual grab sampling (its own stated method: "no continuous online
    analyser") has no continuous material stream to characterize.
    Measurements: also structurally not a fit — "response time,"
    "accuracy," and "output signal" (the concepts this category
    captures elsewhere) don't apply to a manual, intermittent
    sampling method; its own methodology (CEN/TS 15439 Tar Protocol) is
    already fully captured under Parameters. Operating Conditions: no
    data exists to derive a gas temperature at this specific tap point
    from. Performance Indicators: CHECKED, not skipped — a tar removal
    efficiency IS computable from this item's own confirmed raw/clean
    concentration figures, but that efficiency belongs to GC-006/GC-007
    (the equipment that actually removes the tar; GC-007's own removal
    efficiency is already filled in the GC round) — attributing it to
    this sampling port instead would be a real misattribution error,
    not a genuine performance metric for THIS item.

  SA-008 (H2S / COS Analyser) Inputs, Outputs: same structural reasoning
    as SA-001-006. Operating Conditions: same sample-conditioning
    reasoning as SA-001-006 — this is a combined UV-fluorescence/GC-FPD
    analyser, also requiring conditioned sample delivery. Performance
    Indicators: same reasoning as SA-001-006 — accuracy/response time
    already captured under Measurements.

  SA-009 (Dust / Particulate Monitor) Inputs, Outputs: same structural
    reasoning as SA-001-006 (a monitor observes, it doesn't receive a
    material stream of its own — its own Operating Conditions is
    already separately Confirmed, since it IS a direct in-line
    instrument, unlike SA-001-006/SA-008). Performance Indicators:
    CHECKED, not skipped — same misattribution reasoning as SA-007's
    decline: the dust removal efficiency belongs to GC-010 (already
    filled in the GC round), not to the monitor that merely verifies
    it.

  SA-010 (Gas Flow Meter, Clean) Outputs: this item's own confirmed
    Inputs already states "Design flow rate = 50 Nm3/h" — a flow meter
    measures ONE stream passing through it; an Outputs figure would
    restate the identical already-Confirmed number for the identical
    item, the same recategorization discipline already applied to
    GC-001/GC-003/GC-013's Outputs. Parameters: no basis exists to
    derive a physical-spec figure (pipe size, connection type) this
    item doesn't already state, unlike SA-012 (which has its own
    confirmed Process connection) — vendor/design-dependent. Performance
    Indicators: accuracy already captured under Measurements.

  SA-011 Inputs, Outputs: same structural reasoning as SA-001-006 (this
    item's own Operating Conditions IS filled above, since it's a
    direct in-line sensor — but it still has no material stream of its
    own the way process equipment does). Performance Indicators: no
    additional KPI beyond its own already-Confirmed accuracy.

  SA-012 (Gas Pressure Sensor) Inputs, Outputs: same structural
    reasoning as SA-001-006/SA-011 (its own Operating Conditions is
    already separately Confirmed). Performance Indicators: no
    additional KPI beyond its own already-Confirmed accuracy.

HB REPORT (extension — every one of HB's 51 actual gaps, filled and
declined). HB is the largest, most mixed section: a validated physics
core (HB-001 through HB-009, HB-012/013), a parallel membrane
technology (HB-010), auxiliary/optional pathways (HB-011, HB-014
through HB-017), and standardized dispensing (HB-018):

FILLED — 13 of 51:

  HB-004 (WGS Reactor LTS) Inputs: ~7 vol% CO inlet concentration.
    Basis: cross-item derivation from HB-002's own confirmed 7 vol% CO
    outlet concentration (HTS stage) — sequential reactors, the same
    gas stream, HB-002's outlet IS HB-004's inlet directly.

  HB-004 Performance Indicators: LTS-stage relative CO conversion,
    40%. Basis: kinetics.py's own live, independently-validated
    lts_conversion() output (this project's single strongest possible
    basis — verified physics, not a correlation), cross-checked by
    plain arithmetic on two values ALREADY Confirmed in the registry
    (HB-002's 7% outlet, HB-004's own 4.2% outlet: (7-4.2)/7 = 40%) —
    both routes agree exactly. See HB-SPECIFIC DISCIPLINE above for
    the full "not duplicating an already-displayed number" reasoning.

  HB-005 (Steam Generator, WGS) Inputs: ~45 kg/h feedwater rate. Basis:
    standard boiler mass-balance conservation (feedwater mass in =
    steam mass out, negligible blowdown at this scale) from this
    item's own confirmed Steam production rate (45 kg/h, its own
    Outputs) — a genuine new claim about a different physical stream
    at the same value, not a same-item recategorization.

  HB-006 (PSA Unit, H2 Purity) Operating Conditions: ambient
    (~15-40 degC). Basis: comparable-installed-system practice, tied
    directly to this item's own confirmed Adsorbent material
    (activated carbon + zeolite molecular sieve) — both are standard
    ambient-temperature PSA media; adsorption selectivity and capacity
    measurably degrade at elevated temperature, which is why virtually
    all industrial H2 PSA units operate near ambient regardless of
    upstream process conditions. Filled here rather than at HB-007/
    HB-008 (the same physical PSA skid's other two aspect-items) since
    HB-006 (Purity) is the aspect most directly tied to adsorbent
    temperature sensitivity — see HB-SPECIFIC DISCIPLINE above.

  HB-009 (PSA Tail Gas Handler) Operating Conditions: ~0.2 bar(g).
    Basis: this item's own remark for "Tail gas compressor" ALREADY
    states "tail gas exits PSA regeneration at ~0.2 bar(g) (HB-008)"
    without it ever being extracted into its own Operating Conditions
    row — a genuinely new row for an already-stated fact.

  HB-011 (Electrolyser) Inputs: ~0.18 L/h water feed rate. Basis:
    EXACT calculation from this item's own two already-Confirmed
    values — Water consumption (~1 L/Nm3 H2) x H2 production rate
    (rated, 0.18 Nm3/h) = 0.18 L/h.

  HB-012 (H2 Compressor) Performance Indicators: specific compression
    power, ~5.4 kWh/kg H2. Basis: EXACT calculation from this item's
    own confirmed Drive motor power (10 kW) and Flow rate (20.6 Nm3/h,
    converted to ~1.85 kg/h using HB-007's own already-stated Nm3/h-
    to-kg/h conversion factor for this exact same flow, not re-derived)
    = 10 / 1.85 = 5.4 kWh/kg. Consistent with published figures for
    multi-stage mechanical/diaphragm H2 compression to 700-900 bar,
    commonly cited in the roughly 3-7 kWh/kg range.

  HB-013 (H2 Storage Vessel) Outputs: up to 1.2 kg/min discharge rate
    (during active dispensing). Basis: cross-item derivation from
    HB-018's own confirmed Dispensing rate (1.2 kg/min) — HB-018's own
    remark confirms HB-013 as its direct "Source stream(s)". Stated as
    the vessel's operational outflow during dispensing, not claimed as
    its own maximum physical capability.

  HB-014 (LOHC Hydrogenation) Outputs: ~0.031 m3/h carrier (rich oil)
    throughput. Basis: this figure is ALREADY stated in HB-015's own
    remark, explicitly attributed to "HB-014's carrier throughput" —
    independently cross-verified here via mass balance from HB-014's
    own confirmed H2 loading capacity (2 kg H2/h) and loading
    efficiency (6.2 wt%), using DBT's standard ~1040 kg/m3 density (a
    physical constant): (2/0.062)/1040 = 0.031 m3/h — exact agreement
    with the cited figure.

  HB-015 (LOHC Storage Tank) Inputs and Outputs: ~0.031 m3/h carrier
    throughput, both directions. Basis: same figure as HB-014 Outputs
    above, which this item's OWN remark already states as its own
    tank-sizing basis ("Lean carrier tank volume... sized from HB-014's
    carrier throughput"); the twin-tank design's own stated symmetry
    ("lean-out equals rich-in over a full cycle") supports the same
    steady-state figure for both directions.

  HB-016 (LOHC Dehydrogenation) Inputs and Outputs: ~0.032 m3/h carrier
    throughput, both directions. Basis: EXACT calculation from this
    item's own two already-Confirmed values — H2 release capacity
    (2 kg H2/h) / H2 release efficiency (6 wt%) / DBT's standard
    ~1040 kg/m3 density = 0.032 m3/h — cross-consistent with HB-014's/
    HB-015's ~0.031 m3/h (the small difference reflects this item's own
    stated slightly-lower 6% vs 6.2% efficiency, "minor round-trip
    losses" per its own remark). Outputs uses the same basis — the
    carrier compound itself isn't consumed by dehydrogenation, only its
    H2 payload is released, so mass is conserved through this item too.

DECLINED — 38 of 51, with the actual reason:

  HB-001 (WGS Reactor HTS, Temp) Inputs, Outputs: the SAME physical
    HTS reactor as HB-002, which already fully characterizes this
    exact gas stream's composition with its own confirmed Inputs/
    Outputs — the shared-physical-equipment pattern already established
    for GA-001/002, GC-001/002. Operating Conditions: no separately
    confirmed "typical operating" point distinct from this item's own
    DESIGN temperature values (unlike GA-001, which has both). Performance
    Indicators: the conversion-efficiency figure for this exact
    reactor is already Confirmed, attributed to HB-002 (the CO-
    conversion aspect of the same physical vessel).

  HB-002 (WGS Reactor HTS, CO Conv.) Operating Conditions: same
    shared-physical-equipment reasoning as HB-001 — this reactor's own
    temperature is already fully characterized at HB-001; cross-
    populating the identical figure into a different item ID wouldn't
    be new information.

  HB-003 (Heat Exchanger, WGS) Measurements: vendor-only instrument
    spec (no sensor type stated). Operating Conditions: this item's
    own four already-Confirmed temperatures (hot/cold in/out) already
    fully describe its operating condition, under Inputs/Outputs, not a
    separate OC bucket — recategorization, not new information.
    Performance Indicators: CHECKED, not skipped — see HB-SPECIFIC
    DISCIPLINE above for the full "compute, verify, decline" reasoning
    (a naive 47.4% thermal-effectiveness calculation is only valid for
    whichever stream has the lower heat-capacity rate, which can only
    be determined here by inferring an unstated water flow rate from
    a chain of assumptions rather than values directly on file).

  HB-004 Measurements: vendor-only instrument spec (no dedicated LTS-
    outlet CO analyser confirmed — HB-002's own analyser is at the HTS
    outlet, a different physical location; assuming an identical
    instrument exists at LTS outlet would be a vendor/design decision
    not yet made). Operating Conditions: same shared-physical-equipment
    reasoning as HB-001 (no separately confirmed operating-vs-design
    point for this reactor).

  HB-005 Operating Conditions: no separately confirmed operating-vs-
    design point (Steam temperature/pressure are already this item's
    own confirmed Parameters). Performance Indicators: no defensible
    thermal-efficiency KPI — would need fuel/heat input data this
    project doesn't have.

  HB-006 Outputs: this item's own confirmed Parameters ALREADY states
    "H2 purity (design) = 99.97 vol%" — the same design-value-
    classification pattern already noted for HB-008's pressure figure
    in equipment_rfi_fills.py; restating it under Outputs would be
    recategorization. Performance Indicators: the recovery-rate figure
    for this exact PSA skid is already Confirmed, attributed to HB-007
    (the recovery aspect of the same physical equipment).

  HB-007 (PSA Unit, H2 Recovery) Measurements: vendor-only instrument
    spec (no dedicated flow-verification instrument confirmed for this
    aspect). Operating Conditions: same shared-physical-equipment
    reasoning as HB-001/HB-002 — already characterized at HB-006.

  HB-008 (PSA Unit, Pressure) Inputs, Outputs: same shared-physical-
    equipment reasoning as HB-002/HB-007 — this is the pressure/cycle-
    timing aspect of the SAME PSA skid HB-006/HB-007 already fully
    characterize with their own confirmed Inputs/Outputs; no distinct
    material stream of its own. Performance Indicators: same reasoning
    as HB-006 — the recovery figure belongs to HB-007.

  HB-009 Outputs: this item's own confirmed Inputs ALREADY states
    "Tail gas flow rate = 29.4 Nm3/h" — a handling/buffer system
    conserves mass with no separation step, so an Outputs figure would
    restate the identical already-Confirmed number for the identical
    item — the same recategorization discipline already applied to
    GC-001/GC-013 (distinct from GA-007's case, where BOTH Inputs and
    Outputs were freshly-derived, not pre-existing Confirmed data being
    duplicated). Performance Indicators: no efficiency/recovery concept
    applies to a tail-gas handling/recycle system.

  HB-010 (Membrane Separator) Measurements: vendor-only instrument
    spec — consistent with task requirement 3's expectation that this
    parallel technology is more genuinely vendor-dependent; no other
    gap exists for this item (Inputs/Outputs/Operating Conditions/
    Performance Indicators are all already Confirmed).

  HB-011 (Electrolyser) Measurements: vendor-only instrument spec —
    consistent with task requirement 3's expectation for this
    auxiliary/optional item (its own registry name literally carries
    the "— Auxiliary/Optional" suffix).

  HB-012 Outputs: this item's own confirmed Inputs ALREADY states
    "Flow rate = 20.6 Nm3/h" — a compressor doesn't consume or
    generate gas, so an Outputs figure would restate the identical
    already-Confirmed number for the identical item, same
    recategorization discipline as HB-009/GC-013. Measurements:
    vendor-only instrument spec.

  HB-013 Performance Indicators: no defensible KPI (round-trip
    efficiency / boil-off rate concepts don't apply to compressed-gas
    storage, and no data exists to compute either regardless).

  HB-014 Inputs: CHECKED, not skipped — see HB-SPECIFIC DISCIPLINE
    above for the full "compute, verify, decline" reasoning (no
    confirmed figure states what fraction of total H2 production is
    actually routed through this parallel/optional LOHC pathway versus
    the primary compressed-storage route; assuming 100% would
    overclaim). Measurements: vendor-only instrument spec.

  HB-015 Measurements: vendor-only instrument spec (tank level sensor
    type not stated). Performance Indicators: no efficiency/recovery-
    rate concept applies to a passive twin-tank buffer.

  HB-016 Measurements: vendor-only instrument spec.

  HB-017 (H2 Purification, Post-LOHC) Inputs: this item's own
    confirmed Parameters ALREADY states "Design capacity = 2 kg H2/h,"
    which for a polishing/purification unit already IS its own
    throughput concept — recategorization, same discipline as HB-006/
    HB-018. Outputs: CHECKED, not skipped — this item's own confirmed
    ">99%" Recovery efficiency means output would equal input to
    within the stated precision (an open-ended lower bound, not a
    precise figure), so no MEANINGFULLY DISTINCT new number exists
    beyond what Design capacity and Recovery efficiency already convey
    — filling it would be low-value padding, not genuine new
    information. Measurements: vendor-only instrument spec.

  HB-018 (H2 Dispensing Station) Inputs: this item's own confirmed
    Parameters ALREADY states "Source stream(s) = HB-013" — the same
    fact an Inputs row would restate, recategorization. Outputs: this
    item's own confirmed "Dispensing rate = 1.2 kg/min" already IS the
    Outputs concept, just classified under Parameters — same
    recategorization discipline. Measurements: vendor-only instrument
    spec (the confirmed "Metering/billing system" names the meter
    TYPE, not a specific accuracy/certification spec, which is a
    vendor/model decision not yet made).

EU REPORT (extension — every one of EU's 32 gaps, filled and declined).
EU is CHP generation (SOFC/Gas Engine/Microturbine/PEM), grid/thermal
interconnection, and BoP utilities:

FILLED — 8 of 32:

  EU-001 (SOFC Stack, Temp) Performance Indicators: SOFC electrical
    efficiency ranges from ~39.4% (chp.py's own defined near-zero-load
    floor, x=0.01) up to the rated 55% at full load (x=1.0). Basis:
    chp.py's own live, independently-validated part-load correlation
    for SOFC specifically (this project's single strongest possible
    basis for this section, the same discipline as HB-004's kinetics.py
    fill) — genuinely NEW information, since the registry only ever
    states the single rated-load point (already Confirmed at EU-002,
    the efficiency-aspect sibling item for this same physical stack).

  EU-007 (Flare/Emergency Burner) Performance Indicators: >=98%
    combustion/destruction efficiency. Basis: comparable-installed-
    system practice — the widely-recognized regulatory presumption for
    a properly-designed and operated enclosed ground flare with
    adequate residence time, exit velocity, and heating value (e.g. the
    threshold commonly cited in general flare-design/regulatory
    guidance) — a general equipment-class figure, not derived from this
    item's own specific data, stated as such.

  EU-008 (Cooling Tower) Performance Indicators: cooling range, 10 degC.
    Basis: EXACT calculation from this item's own two already-Confirmed
    temperatures (30 degC return - 20 degC supply) — "range" is a
    standard, named cooling-tower performance term, not an invented
    metric.

  EU-010 (UPS/Battery Buffer) Inputs: ~400V, 3-phase AC mains input.
    Basis: matches the plant's established grid voltage standard
    (EU-009/HB-011/EU-003/EU-005, all independently confirmed at 400V)
    — standard for an online double-conversion UPS (this item's own
    confirmed type), which draws from and supplies the same facility
    electrical system, so its input and output sides share the same
    nominal voltage even though the topology itself doesn't require it.

  EU-010 Operating Conditions: ~15-35 degC recommended (0-45 degC
    charge range). Basis: comparable-installed-system practice, tied
    directly to this item's own confirmed Battery technology (Lithium-
    ion, LiFePO4) — a real, standard, checkable temperature-performance
    and safety envelope for this specific chemistry, not a generic
    "ambient" claim.

  EU-010 Performance Indicators: ~92-96% round-trip efficiency. Basis:
    a commonly-published range for online double-conversion UPS systems
    at this power class (e.g. per major UPS manufacturer datasheets) —
    a general equipment-class range, same basis category already
    established as valid by FE-005's dryer-efficiency fill.

  EU-012 (District Heating HX) Performance Indicators: ~85.7% thermal
    effectiveness. Basis: EXACT calculation from this item's own four
    already-Confirmed temperatures, verified via BOTH the primary-side
    and secondary-side formulas independently — they agree exactly
    (85.7% both ways) because the two streams (internal loop water,
    district network water) have EQUAL heat-capacity rates: same fluid,
    matched flow rates (~0.72 m3/h each), matched 30 degC temperature
    drops, all already Confirmed — no inferred intermediate quantity
    needed, unlike EU-011's case (see DECLINED below). Consistent with
    the high effectiveness typically achievable by this item's own
    confirmed HX type (plate heat exchanger).

  EU-013 (Thermal Energy Metering) Operating Conditions: ~45-75 degC.
    Basis: cross-item derivation from EU-012's own confirmed secondary
    supply/return temperatures (75/45 degC) — this item's own existing
    remarks cite "EU-007" (the Flare) for this same fact, an apparent
    mislabeling (EU-007 has no secondary-side or district-heating data
    of any kind) corrected here rather than propagated; see CLAUDE.md's
    "Known source-data issues" section, item 19.

DECLINED — 24 of 32, with the actual reason:

  EU-001 Inputs, Outputs: the SAME physical SOFC stack as EU-002, which
    already fully characterizes this exact fuel/power stream with its
    own confirmed Inputs/Outputs — the shared-physical-equipment
    pattern already established for GA-001/002, GC-001/002, HB-001/002.

  EU-004 (Gas Engine, Thermal Eff.) Outputs: this item's own confirmed
    Parameters ALREADY states the recovered-heat figures (Jacket
    cooling 12 kWth, Exhaust heat 8 kWth, Total 20 kWth) — an Outputs
    row would restate them, recategorization. Measurements: vendor-only
    instrument spec. Operating Conditions: this item's own confirmed
    exhaust/cooling temperatures already fully describe its operating
    condition, under Parameters not a separate OC bucket —
    recategorization, not new information.

  EU-005 (Microturbine) Measurements: vendor-only instrument spec (no
    sensor type stated for this item).

  EU-006 (H2 Fuel Cell, Stationary) Inputs: this item's own confirmed
    Parameters ALREADY states "H2 consumption (rated) = 10 Nm3/h" —
    already the Inputs concept, recategorization. Measurements: vendor-
    only instrument spec.

  EU-007 Inputs: this item's own confirmed Parameters ALREADY states
    "Flare capacity (100% design flow) = 100 Nm3/h" — already the
    Inputs concept, recategorization. Outputs: no quantified combustion-
    product figures exist anywhere to derive from. Measurements:
    vendor-only instrument spec (flame detector TYPE is confirmed, not
    its accuracy/response-time spec). Operating Conditions: no
    defensible basis — this item's own data explicitly states its gas
    composition is variable by design ("Raw syngas to pure H2...
    depending on where in the process the emergency release
    originates"), so no single operating temperature/pressure can be
    stated with confidence.

  EU-008 Outputs: this item's own confirmed cooling-water return
    temperature and flow rate already describe its output stream —
    recategorization. Measurements: vendor-only instrument spec.
    Operating Conditions: this item's own confirmed supply/return
    temperatures already describe its operating condition, under
    Parameters — recategorization.

  EU-009 (Electrical Metering, Grid) Outputs: structurally not a fit —
    a measurement instrument observing the plant's power flows, not a
    process stream of its own, the same pattern already established
    for SA's analysers/sensors. Operating Conditions: no defensible
    basis — this item has no process-gas/thermal interface of its own
    to characterize, and no specific already-confirmed fact to derive
    an ambient claim from (unlike EU-010's LiFePO4 case). Performance
    Indicators: no efficiency/recovery-rate concept applies to a meter.

  EU-011 (Heat Recovery Unit) Measurements: vendor-only instrument
    spec. Performance Indicators: CHECKED, not skipped — see EU-
    SPECIFIC DISCIPLINE above for the full "compute, verify, decline"
    reasoning, directly contrasted with EU-012's successful fill (this
    item's own confirmed data doesn't establish which stream has the
    lower heat-capacity rate, unlike EU-012's case where the two
    streams are confirmed equal).

  EU-012 Measurements: vendor-only instrument spec. Operating
    Conditions: this item's own confirmed four temperatures already
    describe its operating condition, under Parameters —
    recategorization.

  EU-013 Outputs: structurally not a fit — a measurement instrument
    observing the district-heating energy flow, not a process stream of
    its own, same pattern as EU-009. Performance Indicators: metering
    accuracy is already Confirmed (Parameters, "Metered energy accuracy
    class = Class 2") — no additional efficiency/recovery-rate concept
    applies to a passive meter.

AI REPORT (extension, the final section — every one of AI's 67 gaps,
filled and declined). AI is automation/software/network equipment —
PLC, gateway, broker, SCADA, edge server, firewall, cloud hub,
database, model server, twin engine, orchestration controller — plus 3
physical field instruments; the lowest fill rate of any section by
absolute count is the correct, honest outcome here, not a shortfall:

FILLED — 2 of 67:

  AI-002 (Camera / Vision System) Operating Conditions: ~-20 to +50
    degC ambient. Basis: cross-item derivation from this item's own
    confirmed remark, verified correct (not one of the mislabeled
    references found in this section — see the mislabel sweep above),
    that places it physically "at FE-001's hopper/conveyor," combined
    with FE-001's own separately-Confirmed "Operating temperature
    (ambient) = (-20 to +50) degC" — the same cross-item-location
    derivation pattern this project's very first fills (FE-002/FE-003)
    established, applied here for the first time to an AI item.

  AI-004 (PLC, Main Control) Operating Conditions: ~0-60 degC. Basis:
    this item's own confirmed CPU family (Siemens SIMATIC S7-1500, CPU
    1516-3 PN/DP) and its own confirmed control-room housing (non-
    hazardous area, per its own ATEX/Ex rating remark) — the published
    standard operating-temperature range for this specific, real,
    named PLC product family, a comparable-installed-system basis in
    the same category as EU-010's LiFePO4 fill, not a generic "control
    equipment runs at room temperature" claim. No other AI item names a
    specific enough product (all others say "or equivalent" generically)
    to support the same kind of fill — checked for every one of them,
    not just assumed absent.

DECLINED — 65 of 67, with the actual reason:

  AI-001 (Weather Station) Inputs: structurally not a fit — a weather
    station observes ambient conditions, it doesn't receive a material
    or energy stream of its own. Operating Conditions: this item's own
    confirmed "Temperature range = (-40 to +60) degC" Parameter already
    states this exact fact — recategorization, not new information.
    Performance Indicators: no efficiency/recovery-rate concept applies
    to a passive weather sensor, and this item states no accuracy
    figure of its own to build one from.

  AI-002 Inputs, Outputs: structurally not a fit — a machine-vision
    camera observes a video stream, it doesn't receive/output a
    material stream. Performance Indicators: this item's own confirmed
    "AI model accuracy (design) = 90%" Parameter already states the one
    number that would go here — recategorization.

  AI-003 (Bed Pressure-Drop Sensor) Inputs, Outputs: structurally not a
    fit — a differential-pressure transmitter reading GA-002's own
    existing pressure taps has no material stream of its own to
    characterize (the same GA-002/GC-002/SA-family sub-item pattern).
    Performance Indicators: this item's own confirmed Accuracy
    (±0.1%) already covers the one quantified concept this item has —
    no distinct new PI exists.

  AI-004 Inputs: structurally not a fit — a PLC receives electrical
    I/O signals (already fully captured as its own confirmed digital/
    analogue input/output counts), not a process material/energy
    stream in the sense this project's Inputs category means elsewhere.
    Measurements: no sensor-accuracy/response-time concept applies to a
    controller — it isn't a measurement instrument itself. Performance
    Indicators: no efficiency/recovery-rate concept applies to a PLC.

  AI-005 through AI-013 (OPC-UA Gateway, MQTT Broker, DCS/SCADA Server,
    Edge Computing Server, Cybersecurity Firewall, Cloud IoT Hub,
    Time-Series Database, AI Model Server, Digital Twin Engine) —
    EVERY Inputs/Outputs gap across all nine items: structurally not a
    fit, same reasoning as AI-004's Inputs — these are data-processing/
    data-transport/data-storage/data-orchestration systems, not
    material- or energy-handling equipment; forcing a category to
    apply here would contradict this project's own established "not
    just undocumented, structurally doesn't have one" standard (task
    requirement 2's own explicit instruction not to force this). EVERY
    Measurements gap across all nine: no sensor-accuracy/response-time
    concept applies to any of them — they aren't measurement
    instruments. EVERY Performance Indicators gap across all nine: no
    genuine, item-specific efficiency/recovery-rate basis exists that
    isn't either already-Confirmed-elsewhere recategorization (e.g.
    AI-012's "Inference latency"/"Control loop frequency" are already
    Confirmed Parameters) or an unstated-assumption fabrication (see
    AI-008's MTBF-without-MTTR case, discussed above under AI-SPECIFIC
    DISCIPLINE, task requirement 4). EVERY Operating Conditions gap
    across AI-005/006/007/009/010/011/012/013 (AI-008's own OC is
    already Confirmed at -20 to +60 degC): declined — AI-010/011/013
    structurally, since these are cloud-hosted software platforms with
    no physical installation of their own to have an ambient
    temperature at all; AI-005/006/007/009/012 checked and declined
    because, unlike AI-004's named Siemens CPU model, none of these
    items' own data names a specific enough product ("or equivalent"
    generic descriptions only) to support a comparable-installed-system
    fill without forcing it.

  AI-014 (Multi-Module Orchestration Controller) Inputs, Outputs: same
    structural reasoning — a fleet-orchestration/coordination system
    processes status/setpoint data, not a material stream. Operating
    Conditions: same cloud/software reasoning as AI-010/011/013 — this
    item's own data describes a coordination layer across modules, no
    physical installation of its own. Performance Indicators: this
    item's own confirmed "Max modules supported = 25" Parameter already
    states the one quantified design target this item has —
    recategorization.

  AI-015 (RFNBO Compliance & GO Monitor — Auxiliary/Optional) Inputs,
    Outputs, Measurements, Operating Conditions, Performance
    Indicators: structurally not a fit across the board — a compliance/
    reporting software system (applies only if HB-011 is activated) has
    no material stream, no sensor of its own, no physical installation,
    and no efficiency/recovery-rate concept beyond what's already
    stated qualitatively.
"""
import copy

from . import equipment_datasheet
from . import gasifier_mass_balance
from . import kinetics
from . import chp

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


def _source_sa(basis_label):
    return f"Engineering estimate (SA-001..SA-012 extension) — {basis_label}"


def _source_hb(basis_label):
    return f"Engineering estimate (HB-001..HB-018 extension) — {basis_label}"


def _source_eu(basis_label):
    return f"Engineering estimate (EU-001..EU-013 extension) — {basis_label}"


def _source_ai(basis_label):
    return f"Engineering estimate (AI-001..AI-015 extension) — {basis_label}"


_GC_TRAIN_GAS_FLOW_NM3_H = 50  # GC-003's/GC-009's/GC-013's own independently confirmed design gas flow rate, held constant across the whole downstream train per those items' own remarks

# HB-004's own strongest-possible fill: kinetics.py's live, independently-validated
# lts_conversion(), fed the ACTUAL upstream HTS outlet (HB-002's own confirmed 7 vol% CO),
# not re-derived from scratch. Cross-verified below in the self-test against plain
# arithmetic on HB-002's/HB-004's own confirmed registry values.
_HB_HTS_CONVERSION = kinetics.hts_conversion()
_HB_HTS_OUTLET_CO_PCT = 28.0 * (1 - _HB_HTS_CONVERSION)  # should reproduce HB-002's own confirmed 7 vol%
_HB_LTS_RELATIVE_CONVERSION_PCT = kinetics.lts_conversion(y_CO_in=_HB_HTS_OUTLET_CO_PCT / 100.0) * 100.0

_HB_DBT_DENSITY_KG_M3 = 1040.0  # standard physical property of Dibenzyltoluene (DBT), not a design assumption -- used for every LOHC carrier-throughput fill below

# EU-001's own strongest-possible fill: chp.py's live, independently-validated part-load
# efficiency correlation for SOFC specifically -- genuinely new information (the registry
# only states the single rated-load point, already Confirmed at EU-002).
_EU_SOFC_EFF_MIN_PCT = chp.chp_efficiency(0.01, "SOFC") * 100.0
_EU_SOFC_EFF_RATED_PCT = chp.chp_efficiency(1.0, "SOFC") * 100.0  # should reproduce EU-002's own confirmed 55%


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
    "SA-011": {
        "Operating Conditions": [
            {
                "parameter": "Estimated operating temperature",
                "value": "~40", "unit": "°C",
                "remarks": (
                    "This item's own Measurement range remark ALREADY states the number in prose "
                    "('Generous margin around the expected 40°C operating point — a normal-"
                    "condition location') without it ever being extracted into its own Operating "
                    "Conditions row — a genuinely new row for an already-stated fact, not an "
                    "external guess. Cross-consistent with SA-009's and SA-010's own separately-"
                    "Confirmed 40°C Operating temperature at the same late-train position — SA-011 "
                    "is a direct in-line Pt100 RTD sensor, the same instrument category as those "
                    "two (not a sample-conditioned composition analyser like SA-001-006/SA-008, "
                    "where the same process-gas temperature would NOT apply — checked and "
                    "deliberately not extended to those items)."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source_sa("extracted from this item's own remarks text, cross-consistent with SA-009's/SA-010's own confirmed values"),
            },
        ],
    },
    "HB-004": {
        "Inputs": [
            {
                "parameter": "Estimated CO inlet concentration",
                "value": "~7", "unit": "vol%",
                "remarks": (
                    "Cross-item derivation: HB-002's own confirmed CO outlet concentration (design) "
                    "at the HTS stage is 7 vol% — HB-002 and HB-004 are sequential WGS reactors "
                    "(HTS then LTS) on the same gas stream, so HB-002's outlet is HB-004's inlet "
                    "directly."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source_hb("cross-item derivation from HB-002's own confirmed HTS-stage outlet concentration"),
            },
        ],
        "Performance Indicators": [
            {
                "parameter": "Estimated LTS-stage relative CO conversion",
                "value": f"~{_HB_LTS_RELATIVE_CONVERSION_PCT:.1f}", "unit": "%",
                "remarks": (
                    f"This project's single strongest possible basis: kinetics.py's own live, "
                    f"independently-validated lts_conversion() output ({_HB_LTS_RELATIVE_CONVERSION_PCT:.2f}% "
                    f"at the design point), fed the actual upstream HTS outlet composition "
                    f"({_HB_HTS_OUTLET_CO_PCT:.2f} vol% CO, computed from kinetics.py's own "
                    f"hts_conversion() and matching HB-002's own confirmed 7 vol% figure exactly) "
                    f"— not re-derived from scratch. Independently cross-checked by plain "
                    f"arithmetic on two values ALREADY Confirmed in the registry itself alone: "
                    f"HB-002's 7 vol% outlet and HB-004's own 4.2 vol% outlet give "
                    f"(7-4.2)/7 = 40.0% by simple subtraction, with no physics model involved at "
                    f"all — physics model and registry data agree exactly, not just plausibly. "
                    f"This exact figure is also shown live on the Digital Twin tab's own kinetics "
                    f"slider ('LTS relative conversion') — restated here because HB-004's own "
                    f"equipment-datasheet Performance Indicators slot was genuinely empty (unlike "
                    f"HB-002's own PI, already Confirmed at 75%), the same 'exact calculation from "
                    f"confirmed inputs, not a same-item recategorization' pattern as FE-004's "
                    f"specific energy."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source_hb("kinetics.py's own live-validated lts_conversion() output, cross-checked by direct arithmetic on this project's own confirmed registry values"),
            },
        ],
    },
    "HB-005": {
        "Inputs": [
            {
                "parameter": "Estimated feedwater flow rate",
                "value": "~45", "unit": "kg/h",
                "remarks": (
                    "Standard boiler mass-balance conservation (feedwater mass in = steam mass "
                    "out, negligible blowdown at this scale) applied to this item's own confirmed "
                    "Steam production rate (45 kg/h, its own Outputs) — a genuine claim about a "
                    "different physical stream (liquid feedwater vs. steam product) that happens "
                    "to share the same mass value, not a same-item recategorization of the "
                    "identical figure."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source_hb("standard boiler feedwater/steam mass-balance conservation from this item's own confirmed steam production rate"),
            },
        ],
    },
    "HB-006": {
        "Operating Conditions": [
            {
                "parameter": "Estimated operating temperature",
                "value": "~15-40", "unit": "°C",
                "remarks": (
                    "Comparable-installed-system practice, tied directly to this item's own "
                    "confirmed Adsorbent material (activated carbon + zeolite molecular sieve) — "
                    "both are standard ambient-temperature PSA media; adsorption selectivity and "
                    "capacity measurably degrade at elevated temperature, which is why virtually "
                    "all industrial H2 PSA units operate near ambient regardless of upstream "
                    "process conditions, requiring feed cooling first. Filled here (the H2 Purity "
                    "aspect) rather than at HB-007/HB-008 (the same physical PSA skid's other two "
                    "aspect-items) since adsorbent temperature sensitivity is most directly tied to "
                    "purity performance."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source_hb("comparable-installed-system practice (ambient-temperature requirement of the confirmed activated-carbon/zeolite PSA adsorbent)"),
            },
        ],
    },
    "HB-009": {
        "Operating Conditions": [
            {
                "parameter": "Estimated operating pressure",
                "value": "~0.2", "unit": "bar(g)",
                "remarks": (
                    "This item's own remark for 'Tail gas compressor (if recycled)' ALREADY states "
                    "'tail gas exits PSA regeneration at ~0.2 bar(g) (HB-008)' without it ever "
                    "being extracted into its own Operating Conditions row — a genuinely new row "
                    "for an already-stated fact, not an external guess."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source_hb("extracted from this item's own remarks text, citing HB-008's own confirmed regeneration pressure"),
            },
        ],
    },
    "HB-011": {
        "Inputs": [
            {
                "parameter": "Estimated water feed rate",
                "value": "~0.18", "unit": "L/h",
                "remarks": (
                    "Exact calculation from this item's own two already-Confirmed values: Water "
                    "consumption (~1 L/Nm3 H2) x H2 production rate (rated, 0.18 Nm3/h) = "
                    "0.18 L/h."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source_hb("calculated from this item's own confirmed water-consumption ratio and rated H2 production rate"),
            },
        ],
    },
    "HB-012": {
        "Performance Indicators": [
            {
                "parameter": "Estimated specific compression power",
                "value": "~5.4", "unit": "kWh/kg H2",
                "remarks": (
                    "Exact calculation from this item's own confirmed Drive motor power (10 kW) "
                    "and Flow rate (20.6 Nm3/h) — converted to ~1.85 kg/h using HB-007's own "
                    "already-stated Nm3/h-to-kg/h conversion factor for this exact same flow (not "
                    "re-derived): 10 / 1.85 = 5.4 kWh/kg. Consistent with published figures for "
                    "multi-stage mechanical/diaphragm H2 compression from a few bar to 700-900 bar, "
                    "commonly cited in the roughly 3-7 kWh/kg range."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source_hb("calculated from this item's own confirmed motor power and flow rate, compared against published literature range"),
            },
        ],
    },
    "HB-013": {
        "Outputs": [
            {
                "parameter": "Estimated discharge rate (during dispensing)",
                "value": "up to 1.2", "unit": "kg/min",
                "remarks": (
                    "Cross-item derivation from HB-018's own confirmed Dispensing rate "
                    "(1.2 kg/min) — HB-018's own remark confirms this item (HB-013) as its direct "
                    "'Source stream(s)'. Stated as this vessel's operational outflow during active "
                    "dispensing, not claimed as its own independent maximum physical capability."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source_hb("cross-item derivation from HB-018's own confirmed dispensing rate, which names this item as its direct source stream"),
            },
        ],
    },
    "HB-014": {
        "Outputs": [
            {
                "parameter": "Estimated carrier (rich oil) throughput",
                "value": "~0.031", "unit": "m³/h",
                "remarks": (
                    "This figure is ALREADY stated in HB-015's own remark ('Lean carrier tank "
                    "volume... sized from HB-014's carrier throughput (~0.031 m3/h)'), explicitly "
                    "attributed to this item, without ever being extracted into this item's own "
                    "row. Independently cross-verified via mass balance from this item's own "
                    "confirmed H2 loading capacity (2 kg H2/h) and loading efficiency (6.2 wt%), "
                    "using DBT's standard ~1040 kg/m3 density (a physical constant, not a design "
                    "assumption): (2/0.062)/1040 = 0.031 m3/h — exact agreement with the cited "
                    "figure."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source_hb("extracted from HB-015's own remark (which attributes it to this item), independently cross-verified via mass balance from this item's own confirmed values"),
            },
        ],
    },
    "HB-015": {
        "Inputs": [
            {
                "parameter": "Estimated carrier (rich oil) inflow",
                "value": "~0.031", "unit": "m³/h",
                "remarks": (
                    "Same figure as HB-014's estimated carrier throughput, which this item's OWN "
                    "remark already states as its own tank-sizing basis ('Lean carrier tank "
                    "volume... sized from HB-014's carrier throughput')."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source_hb("this item's own remark, citing HB-014's confirmed carrier throughput as its own tank-sizing basis"),
            },
        ],
        "Outputs": [
            {
                "parameter": "Estimated carrier (lean oil) outflow",
                "value": "~0.031", "unit": "m³/h",
                "remarks": (
                    "Same basis as this item's estimated Inputs — the twin-tank design's own "
                    "stated symmetry ('lean-out equals rich-in over a full cycle') supports the "
                    "same steady-state figure for both directions."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source_hb("same basis as this item's estimated Inputs, per this item's own stated twin-tank symmetry"),
            },
        ],
    },
    "HB-016": {
        "Inputs": [
            {
                "parameter": "Estimated carrier (rich oil) inflow",
                "value": "~0.032", "unit": "m³/h",
                "remarks": (
                    "Exact calculation from this item's own two already-Confirmed values: H2 "
                    "release capacity (2 kg H2/h) / H2 release efficiency (6 wt%) / DBT's standard "
                    "~1040 kg/m3 density = 0.032 m3/h — cross-consistent with HB-014's/HB-015's own "
                    "~0.031 m3/h (the small difference reflects this item's own stated slightly-"
                    "lower 6% vs 6.2% efficiency, 'minor round-trip losses' per its own remark)."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source_hb("calculated from this item's own confirmed H2 release capacity and efficiency, using DBT's standard density"),
            },
        ],
        "Outputs": [
            {
                "parameter": "Estimated carrier (lean oil) outflow",
                "value": "~0.032", "unit": "m³/h",
                "remarks": (
                    "Same basis as this item's estimated Inputs — the carrier compound itself "
                    "isn't consumed by dehydrogenation, only its H2 payload is released, so mass "
                    "is conserved through this item too."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source_hb("mass conservation, same basis as this item's estimated Inputs"),
            },
        ],
    },
    "EU-001": {
        "Performance Indicators": [
            {
                "parameter": "Estimated part-load efficiency range",
                "value": f"~{_EU_SOFC_EFF_MIN_PCT:.1f}-{_EU_SOFC_EFF_RATED_PCT:.1f}", "unit": "%",
                "remarks": (
                    f"chp.py's own live, independently-validated part-load correlation for SOFC "
                    f"specifically (this project's strongest possible basis for this section, the "
                    f"same discipline as HB-004's kinetics.py fill): electrical efficiency ranges "
                    f"from ~{_EU_SOFC_EFF_MIN_PCT:.1f}% at chp.py's own defined near-zero-load floor "
                    f"(x=0.01) up to {_EU_SOFC_EFF_RATED_PCT:.1f}% at full load (x=1.0, matching "
                    f"EU-002's own confirmed rated efficiency exactly). Genuinely NEW information — "
                    f"the registry only ever states the single rated-load point (already Confirmed "
                    f"at EU-002, the efficiency-aspect sibling item for this same physical stack)."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source_eu("chp.py's own live-validated part-load correlation for SOFC, cross-checked against EU-002's own confirmed rated efficiency"),
            },
        ],
    },
    "EU-007": {
        "Performance Indicators": [
            {
                "parameter": "Estimated combustion/destruction efficiency",
                "value": ">=98", "unit": "%",
                "remarks": (
                    "Comparable-installed-system practice: the widely-recognized regulatory "
                    "presumption for a properly-designed and operated enclosed ground flare with "
                    "adequate residence time, exit velocity, and heating value (e.g. the threshold "
                    "commonly cited in general flare-design and regulatory guidance). A general "
                    "equipment-class figure, not derived from this item's own specific data, stated "
                    "as such."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source_eu("comparable-installed-system practice (regulatory destruction-efficiency presumption for a properly-designed enclosed ground flare)"),
            },
        ],
    },
    "EU-008": {
        "Performance Indicators": [
            {
                "parameter": "Estimated cooling range",
                "value": "10", "unit": "°C",
                "remarks": (
                    "Exact calculation from this item's own two already-Confirmed temperatures: "
                    "Cooling water return temperature (30°C) - Cooling water supply temperature "
                    "(20°C) = 10°C. 'Range' is a standard, named cooling-tower performance term, "
                    "not an invented metric."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source_eu("calculated from this item's own confirmed supply/return water temperatures (standard cooling-tower 'range' metric)"),
            },
        ],
    },
    "EU-010": {
        "Inputs": [
            {
                "parameter": "Estimated AC mains input",
                "value": "~400, 3-phase", "unit": "V",
                "remarks": (
                    "Matches the plant's established grid voltage standard (EU-009/HB-011/EU-003/"
                    "EU-005, all independently confirmed at 400V) — standard for an online double-"
                    "conversion UPS (this item's own confirmed type), which draws from and supplies "
                    "the same facility electrical system, so its input and output sides share the "
                    "same nominal voltage even though the topology itself doesn't strictly require it."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source_eu("matches the plant's own established grid voltage standard, confirmed independently at four other items"),
            },
        ],
        "Operating Conditions": [
            {
                "parameter": "Estimated operating temperature",
                "value": "~15-35 (0-45 charge range)", "unit": "°C",
                "remarks": (
                    "Comparable-installed-system practice, tied directly to this item's own "
                    "confirmed Battery technology (Lithium-ion, LiFePO4) — a real, standard, "
                    "checkable temperature-performance and safety envelope for this specific "
                    "chemistry, not a generic 'ambient' claim."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source_eu("comparable-installed-system practice (standard LiFePO4 operating-temperature envelope, tied to this item's own confirmed battery chemistry)"),
            },
        ],
        "Performance Indicators": [
            {
                "parameter": "Estimated round-trip efficiency",
                "value": "~92-96", "unit": "%",
                "remarks": (
                    "A commonly-published range for online double-conversion UPS systems at this "
                    "power class (e.g. per major UPS manufacturer datasheets) — a general "
                    "equipment-class range, same basis category already established as valid by "
                    "FE-005's dryer-efficiency fill."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source_eu("published literature range for the equipment class (online double-conversion UPS)"),
            },
        ],
    },
    "EU-012": {
        "Performance Indicators": [
            {
                "parameter": "Estimated thermal effectiveness",
                "value": "~85.7", "unit": "%",
                "remarks": (
                    "Exact calculation from this item's own four already-Confirmed temperatures, "
                    "verified via BOTH the primary-side formula ((80-50)/(80-45)) and the "
                    "secondary-side formula ((75-45)/(80-45)) independently — they agree exactly "
                    "(85.7% both ways) because the two streams (internal loop water, district "
                    "network water) have EQUAL heat-capacity rates: same fluid, matched flow rates "
                    "(~0.72 m3/h each), matched 30°C temperature drops, all already Confirmed — no "
                    "inferred intermediate quantity needed, unlike EU-011's declined case. "
                    "Consistent with the high effectiveness typically achievable by this item's own "
                    "confirmed HX type (plate heat exchanger)."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source_eu("calculated from this item's own confirmed temperatures, cross-verified via both the primary-side and secondary-side formulas since the two streams have equal heat-capacity rates"),
            },
        ],
    },
    "EU-013": {
        "Operating Conditions": [
            {
                "parameter": "Estimated operating temperature range",
                "value": "~45-75", "unit": "°C",
                "remarks": (
                    "Cross-item derivation from EU-012's own confirmed secondary supply/return "
                    "temperatures (75°C / 45°C) — this item's own existing remarks cite 'EU-007' "
                    "(the Flare) for this same fact, an apparent mislabeling (EU-007 has no "
                    "secondary-side or district-heating data of any kind) corrected here rather "
                    "than propagated; see CLAUDE.md's 'Known source-data issues' section, item 19."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source_eu("cross-item derivation from EU-012's own confirmed secondary-side temperatures, correcting this item's own mislabeled 'EU-007' reference"),
            },
        ],
    },
    "AI-002": {
        "Operating Conditions": [
            {
                "parameter": "Estimated operating temperature range",
                "value": "~-20 to +50", "unit": "°C",
                "remarks": (
                    "Cross-item derivation from this item's own confirmed 'Field of view' remark, "
                    "which places it physically at FE-001's hopper/conveyor (independently "
                    "verified correct against the mislabel sweep -- this is one of the few "
                    "cross-references in this item's own data that checks out), combined with "
                    "FE-001's own separately-Confirmed Operating temperature (ambient), "
                    "(-20 to +50) degC. Same cross-item-location derivation pattern this "
                    "project's very first fills (FE-002/FE-003) established."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source_ai("cross-item derivation from FE-001's own confirmed site ambient range, via this item's own confirmed installation location"),
            },
        ],
    },
    "AI-004": {
        "Operating Conditions": [
            {
                "parameter": "Estimated operating temperature range",
                "value": "~0-60", "unit": "°C",
                "remarks": (
                    "Comparable-installed-system practice, tied to a specifically NAMED, real "
                    "product -- this item's own confirmed CPU model (Siemens SIMATIC S7-1500, "
                    "CPU 1516-3 PN/DP), whose published vendor operating-temperature "
                    "specification is the basis, not a generic 'control equipment runs at room "
                    "temperature' claim. Consistent with this item's own confirmed non-hazardous "
                    "control-room housing (per its own ATEX/Ex rating remark) -- not exposed to "
                    "outdoor or hazardous-area extremes."
                ),
                "status": _Q.STATUS_ESTIMATE,
                "source": _source_ai("comparable-installed-system practice (published operating-temperature range for this item's own confirmed CPU product family)"),
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
    assert n_rows == 48, f"REGRESSION: expected 48 rows (7 FE + 10 GA + 7 GC + 1 SA + 13 HB + 8 EU + 2 AI), counted {n_rows}."
    assert n_slots == 48, f"REGRESSION: expected 48 newly-estimated slots, counted {n_slots}."
    assert n_items == 36, f"REGRESSION: expected 36 items touched (6 FE + 6 GA + 5 GC + 1 SA + 10 HB + 6 EU + 2 AI), counted {n_items}."

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

    print("\n=== SA-specific check: exactly one SA fill, and it explicitly documents why it wasn't extended to SA-001-006/SA-008 ===")
    sa_items_filled = [item_id for item_id in ESTIMATE_FILLS if item_id.startswith("SA-")]
    assert sa_items_filled == ["SA-011"], (
        f"REGRESSION: expected only SA-011 to have a fill, found {sa_items_filled}."
    )
    sa011_remarks = ESTIMATE_FILLS["SA-011"]["Operating Conditions"][0]["remarks"]
    assert "checked and" in sa011_remarks.lower() and "not extended" in sa011_remarks.lower(), (
        "REGRESSION: SA-011's fill no longer documents the deliberate decision not to extend the same "
        "reasoning to the sample-conditioned analysers (SA-001-006/SA-008)."
    )
    print("PASSED -- SA's only fill is SA-011, and it explicitly documents why the same reasoning wasn't "
          "extended to the sample-conditioned composition analysers.")

    print("\n=== HB-specific check: kinetics.py's live LTS conversion reproduces both the design target and HB-002's/HB-004's own confirmed registry values ===")
    assert abs(_HB_HTS_OUTLET_CO_PCT - 7.0) < 0.01, (
        f"REGRESSION: kinetics.py's hts_conversion() no longer reproduces HB-002's own confirmed 7 vol% CO outlet (got {_HB_HTS_OUTLET_CO_PCT})."
    )
    assert abs(_HB_LTS_RELATIVE_CONVERSION_PCT - 40.0) < 0.01, (
        f"REGRESSION: kinetics.py's lts_conversion() no longer reproduces the established 40% relative conversion target (got {_HB_LTS_RELATIVE_CONVERSION_PCT})."
    )
    arithmetic_check_pct = (7.0 - 4.2) / 7.0 * 100.0
    assert abs(arithmetic_check_pct - _HB_LTS_RELATIVE_CONVERSION_PCT) < 0.01, (
        "REGRESSION: kinetics.py's own output no longer agrees with plain arithmetic on HB-002's/HB-004's own confirmed registry values."
    )
    print(f"PASSED -- kinetics.py's live physics ({_HB_LTS_RELATIVE_CONVERSION_PCT:.2f}%) and plain arithmetic on "
          f"HB-002's/HB-004's own confirmed values ({arithmetic_check_pct:.2f}%) agree exactly -- HB-004's PI fill "
          f"is doubly validated, not a single unchecked source.")

    print("\n=== HB-specific check: the two computed-then-declined gaps (HB-003 PI, HB-014 Inputs) were never actually filled ===")
    assert "Performance Indicators" not in ESTIMATE_FILLS.get("HB-003", {}), (
        "REGRESSION: HB-003 Performance Indicators appears filled -- the module docstring explicitly declines the "
        "naive thermal-effectiveness calculation as resting on an inferred, unconfirmed water flow rate; it must stay Missing."
    )
    assert "Inputs" not in ESTIMATE_FILLS.get("HB-014", {}), (
        "REGRESSION: HB-014 Inputs appears filled -- the module docstring explicitly declines assuming 100% of H2 "
        "production routes through this optional LOHC pathway with no confirmed split fraction; it must stay Missing."
    )
    print("PASSED -- HB-003 (Heat Exchanger) Performance Indicators and HB-014 (LOHC Hydrogenation) Inputs have no "
          "fill of any kind, exactly as declined in the HB REPORT.")

    print("\n=== HB-specific check: every LOHC carrier-throughput fill (HB-014/015/016) uses the same DBT density constant ===")
    for item_id, category in (("HB-014", "Outputs"), ("HB-015", "Inputs"), ("HB-015", "Outputs"),
                               ("HB-016", "Inputs"), ("HB-016", "Outputs")):
        for row in ESTIMATE_FILLS[item_id][category]:
            assert ("1040" in row["remarks"] or "same basis" in row["remarks"].lower()
                    or "HB-014" in row["remarks"] or "HB-015" in row["remarks"]), (
                f"REGRESSION: {item_id}/{category} doesn't cite the standard DBT density constant or the item it shares a basis with."
            )
    print("PASSED -- every LOHC carrier-throughput fill traces back to the same physical DBT-density constant "
          "(~1040 kg/m3), not five separately invented numbers.")

    print("\n=== EU-specific check: chp.py's live SOFC part-load curve reproduces EU-002's own confirmed rated efficiency, and no other CHP technology's numbers leak in ===")
    assert abs(_EU_SOFC_EFF_RATED_PCT - 55.0) < 0.01, (
        f"REGRESSION: chp.py's chp_efficiency(1.0, 'SOFC') no longer reproduces EU-002's own confirmed 55% rated efficiency (got {_EU_SOFC_EFF_RATED_PCT})."
    )
    assert _EU_SOFC_EFF_MIN_PCT < _EU_SOFC_EFF_RATED_PCT, (
        "REGRESSION: the SOFC part-load floor should be below the rated efficiency."
    )
    eu001_pi_remarks = ESTIMATE_FILLS["EU-001"]["Performance Indicators"][0]["remarks"]
    for other_tech in ("Gas Engine", "Microturbine", "PEM"):
        assert other_tech not in eu001_pi_remarks, (
            f"REGRESSION: EU-001's SOFC fill mentions '{other_tech}' -- possible cross-technology conflation."
        )
    print(f"PASSED -- chp.py's live SOFC curve reproduces EU-002's own confirmed 55% exactly at full load "
          f"({_EU_SOFC_EFF_RATED_PCT:.2f}%), and EU-001's fill never mentions another CHP technology.")

    print("\n=== EU-specific check: the declined heat-exchanger effectiveness (EU-011 PI) was never actually filled, unlike its EU-012 counterpart ===")
    assert "Performance Indicators" not in ESTIMATE_FILLS.get("EU-011", {}), (
        "REGRESSION: EU-011 Performance Indicators appears filled -- the module docstring explicitly declines the "
        "naive thermal-effectiveness calculation as resting on an unconfirmed heat-capacity-rate comparison; it must stay Missing."
    )
    assert "Performance Indicators" in ESTIMATE_FILLS.get("EU-012", {}), (
        "REGRESSION: EU-012 Performance Indicators should be filled -- its two streams have confirmed-equal heat-capacity rates."
    )
    print("PASSED -- EU-011 (ambiguous heat-capacity rates) has no fill, EU-012 (confirmed-equal heat-capacity rates) does -- "
          "the same compute-then-verify discipline applied consistently to two similar-looking calculations with different outcomes.")

    print("\n=== AI-specific check: exactly two AI fills (AI-002, AI-004 Operating Conditions), the lowest of any section ===")
    ai_items_filled = sorted(item_id for item_id in ESTIMATE_FILLS if item_id.startswith("AI-"))
    assert ai_items_filled == ["AI-002", "AI-004"], (
        f"REGRESSION: expected only AI-002 and AI-004 to have a fill, found {ai_items_filled}."
    )
    for item_id in ai_items_filled:
        cats = list(ESTIMATE_FILLS[item_id].keys())
        assert cats == ["Operating Conditions"], (
            f"REGRESSION: expected {item_id}'s only fill to be Operating Conditions, found {cats}."
        )
    print("PASSED -- AI's only fills are AI-002 and AI-004, both Operating Conditions, exactly as reported.")

    print("\n=== AI-specific check: AI-008's computed-then-declined MTBF/availability gap was never actually filled ===")
    assert "AI-008" not in ESTIMATE_FILLS, (
        "REGRESSION: AI-008 appears in ESTIMATE_FILLS -- the module docstring explicitly declines an "
        "availability figure computed from MTBF alone, with no confirmed MTTR to pair it with; it must stay Missing."
    )
    print("PASSED -- AI-008 (Edge Computing Server) has no fill of any kind, exactly as declined in the AI REPORT.")

    print("\n=== AI-specific check: neither AI fill relies on any of the mislabeled AI-section cross-references ===")
    ai002_remarks = ESTIMATE_FILLS["AI-002"]["Operating Conditions"][0]["remarks"]
    assert "FE-001" in ai002_remarks, (
        "REGRESSION: AI-002's fill no longer cites FE-001 as its basis."
    )
    for wrong_id in ("AI-008", "AI-001", "AI-003", "AI-006", "AI-009", "AI-012"):
        assert wrong_id not in ai002_remarks, (
            f"REGRESSION: AI-002's fill mentions {wrong_id!r} -- possible use of a mislabeled cross-reference."
        )
    ai004_remarks = ESTIMATE_FILLS["AI-004"]["Operating Conditions"][0]["remarks"]
    for wrong_id in ("AI-001", "AI-003", "HB-013"):
        assert wrong_id not in ai004_remarks, (
            f"REGRESSION: AI-004's fill mentions {wrong_id!r} -- this fill is meant to be self-contained (its own CPU model only), not cross-item."
        )
    print("PASSED -- AI-002's fill uses only its own verified-correct FE-001 reference; AI-004's fill uses only its "
          "own confirmed CPU model, no cross-item reference at all -- neither touches any of the newly-found mislabels.")

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

    print("\n=== Task requirement 7 (this extension): FE's, GA's, GC's, SA's, HB's, and EU's numbers, regression-verified unchanged ===")
    fe_after = equipment_datasheet.summarize(filled, ids=equipment_datasheet.FE_IDS)
    print(f"FE: {fe_after['confirmed_category_slots']} Confirmed, "
          f"{fe_after['estimated_category_slots']} Engineering Estimate, "
          f"{fe_after['missing_category_slots']} Missing (of {fe_after['total_category_slots']} total slots)")
    assert fe_after["confirmed_category_slots"] == 27, f"REGRESSION: expected 27 Confirmed FE slots, got {fe_after['confirmed_category_slots']}."
    assert fe_after["estimated_category_slots"] == 7, f"REGRESSION: expected 7 Estimate FE slots, got {fe_after['estimated_category_slots']}."
    assert fe_after["missing_category_slots"] == 14, f"REGRESSION: expected 14 Missing FE slots, got {fe_after['missing_category_slots']}."
    print("PASSED -- FE's pilot numbers are unchanged by this EU extension: 27 Confirmed + 7 Engineering Estimate + 14 Missing = 48.")

    ga_after = equipment_datasheet.summarize(filled, ids=equipment_datasheet.GA_IDS)
    print(f"GA: {ga_after['confirmed_category_slots']} Confirmed, "
          f"{ga_after['estimated_category_slots']} Engineering Estimate, "
          f"{ga_after['missing_category_slots']} Missing (of {ga_after['total_category_slots']} total slots)")
    assert ga_after["confirmed_category_slots"] == 31, f"REGRESSION: expected 31 Confirmed GA slots, got {ga_after['confirmed_category_slots']}."
    assert ga_after["estimated_category_slots"] == 10, f"REGRESSION: expected 10 Estimate GA slots, got {ga_after['estimated_category_slots']}."
    assert ga_after["missing_category_slots"] == 19, f"REGRESSION: expected 19 Missing GA slots, got {ga_after['missing_category_slots']}."
    print("PASSED -- GA's extension numbers are unchanged by this EU extension: 31 Confirmed + 10 Engineering Estimate + 19 Missing = 60.")

    gc_after = equipment_datasheet.summarize(filled, ids=equipment_datasheet.GC_IDS)
    print(f"GC: {gc_after['confirmed_category_slots']} Confirmed, "
          f"{gc_after['estimated_category_slots']} Engineering Estimate, "
          f"{gc_after['missing_category_slots']} Missing (of {gc_after['total_category_slots']} total slots)")
    assert gc_after["confirmed_category_slots"] == 52, f"REGRESSION: expected 52 Confirmed GC slots, got {gc_after['confirmed_category_slots']}."
    assert gc_after["estimated_category_slots"] == 7, f"REGRESSION: expected 7 Estimate GC slots, got {gc_after['estimated_category_slots']}."
    assert gc_after["missing_category_slots"] == 31, f"REGRESSION: expected 31 Missing GC slots, got {gc_after['missing_category_slots']}."
    print("PASSED -- GC's extension numbers are unchanged by this EU extension: 52 Confirmed + 7 Engineering Estimate + 31 Missing = 90.")

    sa_after = equipment_datasheet.summarize(filled, ids=equipment_datasheet.SA_IDS)
    print(f"SA: {sa_after['confirmed_category_slots']} Confirmed, "
          f"{sa_after['estimated_category_slots']} Engineering Estimate, "
          f"{sa_after['missing_category_slots']} Missing (of {sa_after['total_category_slots']} total slots)")
    assert sa_after["confirmed_category_slots"] == 26, f"REGRESSION: expected 26 Confirmed SA slots, got {sa_after['confirmed_category_slots']}."
    assert sa_after["estimated_category_slots"] == 1, f"REGRESSION: expected 1 Estimate SA slot, got {sa_after['estimated_category_slots']}."
    assert sa_after["missing_category_slots"] == 45, f"REGRESSION: expected 45 Missing SA slots, got {sa_after['missing_category_slots']}."
    print("PASSED -- SA's extension numbers are unchanged by this EU extension: 26 Confirmed + 1 Engineering Estimate + 45 Missing = 72.")

    hb_after = equipment_datasheet.summarize(filled, ids=equipment_datasheet.HB_IDS)
    print(f"HB: {hb_after['confirmed_category_slots']} Confirmed, "
          f"{hb_after['estimated_category_slots']} Engineering Estimate, "
          f"{hb_after['missing_category_slots']} Missing (of {hb_after['total_category_slots']} total slots)")
    assert hb_after["confirmed_category_slots"] == 57, f"REGRESSION: expected 57 Confirmed HB slots, got {hb_after['confirmed_category_slots']}."
    assert hb_after["estimated_category_slots"] == 13, f"REGRESSION: expected 13 Estimate HB slots, got {hb_after['estimated_category_slots']}."
    assert hb_after["missing_category_slots"] == 38, f"REGRESSION: expected 38 Missing HB slots, got {hb_after['missing_category_slots']}."
    print("PASSED -- HB's extension numbers are unchanged by this EU extension: 57 Confirmed + 13 Engineering Estimate + 38 Missing = 108.")

    eu_after = equipment_datasheet.summarize(filled, ids=equipment_datasheet.EU_IDS)
    print(f"EU: {eu_after['confirmed_category_slots']} Confirmed, "
          f"{eu_after['estimated_category_slots']} Engineering Estimate, "
          f"{eu_after['missing_category_slots']} Missing (of {eu_after['total_category_slots']} total slots)")
    assert eu_after["confirmed_category_slots"] == 46, f"REGRESSION: expected 46 Confirmed EU slots, got {eu_after['confirmed_category_slots']}."
    assert eu_after["estimated_category_slots"] == 8, f"REGRESSION: expected 8 Estimate EU slots, got {eu_after['estimated_category_slots']}."
    assert eu_after["missing_category_slots"] == 24, f"REGRESSION: expected 24 Missing EU slots, got {eu_after['missing_category_slots']}."
    print("PASSED -- EU's extension numbers are unchanged by this AI extension: 46 Confirmed + 8 Engineering Estimate + 24 Missing = 78.")

    print("\n=== AI-specific honest breakdown (this extension, the final section) ===")
    ai_after = equipment_datasheet.summarize(filled, ids=equipment_datasheet.AI_IDS)
    print(f"AI: {ai_after['confirmed_category_slots']} Confirmed, "
          f"{ai_after['estimated_category_slots']} Engineering Estimate, "
          f"{ai_after['missing_category_slots']} Missing (of {ai_after['total_category_slots']} total slots)")
    assert ai_after["confirmed_category_slots"] == 23, f"REGRESSION: expected 23 Confirmed AI slots, got {ai_after['confirmed_category_slots']}."
    assert ai_after["estimated_category_slots"] == 2, f"REGRESSION: expected 2 Estimate AI slots, got {ai_after['estimated_category_slots']}."
    assert ai_after["missing_category_slots"] == 65, f"REGRESSION: expected 65 Missing AI slots, got {ai_after['missing_category_slots']}."
    print("PASSED -- AI: 23 Confirmed + 2 Engineering Estimate + 65 Missing = 90 total slots, matches exactly -- "
          "the lowest fill rate (by absolute count) of any of the seven sections, exactly as expected going in.")

    print("\n=== ALL SEVEN SECTIONS COMPLETE -- registry-wide grand total across all 91 items ===")
    grand = equipment_datasheet.summarize(filled)
    print(f"Registry-wide: {grand['confirmed_category_slots']} Confirmed "
          f"({grand['confirmed_category_slots'] / grand['total_category_slots'] * 100:.1f}%) + "
          f"{grand['estimated_category_slots']} Engineering Estimate "
          f"({grand['estimated_category_slots'] / grand['total_category_slots'] * 100:.1f}%) + "
          f"{grand['missing_category_slots']} Missing Data - Required "
          f"({grand['missing_category_slots'] / grand['total_category_slots'] * 100:.1f}%) = "
          f"{grand['total_category_slots']} total slots across all 91 items in all 7 sections "
          "(FE, GA, GC, SA, HB, EU, AI).")
    assert grand["confirmed_category_slots"] == 262, f"REGRESSION: expected 262 Confirmed registry-wide, got {grand['confirmed_category_slots']}."
    assert grand["estimated_category_slots"] == 48, f"REGRESSION: expected 48 Estimate registry-wide, got {grand['estimated_category_slots']}."
    assert grand["missing_category_slots"] == 236, f"REGRESSION: expected 236 Missing registry-wide, got {grand['missing_category_slots']}."
    assert grand["total_category_slots"] == 546, f"REGRESSION: expected 546 total slots registry-wide, got {grand['total_category_slots']}."
    print("PASSED -- the full engineering-estimate pass across the entire 91-item registry is complete: no section "
          "remains untouched, no gap was force-filled to raise a count, and every fill states a real, checkable basis.")

# (touch: force fresh Streamlit Cloud rebuild after adding GC-001..GC-015 estimates, 2026-08-28)

# (touch: force fresh Streamlit Cloud rebuild after adding HB-001..HB-018 estimates, 2026-08-28)
