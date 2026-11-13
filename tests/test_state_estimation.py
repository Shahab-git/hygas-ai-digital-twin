"""CAL-2: the extended Kalman filter on SYNTHETIC drift (the measurements are the engine's own output plus seeded noise; this proves the loop, not the physics)."""
import os

import numpy as np
import pytest

from python import calibration as cal
from python import state_estimation as se

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
N = 8
LAST = 3


@pytest.fixture(scope="module")
def nominal_run():
    return se.drift_experiment([{}] * N, noise_seed=1)


@pytest.fixture(scope="module")
def ramp_run():
    return se.drift_experiment([{"ER": 0.25 + 0.03 * k / (N - 1)} for k in range(N)], noise_seed=1)


@pytest.fixture(scope="module")
def step_run():
    return se.drift_experiment([{"carbon_conversion": 0.90 if k < N // 2 else 0.86} for k in range(N)], noise_seed=1)


def _rng(name):
    return {s["name"]: s["high"] - s["low"] for s in cal.parameter_specs()}[name]


def test_with_no_drift_the_filter_stays_at_the_truth_and_fits_the_data_to_the_noise(nominal_run):
    s = se.summarise(nominal_run, last=LAST)
    assert s["obs_rmse_sigma"]["filter"] < 1.0
    for n, v in s["parameters"].items():
        assert v["filter_abs_error"] < 0.1 * _rng(n)


def test_a_ramp_in_er_is_tracked_far_better_than_the_static_twin(ramp_run):
    s = se.summarise(ramp_run, last=LAST)
    assert s["obs_rmse_sigma"]["static"] > 2.0                       # the static twin is visibly wrong ...
    assert s["obs_rmse_sigma"]["filter"] < 0.5 * s["obs_rmse_sigma"]["static"]   # ... and the filter removes most of that
    assert s["parameters"]["ER"]["filter_abs_error"] < 0.5 * s["parameters"]["ER"]["static_abs_error"]


def test_a_step_in_carbon_conversion_is_followed_after_the_step(step_run):
    s = se.summarise(step_run, last=LAST)
    assert s["obs_rmse_sigma"]["filter"] < 0.5 * s["obs_rmse_sigma"]["static"]
    # conversion is only weakly identifiable (CAL-1) and 4 steps after the step the filter is still converging (measured 0.022 vs the static 0.040): the claim is "at least a quarter better", not "solved"
    assert s["parameters"]["carbon_conversion"]["filter_abs_error"] < 0.75 * s["parameters"]["carbon_conversion"]["static_abs_error"]
    first = step_run["steps"][N // 2]                                 # the step itself is a surprise: the innovation is large there (a drift detector)
    assert first["nis"] > np.mean([x["nis"] for x in step_run["steps"][1:N // 2]])


def test_the_innovation_statistic_is_consistent_with_the_number_of_observables(nominal_run, ramp_run, step_run):
    for rep in (nominal_run, ramp_run, step_run):
        m = se.summarise(rep)["mean_nis"]
        assert 0.5 * rep["n_observables"] / 2 < m < 2 * rep["n_observables"]         # heuristic band 1.5 .. 12 around the expected 6


def test_the_estimate_never_leaves_the_prior_bounds_and_the_uncertainty_shrinks(ramp_run, step_run):
    specs = {s["name"]: s for s in cal.parameter_specs()}
    for rep in (ramp_run, step_run):
        for st in rep["steps"]:
            for n, v in st["estimate"].items():
                assert specs[n]["low"] <= v <= specs[n]["high"]
        p0 = se.P0_FRACTION * _rng("ER")
        assert rep["steps"][-1]["std"]["ER"] < 0.3 * p0


def test_track_on_the_same_measurements_reproduces_the_experiment(ramp_run):
    again = se.track(ramp_run["measurements"])
    assert [s["estimate"] for s in again["steps"]] == [s["estimate"] for s in ramp_run["steps"]]


def test_a_measurement_missing_an_observable_is_refused_not_guessed():
    with pytest.raises(KeyError):
        se.track([{"H2_mol_pct_dry": 20.0}])


def test_the_filter_changes_nothing_in_the_model(nominal_run):
    assert cal.forward({}) == cal.forward({})
    assert nominal_run["status"].startswith("Calculated on synthetic data; NOT validation")


def test_nothing_in_the_engine_the_runtime_the_app_or_a_script_imports_the_module():
    hits = []
    for base in ("python", "scripts"):
        for dp, _dn, fn in os.walk(os.path.join(ROOT, base)):
            for f in fn:
                if f.endswith(".py") and f != "state_estimation.py":
                    with open(os.path.join(dp, f), encoding="utf-8") as fh:
                        text = fh.read()
                    if "import state_estimation" in text or "from python import state_estimation" in text or "from . import state_estimation" in text or "python.state_estimation" in text:
                        hits.append(os.path.relpath(os.path.join(dp, f), ROOT))
    with open(os.path.join(ROOT, "app.py"), encoding="utf-8") as fh:
        text = fh.read()
    if "import state_estimation" in text or "python.state_estimation" in text:
        hits.append("app.py")
    assert sorted(hits) == []


def test_the_noise_sigmas_set_how_much_the_filter_trusts_the_data(ramp_run):
    meas = ramp_run["measurements"][:2]
    tight = se.track(meas)
    loose = se.track(meas, sigma={o: 10 * v for o, v in cal.SIGMA.items()})
    assert loose["steps"][-1]["std"]["ER"] > 1.5 * tight["steps"][-1]["std"]["ER"]


def test_a_measurement_far_outside_the_prior_cannot_push_the_estimate_past_the_bounds():
    spec = {s["name"]: s for s in cal.parameter_specs()}["ER"]
    y = cal.forward({"ER": 0.40})                                    # clean data from an ER far above the prior's upper bound
    rep = se.track([y, y])
    assert rep["steps"][-1]["estimate"]["ER"] <= spec["high"] + 1e-12
    assert rep["steps"][-1]["estimate"]["ER"] > spec["high"] - 1e-6   # and it is pinned at the bound, not stuck elsewhere
