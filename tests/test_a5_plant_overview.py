"""P2-4: Plant Overview tab: long explanations moved into collapsed expanders, one figure per stage above the schematic.
Offline AppTest of the real app.py (named a5_ so it runs before the runpy-loading tests); not a browser rendering."""
import sys
from unittest import mock
import streamlit as st
from streamlit.testing.v1 import AppTest
from _fakes import FakeSupabase, patched_supabase
import test_app_smoke as smoke

sys.path.insert(0, smoke.ROOT)


def _run():
    st.cache_data.clear()
    with patched_supabase(FakeSupabase({"plant_state_current": smoke._store_rows()})), \
            mock.patch("urllib.request.urlopen", side_effect=smoke._offline_urlopen):
        return AppTest.from_file(smoke.APP, default_timeout=90).run()


def test_stage_figures_equal_the_summary_data_and_explanations_are_collapsed():
    at = _run()
    assert not at.exception, [str(e.value)[:300] for e in at.exception]
    tab = [t for t in at.tabs if t.label == "Plant Overview"][0]
    m = {x.label: x.value for x in tab.metric}
    # the app reads the persisted fixture store, so compare with the SAME rows (values only), not with a fresh engine run
    rows = {(r["equipment_id"], r["category"]): r["entry"]["value"] for r in smoke._store_rows()}
    assert m["Feed handling (FE)"] == f"{float(rows[('FE-001-INPUT', 'msw_delivery_rate_kg_h')]):.2f} kg/h"
    assert m["Hydrogen (HB)"] == f"{float(rows[('HB-012', 'Compressor')]['h2_kg_h']):.2f} kg/h"
    assert m["Cooling EU-008"] == (f"{float(rows[('EU-008', 'CoolingSupply')]['demand_kw']):.0f} / "
                                   f"{float(rows[('EU-008', 'RecommendedCapacityEstimate')]['actual_dokking_value_kw']):.0f} kW")
    labels = [e.label for e in tab.expander]
    assert "About this view" in labels and "About this schematic" in labels
    # the old long paragraphs are now INSIDE those expanders, not loose at the top of the tab
    inside = {e.label: " ".join(str(c.value) for c in e.caption) for e in tab.expander}
    assert "Dynamic" in inside["About this view"] and "compact view is the only new diagram" in inside["About this schematic"]
    assert "🟢 Computed this cycle (model)" in m or "🟢 Computed this cycle (model)" in {x.label for x in tab.metric}
