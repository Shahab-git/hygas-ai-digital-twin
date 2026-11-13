"""DYN-1: the lag layer of python/dynamics.py changes the HOURLY published values very little (scripts/run_hourly_dynamics_impact.py). Offline."""
import importlib.util
import math
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "run_hourly_dynamics_impact.py")


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("run_hourly_dynamics_impact", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def feed(mod):
    return mod.impact(mod.SCENARIOS["feed -20 %"], hours=6)


@pytest.fixture(scope="module")
def er(mod):
    return mod.impact(mod.SCENARIOS["ER 0.25 -> 0.28"], hours=6)


def test_the_analytic_residuals_of_the_assumed_lags_after_one_hour(mod):
    r = mod.residual_after_one_step()
    assert r["tau_conv"] == pytest.approx(math.exp(-3.0), rel=1e-12)          # 1200 s: about 5 % still unrealised after an hour
    assert r["tau_gas"] == pytest.approx(math.exp(-120.0), rel=1e-12) and r["tau_gas"] < 1e-50
    assert r["T_gasifier"] == pytest.approx(math.exp(-30.0), rel=1e-12)
    assert 0.049 < r["tau_conv"] < 0.0499


def test_a_feed_step_is_changed_by_at_most_two_percent_and_only_in_the_first_cycles(feed):
    for col, v in feed.items():
        assert max(abs(x) for x in v) < 2.0                                     # measured 1.28 % (H2 production, gas flow)
    flow = feed["ga001_dry_flow_nm3_h"]
    assert max(abs(x) for x in flow) > 0.5                                      # the lag IS visible after a feed step (guards a no-op comparison)
    assert max(abs(x) for x in flow[:2]) < 1e-9                                 # nothing before the step
    assert all(abs(x) < 0.2 for x in flow[5:])                                  # settled again within the run


def test_an_er_step_is_not_changed_at_all_by_the_lags(er):
    for col, v in er.items():
        assert max(abs(x) for x in v) < 1e-6                                    # ER bypasses tau_conv and tau_gas has relaxed within an hour


def test_the_comparison_is_not_trivially_zero(feed, er):
    assert any(max(abs(x) for x in v) > 0.5 for v in feed.values()) and not any(max(abs(x) for x in v) > 0.5 for v in er.values())
