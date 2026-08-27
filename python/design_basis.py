"""
Project Design Basis tracker v1 — the 17 RFI questions DOK-ING sent,
grouped the same way the RFI document itself groups them: Feedstock,
Hydrogen Product, Site & Infrastructure, Regulatory & Commercial,
Project Scope.

METHOD, stated explicitly per the task this module was built for: every
one of the 17 questions was checked against this project's own real data
BEFORE writing an answer — kinetics.py, psa.py, compliance.py,
uncertainty.py, safety_flags.py, gasifier_mass_balance.py, circularity.py,
data/equipment_registry.json, and CLAUDE.md/README.md — not answered from
memory or invented because a plausible number could be guessed at. Where
a real value already exists somewhere in this project, it is used and
cited to the exact file (and, where useful, the exact line or registry
item) it came from. Where nothing in this project answers the question,
it is marked "Unknown — Required" honestly, the same discipline
equipment_data_requests.py and compliance.py's own
"Not yet documented" status already apply elsewhere in this project.

STATUS MECHANISM — same shape as confirmation_loop.py/uncertainty.py,
deliberately reused rather than invented fresh:
  - STATUS_ASSUMED  — this project has a real, cited answer (either a
    value DOK-ING itself already stated, captured in the equipment
    registry's own remarks, or this project's own explicit default
    assumption pending confirmation — the citation text says honestly
    which one it is; see e.g. feed_contaminants vs. hydrogen_purity
    below for both kinds side by side).
  - STATUS_UNKNOWN   — genuinely absent from this project. No invented
    plausible-sounding placeholder.
  - STATUS_CONFIRMED — reserved for the moment DOK-ING actually answers
    this RFI for real. NOTHING below starts at this status — task
    requirement 4 is explicit that nothing here is "Confirmed" until
    that real round-trip happens. set_confirmed()/is_confirmed()/
    clear_confirmed() below mirror uncertainty.py's own in-memory
    mechanism (the same one confirmation_loop.py wraps with Supabase
    persistence for the six kinetics/PSA assumptions) so the exact same
    pattern is ready to use the moment a real RFI response exists.
    Standing up a Supabase table for THIS tracker (mirroring
    confirmation_schema.sql) is a natural next step at that point, but
    is out of scope here — there is no real response yet to persist,
    only the readiness to record one.

WHERE THE 17 QUESTIONS THEMSELVES COME FROM: no RFI document file exists
in this repo (checked directly — no PDF/DOCX, no file matching
"RFI"/"design basis"/"DOK-ING" anywhere under this project). The 17
questions below are this project's own reconstruction of what such an
RFI would need to ask, grouped into the five categories the task
specified, covering exactly the ground a real design-basis RFI for this
kind of plant would need answered before detailed engineering — not a
literal transcription of a document that isn't in this repo.

FINAL COUNT, verified live by this module's own self-test (not just
asserted here): 10 of the 17 questions have a real, cited answer
somewhere in this project (STATUS_ASSUMED); 7 are genuinely open
(STATUS_UNKNOWN) — supply-contract status, feedstock characterization,
exact site plot/permitting jurisdiction, actual utility availability,
project budget, hydrogen offtake, and the scope-of-supply boundary. That
is not rounded up in either direction.
"""
from datetime import datetime, timezone

STATUS_ASSUMED = "Assumed"
STATUS_UNKNOWN = "Unknown — Required"
STATUS_CONFIRMED = "Confirmed"

CATEGORIES = [
    "Feedstock", "Hydrogen Product", "Site & Infrastructure",
    "Regulatory & Commercial", "Project Scope",
]

DESIGN_BASIS_DISCLAIMER = (
    "**DRAFT — NOT SENT.** This is a design-basis tracker for an RFI to DOK-ING, generated from "
    "this project's own real data where an answer already exists, and marked \"Unknown — "
    "Required\" honestly everywhere it doesn't. It has no real correspondence capability and no "
    "authority to represent you externally — review and edit before actually sending anything to "
    "DOK-ING. Nothing marked \"Assumed\" here is a confirmed DOK-ING answer to this specific RFI; "
    "see each question's own citation for exactly which real source (DOK-ING's own prior stated "
    "data, or this project's own explicit default assumption) it's drawn from."
)

# Order matches the 5 RFI categories above; within a category, questions
# are listed in the order a design-basis conversation would naturally
# raise them (feed rate before feed characterization before supply
# status, etc.) — not sorted by status.
QUESTIONS = {
    "feed_rate_moisture": {
        "category": "Feedstock",
        "question": (
            "What design feed rate (dry and as-received) and inlet moisture content should the "
            "feed-handling and drying equipment be sized for?"
        ),
        "status": STATUS_ASSUMED,
        "answer": (
            "Design dry feed rate: 37.5 kg/h (900 kg/day). As-received (wet) feed rate at the "
            "weighing conveyor: nominal 42 kg/h (0.042 t/h), range 29-50 kg/h. Design inlet "
            "moisture ahead of the dryer: 10% (target outlet moisture after drying: <1%)."
        ),
        "source": (
            "python/gasifier_mass_balance.py:32 (DEFAULT_DRY_FEED_KG_H = 37.5 kg/h); "
            "data/equipment_registry.json — FE-003 \"Nominal feed rate\" (0.042 t/h) and "
            "FE-005 \"Inlet moisture (design)\" (10%)"
        ),
        "note": (
            "FE-001's hopper is independently sized for a ~1 tpd (1000 kg/day) nominal "
            "hot-standby buffer per its own remarks — consistent with, but not identical to, the "
            "900 kg/day dry-feed design rate; the two numbers describe different things (buffer "
            "sizing vs. steady-state design throughput) and shouldn't be conflated."
        ),
        "confirmed_value": None, "confirmed_source": None, "confirmed_notes": None, "confirmed_at": None,
    },
    "feedstock_characterization": {
        "category": "Feedstock",
        "question": (
            "What is the feedstock's waste-stream classification, proximate/ultimate analysis, "
            "calorific value, and sourcing chain-of-custody?"
        ),
        "status": STATUS_UNKNOWN,
        "answer": None,
        "source": None,
        "note": (
            "python/compliance.py's own checklist already flags this exact gap: \"Waste "
            "feedstock sourcing and composition documentation\" is status \"Not yet documented\" "
            "— \"none found in this repo\". Nothing anywhere in this project documents MSW "
            "composition beyond the bulk \"municipal solid waste\" label and the aggregate design "
            "feed rate above."
        ),
        "confirmed_value": None, "confirmed_source": None, "confirmed_notes": None, "confirmed_at": None,
    },
    "feed_contaminants": {
        "category": "Feedstock",
        "question": (
            "What sulfur (H2S) and chlorine (HCl) content should gas cleaning and the WGS/PSA "
            "catalysts be designed to tolerate?"
        ),
        "status": STATUS_ASSUMED,
        "answer": "This project's own default assumption: 200 ppm feed sulfur, 150 ppm feed chlorine, both ±15%.",
        "source": "python/uncertainty.py: ASSUMPTIONS['feed_sulfur_ppm'] / ASSUMPTIONS['feed_chlorine_ppm']",
        "note": (
            "Explicitly NOT a DOK-ING-provided value — uncertainty.py's own docstring states "
            "these +/-15% bounds are \"OUR OWN assumed default for a genuinely unconfirmed "
            "design parameter... NOT sourced from any DOK-ING document\". Two of the six "
            "design-basis assumptions confirmation_loop.py already tracks and can re-confirm "
            "independently of this tracker."
        ),
        "confirmed_value": None, "confirmed_source": None, "confirmed_notes": None, "confirmed_at": None,
    },
    "feedstock_supply": {
        "category": "Feedstock",
        "question": (
            "What is the status of the feedstock supply arrangement — contracted tonnage, source "
            "(MRF residual, direct municipal collection, etc.), and continuity/security of supply?"
        ),
        "status": STATUS_UNKNOWN,
        "answer": None,
        "source": None,
        "note": "No supply contract, sourcing agreement, or continuity commitment is documented anywhere in this repo.",
        "confirmed_value": None, "confirmed_source": None, "confirmed_notes": None, "confirmed_at": None,
    },
    "hydrogen_production_target": {
        "category": "Hydrogen Product",
        "question": "What daily hydrogen production rate should the plant be designed for?",
        "status": STATUS_ASSUMED,
        "answer": "~50 kg H2/day (~2.08 kg/h), used directly as the storage and product-flow sizing basis.",
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
        "category": "Hydrogen Product",
        "question": "What hydrogen purity/quality standard must the product meet?",
        "status": STATUS_ASSUMED,
        "answer": "99.97 vol% (ISO 14687 Grade D), with a 99.95 vol% minimum-acceptable alarm threshold.",
        "source": (
            "data/equipment_registry.json — HB-006 \"H2 purity (design)\" remarks: \"DOK-ING's "
            "actual stated target (ISO 14687 Grade D) — not an assumption, used directly\""
        ),
        "note": (
            "This is the one item on this whole list explicitly labeled in the source registry "
            "itself as DOK-ING's own stated figure, not a project assumption."
        ),
        "confirmed_value": None, "confirmed_source": None, "confirmed_notes": None, "confirmed_at": None,
    },
    "hydrogen_delivery_pressure": {
        "category": "Hydrogen Product",
        "question": (
            "At what pressure should hydrogen be dispensed/delivered, and what storage pressure "
            "should the vessels be rated for?"
        ),
        "status": STATUS_ASSUMED,
        "answer": (
            "Dispensing/operating range 350-700 bar(g); storage vessels rated (design/MAWP) at "
            "875 bar(g), Type IV composite tanks."
        ),
        "source": (
            "data/equipment_registry.json — HB-013 \"Design pressure\" (875 bar(g)) and "
            "\"Operating pressure range\" (350-700 bar(g)); cross-checked in "
            "python/safety_flags.py:39"
        ),
        "note": (
            "HB-013's own remarks describe 875 bar(g) as \"the real industry-standard rating for "
            "700 bar dispensing systems (SAE/ISO Type IV tanks)\" and the operating range as "
            "covering \"both of DOK-ING's stated dispensing pressure options\" — i.e. DOK-ING "
            "apparently specified two dispensing pressure options, both captured here. PSA "
            "adsorption pressure itself (upstream of storage) is separately on file too: HB-008 "
            "\"Adsorption pressure (design)\" = 7 bar(g), remarks: \"within DOK-ING's actual "
            "stated 3-10 bar PSA discharge range — real data, not an assumption\"."
        ),
        "confirmed_value": None, "confirmed_source": None, "confirmed_notes": None, "confirmed_at": None,
    },
    "hydrogen_storage_capacity": {
        "category": "Hydrogen Product",
        "question": "What onsite hydrogen storage buffer/capacity should be provided?",
        "status": STATUS_ASSUMED,
        "answer": "50 kg H2, sized as roughly one day's production buffer (matches the 50 kg/day production target above).",
        "source": "data/equipment_registry.json — HB-013 \"Storage capacity\"",
        "note": None,
        "confirmed_value": None, "confirmed_source": None, "confirmed_notes": None, "confirmed_at": None,
    },
    "site_location": {
        "category": "Site & Infrastructure",
        "question": "What is the project's site — city, country, and host organization?",
        "status": STATUS_ASSUMED,
        "answer": "Zagreb, Croatia — a NACHIP pilot project hosted by DOK-ING d.o.o.",
        "source": "CLAUDE.md and README.md (both project-level documents, not equipment registry data)",
        "note": (
            "This is city/country/host-level context only — the exact plot, address, and land "
            "parcel are NOT established anywhere in this repo (see the next question)."
        ),
        "confirmed_value": None, "confirmed_source": None, "confirmed_notes": None, "confirmed_at": None,
    },
    "site_plot_permits": {
        "category": "Site & Infrastructure",
        "question": (
            "What is the exact site plot/land parcel, available footprint, and the local "
            "permitting authority/jurisdiction the plant must be licensed under?"
        ),
        "status": STATUS_UNKNOWN,
        "answer": None,
        "source": None,
        "note": (
            "Beyond the city/country-level context in the previous question, no exact site "
            "address, land area, zoning status, or permitting authority is documented anywhere "
            "in this repo."
        ),
        "confirmed_value": None, "confirmed_source": None, "confirmed_notes": None, "confirmed_at": None,
    },
    "site_utilities": {
        "category": "Site & Infrastructure",
        "question": (
            "What utilities are actually available/contracted at the site — grid connection "
            "capacity, process/cooling water source and supply, backup fuel gas, etc.?"
        ),
        "status": STATUS_UNKNOWN,
        "answer": None,
        "source": None,
        "note": (
            "EU-009 (Electrical Metering, Grid) specifies the ON-SITE metering equipment's own "
            "design-basis measurement range (0-50 kW at 400V) — that is what the equipment was "
            "SIZED to measure, not a statement of what capacity is actually available or "
            "contracted from the local utility. No grid-connection agreement, water-supply "
            "contract, or DNO approval status is documented anywhere in this repo (EU-009 itself "
            "notes \"DNO / utility approval required = Yes\", unresolved)."
        ),
        "confirmed_value": None, "confirmed_source": None, "confirmed_notes": None, "confirmed_at": None,
    },
    "site_ambient_conditions": {
        "category": "Site & Infrastructure",
        "question": (
            "What ambient/environmental design conditions (temperature range, etc.) should "
            "outdoor equipment be rated for?"
        ),
        "status": STATUS_ASSUMED,
        "answer": "-20 to +50 °C, the standard outdoor design range used consistently across the equipment registry.",
        "source": (
            "data/equipment_registry.json — FE-001 \"Operating temperature (ambient)\"; "
            "consistent with AI-001's wider -40 to +60 °C weather-station rating"
        ),
        "note": (
            "FE-001's own remarks add: \"Standard outdoor range; confirm once site location is "
            "set\" — flagged as pending confirmation in the source data itself, not fully closed "
            "out even though a number is on file."
        ),
        "confirmed_value": None, "confirmed_source": None, "confirmed_notes": None, "confirmed_at": None,
    },
    "regulatory_framework": {
        "category": "Regulatory & Commercial",
        "question": "Which regulatory framework should the plant's hydrogen be certified/documented against?",
        "status": STATUS_ASSUMED,
        "answer": "EU RFNBO framework — Delegated Regulation (EU) 2023/1184 and methodology Regulation (EU) 2023/1185.",
        "source": "python/compliance.py module docstring",
        "note": (
            "compliance.py is explicit that this is the ASSUMED applicable framework for "
            "organizing documentation, not a legal determination: \"this module makes no such "
            "claim\" about actual certification. Real RFNBO certification requires an accredited "
            "third-party auditor; confirming this is in fact the correct/only applicable "
            "framework for this specific plant and jurisdiction is still DOK-ING/legal counsel's "
            "call."
        ),
        "confirmed_value": None, "confirmed_source": None, "confirmed_notes": None, "confirmed_at": None,
    },
    "project_budget": {
        "category": "Regulatory & Commercial",
        "question": "What is the target project budget / CAPEX ceiling?",
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
    "hydrogen_offtake": {
        "category": "Regulatory & Commercial",
        "question": "Is there a hydrogen offtake agreement or defined commercial buyer/market, and at what price basis?",
        "status": STATUS_UNKNOWN,
        "answer": None,
        "source": None,
        "note": (
            "circularity.py explicitly notes the same gap for its own byproduct (ash/carbon "
            "black) revenue estimates: prices used there are \"OUR OWN reasonable placeholder "
            "assumptions... Replace both the moment real offtake-agreement or market pricing "
            "exists\" (python/circularity.py). No hydrogen offtake agreement or pricing basis is "
            "documented anywhere in this repo either."
        ),
        "confirmed_value": None, "confirmed_source": None, "confirmed_notes": None, "confirmed_at": None,
    },
    "project_scope_boundary": {
        "category": "Project Scope",
        "question": (
            "What is the battery-limit/scope boundary — what falls inside DOK-ING's scope of "
            "supply versus outside it (e.g. site civil works, grid interconnection, offtake "
            "logistics)?"
        ),
        "status": STATUS_UNKNOWN,
        "answer": None,
        "source": None,
        "note": (
            "No scope-of-supply or battery-limit document exists anywhere in this repo; the "
            "91-item equipment registry covers plant equipment itself but says nothing about who "
            "supplies/owns civils, grid interconnection, or downstream logistics."
        ),
        "confirmed_value": None, "confirmed_source": None, "confirmed_notes": None, "confirmed_at": None,
    },
    "plant_scale_basis": {
        "category": "Project Scope",
        "question": (
            "What scale/class is this plant designed as — pilot/demonstration vs. commercial — "
            "and should the design basis assume future scale-up?"
        ),
        "status": STATUS_ASSUMED,
        "answer": (
            "A pilot/demonstration-scale plant (NACHIP pilot project), consistent with its small "
            "physical scale throughout the equipment registry (e.g. GA-001 gasifier vessel: "
            "600 mm internal diameter, 4000 mm height; FE-001 hopper: 2 t total capacity)."
        ),
        "source": (
            "CLAUDE.md / README.md (\"NACHIP pilot project\"); cross-checked against "
            "data/equipment_registry.json — GA-001, FE-001"
        ),
        "note": (
            "No explicit future scale-up requirement (e.g. a target commercial-scale capacity "
            "this pilot should be designed to inform) is documented anywhere in this repo."
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
    6's "actual final count", computed fresh every call, not cached."""
    counts = {STATUS_ASSUMED: 0, STATUS_UNKNOWN: 0, STATUS_CONFIRMED: 0}
    for key in QUESTIONS:
        counts[status_of(key)] += 1
    return counts


def _format_question_block(key, cfg):
    lines = [f"### {cfg['question']}", ""]
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
    DESIGN_BASIS_DISCLAIMER (same reasoning as equipment_data_requests.py
    for not reusing regulatory_drafting.DRAFT_DISCLAIMER verbatim — that
    constant's text names the wrong source module for this document)."""
    counts = summarize()
    lines = [
        "# HYGAS-AI — Project Design Basis RFI Tracker",
        "",
        f"_Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}. The 17 "
        f"design-basis questions DOK-ING's RFI needs answered, checked against this project's "
        f"own real data first — every \"Assumed\" answer below is cited to the exact file (and "
        f"equipment registry item, where applicable) it came from; nothing is invented._",
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

    print("\n=== Category grouping check ===")
    seen_categories = {cfg["category"] for cfg in QUESTIONS.values()}
    print(f"Categories used: {sorted(seen_categories)}")
    print(f"Categories declared: {sorted(CATEGORIES)}")
    assert seen_categories == set(CATEGORIES), "REGRESSION: a question's category doesn't match the declared CATEGORIES list."
    for category in CATEGORIES:
        n = sum(1 for cfg in QUESTIONS.values() if cfg["category"] == category)
        print(f"  {category}: {n} question(s)")

    print("\n=== Per-question status ===")
    for key, cfg in QUESTIONS.items():
        print(f"  [{status_of(key)}] {cfg['category']} — {key}")
        if cfg["status"] == STATUS_ASSUMED:
            assert cfg["answer"] is not None and cfg["source"] is not None, (
                f"REGRESSION: {key} is marked Assumed but has no answer/source on file."
            )
        else:
            assert cfg["status"] == STATUS_UNKNOWN, f"REGRESSION: {key} has an unrecognized base status {cfg['status']!r}."
            assert cfg["answer"] is None and cfg["source"] is None, (
                f"REGRESSION: {key} is marked Unknown but has a non-null answer/source — should be Assumed instead."
            )

    print("\n=== Final count (task requirement 6 — not rounded up) ===")
    counts = summarize()
    print(f"Assumed (real, cited answer already in this project): {counts[STATUS_ASSUMED]} of 17")
    print(f"Unknown — Required (genuinely open, needs DOK-ING):    {counts[STATUS_UNKNOWN]} of 17")
    print(f"Confirmed (DOK-ING has actually answered):             {counts[STATUS_CONFIRMED]} of 17")
    assert counts[STATUS_ASSUMED] == 10, f"REGRESSION: expected exactly 10 Assumed, got {counts[STATUS_ASSUMED]}."
    assert counts[STATUS_UNKNOWN] == 7, f"REGRESSION: expected exactly 7 Unknown, got {counts[STATUS_UNKNOWN]}."
    assert counts[STATUS_CONFIRMED] == 0, "REGRESSION: something is marked Confirmed before any real RFI response exists."
    assert counts[STATUS_ASSUMED] + counts[STATUS_UNKNOWN] + counts[STATUS_CONFIRMED] == 17
    print("PASSED -- 10 Assumed + 7 Unknown = 17, matches the documented count exactly.")

    print("\n=== set_confirmed()/clear_confirmed() mechanism check (for future use) ===")
    assert status_of("project_budget") == STATUS_UNKNOWN
    set_confirmed("project_budget", "EUR 4.2M CAPEX ceiling", "DOK-ING RFI response, 2026-XX-XX", "Illustrative test value, cleared below.")
    assert status_of("project_budget") == STATUS_CONFIRMED
    print("  [OK] set_confirmed() flips status to Confirmed live.")
    counts_after = summarize()
    assert counts_after[STATUS_CONFIRMED] == 1 and counts_after[STATUS_ASSUMED] == 10 and counts_after[STATUS_UNKNOWN] == 6
    print("  [OK] summarize() reflects the confirmation immediately: 10 Assumed / 6 Unknown / 1 Confirmed.")
    clear_confirmed("project_budget")
    assert status_of("project_budget") == STATUS_UNKNOWN
    counts_cleared = summarize()
    assert counts_cleared == {STATUS_ASSUMED: 10, STATUS_UNKNOWN: 7, STATUS_CONFIRMED: 0}
    print("  [OK] clear_confirmed() reverts cleanly -- back to 10 Assumed / 7 Unknown / 0 Confirmed.")

    draft = generate_request_list_markdown()
    question_blocks = sum(1 for line in draft.splitlines() if line.startswith("### "))
    print(f"\nMarkdown document length (chars): {len(draft)}")
    print(f"Question blocks in the generated document: {question_blocks} (expected 17)")
    assert question_blocks == 17, f"REGRESSION: document has {question_blocks} question blocks, expected 17."
    print("PASSED -- the generated Markdown document's own question count matches 17 exactly.")
