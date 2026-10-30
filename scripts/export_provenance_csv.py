"""
Export the owner's filled provenance worksheet (xlsx) to the committed CSV that is the source of truth at runtime.

    python scripts/export_provenance_csv.py [XLSX] [CSV]
        defaults: outputs/provenance/provenance_worksheet_filled.xlsx -> data/provenance/provenance_worksheet_filled.csv

Same columns as the generator, UTF-8 with a BOM (so Excel reads H2 / degC correctly), a text cell that starts with = + @ gets a leading space exactly as the generator does (the loader strips
whitespace). openpyxl is imported lazily (it is NOT in requirements.txt); the CSV needs nothing. After writing, the CSV is validated with the same validator as the xlsx and the two
must give identical reports (counts, errors, conflicts, gaps), otherwise the script exits 1 and the CSV is not to be committed. Read-only for everything else.
"""
import csv
import importlib
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
if os.environ.get("HYGAS_ALLOW_DB_WRITES") == "1":
    sys.exit("Refusing to run: HYGAS_ALLOW_DB_WRITES=1 is set. This script never writes to a database; unset it.")

po = importlib.import_module("python.provenance_overlay")
COLUMNS = ["row_id", "priority", "section", "item", "field", "value", "unit", "audit_class", "audit_evidence", "proposed_status_from_audit", "origin", "source", "note"]
DEFAULT_XLSX = os.path.join(ROOT, "outputs", "provenance", "provenance_worksheet_filled.xlsx")
DEFAULT_CSV = os.path.join(ROOT, "data", "provenance", "provenance_worksheet_filled.csv")


def _csv_cell(v):
    s = "" if v is None else str(v)
    return " " + s if s[:1] in ("=", "+", "@") else s


def export(xlsx_path, csv_path):
    rows = po.load_worksheet(xlsx_path)
    missing = [c for c in COLUMNS if rows and c not in rows[0]]
    if missing:
        raise SystemExit(f"the worksheet lacks column(s) {missing}")
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(COLUMNS)
        for r in rows:
            w.writerow([_csv_cell(r.get(c, "")) for c in COLUMNS])
    return rows


def _summary(rep):
    return {k: rep[k] for k in ("errors", "conflicts", "gaps", "counts_by_origin", "counts_by_section", "n_rows")} | {"valid_rows": rep["valid_rows"]}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    xlsx = argv[0] if argv else DEFAULT_XLSX
    out = argv[1] if len(argv) > 1 else DEFAULT_CSV
    rows = export(xlsx, out)
    universe = po.row_universe()
    a, b = po.validate(rows, universe), po.validate(po.load_worksheet(out), universe)
    same = _summary(a) == _summary(b) and [r["row_id"] for r in rows] == [r["row_id"] for r in po.load_worksheet(out)]
    print(f"read {len(rows)} rows from {os.path.basename(xlsx)}; wrote {out}")
    print(f"validation: errors {len(a['errors'])}, conflicts {len(a['conflicts'])}, origins {a['counts_by_origin']}")
    print("CSV round trip identical to the xlsx report:", same)
    return 0 if same and a["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
