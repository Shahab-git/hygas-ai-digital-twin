"""
Provenance worksheet generator -- READ-ONLY and OFFLINE. It changes no registry row, status, default or UI; it only writes a worksheet for the OWNER to fill in.

    python scripts/make_provenance_worksheet.py            (about 3 seconds; writes outputs/provenance/provenance_worksheet.csv and .xlsx; outputs/ is git-ignored)
    python scripts/make_provenance_worksheet.py --doc      (also regenerates docs/provenance_worksheet.md)

One row per registry / fill row (815). The owner columns `origin`, `source`, `note` are prefilled ONLY where the registry-status audit proved something: E1 rows get origin DOK-ING and
the quoted DOK-ING file:line as source. E2 / E3 rows show the row's own remark so the owner decides in one glance; E4 rows (no evidence found) are blank. Nothing is guessed.
The .xlsx needs openpyxl, which is NOT in requirements.txt: without it only the CSV is written (and a line says so).
"""
import csv
import glob
import importlib
import importlib.util
import io
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
if os.environ.get("HYGAS_ALLOW_DB_WRITES") == "1":
    sys.exit("Refusing to run: HYGAS_ALLOW_DB_WRITES=1 is set. This script never writes to a database; unset it.")

po = importlib.import_module("python.provenance_overlay")

OUT_DIR = os.path.join(ROOT, "outputs", "provenance")
DOC_PATH = os.path.join(ROOT, "docs", "provenance_worksheet.md")
COLUMNS = ["row_id", "priority", "section", "item", "field", "value", "unit", "audit_class", "audit_evidence", "proposed_status_from_audit", "origin", "source", "note"]
OWNER_COLUMNS = ("origin", "source", "note")
NAMED_UNITS = ("GA-001", "GA-003", "GA-004", "GA-005", "GA-006", "GA-007", "GA-008", "GA-009", "GA-010", "HB-007", "HB-008", "HB-009", "HB-012")
SA_EXPECTED = ("SA-001", "SA-002", "SA-003", "SA-004", "SA-005")
# modules that only carry registry text (not engine models) are not evidence that the ENGINE refers to a row
NOT_ENGINE = {"equipment_datasheet", "equipment_rfi_fills", "equipment_engineering_estimates", "parameter_table", "equipment_registry", "equipment_data_requests",
              "equipment_request_routing", "design_basis", "provenance_overlay", "data_precedence", "measurement_replay"}


def _load_audit():
    spec = importlib.util.spec_from_file_location("run_registry_status_audit", os.path.join(ROOT, "scripts", "run_registry_status_audit.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def engine_referenced(audit_rows):
    """Registry rows whose exact field name (14+ characters, carried by at most 3 registry items) appears in an engine / model module under python/. A documented heuristic: it finds
    rows the code NAMES (constants and comments that cite them), not rows whose value the engine reads from the registry (it reads none)."""
    reg = [r for r in audit_rows if r["source"] == "registry"]
    carried = {}
    for r in reg:
        carried[r["parameter"]] = carried.get(r["parameter"], 0) + 1
    texts = [io.open(f, encoding="utf-8").read() for f in glob.glob(os.path.join(ROOT, "python", "*.py")) if os.path.basename(f)[:-3] not in NOT_ENGINE]
    return {("registry", r["item_id"], r["parameter"]) for r in reg if len(r["parameter"]) >= 14 and carried[r["parameter"]] <= 3 and any(r["parameter"] in t for t in texts)}


def build_worksheet_rows():
    audit = _load_audit()
    arows = audit.build_rows()
    universe = {u["row_id"]: u for u in po.row_universe()}
    table_rows = set(audit.TABLE_TO_AUDIT.values())
    eng = engine_referenced(arows)
    out = []
    for n, r in enumerate(arows):
        rid = po.row_id(r["source"], r["item_id"], r["parameter"])
        assert rid in universe, rid
        cls = r["class"]
        key = (r["source"], r["item_id"], r["parameter"])
        top = (key in table_rows or key in eng or (r["item_id"] in NAMED_UNITS and cls in ("E2", "E3")) or
               (r["item_id"] in SA_EXPECTED and r["parameter"].startswith("Expected")))
        priority = 1 if top else (2 if cls in ("E2", "E3") else 3)
        evidence = ""
        if cls == "E1":
            evidence = f"{r['evidence_file_line']}: \"{r['evidence_quote']}\" ({r['match']}; {r['subreason']})"
        elif cls in ("E2", "E3"):
            evidence = r["remark"]
        elif r["explicit_status"]:
            evidence = f"existing explicit status: {r['explicit_status']}"
        proposed = "Confirmed" if cls == "E1" else (r["proposed_status"] if cls == "E3" else "")
        row = {"row_id": rid, "priority": priority, "section": r["item_id"][:2], "item": r["item_id"], "field": r["parameter"], "value": "" if r["value"] is None else r["value"],
               "unit": r["unit"] or "", "audit_class": cls, "audit_evidence": evidence, "proposed_status_from_audit": proposed, "origin": "", "source": "", "note": "", "_n": n,
               "_top": top}
        if cls == "E1":
            row["origin"] = po.ORIGIN_DOKING
            row["source"] = f"DOK-ING RFI response, {r['evidence_file_line']}"
            row["note"] = "exact unit conversion of a stated figure" if r["match"] == "unit conversion" else ""
        out.append(row)
    sec = {s: i for i, s in enumerate(po.SECTIONS)}
    out.sort(key=lambda x: (x["priority"], sec[x["section"]], x["item"], x["_n"]))
    return out


def _csv_cell(v):
    s = "" if v is None else str(v)
    return " " + s if s[:1] in ("=", "+", "@") else s                  # Excel would read a leading = + @ in a CSV as a formula; the loader strips whitespace


def write_csv(rows, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        for r in rows:
            w.writerow([_csv_cell(r[c]) for c in COLUMNS])


HOW_TO = [
    "HOW TO FILL THIS (the file changes nothing by itself; phase 2 applies your answers after the checker accepts them)",
    "",
    "One row per registry / fill row, most important first (column `priority`: 1 = the rows the engine, the parameter table or the audit's E2/E3 list name, 2 = other E2/E3, 3 = the rest).",
    "Fill ONLY the three yellow columns: origin, source, note. Do not edit any other column (a changed `value` is reported as a conflict and ignored).",
    "",
    "origin (pick from the drop-down):",
    "  DOK-ING        a DOK-ING document or message states this value  -> would become Confirmed.  `source` REQUIRED: document name, date, page/line or e-mail date.",
    "  SIMILAR_PLANT  taken from a similar MSW / gasification plant or the literature  -> would become Estimated (literature-informed), never Confirmed.  `source` REQUIRED: paper, plant, URL.",
    "  ASSUMED        a design assumption of this project  -> would become Assumed.  `note` REQUIRED: the reason.  `source` optional.",
    "  CALCULATED     derived from other values  -> would become Calculated.  `source` REQUIRED: the formula or script reference.",
    "  UNKNOWN        you do not know  (or leave blank): the row stays 'Unverified (registry)' and is listed as a gap.",
    "",
    "Rows prefilled by the audit: the audit_class E1 rows (a DOK-ING line in data/dokink_rfi_answers.md states the value) have origin DOK-ING and that file:line as source. Check them, change them if you know better.",
    "E2 / E3 rows show the row's own remark in `audit_evidence`; the origin is left blank on purpose. E4 rows (no evidence found in the repo) are blank.",
    "",
    "When done, save as CSV or xlsx and run:  python scripts/check_provenance_worksheet.py <file>  (read-only: validation report and the would-be counts).",
]


def write_xlsx(rows, path):
    try:
        import openpyxl
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
        from openpyxl.worksheet.datavalidation import DataValidation
    except ImportError:
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Provenance"
    yellow, bold = PatternFill("solid", fgColor="FFF2CC"), Font(bold=True)

    def put(sheet, r, c, v):
        cell = sheet.cell(row=r, column=c, value=v)
        if isinstance(v, str):
            cell.data_type = "s"                                            # a remark starting with '=' must stay text
        return cell

    for c, name in enumerate(COLUMNS, start=1):
        cell = put(ws, 1, c, name)
        cell.font = bold
        if name in OWNER_COLUMNS:
            cell.fill = yellow
    for r_i, r in enumerate(rows, start=2):
        for c, name in enumerate(COLUMNS, start=1):
            v = r[name]
            cell = put(ws, r_i, c, str(v) if not isinstance(v, int) or name != "priority" else v)
            if name in OWNER_COLUMNS:
                cell.fill = yellow
            if name in ("audit_evidence", "field", "source", "note"):
                cell.alignment = Alignment(wrap_text=True, vertical="top")
    widths = {"row_id": 38, "priority": 8, "section": 8, "item": 9, "field": 34, "value": 16, "unit": 10, "audit_class": 10, "audit_evidence": 70, "proposed_status_from_audit": 14,
              "origin": 16, "source": 44, "note": 36}
    for c, name in enumerate(COLUMNS, start=1):
        ws.column_dimensions[get_column_letter(c)].width = widths[name]
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(COLUMNS))}{len(rows) + 1}"
    dv = DataValidation(type="list", formula1='"' + ",".join(po.ORIGINS) + '"', allow_blank=True, showErrorMessage=True,
                        errorTitle="origin", error="Pick one of: " + ", ".join(po.ORIGINS))
    ws.add_data_validation(dv)
    o = COLUMNS.index("origin") + 1
    dv.add(f"{get_column_letter(o)}2:{get_column_letter(o)}{len(rows) + 1}")
    how = wb.create_sheet("How to fill this")
    for i, line in enumerate(HOW_TO, start=1):
        put(how, i, 1, line)
    how.column_dimensions["A"].width = 160
    how["A1"].font = bold
    top = wb.create_sheet("Top rows")
    put(top, 1, 1, "Fill these first (priority 1); the same rows are at the top of the Provenance sheet").font = bold
    for i, name in enumerate(("row_id", "field", "value", "unit", "audit_class", "audit_evidence"), start=1):
        put(top, 2, i, name).font = bold
    for r_i, r in enumerate([x for x in rows if x["priority"] == 1], start=3):
        for c, name in enumerate(("row_id", "field", "value", "unit", "audit_class", "audit_evidence"), start=1):
            put(top, r_i, c, str(r[name]))
    for c, w in enumerate((38, 34, 16, 10, 10, 90), start=1):
        top.column_dimensions[get_column_letter(c)].width = w
    wb.save(path)
    return True


def render_doc(rows):
    top = [r for r in rows if r["priority"] == 1]
    n = {k: sum(1 for r in rows if r["audit_class"] == k) for k in ("E1", "E2", "E3", "E4")}
    L = ["# Provenance worksheet (phase 1 of 2: nothing is applied)", "",
         "Source: `docs/registry_status_audit.md` found that 766 registry rows count as Confirmed only because `python/equipment_datasheet.py:512` defaults a missing status to Confirmed, and only 16 have a DOK-ING line in the repo. "
         "The owner has said where the values came from (most from similar MSW / gasification plants, some from DOK-ING, some assumed); **Claude does not guess which row is which.** This phase builds the instrument the owner uses to state the origin of each row, "
         "validates the answers, and prepares the overlay a later phase would apply. **No status, default, registry row or UI is changed.** Phase 2, after the worksheet is filled, applies the answers (a separate task).", "",
         "Files: `scripts/make_provenance_worksheet.py` (generator), `python/provenance_overlay.py` (vocabulary, validator, overlay, effect), `scripts/check_provenance_worksheet.py` (read-only checker), `tests/test_provenance_overlay.py`.", "",
         "## Origin vocabulary and the status a later phase would apply", "",
         "| origin | required | would become | notes |", "|---|---|---|---|",
         "| `DOK-ING` | `source`: document name, date, page/line or e-mail date | Confirmed | without a source: rejected (\"Confirmed needs a citable DOK-ING source\") |",
         "| `SIMILAR_PLANT` | `source`: paper, plant, URL (may be the project's literature reference) | Estimated (literature-informed) | never Confirmed; without a source: rejected |",
         "| `ASSUMED` | `note`: the reason | Assumed | `source` optional |",
         "| `CALCULATED` | `source`: the formula or script reference | Calculated | |",
         "| `UNKNOWN` / blank | nothing | stays \"Unverified (registry)\" | listed as a gap; a blank is never read as DOK-ING |", "",
         "Any other `origin` is rejected. Duplicate `row_id`s and `row_id`s not in the registry are rejected. A `value` that differs from the registry value is reported as a conflict and ignored (the worksheet never edits a value).", "",
         "## How to use it", "",
         "1. `python scripts/make_provenance_worksheet.py` writes `outputs/provenance/provenance_worksheet.csv` and `.xlsx` (the xlsx needs `openpyxl`, which is installed locally but is **not in `requirements.txt`**; the CSV always works).",
         f"2. Fill the yellow columns `origin`, `source`, `note` (a drop-down is in the xlsx). Rows are sorted most important first (`priority` 1 = {sum(1 for r in rows if r['priority'] == 1)} rows, 2 = {sum(1 for r in rows if r['priority'] == 2)}, 3 = {sum(1 for r in rows if r['priority'] == 3)}). **Prefilled:** the {n['E1']} E1 rows (origin `DOK-ING`, source = the quoted `data/dokink_rfi_answers.md` line). E2 / E3 rows show their own remark and are left for you; the {n['E4']} E4 rows are blank.",
         "3. `python scripts/check_provenance_worksheet.py <filled file>` prints the validation report and what the counts would be (row level and the app's slot level). It changes nothing.", "",
         f"## Fill these first ({len(top)} rows)", "",
         "Priority 1 = rows the parameter table uses, rows whose exact field name the engine / model code cites (a heuristic: the code names them, it does not read them from the registry), the audit's E2/E3 rows in GA-001, GA-003, GA-004, GA-005 to GA-010, HB-007, HB-008, HB-009, HB-012, and the SA-001 to SA-005 Expected compositions.", ""]
    L += ["| # | item | field | value | audit | what the row's own remark / the audit says |", "|---|---|---|---|---|---|"]
    for i, r in enumerate(top, start=1):
        L.append("| " + " | ".join(str(c).replace("|", "/").replace("\n", " ") for c in (i, r["item"], r["field"], f"{r['value']} {r['unit']}".strip(), r["audit_class"] or "-", r["audit_evidence"] or "")) + " |")
    L += ["", "## What phase 1 does not do", "",
          "No status is applied, the default (`equipment_datasheet.py:512`) is unchanged, the registry JSON is unchanged, the app and the what-if tab are unchanged, nothing imports `python/provenance_overlay.py`, and `data/registry_status_overlay.json` is not written (that needs `check_provenance_worksheet.py --write`, not used in this task).", ""]
    return "\n".join(L) + "\n"


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    rows = build_worksheet_rows()
    write_csv(rows, os.path.join(OUT_DIR, "provenance_worksheet.csv"))
    has_xlsx = write_xlsx(rows, os.path.join(OUT_DIR, "provenance_worksheet.xlsx"))
    if "--doc" in argv:
        with open(DOC_PATH, "w", encoding="utf-8", newline="\n") as f:
            f.write(render_doc(rows))
    prefilled = sum(1 for r in rows if r["origin"])
    print(f"rows: {len(rows)}; priority 1/2/3: {sum(r['priority'] == 1 for r in rows)}/{sum(r['priority'] == 2 for r in rows)}/{sum(r['priority'] == 3 for r in rows)}; "
          f"audit classes E1/E2/E3/E4: {sum(r['audit_class'] == 'E1' for r in rows)}/{sum(r['audit_class'] == 'E2' for r in rows)}/{sum(r['audit_class'] == 'E3' for r in rows)}/{sum(r['audit_class'] == 'E4' for r in rows)}; "
          f"owner cells prefilled: {prefilled} rows (all E1); blank origin: {len(rows) - prefilled}")
    print("csv written; xlsx " + ("written" if has_xlsx else "NOT written (openpyxl is not installed)"))


if __name__ == "__main__":
    main()
