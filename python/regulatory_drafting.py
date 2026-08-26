"""
Regulatory drafting agent v1 — drafts a compliance summary document
directly from python/compliance.py's live checklist. This is DRAFTING,
not legal writing, and generates no separate content of its own: every
fact in the output is pulled from compliance.build_checklist() at
generation time, so the draft cannot drift out of sync with what the
Compliance Documentation section itself reports.

Same spirit as compliance.py's "not a certification" disclaimer, stated
explicitly here and in the app.py UI: this output is a starting draft
that needs review by someone qualified — compliance/legal counsel, or an
accredited RFNBO auditor — before it goes anywhere near a real
submission. Nothing generated here is legal advice, and nothing here
constitutes a compliance determination.
"""
from datetime import datetime, timezone

from . import compliance

DRAFT_DISCLAIMER = (
    "**DRAFT — NOT LEGAL WRITING.** Auto-generated from this repo's live compliance "
    "checklist (python/compliance.py). It organizes real plant data into the shape a "
    "submission section might read, and nothing more — it needs review by someone "
    "qualified (compliance/legal counsel, an accredited RFNBO auditor) before any real "
    "submission. Nothing in this document is legal advice or a compliance determination."
)


def generate_draft_summary(checklist=None):
    """checklist: optionally pass a pre-built checklist (e.g. to avoid
    rebuilding it twice in the same app.py run); defaults to a fresh
    compliance.build_checklist() call.

    Returns a Markdown string. Every number and fact in it is read from
    the checklist argument (or a fresh one) at call time — nothing is a
    separately-maintained copy.
    """
    checklist = checklist if checklist is not None else compliance.build_checklist()
    counts = compliance.summarize_checklist(checklist)

    categories = []
    for item in checklist:
        if item["category"] not in categories:
            categories.append(item["category"])

    lines = [
        "# HYGAS-AI — Draft Compliance Summary",
        "",
        f"_Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} "
        f"from python/compliance.py's live checklist._",
        "",
        DRAFT_DISCLAIMER,
        "",
        "## Summary",
        "",
        f"- **{counts[compliance.EVIDENCED]}** item(s) — {compliance.EVIDENCED}",
        f"- **{counts[compliance.CONFIRMED]}** item(s) — {compliance.CONFIRMED}",
        f"- **{counts[compliance.ASSUMPTION_PENDING]}** item(s) — {compliance.ASSUMPTION_PENDING}",
        f"- **{counts[compliance.NOT_DOCUMENTED]}** item(s) — {compliance.NOT_DOCUMENTED}",
        "",
    ]

    for category in categories:
        lines.append(f"## {category}")
        lines.append("")
        for item in [i for i in checklist if i["category"] == category]:
            value_str = f" — {item['value']}" if item["value"] else ""
            lines.append(f"### {item['item']}{value_str}")
            lines.append("")
            lines.append(f"**Status:** {item['status']}  ")
            lines.append(f"**Source:** {item['source']}")
            lines.append("")
            lines.append(item["notes"])
            lines.append("")

    # Everything neither evidenced nor confirmed, gathered in one place —
    # deliberately kept separate from the category sections above so
    # nothing validated (or already confirmed) gets mixed in with what
    # still needs confirmation or documentation.
    _resolved_statuses = (compliance.EVIDENCED, compliance.CONFIRMED)
    outstanding = [i for i in checklist if i["status"] not in _resolved_statuses]
    lines.append("## Outstanding Items Requiring Confirmation")
    lines.append("")
    lines.append(
        "Everything below is either an unconfirmed design assumption or missing "
        "documentation — listed together here, separately from the evidenced/confirmed "
        "items above, so nothing resolved gets mixed in with what still needs work."
    )
    lines.append("")
    if outstanding:
        for item in outstanding:
            value_str = f" — {item['value']}" if item["value"] else ""
            lines.append(
                f"- **[{item['status']}]** {item['category']} — {item['item']}{value_str} "
                f"(source: {item['source']})"
            )
    else:
        lines.append("_None — every checklist item is currently evidenced or confirmed._")
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    checklist = compliance.build_checklist()
    draft = generate_draft_summary(checklist)
    print(draft)
    print("---")
    print("Checklist item count:", len(checklist))
    print("Draft length (chars):", len(draft))
