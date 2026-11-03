"""Synthetic benchmark of predictive_maintenance (task A10): reproducible by seed, finite, exact at zero noise. It measures the code, not any plant."""
import importlib.util
import math
import os

import numpy as np
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ACTS = tuple(np.linspace(1.0, 0.6, 3))          # a short trajectory keeps the test fast
LEVELS = (0.0, 0.01)
SEEDS = (0, 1)


@pytest.fixture(scope="module")
def sb():
    spec = importlib.util.spec_from_file_location("run_synthetic_benchmark", os.path.join(ROOT, "scripts", "run_synthetic_benchmark.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def result(sb):
    return sb.run_benchmark(ACTS, LEVELS, SEEDS)


def test_the_benchmark_is_reproducible_by_seed(sb, result):
    again = sb.run_benchmark(ACTS, LEVELS, SEEDS)
    assert again["rows"] == result["rows"] and again["summary"] == result["summary"]
    other = sb.run_benchmark(ACTS, (0.01,), (7,))
    assert other["rows"][0]["mae"] != [r for r in result["rows"] if r["noise_sigma"] == 0.01][0]["mae"]          # a different seed draws different noise


def test_every_recovery_error_is_finite_and_nothing_is_unreachable_at_these_levels(result):
    for r in result["rows"]:
        assert all(math.isfinite(r[k]) for k in ("mae", "bias", "max_abs_error")) and r["n_unreachable"] == 0 and r["n_steps"] == len(ACTS)
    assert all(math.isfinite(s[k]) for s in result["summary"] for k in ("mae_mean", "mae_sd_over_seeds", "bias_mean"))


def test_zero_noise_recovers_the_true_activity_within_numerical_tolerance(result):
    zero = [r for r in result["rows"] if r["noise_sigma"] == 0.0]
    assert zero and all(r["max_abs_error"] < 1e-6 and abs(r["bias"]) < 1e-6 for r in zero)


def test_the_error_grows_with_the_noise_level(result):
    by = {s["noise_sigma"]: s["mae_mean"] for s in result["summary"]}
    assert by[0.01] > 1e-3 > by[0.0]


def test_the_report_says_it_measures_the_code_and_lists_the_modules_without_a_benchmark(sb, result):
    text = sb.render(result)
    assert "This measures the code, not any plant." in text and "not instrument specifications" in text
    assert "Inverse crime" in text and "guaranteed by construction" in text and "model-form error, instrument bias or any plant" in text
    assert "Inverse crime" in open(os.path.join(ROOT, "docs", "maturity_and_readiness_gates.md"), encoding="utf-8").read()
    assert "INVERSE CRIME" in sb.__doc__ and "TEST INPUTS, NOT instrument" in sb.__doc__
    from python import maturity as mt
    assert set(sb.NO_BENCHMARK) == set(mt.MATURITY) - {"predictive_maintenance"} and all(sb.NO_BENCHMARK.values())
    assert all(f"| {m} |" in text for m in sb.NO_BENCHMARK)
