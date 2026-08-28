"""
Equipment data-request routing v1 — classifies a likely OWNER for each
of equipment_data_requests.py's real "Missing Data — Required" gaps, so
the 284-item ask can actually be routed to whoever is realistic to
answer it, instead of being sent to DOK-ING as one undifferentiated
list.

HONESTY, stated up front and repeated in the generated document's own
disclaimer: this is a REASONABLE INFERENCE from equipment TYPE and
CATEGORY, not a confirmed fact. Nothing here is DOK-ING-stated. Where
the reasoning genuinely doesn't resolve cleanly, the item is routed to
"Uncertain / needs discussion" rather than forced into a bucket just to
avoid an empty one — the same discipline as everywhere else in this
project: never manufacture confidence that isn't there.

FOUR OWNER CATEGORIES, and the reasoning behind each (task requirement
2 — auditable at the bucket level, not necessarily one sentence per
item):

  OWNER_VENDOR ("Vendor (equipment not yet selected)") — a category
  whose real content only exists once a specific manufacturer/model is
  chosen: instrument accuracy, response time, calibration interval
  (Measurements); a rated discharge/output capacity (Outputs);
  guaranteed efficiency/recovery-rate (Performance Indicators);
  dimensions/materials/construction (Parameters). No amount of process
  engineering or DOK-ING's own project knowledge can state a specific
  vendor's own delivered spec before that vendor is picked.

  OWNER_DOKING ("DOK-ING (project-level knowledge)") — applied in two
  distinct, narrow ways, not as a catch-all:
    1. DOK-ING's OWN core process technology (the gasifier train, and
       the primary WGS+PSA purification/compression/storage route) —
       DOK-ING's real RFI answers already demonstrate they know this
       process's own feed rate, pressures, and purity targets directly,
       not via an external process engineer or a vendor. For exactly
       these items, the process-design categories (Inputs, Operating
       Conditions) are routed to DOK-ING rather than the generic
       "Design/process engineer" bucket, because DOK-ING IS that
       engineer for their own proprietary technology.
    2. Site/external-infrastructure INTERCONNECTION equipment (grid
       metering, district-heating heat exchanger and metering) — these
       items exist specifically to interface with infrastructure
       outside the plant boundary; only the entity actually deploying
       at a real site (DOK-ING, or whoever they're building for) knows
       the site-specific interconnection facts (contracted capacity,
       network conditions, billing arrangement). No vendor spec sheet
       or abstract design calculation can supply this.

  OWNER_DESIGN ("Design/process engineer") — a category that is a
  function of PROCESS DESIGN CHOICES, not a vendor's product and not
  something DOK-ING would already know off-hand: the required feed/
  flow rate an item must be sized to handle (Inputs), and the process
  operating setpoint it must run at (Operating Conditions), for
  equipment DOK-ING does NOT itself own the core technology for
  (generic balance-of-plant: feed handling, gas cleaning, electrical/
  utilities, and the auxiliary/optional H2 pathways — membrane
  separation, electrolysis, LOHC, dispensing). Also applied to the
  automation/software layer's integration-and-architecture decisions
  (data-flow direction, protocol/redundancy choices, target performance
  levels) — these are systems-design calls a controls/automation
  engineer makes, not a hardware vendor's spec sheet fact.

  OWNER_UNCERTAIN ("Uncertain / needs discussion") — reserved for one
  specific, honestly-flagged case: the "Measurements" category for the
  automation/software items (AI-004 and later — PLCs, gateways, servers,
  firewalls, databases). For physical process equipment, "Measurements"
  unambiguously means an instrument's own spec (Vendor). For IT/network
  infrastructure, it's genuinely ambiguous whether the gap means "what
  telemetry hardware spec does this box have" (Vendor) or "what
  monitoring/observability capability should the architecture provide"
  (Design/process engineer) — routed here rather than guessed either
  way.

WHICH ITEMS FALL INTO DOK-ING's OWN CORE PROCESS vs. GENERIC/AUXILIARY
EQUIPMENT — the one judgment call this module makes at the item level,
not just the category level, stated explicitly so it's checkable:
  CORE (DOK-ING's own "Looper" gasification + primary WGS/PSA route):
    all of GA (GA-001 through GA-010); HB-001 through HB-009 (WGS
    reactors, heat exchanger, steam generator, PSA train, tail-gas
    recycle); HB-012 (H2 compressor) and HB-013 (primary H2 storage) —
    both serving that same primary route.
  NOT core, treated as generic/likely-externally-sourced instead, even
  though they're in the HB section: HB-010 (Membrane Separator — a
  PARALLEL purification technology, not the primary PSA route: 85%
  recovery / 95-98% purity vs. PSA's 99.97%); HB-011, HB-014, HB-015,
  HB-016 (all explicitly labeled "Auxiliary/Optional" in the registry
  itself — an electrolyser and an LOHC train are their own distinct
  technology categories, not DOK-ING's core gasification IP); HB-017
  (downstream of the LOHC train, same reasoning); HB-018 (a dispensing
  station — standardized, commercially available H2 refuelling
  equipment, an interface component, not core conversion technology).
  FE (feed handling) and GC (gas cleaning) are treated as generic
  balance-of-plant throughout — conveyors, shredders, cyclones,
  scrubbers, and bag filters are standard industrial equipment types,
  commonly vendor-sourced even by specialized process technology
  providers; DOK-ING's own RFI answers frame their core identity around
  the gasification-to-H2 conversion itself, not this supporting
  equipment.

INSTRUMENT-ONLY SECTIONS (task's own explicit guidance): all of SA
(gas analysers/sensors, 12 items) plus AI-001/002/003 (Weather Station,
Camera, Bed Pressure-Drop Sensor — physical field instruments, not
software/network infrastructure) → Vendor for every missing category,
same reasoning as the vendor rule above: there's no meaningful
"process design vs. vendor" split for equipment that IS the
instrument.
"""
from . import equipment_data_requests, equipment_datasheet, equipment_rfi_fills

OWNER_VENDOR = "Vendor (equipment not yet selected)"
OWNER_DOKING = "DOK-ING (project-level knowledge)"
OWNER_DESIGN = "Design/process engineer"
OWNER_UNCERTAIN = "Uncertain / needs discussion"

OWNERS = [OWNER_VENDOR, OWNER_DOKING, OWNER_DESIGN, OWNER_UNCERTAIN]

# DOK-ING's own core process technology (see module docstring) — every
# other GA/HB item, plus all of FE/GC/EU/SA/AI, is treated as generic/
# auxiliary/instrument equipment instead.
_CORE_PROCESS_ITEMS = frozenset(
    equipment_datasheet.GA_IDS
    + [f"HB-{i:03d}" for i in range(1, 10)]  # HB-001..HB-009
    + ["HB-012", "HB-013"]
)

# Site/external-infrastructure interconnection equipment — routed to
# DOK-ING for every missing category regardless of which category it is
# (see module docstring, OWNER_DOKING reason 2).
_SITE_INTERCONNECT_ITEMS = frozenset(["EU-009", "EU-012", "EU-013"])

# Physical field instruments outside the SA section that get the same
# "it IS the instrument" treatment as SA.
_AI_INSTRUMENT_ITEMS = frozenset(["AI-001", "AI-002", "AI-003"])


def classify_owner(item_id, category):
    """Returns (owner, reason) for one (item_id, category) gap. `reason`
    is a short, stated justification — always non-empty, always
    traceable to the rules documented in this module's own docstring."""
    section = item_id.split("-")[0]

    # -- Instrument-only equipment: SA section, and the 3 physical AI
    # field instruments. There's no vendor/design split for equipment
    # that IS the instrument -- every category is a product spec.
    if section == "SA" or item_id in _AI_INSTRUMENT_ITEMS:
        return OWNER_VENDOR, (
            "This item IS a physical instrument/sensor — every spec (range, accuracy, "
            "response time, output signal, mounting) is inherent to the specific model "
            "chosen, not derivable before a vendor is selected."
        )

    # -- Automation/software/network infrastructure (AI-004 onward).
    if section == "AI":
        if category == "Measurements":
            return OWNER_UNCERTAIN, (
                "\"Measurements\" for IT/network infrastructure is genuinely ambiguous — "
                "could mean a specific product's own telemetry/hardware spec (Vendor) or a "
                "monitoring/observability capability the system architecture should specify "
                "(Design/process engineer). Not forced into either without more context."
            )
        return OWNER_DESIGN, (
            "Data-flow direction, integration points, protocol/redundancy choices, and "
            "target performance levels for automation/software infrastructure are "
            "systems-architecture decisions a controls/automation engineer makes — not a "
            "hardware vendor's spec sheet fact, and not something DOK-ING's core process "
            "expertise (gasification/WGS/PSA) covers directly."
        )

    # -- Site/external-infrastructure interconnection equipment: always
    # DOK-ING, regardless of category.
    if item_id in _SITE_INTERCONNECT_ITEMS:
        return OWNER_DOKING, (
            "This item exists specifically to interface with infrastructure OUTSIDE the "
            "plant boundary (the grid, a district heating network) — only the entity "
            "actually deploying at a real site knows the site-specific interconnection "
            "facts (contracted capacity, network conditions, billing arrangement); no "
            "vendor spec sheet or abstract design calculation supplies this."
        )

    # -- Everything else: physical process/BoP equipment (FE, GA, GC,
    # HB, EU). Category-level split, with the core-vs-generic item
    # distinction (see module docstring) deciding whether the
    # process-design categories go to DOK-ING or a Design/process
    # engineer.
    is_core = item_id in _CORE_PROCESS_ITEMS
    if category in ("Inputs", "Operating Conditions"):
        if is_core:
            return OWNER_DOKING, (
                "This item is part of DOK-ING's own core gasification + primary WGS/PSA "
                "process (\"the Looper\") — their real RFI answers already show they know "
                "this process's own feed rate, pressures, and operating targets directly, "
                "not via an external process engineer."
            )
        return OWNER_DESIGN, (
            "The required feed/flow rate and operating setpoint for this generic/auxiliary "
            "balance-of-plant item are process-design calculations needed to size and "
            "interface it with DOK-ING's core process — not a vendor's product fact, and "
            "not something settled independent of that design work."
        )
    # Measurements, Outputs, Performance Indicators, Parameters.
    return OWNER_VENDOR, (
        "A rated output/discharge capacity, an instrument's accuracy/calibration, a "
        "guaranteed efficiency or recovery rate, or basic construction specs (dimensions, "
        "materials) only exist once a specific manufacturer/model is chosen for this item."
    )


def route_requests(requests):
    """Returns a NEW list of dicts (requests are not mutated) — each
    original request dict plus "owner" and "owner_reason" keys."""
    routed = []
    for r in requests:
        owner, reason = classify_owner(r["item_id"], r["category"])
        routed.append({**r, "owner": owner, "owner_reason": reason})
    return routed


def summarize_by_owner(routed_requests):
    """Counts by owner — task requirement 5's honest breakdown."""
    counts = {o: 0 for o in OWNERS}
    for r in routed_requests:
        counts[r["owner"]] += 1
    return counts


ROUTING_DISCLAIMER = (
    "**This routing is a REASONABLE INFERENCE, not a confirmed fact.** Each item below was "
    "classified by equipment type and missing category — never DOK-ING-stated. DOK-ING should "
    "correct any item that's actually routed to the wrong owner; this list exists to make that "
    "correction easy (each item states its own reasoning), not to preempt it. Items this module "
    "isn't confident about are marked \"Uncertain / needs discussion\" rather than forced into a "
    "bucket — see python/equipment_request_routing.py for the full stated logic behind every "
    "bucket."
)


def _format_routed_line(r):
    return (
        f"- **{r['item_id']}** — {r['item_name']} — *{r['category']}*: Missing Data — "
        f"Required. {r['hint']}"
    )


def generate_routed_request_document(routed_requests=None):
    """The downloadable Markdown document — grouped by likely OWNER as
    the primary structure (task requirement 3), equipment SECTION as
    the secondary grouping within each owner. Same generate-from-live-
    data approach as equipment_data_requests.generate_request_list_
    markdown(), with its own disclaimer (ROUTING_DISCLAIMER above) —
    not regulatory_drafting.DRAFT_DISCLAIMER or equipment_data_requests
    .DATA_REQUEST_DISCLAIMER verbatim, since neither describes routing
    at all; same precedent as every prior module in this project that
    declined to reuse a disclaimer naming the wrong thing."""
    from datetime import datetime, timezone

    if routed_requests is None:
        datasheets = equipment_rfi_fills.apply_rfi_fills(equipment_datasheet.build_all_datasheets())
        routed_requests = route_requests(equipment_data_requests.build_gap_requests(datasheets))

    counts = summarize_by_owner(routed_requests)
    total = len(routed_requests)

    lines = [
        "# HYGAS-AI — Equipment Data Request List, Routed by Likely Owner",
        "",
        f"_Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} from the live "
        f"equipment registry gap list (python/equipment_data_requests.py), with a likely-owner "
        f"classification layered on top (python/equipment_request_routing.py) so these "
        f"{total} requests can be routed to whoever's realistic to answer each one, instead of "
        f"sent to DOK-ING as one undifferentiated list._",
        "",
        ROUTING_DISCLAIMER,
        "",
        "## Summary — requests by likely owner",
        "",
    ]
    for owner in OWNERS:
        pct = counts[owner] / total * 100 if total else 0.0
        lines.append(f"- **{owner}** — {counts[owner]} request(s) ({pct:.0f}% of {total})")
    lines.append("")

    for owner in OWNERS:
        owner_requests = [r for r in routed_requests if r["owner"] == owner]
        lines.append(f"## {owner} ({len(owner_requests)} request(s))")
        lines.append("")
        if not owner_requests:
            lines.append("_None._")
            lines.append("")
            continue
        for section_label, section_name, _ in equipment_data_requests.SECTIONS:
            section_requests = [r for r in owner_requests if r["section"] == section_label]
            if not section_requests:
                continue
            lines.append(f"### {section_label} — {section_name} ({len(section_requests)} request(s))")
            lines.append("")
            for r in section_requests:
                lines.append(_format_routed_line(r))
                lines.append(f"  *Likely owner reasoning:* {r['owner_reason']}")
            lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    datasheets = equipment_rfi_fills.apply_rfi_fills(equipment_datasheet.build_all_datasheets())
    requests = equipment_data_requests.build_gap_requests(datasheets)
    print(f"Total gap requests: {len(requests)} (expected 284)")
    assert len(requests) == 284, f"REGRESSION: expected 284 gap requests, got {len(requests)}."

    print("\n=== Routing every gap -- verify nothing crashes, nothing left unclassified ===")
    routed = route_requests(requests)
    assert len(routed) == len(requests)
    for r in routed:
        assert r["owner"] in OWNERS, f"REGRESSION: {r['item_id']}/{r['category']} got an unrecognized owner {r['owner']!r}."
        assert r["owner_reason"] and r["owner_reason"].strip(), f"REGRESSION: {r['item_id']}/{r['category']} has an empty reason."
    print(f"PASSED -- all {len(routed)} gaps classified into one of {OWNERS}, each with a non-empty stated reason.")

    print("\n=== Task requirement 5: honest breakdown by owner ===")
    counts = summarize_by_owner(routed)
    for owner in OWNERS:
        pct = counts[owner] / len(routed) * 100
        print(f"  {owner}: {counts[owner]} ({pct:.1f}%)")
    assert sum(counts.values()) == 284
    print(f"PASSED -- {sum(counts.values())} total, matches 284 exactly.")

    print("\n=== Spot checks against the module's own stated rules ===")
    SPOT_CHECKS = [
        # (item_id, category, expected_owner)
        ("SA-001", "Inputs", OWNER_VENDOR),           # instrument-only section
        ("AI-001", "Outputs", OWNER_VENDOR),           # physical field instrument
        ("AI-004", "Inputs", OWNER_DESIGN),            # automation architecture
        ("AI-006", "Measurements", OWNER_UNCERTAIN),   # ambiguous IT measurements
        ("EU-009", "Outputs", OWNER_DOKING),           # site interconnection override
        ("EU-013", "Operating Conditions", OWNER_DOKING),  # site interconnection override
        ("GA-002", "Inputs", OWNER_DOKING),            # DOK-ING's own core process
        ("GA-003", "Operating Conditions", OWNER_DOKING),
        ("GA-006", "Outputs", OWNER_VENDOR),           # core item, but Outputs still vendor
        ("HB-005", "Inputs", OWNER_DOKING),            # core WGS/steam train
        ("HB-018", "Inputs", OWNER_DESIGN),            # dispensing -- NOT core, generic BoP
        ("HB-011", "Operating Conditions", OWNER_DESIGN),  # electrolyser -- auxiliary/optional
        ("HB-014", "Inputs", OWNER_DESIGN),            # LOHC train -- auxiliary/optional
        ("FE-007", "Outputs", OWNER_VENDOR),
        ("FE-003", "Operating Conditions", OWNER_DESIGN),  # generic BoP
        ("GC-002", "Inputs", OWNER_DESIGN),            # generic BoP
    ]
    for item_id, category, expected in SPOT_CHECKS:
        owner, reason = classify_owner(item_id, category)
        status = "OK" if owner == expected else "MISMATCH"
        print(f"  [{status}] {item_id}/{category} -> {owner} (expected {expected})")
        assert owner == expected, f"REGRESSION: {item_id}/{category} routed to {owner!r}, expected {expected!r}."
    print(f"PASSED -- {len(SPOT_CHECKS)} spot-checks against the module's own stated rules all matched.")

    draft = generate_routed_request_document(routed)
    request_lines = sum(1 for line in draft.splitlines() if line.startswith("- **") and "Missing Data" in line)
    print(f"\nMarkdown document length (chars): {len(draft)}")
    print(f"Request lines in the generated document: {request_lines} (expected 284)")
    assert request_lines == 284, f"REGRESSION: document has {request_lines} request lines, expected 284."
    print("PASSED -- the generated routed document's own line count matches 284 exactly.")
