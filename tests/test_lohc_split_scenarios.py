"""LOHC split scenarios (P1-14, scripts/run_lohc_split_scenarios.py): a read-only sweep of the HB-007 split, NOT a chosen split.

Guards: the pure balance is right and reproduces the registry's own capacity numbers (0.031 m3/h of carrier, ~19 kW, 1 m3 tank about a day's buffer); the split is bounded
and clipped at the 2 kg/h capacity; the engine's HB-007 key and the LOHC chain stay Missing (the script wires nothing in); no database call. Offline: counting fake store."""
import importlib.util
import os

import pytest

from _fakes import FakeSupabase, patched_supabase
from python import hb_remaining_chain as hbrem
from python import plant_status as ps
from python import tab1_integration as t1

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(ROOT, "scripts", "run_lohc_split_scenarios.py")


@pytest.fixture(scope="module")
def study():
    spec = importlib.util.spec_from_file_location("run_lohc_split_scenarios", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_at_capacity_the_balance_reproduces_the_registry_numbers(study):
    s = study.scenario(3.0, 1.0)
    assert s["loaded_kg_h"] == 2.0 and s["clipped"] and s["to_compressed_route_kg_h"] == pytest.approx(1.0)
    assert s["carrier_m3_h"] == pytest.approx(0.031, rel=1e-12)                       # HB-015 remark, by construction of the derived density
    assert study.carrier_density_kg_m3() == pytest.approx(1040.6, abs=0.1)
    assert s["hydrogenation_heat_kw"] == pytest.approx(18.5, abs=0.1)                  # registry HB-016: 19 kW for "1000 mol H2/h" (we use 2 kg/h = 992 mol/h)
    assert s["rich_tank_hours"] == pytest.approx(32.3, abs=0.1)                        # HB-015 "roughly a day's buffer"
    assert s["round_trip"] == pytest.approx(6.0 / 6.2 * 0.99, rel=1e-12)
    assert s["released_kg_h"] == pytest.approx(2.0 * 6.0 / 6.2 * 0.99, rel=1e-12)


def test_split_zero_and_below_capacity_and_bounds(study):
    z = study.scenario(3.25, 0.0)
    assert z["loaded_kg_h"] == 0 and z["to_compressed_route_kg_h"] == 3.25 and z["rich_tank_hours"] is None and z["round_trip"] is None
    h = study.scenario(1.85, 0.5)
    assert h["loaded_kg_h"] == pytest.approx(0.925) and not h["clipped"]
    assert h["loaded_kg_h"] + h["to_compressed_route_kg_h"] == pytest.approx(1.85)       # hydrogen is conserved between the two routes
    for bad in (-0.01, 1.01):
        with pytest.raises(ValueError):
            study.scenario(1.85, bad)


def test_the_sweep_is_monotone_in_the_split(study):
    rows = [study.scenario(3.25, s) for s in study.SPLITS]
    loaded = [r["loaded_kg_h"] for r in rows]
    assert loaded == sorted(loaded) and study.SPLITS[0] == 0.0 and study.SPLITS[-1] == 1.0


def test_the_script_wires_nothing_in_and_the_branch_stays_missing(study):
    e = hbrem.hb007_h2_split_fraction(lambda k: None)
    assert e["status"] == ps.STATUS_MISSING and e["value"] is None
    fake = FakeSupabase()
    with patched_supabase(fake):
        snap = t1.build_live_snapshot(5)[0]
        h2 = study.live_psa_h2_kg_h("regasify")
    assert snap[("HB-007", "H2SplitFraction")]["status"] == ps.STATUS_MISSING
    assert snap[("HB-014", "MassBalance")]["status"] == ps.STATUS_MISSING
    assert [c for c in fake.calls if c[0] != "select"] == []
    assert h2 == pytest.approx(78.0 / 24.0, abs=0.01)                                  # the regasify hydrogen of docs/tail_gas_heat.md (P1-06f: the script's "regasify" is now explicit)
    assert study.live_psa_h2_kg_h("heat_only") == pytest.approx(55.7 / 24.0, abs=0.01)  # P1-06f: the real default's hydrogen, the other row of the study


