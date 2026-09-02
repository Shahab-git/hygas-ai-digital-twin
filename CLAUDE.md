# HYGAS-AI Digital Twin — Project Context for Claude Code

## What this project is

A digital twin for a municipal-solid-waste (MSW) gasification plant that
produces hydrogen via water-gas-shift conversion, PSA purification, and
CHP utilisation. NACHIP pilot project (DOK-ING d.o.o., Zagreb, Croatia).

Two parallel implementations are planned and should both be maintained:
- **MATLAB/Simulink** (`/matlab`) — the rigorous, engineering-grade physics
  model. This is intended as the validated source of truth for every number
  below, once built.
- **Python** (`/python`) — verified cross-check implementations of the same
  physics, used as the backend for a live Streamlit dashboard, since
  Streamlit Cloud can't run Simulink.

`/matlab` doesn't exist yet in this repo. `/python` now exists, but only
covers the WGS/PSA/CHP/dispatch subset below — the gasifier, gas cleaning,
and interstage HX are not yet implemented in either language. When adding
a new physics module, implement it in both languages and cross-check that
they agree numerically before considering it done.

## Repository structure (verified against actual code)

- `app.py` — Streamlit dashboard entry point. Interactive WGS kinetics
  and PSA recovery (recompute on every slider move), on-demand CHP
  dispatch GA (button-triggered, since 150 generations takes a few
  seconds), and a static validated-milestones reference table.
- `python/kinetics.py` — `hts_conversion()` / `lts_conversion()`. Finite
  volume integration of Arrhenius/Van't Hoff WGS kinetics (Moe 1962
  equilibrium correlation) for the Fe-Cr (HTS) and Cu/ZnO/Al2O3 (LTS)
  catalysts — separate `Ea`/`k0` per stage, so the LTS-reusing-HTS-kinetics
  bug noted below cannot recur structurally.
- `python/psa.py` — `psa_recovery()`. Selectivity + pressure-ratio
  correlation (Ruthven/Farooq/Knaebel), explicitly documented in-file as
  a first-pass design heuristic, not a full multi-bed cycle simulation.
- `python/chp.py` — `chp_efficiency()`. Empirical part-load curves for
  SOFC, Gas Engine, Microturbine, and PEM Fuel Cell, each reducing to its
  rated efficiency at load_factor=1.0.
- `python/dispatch_ga.py` — `run_dispatch_ga()`. Genetic algorithm
  (tournament selection, blend crossover, Gaussian mutation) dispatching
  the 4 CHP units under separate syngas/H2 fuel budgets.
- `requirements.txt` — `streamlit`, `numpy`.

## Validated milestones

The WGS/PSA/CHP rows are now confirmed live in this repo's Python code
(each module's `__main__` block reproduces its target exactly; `app.py`
runs end-to-end under `streamlit run`, checked 2026-08-25). The gasifier,
gas cleaning, and interstage HX rows are prior MATLAB/Simulink results —
targets for future implementation, not yet built here in either language.

| Subsystem | Result | Target | Live in this repo? |
|---|---|---|---|
| Gasifier mass balance | 46.88 kg/h | 46.9 kg/h | No — not yet built |
| Gas cleaning | 45.94 kg/h | ~45.9 kg/h | No — not yet built |
| WGS HTS (Arrhenius/Van't Hoff kinetics, Fe-Cr catalyst) | 75.0% conversion | 75.0% | Yes — `python/kinetics.py` |
| Interstage HX | 4.134 kW | ~4.1 kW | No — not yet built |
| WGS LTS (Cu/ZnO/Al2O3 catalyst) | 40.0% relative conversion | 40.0% | Yes — `python/kinetics.py` |
| WGS overall | 85.0% | 85.0% | Yes — `python/kinetics.py` |
| PSA recovery (selectivity + pressure-ratio correlation) | 75.0% | 75.0% | Yes — `python/psa.py` |
| CHP part-load efficiency (4 technologies) | verified at rated + part-load | — | Yes — `python/chp.py` |
| CHP dispatch GA | correctly deprioritises the least-efficient unit (Microturbine) under fuel constraints | fuel-constrained optimum | Yes — `python/dispatch_ga.py` |

Two real bugs were found and fixed in prior development on this project
(worth guarding against when rebuilding):
1. Gasifier mass balance originally double-counted gasification air.
2. LTS reaction reused HTS's catalyst kinetics, giving ~0% conversion —
   correctly revealed that LTS needs its own catalyst-specific kinetics
   (Cu/ZnO/Al2O3, not Fe-Cr, Ea=75 kJ/mol vs Ea=111 kJ/mol).

Six design-basis parameters remain unconfirmed by DOK-ING: steam-to-feed
ratio (0.4), air equivalence ratio (0.25), feed sulfur/H2S (200 ppm),
feed chlorine/HCl (150 ppm) — treat these as assumptions, not established
facts, in any new work.

**New item to flag with DOK-ING (found during Phase 2's live EU-008
implementation, `python/eu_utilities_chp.py`):** EU-008's Confirmed 20 kW
cooling-tower rating appears significantly undersized against this
model's own computed ~58 kW peak demand (GC-004 quench + HB-003 cold-side
+ HB-012 compressor, summed and swept across ER=0.25 through 0.55) —
recommend confirming actual installed/specified cooling capacity, or
providing real operating data to check this model's assumptions. A
separate, additive `Estimated` resizing recommendation (peak demand x a
15% margin) is published alongside the untouched Confirmed 20 kW figure
at `("EU-008", "RecommendedCapacityEstimate")` in the Shared Plant State
— see that module's own docstring and self-test for the full derivation.
This does NOT modify `data/equipment_registry.json`'s own EU-008 row.

DOK-ING's real, formal RFI response (data/dokink_rfi_answers.md, applied
in python/design_basis.py) has since confirmed all 17 design-basis RFI
questions. One real discrepancy came out of it — DOK-ING's confirmed
nominal feed rate (1 tonne/day, 1,000 kg/day) differed from this
project's own physics-model design point (37.5 kg/h dry feed = 900
kg/day) — and has SINCE BEEN RESOLVED by explicit user decision: the
physics core is now recalibrated to DOK-ING's confirmed figure.

**Current feed-rate basis (use this in any new work): 41.67 kg/h dry
feed = 1,000 kg/day** (`python/gasifier_mass_balance.py`'s
`DEFAULT_DRY_FEED_KG_H`), up from the old 37.5 kg/h / 900 kg/day, a
+11.12% scale-up. The ash (10%) and carbon-black (5%) fractions
themselves are UNCHANGED — only the absolute feed rate they're applied
to — so absolute ash/carbon-black mass flows and circularity.py's
revenue-potential figures scaled by the same +11.12% (ash 3.750 -> 4.167
kg/h, carbon black 1.875 -> 2.0835 kg/h), while the diversion-from-
landfill percentage (a pure ratio) did not change. kinetics.py's WGS
conversion (75.0%/40.0%/85.0%) and psa.py's PSA recovery (75.0%) have no
numeric dependency on this constant and are UNCHANGED, along with every
module downstream of them (uncertainty.py's Monte Carlo,
performance_guarantee.py, multi_module_orchestration.py, pinn_kinetics.py,
sim_to_real.py, time_series_sim.py, tda_analysis.py) — verified directly
by searching each file for a dependency, not assumed. The ~50 kg/day H2
production target also did not need to move: it was always an
externally DOK-ING-stated figure already anchored to the 1,000 kg/day
basis, not derived by this project's own code from the feed-rate
constant. See python/design_basis.py's feedstock_rate_variation entry
and python/gasifier_mass_balance.py's own docstring for the full detail.

## The 19 innovations and what equipment each belongs to

Organise new modules around these, grouped by category. Each maps to a
specific plant subsystem — build accordingly rather than as a monolith.
A starting equipment registry (AI-001 through AI-015) exists as
spreadsheets outside this repo and should be brought in as the data
layer is built.

**Engineering & Product**
- Novelty audit → applies across the full equipment set
- Circularity scoring → ash & carbon black recovery
- Multi-module orchestration → multi-plant coordinator
- RFNBO compliance → compliance tracker
- Predictive maintenance → bed pressure sensor

**Mathematical**
- Reaction kinetics → shift reactors (design targets above)
- MPC + RL → central optimiser (not yet built — next major piece)
- Monte Carlo uncertainty → shift reactors (propagate the 6 unconfirmed
  assumptions into confidence intervals, not point values)

**Rare methods**
- Physics-informed neural nets → gasifier
- Sim-to-real transfer → central optimiser
- Federated learning → cloud data hub
- Performance guarantee → hydrogen purifier
- Topological data analysis → plant control screen

**AI agents** (none built yet — genuinely the least-started category)
- Operator copilot → plant control screen (most demoable, no real plant
  data needed to build a first version)
- Root-cause diagnosis → bed pressure sensor
- Multi-agent negotiation → multi-plant coordinator
- Confirmation-loop agent → shift reactors (automates re-confirming the
  6 unconfirmed assumptions with DOK-ING)
- Regulatory drafting agent → compliance tracker
- Vendor-sourcing agent → full equipment set (also very demoable — every
  item in the registry needs a real vendor quote)

## Coding conventions for this project

- Prefer complete, ready-to-run code over structural advice or pseudocode.
- Every new physics module needs a numeric check against its established
  design target before being considered done — state the check explicitly
  in a comment, the way the existing MATLAB blocks do.
- Be explicit about simplifications. If something is a first-pass
  correlation rather than a rigorous model (like the PSA recovery
  correlation), say so in the code comments — don't present a
  simplification as more rigorous than it is.
- MATLAB Simulink errors are usually diagnosable from the exact error
  message text (line/column references) without needing to see the block's
  code directly.

## Known source-data issues (data/equipment_registry.json)

Found while building `python/equipment_engineering_estimates.py`'s
GC-001 through GC-015, SA-001 through SA-012, and HB-001 through HB-018
(all 2026-08-28) engineering-estimate fills, then confirmed complete by
a dedicated, systematic sweep of the ENTIRE 91-item registry (also
2026-08-28, not just the sections already worked) for every mention of
GC-006/GC-008/GC-009/GC-012 specifically — pre-existing errors in the
original registry data itself, unrelated to that work. NOT fixed at
the source: `data/equipment_registry.json` is DOK-ING's own static
datasheet extract and off-limits to edit (see that module's own
docstring). Worth correcting whenever the registry maintainer next
reviews the source spreadsheet:

1. GC-007 (Wet Scrubber, Tar)'s own remark for "Tar inlet concentration
   (design)" attributes the 0.5 g/Nm3 figure to "GC-008's bulk packed-bed
   removal." GC-008 is the Wet Scrubber (H2S) — GC-006 (Tar Removal Unit,
   the actual packed-bed tar adsorber) is almost certainly the intended
   reference.
2. GC-012 (Activated Carbon Filter)'s own remark for "H2S / COS removal
   target" compares itself against "GC-006's <1 ppm H2S target." GC-006
   is the Tar Removal Unit — GC-008 (the actual H2S scrubber, whose own
   confirmed removal target is <1 ppm) is almost certainly intended.
3. SA-007 (Tar Sampling Port)'s own remark places its "raw" sampling
   port "upstream of GC-008," but its own "Expected tar concentration
   (raw)" figure is explicitly back-calculated using GC-006's removal
   efficiency ("assuming GC-006's ~95% bulk removal efficiency"). The
   raw port should almost certainly be described as upstream of GC-006
   (the actual bulk tar-removal unit it's measuring across), not GC-008
   (the H2S scrubber, unrelated to tar).
4. SA-008 (H2S / COS Analyser)'s own remark says its <0.1 ppm expected
   H2S concentration "matches GC-009's target." GC-009 is the HCl
   Scrubber — its own confirmed target is <5 ppm HCl, a different
   species entirely. GC-012 (Activated Carbon Filter)'s own confirmed
   "<0.1 ppm outlet" H2S/COS removal target is the actual, exact match.
   (The SAME item's own "Alarm setpoint H2S" remark repeats this exact
   mix-up a second time, describing "GC-009 bed breakthrough" — GC-009
   is a wet scrubber with no adsorbent bed to break through at all;
   GC-012, the item with an actual carbon bed, is almost certainly
   intended there too.)

A REPEATED PATTERN found in HB's own data (three more occurrences of
essentially the same GC-009/GC-006-vs-GC-012/GC-008 confusion already
seen in #2 and #4 above — a real, systematic mix-up in the source
spreadsheet between the H2S-handling units (GC-008 Wet Scrubber H2S,
GC-012 Activated Carbon Filter) and two unrelated units (GC-006 Tar
Removal Unit, GC-009 HCl Scrubber):

5. HB-004 (WGS Reactor LTS)'s own remark for "Sensitivity to sulphur"
   says "this is exactly why GC-009's outlet target was set to <0.1 ppm
   H2S/COS" — same GC-009-vs-GC-012 mix-up as #4; GC-012's own confirmed
   target is the actual match.
6. HB-009 (PSA Tail Gas Handler)'s own remark for "Tail gas H2S content"
   and HB-010 (Membrane Separator)'s own remark for "Max allowable H2S"
   BOTH say gas has passed through "GC-006/GC-009 H2S removal upstream."
   Neither GC-006 (tar) nor GC-009 (HCl) does H2S removal — the actual
   H2S-handling units are GC-008 (Wet Scrubber, H2S) and GC-012
   (Activated Carbon Filter).
7. HB-017 (H2 Purification, Post-LOHC)'s own remark for "Purification
   method" compares itself to "GC-009's activated carbon approach."
   GC-009 uses NaOH wet scrubbing, not activated carbon — GC-012 (the
   actual Activated Carbon Filter) is almost certainly intended.

SIX MORE occurrences found by the dedicated, registry-wide sweep
(2026-08-28) — every mention of GC-006, GC-008, GC-009, or GC-012 in
all 91 items was checked, not just the sections already worked on:

9. GC-005 (Quench Tower, Water)'s own remark for "pH of quench water"
   says absorbed HCl/H2S lowers pH "before dedicated downstream
   scrubbing (GC-006/GC-015) removes these species properly." GC-006 is
   the Tar Removal Unit (a dry packed-bed adsorber, not a scrubber for
   HCl/H2S) and GC-015 is the Condensate Tank (not a scrubber at all).
   GC-008 (Wet Scrubber, H2S) and GC-009 (HCl Scrubber) — the actual
   dedicated downstream scrubbers for exactly these two species — are
   almost certainly the intended reference.
10. GC-010 (Bag Filter, Dust)'s own remark for "Outlet dust loading
    (design)" says the tight target "protects GC-009's carbon bed."
    GC-009 (HCl Scrubber) uses random packing, not a carbon bed — GC-012
    (Activated Carbon Filter), which sits directly downstream of GC-010/
    GC-011 in the train and is the item that actually has a carbon bed,
    is almost certainly intended.
11. GC-015 (Condensate Tank)'s own remark for "Condensate flow rate
    (design)" attributes its inflow to "quench blowdown (GC-005) plus
    scrubber blowdowns (GC-006, GC-007, GC-015)." GC-006 is a dry
    adsorber with no liquid blowdown, and citing GC-015 as a source
    feeding itself is a self-reference. GC-007, GC-008, and GC-009 — the
    train's three actual WET scrubbers, each with a genuine liquid
    blowdown — are almost certainly the intended list.
12. SA-007 (Tar Sampling Port)'s own remark for "Sampling frequency"
    ties its schedule to "the media-replacement interval already set at
    GC-008." GC-008 is the H2S scrubber, unrelated to tar. GC-006 (Tar
    Removal Unit, whose own confirmed Service interval is ~3 months —
    the exact figure SA-007 is a tar-sampling item tied to) is almost
    certainly intended.
13. A THIRD confusion pair, distinct from the tar/H2S/HCl species
    mix-up above (this one is simply the wrong GC item NUMBER, "012"
    instead of "013" — GC-012, the Activated Carbon Filter, has no
    flow-meter data of any kind): SA-010 (Gas Flow Meter, Clean)'s own
    remarks for "Flow meter type" ("Same approach as GA-003/GC-012")
    and "Measurement range" ("Matches GC-012's margin approach
    directly"), plus HB-007 (PSA Unit, H2 Recovery)'s own remark for
    "Feed gas flow rate" ("established... through the whole gas train
    (GC-012/013...)"), all cite GC-012 for gas-flow-meter type/range
    facts. GC-013 (Gas Blower/ID Fan, Flow), whose own confirmed Flow
    meter type ("Thermal mass flow meter") and Flow meter range
    ("0-100 Nm3/h") are EXACT matches for what all three remarks
    describe, is almost certainly the intended reference in all three
    places.
14. HB-007's own remark for "H2 recovery rate (design)" says this
    unconfirmed assumption has been "flagged and tracked since GC-006."
    GC-006 (Tar Removal Unit) has no logical connection to a PSA H2-
    recovery-rate assumption. Unlike the other findings here, no
    specific correct GC item suggests itself — the intended reference
    may be a project/task-history note rather than an equipment cross-
    reference at all. Flagged as a genuine anomaly, not a confident
    correction.

A separate, unrelated mislabeling, also found in HB:

15. HB-004's own remark for "Inlet temperature (design)" says it
    "Matches HB-005's hot-side outlet directly." HB-005 is the Steam
    Generator, which has no hot-side/cold-side terminology anywhere in
    its own data — HB-003 (Heat Exchanger, WGS), whose own confirmed Hot
    side outlet temperature is exactly 220°C (matching HB-004's stated
    220°C inlet), is almost certainly the intended reference.

Found while building EU-001 through EU-013's engineering-estimate fills
(2026-08-28): checked EU's own remarks specifically for the GC-006/
GC-008/GC-009/GC-012 pattern above — ZERO new instances (EU's own data
contains no reference to any of those four GC items at all, consistent
with the dedicated registry-wide sweep that already covered EU). While
reviewing EU's OWN cross-references for correctness generally, six more
mislabeled remarks turned up instead, unrelated to the GC-006/008/009/
012 pattern — same discipline, flagged rather than fixed at the source:

16. EU-004's own remark for "Cooling water supply temperature" cites
    "the ambient plant utility water temperature already used elsewhere
    (e.g. GA-004)." GA-004 (Air/Steam Injection, Temp) has no water
    temperature anywhere in its own data (only steam temperatures,
    200°C/350°C) — GC-005 and HB-003, both of which have their own
    confirmed 20°C ambient water figure, are almost certainly the
    intended reference.
17. EU-011's own remark for "Heat exchanger type" cites "HB-005's
    earlier heat-recovery design choice." HB-005 is the Steam Generator,
    with no heat-exchanger-type field in its own data — HB-003 (Heat
    Exchanger, WGS), whose own confirmed type is exactly "Shell-and-tube
    heat exchanger," is almost certainly intended (this same item,
    EU-011, correctly cites HB-003 elsewhere in its own data for a
    similar claim, "Recovery medium," suggesting this one is a genuine
    slip rather than a considered choice).
18. EU-012's own remark for "Thermal output (design)" attributes part
    of its combined capacity to "EU-006 (9kWth)." EU-006 (H2 Fuel Cell,
    Stationary) has no thermal-output figure anywhere in its own data —
    EU-011 (Heat Recovery Unit)'s own confirmed "Thermal duty recovered
    = 9 kWth" is the exact, intended match.
19. EU-013's own remarks (three occurrences — "Measured flow rate
    range," "Supply/return temperature range," and "Heat delivery
    point") all cite "EU-007." EU-007 is the Flare/Emergency Burner,
    with no secondary-side flow, temperature, or district-heating data
    of any kind — EU-012 (District Heating HX), whose own confirmed
    secondary-side flow (~0.72 m3/h) and temperatures (75°C supply /
    45°C return) are exact matches for all three, is almost certainly
    intended throughout.
20. HB-005's own "Heat source" parameter has an internal VALUE/REMARKS
    inconsistency: its VALUE field reads "Preheated feed water from
    HB-005 (150°C)..." — a self-reference — while its OWN REMARKS field
    for the SAME row correctly says "Closes the loop with HB-003
    directly." HB-003's own confirmed Cold side outlet temperature is
    exactly 150°C, confirming HB-003 (not a self-reference to HB-005)
    is the actually-intended source; the remarks field already has it
    right, only the value field's citation is wrong.

Found while building AI-001 through AI-015's engineering-estimate fills
(2026-08-31, the final section) — by far the largest batch found in any
single sweep. Every VALUE and REMARKS field across all 15 AI items was
checked against the actual identity of every cross-referenced item (not
just remarks — the HB-005/AI-002 precedent above already established
that VALUE fields carry the same risk). AI's own data turned out to
have an unusually high error rate: 52 new erroneous cross-references,
organized as five systematic PATTERNS (the same wrong ID substituted
for the same correct one, repeatedly) plus 12 individual one-offs.

PATTERN A — AI-001 (Weather Station) mistakenly cited in place of
AI-004 (PLC, Main Control), 12 occurrences. Every one involves a fact
that only makes sense for a PLC (a "scan cycle," "~320 I/O points,"
being called "AI-001 PLC" outright) attributed to the weather station,
which has neither: AI-005's "Number of OPC-UA tags"/"Tag update rate"/
"Communication interface" (x2)/"Redundancy" remarks; AI-007's "SCADA
software" remark ("Ecosystem-consistent with AI-001's Siemens S7-1500
PLC choice" — AI-001 states no vendor at all; AI-004's own confirmed
CPU model IS a Siemens S7-1500); AI-008's "ATEX/Ex rating" value AND
remarks (one row, both fields: "AI-001's PLC placement"); AI-012's
"Fallback control mode" value ("Fallback to conventional PID control
on AI-001 PLC" — a safety-architecture claim, wrong on the safety-
critical fallback path) and "Inference latency" remarks; AI-013's
"Twin platform software" remarks (paired with a Pattern D error in the
same field, see below); AI-014's "Module health monitoring" value
(paired with a Pattern E error, see below) and "Central vs. distributed
control" value.

PATTERN B — AI-003 (Bed Pressure-Drop Sensor) mistakenly cited in
place of AI-005 (OPC-UA Gateway), 8 occurrences. Every one involves a
fact that only makes sense for the gateway (being called a "gateway"
outright, "1000 tags at 100ms," "SignAndEncrypt" — an OPC-UA security
mode) attributed to the differential-pressure sensor, which has
neither: AI-004's "Communication interfaces" value ("OPC-UA (to AI-003
gateway)"); AI-006's "Max message throughput" and "TLS/SSL encryption"
remarks; AI-006's "Hardware/cloud hosting" remarks ("OT gateway
(AI-003)", paired with a Pattern C error in the same field); AI-007's
"Number of I/O tags" remarks (explicitly says "mirrors the same tag
universe as the OPC-UA gateway" while citing AI-003, self-contradictory
on its face); AI-010's "Security standard" remarks ("AI-003's OPC-UA
security approach", paired with an individual finding in the same
field, see below); AI-013's "Number of live data tags" and "API type"
remarks/value (each paired with a Pattern D error in the same field).

PATTERN C — AI-006 (MQTT Broker) mistakenly cited in place of AI-010
(Cloud IoT Hub), 7 occurrences, including a genuine SELF-REFERENCE
(the same class of error as HB-005's, item 20 above): AI-006's own
"Hardware/cloud hosting" row has TWO separate wrong-ID citations — its
VALUE field reads "bridges to AI-006 Cloud IoT Hub," self-referencing
its own item ID for a DIFFERENT item's role (AI-006 IS the MQTT Broker,
not the Cloud IoT Hub), and its REMARKS field separately says "the
cloud layer (AI-006)," the identical self-reference again. AI-011's
"Deployment" value+remarks (one row, both fields: "co-located with
AI-006 Cloud IoT Hub"), "Write throughput" remarks (cites "AI-006's
~500,000 msg/day ingestion rate" — that figure is AI-010's own
confirmed Message ingestion rate exactly), and "Data retention policy"
remarks (cites both "AI-002" and "AI-006" for the "90 days hot tier...
5 years cold/archive" figures, which are AI-010's own confirmed hot/
cold retention values exactly — both wrong IDs point to the same
correct one). AI-014's "Communication protocol" value ("MQTT (to
AI-006 Cloud IoT Hub...)").

PATTERN D — AI-002 (Camera / Vision System) mistakenly cited in place
of AI-007 (DCS/SCADA Server, which holds the historian/VPN/
cybersecurity-standard data actually being described), 8 occurrences.
AI-002's own confirmed data (camera type, resolution, frame rate, FOV,
AI model purpose/accuracy, interface, IP rating, housing) has none of
these concepts at all: AI-009's "Firewall standard," "VPN support," and
"Logging/SIEM integration" remarks (three separate rows on the SAME
item, each citing AI-002 for a fact that exactly matches one of AI-007's
own confirmed fields — IEC 62443, VPN with MFA, integrated historian,
respectively); AI-010's "Data retention (cold/archive)" remarks (cites
AI-002 for "5," which is AI-007's own confirmed Historian retention
period exactly); AI-011's "High availability" remarks (cites "AI-002's
historian," paired with a Pattern E error in the same field); AI-013's
"Twin platform software" remarks (paired with a Pattern A error) and
"Number of live data tags" remarks (paired with a Pattern B error);
AI-015's "Reporting interface" value ("Automated reporting via AI-002
historian").

PATTERN E — AI-009 (Cybersecurity Firewall) mistakenly cited in place
of AI-013 (Digital Twin Engine), 5 occurrences (4 high-confidence, 1
lower-confidence): AI-010's "Integration with twin platform" remarks
("Feeds AI-009's Digital Twin Engine directly" — AI-009 is the
firewall, not the twin engine); AI-011's "High availability" remarks
("AI-009's Digital Twin Engine," paired with a Pattern D error) and
"API/query language" value (lists AI-009 among the API's consumers — a
firewall doesn't consume a time-series database's query API the way a
twin engine or model server would); AI-014's "Module health monitoring"
value ("AI-009 digital twin instance," paired with a Pattern A error).
Lower-confidence: AI-006's "Max concurrent clients" remarks lists
AI-009 among the broker's publisher/subscriber ecosystem — a firewall
doesn't publish/subscribe at the application layer either; flagged as
likely the same confusion, not asserted with the same confidence as
the other four.

Twelve further INDIVIDUAL mislabels, outside the five patterns above:

21. AI-002's own "AI model purpose" VALUE field says flagged material
    is caught "before it reaches FE-003 shredder." FE-003 is the
    Weighing Conveyor, not a shredder — FE-004 (Shredder / Size
    Reducer) is the actual shredder.
22. The SAME field's own REMARKS say it "Complements FE-008's magnetic
    tramp-metal removal." FE-008 is the Air-lock / Rotary Valve, not a
    magnetic separator — FE-002 (Magnetic & Eddy Current Separator) is
    the actual magnetic-removal item.
23. AI-002's own "Interface" VALUE field says it connects to the "AI
    Model Server (AI-008)." AI-008 is the Edge Computing Server —
    AI-012 is the actual "AI Model Server (MPC/RL)."
24. AI-007's own "Cybersecurity standard" remarks say IEC 62443 is
    "directly relevant given AI-012's dedicated ICS firewall role."
    AI-012 is the AI Model Server, not a firewall — AI-009
    (Cybersecurity Firewall, ICS) is the actual firewall.
25. AI-010's own "Security standard" remarks separately say "AI-012's
    ICS standard" (paired with the AI-003/AI-005 Pattern B error
    already counted above) — the same AI-012-for-AI-009 confusion as
    item 24, a second occurrence.
26. AI-010's own "Max device connections" remarks say it "Matches
    AI-004's established client capacity." AI-004 (PLC) has no client-
    capacity concept — AI-006's own confirmed "Max concurrent clients =
    50" is the exact match (AI-010's own value is also 50).
27. AI-012's own "Hardware spec (inference)" remarks say this is a
    "Heavier workload than AI-005's edge inference." AI-005 (OPC-UA
    Gateway) does no inference — AI-008 (Edge Computing Server) is the
    plant's actual edge-inference item.
28. AI-013's own "State sync frequency" remarks say this is "Slower
    than AI-008's 0.1Hz MPC cycle." AI-008 (Edge Computing Server) has
    no MPC cycle — "0.1Hz" is AI-012's own confirmed Control loop
    frequency exactly.
29. AI-013's own "API type" VALUE field says it "reads from AI-003
    gateway, AI-007 time-series DB" — TWO errors in one field: "AI-003
    gateway" is the same Pattern B error (should be AI-005), and
    "AI-007 time-series DB" is wrong on a different axis — AI-007 is
    the DCS/SCADA Server, not a time-series database; AI-011 (Time-
    Series Database) is the actual match.
30. AI-014's own "Shared utility coordination" VALUE field cites
    "steam (HB-004)." HB-004 is the WGS Reactor (LTS), which produces
    no steam — HB-005 (Steam Generator) is the actual steam source.
31. The SAME field also cites "cooling (EU-011)." EU-011 is the Heat
    Recovery Unit (captures heat, the opposite function) — EU-008,
    literally named "Cooling Tower," is almost certainly the intended
    reference.
32. AI-015's own "Renewable power verification method" VALUE and
    REMARKS fields (one row, both fields) say this is "cross-referenced
    with AI-010's weather data." AI-010 is the Cloud IoT Hub, which
    generates no weather data — AI-001 (Weather Station) is the actual
    source.

TOTAL: 75 distinct erroneous remarks found across the registry to date
(the 8 GC-006/GC-008/GC-009/GC-012 mix-ups already known before the
first 2026-08-28 sweep, 8 more of the same pattern the dedicated sweep
found in items 9-14, the 1 separate HB-003/HB-005 mix-up in item 15,
6 more found while working EU in items 16-20, and 52 more found while
working AI — 5 systematic patterns totaling 40 occurrences plus 12
individual one-offs, items 21-32 plus the pattern lists above). None of
the 75 is relied upon by any fill in
`python/equipment_engineering_estimates.py` — each was checked
individually against every FE/GA/GC/SA/HB/EU/AI estimate actually
shipped, and none was used as a stated basis; no previously-shipped
estimate has needed correction or withdrawal as a result of any sweep.

## Not yet built (the actual current state)

`python/kinetics.py`, `python/psa.py`, `python/chp.py`,
`python/dispatch_ga.py`, and `app.py` exist and are verified (see above).
Still missing:

1. `/matlab` — the physics model itself; nothing in this repo has been
   cross-checked against Simulink yet, only against the documented targets.
2. Gasifier, gas cleaning, and interstage HX — no Python or MATLAB
   implementation yet.
3. Digital twin data layer — time-series logging of simulation runs.
4. MPC controller (central optimiser / AI reasoning layer).
5. AI agents — start with operator copilot and vendor-sourcing agent.
6. Everything in the "Rare methods" category above.
7. Monte Carlo uncertainty propagation for the 6 unconfirmed assumptions.
8. Liquid-carrier H2 storage (room temperature/pressure) — DOK-ING's real
   RFI response (data/dokink_rfi_answers.md, RFI #8) confirms this exists
   as an alternative to the compressed-gas route (HB-013's 875 bar(g)
   tanks) this repo already models. May or may not be the same carrier
   chemistry as HB-014 through HB-017's existing LOHC (Dibenzyltoluene)
   entries — DOK-ING's answer doesn't name the carrier, so this isn't
   assumed identical. Documented, not built.
9. Larger reactor sizes beyond the 1 tpd unit this whole project models —
   DOK-ING's product line goes up to 25 tonnes/day for the largest
   reactor (RFI #1). This repo's physics and equipment registry cover
   ONLY the 1 tpd unit; scaling behavior for larger units is unmodeled.
