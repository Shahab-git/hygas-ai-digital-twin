"""Phase 1 task P1-04 (the two safety items of G5-08, items 5 and 6): no number moves.

1. operator_setpoints.request_setpoint is a durable database write and now refuses unless the caller
   says explicit_operator_call=True or the runtime flag HYGAS_ALLOW_DB_WRITES=1 is set.
2. performance_guarantee.price_with_confirmation_scenario no longer writes to the shared
   uncertainty.ASSUMPTIONS dict (set_confirmed / restore); it passes the hypothetical range as a
   confirmed_overrides argument. The results equal what the old mutate-and-restore code gave."""
import copy

import pytest

from _fakes import FakeSupabase, patched_supabase
from python import operator_setpoints as osp
from python import performance_guarantee as pg
from python import uncertainty

KEY = ("GA-001-INPUT", "equivalence_ratio")


@pytest.fixture(autouse=True)
def _no_flag(monkeypatch):
    monkeypatch.delenv("HYGAS_ALLOW_DB_WRITES", raising=False)


def test_request_setpoint_refuses_by_default_and_sends_nothing():
    fake = FakeSupabase()
    with patched_supabase(fake):
        with pytest.raises(RuntimeError, match="writes to the database"):
            osp.request_setpoint(KEY, 0.3, requested_by="test")
        with pytest.raises(RuntimeError):
            osp.request_setpoint(KEY, 0.3, explicit_operator_call="yes")      # only the literal True counts
    assert fake.calls == []


def test_request_setpoint_writes_for_an_explicit_operator_call_or_the_runtime_flag(monkeypatch):
    fake = FakeSupabase()
    with patched_supabase(fake):
        osp.request_setpoint(KEY, 0.3, requested_by="op", explicit_operator_call=True)
        monkeypatch.setenv("HYGAS_ALLOW_DB_WRITES", "1")
        osp.request_setpoint(KEY, 0.31, requested_by="op")
    assert [c[0] for c in fake.calls if c[0] != "select"] == ["upsert", "upsert"]


def _scenario(name="psa_target_calibration", lo=0.90, hi=1.00):
    return pg.price_with_confirmation_scenario(name, lo, hi, 0.735, n_runs=60)


def test_the_scenario_leaves_the_shared_assumptions_dict_exactly_as_it_was():
    before = copy.deepcopy(uncertainty.ASSUMPTIONS)
    _scenario()
    assert uncertainty.ASSUMPTIONS == before
    assert not uncertainty.is_confirmed("psa_target_calibration")


def test_the_scenario_equals_the_old_mutate_and_restore_result():
    new = _scenario()
    try:                                                   # the old behaviour, reproduced by hand
        before = pg.price_guarantee(0.735, pg.DEFAULT_PENALTY_EUR_PER_POINT, n_runs=60, seed=42)
        uncertainty.set_confirmed("psa_target_calibration", 0.90, 1.00)
        after = pg.price_guarantee(0.735, pg.DEFAULT_PENALTY_EUR_PER_POINT, n_runs=60, seed=42)
    finally:
        uncertainty.clear_confirmed("psa_target_calibration")
    for mine, old in ((new["before"], before), (new["after"], after)):
        assert mine["breach_probability"] == old["breach_probability"] and mine["expected_cost"] == old["expected_cost"]
    assert new["after"]["breach_probability"] != new["before"]["breach_probability"] or new["after"]["expected_cost"] != new["before"]["expected_cost"]


def test_a_bad_range_or_name_raises_before_anything_runs():
    before = copy.deepcopy(uncertainty.ASSUMPTIONS)
    with pytest.raises(ValueError):
        _scenario(lo=1.0, hi=0.9)
    with pytest.raises(KeyError):
        _scenario(name="no_such_assumption")
    assert uncertainty.ASSUMPTIONS == before


def test_bounds_and_the_monte_carlo_are_unchanged_without_an_override():
    assert uncertainty.bounds("psa_target_calibration") == uncertainty.bounds("psa_target_calibration", None)
    a = uncertainty.run_monte_carlo(n_runs=20, seed=1)
    b = uncertainty.run_monte_carlo(n_runs=20, seed=1, confirmed_overrides=None)
    assert a == b
