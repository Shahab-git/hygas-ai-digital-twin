"""P2-3: the Design Basis decision board. Offline; the counts must come from code, not from typed numbers."""
import sys
from unittest import mock
import streamlit as st
from streamlit.testing.v1 import AppTest
from _fakes import FakeSupabase, patched_supabase
import test_app_smoke as smoke

sys.path.insert(0, smoke.ROOT)
from python import design_basis, design_basis_board as dbb, tab1_integration as t1


def test_board_counts_come_from_the_code():
    snap = t1.build_live_snapshot()[0]
    d = dbb.board_data(snap)
    assert d["rfi1_total"] == len(design_basis.QUESTIONS) and d["rfi1_confirmed"] == design_basis.summarize()[design_basis.STATUS_CONFIRMED]
    assert d["registry_doking"] == dbb.registry_rows_by_label().get("Confirmed", 0)
    assert d["registry_total"] == sum(dbb.registry_rows_by_label().values())
    assert d["measured"] == sum(1 for e in snap.values() if e["status"] == "Measured")


def test_the_n2_line_uses_the_live_figures_and_degrades_without_them():
    snap = t1.build_live_snapshot()[0]
    live = snap[("GA-001", "Outputs")]["value"]["N2_mol_pct_dry"]
    why = dbb.board_data(snap)["open_questions"][0][1]
    assert dbb.registry_expected_n2_pct() == 10.0
    assert f"{live:.0f}" in why and "10" in why
    assert "could not be read" in dbb.board_data({})["open_questions"][0][1]


def test_the_app_shows_the_board_on_the_design_basis_tab():
    st.cache_data.clear()
    with patched_supabase(FakeSupabase({"plant_state_current": smoke._store_rows()})), \
            mock.patch("urllib.request.urlopen", side_effect=smoke._offline_urlopen):
        at = AppTest.from_file(smoke.APP, default_timeout=90).run()
    assert not at.exception, [str(e.value)[:300] for e in at.exception]
    tab = [t for t in at.tabs if t.label == "Design Basis"][0]
    m = {x.label: x.value for x in tab.metric}
    assert m["RFI #1 confirmed by DOK-ING"] == f"{len(design_basis.QUESTIONS)} / {len(design_basis.QUESTIONS)}"
    assert m["Registry rows with a DOK-ING source"] == str(dbb.registry_rows_by_label()["Confirmed"])
    assert m["Measured values in the model"] == str(sum(1 for r in smoke._store_rows() if r["entry"].get("status") == "Measured"))
