"""Readiness gate (task A10): pass / fail with the missing evidence; every criterion defaults to None; informational only.

Every number below is a TEST value passed in explicitly. The module has no default threshold, and these tests pin that (a criterion default set to a number fails)."""
import copy
import dataclasses

import pytest

from python import maturity as mt
from python import readiness_gate as rg

CAPS = rg.CAPABILITIES
COMPLETE = rg.Evidence(measured_pairs_count=100, synthetic_pairs_count=50, operating_range_coverage=0.8, instrument_uncertainty_known=True, identifiability_screen_passed=True,
                       heldout_campaigns=3, heldout_error=0.05, failure_events_count=4, confirmed_envelope_present=True, fallback_defined=True)
CRIT = rg.Criteria(min_measured_pairs=50, min_operating_range_coverage=0.7, min_heldout_campaigns=2, max_heldout_error=0.1, min_failure_events=3)       # TEST values only


def test_the_six_capabilities_and_their_required_items_are_pinned():
    assert CAPS == ("calibration", "validation", "virtual_sensing", "predictive_maintenance", "optimisation", "online_replacement")
    assert rg.REQUIRED["calibration"] == ("measured_pairs_count", "operating_range_coverage", "instrument_uncertainty_known", "identifiability_screen_passed")
    assert set(rg.REQUIRED["validation"]) - set(rg.REQUIRED["calibration"]) == {"heldout_campaigns", "heldout_error"}
    assert set(rg.REQUIRED["predictive_maintenance"]) - set(rg.REQUIRED["validation"]) == {"failure_events_count"}
    assert set(rg.REQUIRED["optimisation"]) - set(rg.REQUIRED["validation"]) == {"confirmed_envelope_present"}
    assert set(rg.REQUIRED["online_replacement"]) - set(rg.REQUIRED["validation"]) == {"confirmed_envelope_present", "fallback_defined"}
    assert set(rg.REQUIRED["virtual_sensing"]) == set(rg.REQUIRED["validation"])


def test_every_criterion_defaults_to_none_no_number_is_chosen():
    crit = rg.Criteria()
    assert [f.name for f in dataclasses.fields(crit)] == ["min_measured_pairs", "min_operating_range_coverage", "min_heldout_campaigns", "max_heldout_error", "min_failure_events"]
    assert all(getattr(crit, f.name) is None for f in dataclasses.fields(crit))
    assert all(f.default is None for f in dataclasses.fields(rg.Criteria))


@pytest.mark.parametrize("cap", CAPS)
def test_with_no_evidence_and_no_criteria_the_gate_fails_and_names_everything(cap):
    r = rg.readiness_gate(cap, None, None)
    assert r["passes"] is False and r["maturity_allowed"] == mt.PHYSICS_ESTIMATE
    for item in rg.REQUIRED[cap]:
        assert f"missing evidence: {item}" in r["reasons"], (cap, item)
        field = rg.ITEM_CRITERION[item][0]
        if field:
            assert f"criteria not set: {field}" in r["reasons"], (cap, field)


@pytest.mark.parametrize("cap", CAPS)
def test_complete_evidence_with_criteria_none_still_fails_with_criteria_not_set(cap):
    r = rg.readiness_gate(cap, COMPLETE, rg.Criteria())
    assert r["passes"] is False
    fields = {rg.ITEM_CRITERION[i][0] for i in rg.REQUIRED[cap] if rg.ITEM_CRITERION[i][0]}
    assert {x for x in r["reasons"] if x.startswith("criteria not set:")} == {f"criteria not set: {f}" for f in fields}
    assert not any(x.startswith("missing evidence") for x in r["reasons"])


@pytest.mark.parametrize("cap", CAPS)
def test_hand_built_complete_evidence_and_criteria_pass(cap):
    r = rg.readiness_gate(cap, COMPLETE, CRIT)
    assert r == {"passes": True, "reasons": [], "maturity_allowed": mt.VALIDATED_ON_HELDOUT}


@pytest.mark.parametrize("cap", CAPS)
def test_each_missing_item_alone_gives_exactly_its_named_reason(cap):
    blank = {"measured_pairs_count": 0, "operating_range_coverage": None, "instrument_uncertainty_known": False, "identifiability_screen_passed": False, "heldout_campaigns": 0,
             "heldout_error": None, "failure_events_count": 0, "confirmed_envelope_present": False, "fallback_defined": False}
    for item in rg.REQUIRED[cap]:
        ev = dataclasses.replace(COMPLETE, **{item: blank[item]})
        r = rg.readiness_gate(cap, ev, CRIT)
        assert r["passes"] is False and r["reasons"] == [f"missing evidence: {item}"], (cap, item, r["reasons"])


@pytest.mark.parametrize("item,field,limit,ok,bad", [
    ("measured_pairs_count", "min_measured_pairs", 50, 50, 49), ("operating_range_coverage", "min_operating_range_coverage", 0.7, 0.7, 0.69),
    ("heldout_campaigns", "min_heldout_campaigns", 2, 2, 1), ("failure_events_count", "min_failure_events", 3, 3, 2)])
def test_both_sides_of_every_minimum_threshold(item, field, limit, ok, bad):
    crit = dataclasses.replace(rg.Criteria(), **{k: v for k, v in dataclasses.asdict(CRIT).items()})
    assert getattr(crit, field) == limit
    assert rg.readiness_gate("predictive_maintenance", dataclasses.replace(COMPLETE, **{item: ok}), crit)["passes"] is True               # exactly at the limit passes
    r = rg.readiness_gate("predictive_maintenance", dataclasses.replace(COMPLETE, **{item: bad}), crit)
    assert r["passes"] is False and any(x.startswith(f"below criterion: {item}") for x in r["reasons"])


def test_both_sides_of_the_held_out_error_maximum():
    assert rg.readiness_gate("validation", dataclasses.replace(COMPLETE, heldout_error=0.1), CRIT)["passes"] is True
    r = rg.readiness_gate("validation", dataclasses.replace(COMPLETE, heldout_error=0.1001), CRIT)
    assert r["passes"] is False and any(x.startswith("above criterion: heldout_error") for x in r["reasons"])


def test_maturity_allowed_follows_the_evidence_not_the_capability():
    none, synth = rg.Evidence(), rg.Evidence(synthetic_pairs_count=10)
    plant = rg.Evidence(measured_pairs_count=5)
    held = dataclasses.replace(plant, heldout_campaigns=2, heldout_error=0.05)
    for cap in CAPS:
        assert rg.readiness_gate(cap, none, CRIT)["maturity_allowed"] == mt.PHYSICS_ESTIMATE
        assert rg.readiness_gate(cap, synth, CRIT)["maturity_allowed"] == mt.SYNTHETIC_BENCHMARK
        assert rg.readiness_gate(cap, plant, CRIT)["maturity_allowed"] == mt.TRAINED_ON_PLANT_DATA
        assert rg.readiness_gate(cap, held, CRIT)["maturity_allowed"] == mt.VALIDATED_ON_HELDOUT
    assert rg.readiness_gate("calibration", held, rg.Criteria())["maturity_allowed"] == mt.TRAINED_ON_PLANT_DATA, "held-out criteria None: the last step is unreachable"
    assert rg.readiness_gate("calibration", dataclasses.replace(held, heldout_error=0.2), CRIT)["maturity_allowed"] == mt.TRAINED_ON_PLANT_DATA
    assert rg.readiness_gate("calibration", dataclasses.replace(held, heldout_campaigns=1), CRIT)["maturity_allowed"] == mt.TRAINED_ON_PLANT_DATA
    assert rg.readiness_gate("calibration", dataclasses.replace(held, measured_pairs_count=0, synthetic_pairs_count=3), CRIT)["maturity_allowed"] == mt.SYNTHETIC_BENCHMARK, \
        "held-out figures without plant data do not raise the class"


def test_maturity_allowed_never_exceeds_what_a_complete_but_unset_gate_supports():
    r = rg.readiness_gate("online_replacement", COMPLETE, rg.Criteria())
    assert r["passes"] is False and r["maturity_allowed"] == mt.TRAINED_ON_PLANT_DATA


def test_an_unknown_capability_is_an_error():
    with pytest.raises(ValueError):
        rg.readiness_gate("autonomous_control", COMPLETE, CRIT)


def test_the_gate_has_no_side_effect_and_returns_a_fresh_result():
    ev, cr = copy.deepcopy(COMPLETE), copy.deepcopy(CRIT)
    a = rg.readiness_gate("validation", ev, cr)
    a["reasons"].append("tampered")
    b = rg.readiness_gate("validation", ev, cr)
    assert b["reasons"] == [] and ev == COMPLETE and cr == CRIT
    with pytest.raises(dataclasses.FrozenInstanceError):
        ev.measured_pairs_count = 0
    with pytest.raises(dataclasses.FrozenInstanceError):
        cr.min_measured_pairs = 0
