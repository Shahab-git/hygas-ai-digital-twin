"""
Project Design Basis tracker v3 — the 17 RFI questions DOK-ING actually
sent, verbatim from data/rfi_dokink.md, grouped exactly as that document
groups them: Feedstock (5), Hydrogen Product (5), Site & Infrastructure
(2), Regulatory & Commercial (4), Project Scope (1).

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

FINAL COUNT, verified live by this module's own self-test: 8 of the 17
real RFI questions have a real, cited answer somewhere in this project
(STATUS_ASSUMED); 9 are genuinely open (STATUS_UNKNOWN). This is DOWN
BY ONE from v2's reported 9/8, entirely because of the #12 fix above —
every other question's status is unchanged from v2. (It happens to
match the unsourced walkthrough's own 8/17 headline number, but for a
different reason than the walkthrough gave: the walkthrough's own count
excluded #12 by hedging rather than by applying a stated rule, and
undercounted #2 as fully separate from its ash-content evidence without
citing GA-005 specifically. The convergence on 8/17 here comes from
independently re-deriving #12 against #11's own precedent, not from
adopting the walkthrough's number.) Not rounded up in either direction.
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

DESIGN_BASIS_DISCLAIMER = (
    "**DRAFT — NOT SENT.** This is a design-basis tracker for the real RFI DOK-ING sent "
    "(data/rfi_dokink.md), generated from this project's own real data where an answer already "
    "exists, and marked \"Unknown — Required\" honestly everywhere it doesn't. It has no real "
    "correspondence capability and no authority to represent you externally — review and edit "
    "before actually sending anything to DOK-ING. Nothing marked \"Assumed\" here is a confirmed "
    "DOK-ING answer to this RFI; see each question's own citation for exactly which real source "
    "(DOK-ING's own prior stated data, captured in the equipment registry, or this project's own "
    "explicit default assumption) it's drawn from."
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


def is_confirmed(key):
    return QUESTIONS[key]["confirmed_value"] is not None


def status_of(key):
    """The LIVE status: STATUS_CONFIRMED if set_confirmed() has been
    called for this question, else the question's own base status
    (Assumed/Unknown) — same live-check pattern as
    uncertainty.is_confirmed()/compliance.py's checklist."""
    return STATUS_CONFIRMED if is_confirmed(key) else QUESTIONS[key]["status"]


def set_confirmed(key, value, source, notes=""):
    """Records a REAL DOK-ING answer to this RFI question. Not called
    anywhere in this module or app.py yet — see module docstring's
    STATUS MECHANISM section for why: no real RFI response exists to
    record. Mirrors uncertainty.set_confirmed()'s in-memory pattern
    exactly, ready for a confirmation_loop.py-style Supabase-backed
    wrapper the moment a real response needs to be persisted."""
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

    print("\n=== Per-question status ===")
    for key, cfg in sorted(QUESTIONS.items(), key=lambda kv: kv[1]["rfi_number"]):
        print(f"  [{status_of(key)}] RFI #{cfg['rfi_number']} ({cfg['category']}) — {key}")
        if cfg["status"] == STATUS_ASSUMED:
            assert cfg["answer"] is not None and cfg["source"] is not None, (
                f"REGRESSION: {key} is marked Assumed but has no answer/source on file."
            )
        else:
            assert cfg["status"] == STATUS_UNKNOWN, f"REGRESSION: {key} has an unrecognized base status {cfg['status']!r}."
            assert cfg["answer"] is None and cfg["source"] is None, (
                f"REGRESSION: {key} is marked Unknown but has a non-null answer/source — should be Assumed instead."
            )

    print("\n=== Final count (task requirement 4 — not rounded up) ===")
    counts = summarize()
    print(f"Assumed (real, cited answer already in this project): {counts[STATUS_ASSUMED]} of 17")
    print(f"Unknown — Required (genuinely open, needs DOK-ING):    {counts[STATUS_UNKNOWN]} of 17")
    print(f"Confirmed (DOK-ING has actually answered):             {counts[STATUS_CONFIRMED]} of 17")
    assert counts[STATUS_ASSUMED] == 8, f"REGRESSION: expected exactly 8 Assumed, got {counts[STATUS_ASSUMED]}."
    assert counts[STATUS_UNKNOWN] == 9, f"REGRESSION: expected exactly 9 Unknown, got {counts[STATUS_UNKNOWN]}."
    assert counts[STATUS_CONFIRMED] == 0, "REGRESSION: something is marked Confirmed before any real RFI response exists."
    assert counts[STATUS_ASSUMED] + counts[STATUS_UNKNOWN] + counts[STATUS_CONFIRMED] == 17
    print("PASSED -- 8 Assumed + 9 Unknown = 17, matches the documented count exactly (down from v2's 9/8 after the #12 fix).")

    print("\n=== set_confirmed()/clear_confirmed() mechanism check (for future use) ===")
    assert status_of("project_budget") == STATUS_UNKNOWN
    set_confirmed("project_budget", "EUR 4.2M CAPEX ceiling", "DOK-ING RFI response, 2026-XX-XX", "Illustrative test value, cleared below.")
    assert status_of("project_budget") == STATUS_CONFIRMED
    print("  [OK] set_confirmed() flips status to Confirmed live.")
    counts_after = summarize()
    assert counts_after[STATUS_CONFIRMED] == 1 and counts_after[STATUS_ASSUMED] == 8 and counts_after[STATUS_UNKNOWN] == 8
    print("  [OK] summarize() reflects the confirmation immediately: 8 Assumed / 8 Unknown / 1 Confirmed.")
    clear_confirmed("project_budget")
    assert status_of("project_budget") == STATUS_UNKNOWN
    counts_cleared = summarize()
    assert counts_cleared == {STATUS_ASSUMED: 8, STATUS_UNKNOWN: 9, STATUS_CONFIRMED: 0}
    print("  [OK] clear_confirmed() reverts cleanly -- back to 8 Assumed / 9 Unknown / 0 Confirmed.")

    draft = generate_request_list_markdown()
    question_blocks = sum(1 for line in draft.splitlines() if line.startswith("### RFI #"))
    print(f"\nMarkdown document length (chars): {len(draft)}")
    print(f"Question blocks in the generated document: {question_blocks} (expected 17)")
    assert question_blocks == 17, f"REGRESSION: document has {question_blocks} question blocks, expected 17."
    print("PASSED -- the generated Markdown document's own question count matches 17 exactly.")
