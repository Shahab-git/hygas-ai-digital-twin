"""
Project Design Basis tracker v5 — the 17 RFI questions DOK-ING actually
sent, verbatim from data/rfi_dokink.md, grouped exactly as that document
groups them: Feedstock (5), Hydrogen Product (5), Site & Infrastructure
(2), Regulatory & Commercial (4), Project Scope (1).

v5 PHYSICS CORE RECALIBRATED — the v4 "Known Discrepancy — Requires User
Decision" on #1 (feed rate) is now RESOLVED, not just documented. The
user made the explicit decision v4 deferred: recalibrate this project's
physics core from the old 900 kg/day (37.5 kg/h) design point to
DOK-ING's confirmed 1,000 kg/day (41.67 kg/h). Applied in
python/gasifier_mass_balance.py (DEFAULT_DRY_FEED_KG_H), which
python/circularity.py inherits automatically (no separate constant to
update there). ASH_FRACTION (0.10) and CARBON_BLACK_FRACTION (0.05) were
deliberately left untouched — percentages of feed mass, not absolute
quantities — so only the absolute ash/carbon-black mass flows scaled,
by the same +11.12% the feed rate itself scaled. Confirmed directly (by
searching, not assuming) that kinetics.py and psa.py have ZERO numeric
dependency on this constant, so WGS conversion (75.0%/40.0%/85.0%) and
PSA recovery (75.0%) are unaffected, and so is every module downstream
of THEM (uncertainty.py's Monte Carlo, performance_guarantee.py,
multi_module_orchestration.py, pinn_kinetics.py, sim_to_real.py,
time_series_sim.py, tda_analysis.py). The ~50 kg/day H2 target
(hydrogen_production_target, #6) also did not need to move — it was
already an externally DOK-ING-stated figure anchored to the 1,000 kg/day
basis, not derived by this project's own code from the old constant; see
that question's and #1's own confirmed_notes for the full reconciliation.
#1's confirmed_notes below, and app.py's Circularity Scoring section,
both now say RESOLVED rather than flagging an open discrepancy.

v4 REAL RFI RESPONSE RECEIVED — the first real (not Assumed, not
reconstructed, not a hedge to reconcile) answers this tracker has ever
had. DOK-ING answered all 17 questions formally, via Ankica Kovac; the
verbatim answers are committed at data/dokink_rfi_answers.md and applied
here via apply_dokink_rfi_response(), called automatically at the bottom
of this module (import-time, not something app.py or the self-test has
to remember to call) — the first REAL use of the set_confirmed()
mechanism this module has had since it was built. All 17 questions are
now STATUS_CONFIRMED; every prior STATUS_ASSUMED/STATUS_UNKNOWN base
status from the v3 reconciliation stays on the entry as historical
record (QUESTIONS[key]["status"]) and IS still what clear_confirmed()
reverts to, but is no longer what status_of() returns day-to-day.

Two things this real response changed beyond just filling in blanks:
  - #1 (feed rate): DOK-ING confirmed "1 tonne/day (1,000 kg/day)" as
    nominal capacity — a DIFFERENT number than this project's own
    physics-model design point (37.5 kg/h dry feed = 900 kg/day,
    gasifier_mass_balance.py's DEFAULT_DRY_FEED_KG_H, and everything
    built on it: kinetics.py's GHSV defaults, circularity.py,
    equipment_data_requests.py's citations, etc.). Per explicit
    instruction, NO physics constant anywhere in this repo was changed
    because of this — recalibrating the design point is a decision for
    the user to make explicitly, not something to resolve silently by
    picking a number. Flagged as a "Known Discrepancy — Requires User
    Decision" on this entry's confirmed_notes, and the same flag is
    surfaced in app.py wherever the app itself cites the feed rate
    (the Circularity Scoring section) — see that section's own comment
    for exactly where.
  - #9 (end use) and #10 (co-products): DOK-ING's real answers CORRECT
    the prior Assumed framing, not just supersede it. The prior answer
    read EU-006's PEM fuel cell and the CHP/heat-recovery equipment
    train as evidence the plant leaned toward specific end
    uses/co-product commitments; DOK-ING's real answer is broader and
    different in kind — end use is "no fixed limitation, depends
    entirely on contracts," and CHP is explicitly "optional, not
    fixed." EU-006 and the CHP suite remain real, valid, DEPLOYABLE
    equipment configurations — just not confirmed as THE decision the
    way the prior Assumed answer implied. See #9/#10's confirmed_notes.
  - #14 (RFNBO): DOK-ING confirmed RFNBO qualification is NOT required
    — optional, pursued only for its effect on hydrogen's economic
    value. This CORRECTS python/compliance.py's own prior framing
    (which treated RFNBO as this project's implicit target) and
    app.py's top-line tagline — both updated; see compliance.py's own
    docstring for the correction and why regulatory_drafting.py needed
    no separate fix (it reads compliance.py's checklist live).
  - New, unmodeled information documented but NOT built out anywhere in
    this repo (per explicit instruction — document, don't build): a
    liquid-carrier H2 storage alternative (room temperature/pressure,
    #8) alongside the compressed-gas route this project's equipment
    registry already models, and larger reactor sizes up to 25 tonnes/
    day (#1) — this whole repo's physics and equipment registry cover
    ONLY the 1 tpd unit. Both also noted in CLAUDE.md's "Not yet built"
    list.

v3 RECONCILIATION, against an unsourced walkthrough claiming 8/17
Assumed: that walkthrough was treated as a claim to verify, not copied
in — every one of its 17 answers was checked question-by-question
against v2's actual answers and, where they disagreed, against the real
cited source file directly, not taken on the walkthrough's word. Result:
  - #2 (feedstock composition): a REAL BUG in v2, not a disagreement —
    v2's note wrongly claimed "no ash content... documented anywhere".
    GA-005's own remarks state "Ash discharge rate (design) = 10% of
    feed — Matches the 10% ash content (dry basis) already used in the
    mass/energy balance" (also gasifier_mass_balance.py's ASH_FRACTION
    = 0.10) — a real, if partial, feedstock proximate-analysis figure
    v2 missed. The walkthrough's mention of ~10% ash prompted a
    recheck that found this independently verifiable in the source
    registry. Also added: the feed_sulfur_ppm/feed_chlorine_ppm
    assumptions (uncertainty.py) that Q2's own wording ("...S/Cl
    content...") calls for and v2 had omitted. Status stays Unknown —
    the majority of what's asked (volatile matter, fixed carbon,
    C/H/O/N, LHV) is still genuinely undocumented — but the note was
    factually wrong and is fixed.
  - #9 (hydrogen end use): the walkthrough's narrower answer (fuel cell
    only) was checked against v2's dual-citation answer (fuel cell AND
    mobility dispensing, via HB-013's own "dispensing pressure options"
    wording) — v2's answer holds up and is, if anything, more complete
    than the walkthrough's. No change.
  - #12 (nearby infrastructure): the walkthrough flagged this as
    uncertain ("partial", MRF interface may not fully answer the
    question). Investigated independently by checking it against how
    #11 (site utilities) is treated: v2 had been INCONSISTENT — #11
    correctly treats the plant's own utility-metering equipment (EU-009)
    as insufficient to answer "what's actually available on site" (a
    design spec isn't a confirmed real-world fact), but #12 let the same
    category of evidence (EU-012/EU-013's district-heating interconnect
    equipment, FE-002's MRF supply-chain fact) count as Assumed anyway.
    That inconsistency was the actual bug. FIXED: #12 changed from
    Assumed to Unknown, with the reasoning documented on the entry
    itself. This is the one place the walkthrough's hedge pointed at a
    real problem, though the fix follows from re-applying v2's own #11
    standard consistently, not from taking the walkthrough's word.
  - #13 (project driver): verified a genuinely new, real citation the
    walkthrough didn't raise directly but that a broader check turned
    up — app.py's own UI names "SMITH2 R&D Hydrogen Agency" alongside
    DOK-ING/NACHIP (app.py:1480). Added to the note as circumstantial
    context. The walkthrough's own added claim that SMITH2 is "based in
    Zagreb" could NOT be verified anywhere in this repo (only DOK-ING is
    tied to Zagreb, in CLAUDE.md/README.md) and was deliberately NOT
    incorporated — an unverifiable claim doesn't get added just because
    it appeared in the walkthrough.
  - #11 (site utilities): the walkthrough's stated reasoning ("SA
    section 64% missing data") refers to Sensors & Analysers, an
    unrelated equipment-datasheet section (Tab 6) with no connection to
    Site & Infrastructure utilities — an apparent mix-up in the
    walkthrough. The status (Unknown) still matches, but that specific
    justification was NOT incorporated since it doesn't actually apply.
  - All other 12 questions (#1, #3, #4, #5, #6, #7, #8, #10, #14, #15,
    #16, #17): the walkthrough's stated answers/status matched v2's
    exactly on independent recheck. No changes.

v1 of this module (before data/rfi_dokink.md existed in this repo) had
to RECONSTRUCT what a plausible RFI might ask, with its own invented
5/4/4/3/2 category split. That reconstruction is gone — every question
below is copied verbatim from the real document (see each entry's
"rfi_number", which is that question's literal number in
data/rfi_dokink.md), and every answer was RE-DERIVED against the real
wording from scratch, not relabeled from v1. Several genuinely differ:
  - v1 answered a generic "what regulatory framework applies" question
    with the RFNBO/compliance.py citation. The REAL RFI splits that into
    two separate questions — #14 ("does H2 need to qualify as RFNBO")
    and #15 ("what jurisdiction's regulations apply, do you hold
    permits"). The compliance.py citation answers #14 well; it does NOT
    answer #15's permit/jurisdiction-authority half, which stays Unknown
    here even though v1's single merged question looked more complete.
  - The real RFI's #16 ("target tonnes of MSW diverted from landfill,
    independent of H2 output") does NOT exist in v1 at all. Checked
    fresh against circularity.py: that module computes a real
    "diversion_fraction", but it's a DIFFERENT metric (ash+carbon-black
    byproduct mass / feed mass, ~15%) — not a landfill-diversion TONNAGE
    TARGET for the feedstock itself. Conflating the two would overstate
    what's on file, so #16 is Unknown, not answered via circularity.py.
  - The real RFI's #3 (raw MSW vs. pre-sorted RDF/SRF, who pre-sorts)
    and #12 (nearby infrastructure to interface with) were NOT asked at
    all in v1's reconstruction. Both turned out to have real, citable
    answers once checked properly — FE-002's own remarks state the feed
    arrives "already pre-sorted at the MRF" (an external Materials
    Recovery Facility) and describe FE-002's own duty as "polishing
    catch, not primary recovery". This is a case where redoing the
    check properly FOUND a real answer the old reconstruction missed
    entirely, simply because it never asked this specific question.

METHOD, same discipline as v1 and as equipment_data_requests.py before
it: every one of the 17 real questions was checked against this
project's own real data BEFORE writing an answer — kinetics.py, psa.py,
compliance.py, uncertainty.py, safety_flags.py, gasifier_mass_balance.py,
circularity.py, chp.py/dispatch_ga.py, data/equipment_registry.json, and
CLAUDE.md/README.md. Where a real value exists, it's cited to the exact
file (and registry item, where applicable). Where nothing in this
project answers it, or where only PART of a compound question is
answered, that's stated honestly in the note — never rounded up to look
more complete than it is (see e.g. #1's unaddressed "seasonal variation"
half, or #9's "supports 2 of 4 listed options, doesn't confirm which is
primary" caveat).

STATUS MECHANISM — unchanged from v1, same shape as
confirmation_loop.py/uncertainty.py:
  - STATUS_ASSUMED  — a real, cited answer exists in this project.
  - STATUS_UNKNOWN  — genuinely absent. No invented placeholder.
  - STATUS_CONFIRMED — reserved for the moment DOK-ING actually answers
    this RFI for real. Nothing below starts at this status.
    set_confirmed()/is_confirmed()/clear_confirmed() mirror
    uncertainty.py's own in-memory mechanism, ready to use the moment a
    real RFI response exists; a Supabase-backed wrapper (mirroring
    confirmation_loop.py) is a natural next step at that point, out of
    scope here since there's no real response yet to persist.

FINAL COUNT, verified live by this module's own self-test: all 17 of 17
real RFI questions are now STATUS_CONFIRMED, with DOK-ING's own real
answer, applied via set_confirmed() in apply_dokink_rfi_response()
below. This SUPERSEDES the v3 reconciliation's 8 Assumed / 9 Unknown
split — that split remains visible per-entry (QUESTIONS[key]["status"])
as the historical pre-RFI-response baseline, and is exactly what
clear_confirmed() reverts a question to, but summarize()/status_of()
now report Confirmed for all 17 day-to-day. Not rounded up in either
direction: 17 Confirmed, not "basically all of them."
"""
from datetime import datetime, timezone

STATUS_ASSUMED = "Assumed"
STATUS_UNKNOWN = "Unknown — Required"
STATUS_CONFIRMED = "Confirmed"

CATEGORIES = [
    "Feedstock", "Hydrogen Product", "Site & Infrastructure",
    "Regulatory & Commercial", "Project Scope",
]

RFI_SOURCE = "data/rfi_dokink.md — the real, verbatim RFI DOK-ING sent"
RFI_ANSWERS_SOURCE = "data/dokink_rfi_answers.md — DOK-ING's real RFI response, via Ankica Kovac"

DESIGN_BASIS_DISCLAIMER = (
    "**Design-basis tracker for the real RFI DOK-ING sent** (data/rfi_dokink.md). All 17 "
    "questions are now **Confirmed** with DOK-ING's own real, formal answers (via Ankica Kovac — "
    "see data/dokink_rfi_answers.md), applied through this module's set_confirmed() mechanism. "
    "This document still has no real correspondence capability and no authority to represent you "
    "externally on its own — it's a record of what's confirmed, not a live channel to DOK-ING. "
    "Where a Confirmed answer differs materially from what this project's own physics/equipment "
    "data previously assumed, that's flagged explicitly rather than silently overwritten — no "
    "physics constant was ever changed automatically just because a real answer arrived. #1's "
    "feed-rate discrepancy WAS since resolved, but only as an explicit, separate recalibration "
    "decision the user made afterward — not an automatic side effect of this confirmation; see "
    "that question's own confirmed_notes for exactly what changed."
)

# Order matches the 5 real RFI categories and the real question numbering
# within each — data/rfi_dokink.md, not sorted by status.
QUESTIONS = {
    "feedstock_rate_variation": {
        "rfi_number": 1,
        "category": "Feedstock",
        "question": (
            "How much feedstock (MSW) do you want the system to process per day (tonnes/day)? "
            "Is this a fixed rate or does it need to handle seasonal variation?"
        ),
        "status": STATUS_ASSUMED,
        "answer": (
            "Design dry feed rate: 37.5 kg/h (0.9 t/day / 900 kg/day). As-received (wet) nominal "
            "feed rate at the weighing conveyor: ~0.042 t/h (~1.0 t/day), range 0.029-0.050 t/h. "
            "FE-001's hopper is separately sized for a ~1 tpd nominal hot-standby buffer."
        ),
        "source": (
            "python/gasifier_mass_balance.py:32 (DEFAULT_DRY_FEED_KG_H); "
            "data/equipment_registry.json — FE-003 \"Nominal feed rate\" and FE-001 remarks"
        ),
        "note": (
            "The RATE is answered. The second half of this question — whether the plant needs to "
            "tolerate SEASONAL variation in feedstock volume — is NOT addressed anywhere in this "
            "project; every feed-rate figure on file is a single fixed design point, with no "
            "seasonal profile, turndown-for-seasonality analysis, or variability range documented."
        ),
        "confirmed_value": None, "confirmed_source": None, "confirmed_notes": None, "confirmed_at": None,
    },
    "feedstock_composition": {
        "rfi_number": 2,
        "category": "Feedstock",
        "question": (
            "What is the composition of your feedstock — proximate/ultimate analysis (moisture, "
            "ash, volatile matter, fixed carbon, C/H/O/N/S/Cl content) and calorific value (LHV)?"
        ),
        "status": STATUS_UNKNOWN,
        "answer": None,
        "source": None,
        "note": (
            "python/compliance.py's own checklist already flags this exact gap: \"Waste "
            "feedstock sourcing and composition documentation\" is status \"Not yet documented\" "
            "— \"none found in this repo\". Still true overall — but four of this question's named "
            "sub-parameters DO have a real, if partial, figure on file, corrected here after a "
            "prior version of this tracker wrongly claimed \"no ash content... documented "
            "anywhere\": moisture ~10% design inlet (FE-005); ash ~10 wt% dry basis (GA-005's own "
            "remarks: \"Ash discharge rate (design) = 10% of feed — Matches the 10% ash content "
            "(dry basis) already used in the mass/energy balance\", also "
            "python/gasifier_mass_balance.py's ASH_FRACTION = 0.10); sulfur ~200 ppm and chlorine "
            "~150 ppm — but the last two are explicitly THIS PROJECT'S OWN default assumption, "
            "NOT DOK-ING-sourced (python/uncertainty.py: ASSUMPTIONS['feed_sulfur_ppm'] / "
            "['feed_chlorine_ppm']). Still completely absent: volatile matter, fixed carbon, "
            "carbon/hydrogen/oxygen/nitrogen elemental content, and calorific value (LHV) for the "
            "raw feedstock — no full proximate/ultimate analysis exists, which is why this stays "
            "Unknown despite the four partial figures above. (GA-008/GA-010's \"ash "
            "content\"/\"moisture content\" figures describe the ash and carbon-black BYPRODUCT "
            "streams' own purity, not the incoming feedstock, and shouldn't be conflated with "
            "GA-005's feedstock-ash figure above.)"
        ),
        "confirmed_value": None, "confirmed_source": None, "confirmed_notes": None, "confirmed_at": None,
    },
    "feedstock_presorting": {
        "rfi_number": 3,
        "category": "Feedstock",
        "question": (
            "Is the feedstock raw MSW, or has it already been sorted/pre-processed (e.g. RDF, "
            "SRF)? Who handles that pre-sorting?"
        ),
        "status": STATUS_ASSUMED,
        "answer": (
            "Pre-processed, not raw MSW: the feedstock arrives already sorted at an external MRF "
            "(Materials Recovery Facility) before reaching this plant. FE-002 (Magnetic & Eddy "
            "Current Separator) performs only a \"polishing catch, not primary recovery\" — "
            "residual ferrous/non-ferrous tramp-metal removal on a stream that's already largely "
            "metal-free going in."
        ),
        "source": (
            "data/equipment_registry.json — FE-002 \"Target metal fraction\" remarks: "
            "\"(post-MRF, polishing duty)... DOK-ING's feed is already pre-sorted at the MRF\""
        ),
        "note": (
            "This answers \"raw vs. pre-sorted\" and \"who handles the pre-sorting\" (an external "
            "MRF, not this plant) directly. It does NOT confirm whether the pre-sorted output is "
            "specifically RDF or SRF (refuse-derived fuel / solid recovered fuel, per the "
            "question's own examples) — no fuel-classification standard is named anywhere."
        ),
        "confirmed_value": None, "confirmed_source": None, "confirmed_notes": None, "confirmed_at": None,
    },
    "feedstock_supply_contract": {
        "rfi_number": 4,
        "category": "Feedstock",
        "question": (
            "Is feedstock supply guaranteed under contract, or does the plant need to tolerate "
            "gaps or substitute feedstocks?"
        ),
        "status": STATUS_UNKNOWN,
        "answer": None,
        "source": None,
        "note": (
            "No supply contract, sourcing agreement, or statement about tolerating feedstock "
            "gaps/substitutes is documented anywhere in this repo."
        ),
        "confirmed_value": None, "confirmed_source": None, "confirmed_notes": None, "confirmed_at": None,
    },
    "feedstock_source_location": {
        "rfi_number": 5,
        "category": "Feedstock",
        "question": (
            "Where does the feedstock come from — a single municipal source, multiple sources, "
            "or will you need to purchase/import it?"
        ),
        "status": STATUS_UNKNOWN,
        "answer": None,
        "source": None,
        "note": (
            "Beyond confirming the feed arrives via an MRF (previous question), nothing in this "
            "project states WHERE that MRF or its input waste stream is located, or whether it's "
            "a single municipal source, multiple sources, or purchased/imported material."
        ),
        "confirmed_value": None, "confirmed_source": None, "confirmed_notes": None, "confirmed_at": None,
    },
    "hydrogen_production_target": {
        "rfi_number": 6,
        "category": "Hydrogen Product",
        "question": "How much hydrogen do you want to produce per day (kg/day) or per year (tonnes/year)?",
        "status": STATUS_ASSUMED,
        "answer": (
            "~50 kg H2/day (~2.08 kg/h); ~18.25 t/year (= 50 kg/day x 365, calculated from the "
            "daily figure — not separately stated anywhere as an annual number)."
        ),
        "source": (
            "data/equipment_registry.json — HB-013 \"Storage capacity\" remarks (\"matching "
            "DOK-ING's ~50 kg/day target directly\") and HB-007 \"Product H2 flow rate\" remarks "
            "(\"modestly below DOK-ING's 50 kg/day (2.083 kg/h) target\")"
        ),
        "note": (
            "HB-007's own calculated product rate (~1.85 kg/h from the PSA train) falls modestly "
            "short of the 50 kg/day / 2.083 kg/h target on its own — a real, already-acknowledged "
            "design margin gap, not smoothed over."
        ),
        "confirmed_value": None, "confirmed_source": None, "confirmed_notes": None, "confirmed_at": None,
    },
    "hydrogen_purity": {
        "rfi_number": 7,
        "category": "Hydrogen Product",
        "question": "What purity does the hydrogen need to meet (e.g. 99.9%, 99.999% for fuel cell/mobility grade)?",
        "status": STATUS_ASSUMED,
        "answer": (
            "99.97 vol% (ISO 14687 Grade D) design target, 99.95 vol% minimum-acceptable alarm "
            "threshold — inside the RFI's own example range, at the ISO 14687 Grade D tier rather "
            "than the highest grade."
        ),
        "source": (
            "data/equipment_registry.json — HB-006 \"H2 purity (design)\" remarks: \"DOK-ING's "
            "actual stated target (ISO 14687 Grade D) — not an assumption, used directly\""
        ),
        "note": (
            "This is the one item on this whole tracker explicitly labeled in the source registry "
            "itself as DOK-ING's own stated figure, not a project assumption."
        ),
        "confirmed_value": None, "confirmed_source": None, "confirmed_notes": None, "confirmed_at": None,
    },
    "hydrogen_delivery_pressure": {
        "rfi_number": 8,
        "category": "Hydrogen Product",
        "question": "At what pressure does the hydrogen need to be delivered (storage pressure vs. dispensing pressure)?",
        "status": STATUS_ASSUMED,
        "answer": (
            "Storage (design/MAWP): 875 bar(g), Type IV composite tanks. Dispensing/operating "
            "range: 350-700 bar(g) — matching the two standard SAE/ISO Type IV dispensing "
            "pressure classes."
        ),
        "source": (
            "data/equipment_registry.json — HB-013 \"Design pressure\" / \"Operating pressure "
            "range\"; cross-checked in python/safety_flags.py:39"
        ),
        "note": (
            "HB-013's own remarks describe 875 bar(g) as \"the real industry-standard rating for "
            "700 bar dispensing systems (SAE/ISO Type IV tanks)\" and the operating range as "
            "covering \"both of DOK-ING's stated dispensing pressure options\". Upstream PSA "
            "adsorption pressure is separately on file too: HB-008 = 7 bar(g), \"within DOK-ING's "
            "actual stated 3-10 bar PSA discharge range — real data, not an assumption\"."
        ),
        "confirmed_value": None, "confirmed_source": None, "confirmed_notes": None, "confirmed_at": None,
    },
    "hydrogen_end_use": {
        "rfi_number": 9,
        "category": "Hydrogen Product",
        "question": (
            "What is the intended end use — mobility/refuelling station, industrial feedstock, "
            "grid injection/blending, or stationary power via fuel cell?"
        ),
        "status": STATUS_ASSUMED,
        "answer": (
            "Real equipment-registry evidence supports two of the four listed end uses: "
            "stationary power via fuel cell (EU-006, a dedicated PEM H2 Fuel Cell drawing "
            "directly from HB-013 storage) and mobility/refuelling dispensing (HB-013's 350/700 "
            "bar(g) operating range matches the standard SAE J2601 heavy-duty/light-duty vehicle "
            "refuelling pressure classes)."
        ),
        "source": (
            "data/equipment_registry.json — EU-006 (H2 Fuel Cell, Stationary); "
            "HB-013 \"Operating pressure range\""
        ),
        "note": (
            "This does NOT confirm which end use is primary, nor rule out the other two "
            "RFI-listed options (industrial feedstock, grid injection/blending) — no equipment or "
            "documentation anywhere in this project addresses either of those. Marked Assumed "
            "because real, citable equipment evidence exists for two of the four options, not "
            "because the question is fully answered."
        ),
        "confirmed_value": None, "confirmed_source": None, "confirmed_notes": None, "confirmed_at": None,
    },
    "hydrogen_coproducts": {
        "rfi_number": 10,
        "category": "Hydrogen Product",
        "question": "Do you also want electricity and/or heat as co-products, or is hydrogen the sole target output?",
        "status": STATUS_ASSUMED,
        "answer": (
            "Yes — both electricity and heat are explicit co-products, not sole-H2 output. "
            "Electricity: 4 CHP technologies (SOFC, Gas Engine, Microturbine, PEM Fuel Cell — "
            "EU-001 through EU-006), dispatched via python/dispatch_ga.py. Heat: EU-011 Heat "
            "Recovery Unit, EU-012 District Heating HX, and EU-013 Thermal Energy Metering "
            "(District Heat) — a complete heat-export train, not just internal process heat "
            "recovery."
        ),
        "source": (
            "python/chp.py, python/dispatch_ga.py; data/equipment_registry.json — "
            "EU-001 through EU-006, EU-011, EU-012, EU-013"
        ),
        "note": None,
        "confirmed_value": None, "confirmed_source": None, "confirmed_notes": None, "confirmed_at": None,
    },
    "site_utilities_available": {
        "rfi_number": 11,
        "category": "Site & Infrastructure",
        "question": (
            "What utilities are already available on site — grid power connection, water supply, "
            "existing steam or heat network?"
        ),
        "status": STATUS_UNKNOWN,
        "answer": None,
        "source": None,
        "note": (
            "EU-009 (Electrical Metering, Grid) specifies the ON-SITE metering equipment's own "
            "design-basis measurement range (0-50 kW at 400V) — what the equipment was SIZED to "
            "measure, not a statement of what capacity is actually available or contracted from "
            "the local utility (EU-009 itself notes \"DNO / utility approval required = Yes\", "
            "unresolved). No grid-connection agreement, water-supply contract, or existing "
            "steam/heat-network CONNECTION status is documented anywhere in this repo."
        ),
        "confirmed_value": None, "confirmed_source": None, "confirmed_notes": None, "confirmed_at": None,
    },
    "site_nearby_infrastructure": {
        "rfi_number": 12,
        "category": "Site & Infrastructure",
        "question": "Is there existing waste-handling or industrial infrastructure nearby that this plant needs to interface with?",
        "status": STATUS_UNKNOWN,
        "answer": None,
        "source": None,
        "note": (
            "CORRECTED after a reconciliation pass: an earlier version of this tracker marked this "
            "Assumed, citing FE-002's MRF remark and EU-012/EU-013's district-heating "
            "interconnection equipment. On review that was inconsistent with how the previous "
            "question (#11, site utilities) is treated, and the inconsistency was the actual bug: "
            "EU-012/EU-013 show what the plant's OWN DESIGN is built to interface with IF such a "
            "network exists — the same category of evidence as EU-009's metering equipment in #11, "
            "which was correctly judged NOT sufficient to answer \"what's actually available on "
            "site\". Neither confirms a real, physical, nearby facility actually exists; both "
            "describe what the plant's design accommodates. Similarly, FE-002's \"pre-sorted at "
            "the MRF\" remark is a feedstock SUPPLY-CHAIN fact (already answering #3 above) — it "
            "doesn't establish that the MRF, or any other waste-handling/industrial facility, is "
            "physically NEAR this plant's site, only that one exists somewhere in the supply "
            "chain. No site-specific confirmation of nearby existing infrastructure — waste-"
            "handling or industrial — is documented anywhere in this project."
        ),
        "confirmed_value": None, "confirmed_source": None, "confirmed_notes": None, "confirmed_at": None,
    },
    "project_driver": {
        "rfi_number": 13,
        "category": "Regulatory & Commercial",
        "question": (
            "What is driving this project — regulatory compliance, decarbonization targets, a "
            "new revenue stream, grant funding, or something else?"
        ),
        "status": STATUS_UNKNOWN,
        "answer": None,
        "source": None,
        "note": (
            "This project is described only as a \"NACHIP pilot project\" (CLAUDE.md/README.md), "
            "with app.py's own UI additionally naming \"SMITH2 R&D Hydrogen Agency\" alongside "
            "DOK-ING (app.py:1480 caption: \"HYGAS-AI — SMITH2 R&D Hydrogen Agency — NACHIP Pilot "
            "Programme\") — a second real, named party beyond DOK-ING. Neither NACHIP nor SMITH2 "
            "is explained anywhere in this repo, though \"R&D Hydrogen Agency\" and \"pilot "
            "programme\" framing circumstantially suggests a research/demonstration motivation "
            "rather than a straightforward commercial one. That's a plausible inference from the "
            "naming, not a stated answer — none of the RFI's listed drivers (regulatory "
            "compliance, decarbonization targets, new revenue stream, grant funding) is ever "
            "explicitly named anywhere in this repo, so this stays Unknown."
        ),
        "confirmed_value": None, "confirmed_source": None, "confirmed_notes": None, "confirmed_at": None,
    },
    "rfnbo_requirement": {
        "rfi_number": 14,
        "category": "Regulatory & Commercial",
        "question": "Does the hydrogen need to qualify as \"green\" or \"low-carbon\" under EU RFNBO rules, or is that not a requirement?",
        "status": STATUS_ASSUMED,
        "answer": (
            "Yes — RFNBO (\"green\"/low-carbon) qualification under the EU framework is the "
            "explicit assumed target: Delegated Regulation (EU) 2023/1184 and methodology "
            "Regulation (EU) 2023/1185."
        ),
        "source": "python/compliance.py module docstring",
        "note": (
            "compliance.py is explicit this is the ASSUMED applicable framework for organizing "
            "documentation, not a legal determination: \"this module makes no such claim\" about "
            "actual certification. Real RFNBO certification requires an accredited third-party "
            "auditor."
        ),
        "confirmed_value": None, "confirmed_source": None, "confirmed_notes": None, "confirmed_at": None,
    },
    "jurisdiction_permits": {
        "rfi_number": 15,
        "category": "Regulatory & Commercial",
        "question": "What jurisdiction's regulations apply, and do you already hold any permits or environmental approvals?",
        "status": STATUS_UNKNOWN,
        "answer": None,
        "source": None,
        "note": (
            "Zagreb, Croatia (CLAUDE.md/README.md) establishes country-level context, and the "
            "previous question establishes the assumed EU RFNBO regulatory TARGET — but neither "
            "is the same as this question, which asks which specific jurisdiction's regulations "
            "legally apply and whether any permits or environmental approvals are already held. "
            "No permitting authority, permit status, or environmental approval is documented "
            "anywhere in this project."
        ),
        "confirmed_value": None, "confirmed_source": None, "confirmed_notes": None, "confirmed_at": None,
    },
    "landfill_diversion_target": {
        "rfi_number": 16,
        "category": "Regulatory & Commercial",
        "question": "Is there a target for tonnes of MSW diverted from landfill, independent of the hydrogen output?",
        "status": STATUS_UNKNOWN,
        "answer": None,
        "source": None,
        "note": (
            "python/circularity.py computes a real \"diversion_fraction\" (~15% of dry feed mass "
            "— ash + carbon black byproduct mass / feed mass), but that is a DIFFERENT metric: "
            "the fraction of the FEED that leaves as a reusable solid byproduct, not a "
            "landfill-diversion TONNAGE TARGET for the feedstock itself (which this gasification "
            "plant diverts from landfill by definition, simply by processing it). No explicit "
            "landfill-diversion target, independent of the H2 output, is documented anywhere — "
            "conflating circularity.py's byproduct fraction with this question would overstate "
            "what's actually on file."
        ),
        "confirmed_value": None, "confirmed_source": None, "confirmed_notes": None, "confirmed_at": None,
    },
    "project_budget": {
        "rfi_number": 17,
        "category": "Project Scope",
        "question": "Is there a target budget or capital cost range the design needs to respect?",
        "status": STATUS_UNKNOWN,
        "answer": None,
        "source": None,
        "note": (
            "No financial figures — CAPEX, OPEX, budget ceiling, or funding source — appear "
            "anywhere in this repo. (The only \"budget\" terminology present is "
            "dispatch_ga.py's unrelated syngas/H2 FUEL dispatch budgets, an operational kW "
            "allocation concept, not a financial one.)"
        ),
        "confirmed_value": None, "confirmed_source": None, "confirmed_notes": None, "confirmed_at": None,
    },
}


# Structured, numeric form of RFI #2's own confirmed prose answer (set_confirmed()'s
# own "value" argument is free text, matching every other question's own storage --
# see apply_dokink_rfi_response() below). This is NOT a separate, independent data
# source: every number here is transcribed directly from that SAME confirmed prose
# ("Moisture 5-15(20)%, Ash 5-15%, Volatile Matter >65%, Carbon >45%, Hydrogen >5%,
# LHV 15-20 MJ/kg (dry basis)"), and this module's own self-test cross-checks the two
# stay consistent. Exists so a live consumer (e.g. ga001_gasifier_model.py's own
# feedstock-composition getter) can read real numeric bounds via a clean function call
# instead of parsing prose -- "read live, don't hardcode a copy" for a value that is
# only fully usable as a specific number, not just a sentence.
FEEDSTOCK_COMPOSITION_CONFIRMED_RANGES = {
    "moisture_pct": (5.0, 15.0),         # DOK-ING's own "(20)" is a stated wider outlier
                                           # case, not the primary range -- not used here
    "ash_pct": (5.0, 15.0),
    "volatile_matter_pct_min": 65.0,      # open-ended minimum, no upper bound given
    "carbon_pct_min": 45.0,               # open-ended minimum, no upper bound given
    "hydrogen_pct_min": 5.0,              # open-ended minimum, no upper bound given
    "lhv_mj_per_kg": (15.0, 20.0),
    "basis_note": (
        "DOK-ING's own answer states LHV explicitly as dry basis; moisture/ash/VM are "
        "conventional proximate-analysis percentages (typically as-received for moisture, "
        "dry basis for ash/VM); carbon/hydrogen are given as bare percentage floors with "
        "no basis stated and no oxygen/nitrogen figures at all -- NOT a complete "
        "proximate/ultimate analysis, a real, stated limitation, not resolved here."
    ),
}


def get_feedstock_composition_ranges():
    """Returns FEEDSTOCK_COMPOSITION_CONFIRMED_RANGES if RFI #2 is
    currently confirmed (is_confirmed() live-checked, same pattern as
    status_of()), else None -- the graceful, live-checked getter every
    real consumer of this data should call, rather than reading the
    module-level dict directly (which would skip the confirmation check)."""
    return FEEDSTOCK_COMPOSITION_CONFIRMED_RANGES if is_confirmed("feedstock_composition") else None


def is_confirmed(key):
    return QUESTIONS[key]["confirmed_value"] is not None


def status_of(key):
    """The LIVE status: STATUS_CONFIRMED if set_confirmed() has been
    called for this question, else the question's own base status
    (Assumed/Unknown) — same live-check pattern as
    uncertainty.is_confirmed()/compliance.py's checklist."""
    return STATUS_CONFIRMED if is_confirmed(key) else QUESTIONS[key]["status"]


def set_confirmed(key, value, source, notes=""):
    """Records a REAL DOK-ING answer to this RFI question. Called for
    real, for all 17 questions, by apply_dokink_rfi_response() below —
    see the v4 docstring section for what changed. Mirrors
    uncertainty.set_confirmed()'s in-memory pattern exactly; a
    confirmation_loop.py-style Supabase-backed wrapper (to persist a
    FUTURE re-confirmation or amendment across process restarts, the
    way confirmation_loop.py does for the six kinetics/PSA assumptions)
    remains a natural next step, not yet needed since the current real
    response is already committed to this repo as a file
    (data/dokink_rfi_answers.md), which survives a process restart on
    its own."""
    if key not in QUESTIONS:
        raise KeyError(key)
    QUESTIONS[key]["confirmed_value"] = value
    QUESTIONS[key]["confirmed_source"] = source
    QUESTIONS[key]["confirmed_notes"] = notes
    QUESTIONS[key]["confirmed_at"] = datetime.now(timezone.utc).isoformat()


def clear_confirmed(key):
    QUESTIONS[key]["confirmed_value"] = None
    QUESTIONS[key]["confirmed_source"] = None
    QUESTIONS[key]["confirmed_notes"] = None
    QUESTIONS[key]["confirmed_at"] = None


def summarize():
    """Counts by LIVE status across all 17 questions — task requirement
    4's "actual final count", computed fresh every call, not cached."""
    counts = {STATUS_ASSUMED: 0, STATUS_UNKNOWN: 0, STATUS_CONFIRMED: 0}
    for key in QUESTIONS:
        counts[status_of(key)] += 1
    return counts


def _format_question_block(key, cfg):
    lines = [f"### RFI #{cfg['rfi_number']} — {cfg['question']}", ""]
    status = status_of(key)
    lines.append(f"**Status:** {status}")
    if is_confirmed(key):
        lines.append(f"**Confirmed answer:** {cfg['confirmed_value']}")
        lines.append(f"**Confirmed source:** {cfg['confirmed_source']}")
        if cfg["confirmed_notes"]:
            lines.append(f"**Confirmed notes:** {cfg['confirmed_notes']}")
        lines.append(f"**Confirmed at:** {cfg['confirmed_at']}")
    elif cfg["answer"] is not None:
        lines.append(f"**Answer (from this project):** {cfg['answer']}")
        lines.append(f"**Source:** {cfg['source']}")
    else:
        lines.append("**Answer:** None on file in this project — required from DOK-ING.")
    if cfg["note"]:
        lines.append("")
        lines.append(cfg["note"])
    lines.append("")
    return "\n".join(lines)


def generate_request_list_markdown():
    """The downloadable Markdown document — same generate-from-live-data
    approach and header/disclaimer/summary/grouped-section structure as
    equipment_data_requests.generate_request_list_markdown() and
    confirmation_loop.generate_all_requests_draft(), with its own
    DESIGN_BASIS_DISCLAIMER (see module docstring for why it isn't
    regulatory_drafting.DRAFT_DISCLAIMER verbatim — that constant names
    the wrong source module for this document)."""
    counts = summarize()
    lines = [
        "# HYGAS-AI — Project Design Basis RFI Tracker",
        "",
        f"_Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}. The 17 "
        f"design-basis questions from {RFI_SOURCE}, checked against this project's own real data "
        f"— every \"Assumed\" answer below is cited to the exact file (and equipment registry "
        f"item, where applicable) it came from; nothing is invented._",
        "",
        DESIGN_BASIS_DISCLAIMER,
        "",
        "## Summary",
        "",
        f"- **{counts[STATUS_ASSUMED]}** of 17 questions — **{STATUS_ASSUMED}** (a real, cited "
        f"answer already exists in this project)",
        f"- **{counts[STATUS_UNKNOWN]}** of 17 questions — **{STATUS_UNKNOWN}** (genuinely open, "
        f"needs a real answer from DOK-ING)",
        f"- **{counts[STATUS_CONFIRMED]}** of 17 questions — **{STATUS_CONFIRMED}** (DOK-ING has "
        f"actually answered this RFI item)",
        "",
    ]
    for category in CATEGORIES:
        cat_keys = [k for k, cfg in QUESTIONS.items() if cfg["category"] == category]
        lines.append(f"## {category}")
        lines.append("")
        for key in cat_keys:
            lines.append(_format_question_block(key, QUESTIONS[key]))
    return "\n".join(lines)


def apply_dokink_rfi_response():
    """Applies DOK-ING's real, formal RFI response (data/dokink_rfi_answers.md,
    received via Ankica Kovac) to all 17 questions via set_confirmed() —
    the first real use of that mechanism. Called once, automatically, at
    the bottom of this module (import time), so every consumer (app.py,
    this module's own self-test) sees the Confirmed state without having
    to remember to call this — the same "apply once per fresh process"
    shape confirmation_loop.py's sync_confirmed_from_db() uses for the
    six kinetics/PSA assumptions, except the source here is a real file
    already committed to this repo, not a live database query, so a
    plain function call at import time is enough; no Supabase round trip
    needed to survive a process restart.

    Each call's `notes` argument carries forward exactly what task
    requirements 2-5 asked for: the #1 feed-rate discrepancy flagged
    explicitly (not resolved), the #9/#10 corrections to the prior
    Assumed framing, and the #1/#8 new-but-unmodeled information (larger
    reactor sizes, the liquid-carrier storage alternative)."""
    set_confirmed(
        "feedstock_rate_variation",
        "Nominal capacity fixed at 1 tonne/day (1,000 kg/day) for continuous 24/7 operation, with "
        "operational turndown ~70-120%. Larger seasonal swings handled by parallel modular units. "
        "Other reactor sizes exist, up to 25 tonnes/day for the largest.",
        f"{RFI_ANSWERS_SOURCE} (RFI #1)",
        "✅ DISCREPANCY RESOLVED — PHYSICS CORE RECALIBRATED: this question previously flagged a "
        "\"Known Discrepancy — Requires User Decision\" between DOK-ING's confirmed nominal "
        "capacity (1,000 kg/day) and this project's own physics-model design point (37.5 kg/h dry "
        "feed = 900 kg/day). The user has since made that explicit decision: recalibrate the "
        "physics core to DOK-ING's confirmed figure. python/gasifier_mass_balance.py's "
        "DEFAULT_DRY_FEED_KG_H is now 41.67 kg/h (1,000 kg/day), up from 37.5 kg/h (900 kg/day) — "
        "a +11.12% scale factor. ASH_FRACTION (0.10) and CARBON_BLACK_FRACTION (0.05) were "
        "deliberately left UNCHANGED — they are percentages of feed mass, not absolute "
        "quantities, and nothing in DOK-ING's response revised them; only the absolute ash/"
        "carbon-black mass flows (python/circularity.py) scaled by the same +11.12%, from "
        "3.750/1.875 kg/h to 4.167/2.0835 kg/h. kinetics.py's WGS conversion percentages "
        "(75.0%/40.0%/85.0%) and psa.py's PSA recovery (75.0%) are UNCHANGED — neither module "
        "has ever had a numeric dependency on the feed-rate constant, confirmed directly by "
        "searching both files, not assumed. The ~50 kg/day H2 production target (see the "
        "hydrogen_production_target question) ALSO did not need to move: it was already an "
        "externally DOK-ING-stated figure (HB-013/HB-007 registry remarks, and DOK-ING's own "
        "RFI #6 answer: \"~50 kg/day from 1 tpd\") anchored to the 1,000 kg/day basis all along, "
        "not derived by this project's own code from the old 900 kg/day constant — it was the "
        "OLD design point that was slightly inconsistent with it, not the target itself. NEW, "
        "UNMODELED INFORMATION (unaffected by the recalibration, still just documented): "
        "DOK-ING's product line extends well beyond the 1 tpd unit this whole project models — "
        "up to 25 tonnes/day for the largest reactor. This repo's physics and equipment registry "
        "cover ONLY the 1 tpd unit, now at its recalibrated 1,000 kg/day basis; larger units are "
        "not modeled anywhere here (also noted in CLAUDE.md's \"Not yet built\" list).",
    )
    set_confirmed(
        "feedstock_composition",
        "Moisture 5-15(20)%, Ash 5-15%, Volatile Matter >65%, Carbon >45%, Hydrogen >5%, LHV "
        "15-20 MJ/kg (dry basis). Trace S/Cl captured via downstream scrubbing/dry gas cleaning.",
        f"{RFI_ANSWERS_SOURCE} (RFI #2)",
        "This project's own design-basis default of ~10% ash (dry basis, GA-005, "
        "gasifier_mass_balance.py's ASH_FRACTION) falls inside DOK-ING's confirmed 5-15% ash "
        "range — consistent, not contradicted. The 200 ppm S / 150 ppm Cl defaults in "
        "python/uncertainty.py (this project's own assumption, not previously DOK-ING-sourced) "
        "aren't directly checkable against this answer, since S/Cl are described qualitatively "
        "here (\"captured via downstream scrubbing/dry gas cleaning\") rather than as a specific "
        "ppm figure — the 200/150 ppm default remains this project's own assumption, now not "
        "contradicted but also not confirmed at that precision. LHV (15-20 MJ/kg dry basis) and "
        "the full C/H/O/N breakdown are genuinely new information — this project never had a "
        "raw-feedstock LHV or elemental analysis to compare against.",
    )
    set_confirmed(
        "feedstock_presorting",
        "Pre-sorted and shredded (<20-30mm particle size) — plastic, dried sewage sludge, "
        "wood chips, textiles. No RDF/SRF pre-production needed. Pre-sorting handled by local "
        "waste utilities/MRFs before the Looper's inlet hopper.",
        f"{RFI_ANSWERS_SOURCE} (RFI #3)",
        "Confirms this project's own prior finding (FE-002's registry remarks: \"DOK-ING's feed "
        "is already pre-sorted at the MRF\") was directionally correct. New information: DOK-ING's "
        "product is named \"the Looper\" (not previously named anywhere in this repo), and no "
        "RDF/SRF pre-production step is needed, contrary to what the RFI question's own framing "
        "might have implied.",
    )
    set_confirmed(
        "feedstock_supply_contract",
        "Guaranteed, but system tolerates gaps via hot-standby state and accepts substitute "
        "feedstocks (RDF, waste biomass, textiles, dried sludge).",
        f"{RFI_ANSWERS_SOURCE} (RFI #4)",
        "New information: FE-001's hopper being sized for a hot-standby buffer (equipment_registry"
        ".json remarks) turns out to match a real, confirmed design feature — DOK-ING's own "
        "answer explicitly cites hot-standby tolerance for supply gaps, not just a buffer-sizing "
        "coincidence.",
    )
    set_confirmed(
        "feedstock_source_location",
        "Flexible by deployment site — single municipal utility, wastewater treatment "
        "facility (sludge), or local industrial/commercial waste streams.",
        f"{RFI_ANSWERS_SOURCE} (RFI #5)",
        "",
    )
    set_confirmed(
        "hydrogen_production_target",
        "~50 kg/day from 1 tpd of standard high-calorific plastic waste, varying with feedstock "
        "C/H ratio and moisture.",
        f"{RFI_ANSWERS_SOURCE} (RFI #6)",
        "Matches this project's own prior figure (~50 kg/day, HB-013/HB-007 remarks) closely — "
        "confirms rather than contradicts. DOK-ING's answer clarifies the figure is "
        "feedstock-dependent (varies with C/H ratio and moisture), not a fixed guarantee "
        "regardless of feed composition.",
    )
    set_confirmed(
        "hydrogen_purity",
        "99.97% (ISO 14687 Grade D), suitable for mobility/fuel-cell vehicle use.",
        f"{RFI_ANSWERS_SOURCE} (RFI #7)",
        "Exact match to this project's own prior figure (HB-006's registry remarks, already "
        "labeled there as \"DOK-ING's actual stated target... not an assumption, used directly\") "
        "— now formally confirmed via the real RFI response too, not just carried over from "
        "the equipment registry's own citation.",
    )
    set_confirmed(
        "hydrogen_delivery_pressure",
        "PSA discharges at 3-10 bar. Multi-stage booster compression to 350/700 bar for mobility "
        "dispensing/tube trailers. Alternative: a liquid carrier storing H2 at room "
        "temperature/pressure also exists as an option.",
        f"{RFI_ANSWERS_SOURCE} (RFI #8)",
        "Matches this project's own prior figures closely: HB-008's 7 bar(g) PSA adsorption "
        "pressure falls inside the confirmed 3-10 bar range; HB-013's 350/700 bar(g) "
        "operating/dispensing range matches exactly. NEW, UNMODELED INFORMATION: a liquid-carrier "
        "H2 storage alternative (room temperature/pressure) exists as an option alongside the "
        "compressed-gas route this project's equipment registry models. HB-014 through HB-017 "
        "already model an LOHC (Dibenzyltoluene) hydrogenation/storage/dehydrogenation train as "
        "an \"Auxiliary/Optional\" path, so this MAY be the same alternative DOK-ING is "
        "describing — but the RFI response doesn't name the carrier chemistry explicitly, so "
        "this is documented as a real, confirmed option, not assumed identical to the existing "
        "LOHC entries without DOK-ING saying so. Not built out further here.",
    )
    set_confirmed(
        "hydrogen_end_use",
        "No fixed limitation — depends entirely on contracts and contracted prices.",
        f"{RFI_ANSWERS_SOURCE} (RFI #9)",
        "CORRECTS this project's own prior framing: the previous Assumed answer treated EU-006 (a "
        "real, specified PEM H2 Fuel Cell in the equipment registry) and HB-013's dispensing-"
        "pressure range as evidence the intended end use leaned toward stationary power and/or "
        "mobility specifically. DOK-ING's real answer is broader and different in kind: end use is "
        "explicitly NOT fixed to any one path — it's a commercial/contractual decision. EU-006's "
        "own equipment data remains real and valid as ONE deployable configuration this plant "
        "supports; it is not, and was never confirmed to be, THE definitive end-use decision.",
    )
    set_confirmed(
        "hydrogen_coproducts",
        "H2 is primary; CHP using excess heat/syngas is optional, not fixed. Ash residue recovered "
        "for construction applications (aggregate/brick). Carbon black recovered as a raw material.",
        f"{RFI_ANSWERS_SOURCE} (RFI #10)",
        "Partly corrects this project's own prior framing: the previous Assumed answer treated the "
        "full CHP suite (EU-001 through EU-006) and heat-export train (EU-011/EU-012/EU-013) as "
        "confirming electricity AND heat are both explicit co-products on equal footing with H2. "
        "DOK-ING's real answer reframes this: H2 is PRIMARY, CHP is explicitly OPTIONAL, not "
        "fixed — the equipment registry's CHP/heat-recovery items remain real, valid OPTIONAL "
        "configurations, not a confirmed always-on co-product commitment. Newly confirmed and "
        "consistent with this project's own circularity.py: ash recovered for construction use "
        "(matches GA-009's real EN 12620 aggregate-standard equipment) and carbon black recovered "
        "as a raw material (matches GA-008/GA-010's real equipment) — circularity.py's own "
        "byproduct-recovery framing holds up well, even though its specific EUR/kg prices remain "
        "this project's own placeholder assumption, not DOK-ING-sourced.",
    )
    set_confirmed(
        "site_utilities_available",
        "Grid power connection and water supply both available.",
        f"{RFI_ANSWERS_SOURCE} (RFI #11)",
        "Doesn't state a connected CAPACITY (kW) or supply VOLUME — EU-009's own 0-50 kW "
        "metering design range remains this project's own equipment spec, not a stated grid "
        "capacity. Existing steam/heat network availability specifically wasn't addressed in "
        "DOK-ING's answer (which only confirms grid power and water).",
    )
    set_confirmed(
        "site_nearby_infrastructure",
        "No.",
        f"{RFI_ANSWERS_SOURCE} (RFI #12)",
        "A clean, direct negative answer — confirms the v3 reconciliation-pass correction "
        "(flipping this question from Assumed to Unknown) was the right call: there genuinely is "
        "NO existing nearby waste-handling/industrial infrastructure to interface with, consistent "
        "with treating the plant's own design equipment (MRF supply-chain link, district-heating "
        "interconnect capability) as NOT the same thing as confirmed nearby infrastructure.",
    )
    set_confirmed(
        "project_driver",
        "Dual commercial/environmental model — gate fees for processing waste, plus revenue "
        "from green H2 sales, process heat, and upcycled mineral residues.",
        f"{RFI_ANSWERS_SOURCE} (RFI #13)",
        "New information beyond any single one of the RFI's own listed driver options (regulatory "
        "compliance, decarbonization targets, new revenue stream, grant funding) — DOK-ING's "
        "answer is a genuinely dual, more specific commercial model (gate fees + product sales "
        "across three revenue lines), closer to \"a new revenue stream\" but more specific than "
        "that framing captured.",
    )
    set_confirmed(
        "rfnbo_requirement",
        "Not required — but increases hydrogen's economic value/price if achieved.",
        f"{RFI_ANSWERS_SOURCE} (RFI #14)",
        "CORRECTS this project's own prior framing: python/compliance.py's checklist and its "
        "\"RFNBO compliance documentation\" framing (plus app.py's own former \"RFNBO-compliant "
        "green hydrogen\" tagline) treated RFNBO qualification as this project's implicit target. "
        "DOK-ING's real answer reframes this explicitly: RFNBO is OPTIONAL, pursued only for its "
        "economic upside, not a compliance obligation — compliance.py and its app.py UI have "
        "been updated accordingly; see compliance.py's own docstring for the correction.",
    )
    set_confirmed(
        "jurisdiction_permits",
        "Holds a waste processing permit (specific jurisdiction not stated).",
        f"{RFI_ANSWERS_SOURCE} (RFI #15)",
        "Confirms a permit IS held (a real, positive fact this project had no prior basis for), "
        "but does NOT name the specific jurisdiction, permitting authority, or permit scope/type "
        "— so the earlier country-level context (Zagreb, Croatia, CLAUDE.md/README.md) remains "
        "the only location information on file; this answer neither confirms nor contradicts that, "
        "it just doesn't independently state a jurisdiction.",
    )
    set_confirmed(
        "landfill_diversion_target",
        "No general tonnage target — this phase specifically targets high-value contaminated "
        "waste streams (oiled plastic, contaminated construction packaging) that currently go to "
        "specialized processing or incineration (e.g., Vienna), not landfill.",
        f"{RFI_ANSWERS_SOURCE} (RFI #16)",
        "CONFIRMS the v3 reconciliation-pass reasoning that circularity.py's \"diversion_fraction\" "
        "(~15%, ash+carbon-black byproduct mass / feed mass) was correctly kept separate from this "
        "question — DOK-ING's real answer describes something entirely different (a targeted "
        "contaminated-waste-stream strategy, not a general landfill-diversion tonnage target, and "
        "not related to circularity.py's byproduct-mass metric at all). New information: the "
        "specific competing disposal route named is incineration in Vienna.",
    )
    set_confirmed(
        "project_budget",
        "No fixed capital cost goal or limit — the modular, factory-assembled design is "
        "inherently intended to minimize cost versus traditional large-scale plants.",
        f"{RFI_ANSWERS_SOURCE} (RFI #17)",
        "A real, if qualitative, answer — no numeric CAPEX ceiling exists (consistent with the "
        "prior Unknown status), but the design PHILOSOPHY (modular, factory-assembled, "
        "cost-minimizing vs. traditional large-scale plants) is new, real information this project "
        "had no prior citation for anywhere.",
    )


apply_dokink_rfi_response()


if __name__ == "__main__":
    print(f"Total questions: {len(QUESTIONS)} (expected 17)")
    assert len(QUESTIONS) == 17, f"REGRESSION: expected exactly 17 RFI questions, found {len(QUESTIONS)}."

    print("\n=== RFI number check -- exactly 1..17, no gaps or duplicates ===")
    rfi_numbers = sorted(cfg["rfi_number"] for cfg in QUESTIONS.values())
    print(f"rfi_number values: {rfi_numbers}")
    assert rfi_numbers == list(range(1, 18)), "REGRESSION: rfi_number values aren't exactly 1..17."

    print("\n=== Category grouping + count check (task requirement 2: 5/5/2/4/1) ===")
    EXPECTED_CATEGORY_COUNTS = {
        "Feedstock": 5, "Hydrogen Product": 5, "Site & Infrastructure": 2,
        "Regulatory & Commercial": 4, "Project Scope": 1,
    }
    seen_categories = {cfg["category"] for cfg in QUESTIONS.values()}
    assert seen_categories == set(CATEGORIES), "REGRESSION: a question's category doesn't match the declared CATEGORIES list."
    for category in CATEGORIES:
        n = sum(1 for cfg in QUESTIONS.values() if cfg["category"] == category)
        print(f"  {category}: {n} question(s) (expected {EXPECTED_CATEGORY_COUNTS[category]})")
        assert n == EXPECTED_CATEGORY_COUNTS[category], (
            f"REGRESSION: {category} has {n} questions, expected {EXPECTED_CATEGORY_COUNTS[category]}."
        )

    print("\n=== Historical base-status check (the pre-RFI-response v3 baseline) ===")
    EXPECTED_BASE_COUNTS = {STATUS_ASSUMED: 8, STATUS_UNKNOWN: 9}
    base_counts = {STATUS_ASSUMED: 0, STATUS_UNKNOWN: 0}
    for key, cfg in sorted(QUESTIONS.items(), key=lambda kv: kv[1]["rfi_number"]):
        base_counts[cfg["status"]] += 1
        if cfg["status"] == STATUS_ASSUMED:
            assert cfg["answer"] is not None and cfg["source"] is not None, (
                f"REGRESSION: {key}'s base status is Assumed but has no answer/source on file."
            )
        else:
            assert cfg["status"] == STATUS_UNKNOWN, f"REGRESSION: {key} has an unrecognized base status {cfg['status']!r}."
            assert cfg["answer"] is None and cfg["source"] is None, (
                f"REGRESSION: {key}'s base status is Unknown but has a non-null answer/source."
            )
    print(f"  Base (pre-RFI-response) split: {base_counts[STATUS_ASSUMED]} Assumed / "
          f"{base_counts[STATUS_UNKNOWN]} Unknown (expected 8/9 -- the v3 reconciliation result, "
          f"preserved as QUESTIONS[key]['status'] even though it's no longer the LIVE status)")
    assert base_counts == EXPECTED_BASE_COUNTS, f"REGRESSION: base status split is {base_counts}, expected {EXPECTED_BASE_COUNTS}."

    print("\n=== apply_dokink_rfi_response() actually worked -- task requirement 1: verify, don't just run ===")
    print("(apply_dokink_rfi_response() already ran once at module import, above -- checking its effect here)")
    for key, cfg in sorted(QUESTIONS.items(), key=lambda kv: kv[1]["rfi_number"]):
        assert is_confirmed(key), f"REGRESSION: {key} is not confirmed after apply_dokink_rfi_response()."
        assert status_of(key) == STATUS_CONFIRMED, f"REGRESSION: {key}'s live status is {status_of(key)!r}, expected Confirmed."
        assert cfg["confirmed_value"] and cfg["confirmed_value"].strip(), f"REGRESSION: {key} has an empty confirmed_value."
        assert RFI_ANSWERS_SOURCE in cfg["confirmed_source"], (
            f"REGRESSION: {key}'s confirmed_source doesn't cite data/dokink_rfi_answers.md: {cfg['confirmed_source']!r}"
        )
        assert cfg["confirmed_at"] is not None, f"REGRESSION: {key} has no confirmed_at timestamp."
        print(f"  [Confirmed] RFI #{cfg['rfi_number']} ({cfg['category']}) — {key}")
    print("PASSED -- all 17 questions are genuinely Confirmed, each with a non-empty answer, a "
          "source citing data/dokink_rfi_answers.md, and a timestamp -- not just is_confirmed() "
          "returning True by accident.")

    print("\n=== get_feedstock_composition_ranges(): structured numbers match the confirmed prose ===")
    ranges = get_feedstock_composition_ranges()
    assert ranges is not None, "REGRESSION: feedstock_composition is confirmed but the getter returned None."
    prose = QUESTIONS["feedstock_composition"]["confirmed_value"]
    for needle in ("5-15(20)%", "Ash 5-15%", "Volatile Matter >65%", "Carbon >45%", "Hydrogen >5%", "15-20 MJ/kg"):
        assert needle in prose, f"REGRESSION: expected substring {needle!r} not found in the confirmed prose -- structured ranges may have drifted from it."
    assert ranges["moisture_pct"] == (5.0, 15.0) and ranges["ash_pct"] == (5.0, 15.0)
    assert ranges["carbon_pct_min"] == 45.0 and ranges["hydrogen_pct_min"] == 5.0
    assert ranges["lhv_mj_per_kg"] == (15.0, 20.0)
    print(f"  Structured ranges: {ranges}")
    print("  PASSED -- every structured number is directly transcribed from, and verified consistent "
          "with, the SAME confirmed prose answer -- not a separate, independently-drifting source.")

    clear_confirmed("feedstock_composition")
    assert get_feedstock_composition_ranges() is None, (
        "REGRESSION: get_feedstock_composition_ranges() should return None once un-confirmed -- "
        "it must be live-checked, not a static constant a caller could read even when unconfirmed."
    )
    set_confirmed(
        "feedstock_composition",
        QUESTIONS["feedstock_composition"]["confirmed_value"] or prose,
        f"{RFI_ANSWERS_SOURCE} (RFI #2)", "restored after the round-trip check above",
    )
    assert get_feedstock_composition_ranges() is not None
    print("  PASSED -- the getter is genuinely live-checked (None when unconfirmed, restored correctly "
          "after re-confirming), not a static passthrough.")

    print("\n=== Spot-check specific confirmed values against the real answers ===")
    SPOT_CHECKS = [
        ("feedstock_rate_variation", "1 tonne/day (1,000 kg/day)"),
        ("feedstock_rate_variation", "25 tonnes/day"),  # larger-reactor new info, in the notes
        ("hydrogen_purity", "99.97%"),
        ("hydrogen_delivery_pressure", "liquid carrier"),  # new-info flag, in the notes
        ("site_nearby_infrastructure", "No."),
        ("rfnbo_requirement", "Not required"),
        ("project_budget", "No fixed capital cost goal"),
    ]
    for key, expected_substring in SPOT_CHECKS:
        haystack = QUESTIONS[key]["confirmed_value"] + " " + (QUESTIONS[key]["confirmed_notes"] or "")
        assert expected_substring in haystack, (
            f"REGRESSION: expected {expected_substring!r} in {key}'s confirmed value/notes, not found."
        )
    print(f"PASSED -- {len(SPOT_CHECKS)} spot-checks against the real DOK-ING answer text all matched.")

    print("\n=== Discrepancy-resolved check (recalibration) ===")
    q1_notes = QUESTIONS["feedstock_rate_variation"]["confirmed_notes"]
    assert "DISCREPANCY RESOLVED" in q1_notes, "REGRESSION: #1's confirmed_notes lost the resolution marker."
    assert "KNOWN DISCREPANCY" not in q1_notes, "REGRESSION: #1's confirmed_notes still shows the old open-discrepancy flag."
    assert "41.67" in q1_notes and "1,000 kg/day" in q1_notes and "37.5" in q1_notes and "900 kg/day" in q1_notes, (
        "REGRESSION: #1's resolution note doesn't state both the old and new numbers."
    )
    assert "+11.12%" in q1_notes, "REGRESSION: #1's resolution note doesn't state the scale factor."
    print("PASSED -- #1's confirmed_notes shows DISCREPANCY RESOLVED (not the old KNOWN DISCREPANCY "
          "flag), states both the old (37.5 kg/h / 900 kg/day) and new (41.67 kg/h / 1,000 kg/day) "
          "figures, and the +11.12% scale factor.")

    print("\n=== Physics-core recalibration check (cross-module, not just this module's own text) ===")
    from . import gasifier_mass_balance, circularity
    assert gasifier_mass_balance.DEFAULT_DRY_FEED_KG_H == 41.67, (
        f"REGRESSION: gasifier_mass_balance.DEFAULT_DRY_FEED_KG_H is "
        f"{gasifier_mass_balance.DEFAULT_DRY_FEED_KG_H}, expected 41.67 (the recalibrated value)."
    )
    assert gasifier_mass_balance.ASH_FRACTION == 0.10 and gasifier_mass_balance.CARBON_BLACK_FRACTION == 0.05, (
        "REGRESSION: the ash/carbon-black FRACTIONS changed -- they should be untouched by the "
        "feed-rate recalibration, only the absolute feed rate should have changed."
    )
    _flows = gasifier_mass_balance.byproduct_mass_flows()
    assert abs(_flows["ash_kg_h"] - 4.167) < 1e-6, f"REGRESSION: recalibrated ash_kg_h is {_flows['ash_kg_h']}, expected 4.167."
    assert abs(_flows["carbon_black_kg_h"] - 2.0835) < 1e-6, (
        f"REGRESSION: recalibrated carbon_black_kg_h is {_flows['carbon_black_kg_h']}, expected 2.0835."
    )
    _circ = circularity.circularity_summary()
    assert abs(_circ["diversion_fraction"] - 0.15) < 1e-9, (
        f"REGRESSION: diversion_fraction is {_circ['diversion_fraction']}, expected exactly 0.15 (10%+5%) "
        f"-- a pure ratio, must be UNCHANGED by the recalibration."
    )
    print(f"PASSED -- gasifier_mass_balance.DEFAULT_DRY_FEED_KG_H = 41.67 kg/h (recalibrated), "
          f"ASH_FRACTION/CARBON_BLACK_FRACTION untouched (0.10/0.05), computed ash/carbon-black "
          f"flows match the recalibrated values (4.167/2.0835 kg/h), and circularity.py's "
          f"diversion_fraction is still exactly 15% -- a pure ratio, correctly unaffected.")

    print("\n=== Final count (task requirement 6 — not rounded up) ===")
    counts = summarize()
    print(f"Assumed (real, cited answer already in this project): {counts[STATUS_ASSUMED]} of 17")
    print(f"Unknown — Required (genuinely open, needs DOK-ING):    {counts[STATUS_UNKNOWN]} of 17")
    print(f"Confirmed (DOK-ING has actually answered):             {counts[STATUS_CONFIRMED]} of 17")
    assert counts[STATUS_CONFIRMED] == 17, f"REGRESSION: expected exactly 17 Confirmed, got {counts[STATUS_CONFIRMED]}."
    assert counts[STATUS_ASSUMED] == 0 and counts[STATUS_UNKNOWN] == 0
    print("PASSED -- 17 of 17 Confirmed, with DOK-ING's real RFI response applied to every question.")

    print("\n=== set_confirmed()/clear_confirmed() round-trip check (proves the mechanism, not just that it runs) ===")
    # Pick one question whose historical base status was Assumed, and one whose base status was
    # Unknown, to prove clear_confirmed() reverts to the CORRECT per-question baseline -- not a
    # single hardcoded status -- and that re-confirming restores the real DOK-ING answer exactly.
    for probe_key in ("hydrogen_purity", "project_budget"):
        expected_base = QUESTIONS[probe_key]["status"]
        saved_value = QUESTIONS[probe_key]["confirmed_value"]
        saved_source = QUESTIONS[probe_key]["confirmed_source"]
        saved_notes = QUESTIONS[probe_key]["confirmed_notes"]
        clear_confirmed(probe_key)
        assert status_of(probe_key) == expected_base, (
            f"REGRESSION: clearing {probe_key} didn't revert to its own base status {expected_base!r}."
        )
        assert not is_confirmed(probe_key)
        print(f"  [OK] clear_confirmed({probe_key!r}) reverts to its real base status ({expected_base}).")
        set_confirmed(probe_key, saved_value, saved_source, saved_notes)
        assert status_of(probe_key) == STATUS_CONFIRMED and QUESTIONS[probe_key]["confirmed_value"] == saved_value
        print(f"  [OK] re-confirming {probe_key!r} restores the exact real DOK-ING answer.")
    counts_restored = summarize()
    assert counts_restored[STATUS_CONFIRMED] == 17, "REGRESSION: not all 17 are Confirmed again after the round-trip probes."
    print("PASSED -- the mechanism genuinely reverts to each question's own historical baseline and "
          "restores exactly, not just returning True/False without real state changes.")

    draft = generate_request_list_markdown()
    question_blocks = sum(1 for line in draft.splitlines() if line.startswith("### RFI #"))
    confirmed_blocks = draft.count("**Confirmed answer:**")
    print(f"\nMarkdown document length (chars): {len(draft)}")
    print(f"Question blocks in the generated document: {question_blocks} (expected 17)")
    print(f"'Confirmed answer:' blocks in the generated document: {confirmed_blocks} (expected 17)")
    assert question_blocks == 17, f"REGRESSION: document has {question_blocks} question blocks, expected 17."
    assert confirmed_blocks == 17, f"REGRESSION: document has {confirmed_blocks} Confirmed-answer blocks, expected 17."
    assert "DISCREPANCY RESOLVED" in draft, "REGRESSION: the discrepancy-resolved note didn't make it into the generated document."
    assert "KNOWN DISCREPANCY" not in draft, "REGRESSION: the old open-discrepancy flag is still in the generated document."
    print("PASSED -- the generated Markdown document renders all 17 as Confirmed, with the "
          "discrepancy-resolved note visible and the old open-discrepancy flag gone.")
