"""Audit fix J2: the acceptance items of fix A (real elapsed time as the cycle
time step) plus fix C's counter. No database, no network (fake client)."""
import contextlib
import io
import json
import os
import runpy

import pytest

from _fakes import FakeSupabase, patched_supabase
from python import (ai_automation_layer as ai, cycle_clock, eu_utilities_chp as eu, fe_feed_handling as fe,
                    ga001_gasifier_model as ga, gc_gas_cleaning_chain as gc, hb_remaining_chain as hbr,
                    hb_wgs_psa_storage_chain as hb, plant_status as ps, sa_virtual_sensors as sa,
                    shared_plant_state as sps, simulation_engine as se, tab1_integration)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(autouse=True)
def _reset_clock():
    cycle_clock.set_elapsed_hours(None)
    yield
    cycle_clock.set_elapsed_hours(None)


def _dump(snapshot):
    return json.dumps({f"{k[0]}|{k[1]}": v for k, v in snapshot.items()}, sort_keys=True, default=str)


def _ok(value, status=ps.STATUS_CALCULATED):
    return {"status": status, "value": value}


_MISSING = {"status": ps.STATUS_MISSING, "value": None}


def test_default_dt_is_the_old_constant_and_explicit_one_changes_nothing():
    assert cycle_clock.hours_per_cycle() == hb.ASSUMED_HOURS_PER_CYCLE == 1.0
    with patched_supabase(FakeSupabase()):
        default_snap, _s, _e = tab1_integration.build_live_snapshot()
        cycle_clock.set_elapsed_hours(1.0)
        explicit_snap, _s, _e = tab1_integration.build_live_snapshot()
    assert _dump(default_snap) == _dump(explicit_snap)


@pytest.mark.parametrize("dt", [1.0, 4.0, 6.0])
def test_accumulators_change_in_proportion_to_dt(dt):
    cycle_clock.set_elapsed_hours(dt)
    # FE-001: level change = (delivery - 41.67)/1000 * dt
    r_fe = fe.fe001_inventory(lambda k: {("FE-001-INPUT", "msw_delivery_rate_kg_h"): _ok(45.0),
                                         ("FE-001", "Inventory"): _ok({"level_t": 0.5})}[k])
    assert r_fe["value"]["level_t"] - 0.5 == pytest.approx((45.0 - fe.FE003_NOMINAL_KG_H) / 1000.0 * dt)
    # HB-013: change = (inflow - outflow) * dt
    inputs = {("HB-012", "Compressor"): _ok({"h2_kg_h": 1.0}), ("HB-013", "Storage"): _ok({"level_kg": 10.0}),
              ("HB-011", "Electrolyser"): _MISSING, ("HB-018", "Dispensing"): _MISSING, ("EU-006", "FuelCell"): _MISSING}
    r_hb = hb.hb013_storage_level(lambda k: inputs[k])
    assert r_hb["value"]["level_kg"] - 10.0 == pytest.approx(1.0 * dt)
    # EU-010: charge net*dt*efficiency, discharge net*dt
    r_ch = eu.eu010_ups_battery(lambda k: {("EU-009", "GridBalance"): _ok({"net_kw": 0.2}), ("EU-010", "UPS"): _ok({"soc_kwh": 2.0})}[k])
    assert r_ch["value"]["soc_kwh"] - 2.0 == pytest.approx(0.2 * dt * eu.EU010_ROUNDTRIP_EFFICIENCY)
    r_di = eu.eu010_ups_battery(lambda k: {("EU-009", "GridBalance"): _ok({"net_kw": -0.1}), ("EU-010", "UPS"): _ok({"soc_kwh": 2.0})}[k])
    assert r_di["value"]["soc_kwh"] - 2.0 == pytest.approx(-0.1 * dt)


def test_engine_three_cycles_dt_1_4_6_fe001_follows_the_formula():
    state = sps.SharedPlantState()
    engine = se.SimulationEngine(state)
    for register in (fe.register_fe_chain, ga.register_ga001, gc.register_gc_chain, hb.register_hb_chain,
                     hbr.register_hb_remaining, eu.register_eu_chain, sa.register_sa_sensors, ai.register_ai_layer):
        register(engine)
    delivery = fe.FE001_DEFAULT_DELIVERY_RATE_KG_H * 1.10
    engine._models[("FE-001-INPUT", "msw_delivery_rate_kg_h")]["fn"] = lambda gi: {
        "value": delivery, "status": ps.STATUS_ASSUMED, "validation_basis": ps.VALIDATION_NA, "confidence_note": "test"}
    previous = fe.FE001_LIVE_CAPACITY_T * 0.5
    with patched_supabase(FakeSupabase()):
        for cycle, dt in enumerate((1.0, 4.0, 6.0), 1):
            cycle_clock.set_elapsed_hours(dt)
            engine.run_cycle(now=f"2026-09-10T00:{cycle:02d}:00Z")
            level = state.get_snapshot()[("FE-001", "Inventory")]["value"]["level_t"]
            assert level - previous == pytest.approx((delivery - fe.FE003_NOMINAL_KG_H) / 1000.0 * dt)
            previous = level


@pytest.mark.parametrize("label,previous,expected_h,clamped", [
    ("zero hours", "2026-10-27T12:00:00+00:00", 0.05, True),
    ("30 hours", "2026-10-26T06:00:00+00:00", 12.0, True),
    ("negative (clock skew)", "2026-10-27T14:00:00+00:00", 0.05, True),
    ("normal 1.5 h", "2026-10-27T10:30:00+00:00", 1.5, False),
    ("missing timestamp", None, 1.0, False),
    ("unparsable timestamp", "not-a-date", 1.0, False),
])
def test_elapsed_hours_clamp_rule(label, previous, expected_h, clamped):
    result = cycle_clock.compute_elapsed_hours(previous, "2026-10-27T12:00:00+00:00")
    assert result["elapsed_h_used"] == pytest.approx(expected_h), label
    assert result["clamped"] is clamped, label


def test_set_elapsed_hours_refuses_nonsense():
    for bad in (0, -1.0, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            cycle_clock.set_elapsed_hours(bad)


def test_driver_three_runs_counter_and_elapsed_hours(monkeypatch):
    """Fix A4 + C: three simulated consecutive runs against an in-memory store ->
    CycleCounter 1, 2, 3; rows' cycle column follows it; ElapsedHours = 1.0 (empty
    store), 4.0, 2.0; updated_at advances."""
    monkeypatch.setenv("HYGAS_ALLOW_DB_WRITES", "1")
    driver = runpy.run_path(os.path.join(ROOT, "scripts", "run_continuous_cycle.py"), run_name="driver_under_test")
    fake = FakeSupabase(missing_tables={"digital_twin_cycle_log"})
    times = ["2026-10-27T08:17:00+00:00", "2026-10-27T12:17:00+00:00", "2026-10-27T14:17:00+00:00"]
    expected_dt = [1.0, 4.0, 2.0]
    with patched_supabase(fake):
        for run, (now_iso, dt) in enumerate(zip(times, expected_dt), 1):
            with contextlib.redirect_stdout(io.StringIO()):
                driver["main"](now_iso=now_iso)
            rows = {(r["equipment_id"], r["category"]): r for r in fake.tables["plant_state_current"]}
            assert rows[("RUNTIME", "CycleCounter")]["entry"]["value"] == run
            assert {r["cycle"] for r in rows.values()} == {run}
            assert rows[("RUNTIME", "ElapsedHours")]["entry"]["value"]["elapsed_h_used"] == pytest.approx(dt)
            assert {r["updated_at"] for r in rows.values()} == {now_iso}
    assert cycle_clock.hours_per_cycle() == 1.0, "the driver must restore the default dt when it finishes"
