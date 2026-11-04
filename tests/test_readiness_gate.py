"""Readiness gate (tasks A10 and A10c): pass / fail with the missing evidence, following the roadmap's Track D gate table; every criterion defaults to None; informational only.

Every number below is a TEST value passed in explicitly. The module has no default threshold, and these tests pin that (a criterion default set to a number fails). The requirement table in
docs/maturity_and_readiness_gates.md is generated from REQUIRED and tested for freshness."""
import copy
import dataclasses
import os

import pytest

from python import maturity as mt
from python import readiness_gate as rg

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CAPS = rg.CAPABILITIES
INCONSISTENT = "physical_model_validated claimed without a passing validation gate"
COMPLETE = rg.Evidence(measured_pairs_count=100, synthetic_pairs_count=50, operating_range_coverage=0.8, instrument_uncertainty_known=True, identifiability_screen_passed=True,
                       balance_closure_within_uncertainty=True, heldout_campaigns=3, heldout_data_independent=True, heldout_error=0.05, error_metrics_per_quantity=True,
                       physical_model_validated=True, failure_events_count=4, failure_events_defined=True, intervals_reported=True, uncertainty_bounds_available=True,
                       confirmed_envelope_present=True, shadow_mode_comparison_done=True, calibrated_model_available=True, quality_gate_defined=True, drift_monitoring_defined=True,
                       fallback_defined=True)
CRIT = rg.Criteria(min_measured_pairs=50, min_operating_range_coverage=0.7, min_heldout_campaigns=2, max_heldout_error=0.1, max_target_accuracy=0.08, min_failure_events=3)       # TEST values only
BLANK = {"measured_pairs_count": 0, "operating_range_coverage": None, "heldout_campaigns": 0, "heldout_error": None, "failure_events_count": 0}
VALIDATION_ITEMS = set(rg.REQUIRED["validation"])

EXPECTED_REQUIRED = {
    "calibration": ("measured_pairs_count", "operating_range_coverage", "instrument_uncertainty_known", "identifiability_screen_passed", "balance_closure_within_uncertainty"),
    "validation": ("heldout_campaigns", "heldout_data_independent", "heldout_error", "error_metrics_per_quantity"),
    "virtual_sensing": ("measured_pairs_count", "operating_range_coverage", "physical_model_validated", "heldout_error"),
    "predictive_maintenance": ("failure_events_count", "failure_events_defined", "intervals_reported"),
    "optimisation": ("physical_model_validated", "uncertainty_bounds_available", "confirmed_envelope_present", "shadow_mode_comparison_done"),
    "online_replacement": ("calibrated_model_available", "quality_gate_defined", "drift_monitoring_defined", "fallback_defined"),
}


def _blank(item):
    return BLANK.get(item, False)


def test_the_requirement_table_is_the_roadmaps_track_d_table():
    assert CAPS == ("calibration", "validation", "virtual_sensing", "predictive_maintenance", "optimisation", "online_replacement")
    assert rg.REQUIRED == EXPECTED_REQUIRED
    assert set(rg.REQUIRED["calibration"]) & VALIDATION_ITEMS == set(), "the calibration set is not required for validation"
    assert "heldout_error" in rg.REQUIRED["virtual_sensing"] and "physical_model_validated" in rg.REQUIRED["virtual_sensing"]
    assert rg.criterion_for("validation", "heldout_error") == ("max_heldout_error", "max")
    assert rg.criterion_for("virtual_sensing", "heldout_error") == ("max_target_accuracy", "max")


def test_every_required_item_is_a_field_of_evidence_and_every_criterion_a_field_of_criteria():
    ev_fields = {f.name for f in dataclasses.fields(rg.Evidence)}
    cr_fields = {f.name for f in dataclasses.fields(rg.Criteria)}
    for cap, items in rg.REQUIRED.items():
        for item in items:
            assert item in ev_fields, (cap, item)
            field, _ = rg.criterion_for(cap, item)
            assert field is None or field in cr_fields, (cap, item, field)


def test_every_criterion_defaults_to_none_no_number_is_chosen():
    crit = rg.Criteria()
    assert [f.name for f in dataclasses.fields(crit)] == ["min_measured_pairs", "min_operating_range_coverage", "min_heldout_campaigns", "max_heldout_error", "max_target_accuracy",
                                                           "min_failure_events"]
    assert all(getattr(crit, f.name) is None for f in dataclasses.fields(crit))
    assert all(f.default is None for f in dataclasses.fields(rg.Criteria))


def test_every_evidence_field_defaults_to_missing():
    ev = rg.Evidence()
    for f in dataclasses.fields(ev):
        v = getattr(ev, f.name)
        assert v is None or v is False or v == 0, (f.name, v)


@pytest.mark.parametrize("cap", CAPS)
def test_with_no_evidence_and_no_criteria_the_gate_fails_and_names_everything(cap):
    r = rg.readiness_gate(cap, None, None)
    assert r["passes"] is False and r["maturity_allowed"] == mt.PHYSICS_ESTIMATE
    for item in rg.REQUIRED[cap]:
        assert f"missing evidence: {item}" in r["reasons"], (cap, item)
        field, _ = rg.criterion_for(cap, item)
        if field:
            assert f"criteria not set: {field}" in r["reasons"], (cap, field)
    assert INCONSISTENT not in r["reasons"]


@pytest.mark.parametrize("cap", CAPS)
def test_complete_evidence_with_criteria_none_still_fails_with_criteria_not_set(cap):
    r = rg.readiness_gate(cap, COMPLETE, rg.Criteria())
    assert r["passes"] is False
    fields = {rg.criterion_for(cap, i)[0] for i in rg.REQUIRED[cap] if rg.criterion_for(cap, i)[0]}
    assert {x for x in r["reasons"] if x.startswith("criteria not set:")} == {f"criteria not set: {f}" for f in fields}
    assert not any(x.startswith("missing evidence") for x in r["reasons"])
    assert INCONSISTENT in r["reasons"], "the claim physical_model_validated cannot be backed while the validation criteria are None"


@pytest.mark.parametrize("cap", CAPS)
def test_hand_built_complete_evidence_and_criteria_pass(cap):
    r = rg.readiness_gate(cap, COMPLETE, CRIT)
    assert r == {"passes": True, "reasons": [], "maturity_allowed": mt.VALIDATED_ON_HELDOUT}


@pytest.mark.parametrize("cap", CAPS)
def test_each_missing_item_alone_gives_exactly_its_named_reason(cap):
    for item in rg.REQUIRED[cap]:
        ev = dataclasses.replace(COMPLETE, **{item: _blank(item)})
        r = rg.readiness_gate(cap, ev, CRIT)
        expected = [f"missing evidence: {item}"]
        if item in VALIDATION_ITEMS:                                   # the claimed physical_model_validated no longer has a passing validation gate behind it
            expected.append(INCONSISTENT)
        assert r["passes"] is False and r["reasons"] == expected, (cap, item, r["reasons"])


@pytest.mark.parametrize("cap,item,field,ok,bad", [
    ("calibration", "measured_pairs_count", "min_measured_pairs", 50, 49), ("calibration", "operating_range_coverage", "min_operating_range_coverage", 0.7, 0.69),
    ("virtual_sensing", "measured_pairs_count", "min_measured_pairs", 50, 49), ("virtual_sensing", "operating_range_coverage", "min_operating_range_coverage", 0.7, 0.69),
    ("validation", "heldout_campaigns", "min_heldout_campaigns", 2, 1), ("predictive_maintenance", "failure_events_count", "min_failure_events", 3, 2)])
def test_both_sides_of_every_minimum_threshold(cap, item, field, ok, bad):
    assert rg.readiness_gate(cap, dataclasses.replace(COMPLETE, **{item: ok}), CRIT)["passes"] is True               # exactly at the limit passes
    r = rg.readiness_gate(cap, dataclasses.replace(COMPLETE, **{item: bad}), CRIT)
    assert r["passes"] is False and any(x.startswith(f"below criterion: {item}") and field in x for x in r["reasons"])


def test_both_sides_of_the_validation_error_maximum():
    assert rg.readiness_gate("validation", dataclasses.replace(COMPLETE, heldout_error=0.1), CRIT)["passes"] is True
    r = rg.readiness_gate("validation", dataclasses.replace(COMPLETE, heldout_error=0.1001), CRIT)
    assert r["passes"] is False and any(x.startswith("above criterion: heldout_error") and "max_heldout_error" in x for x in r["reasons"])


def test_virtual_sensing_compares_the_error_with_the_target_accuracy_not_with_the_validation_criterion():
    # target accuracy 0.08 is STRICTER than the validation maximum 0.1: an error of 0.09 validates but is too large for the sensor
    ev = dataclasses.replace(COMPLETE, heldout_error=0.09)
    assert rg.readiness_gate("validation", ev, CRIT)["passes"] is True
    r = rg.readiness_gate("virtual_sensing", ev, CRIT)
    assert r["passes"] is False and r["reasons"] == ["above criterion: heldout_error 0.09 > max_target_accuracy 0.08"]
    assert rg.readiness_gate("virtual_sensing", dataclasses.replace(COMPLETE, heldout_error=0.08), CRIT)["passes"] is True            # exactly at the target accuracy
    # target accuracy LOOSER than the validation maximum: an error of 0.15 fails validation (and so the claim) but is not reported against max_heldout_error in virtual sensing
    loose = dataclasses.replace(CRIT, max_target_accuracy=0.2)
    r = rg.readiness_gate("virtual_sensing", dataclasses.replace(COMPLETE, heldout_error=0.15), loose)
    assert not any("max_heldout_error" in x for x in r["reasons"]) and not any(x.startswith("above criterion") for x in r["reasons"])
    assert r["reasons"] == [INCONSISTENT]
    # the validation criterion alone does not make virtual sensing computable
    r = rg.readiness_gate("virtual_sensing", COMPLETE, dataclasses.replace(CRIT, max_target_accuracy=None))
    assert "criteria not set: max_target_accuracy" in r["reasons"] and "criteria not set: max_heldout_error" not in r["reasons"]


def test_maturity_allowed_follows_the_evidence_and_only_the_validation_gate_grants_the_top_class():
    none, synth, plant = rg.Evidence(), rg.Evidence(synthetic_pairs_count=10), rg.Evidence(measured_pairs_count=5)
    held = dataclasses.replace(plant, heldout_campaigns=2, heldout_data_independent=True, heldout_error=0.05, error_metrics_per_quantity=True)
    for cap in CAPS:
        assert rg.readiness_gate(cap, none, CRIT)["maturity_allowed"] == mt.PHYSICS_ESTIMATE
        assert rg.readiness_gate(cap, synth, CRIT)["maturity_allowed"] == mt.SYNTHETIC_BENCHMARK
        assert rg.readiness_gate(cap, plant, CRIT)["maturity_allowed"] == mt.TRAINED_ON_PLANT_DATA
        assert rg.readiness_gate(cap, held, CRIT)["maturity_allowed"] == mt.VALIDATED_ON_HELDOUT
    assert rg.readiness_gate("calibration", held, rg.Criteria())["maturity_allowed"] == mt.TRAINED_ON_PLANT_DATA, "validation criteria None: the top class is unreachable"
    for missing in ("heldout_data_independent", "error_metrics_per_quantity"):
        assert rg.readiness_gate("calibration", dataclasses.replace(held, **{missing: False}), CRIT)["maturity_allowed"] == mt.TRAINED_ON_PLANT_DATA, missing
    assert rg.readiness_gate("calibration", dataclasses.replace(held, heldout_error=0.2), CRIT)["maturity_allowed"] == mt.TRAINED_ON_PLANT_DATA
    assert rg.readiness_gate("calibration", dataclasses.replace(held, heldout_campaigns=1), CRIT)["maturity_allowed"] == mt.TRAINED_ON_PLANT_DATA
    assert rg.readiness_gate("calibration", dataclasses.replace(held, measured_pairs_count=0, synthetic_pairs_count=3), CRIT)["maturity_allowed"] == mt.SYNTHETIC_BENCHMARK, \
        "held-out figures without plant data do not raise the class"


def test_online_replacement_and_predictive_maintenance_passing_do_not_grant_the_top_class():
    ev = rg.Evidence(measured_pairs_count=5, failure_events_count=5, failure_events_defined=True, intervals_reported=True, calibrated_model_available=True, quality_gate_defined=True,
                     drift_monitoring_defined=True, fallback_defined=True)
    for cap in ("online_replacement", "predictive_maintenance"):
        r = rg.readiness_gate(cap, ev, CRIT)
        assert r["passes"] is True and r["maturity_allowed"] == mt.TRAINED_ON_PLANT_DATA, cap
    assert rg.readiness_gate("validation", ev, CRIT)["passes"] is False
    assert rg.readiness_gate("online_replacement", COMPLETE, rg.Criteria())["maturity_allowed"] == mt.TRAINED_ON_PLANT_DATA


def test_online_replacement_needs_a_calibrated_model_not_a_validated_one():
    ev = rg.Evidence(calibrated_model_available=True, quality_gate_defined=True, drift_monitoring_defined=True, fallback_defined=True)
    assert rg.readiness_gate("online_replacement", ev, rg.Criteria()) == {"passes": True, "reasons": [], "maturity_allowed": mt.PHYSICS_ESTIMATE}
    assert not any("validated" in x for x in rg.readiness_gate("online_replacement", rg.Evidence(), rg.Criteria())["reasons"])


# ------------------------------------------------------------------ physical_model_validated cannot be set on its own

def test_the_helper_sets_physical_model_validated_only_from_a_passing_validation_result():
    base = dataclasses.replace(COMPLETE, physical_model_validated=False)
    passing = rg.readiness_gate("validation", base, CRIT)
    assert passing["passes"] is True
    assert rg.evidence_with_validation_result(base, passing).physical_model_validated is True
    failing = rg.readiness_gate("validation", dataclasses.replace(base, heldout_error=0.5), CRIT)
    assert failing["passes"] is False
    assert rg.evidence_with_validation_result(base, failing).physical_model_validated is False
    assert rg.evidence_with_validation_result(COMPLETE, failing).physical_model_validated is False, "a hand-set True is reset by a failing result"
    for bad in (None, {}, {"passes": True, "reasons": ["x"], "maturity_allowed": "x"}, {"passes": False, "reasons": [], "maturity_allowed": "x"}):
        assert rg.evidence_with_validation_result(base, bad).physical_model_validated is False
    assert base.physical_model_validated is False, "the original evidence is not changed"


@pytest.mark.parametrize("cap", CAPS)
def test_a_hand_set_true_without_a_passing_validation_gate_is_an_inconsistency(cap):
    ev = dataclasses.replace(COMPLETE, heldout_error=0.5)                        # validation fails (error above the maximum) ...
    assert rg.readiness_gate("validation", ev, CRIT)["passes"] is False
    r = rg.readiness_gate(cap, ev, CRIT)                                          # ... but physical_model_validated is True in the evidence
    assert INCONSISTENT in r["reasons"] and r["passes"] is False
    ev0 = rg.Evidence(physical_model_validated=True)
    assert INCONSISTENT in rg.readiness_gate(cap, ev0, CRIT)["reasons"]


def test_a_true_that_comes_from_a_passing_validation_result_is_consistent_and_enables_virtual_sensing_and_optimisation():
    base = dataclasses.replace(COMPLETE, physical_model_validated=False)
    assert "missing evidence: physical_model_validated" in rg.readiness_gate("virtual_sensing", base, CRIT)["reasons"]
    ev = rg.evidence_with_validation_result(base, rg.readiness_gate("validation", base, CRIT))
    for cap in ("virtual_sensing", "optimisation"):
        assert rg.readiness_gate(cap, ev, CRIT)["passes"] is True, cap
    assert INCONSISTENT not in rg.readiness_gate("calibration", ev, CRIT)["reasons"]


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


def test_the_requirement_table_in_the_docs_is_the_generated_one():
    with open(os.path.join(ROOT, "docs", "maturity_and_readiness_gates.md"), encoding="utf-8") as fh:
        text = fh.read().replace("\r\n", "\n")
    a, b = text.index(rg.TABLE_START), text.index(rg.TABLE_END) + len(rg.TABLE_END)
    assert text[a:b] == rg.requirements_markdown(), "docs/maturity_and_readiness_gates.md is stale: regenerate the block between the REQUIRED markers from python/readiness_gate.requirements_markdown()"
    for cap in CAPS:
        assert f"`{cap}`" in text[a:b]
    assert text.count(rg.TABLE_START) == 1


# --- invalid held-out error values (A10 Gate 5 defect): NaN, infinities, negative values and non-numbers must never pass or grant the top class ------------------------------------------------

INVALID_ERRORS = [float("nan"), float("inf"), float("-inf"), -1.0, -1e-12, True, False, "0.05", [0.05]]


@pytest.mark.parametrize("bad", INVALID_ERRORS, ids=repr)
@pytest.mark.parametrize("cap", ("validation", "virtual_sensing"))
def test_an_invalid_heldout_error_fails_the_gate_and_names_the_item(cap, bad):
    r = rg.readiness_gate(cap, dataclasses.replace(COMPLETE, heldout_error=bad), CRIT)
    assert r["passes"] is False
    assert any(x.startswith("invalid evidence: heldout_error") for x in r["reasons"]), r["reasons"]
    assert "missing evidence: heldout_error" not in r["reasons"]


@pytest.mark.parametrize("bad", INVALID_ERRORS, ids=repr)
def test_an_invalid_heldout_error_never_grants_the_top_class(bad):
    for cap in CAPS:
        r = rg.readiness_gate(cap, dataclasses.replace(COMPLETE, heldout_error=bad), CRIT)
        assert r["maturity_allowed"] == mt.TRAINED_ON_PLANT_DATA, (cap, r)
    assert rg.maturity_allowed(dataclasses.replace(COMPLETE, heldout_error=bad), CRIT) != mt.VALIDATED_ON_HELDOUT
    assert rg.validation_passes(dataclasses.replace(COMPLETE, heldout_error=bad), CRIT) is False


@pytest.mark.parametrize("bad", INVALID_ERRORS, ids=repr)
def test_an_invalid_heldout_error_fails_even_when_the_criterion_is_none_with_both_reasons(bad):
    r = rg.readiness_gate("validation", dataclasses.replace(COMPLETE, heldout_error=bad), rg.Criteria(min_heldout_campaigns=2))
    assert r["passes"] is False and "criteria not set: max_heldout_error" in r["reasons"]
    assert any(x.startswith("invalid evidence: heldout_error") for x in r["reasons"])


def test_valid_finite_nonnegative_errors_keep_their_behaviour():
    for ok in (0, 0.0, 0.05, 0.1):                                                        # zero and exactly the limit pass, as before
        r = rg.readiness_gate("validation", dataclasses.replace(COMPLETE, heldout_error=ok), CRIT)
        assert r == {"passes": True, "reasons": [], "maturity_allowed": mt.VALIDATED_ON_HELDOUT}, ok
    r = rg.readiness_gate("validation", dataclasses.replace(COMPLETE, heldout_error=0.1001), CRIT)               # a valid failing value still fails, with the old reason
    assert r["passes"] is False and r["reasons"] == ["above criterion: heldout_error 0.1001 > max_heldout_error 0.1", INCONSISTENT]   # the claimed flag no longer has a passing validation behind it
    assert r["maturity_allowed"] == mt.TRAINED_ON_PLANT_DATA
    r = rg.readiness_gate("validation", dataclasses.replace(COMPLETE, heldout_error=None), CRIT)                 # None is still plain "missing"
    assert r["reasons"][0] == "missing evidence: heldout_error"


def test_a_hand_set_claim_cannot_be_rescued_by_an_invalid_error():
    r = rg.readiness_gate("optimisation", dataclasses.replace(COMPLETE, heldout_error=float("nan")), CRIT)
    assert r["passes"] is False and INCONSISTENT in r["reasons"]


# --- invalid operating-range coverage (P0-CLOSE C4): the same weakness as the held-out error, for a fraction that must lie in [0, 1] ---------------------------------------------------------

INVALID_COVERAGE = [float("nan"), float("inf"), float("-inf"), -0.1, -1e-12, 1.0000001, 2, 70, 10 ** 400, True, False, "0.8", [0.8]]     # 70 = a percentage given as a fraction; 10 ** 400 must not crash


@pytest.mark.parametrize("bad", INVALID_COVERAGE, ids=repr)
@pytest.mark.parametrize("cap", ("calibration", "virtual_sensing"))
def test_an_invalid_coverage_fails_the_gate_names_the_item_and_is_not_compared_with_the_threshold(cap, bad):
    r = rg.readiness_gate(cap, dataclasses.replace(COMPLETE, operating_range_coverage=bad), CRIT)
    assert r["passes"] is False
    assert any(x.startswith("invalid evidence: operating_range_coverage") and x.endswith("(must be a finite number in [0, 1])") for x in r["reasons"]), r["reasons"]
    assert "missing evidence: operating_range_coverage" not in r["reasons"]
    assert not any("criterion: operating_range_coverage" in x for x in r["reasons"]), "an invalid value is not compared with the threshold"


@pytest.mark.parametrize("bad", INVALID_COVERAGE, ids=repr)
@pytest.mark.parametrize("cap", ("calibration", "virtual_sensing"))
def test_an_invalid_coverage_also_reports_a_criterion_that_is_not_set(cap, bad):
    r = rg.readiness_gate(cap, dataclasses.replace(COMPLETE, operating_range_coverage=bad), dataclasses.replace(CRIT, min_operating_range_coverage=None))
    assert r["passes"] is False and "criteria not set: min_operating_range_coverage" in r["reasons"]
    assert any(x.startswith("invalid evidence: operating_range_coverage") for x in r["reasons"])


@pytest.mark.parametrize("bad", INVALID_COVERAGE, ids=repr)
def test_an_invalid_coverage_changes_nothing_in_a_gate_that_does_not_require_it(bad):
    ev = dataclasses.replace(COMPLETE, operating_range_coverage=bad)
    assert rg.readiness_gate("validation", ev, CRIT) == rg.readiness_gate("validation", COMPLETE, CRIT)           # validation does not require coverage: unchanged on purpose
    assert rg.maturity_allowed(ev, CRIT) == rg.maturity_allowed(COMPLETE, CRIT)


def test_valid_coverages_keep_their_behaviour():
    low = dataclasses.replace(CRIT, min_operating_range_coverage=0.4)
    for cap in ("calibration", "virtual_sensing"):
        for ok in (0.5, 0.7, 1, 1.0):                                                          # inside [0, 1]; the upper end is allowed
            r = rg.readiness_gate(cap, dataclasses.replace(COMPLETE, operating_range_coverage=ok), low)
            assert not any("operating_range_coverage" in x for x in r["reasons"]), (cap, ok, r["reasons"])
        r = rg.readiness_gate(cap, dataclasses.replace(COMPLETE, operating_range_coverage=0.5), CRIT)                  # valid but below the 0.7 criterion: the old reason
        assert r["passes"] is False and "below criterion: operating_range_coverage 0.5 < min_operating_range_coverage 0.7" in r["reasons"]
        r = rg.readiness_gate(cap, dataclasses.replace(COMPLETE, operating_range_coverage=0), low)                      # zero is a valid value (and below the criterion)
        assert "below criterion: operating_range_coverage 0 < min_operating_range_coverage 0.4" in r["reasons"]
    assert rg.readiness_gate("calibration", dataclasses.replace(COMPLETE, operating_range_coverage=0.5), low)["passes"] is True


def test_a_coverage_of_none_is_still_plain_missing():
    for cap in ("calibration", "virtual_sensing"):
        r = rg.readiness_gate(cap, dataclasses.replace(COMPLETE, operating_range_coverage=None), CRIT)
        assert "missing evidence: operating_range_coverage" in r["reasons"]
        assert not any(x.startswith("invalid evidence") for x in r["reasons"])
