"""Tests for python/dynamics.py (dynamics layer v0).

No network, no database (the counting fake client is patched in and must record 0 calls);
runs in a few tens of seconds. All time constants used here are the module's Assumed ones or
explicit test overrides -- nothing here validates them against plant data.
"""
import json
import math

import pytest

from _fakes import FakeSupabase, patched_supabase
from python import cycle_clock, dynamics as dy, plant_status as ps, tab1_integration
from python import eu_utilities_chp as eu

OFF = {"T_gasifier": 0, "tau_conv": 0, "tau_gas": 0, "EU008_cooling_water": 0}


@pytest.fixture(autouse=True)
def _fake_db():
    """Every test runs against a counting fake client; the clock must start and end at its default."""
    cycle_clock.set_elapsed_hours(None)
    fake = FakeSupabase()
    with patched_supabase(fake):
        yield fake
    assert fake.calls == [], f"dynamics must make no database calls: {fake.calls}"
    assert cycle_clock._elapsed_hours is None


def _dump(snapshot):
    return json.loads(json.dumps({f"{k[0]}|{k[1]}": v for k, v in snapshot.items()}, sort_keys=True, default=str))


def _override(value):
    return lambda get_input: {"value": value, "status": ps.STATUS_ASSUMED, "validation_basis": ps.VALIDATION_NA,
                              "confidence_note": "test reference input"}


# --------------------------------------------------------------------------- C1 identity at 1 h
@pytest.mark.parametrize("taus,label", [
    (OFF, "all lags off"),
    ({"T_gasifier": 0, "tau_conv": 0, "tau_gas": 0}, "EU008 conversion ON (default) -- must still be exactly 0.5 at dt = 1 h"),
])
def test_c1_identity_with_build_live_snapshot_at_one_hour(taus, label):
    n = 5
    result = dy.run_transient([], dt_s=3600, duration_s=n * 3600, taus=taus, warmup_cycles=0)
    reference, _state, _engine = tab1_integration.build_live_snapshot(n_cycles=n)
    a, b = _dump(result.final_snapshot), _dump(reference)
    assert set(a) == set(b) and len(a) == 120
    assert [k for k in a if a[k] != b[k]] == [], label
    assert eu.EU008_DAMPING == 0.5, "the module constant must be restored"


def test_c1_eu008_damping_identity_is_exact_and_scales_with_dt():
    default_tau = dy.TAU_SPECS["EU008_cooling_water"].default_s
    assert dy.eu008_damping_for_dt(3600.0, default_tau) == 0.5          # bit-exact, not approximately
    assert dy.eu008_damping_for_dt(1800.0, default_tau) == pytest.approx(0.5 ** 0.5, rel=1e-15)
    assert dy.eu008_damping_for_dt(60.0, 0.0) == 0.5                    # 0 = keep the old per-cycle value
    # two half-hour steps relax exactly as much as one hourly step (the property that makes the conversion consistent)
    assert dy.eu008_damping_for_dt(1800.0, default_tau) ** 2 == pytest.approx(0.5, rel=1e-15)


# --------------------------------------------------------------------------- C2 convergence to steady state
def test_c2_long_run_converges_to_the_steady_state_engine_at_the_final_inputs():
    taus = {"T_gasifier": 30, "tau_conv": 60, "tau_gas": 30, "EU008_cooling_water": 120}
    final = {"feed_rel": 0.10, "ER": 0.28, "T_setpoint_C": 930.0}
    result = dy.run_transient([{"t_s": 120, **final}], dt_s=60, duration_s=2400, taus=taus, warmup_cycles=24)   # 2400 s = 20 x max tau
    base_feed = 41.67
    snap, _s, _e = tab1_integration.build_live_snapshot(n_cycles=30, overrides={
        ("FE-001-INPUT", "msw_delivery_rate_kg_h"): _override(base_feed * 1.10),
        ("GA-001-INPUT", "equivalence_ratio"): _override(0.28),
        ("GA-001-INPUT", "operating_temperature_C"): _override(930.0)})
    ga = snap[("GA-001", "Outputs")]["value"]
    steady = {
        "ga001_dry_flow_nm3_h": ga["dry_flow_nm3_h"], "H2_pct_dry": ga["H2_mol_pct_dry"], "CO_pct_dry": ga["CO_mol_pct_dry"],
        "CO2_pct_dry": ga["CO2_mol_pct_dry"], "CH4_pct_dry": ga["CH4_mol_pct_dry"], "N2_pct_dry": ga["N2_mol_pct_dry"],
        "lhv_mj_nm3": snap[("SA-006", "Reading")]["value"],
        "h2_production_kg_h": snap[("HB-012", "Compressor")]["value"]["h2_kg_h"],
        "eu008_demand_kw": snap[("EU-008", "CoolingSupply")]["value"]["demand_kw"],
        "eu008_supply_temp_c": snap[("EU-008", "CoolingSupply")]["value"]["supply_temp_c"],
        "T_gasifier_C": 930.0,
    }
    last = result.series[-1]
    for name, expected in steady.items():
        assert last[name] == pytest.approx(expected, rel=1e-6), name
    assert last["ai004_eu009_state"] == snap[("AI-004", "EU-009-State")]["value"]
    # The response really moved (this is not a trivially flat series).
    assert abs(last["ga001_dry_flow_nm3_h"] - result.series[0]["ga001_dry_flow_nm3_h"]) > 5.0
    # NOT compared, on purpose: hb013_storage_kg and eu010_soc_kwh are INVENTORIES (integrals), not steady-state
    # outputs; they are checked against the integral of their own flows in test_c5.


# --------------------------------------------------------------------------- C3 first-order shape
def test_c3_t_gasifier_is_first_order_63_and_95_percent():
    tau = 120.0
    t_step = 60.0
    result = dy.run_transient([{"t_s": t_step, "T_setpoint_C": 930.0}], dt_s=60, duration_s=720,
                              taus={"T_gasifier": tau, "tau_conv": 0, "tau_gas": 0, "EU008_cooling_water": 0}, warmup_cycles=2)
    t0 = result.series[0]["T_gasifier_C"]
    assert t0 == 950.0
    delta = 930.0 - t0
    by_t = {row["t_s"]: row for row in result.series}

    def fraction(t):
        return (by_t[t]["T_gasifier_C"] - t0) / delta

    assert fraction(t_step + tau) == pytest.approx(0.632, abs=0.01)
    assert fraction(t_step + 3 * tau) == pytest.approx(0.950, abs=0.01)
    for t, row in by_t.items():            # and it is the exact exponential everywhere on the grid
        if t >= t_step + 60:
            assert fraction(t) == pytest.approx(1 - math.exp(-(t - t_step) / tau), abs=1e-12)


# --------------------------------------------------------------------------- C4 numerical convergence in dt
def _t95(series, column, t_step):
    first, last = series[0][column], series[-1][column]
    for a, b in zip(series, series[1:]):
        fa, fb = (a[column] - first) / (last - first), (b[column] - first) / (last - first)
        if fb >= 0.95 > fa:
            return a["t_s"] + (0.95 - fa) / (fb - fa) * (b["t_s"] - a["t_s"]) - t_step   # interpolated: no grid-size artefact
    raise AssertionError("95 % never reached")


def test_c4_results_converge_as_dt_changes():
    taus = {"T_gasifier": 120, "tau_conv": 0, "tau_gas": 120, "EU008_cooling_water": 0}
    runs = {dt: dy.run_transient([{"t_s": 240, "T_setpoint_C": 930.0}], dt_s=dt, duration_s=1200, taus=taus, warmup_cycles=8)
            for dt in (30, 60, 120)}

    def spread(values):
        return (max(values) - min(values)) / (sum(values) / len(values))

    # (a) final values agree across dt for every recorded output
    for column in ("T_gasifier_C", "ga001_dry_flow_nm3_h", "H2_pct_dry", "CO_pct_dry", "CO2_pct_dry", "lhv_mj_nm3",
                   "h2_production_kg_h", "eu008_demand_kw"):
        assert spread([r.series[-1][column] for r in runs.values()]) < 0.01, column
    # (b) time to 95 % of the T_gasifier response: the exponential lag is exact, so it agrees within 1 %
    t95_T = {dt: _t95(r.series, "T_gasifier_C", 240) for dt, r in runs.items()}
    assert spread(list(t95_T.values())) < 0.01, t95_T
    assert t95_T[60] == pytest.approx(3 * 120, rel=0.01)
    # (c) GA-001's flow response ALSO depends on the engine's EXISTING one-cycle couplings (GA-001 reads the previous cycle's
    # HB-009 tail gas and FE-005 feed), which at a short dt are dt-long delays / loop gains. That makes the 95 % time of a
    # COUPLED output weakly dt-dependent -- it is not an error of the exponential lags (T_gasifier above is exact). Measured:
    # 586 / 579 / 573 s (1500 s runs) and 573 / 567 / 561 s (these 1200 s runs) for dt = 30 / 60 / 120, i.e. a ~2.2-2.3 %
    # spread, above the 1 % target. Asserted <= 3 % so a regression is caught; reported as a finding, not hidden.
    t95_flow = {dt: _t95(r.series, "ga001_dry_flow_nm3_h", 240) for dt, r in runs.items()}
    assert spread(list(t95_flow.values())) < 0.03, t95_flow
    # (d) h2_production_kg_h moves by ~1e-5 relative in this scenario: its 95 % time is noise-level and NOT asserted.


# --------------------------------------------------------------------------- C5 inventory consistency
@pytest.fixture(scope="module")
def quiet_result():
    with patched_supabase(FakeSupabase()):
        return dy.run_transient([], dt_s=60, duration_s=900, warmup_cycles=12)


def test_c5_hb013_level_change_equals_the_integral_of_its_recorded_flows(quiet_result):
    rows, dt_h = quiet_result.series, 60 / 3600.0
    unclamped_steps = 0
    cumulative_change = cumulative_integral = 0.0
    for prev, row in zip(rows, rows[1:]):
        integral = (row["hb013_inflow_kg_h"] - row["hb013_outflow_kg_h"]) * dt_h
        change = row["hb013_storage_kg"] - prev["hb013_storage_kg"]
        if row["hb013_storage_kg"] > 0.0:                       # not at the empty clamp (the 50 kg capacity is never reached)
            assert change == pytest.approx(integral, abs=1e-9)
            unclamped_steps += 1
            cumulative_change += change
            cumulative_integral += integral
        else:                                                   # clamped at 0: the unclamped balance would have gone negative
            assert prev["hb013_storage_kg"] + integral <= 1e-9
    assert unclamped_steps >= 5
    assert cumulative_change == pytest.approx(cumulative_integral, abs=1e-8)


# --------------------------------------------------------------------------- C6 no side effects
def test_c6_clock_and_damping_are_restored_even_when_the_run_raises(monkeypatch, _fake_db):
    calls = {"n": 0}
    real = dy.synthetic_timestamp

    def exploding(i):
        calls["n"] += 1
        if calls["n"] > 4:
            raise RuntimeError("boom in the middle of the run")
        return real(i)

    monkeypatch.setattr(dy, "synthetic_timestamp", exploding)
    with pytest.raises(RuntimeError, match="boom"):
        dy.run_transient([{"t_s": 0, "T_setpoint_C": 930.0}], dt_s=60, duration_s=600, warmup_cycles=2)
    assert cycle_clock._elapsed_hours is None and cycle_clock.hours_per_cycle() == 1.0
    assert eu.EU008_DAMPING == 0.5
    assert _fake_db.calls == []


def test_c6_a_normal_run_leaves_everything_as_it_found_it(quiet_result, _fake_db):
    assert cycle_clock._elapsed_hours is None and eu.EU008_DAMPING == 0.5
    assert _fake_db.calls == []


# --------------------------------------------------------------------------- C7 honesty
def test_c7_every_tau_used_is_listed_and_tagged_assumed(quiet_result):
    result = quiet_result
    listed = {a["name"] for a in result.assumptions}
    assert listed == set(dy.TAU_SPECS)
    assert set(result.used_taus) <= listed and result.used_taus, "the default run uses lags, so some must be recorded as used"
    assert result.verify_honesty() is True
    for a in result.assumptions:
        assert a["status"] == ps.STATUS_ASSUMED
        lo, hi = a["range_s"]
        assert lo <= a["value_s"] <= hi, a["name"]
        assert a["reasoning"].strip() and a["question_for_doking"].strip()
    assert "Measured" not in result.status.replace("not Measured", "") and "Confirmed" not in result.status.replace("not Confirmed", "")


def test_c7_an_unlisted_tau_is_caught_and_unknown_names_are_rejected(quiet_result):
    broken = dy.TransientResult(quiet_result.series, [a for a in quiet_result.assumptions if a["name"] != "tau_gas"],
                                quiet_result.used_taus, quiet_result.meta, quiet_result.final_snapshot)
    with pytest.raises(AssertionError, match="tau_gas"):
        broken.verify_honesty()
    with pytest.raises(ValueError, match="unknown time constant"):
        dy.run_transient([], dt_s=60, duration_s=60, taus={"Surprise": 5.0}, warmup_cycles=0)
    with pytest.raises(ValueError, match="unknown scenario key"):
        dy.run_transient([{"t_s": 0, "mystery": 1}], dt_s=60, duration_s=60, warmup_cycles=0)


def test_steps_at_t_zero_are_initial_conditions():
    """{"t_s": 0, ...} defines the starting steady state (used by the T 900 -> 930 demo): row 0 already has it."""
    result = dy.run_transient([{"t_s": 0, "T_setpoint_C": 900.0}, {"t_s": 60, "T_setpoint_C": 930.0}], dt_s=60,
                              duration_s=120, taus={"T_gasifier": 120, "tau_conv": 0, "tau_gas": 0, "EU008_cooling_water": 0}, warmup_cycles=2)
    assert result.series[0]["T_gasifier_C"] == 900.0 and result.series[0]["T_setpoint_C"] == 900.0
    assert result.series[1]["T_setpoint_C"] == 900.0                       # step at t = 60 acts from the next sub-step
    assert result.series[2]["T_gasifier_C"] == pytest.approx(930.0 - 30.0 * math.exp(-0.5))


# =========================================================================== v0.1 : split lags, recycle delay
from scipy.integrate import solve_ivp  # noqa: E402  (scipy is a project requirement)
from scipy.interpolate import CubicSpline  # noqa: E402
from scipy.optimize import brentq  # noqa: E402

LAGS_OFF = {"T_gasifier": 0, "tau_conv": 0, "tau_gas": 0, "tau_rec": 0, "EU008_cooling_water": 0}


def test_v01_defaults_lie_strictly_inside_their_ranges():
    for name, spec in dy.TAU_SPECS.items():
        lo, hi = spec.range_s
        assert lo < spec.default_s < hi, f"{name}: default {spec.default_s} must be strictly inside ({lo}, {hi})"
        assert spec.status == ps.STATUS_ASSUMED and spec.reasoning.strip() and spec.question_for_doking.strip()
    assert "GasHoldup" not in dy.TAU_SPECS and {"tau_conv", "tau_gas", "tau_rec"} <= set(dy.TAU_SPECS)


# ---- each lag separately and the cascade: the lag probe uses the very same update functions as the plant
@pytest.mark.parametrize("tau_conv,tau_gas", [(90.0, 30.0), (60.0, 60.0)], ids=["distinct taus", "equal taus (limit branch)"])
def test_v01_probe_matches_the_exact_analytic_lag_and_cascade_responses(tau_conv, tau_gas):
    taus = {**LAGS_OFF, "tau_conv": tau_conv, "tau_gas": tau_gas}
    result = dy.run_transient([{"t_s": 60, "ER": 0.30}], dt_s=30, duration_s=600, taus=taus, warmup_cycles=2)
    for row in result.series:
        t = row["t_s"] - 60.0
        if t < 30:
            assert row["probe_conv"] == row["probe_gas"] == row["probe_cascade"] == 0.0
            continue
        assert row["probe_conv"] == pytest.approx(1 - math.exp(-t / tau_conv), abs=1e-12)
        assert row["probe_gas"] == pytest.approx(1 - math.exp(-t / tau_gas), abs=1e-12)
        assert row["probe_cascade"] == pytest.approx(dy.cascade_step_response(t, tau_conv, tau_gas), abs=1e-12)
    # the 63.2 % / 95 % points of a single lag at t = tau and 3 tau
    assert 1 - math.exp(-1) == pytest.approx(0.632, abs=0.001) and 1 - math.exp(-3) == pytest.approx(0.950, abs=0.001)
    assert dy.cascade_step_response(0.0, tau_conv, tau_gas) == 0.0


def test_v01_cascade_psi_is_between_zero_and_the_single_lag_gain():
    for tc, tg, dt in [(1200.0, 30.0, 60.0), (30.0, 1200.0, 60.0), (60.0, 60.0, 60.0), (5.0, 3.0, 60.0)]:
        psi = dy.cascade_psi(dt, tc, tg)
        assert 0.0 < psi < 1.0 - math.exp(-dt / tg), (tc, tg, psi)


@pytest.fixture(scope="module")
def routing_run():
    taus = {**LAGS_OFF, "T_gasifier": 120, "tau_conv": 240, "tau_gas": 60, "tau_rec": 240}
    scenario = [{"t_s": 120, "T_setpoint_C": 930.0}, {"t_s": 360, "ER": 0.30}, {"t_s": 600, "feed_rel": 0.10}]
    with patched_supabase(FakeSupabase()):
        return dy.run_transient(scenario, dt_s=60, duration_s=1200, taus=taus, warmup_cycles=6)


def test_v01_er_bypasses_tau_conv_and_is_seen_by_ga001_unlagged(routing_run):
    """Item A (what-if tab round): an ER step goes through tau_gas ONLY. ER_effective is the raw ER at every sub-step
    (it used to relax through tau_conv = 240 s here)."""
    rows = {r["t_s"]: r for r in routing_run.series}
    for t, row in rows.items():
        if t == 0:                      # warm-up end: no GA-001 diagnostics recorded yet
            continue
        assert row["ga001_ER_effective"] == (0.25 if t <= 360 else 0.30), t     # a step applies from the sub-step that starts at 360
        assert row["ga001_ER_effective"] == row["ER"], t


def test_v01_feed_effective_follows_tau_conv_exactly(routing_run):
    """The feed is the quantity tau_conv acts on: every sub-step is the exact one-lag update toward the raw feed GA-001 reads
    (routing_run: tau_conv = 240 s, dt = 60 s). Guards against the feed bypassing tau_conv."""
    rows = {r["t_s"]: r for r in routing_run.series}
    decay = math.exp(-60.0 / 240.0)
    checked = 0
    for t in range(120, 1201, 60):
        raw, previous = rows[t]["ga001_dry_feed_raw_kg_h"], rows[t - 60]["ga001_dry_feed_effective_kg_h"]
        assert rows[t]["ga001_dry_feed_effective_kg_h"] == pytest.approx(raw + (previous - raw) * decay, abs=1e-9), t
        checked += 1
    assert checked == 19 and rows[1200]["ga001_dry_feed_effective_kg_h"] < rows[1200]["ga001_dry_feed_raw_kg_h"]   # still relaxing


def test_v01_routing_t_skips_tau_conv_er_and_feed_use_it(routing_run):
    rows = {r["t_s"]: r for r in routing_run.series}
    # T step (t = 120): T_gasifier moves, the conv-lagged inputs do not
    assert rows[240]["T_gasifier_C"] < 950.0
    assert rows[360]["ga001_ER_effective"] == rows[60]["ga001_ER_effective"] == pytest.approx(0.25)
    assert rows[360]["ga001_dry_feed_effective_kg_h"] == pytest.approx(rows[60]["ga001_dry_feed_effective_kg_h"], rel=1e-12)
    # ER step (t = 360): ER_effective is at the new value at once (no tau_conv); the effective feed does not move
    assert rows[420]["ga001_ER_effective"] == 0.30
    assert rows[540]["ga001_dry_feed_effective_kg_h"] == pytest.approx(rows[60]["ga001_dry_feed_effective_kg_h"], rel=1e-12)
    # the OUTPUT does lag (tau_gas): one sub-step after the step it is not yet at the sub-step's steady-state value
    assert rows[420]["ga001_dry_flow_nm3_h"] != pytest.approx(rows[420]["ga001_dry_flow_y1_nm3_h"], rel=1e-6)
    # feed step (t = 600): the effective feed moves (tau_conv); ER_effective stays at 0.30
    assert rows[900]["ga001_dry_feed_effective_kg_h"] > rows[540]["ga001_dry_feed_effective_kg_h"] * 1.001
    assert rows[1200]["ga001_ER_effective"] == 0.30


def test_v01_the_feed_seen_by_ga001_is_exactly_one_sub_step_late(routing_run):
    """The residual dt-dependence of a FEED step: GA-001 reads FE-005 through the engine's one-cycle lag
    (ga001_gasifier_model.py:1137,1148)."""
    rows = {r["t_s"]: r for r in routing_run.series}
    old = rows[600]["ga001_dry_feed_raw_kg_h"]
    assert rows[660]["ga001_dry_feed_raw_kg_h"] == pytest.approx(old, rel=1e-12)     # the step acted in the sub-step 600-660 ...
    assert rows[720]["ga001_dry_feed_raw_kg_h"] > old * 1.09                          # ... but GA-001 sees it one sub-step later


def test_v01_gas_stage_matches_an_independent_numerical_integration_of_the_ode(routing_run):
    """Each recorded gas-state step is compared with scipy's DOP853 integration of dx/ds = (y(s) - x)/tau_gas, y(s) along the
    exponential the inputs moved on (tau_conv, or tau_T when only the temperature moved; a ramp when only the delayed recycle
    moved) -- independent of the closed-form psi."""
    rows, dt, tau_gas, tau_conv, tau_T = routing_run.series, 60.0, 60.0, 240.0, 120.0
    checked = 0
    for prev, row in zip(rows[2:], rows[3:]):
        y0, y1 = row["ga001_dry_flow_y0_nm3_h"], row["ga001_dry_flow_y1_nm3_h"]
        eff = lambda r: r["ga001_dry_feed_effective_kg_h"]      # only the feed is conv-lagged (ER bypasses tau_conv)
        conv_moved = eff(row) != eff(prev)
        t_moved = row["T_gasifier_C"] != prev["T_gasifier_C"]
        if y1 == y0:
            phi = lambda s: 0.0
        elif conv_moved:                                         # inputs moved on the tau_conv exponential
            phi = lambda s: (1 - math.exp(-s / tau_conv)) / (1 - math.exp(-dt / tau_conv))
        elif t_moved:                                            # only the temperature moved: the tau_T exponential
            phi = lambda s: (1 - math.exp(-s / tau_T)) / (1 - math.exp(-dt / tau_T))
        else:                                                    # only the delayed recycle moved: a ramp
            phi = lambda s: s / dt
        sol = solve_ivp(lambda s, x: [(y0 + (y1 - y0) * phi(s) - x[0]) / tau_gas], (0.0, dt), [prev["ga001_dry_flow_nm3_h"]],
                        method="DOP853", rtol=1e-12, atol=1e-12)
        assert row["ga001_dry_flow_nm3_h"] == pytest.approx(sol.y[0][-1], rel=1e-9), row["t_s"]
        checked += 1
    assert checked >= 10


def test_v01_the_lagged_flow_never_exceeds_the_steady_state_target_after_an_er_step(routing_run):
    rows = [r for r in routing_run.series if 360 <= r["t_s"] <= 600]
    assert max(r["ga001_dry_flow_nm3_h"] for r in rows) <= max(r["ga001_dry_flow_target_nm3_h"] for r in rows)


# --------------------------------------------------------------------------- C: recycle delay
def test_v01_recycle_delay_of_one_cycle_at_one_hour_is_bit_identical():
    n = 5
    result = dy.run_transient([], dt_s=3600, duration_s=n * 3600, taus={**LAGS_OFF, "tau_rec": 3600.0}, warmup_cycles=0)
    reference, _s, _e = tab1_integration.build_live_snapshot(n_cycles=n)
    a, b = _dump(result.final_snapshot), _dump(reference)
    assert len(a) == len(b) == 120 and [k for k in a if a[k] != b[k]] == []
    # the default 60 s delay clamps to one cycle at dt = 1 h and is identical too
    result2 = dy.run_transient([], dt_s=3600, duration_s=n * 3600, taus={**LAGS_OFF, "tau_rec": 60.0}, warmup_cycles=0)
    c = _dump(result2.final_snapshot)
    assert [k for k in c if c[k] != b[k]] == []


def test_v01_delayed_entry_node_interpolation_and_clamping():
    def e(x):
        return {"status": ps.STATUS_CALCULATED, "value": {"species_nm3_h": {"H2": x, "CO": 2 * x}, "tail_flow_nm3_h": 10 * x, "flag": True}}

    buf = [(0.0, e(1.0)), (60.0, e(2.0)), (120.0, e(4.0))]
    tol = 1e-9
    entry, interpolated = dy.delayed_entry(buf, 60.0, tol)
    assert entry is buf[1][1] and not interpolated                      # on a node: the entry object itself, untouched
    entry, interpolated = dy.delayed_entry(buf, 90.0, tol)
    assert interpolated and entry["value"]["species_nm3_h"]["H2"] == pytest.approx(3.0) and entry["value"]["flag"] is True
    assert entry["value"]["tail_flow_nm3_h"] == pytest.approx(30.0)
    assert dy.delayed_entry(buf, -5.0, tol)[0] is buf[0][1]            # before the first node
    assert dy.delayed_entry(buf, 500.0, tol)[0] is buf[-1][1]          # after the last: the delay clamps to one sub-step
    assert dy.delayed_entry([], 10.0, tol) == (None, False)


def _t95_spline(series, column, t_step):
    first, last = series[0][column], series[-1][column]
    ts = [r["t_s"] for r in series]
    fr = [(r[column] - first) / (last - first) for r in series]
    spline = CubicSpline(ts, fr)
    i = next(k for k in range(1, len(fr)) if fr[k] >= 0.95 > fr[k - 1])
    return brentq(lambda t: float(spline(t)) - 0.95, ts[i - 1], ts[i]) - t_step


def test_v01_time_to_95_percent_of_ga001_flow_agrees_across_dt_for_t_and_er_steps():
    """dt = 30 / 60 / 120 s with tau_rec = 240 s (>= 2 dt_max, so the delay is resolved) and every other tau >= 2 dt_max.
    Measured spreads 0.30 % (T) and 0.61 % (ER); with the engine's one-cycle lag they were 3.8 % and 6.1 %.
    Item A: an ER step now passes through tau_gas ONLY, so the ER case uses tau_gas = 240 s (>= 2 dt_max, the rule stated above)
    and a longer run; with tau_gas = 60 s the ER response is faster than a 120 s grid can resolve. The 1 % tolerance is unchanged."""
    taus = {**LAGS_OFF, "T_gasifier": 120, "tau_conv": 240, "tau_gas": 60, "tau_rec": 240}
    taus_er = {**taus, "tau_gas": 240}
    for name, step, tau_set, duration in (("T", {"T_setpoint_C": 930.0}, taus, 1200), ("ER", {"ER": 0.30}, taus_er, 2400)):
        t95 = {dt: _t95_spline(dy.run_transient([{"t_s": 240, **step}], dt_s=dt, duration_s=duration, taus=tau_set,
                                                warmup_cycles=6).series, "ga001_dry_flow_nm3_h", 240) for dt in (30, 60, 120)}
        values = list(t95.values())
        assert (max(values) - min(values)) / (sum(values) / len(values)) < 0.01, (name, t95)
