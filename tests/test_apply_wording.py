"""Wording follow-up (UI text only): the slot label is 'Not DOK-ING-confirmed', no static sentence in the rendered app calls registry data 'Confirmed' without the DOK-ING-source
qualifier, the counts are the provenance phase 2 counts, the snapshot is unchanged, and the change to app.py is TEXT ONLY.

ORDER: the AppTest-based test must run before any bare-mode runpy of app.py in the same pytest process (an AppTest after a runpy fails with a Streamlit form-context error). Pytest runs
files alphabetically, so this file (like tests/test_apply_provenance.py) sorts before tests/test_ga_carbon_black_card.py, the first runpy user. This file has no runpy. Rename with care."""
import ast
import json
import os
import re
import subprocess
import urllib.error
from unittest import mock

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import _d2_wording
from _fakes import FakeSupabase, patched_supabase
from python import equipment_datasheet as eds
from python import equipment_engineering_estimates as eee
from python import equipment_rfi_fills as erf
from python import tab1_integration as t1

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP = os.path.join(ROOT, "app.py")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "sample_snapshot.json")
BLOCKED = urllib.error.URLError("network blocked in tests")

# "Confirmed" claims about registry data that survive on purpose: each is TRUE under the rule (Confirmed = a DOK-ING source is cited) ...
TRUE_AS_WRITTEN = (
    r"no real Confirmed target exists",                    # GA-001 outputs have no target at all (a statement of absence)
    r"SEPARATE Confirmed target efficiency exists",        # same, GC tab
    r"a Confirmed DESIGN TARGET",                          # HB-006 99.97 % purity: dokink_rfi_answers.md:33 (audit class E1)
    r"real Confirmed answer",                              # the Design Basis cards: each cites its line of data/dokink_rfi_answers.md (design_basis.py, its own status system)
)
# ... and these are text inside ENGINE modules (they are part of the snapshot's confidence notes), which this task must not change. They still call a registry value 'Confirmed'.
# Listed here so that a NEW such sentence fails this test, and so that fixing one of them (an engine-text task) means removing it from this list.
KNOWN_ENGINE_STRINGS = (
    (r"FE-002's own Confirmed '>98% removal", "own Confirmed '>98% removal efficiency", "python/fe_feed_handling.py"),
    (r"GC-002's own Confirmed >90% efficiency", "own Confirmed >90% efficiency", "python/gc_gas_cleaning_chain.py"),
    (r"ACTUAL/DOK-ING VALUE: Confirmed", "ACTUAL/DOK-ING VALUE: Confirmed", "python/eu_utilities_chp.py"),
    # LEDGER D2 (deliberate edit): the tab1_integration.py sentence ("exceeds its Confirmed 20kW rating") was reworded and is computed live, so it no longer renders: entry removed
)
CLAIM = re.compile(r"(?:\b(?:own|its|real|a|an|already)[ -]Confirmed\b|ACTUAL/DOK-ING VALUE: Confirmed|\(Confirmed\)|\d+ Confirmed \+|Confirmed[ -](?:rating|nameplate|capacity|target|technology|inlet|motor|design|reference|static|constant|bounds|remarks))")


def _rows():
    with open(FIXTURE, encoding="utf-8") as h:
        doc = json.load(h)
    return [{"equipment_id": e["key"][0], "category": e["key"][1], "entry": e["entry"], "cycle": 1, "published_at": "2026-09-10T00:04:00Z"} for e in doc["entries"]]


@pytest.fixture(scope="module")
def rendered():
    st.cache_data.clear()
    fake = FakeSupabase({"plant_state_current": _rows()})
    with patched_supabase(fake), mock.patch("urllib.request.urlopen", side_effect=BLOCKED):
        at = AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception, [str(e.value)[:300] for e in at.exception]
    assert [c for c in fake.calls if c[0] != "select"] == [], "the app wrote to the (fake) database"
    parts = []
    for kind in ("markdown", "caption", "info", "warning", "success", "error", "subheader", "header", "title", "text"):
        parts += [str(el.value) for el in getattr(at, kind, [])]
    parts += [f"{m.label} :: {m.value}" for m in at.metric]
    return {"at": at, "text": "\n".join(parts), "fake": fake}


# ---------------------------------------------------------------- the rendered app (first: see the ORDER note)

def test_the_slot_label_is_not_dokink_confirmed_and_the_old_label_is_gone(rendered):
    at, text = rendered["at"], rendered["text"]
    labels = [m.label for m in at.metric]
    assert labels.count("Not DOK-ING-confirmed") >= 7 and "Not DOK-ING-confirmed slots" in labels      # seven section tabs + the all-sections card
    assert not [l for l in labels if re.fullmatch(r"Not[ -]confirmed( slots)?", l, re.I)], [l for l in labels if "onfirmed" in l]
    assert not re.search(r"\*\*\d+ not confirmed\*\*", text, re.I), "the slot caption still says 'not confirmed'"       # other uses (e.g. 'also not confirmed at that precision') are unrelated prose
    assert "**297 not DOK-ING-confirmed**" in text


def test_the_counts_are_unchanged_by_the_wording(rendered):
    s = eds.summarize(eds.resolve_datasheets(eee.apply_estimates(erf.apply_rfi_fills(eds.build_all_datasheets()))))
    assert (s["confirmed_category_slots"], s["estimated_category_slots"], s["missing_category_slots"], s["total_category_slots"]) == (13, 297, 236, 546)
    assert s["evidence_label_rows"]["Confirmed"] == 16 and s["evidence_label_rows"]["Unverified (registry)"] == 737
    metrics = {}
    for m in rendered["at"].metric:
        metrics.setdefault(m.label, []).append(m.value)
    assert metrics["Confirmed (DOK-ING-sourced) slots"] == ["13 / 546"] and metrics["Not DOK-ING-confirmed slots"] == ["297 / 546"]
    assert "Confirmed means a DOK-ING source is cited; unverified rows have no stated origin yet." in rendered["text"]


def test_no_static_sentence_calls_registry_data_confirmed_without_the_dokink_qualifier(rendered):
    text = rendered["text"]
    remaining = []
    for m in CLAIM.finditer(text):
        ctx = " ".join(text[max(0, m.start() - 45): m.end() + 60].split())
        if any(re.search(p, ctx) for p in TRUE_AS_WRITTEN):
            continue
        remaining.append(ctx)
    unexplained = [c for c in remaining if not any(re.search(p, c) for p, _, _ in KNOWN_ENGINE_STRINGS)]
    assert unexplained == [], unexplained
    for pattern, phrase, rel in KNOWN_ENGINE_STRINGS:              # the allow-list entries really are engine-module text (and still there)
        assert any(re.search(pattern, c) for c in remaining), f"{pattern!r} no longer renders: remove it from KNOWN_ENGINE_STRINGS"
        # LEDGER D2 (deliberate edit): these sentences were reworded in the engine modules (task A3 item D); they still render here only because the committed sample
        # snapshot (tests/fixtures/sample_snapshot.json) is a frozen copy of the OLD text. So the old phrase must be gone from the engine file (it used to be asserted present).
        assert phrase not in open(os.path.join(ROOT, rel), encoding="utf-8").read(), (phrase, rel)


def test_the_reworded_paragraphs_say_what_the_overlay_supports(rendered):
    text = " ".join(rendered["text"].split())
    assert "registry entries whose origin is stated in the provenance worksheet (counts at the top of Section 7) or a stated engineering estimate" in text
    assert "(the Confirmed / Not DOK-ING-confirmed split is shown in the counts above)" in text
    assert "ER Estimated (literature-informed) and steam ratio Assumed in the provenance worksheet; not DOK-ING-confirmed" in text
    assert "27 Confirmed + 7" not in text and "real registry/vendor/DOK-ING data (Confirmed)" not in text
    assert "Assumed — reads a static registry design constant" in text and "reads a Confirmed static" not in text


def test_no_database_or_network_call_was_made(rendered):
    assert [c for c in rendered["fake"].calls if c[0] != "select"] == []


# ---------------------------------------------------------------- nothing but text changed

def _strip_strings(src):
    class T(ast.NodeTransformer):
        def visit_JoinedStr(self, node):
            return ast.copy_location(ast.Constant("S"), node)

        def visit_Constant(self, node):
            return ast.copy_location(ast.Constant("S" if isinstance(node.value, str) else node.value), node)
    return ast.dump(T().visit(ast.parse(src)))


def test_app_py_changed_in_its_strings_only():
    """Scoped to this task: runs only when every commit between origin/main and HEAD starts with 'Wording follow-up'. All string constants and f-strings are neutralised; the rest of
    the syntax tree of app.py must be identical to origin/main's (no logic, no call, no layout change)."""
    try:
        subprocess.run(["git", "rev-parse", "--verify", "origin/main"], cwd=ROOT, capture_output=True, check=True)
        subjects = subprocess.run(["git", "log", "origin/main..HEAD", "--format=%s"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()
        old = subprocess.run(["git", "show", "origin/main:app.py"], cwd=ROOT, capture_output=True, check=True).stdout.decode("utf-8")
    except Exception:                                                   # noqa: BLE001
        pytest.skip("git history not available")
    if not subjects or not all(s.startswith("Wording follow-up") for s in subjects):
        pytest.skip("not a wording-follow-up range")
    new = open(APP, encoding="utf-8").read()
    assert _strip_strings(new) == _strip_strings(old)
    assert new != old


def test_this_tasks_commits_touch_only_text_files():
    try:
        subprocess.run(["git", "rev-parse", "--verify", "origin/main"], cwd=ROOT, capture_output=True, check=True)
        names = subprocess.run(["git", "log", "origin/main..HEAD", "--grep=^Wording follow-up", "--name-only", "--format="], cwd=ROOT, capture_output=True, text=True,
                               check=True).stdout.split()
    except Exception:                                                   # noqa: BLE001
        pytest.skip("git history not available")
    allowed = {"app.py", "docs/provenance_phase2.md", "tests/test_apply_provenance.py", "tests/test_apply_wording.py"}
    assert set(names) <= allowed, sorted(set(names) - allowed)


def test_the_snapshot_and_its_persisted_key_count_are_unchanged():
    fake = FakeSupabase()
    with patched_supabase(fake):
        snap, _state, _engine = t1.build_live_snapshot(2)
    assert len(snap) == 123 and all(isinstance(k, tuple) and len(k) == 2 for k in snap)      # HEAT INTEGRATION (deliberate edit): 121 = 120 + the read-only (PLANT, HeatIntegration) key; A1 (deliberate edit): +1 = the switch input; A1.3 (deliberate edit): 123 = 122 + the read-only (GA-001, AgentConsistency) key
    assert not [k for k in snap if re.search(r"wording|overlay|provenance|unverified", " ".join(k), re.I)]
    assert fake.calls == []


def test_no_reworded_phrase_has_come_back_in_the_live_snapshot():
    """This file renders the app from a frozen sample snapshot (the OLD text), so it cannot see an engine note that goes back to the old wording. The live snapshot can: none of the
    old phrases of tests/_d2_wording.py (ledger D2 and wording pass W1, the old side of every pair) may be in it. WORDING W2.3 (deliberate addition)."""
    fake = FakeSupabase()
    with patched_supabase(fake):
        snap = t1.build_live_snapshot(20)[0]
    text = json.dumps({f"{k[0]}|{k[1]}": v for k, v in snap.items()}, sort_keys=True, default=str)
    assert sum(new in text for new, _ in _d2_wording.PAIRS) >= 89, "not vacuous: the new phrases are what the live snapshot says"
    assert [old for _, old in _d2_wording.PAIRS if old in text] == []
    assert [c for c in fake.calls if c[0] != "select"] == []

