"""P0-CLOSE C2 / C5: a status stated in a table of docs/*.md must be the status the ledger / the parameter table resolves for that tag.

docs/data_replacement_layer.md was written when every registry row without a status key counted as Confirmed; since Provenance Phase 2 none does, and its tables kept saying
Confirmed for rows the ledger gives Assumed / Estimated / Calculated / Unverified (registry). This file reads every markdown table of docs/*.md that has a tag column ("tag",
"parameter", "ledger_id") and a status column ("status", "status now"), looks each tag up in the parameter table and the ledger, and fails when the stated status is not one of the
statuses those two give for that tag (a tag can have two rows: the engine input and its registry counterpart). Prose is not parsed; a table with no such columns is not checked.
It also pins that the generated statuses of data_replacement_layer.md equal the live table exactly, so a status change in code or overlay is a visible failure until the document is regenerated.
Offline: no database, no network."""
import collections
import glob
import importlib
import os
import re

import pytest

pt = importlib.import_module("python.parameter_table")      # a test, not an engine / runtime / app file; same form as tests/test_apply_provenance.py (tests/test_data_layer.py scans for the plain import)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TAG_COLUMNS = ("tag", "parameter", "ledger_id")
STATUS_COLUMNS = ("status", "status now")
SEPARATOR = re.compile(r"^\|[\s:|-]+\|$")


def _cells(line):
    return [c.strip() for c in line.replace("\\|", "/").strip().strip("|").split("|")]


def table_rows(text):
    """[(line number, tag, status)] for every row of every table of `text` that has a tag column and a status column."""
    lines = text.splitlines()
    out, i = [], 0
    while i < len(lines) - 1:
        if lines[i].startswith("|") and SEPARATOR.match(lines[i + 1]):
            header = [h.lower() for h in _cells(lines[i])]
            tag_col = next((k for k, h in enumerate(header) if h in TAG_COLUMNS), None)
            status_col = next((k for k, h in enumerate(header) if h in STATUS_COLUMNS), None)
            j = i + 2
            while j < len(lines) and lines[j].startswith("|"):
                if tag_col is not None and status_col is not None:
                    c = _cells(lines[j])
                    if len(c) > max(tag_col, status_col):
                        out.append((j + 1, c[tag_col].strip("`*").replace("LEDGER.", ""), c[status_col].strip("`*")))
                j += 1
            i = j
        else:
            i += 1
    return out


def status_problems(text, known):
    """Rows whose tag is known and whose stated status is not one of the statuses `known` gives for it."""
    return [(n, tag, status, sorted(known[tag])) for n, tag, status in table_rows(text) if tag in known and status not in known[tag]]


@pytest.fixture(scope="module")
def table():
    return pt.build_table()


@pytest.fixture(scope="module")
def known(table):
    out = {}
    for r in table + pt.build_ledger():
        out.setdefault(r["tag"], set()).add(r["status"])
    return out


def _doc(name):
    return open(os.path.join(ROOT, "docs", name), encoding="utf-8").read()


def test_the_table_parser_reads_columns_by_name_and_ignores_other_tables():
    text = ("| tag | value | status |\n|---|---|---|\n| `A.x` | 1 | Assumed |\n| **B.y** | 2 | Confirmed |\n\n"
            "| item | remark |\n|---|---|\n| A.x | Confirmed |\n\n"
            "| ledger_id | status |\n|---|---|\n| LEDGER.C.z | Estimated |\n| D.w | a\\|b |\n")
    assert table_rows(text) == [(3, "A.x", "Assumed"), (4, "B.y", "Confirmed"), (12, "C.z", "Estimated"), (13, "D.w", "a/b")]


def test_a_stated_status_that_differs_from_the_resolved_one_is_reported():
    known = {"A.x": {"Assumed"}, "B.y": {"Estimated", "Assumed"}}
    ok = "| tag | status |\n|---|---|\n| A.x | Assumed |\n| B.y | Estimated |\n| B.y | Assumed |\n| unknown.tag | Confirmed |\n"
    assert status_problems(ok, known) == []
    bad = ok.replace("| A.x | Assumed |", "| A.x | Confirmed |")
    assert status_problems(bad, known) == [(3, "A.x", "Confirmed", ["Assumed"])]


def test_every_status_in_every_docs_table_is_the_ledger_or_table_status(known):
    checked, problems = collections.Counter(), {}
    for path in sorted(glob.glob(os.path.join(ROOT, "docs", "*.md"))):
        name = os.path.basename(path)
        text = open(path, encoding="utf-8").read()
        checked[name] = sum(1 for _, tag, _ in table_rows(text) if tag in known)
        p = status_problems(text, known)
        if p:
            problems[name] = p
    assert problems == {}, problems
    assert checked["data_replacement_layer.md"] >= 40 and checked["design_basis_ledger.md"] == 173, "not vacuous: the two documents that state statuses per tag are read"


def test_the_generated_tables_of_data_replacement_layer_equal_the_live_table(table):
    text = _doc("data_replacement_layer.md")
    a, b = text.index("## 2. Parameter table"), text.index("## 3. Precedence rule")
    in_doc = collections.Counter((tag, status) for _, tag, status in table_rows(text[a:b]))
    live = collections.Counter((r["tag"], r["status"]) for r in table)
    assert in_doc == live, (sorted((in_doc - live).items()), sorted((live - in_doc).items()))


def test_the_document_no_longer_says_registry_rows_are_confirmed_by_default():
    text = _doc("data_replacement_layer.md")
    for stale in ("Registry rows without a status key count as Confirmed", "counted Confirmed by default", "default for every row without a status key"):
        assert stale not in text, stale
    assert "no default to Confirmed any more" in text
