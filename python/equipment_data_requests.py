"""
Equipment data-request generator v1 — the missing-data equivalent of
confirmation_loop.py's draft-request pattern for the six design
assumptions, applied instead across every "Missing Data — Required"
slot python/equipment_datasheet.py already identifies across all 91
registry items (291 slots as of the AI section shipping — see that
module's own "GRAND TOTAL" self-test output).

SCOPE, same drafting-not-correspondence spirit as confirmation_loop.py
and regulatory_drafting.py: this does NOT send anything to DOK-ING or
SMITH2. It drafts a Markdown document listing every real gap, for the
user to review, edit, and actually send themselves.

HARD RULE, same as equipment_datasheet.py: nothing here is a separately
maintained or hardcoded list of gaps. build_gap_requests() calls
equipment_datasheet.build_all_datasheets()/summarize() fresh (or takes
an already-built datasheets dict, to avoid rebuilding it twice in the
same app.py run) and derives every request line from whatever category
buckets are ACTUALLY empty at call time. If new data lands in the
registry tomorrow and a category that used to be empty gets populated,
the corresponding request line disappears from the very next call —
there is no static list to fall out of sync. verify_gap_list() (and the
module's own self-test) checks this directly: it rebuilds the missing
(item_id, category) set independently from the datasheets dict and
asserts it is EXACTLY the set the generated requests cover — no more,
no less. See requirement 5 in the task this module was built for.

WHAT "HINT" MEANS HERE, and why it isn't a per-category invented
description: two real, live sources feed each request line's note,
neither of them a guess at content that isn't actually in the registry:
  1. A category-vocabulary hint, built by reaching directly into
     equipment_datasheet.py's own keyword tuples (_INPUTS_KEYWORDS,
     _OUTPUTS_KEYWORDS, etc. — the SAME tuples classify() itself reads,
     not a copy of them) and naming a few of the actual keywords that
     rule looks for. This describes what KIND of value would populate
     the slot (e.g. "a value whose parameter name reads like 'inlet',
     'feed rate', ...") without inventing a specific number or spec —
     and because it reads the live tuples, it updates itself
     automatically if those keyword lists ever change.
  2. An item-level context note, built from two things already present
     in equipment_registry.py's own data: whether the item has no
     vendor-confirmed datasheet on file yet (equipment_registry.
     needs_vendor_sourcing()), and whether any of the item's OWN
     parameter remarks (the registry's real "remarks" field, checked
     directly — see below) flag an open item ("confirm", "pending",
     "estimate", "not yet confirmed", "TBD"). Checked directly against
     the real committed registry: 12 parameter rows project-wide
     currently carry such a caveat (FE-001, GA-003, GC-006, GC-008,
     GC-009, SA-008, HB-003, HB-007, HB-012, EU-008, AI-010, AI-011) —
     e.g. GA-003's "Primary air flow rate (design)" is annotated "not
     DOK-ING-confirmed, treat as an estimate". This DOES have a visible
     effect on the current output: 38 of the 291 request lines (every
     line for an item that both carries one of these 12 caveats AND has
     at least one empty category) surface this note today, verified
     directly against build_gap_requests()'s own output.
  Note the boundary explicitly: source-1's hint is genuinely PER
  CATEGORY (it names the right keyword vocabulary for the exact missing
  slot). Source-2's hint is ITEM-level, not category-scoped — the real
  registry's remarks are written against PRESENT parameters, not
  missing ones, so there is no reliable way to attribute a specific
  remark to a specific missing category. It is surfaced anyway, on
  every missing-category line for that item, clearly labeled as a
  separate "Also:" clause, rather than silently pretending a precision
  it doesn't have.

Draft generation reuses regulatory_drafting.py's Markdown STRUCTURE —
title line, generated-timestamp line, disclaimer, "## Summary", then
grouped sections — the same shape confirmation_loop.py already reused
for its own draft. It does NOT reuse regulatory_drafting.DRAFT_DISCLAIMER
verbatim, though, unlike confirmation_loop.py: that constant's own text
specifically says "Auto-generated from this repo's live compliance
checklist (python/compliance.py)", which would misattribute THIS
document's real source (equipment_registry.py, via equipment_datasheet.py
— nothing to do with compliance.py's checklist). Checked directly
against confirmation_loop.py's own generated output: that module has
carried the same imprecise attribution since it shipped, reusing the
same constant for a document that also isn't drawn from compliance.py.
Rather than propagate that inaccuracy into a THIRD document, this module
defines its own DATA_REQUEST_DISCLAIMER below — same "draft, needs
review before you act on it" spirit and bold-header style, correct
source attribution. Fixing confirmation_loop.py's existing use is out of
scope for this module and not touched here.
"""
import re
from datetime import datetime, timezone

from . import equipment_datasheet, equipment_registry

DATA_REQUEST_DISCLAIMER = (
    "**DRAFT — NOT SENT.** Auto-generated from this repo's live equipment registry "
    "(python/equipment_registry.py), via python/equipment_datasheet.py's own \"Missing Data — "
    "Required\" classification. It organizes real, currently-missing data points into the shape "
    "of a request list, and nothing more — it has no real correspondence capability and no "
    "authority to represent you externally. Review and edit before actually sending anything to "
    "DOK-ING, SMITH2, or any other vendor/contractor."
)

# Canonical section order — same order as the nine app.py tabs (Tab 1/2
# aren't equipment sections). Used both for the body's section grouping
# (task requirement 2: "Group the output by section (FE, GA, GC, SA,
# HB, EU, AI)") and to look up each section's own id list / full name.
SECTIONS = [
    ("FE", "Feed Handling", equipment_datasheet.FE_IDS),
    ("GA", "Gasification", equipment_datasheet.GA_IDS),
    ("GC", "Gas Cleaning", equipment_datasheet.GC_IDS),
    ("SA", "Sensors & Analysers", equipment_datasheet.SA_IDS),
    ("HB", "Hydrogen & BoP", equipment_datasheet.HB_IDS),
    ("EU", "Electrical & Utilities", equipment_datasheet.EU_IDS),
    ("AI", "Automation & Instrumentation", equipment_datasheet.AI_IDS),
]

_CATEGORY_KEYWORDS = {
    "Inputs": equipment_datasheet._INPUTS_KEYWORDS,
    "Outputs": equipment_datasheet._OUTPUTS_KEYWORDS,
    "Measurements": equipment_datasheet._MEASUREMENTS_KEYWORDS,
    "Operating Conditions": equipment_datasheet._OPERATING_KEYWORDS,
    "Performance Indicators": equipment_datasheet._PERFORMANCE_KEYWORDS,
    # "Parameters" deliberately absent — it's classify()'s default
    # bucket, not matched by a keyword list of its own; see
    # _category_hint() below.
}

# The real registry's own caveat language — checked directly against
# every parameter's "remarks" field project-wide (see module docstring
# for the six current matches and why none currently overlaps a missing
# slot).
_CAVEAT_PATTERN = re.compile(
    r"confirm|pending|estimate|not[\s-]?(?:yet[\s-]?)?confirmed|tbd|to be determined", re.I
)


def _category_hint(category):
    """What kind of value would fill this category — read live from
    equipment_datasheet.classify()'s own keyword tuples, not a
    hand-written description that could drift out of sync with the
    actual rule."""
    keywords = _CATEGORY_KEYWORDS.get(category)
    if keywords:
        sample = ", ".join(f'"{k}"' for k in keywords[:3])
        return (
            f"Would need a real value whose parameter name reads like {sample}, etc. — the "
            f"same keyword vocabulary python/equipment_datasheet.py's classify() already uses "
            f"to sort a parameter into {category}."
        )
    return (
        "Would need a real design/construction spec not already captured elsewhere on this "
        "datasheet (dimensions, materials, ratings, etc.) — Parameters is classify()'s default "
        "bucket, not matched by any of the other five categories' own keywords."
    )


def _item_context_notes(item):
    """Item-level (not category-scoped) context, from two real registry
    facts — see module docstring's "WHAT HINT MEANS HERE" section for
    why these two and not an invented per-category guess."""
    notes = []
    if equipment_registry.needs_vendor_sourcing(item):
        notes.append("no vendor-confirmed datasheet is on file for this item yet either — see Vendor Sourcing")
    for p in item["parameters"]:
        remark = p.get("remarks") or ""
        if remark and _CAVEAT_PATTERN.search(remark):
            notes.append(f"registry remark on \"{p['parameter']}\" flags an open item: \"{remark}\"")
    return notes


def build_gap_requests(datasheets=None):
    """Returns one dict per "Missing Data — Required" slot, LIVE from
    equipment_datasheet.build_all_datasheets() (or a dict already built
    by the caller, to avoid rebuilding it twice in the same app.py run —
    same optional-arg pattern as equipment_datasheet.summarize()).
    Grouped by section, and within each section sorted so the
    most-complete items (fewest missing categories) come first and the
    sparsest items come last — see task requirement 2."""
    datasheets = datasheets if datasheets is not None else equipment_datasheet.build_all_datasheets()
    requests = []
    for section_label, section_name, ids in SECTIONS:
        section_items = []
        for item_id in ids:
            entry = datasheets.get(item_id)
            if entry is None:
                continue
            item = entry["item"]
            sheet = entry["datasheet"]
            missing_cats = [c for c in equipment_datasheet.CATEGORIES if not sheet[c]]
            if missing_cats:
                section_items.append((item_id, item, missing_cats))
        # Fewest missing categories first (most-complete items first),
        # item id as a stable tiebreak.
        section_items.sort(key=lambda t: (len(t[2]), t[0]))
        for item_id, item, missing_cats in section_items:
            context_notes = _item_context_notes(item)
            for category in missing_cats:
                requests.append({
                    "section": section_label, "section_name": section_name,
                    "item_id": item_id, "item_name": item["name"],
                    "category": category,
                    "hint": _category_hint(category),
                    "context_notes": context_notes,
                })
    return requests


def verify_gap_list(datasheets=None):
    """The live-sync check task requirement 5 asks for: rebuilds the set
    of actually-missing (item_id, category) pairs directly from the
    datasheets dict, independently of build_gap_requests(), and returns
    both sets so a caller (the self-test below, or app.py) can assert
    exact equality — nothing genuinely present in the registry is
    listed as a request, and nothing actually missing is left out."""
    datasheets = datasheets if datasheets is not None else equipment_datasheet.build_all_datasheets()
    requests = build_gap_requests(datasheets)
    request_pairs = {(r["item_id"], r["category"]) for r in requests}
    actual_missing_pairs = {
        (item_id, cat)
        for item_id, entry in datasheets.items()
        for cat in equipment_datasheet.CATEGORIES
        if not entry["datasheet"][cat]
    }
    return requests, request_pairs, actual_missing_pairs


def _format_request_line(req):
    """One request: item ID, item name, missing category, and a hint —
    task requirement 1, one line per gap so the whole document stays a
    flat, scannable, copy-pasteable list."""
    note = req["hint"]
    if req["context_notes"]:
        note += " Also: " + "; ".join(req["context_notes"]) + "."
    return f"- **{req['item_id']}** — {req['item_name']} — *{req['category']}*: Missing Data — Required. {note}"


def generate_request_list_markdown(datasheets=None):
    """The downloadable Markdown document — same generate-from-live-data
    approach and header/disclaimer/summary/section structure as
    regulatory_drafting.generate_draft_summary() and confirmation_loop.
    generate_all_requests_draft(), but with its own DATA_REQUEST_DISCLAIMER
    (see module docstring for why it isn't regulatory_drafting.
    DRAFT_DISCLAIMER verbatim)."""
    datasheets = datasheets if datasheets is not None else equipment_datasheet.build_all_datasheets()
    requests = build_gap_requests(datasheets)
    combined_summary = equipment_datasheet.summarize(datasheets)

    section_summaries = []
    for section_label, section_name, ids in SECTIONS:
        s = equipment_datasheet.summarize(datasheets, ids=ids)
        n_requests = sum(1 for r in requests if r["section"] == section_label)
        pct_missing = (
            s["missing_category_slots"] / s["total_category_slots"] * 100
            if s["total_category_slots"] else 0.0
        )
        section_summaries.append({
            "label": section_label, "name": section_name, "n_requests": n_requests,
            "populated": s["populated_category_slots"], "total": s["total_category_slots"],
            "pct_missing": pct_missing,
        })
    # Task requirement 3: "so DOK-ING/SMITH2 can see at a glance where
    # their engineering documentation is thinnest" — summary sorted
    # sparsest-first (highest % missing first), independent of the
    # body's canonical FE->AI section order below.
    summary_sorted = sorted(section_summaries, key=lambda s: s["pct_missing"], reverse=True)

    total_slots = combined_summary["total_category_slots"]
    populated_slots = combined_summary["populated_category_slots"]
    pct_complete = populated_slots / total_slots * 100 if total_slots else 0.0

    lines = [
        "# HYGAS-AI — Equipment Data Request List",
        "",
        f"_Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} directly from the "
        f"live equipment registry (python/equipment_registry.py), via python/equipment_datasheet.py's "
        f"own \"Missing Data — Required\" classification. Nothing below is a separately maintained "
        f"list — every line reflects a real, currently-empty category slot at generation time, and "
        f"will stop appearing on its own once real data fills that slot._",
        "",
        DATA_REQUEST_DISCLAIMER,
        "",
        "## Summary — requests by section (thinnest documentation first)",
        "",
        f"**{combined_summary['missing_category_slots']}** total data requests across all 91 "
        f"registry items ({populated_slots} of {total_slots} possible (item × category) slots "
        f"already populated — {pct_complete:.1f}% complete).",
        "",
    ]
    for s in summary_sorted:
        lines.append(
            f"- **{s['label']}** ({s['name']}) — {s['n_requests']} request(s), "
            f"{s['populated']}/{s['total']} slots populated ({s['pct_missing']:.0f}% missing)"
        )
    lines.append("")

    for section_label, section_name, ids in SECTIONS:
        section_requests = [r for r in requests if r["section"] == section_label]
        lines.append(f"## {section_label} — {section_name} ({len(section_requests)} request(s))")
        lines.append("")
        if not section_requests:
            lines.append("_None — every item in this section already has all six categories populated._")
        else:
            for r in section_requests:
                lines.append(_format_request_line(r))
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    datasheets = equipment_datasheet.build_all_datasheets()

    print("=== Gap-list live-sync verification ===")
    requests, request_pairs, actual_missing_pairs = verify_gap_list(datasheets)
    print(f"Generated requests: {len(requests)}")
    print(f"Unique (item, category) pairs requested: {len(request_pairs)}")
    print(f"Actually-missing (item, category) pairs in the datasheets: {len(actual_missing_pairs)}")
    assert len(requests) == len(request_pairs), "REGRESSION: a duplicate (item, category) request was generated!"
    assert request_pairs == actual_missing_pairs, (
        "REGRESSION: the generated request list does not exactly match the real missing slots -- "
        f"in requests but not actually missing: {request_pairs - actual_missing_pairs or 'none'}; "
        f"actually missing but not requested: {actual_missing_pairs - request_pairs or 'none'}"
    )
    print("PASSED -- the request list exactly matches every real 'Missing Data - Required' slot, "
          "no more, no less.")

    combined = equipment_datasheet.summarize(datasheets)
    print(f"\nequipment_datasheet's own missing_category_slots: {combined['missing_category_slots']} "
          f"(expected 291)")
    assert combined["missing_category_slots"] == 291, (
        f"REGRESSION: expected 291 missing slots (the known current gap count), got "
        f"{combined['missing_category_slots']} -- either the registry changed or a section's "
        f"keyword rule changed; re-verify before shipping."
    )
    assert len(requests) == 291, f"REGRESSION: generated {len(requests)} requests, expected exactly 291."

    print("\n=== Caveat-note check: registry remarks flagged as an open item, and where they surface ===")
    caveated_lines = [r for r in requests if any("registry remark on" in n for n in r["context_notes"])]
    caveated_items = sorted({r["item_id"] for r in caveated_lines})
    print(f"Request lines carrying a registry-remark caveat note: {len(caveated_lines)} (expected 38)")
    print(f"Distinct items involved: {caveated_items}")
    assert len(caveated_lines) == 38, (
        f"REGRESSION: expected 38 request lines with a registry-remark caveat note, got "
        f"{len(caveated_lines)} -- re-verify the docstring's claim before shipping."
    )
    print("PASSED -- the docstring's '38 of 291 lines carry a caveat note' claim is verified live.")
    print("PASSED -- exactly 291 request lines generated, matching the known current gap count.")

    print("\n=== Per-section request counts ===")
    for section_label, section_name, ids in SECTIONS:
        n = sum(1 for r in requests if r["section"] == section_label)
        print(f"  {section_label} ({section_name}): {n} request(s)")

    print("\n=== Sample: first 3 request lines ===")
    for r in requests[:3]:
        print(" ", _format_request_line(r))

    draft = generate_request_list_markdown(datasheets)
    # Both the summary section and the per-item body use "- **" bullets
    # (e.g. "- **AI** (Automation & Instrumentation) — 67 request(s)...");
    # only the body's request lines carry "Missing Data — Required", so
    # that phrase is what distinguishes an actual request line from a
    # summary-table row.
    body_line_count = sum(1 for line in draft.splitlines() if line.startswith("- **") and "Missing Data" in line)
    print(f"\nMarkdown document length (chars): {len(draft)}")
    print(f"Request bullet lines in the generated document: {body_line_count} (expected 291)")
    assert body_line_count == 291, f"REGRESSION: document body has {body_line_count} request lines, expected 291."
    print("PASSED -- the generated Markdown document's own bullet-line count matches 291 exactly.")
