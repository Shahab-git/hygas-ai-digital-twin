"""
Provenance worksheet checker -- READ-ONLY. Validates a filled worksheet (CSV or xlsx) and prints what the counts WOULD be; it changes nothing.

    python scripts/check_provenance_worksheet.py <file>            validation report + would-be counts (exit code 1 if there are errors or value conflicts)
    python scripts/check_provenance_worksheet.py <file> --write    ALSO writes the status overlay JSON (default data/registry_status_overlay.json, or --out PATH)
                                                                   -- only if the worksheet is valid; NOT used in phase 1, and nothing reads the file in phase 1.

Counts are shown at row level and at the app's slot level (the same slot logic as equipment_datasheet.summarize(): a slot is Confirmed if any of its rows is; any other status shows
as the single 'Engineering Estimate' badge). 'today' is the current behaviour (a row without a status counts as Confirmed, equipment_datasheet.py:512).
"""
import importlib
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
if os.environ.get("HYGAS_ALLOW_DB_WRITES") == "1":
    sys.exit("Refusing to run: HYGAS_ALLOW_DB_WRITES=1 is set. This script never writes to a database; unset it.")

po = importlib.import_module("python.provenance_overlay")


def _table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    return out + ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]


def report(path):
    """(text, ok, overlay). Reads the worksheet; touches nothing."""
    rows = po.load_worksheet(path)
    universe = po.row_universe()
    rep = po.validate(rows, universe)
    overlay = po.to_overlay(rep["valid_rows"])
    eff = po.effect(overlay)
    L = [f"# Provenance worksheet check: {os.path.basename(str(path))}", "", f"rows read: {rep['n_rows']}; registry / fill rows: {len(universe)}; errors: {len(rep['errors'])}; value conflicts: {len(rep['conflicts'])}; "
         f"gaps (no usable origin): {len(rep['gaps'])}; overlay entries: {len(overlay)}", ""]
    if rep["errors"]:
        L += ["## Errors (these rows are NOT in the overlay)", ""] + _table(["line", "row_id", "kind", "message"], [[e["line"], e["row_id"], e["kind"], e["message"]] for e in rep["errors"]]) + [""]
    if rep["conflicts"]:
        L += ["## Value conflicts (reported, not applied; the row is NOT in the overlay)", ""] + _table(["line", "row_id", "worksheet", "registry"], [[c["line"], c["row_id"], c["worksheet_value"], c["registry_value"]] for c in rep["conflicts"]]) + [""]
    L += ["## Rows per origin", ""] + _table(["origin", "rows"], list(rep["counts_by_origin"].items())) + [""]
    L += ["## Rows per section and origin", ""] + _table(["section"] + list(po.ORIGINS), [[s] + [rep["counts_by_section"][s][o] for o in po.ORIGINS] for s in po.SECTIONS]) + [""]
    keys = list(eff["today"]["rows"])
    L += ["## Would-be counts, row level (rows with a value)", ""] + _table(["status", "today", "would be"], [[k, eff["today"]["rows"][k], eff["would_be"]["rows"][k]] for k in keys]) + [""]
    skeys = list(eff["today"]["slots"])
    L += ["## Would-be counts, the app's slot level (equipment_datasheet.summarize)", ""] + _table(["slots", "today", "would be"], [[k, eff["today"]["slots"][k], eff["would_be"]["slots"][k]] for k in skeys]) + [""]
    L += ["Nothing is applied: this is a report. The overlay is not read by any module in phase 1."]
    return "\n".join(L) + "\n", rep["valid"], overlay


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0].startswith("--"):
        sys.exit(__doc__)
    path = argv[0]
    text, ok, overlay = report(path)
    print(text)
    if "--write" in argv:
        if not ok:
            print("NOT written: the worksheet has errors or value conflicts.")
            return 1
        out = argv[argv.index("--out") + 1] if "--out" in argv else po.DEFAULT_OVERLAY_PATH
        po.write_overlay(overlay, out)
        print(f"overlay written to {out} ({len(overlay)} entries)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
