"""
The one place that decides the status of a registry / fill row (provenance phase 2).

There is NO default to Confirmed. Until this change `equipment_datasheet.slot_status()` counted any row without a status key as Confirmed, which made 766 registry rows "Confirmed" although only 16
have a DOK-ING line in the repo. Now a row's status comes from exactly one of:

  1. an explicit status on the row itself (the 48 ESTIMATE_FILLS rows carry "Engineering Estimate (Not Vendor/DOK-ING Confirmed)" and keep it). An explicit "Confirmed" with no citation is NOT honoured;
  2. an entry of data/registry_status_overlay.json, generated from the owner's worksheet (data/provenance/provenance_worksheet_filled.csv):
         DOK-ING + source -> Confirmed;  SIMILAR_PLANT + source -> Estimated (literature-informed);  ASSUMED + note -> Assumed;  CALCULATED + source -> Calculated
     An entry that breaks its own rule (DOK-ING without a source, a status that does not match the origin, an unknown origin) is IGNORED, so a corrupted overlay can never produce a Confirmed row;
  3. otherwise: "Unverified (registry)" -- no stated origin yet. Never a guess, never Confirmed.

A missing, unreadable or malformed overlay file means every row is "Unverified (registry)".

This module imports nothing from the project (equipment_datasheet imports it). Display only: nothing in the engine, the snapshot or the runtime reads it. Python 3.11-compatible.
"""
import json
import os

STATUS_CONFIRMED = "Confirmed"
STATUS_ESTIMATED = "Estimated"
STATUS_ASSUMED = "Assumed"
STATUS_CALCULATED = "Calculated"
STATUS_UNVERIFIED = "Unverified (registry)"

ORIGIN_DOKING, ORIGIN_SIMILAR, ORIGIN_ASSUMED, ORIGIN_CALCULATED, ORIGIN_UNKNOWN = "DOK-ING", "SIMILAR_PLANT", "ASSUMED", "CALCULATED", "UNKNOWN"
ORIGINS = (ORIGIN_DOKING, ORIGIN_SIMILAR, ORIGIN_ASSUMED, ORIGIN_CALCULATED, ORIGIN_UNKNOWN)
ORIGIN_TO_STATUS = {ORIGIN_DOKING: STATUS_CONFIRMED, ORIGIN_SIMILAR: STATUS_ESTIMATED, ORIGIN_ASSUMED: STATUS_ASSUMED, ORIGIN_CALCULATED: STATUS_CALCULATED}
# the owner column that must be non-empty for each origin (the citation a Confirmed / Estimated / Calculated status stands on, the reason for an Assumed one)
REQUIRED_FIELD = {
    ORIGIN_DOKING: ("source", "Confirmed needs a citable DOK-ING source (document name, date, page/line or e-mail date)"),
    ORIGIN_SIMILAR: ("source", "SIMILAR_PLANT needs a source (paper, plant, URL or the project's literature reference)"),
    ORIGIN_ASSUMED: ("note", "ASSUMED needs a reason in `note`"),
    ORIGIN_CALCULATED: ("source", "CALCULATED needs the formula or script reference in `source`"),
}
SOURCE_REGISTRY, SOURCE_RFI, SOURCE_ESTIMATE = "registry", "RFI_FILLS", "ESTIMATE_FILLS"

# what the app prints for a status (display wording; the status values above are what code compares)
LABELS = {STATUS_CONFIRMED: "Confirmed", STATUS_ESTIMATED: "Estimated (literature-informed)", STATUS_ASSUMED: "Assumed", STATUS_CALCULATED: "Calculated",
          STATUS_UNVERIFIED: "Unverified (registry)"}
# strongest evidence first; used for the label of a slot (its best row). An explicit Engineering Estimate ranks with Estimated.
LABEL_RANK = (STATUS_CONFIRMED, STATUS_CALCULATED, STATUS_ESTIMATED, "Engineering Estimate", STATUS_ASSUMED, STATUS_UNVERIFIED)

OVERLAY_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "registry_status_overlay.json")
_cache = {}


def row_id(source, item_id, parameter):
    """Stable id of one datasheet row: `<source>|<item>|<field>`."""
    return f"{source}|{item_id}|{parameter}"


def entry_problem(entry):
    """None if an overlay entry may be honoured; otherwise why not."""
    if not isinstance(entry, dict):
        return "entry is not an object"
    origin = entry.get("origin")
    if origin not in ORIGIN_TO_STATUS:
        return f"origin {origin!r} maps to no status"
    if entry.get("status") != ORIGIN_TO_STATUS[origin]:
        return f"status {entry.get('status')!r} does not match origin {origin} ({ORIGIN_TO_STATUS[origin]})"
    field, message = REQUIRED_FIELD[origin]
    if not str(entry.get(field) or "").strip():
        return message
    return None


def load_overlay(path=None):
    """(entries, header). Entries that break their own rule are dropped; a missing / unreadable / malformed file gives ({}, {"error": ...}) = everything Unverified. Cached per file mtime."""
    path = os.path.abspath(path or OVERLAY_PATH)
    try:
        stamp = os.stat(path).st_mtime_ns
    except OSError:
        return {}, {"error": f"{os.path.basename(path)} not found"}
    if _cache.get(path, (None,))[0] == stamp:
        return _cache[path][1], _cache[path][2]
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        raw = doc["entries"]
        header = doc.get("header", {})
        if not isinstance(raw, dict):
            raise ValueError("entries is not an object")
    except (OSError, ValueError, KeyError, TypeError) as e:
        return {}, {"error": f"{os.path.basename(path)} unreadable: {e}"}
    entries = {rid: e for rid, e in raw.items() if entry_problem(e) is None}
    header = dict(header, n_ignored=len(raw) - len(entries))
    _cache[path] = (stamp, entries, header)
    return entries, header


def resolve_row(source_kind, item_id, row, overlay=None):
    """The status of one datasheet row: {"status", "label", "citation", "origin", "reason"}. `overlay` = entries dict (default: the committed overlay)."""
    explicit = row.get("status")
    if explicit and explicit != STATUS_CONFIRMED:
        return {"status": explicit, "label": explicit if explicit not in LABELS else LABELS[explicit], "citation": row.get("source", ""), "origin": "", "reason": "explicit status on the row"}
    entries = overlay if overlay is not None else load_overlay()[0]
    entry = entries.get(row_id(source_kind, item_id, row["parameter"]))
    if entry is not None and entry_problem(entry) is None:
        status = ORIGIN_TO_STATUS[entry["origin"]]
        citation = entry.get("source") or entry.get("note") or ""
        return {"status": status, "label": LABELS[status], "citation": citation, "origin": entry["origin"], "reason": "owner's worksheet answer (overlay)"}
    why = "an explicit Confirmed with no overlay entry is not honoured" if explicit == STATUS_CONFIRMED else "no stated origin"
    return {"status": STATUS_UNVERIFIED, "label": LABELS[STATUS_UNVERIFIED], "citation": "", "origin": "", "reason": why}


def label_of(status):
    """Display label of a status value (an explicit Engineering Estimate keeps its own text)."""
    return LABELS.get(status, status)


def rank_of(status):
    key = "Engineering Estimate" if isinstance(status, str) and status.startswith("Engineering Estimate") else status
    return LABEL_RANK.index(key) if key in LABEL_RANK else len(LABEL_RANK)


def best_status(statuses):
    """The strongest status among a slot's rows (None for an empty slot)."""
    statuses = list(statuses)
    return min(statuses, key=rank_of) if statuses else None
