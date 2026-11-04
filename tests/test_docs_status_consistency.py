"""P0-CLOSE C2 / C5: a status stated in a table of docs/*.md must be the status the ledger / the parameter table resolves for that tag.

docs/data_replacement_layer.md was written when every registry row without a status key counted as Confirmed; since Provenance Phase 2 none does, and its tables kept saying
Confirmed for rows the ledger gives Assumed / Estimated / Calculated / Unverified (registry). This file reads every markdown table of docs/*.md that has a tag column ("tag",
"parameter", "ledger_id") and a status column ("status", "status now"), looks each tag up in the parameter table and the ledger, and fails when the stated status is not one of the
statuses those two give for that tag (a tag can have two rows: the engine input and its registry counterpart). Prose is not parsed; a table with no such columns is not checked.
It also pins that the generated statuses of data_replacement_layer.md equal the live table exactly, so a status change in code or overlay is a visible failure until the document is regenerated.

P0-CLOSE C5, second part: the same idea for the docstrings and comments of the 18 CONFIRMED_SCOPE modules, built on the existing guard (python/ledger_coverage.confirmed_mentions and its REGISTRY-STATED
class, pinned in tests/test_design_basis_ledger.py::CONFIRMED_PIN) instead of a second scanner. A REGISTRY-STATED mention (a registry value called Confirmed with no DOK-ING source next to it) whose
line names item tags (GA-001, GC-005, HB-012, ...) is a LEDGER CONTRADICTION when none of the named items has a Confirmed value anywhere: no registry row resolved to Confirmed by
registry_status.resolve_row and no ledger row with Confirmed. The contradictions that exist today are PINNED per file (LEDGER_CONTRADICTION_PIN, the accepted limitation recorded in the A3d report,
section 8): a new one, or one removed, fails here and must be made on purpose. It is deliberately coarse: the test works at item level (HB-012 has one Confirmed row, so "HB-012's own Confirmed motor
rating" is not counted although the motor rating is Unverified (registry)) and it cannot see a mention whose line names no item tag.
Offline: no database, no network."""
import collections
import glob
import importlib
import os
import re

import pytest

from python import equipment_registry, registry_status
from python import ledger_coverage as lc

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
    assert checked["data_replacement_layer.md"] >= 40 and checked["design_basis_ledger.md"] == 179, "not vacuous: the two documents that state statuses per tag are read"


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


# ------------------------------------------------------------------ P0-CLOSE C5: docstrings and comments of the engine modules against the ledger

ITEM_TAG = re.compile(r"\b([A-Z]{2}-\d{3})\b")
# {file: number of REGISTRY-STATED mentions whose named items have no Confirmed value anywhere}; 91 on 2026-11-04 (origin/main 5dfe3bc + P0-CLOSE C3). Accepted limitation: not reworded in this task.
LEDGER_CONTRADICTION_PIN = {
    "python/balance_audit.py": 1, "python/eu_utilities_chp.py": 11, "python/fe_feed_handling.py": 4, "python/ga001_gasifier_model.py": 7, "python/gc_gas_cleaning_chain.py": 35,
    "python/hb_remaining_chain.py": 18, "python/hb_wgs_psa_storage_chain.py": 13, "python/tab1_integration.py": 2,
}


@pytest.fixture(scope="module")
def known_rows(table):
    return table + pt.build_ledger()


@pytest.fixture(scope="module")
def item_status(known_rows):
    """{item id: set of statuses}: every registry row of the item as resolved by registry_status.resolve_row (the committed overlay), plus the ledger rows whose tag starts with the item id."""
    out = {}
    for item in equipment_registry.load_registry():
        for p in item["parameters"]:
            out.setdefault(item["id"], set()).add(registry_status.resolve_row(registry_status.SOURCE_REGISTRY, item["id"], p)["status"])
    for r in known_rows:
        m = re.match(r"([A-Z]{2}-\d{3})\.", r["tag"])
        if m:
            out.setdefault(m.group(1), set()).add(r["status"])
    return out


def ledger_contradictions(mentions, item_status):
    """The REGISTRY-STATED mentions whose line names at least one item tag and none of the named items has a Confirmed value (an item unknown to the registry and the ledger counts as having none)."""
    out = []
    for m in mentions:
        tags = ITEM_TAG.findall(m["text"])
        if m["class"] == lc.MENTION_REGISTRY and tags and all("Confirmed" not in item_status.get(t, set()) for t in tags):
            out.append(m)
    return out


def _counts(found):
    return dict(sorted(collections.Counter(m["file"] for m in found).items()))


def test_the_items_that_have_a_confirmed_value_are_exactly_these(item_status):
    assert sorted(k for k, v in item_status.items() if "Confirmed" in v) == ["FE-003", "FE-004", "HB-006", "HB-012", "HB-013", "HB-018"]      # the 6 registry rows resolved to Confirmed (+ the 2 ledger rows)


def test_the_ledger_contradictions_in_the_engine_comments_are_the_pinned_ones(item_status):
    found = ledger_contradictions(lc.confirmed_mentions(), item_status)
    assert _counts(found) == LEDGER_CONTRADICTION_PIN, _counts(found)
    assert len(found) == sum(LEDGER_CONTRADICTION_PIN.values()) == 91
    assert all(m["where"] in ("docstring", "comment", "string") for m in found)


def test_a_new_confirmed_mention_naming_an_unconfirmed_item_is_caught_and_one_naming_a_confirmed_item_is_not(item_status):
    pinned = _counts(ledger_contradictions(lc.confirmed_mentions(), item_status))
    file = "python/gc_gas_cleaning_chain.py"
    src = open(os.path.join(ROOT, file), encoding="utf-8").read()
    for added, delta in (("# GC-005's own Confirmed blowdown ratio\n", 1),                                  # GC-005 has no Confirmed value: a contradiction
                         ("# FE-003's own Confirmed nominal rate\n", 0),                                    # FE-003 has one: not a contradiction
                         ("# GC-005's own registry blowdown ratio (Unverified (registry))\n", 0)):          # no "confirmed" in the line at all
        got = _counts(ledger_contradictions(lc.confirmed_mentions(sources={file: src + "\n" + added}), item_status))
        assert got[file] == pinned[file] + delta, (added, got)
    sourced = lc.confirmed_mentions(sources={file: src + "\n# GC-005's own Confirmed blowdown ratio (DOK-ING RFI #1 answer)\n"})
    assert _counts(ledger_contradictions(sourced, item_status)) == pinned, "a mention that names its DOK-ING source is not REGISTRY-STATED"
