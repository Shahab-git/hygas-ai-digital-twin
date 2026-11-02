"""The committed ledger export does not depend on line numbers (task A3c, section 1).

`build_ledger()` keeps `file_line` for interactive use; `docs/design_basis_ledger.md` and `.csv` carry `anchor` (module:symbol) instead and no code line numbers in their text. Proved on a
TEMPORARY COPY of the repository: unrelated lines added above every ledgered constant and function leave the export identical to the committed files; a changed value, status/origin,
consumer or anchor changes it. Each copy runs scripts/export_design_basis_ledger.py as a subprocess (offline: the in-memory fake store, no database, no network).
Nothing outside tmp_path is written."""
import os
import re
import shutil
import subprocess
import sys

import pytest

from python import ledger_anchors as la
from python import ledger_coverage as lc
from python import parameter_table as pt

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
COMMITTED = {n: open(os.path.join(ROOT, "docs", n), encoding="utf-8", newline="").read().replace("\r\n", "\n") for n in ("design_basis_ledger.md", "design_basis_ledger.csv")}


@pytest.fixture(scope="module")
def ledger():
    return pt.build_ledger()


# ---------------------------------------------------------------- anchors

def test_every_row_has_a_symbolic_anchor_and_no_two_rows_share_one(ledger):
    rep = la.anchor_report(ledger)
    assert rep["rows"] == len(ledger) == 173 and rep["shared"] == []
    for r in ledger:
        a = r["anchor"]
        assert re.match(r"^(registry:[A-Z]+-\d+/.+|[a-z_0-9]+:[A-Za-z_0-9#+:'\[\]\(\)\. /,-]+)$", a), (r["ledger_id"], a)
        assert not re.search(r":\d+$", a), (r["ledger_id"], "an anchor ends in a symbol or #n, never in a bare line number")


def test_the_ambiguous_and_fallback_anchors_are_exactly_these(ledger):
    rep = la.anchor_report(ledger)
    assert rep["ambiguous"] == ["balance_audit:efficiency_check:h2_kw_engine#1", "chp:chp_efficiency:x+eta#1+eta#2+eta#3+eta#4+eta#5+eta#6+eta#7", "hb_wgs_psa_storage_chain:hb012_compressor:T1_K#1"]
    assert rep["fallback"] == ["gc_gas_cleaning_chain:gc004_cooling_duty#1", "gc_gas_cleaning_chain:gc004_cooling_duty#2"]


def test_a_literal_is_named_by_what_it_is_assigned_to_and_numbered_only_as_a_fallback():
    src = ("def f(a, b=0.37):\n"
           "    x = 3.5\n"
           "    y = g(k=4.5)\n"
           "    z = {'rate': 5.5}\n"
           "    return h(6.5) + 7.5\n"
           "def g2():\n"
           "    t = 8.5\n"
           "    t = 9.5\n")
    occ = la.function_literals(src, "f")
    assert [n for n, _, _ in occ] == ["b", "x", "k", "rate", None, None]
    assert la.literal_anchor("python/m.py", src, "f", [0.37])[0] == "m:f:b"
    assert la.literal_anchor("python/m.py", src, "f", [3.5])[0] == "m:f:x"
    assert la.literal_anchor("python/m.py", src, "f", [4.5])[0] == "m:f:k"
    assert la.literal_anchor("python/m.py", src, "f", [5.5])[0] == "m:f:rate"
    a, flags = la.literal_anchor("python/m.py", src, "f", [6.5])
    assert a == "m:f#5" and flags == {"fallback"}, "no stable name: module:function#n, n counted within that function only"
    assert la.literal_anchor("python/m.py", src, "f", [7.5])[0] == "m:f#6"
    a, flags = la.literal_anchor("python/m.py", src, "g2", [9.5])
    assert a == "m:g2:t#2" and flags == {"ambiguous"}, "two literals named t: an ordinal"
    assert la.literal_anchor("python/m.py", src, "g2", [8.5])[0] == "m:g2:t#1"


def test_an_anchor_does_not_contain_the_position_of_the_line_it_is_on():
    src = "\n\n\n# unrelated\n" + "def f():\n    x = 3.5\n"
    assert la.literal_anchor("python/m.py", src, "f", [3.5])[0] == la.literal_anchor("python/m.py", "def f():\n    x = 3.5\n", "f", [3.5])[0]


def test_the_committed_export_carries_no_code_line_numbers_and_no_file_line_column():
    for name, text in COMMITTED.items():
        assert not re.search(r"\.(py|json):\d+", text), (name, re.findall(r".{30}\.(?:py|json):\d+", text)[:3])
    assert "file_line" not in COMMITTED["design_basis_ledger.csv"].split("\n")[0] and "anchor" in COMMITTED["design_basis_ledger.csv"].split("\n")[0]
    assert la.strip_code_lines("see python/psa.py:12 and data/x.json:3-4 and data/dokink_rfi_answers.md:15") == "see python/psa.py and data/x.json and data/dokink_rfi_answers.md:15"


# ---------------------------------------------------------------- the export on a temporary copy

COPY = ("python", "data", "docs", "scripts", "app.py", "tests/_fakes.py")             # the consumer search reads app.py and scripts/ too
UNRELATED = "# unrelated line added above (task A3c test)\n"


def _copy_repo(dst):
    for rel in COPY:
        src, to = os.path.join(ROOT, rel), os.path.join(dst, rel)
        if os.path.isdir(src):
            shutil.copytree(src, to, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            os.makedirs(os.path.dirname(to), exist_ok=True)
            shutil.copy(src, to)


def _export(dst):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    env.pop("HYGAS_ALLOW_DB_WRITES", None)
    r = subprocess.run([sys.executable, os.path.join("scripts", "export_design_basis_ledger.py")], cwd=dst, env=env, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout[-400:] + r.stderr[-1500:]
    return {n: open(os.path.join(dst, "docs", n), encoding="utf-8", newline="").read().replace("\r\n", "\n") for n in COMMITTED}


def _edit(dst, rel, fn):
    p = os.path.join(dst, rel)
    t = open(p, encoding="utf-8", newline="").read()
    nl = "\r\n" if "\r\n" in t else "\n"
    out = fn(t.replace("\r\n", "\n"))
    assert out != t.replace("\r\n", "\n"), f"the edit changed nothing in {rel}"
    open(p, "w", encoding="utf-8", newline="").write(out.replace("\n", nl))


def _shift_everything(dst):
    """Unrelated lines above every top-level function and every UPPER_CASE constant of every scanned module (and at the top of each file)."""
    for mod in lc.SCAN_MODULES + ("tab1_integration",):
        rel = lc.rel_path(mod)

        def shift(t):
            # not between a comment and the line it comments: the "Confirmed" class of a mention is decided by what stands in the next 3 lines (A3b 2.2), so a line inserted INSIDE such a
            # block is not an unrelated line
            lines, out = t.splitlines(), []
            for i, line in enumerate(lines):
                if re.match(r"(def |[A-Z][A-Z0-9_]* *=)", line) and not (i and lines[i - 1].lstrip().startswith("#")):
                    out.append(UNRELATED.strip())
                out.append(line)
            return UNRELATED * 3 + chr(10).join(out) + chr(10)
        _edit(dst, rel, shift)


def _same_after(dst):
    got = _export(dst)
    return {n: got[n] == COMMITTED[n] for n in COMMITTED}


def test_unrelated_lines_above_every_ledgered_constant_leave_the_export_identical(tmp_path):
    _copy_repo(str(tmp_path))
    _shift_everything(str(tmp_path))
    n_shifted = sum(open(os.path.join(tmp_path, lc.rel_path(m)), encoding="utf-8").read().count(UNRELATED) for m in lc.SCAN_MODULES)
    assert n_shifted > 300, "the copy really moved the lines"
    # build_ledger() still reports the moved lines (file_line is for interactive use) ...
    prog = "from python import parameter_table as pt; print(chr(10).join(r['tag'] + '|' + r['source'] + '|' + r['file_line'] for r in pt.build_ledger()))"
    moved = subprocess.run([sys.executable, "-c", prog], cwd=str(tmp_path), capture_output=True, text=True, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    assert moved.returncode == 0, moved.stderr[-800:]
    before = {r["tag"] + "|" + r["source"]: r["file_line"] for r in pt.build_ledger()}
    after = dict(line.rsplit("|", 1) for line in moved.stdout.strip().splitlines())
    assert sum(1 for k, v in after.items() if k in before and before[k] != v and not k.split("|", 1)[1].startswith("registry")) > 100
    # ... and the committed export is still exactly what is generated
    assert _same_after(str(tmp_path)) == {"design_basis_ledger.md": True, "design_basis_ledger.csv": True}


def _mut_value(dst):
    _edit(dst, "python/fe_feed_handling.py", lambda t: t.replace("FE001_LIVE_CAPACITY_T = 1.7\n", "FE001_LIVE_CAPACITY_T = 1.8\n", 1))


def _mut_status_origin(dst):
    import json
    p = os.path.join(dst, "data", "registry_status_overlay.json")
    d = json.load(open(p, encoding="utf-8"))
    del d["entries"]["registry|FE-003|Nominal feed rate"]
    json.dump(d, open(p, "w", encoding="utf-8"), indent=1)


def _mut_consumer(dst):
    _edit(dst, "python/fe_feed_handling.py", lambda t: t.rstrip("\n") + "\n\n\ndef _extra_reader_for_the_test():\n    return FE001_LIVE_CAPACITY_T\n")


def _mut_anchor(dst):
    _edit(dst, "python/gc_gas_cleaning_chain.py", lambda t: t.replace("    efficiency = 0.95\n    outlet_mg_nm3 = inlet_mg_nm3 * (1.0 - efficiency)\n", "    collection_eff = 0.95\n    outlet_mg_nm3 = inlet_mg_nm3 * (1.0 - collection_eff)\n", 1)
                                                         .replace('"efficiency": efficiency, "outlet_mg_nm3"', '"efficiency": collection_eff, "outlet_mg_nm3"', 1))


@pytest.mark.parametrize("mutate,what", [(_mut_value, "value"), (_mut_status_origin, "status and origin"), (_mut_consumer, "consumer"), (_mut_anchor, "anchor")])
def test_a_changed_value_status_origin_consumer_or_anchor_changes_the_export(tmp_path, mutate, what):
    _copy_repo(str(tmp_path))
    mutate(str(tmp_path))
    same = _same_after(str(tmp_path))
    assert same != {"design_basis_ledger.md": True, "design_basis_ledger.csv": True}, f"a changed {what} must make the export differ from the committed files"
