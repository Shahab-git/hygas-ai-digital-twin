"""
Provenance worksheet validator and status-overlay loader (phase 1: NOTHING IS APPLIED, NOTHING IS WIRED).

The registry-status audit (docs/registry_status_audit.md) found that 766 registry rows count as Confirmed only because equipment_datasheet.py:512 defaults a missing status to
Confirmed. The owner states the origin of each row in a worksheet (scripts/make_provenance_worksheet.py); this module reads the filled worksheet, validates it, and prepares the
status overlay a later phase would apply. It changes no registry row, status, default, engine file or UI, and no engine, app or datasheet module imports it (a test scans for it).

ORIGIN -> status the later phase would apply (documented here, not applied):
  DOK-ING        + non-empty `source` (document, date, page/line or e-mail date)   -> Confirmed        (without a source: rejected, "Confirmed needs a citable DOK-ING source")
  SIMILAR_PLANT  + non-empty `source` (paper / plant / URL / literature reference)  -> Estimated       (literature-informed; never Confirmed; without a source: rejected)
  ASSUMED        + non-empty `note` (the reason)                                    -> Assumed         (source optional)
  CALCULATED     + non-empty `source` (the formula or script reference)             -> Calculated
  UNKNOWN / blank                                                                   -> stays "Unverified (registry)" and is listed as a gap
Anything else in `origin` is rejected. A blank origin is never read as DOK-ING.

A worksheet value that differs from the registry value is reported as a CONFLICT and that row is not put in the overlay (the worksheet never edits a value).

xlsx files need openpyxl, which is NOT in requirements.txt (CI installs only that file plus pytest): it is imported lazily and a missing install raises a clear error; CSV always works.
Python 3.11-compatible.
"""
import copy
import csv
import datetime
import hashlib
import json
import os

from . import equipment_datasheet as eds
from . import equipment_engineering_estimates as eee
from . import equipment_registry
from . import equipment_rfi_fills as erf
from . import plant_status as ps
from . import registry_status as rs

ORIGIN_DOKING, ORIGIN_SIMILAR, ORIGIN_ASSUMED, ORIGIN_CALCULATED, ORIGIN_UNKNOWN = (rs.ORIGIN_DOKING, rs.ORIGIN_SIMILAR, rs.ORIGIN_ASSUMED, rs.ORIGIN_CALCULATED, rs.ORIGIN_UNKNOWN)
ORIGINS = rs.ORIGINS
ORIGIN_TO_STATUS = rs.ORIGIN_TO_STATUS
UNVERIFIED = rs.STATUS_UNVERIFIED
REQUIRED_FIELD = rs.REQUIRED_FIELD
SECTIONS = ("FE", "GA", "GC", "SA", "HB", "EU", "AI")
DEFAULT_OVERLAY_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "registry_status_overlay.json")

SOURCE_REGISTRY, SOURCE_RFI, SOURCE_ESTIMATE = rs.SOURCE_REGISTRY, rs.SOURCE_RFI, rs.SOURCE_ESTIMATE
row_id = rs.row_id


# --- the universe (every row the datasheet view can show) -------------------------------------------------------------------------------------

def row_universe():
    rows = []
    for item in equipment_registry.load_registry():
        for p in item["parameters"]:
            rows.append({"row_id": row_id(SOURCE_REGISTRY, item["id"], p["parameter"]), "source_kind": SOURCE_REGISTRY, "item_id": item["id"], "parameter": p["parameter"],
                         "value": p.get("value"), "unit": p.get("unit"), "remark": p.get("remarks") or "", "explicit_status": p.get("status")})
    for kind, table in ((SOURCE_RFI, erf.RFI_FILLS), (SOURCE_ESTIMATE, eee.ESTIMATE_FILLS)):
        for item_id, cats in table.items():
            for prows in cats.values():
                for p in prows:
                    rows.append({"row_id": row_id(kind, item_id, p["parameter"]), "source_kind": kind, "item_id": item_id, "parameter": p["parameter"], "value": p.get("value"),
                                 "unit": p.get("unit"), "remark": p.get("remarks") or "", "explicit_status": p.get("status")})
    for r in rows:
        r["section"] = r["item_id"][:2]
    ids = [r["row_id"] for r in rows]
    if len(set(ids)) != len(ids):
        raise ValueError("row ids are not unique in the registry / fill tables")
    return rows


# --- reading a filled worksheet -----------------------------------------------------------------------------------------------------------------

def _clean(v):
    return "" if v is None else str(v).strip()


def _require_openpyxl():
    try:
        import openpyxl
    except ImportError as e:                                           # pragma: no cover - environment dependent
        raise RuntimeError("reading an .xlsx worksheet needs openpyxl, which is not in requirements.txt; save the sheet as CSV or install openpyxl locally") from e
    return openpyxl


def load_worksheet(path, sheet="Provenance"):
    """Rows of a filled worksheet as dicts (all columns as text). CSV (utf-8, with or without BOM) or xlsx (sheet `Provenance`)."""
    if str(path).lower().endswith((".xlsx", ".xlsm")):
        openpyxl = _require_openpyxl()
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb[sheet]
        it = ws.iter_rows(values_only=True)
        header = [_clean(h) for h in next(it)]
        out = [{h: _clean(v) for h, v in zip(header, row)} for row in it if any(c not in (None, "") for c in row)]
        wb.close()
        return out
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [{k.strip(): _clean(v) for k, v in rec.items() if k is not None} for rec in csv.DictReader(f)]


def _same_value(a, b):
    a, b = _clean(a), _clean(b)
    if a == b:
        return True
    try:
        return float(a) == float(b)
    except ValueError:
        return False


# --- validation ---------------------------------------------------------------------------------------------------------------------------------

def validate(rows, universe=None):
    """Enforces the origin rules. Returns {"errors", "conflicts", "gaps", "counts_by_origin", "counts_by_section", "n_rows", "valid_rows", "valid"}.
    A row with an error or a value conflict is not `valid_rows` and never reaches the overlay. Nothing is changed."""
    universe = universe if universe is not None else row_universe()
    known = {r["row_id"]: r for r in universe}
    errors, conflicts, valid_rows = [], [], []
    seen = set()
    for i, r in enumerate(rows, start=1):
        rid = _clean(r.get("row_id"))
        origin = _clean(r.get("origin")).upper()
        source, note = _clean(r.get("source")), _clean(r.get("note"))
        problems = []
        if not rid:
            problems.append(("missing_row_id", "the row has no row_id"))
        elif rid in seen:
            problems.append(("duplicate_row_id", f"row_id {rid!r} appears more than once"))
        elif rid not in known:
            problems.append(("unknown_row_id", f"row_id {rid!r} is not in the registry or the fill tables"))
        if rid:
            seen.add(rid)
        if origin and origin not in ORIGINS:
            problems.append(("bad_origin", f"origin {r.get('origin')!r} is not one of {ORIGINS}"))
        elif origin in REQUIRED_FIELD:
            field, message = REQUIRED_FIELD[origin]
            if not (source if field == "source" else note):
                problems.append(("missing_" + field, message))
        for kind, message in problems:
            errors.append({"line": i, "row_id": rid, "kind": kind, "message": message})
        if rid in known and "value" in r and not _same_value(r.get("value"), known[rid]["value"]):
            conflicts.append({"line": i, "row_id": rid, "worksheet_value": _clean(r.get("value")), "registry_value": _clean(known[rid]["value"]),
                              "message": "the worksheet value differs from the registry value: reported, NOT applied"})
        elif not problems:
            valid_rows.append({"row_id": rid, "origin": origin, "source": source, "note": note})
    conflict_ids = {c["row_id"] for c in conflicts}
    valid_rows = [v for v in valid_rows if v["row_id"] not in conflict_ids]
    in_sheet = {_clean(r.get("row_id")) for r in rows}
    usable = {v["row_id"] for v in valid_rows if v["origin"] in ORIGIN_TO_STATUS}
    gaps = sorted(rid for rid, u in known.items() if rid not in usable and u["value"] is not None)       # a row with an error or a conflict is a gap too
    counts_by_origin = {o: 0 for o in ORIGINS}
    counts_by_origin["(blank)"] = 0
    counts_by_section = {s: {o: 0 for o in ORIGINS} for s in SECTIONS}
    for v in valid_rows:
        if v["origin"] == "":
            counts_by_origin["(blank)"] += 1
        else:
            counts_by_origin[v["origin"]] += 1
            counts_by_section[known[v["row_id"]]["section"]][v["origin"]] += 1
    counts_by_origin["(blank)"] += sum(1 for rid in known if rid not in in_sheet)
    return {"errors": errors, "conflicts": conflicts, "gaps": gaps, "counts_by_origin": counts_by_origin, "counts_by_section": counts_by_section,
            "n_rows": len(rows), "valid_rows": valid_rows, "valid": not errors and not conflicts}


def to_overlay(valid_rows):
    """{row_id: {status, origin, source, note}} for rows with a usable origin. UNKNOWN / blank rows are absent (they stay Unverified). Not applied anywhere."""
    out = {}
    for v in valid_rows:
        if v["origin"] in ORIGIN_TO_STATUS:
            out[v["row_id"]] = {"status": ORIGIN_TO_STATUS[v["origin"]], "origin": v["origin"], "source": v["source"], "note": v["note"]}
    return out


OVERLAY_FORMAT = 1


def sha256_lf(path):
    """SHA-256 of a text file with CRLF read as LF, so the value is the same on Windows (autocrlf working tree) and on a Linux checkout of the same commit."""
    with open(path, "rb") as f:
        return hashlib.sha256(f.read().replace(b"\r\n", b"\n")).hexdigest()


def overlay_header(source_path, entries, generated_at=None):
    """The header kept in data/registry_status_overlay.json: when it was generated, from which file, and that file's SHA-256."""
    digest = sha256_lf(source_path)
    stamp = generated_at or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"format": OVERLAY_FORMAT, "generated_at": stamp, "source_file": os.path.basename(str(source_path)), "source_sha256": digest, "sha256_basis": "file content with LF line endings", "n_entries": len(entries),
            "meaning": "row_id -> resolved status; DOK-ING->Confirmed (source cited), SIMILAR_PLANT->Estimated (literature-informed), ASSUMED->Assumed, CALCULATED->Calculated; "
                       "rows absent here are 'Unverified (registry)'"}


def write_overlay(overlay, path=DEFAULT_OVERLAY_PATH, header=None):
    """Writes the overlay JSON ({"header": ..., "entries": {row_id: {...}}}). Called only by `check_provenance_worksheet.py --write`."""
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"header": header or {"format": OVERLAY_FORMAT}, "entries": dict(sorted(overlay.items()))}, f, ensure_ascii=False, indent=1)
        f.write("\n")


# --- the would-be effect on the counts --------------------------------------------------------------------------------------------------------------

def _app_datasheets():
    """The datasheets exactly as the app builds them (registry + RFI fills + estimate fills), unresolved."""
    return eee.apply_estimates(erf.apply_rfi_fills(eds.build_all_datasheets()))


def _counts(resolved):
    rows = {"Confirmed": 0, "Estimated": 0, "Estimated (existing fills)": 0, "Assumed": 0, "Calculated": 0, UNVERIFIED: 0}
    for entry in resolved.values():
        for bucket in entry["datasheet"].values():
            for r in bucket:
                st = r["status"]
                key = "Estimated (existing fills)" if st == eds.STATUS_ESTIMATE else st
                rows[key] = rows.get(key, 0) + 1
    s = eds.summarize(resolved)
    return rows, {"Confirmed": s["confirmed_category_slots"], "Engineering Estimate (non-Confirmed)": s["estimated_category_slots"], "Missing": s["missing_category_slots"],
                  "total": s["total_category_slots"]}


def _legacy_default_counts():
    """The behaviour BEFORE provenance phase 2, kept only as a documented comparison: a row without a status key counted as Confirmed (equipment_datasheet.py:512 then)."""
    rows = {"Confirmed": 0, "Estimated": 0, "Estimated (existing fills)": 0, "Assumed": 0, "Calculated": 0, UNVERIFIED: 0}
    confirmed = estimate = missing = 0
    for entry in _app_datasheets().values():
        for bucket in entry["datasheet"].values():
            if not bucket:
                missing += 1
                continue
            states = [r.get("status", eds.STATUS_CONFIRMED) for r in bucket]
            for st in states:
                rows["Estimated (existing fills)" if st == eds.STATUS_ESTIMATE else st] += 1
            if eds.STATUS_CONFIRMED in states:
                confirmed += 1
            else:
                estimate += 1
    return rows, {"Confirmed": confirmed, "Engineering Estimate (non-Confirmed)": estimate, "Missing": missing, "total": confirmed + estimate + missing}


def effect(overlay):
    """What the counts are in three situations; nothing is applied by calling this.
    before_phase2_default: the old behaviour (a row without a status counted as Confirmed); today: the committed overlay (data/registry_status_overlay.json) resolved by
    registry_status; would_be: `overlay` resolved the same way. Row level (rows with a value) and the app's slot level (equipment_datasheet.summarize)."""
    out = {}
    out["before_phase2_default"] = dict(zip(("rows", "slots"), _legacy_default_counts()))
    out["today"] = dict(zip(("rows", "slots"), _counts(eds.resolve_datasheets(_app_datasheets()))))
    out["would_be"] = dict(zip(("rows", "slots"), _counts(eds.resolve_datasheets(_app_datasheets(), overlay))))
    return out
