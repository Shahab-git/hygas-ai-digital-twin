"""Tests of the "Transient What-If" tab (Tab 11): python/ui_transient_tab.py + python/ui_transient_sim.py.

The tab is rendered ALONE through Streamlit's AppTest (a three-line script), so every database / network count below belongs to the
new code path and to nothing else. The full app (header, Tab 2 sum of 91, 11 tabs) is covered by tests/test_app_smoke.py.

Offline: the Supabase client is the counting fake (tests/_fakes.py), urlopen and socket connections are counted and refused.
Real simulations run in the tab's child process (that is the production path); each costs a few seconds, so the scenario runs are
done once, in one module-scoped fixture, and shared between the tests.
"""
import contextlib
import html
import ipaddress
import json
import math
import os
import socket
import subprocess
import time
import urllib.request
from unittest import mock

import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from _fakes import FakeSupabase, patched_supabase
from python import cycle_clock, dynamics as dy, ui_transient_charts as ch, ui_transient_sim as sim
from python import ui_transient_tab as tab
from python import eu_utilities_chp as eu

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = f"import sys\nsys.path.insert(0, {ROOT!r})\nfrom python import ui_transient_tab\nui_transient_tab.render()\n"


@pytest.fixture(autouse=True, scope="module")
def _clean_streamlit_main_dg():
    """tests/test_tab2_counts.py runs the whole app.py in bare mode (no runtime); there Streamlit records the last st.form
    (confirm_form_psa_target_calibration) on the process-wide main DeltaGenerator and never clears it, so any later AppTest button
    fails with "st.button() can't be used in an st.form()". Clear it for this module and put the previous value back afterwards."""
    from streamlit import delta_generator_singletons as singletons

    main_dg = singletons.get_dg_singleton_instance().main_dg
    previous = main_dg._form_data
    main_dg._form_data = None
    yield
    main_dg._form_data = previous


class _Counters:
    def __init__(self):
        self.urlopen = []
        self.sockets = []


def _is_loopback(address):
    """True for an address that stays on this machine: a loopback IP (127.0.0.0/8, ::1), "localhost", or an AF_UNIX path. A hostname is NOT
    loopback (reaching it would need DNS), so it is refused."""
    if isinstance(address, (str, bytes)):
        return True                                           # AF_UNIX path
    host = address[0]
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@contextlib.contextmanager
def _refuse_external_sockets(counters):
    """Zero-network guard: any connect / connect_ex to a NON-loopback address raises (and is counted) before a packet is sent. Loopback is
    allowed because asyncio builds its internal event-loop socket pair by connecting to 127.0.0.1 (socket._fallback_socketpair on Windows,
    and on any platform without a native socketpair); refusing it made every AppTest fail on Python 3.13 / Windows. That is not network use."""
    originals = {name: getattr(socket.socket, name) for name in ("connect", "connect_ex")}

    def guard(name):
        def guarded(self, address, *args, **kwargs):
            if _is_loopback(address):
                return originals[name](self, address, *args, **kwargs)
            counters.sockets.append(address)
            raise AssertionError(f"the what-if tab opened a socket to {address!r}")
        return guarded

    with mock.patch.object(socket.socket, "connect", guard("connect")), mock.patch.object(socket.socket, "connect_ex", guard("connect_ex")):
        yield


def _tab(counters=None):
    """A fresh AppTest of the tab alone, offline."""
    return AppTest.from_string(SCRIPT, default_timeout=120)


def _quick(at, scenario, **extra):
    """Short run: 10 min at dt = 30 s with the step at 3 min (20 steps)."""
    at.radio(key="wi_scenario").set_value(scenario).run()        # a new step type brings its own dt / duration defaults ...
    at.radio(key="wi_dt_s").set_value(30)                          # ... so the quick run sets its own: 10 min at dt = 30 s (20 steps)
    at.number_input(key="wi_duration_min").set_value(10)
    at.number_input(key="wi_step_min").set_value(3)
    for key, value in extra.items():
        at.slider(key=key).set_value(value)
    at.run()                                    # the widget values are committed first, then the button is pressed
    return at.button(key="wi_run").click().run()


@pytest.fixture(scope="module")
def runs():
    """{name: (AppTest after the run, payload)} for the three scenarios and one changed-tau run, with the call counters."""
    st.cache_data.clear()
    fake = FakeSupabase()
    counters = _Counters()

    def refuse_urlopen(*args, **kwargs):
        counters.urlopen.append(args)
        raise AssertionError("the what-if tab made a network call")

    out = {"fake": fake, "counters": counters}
    started = time.perf_counter()
    with patched_supabase(fake), mock.patch("urllib.request.urlopen", side_effect=refuse_urlopen), _refuse_external_sockets(counters):
        at0 = _tab().run()
        out["default"] = at0
        for name, scenario, extra in (("feed", "feed", {}), ("er", "er", {}), ("T", "T", {}),
                                      ("feed_fast_conv", "feed", {"wi_tau_tau_conv": 600.0})):
            at = _quick(_tab().run(), scenario, **extra)
            out[name] = (at, at.session_state["wi_payload"] if "wi_payload" in at.session_state else None)
    out["seconds"] = time.perf_counter() - started
    return out


# ------------------------------------------------------------------------------------------------ render with defaults
def test_tab_renders_with_defaults_and_shows_the_banner_and_the_not_valid_box(runs):
    at = runs["default"]
    assert not at.exception, [str(e.value)[:300] for e in at.exception]
    assert not at.error
    markdown = "\n".join(m.value for m in at.markdown)
    assert sim.BANNER_TEXT in markdown
    assert sim.BANNER_TEXT.startswith("WHAT-IF SIMULATION. Not the live plant. Time constants are Assumed and not validated against plant data.")
    assert "Not valid in transients" in markdown
    for item in ("HB-013", "HB-018", "EU-010"):
        assert item in markdown
    assert "No result yet" in "\n".join(i.value for i in at.info)
    run = at.button(key="wi_run")
    assert run.disabled is False


def test_the_five_time_constants_are_sliders_limited_to_their_declared_ranges(runs):
    at = runs["default"]
    assert set(dy.TAU_SPECS) == {"T_gasifier", "tau_conv", "tau_gas", "tau_rec", "EU008_cooling_water"}
    for name, spec in dy.TAU_SPECS.items():
        slider = at.slider(key=f"wi_tau_{name}")
        assert (slider.min, slider.max) == (spec.range_s[0], spec.range_s[1]), name
        assert slider.value == spec.default_s, name
        assert spec.status == "Assumed"
    markdown = "\n".join(m.value for m in at.markdown)
    assert markdown.count(">Assumed<") >= 5                     # one status tag per time constant (plus the headings)


def test_default_dt_warns_about_poorly_resolved_taus_but_runs(runs):
    at = runs["default"]
    warnings = " ".join(w.value for w in at.warning)
    assert "tau_gas = 30 s" in warnings and "Poorly resolved" in warnings
    assert at.radio(key="wi_dt_s").value == 30


# ----------------------------------------------------------------------------------------------------- the three runs
@pytest.mark.parametrize("name", ["feed", "er", "T"])
def test_pressing_run_completes_for_each_scenario_with_series_and_charts(runs, name):
    at, payload = runs[name]
    assert not at.exception, [str(e.value)[:300] for e in at.exception]
    assert not at.error, [e.value for e in at.error]
    assert payload and len(payload["series"]) == 21 and payload["n_steps"] == 20
    assert payload["series"][0]["t_s"] == 0 and payload["series"][-1]["t_s"] == 600
    assert all(math.isfinite(v) for row in payload["series"] for v in row.values())
    assert len(at.get("vega_lite_chart")) == 1 + len(sim.PLOT_QUANTITIES)         # the normalised chart + one absolute panel per quantity
    assert {"wi_dl_series", "wi_dl_response"} <= {d.key for d in at.get("download_button")}
    # the response table has one row per plotted quantity and carries before / end / final values
    assert [r["key"] for r in payload["response"]] == [q[0] for q in sim.PLOT_QUANTITIES]
    flow = payload["response"][0]
    assert flow["before"] == payload["series"][3 * 2]["ga001_dry_flow_nm3_h"]       # the row at the step time (t = 180 s, dt = 30 s)
    assert flow["final"] != flow["before"] or name == "T"


def test_the_response_times_use_the_demo_scripts_definitions(runs):
    """time_to_fraction is a copy of scripts/run_transient_demo.py's; pin them together (the demo is loaded without its import side
    effects leaking: it replaces the database clients at import, which the mock context undoes)."""
    import importlib.util

    from python import confirmation_loop, vendor_log

    with mock.patch.object(vendor_log, "_get_client"), mock.patch.object(confirmation_loop, "_get_client"):
        spec = importlib.util.spec_from_file_location("_demo_under_test", os.path.join(ROOT, "scripts", "run_transient_demo.py"))
        demo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(demo)
    _at, payload = runs["er"]
    series, step = payload["series"], payload["params"]["step_s"]
    checked = 0
    for r in payload["response"]:
        if not r["meaningful"]:
            continue
        for fraction, key in ((0.632, "t63"), (0.95, "t95")):
            assert demo.time_to_fraction(series, r["key"], r["before"], r["final"], fraction, step) == r[key]
            checked += 1
    assert checked >= 10
    # and on a synthetic exponential the definition returns the analytic point (interpolation error only)
    synth = [{"t_s": t, "x": 1 - math.exp(-t / 100.0)} for t in range(0, 1000, 10)]
    assert sim.time_to_fraction(synth, "x", 0.0, 1.0, 0.632, 0) == pytest.approx(100.0, abs=0.5)


def test_changing_a_time_constant_changes_the_result(runs):
    _a, base = runs["feed"]
    _b, fast = runs["feed_fast_conv"]
    assert next(a for a in fast["assumptions"] if a["name"] == "tau_conv")["value_s"] == 600.0
    assert next(a for a in base["assumptions"] if a["name"] == "tau_conv")["value_s"] == 1200.0
    assert fast["series"][-1]["ga001_dry_flow_nm3_h"] != base["series"][-1]["ga001_dry_flow_nm3_h"]
    # a faster conversion lag has covered more of the change by the end of the same run
    assert fast["response"][0]["end_pct"] > base["response"][0]["end_pct"]


# ------------------------------------------------------------------------------- invalid quantities are never plotted
def test_hb013_hb018_eu010_are_never_plotted_or_exported(runs):
    forbidden = ("hb013", "hb018", "eu010", "ai004", "HB-013", "HB-018", "EU-010", "storage", "dispens", "soc_kwh")
    for name in ("feed", "er", "T"):
        at, payload = runs[name]
        assert not set(sim.NOT_VALID_SERIES) & set(payload["series"][0]), name
        assert not set(sim.NOT_VALID_SERIES) & {r["key"] for r in payload["response"]}
        for chart in at.get("vega_lite_chart"):
            spec = chart.proto.spec.lower()
            assert not [w for w in forbidden if w.lower() in spec], (name, [w for w in forbidden if w.lower() in spec])
        assert not set(sim.NOT_VALID_SERIES) & set(payload["units"])
        csv_text = sim.build_csv(payload)
        assert "# Not included on purpose (not valid in transients)" in csv_text
        table = pd.read_csv(pd.io.common.StringIO(csv_text), comment="#")
        assert not set(sim.NOT_VALID_SERIES) & set(table.columns) and list(table.columns) == list(sim.SERIES_COLUMNS)
    assert {q[0] for q in sim.PLOT_QUANTITIES}.isdisjoint(sim.NOT_VALID_SERIES)


def test_the_csv_carries_the_banner_and_the_assumed_time_constants(runs):
    _at, payload = runs["T"]
    text = sim.build_csv(payload)
    header = [line for line in text.splitlines() if line.startswith("#")]
    assert header[0] == "# " + sim.BANNER_TEXT
    for name in dy.TAU_SPECS:
        assert any(line.startswith(f"#   {name}, ") and ", Assumed, " in line for line in header), name
    response = sim.build_response_csv(payload)
    assert response.splitlines()[0] == "# " + sim.BANNER_TEXT and "t63_s" in response


# ----------------------------------------------------------------------------------------------------- no side effects
def test_zero_database_or_network_calls_and_nothing_shared_was_touched(runs):
    assert runs["fake"].calls == [], runs["fake"].calls
    assert runs["counters"].urlopen == [] and runs["counters"].sockets == []
    assert cycle_clock._elapsed_hours is None and eu.EU008_DAMPING == 0.5     # the server process's globals were never moved


def test_the_worker_environment_has_no_credentials_and_writes_are_forced_off():
    env = sim.child_env({"SUPABASE_URL": "u", "SUPABASE_KEY": "k", "GITHUB_TOKEN": "t", "MY_SECRET": "s", "PATH": "/bin", "HOME": "/h",
                        "HYGAS_ALLOW_DB_WRITES": "1"})
    assert {"PATH", "HOME"} <= set(env)
    assert not [k for k in env if any(m in k.upper() for m in ("SUPABASE", "TOKEN", "SECRET", "KEY"))]
    assert env["HYGAS_ALLOW_DB_WRITES"] == "0"


def test_the_simulation_itself_is_database_and_network_free_and_restores_the_globals(monkeypatch):
    """simulate() is what the child runs. In-process here, under the counting fake and with sockets refused: the 24 warm-up engine
    cycles plus the first sub-steps run, then a failure is injected. The failing run restores cycle_clock and EU008_DAMPING
    (dynamics.run_transient's finally). The full-length runs happen in the child process (the `runs` fixture)."""
    fake = FakeSupabase()
    counters = _Counters()
    params = sim.normalise_params({"duration_min": 10, "step_min": 3})
    with patched_supabase(fake), _refuse_external_sockets(counters):
        calls = {"n": 0}
        original = dy.relax

        def boom(*a, **k):
            calls["n"] += 1
            if calls["n"] > 5:
                raise RuntimeError("injected failure")
            return original(*a, **k)

        monkeypatch.setattr(dy, "relax", boom)
        with pytest.raises(RuntimeError, match="injected failure"):
            sim.simulate(params)
    assert fake.calls == [] and counters.sockets == []
    assert cycle_clock._elapsed_hours is None and eu.EU008_DAMPING == 0.5


def test_a_failed_or_busy_run_is_a_message_never_a_traceback(monkeypatch):
    st.cache_data.clear()
    for failure in (sim.WhatIfError("The simulation failed (exit code 1): ValueError: boom"), sim.WhatIfBusy("Another what-if run is in progress"),
                    RuntimeError("unexpected")):
        def fail(params, _failure=failure):
            raise _failure

        monkeypatch.setattr(sim, "run_in_child", fail)
        at = _tab().run()
        at.button(key="wi_run").click().run()
        assert not at.exception, [str(e.value)[:200] for e in at.exception]
        shown = " ".join(e.value for e in at.error)
        assert shown and "Traceback" not in shown, shown
        assert at.session_state["wi_payload"] is None if "wi_payload" in at.session_state else True


def test_a_worker_crash_becomes_a_one_line_error(monkeypatch):
    crashed = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="Traceback (most recent call last):\n  File x\nValueError: bad\n")
    monkeypatch.setattr(sim.subprocess, "run", lambda *a, **k: crashed)
    with pytest.raises(sim.WhatIfError) as excinfo:
        sim.run_in_child(sim.normalise_params({}))
    assert "Traceback" not in str(excinfo.value) and "ValueError: bad" in str(excinfo.value)
    monkeypatch.setattr(sim.subprocess, "run", mock.Mock(side_effect=subprocess.TimeoutExpired(cmd="x", timeout=1)))
    with pytest.raises(sim.WhatIfError, match="longer than"):
        sim.run_in_child(sim.normalise_params({}))


def test_only_one_run_at_a_time(monkeypatch):
    assert sim._RUN_LOCK.acquire(blocking=False)
    try:
        with pytest.raises(sim.WhatIfBusy):
            sim.run_in_child(sim.normalise_params({}))
    finally:
        sim._RUN_LOCK.release()


# ---------------------------------------------------------------------------------------- limits, caps, dt resolution
def test_a_tau_outside_its_declared_range_is_refused():
    for name, (lo, hi) in sim.tau_ranges().items():
        for bad in (lo - 1.0, hi + 1.0):
            p = sim.normalise_params({"taus": {name: bad}})
            assert any(name in e and "outside its declared range" in e for e in sim.validate_params(p)), (name, bad)
        for good in (lo, hi):
            p = sim.normalise_params({"taus": {name: good}, "dt_s": 30})
            assert not any("outside its declared range" in e for e in sim.validate_params(p)), (name, good)
    assert sim.validate_params(sim.normalise_params({})) == []
    with pytest.raises(sim.WhatIfError, match="outside its declared range"):
        sim.run_in_child(sim.normalise_params({"taus": {"tau_gas": 5000.0}}))


def test_input_limits_come_from_the_declared_ranges():
    assert sim.ER_RANGE == (0.2125, 0.2875)
    for p, text in ((sim.normalise_params({"scenario": "er", "er_new": 0.30}), "limits of this tab"),
                    (sim.normalise_params({"scenario": "feed", "feed_pct": 50.0}), "Feed change"),
                    (sim.normalise_params({"scenario": "T", "T_new": 1100.0}), "T setpoint")):
        assert any(text in e for e in sim.validate_params(p)), text


def test_caps_on_steps_and_duration_give_a_message():
    too_many = sim.normalise_params({"duration_min": 240, "dt_s": 30})              # 480 steps
    assert any("Cap hit" in e and "240 steps" in e for e in sim.validate_params(too_many))
    too_long = sim.normalise_params({"duration_min": 300, "dt_s": 120, "taus": {"tau_gas": 120.0, "tau_rec": 140.0}})
    assert any("Cap hit" in e and "4 h" in e for e in sim.validate_params(too_long))
    edge = sim.normalise_params({"duration_min": 120, "dt_s": 30})                  # exactly 240 steps is allowed
    assert sim.validate_params(edge) == [] and edge["duration_s"] // edge["dt_s"] == sim.MAX_STEPS


def test_dt_rule_warns_below_two_dt_and_blocks_below_one_dt():
    taus = sim.default_taus()
    blocked, warned = sim.check_resolution(taus, 30)
    assert blocked == [] and [n for n, _ in warned] == ["tau_gas"]                  # 30 s < 60 s
    blocked, warned = sim.check_resolution(taus, 60)
    assert [n for n, _ in blocked] == ["tau_gas"] and {n for n, _ in warned} == {"tau_rec"}
    p = sim.normalise_params({"dt_s": 60})
    assert any("tau_gas = 30 s is shorter than dt = 60 s" in e for e in sim.validate_params(p))
    assert sim.validate_params(sim.normalise_params({"dt_s": 60, "taus": {"tau_gas": 60.0, "tau_rec": 120.0}})) == []


def test_in_the_page_a_blocked_dt_disables_the_run_button_and_says_why():
    st.cache_data.clear()
    at = _tab().run()
    at.radio(key="wi_dt_s").set_value(60).run()
    assert at.button(key="wi_run").disabled is True
    assert any("tau_gas = 30 s is shorter than dt = 60 s" in e.value for e in at.error)
    at.slider(key="wi_tau_tau_gas").set_value(60.0)
    at.slider(key="wi_tau_tau_rec").set_value(120.0).run()
    assert at.button(key="wi_run").disabled is False and not at.error


def test_the_step_time_is_snapped_to_a_sub_step_boundary():
    p = sim.normalise_params({"step_min": 10.1, "duration_min": 125, "dt_s": 120, "taus": {"tau_gas": 120.0, "tau_rec": 140.0}})
    assert p["step_s"] % 120 == 0 and p["duration_s"] % 120 == 0


def test_reset_to_defaults_restores_every_input():
    at = _tab().run()
    at.radio(key="wi_scenario").set_value("T")
    at.slider(key="wi_tau_tau_conv").set_value(900.0)
    at.number_input(key="wi_duration_min").set_value(60).run()
    at.button(key="wi_reset").click().run()
    assert at.radio(key="wi_scenario").value == "feed" and at.slider(key="wi_tau_tau_conv").value == 1200.0
    assert at.number_input(key="wi_duration_min").value == 120


def test_the_measured_time_of_the_shared_runs_is_reported_not_asserted(runs, record_property):
    """The fixture's four real runs (child processes) are the bulk of this file's time. The measurement is information only: a shared CI
    runner took 69 s where a development machine takes ~33 s, so a budget here is a flaky test, not a check. (Hang protection lives in the
    worker's 300 s kill and in the AppTest / subprocess timeouts, which are unchanged.) Recorded as a test property and printed (-rP)."""
    record_property("what_if_shared_runs_seconds", round(runs["seconds"], 1))
    print(f"what-if shared runs (4 child-process simulations): {runs['seconds']:.1f} s  [information only, never a pass/fail condition]")
    assert set(runs) >= {"default", "feed", "er", "T", "feed_fast_conv", "seconds"}                 # the measurement exists; its value is not judged


# ------------------------------------------------------------------------------------ A: dt 10 / 15 s, clamp, "not resolved"
def _exponential(tau, dt, n=80):
    return [{"t_s": k * dt, "x": 1.0 - math.exp(-k * dt / tau)} for k in range(n)]


@pytest.mark.parametrize("tau,dt", [(10.0, 30), (25.0, 15), (60.0, 30), (200.0, 30), (20.0, 10), (500.0, 120)])
def test_a_a_time_is_flagged_not_resolved_exactly_when_it_is_shorter_than_two_steps(tau, dt):
    series = _exponential(tau, dt)
    keys = [q[0] for q in sim.PLOT_QUANTITIES]
    for row in series:
        row.update({k: row["x"] for k in keys})
    row = sim.response_table(series, 0, {k: 1.0 for k in keys}, dt)[0]       # the step at t = 0, final value 1.0
    for key, flag in (("t63", "t63_unresolved"), ("t95", "t95_unresolved")):
        value = row[key]
        assert value is not None and row[flag] == (value < 2 * dt), (tau, dt, key, value)


def test_a_labels_appear_in_the_table_and_the_csv_only_in_the_unresolved_cases(runs):
    seen_label = seen_number = 0
    for name in ("er", "T"):
        at, payload = runs[name]
        dt = payload["params"]["dt_s"]
        frame = next(d.value for d in at.dataframe if "t63 [s]" in list(d.value.columns))
        csv_text = sim.build_response_csv(payload)
        body = [line for line in csv_text.splitlines() if not line.startswith("#")][1:]
        for r, (_i, shown), line in zip(payload["response"], frame.iterrows(), body):
            for key, flag, column in (("t63", "t63_unresolved", "t63 [s]"), ("t95", "t95_unresolved", "t95 [s]")):
                value = r[key] if r["meaningful"] else None
                unresolved = value is not None and value < 2 * dt
                assert r[flag] == unresolved, (name, r["key"], key)
                assert (shown[column] == sim.UNRESOLVED_LABEL) == unresolved, (name, r["key"], key, shown[column])
                if unresolved:
                    seen_label += 1
                elif value is not None:
                    seen_number += 1
                    assert shown[column] == f"{value:.0f}", (name, r["key"], key, shown[column])
            assert (sim.UNRESOLVED_LABEL in line) == (r["t63_unresolved"] or r["t95_unresolved"]), line
        assert f"# sampling interval dt = {dt} s" in csv_text
        assert f"Sampling interval dt = {dt} s" in " ".join(c.value for c in at.caption)
    assert seen_label >= 2 and seen_number >= 2           # both cases occurred, so the test is not vacuous


def test_a_dt_10_and_15_are_runnable_only_when_the_rule_allows():
    assert sim.DT_CHOICES_S == (10, 15, 30, 60, 120)
    for dt in (10, 15):
        assert sim.validate_params(sim.normalise_params({"dt_s": dt, "duration_min": 10, "step_min": 3})) == []      # the Assumed defaults
    p = sim.normalise_params({"dt_s": 10, "duration_min": 10, "step_min": 3, "taus": {"tau_gas": 8.0}})              # 8 s < dt = 10 s
    assert any("tau_gas = 8 s is shorter than dt = 10 s" in e for e in sim.validate_params(p))
    p = sim.normalise_params({"dt_s": 15, "duration_min": 10, "step_min": 3, "taus": {"tau_gas": 14.0, "tau_rec": 12.0}})
    errors = sim.validate_params(p)
    assert any("tau_gas = 14 s is shorter than dt = 15 s" in e for e in errors) and any("tau_rec = 12 s is shorter than dt = 15 s" in e for e in errors)
    blocked, warned = sim.check_resolution({**sim.default_taus(), "tau_gas": 20.0}, 15)
    assert blocked == [] and [n for n, _ in warned] == ["tau_gas"]                                                    # 15 <= 20 < 30
    assert sim.validate_params(sim.normalise_params({"dt_s": 10, "duration_min": 40})) == []                          # exactly 240 steps
    assert any("Cap hit" in e for e in sim.validate_params(sim.normalise_params({"dt_s": 10, "duration_min": 41})))


def test_a_the_duration_clamp_and_the_maximum_for_each_dt():
    assert [sim.max_duration_s(d) for d in sim.DT_CHOICES_S] == [2400, 3600, 7200, 14400, 14400]
    assert sim.clamp_duration_min(120, 10) == (40, True) and sim.clamp_duration_min(120, 15) == (60, True)
    assert sim.clamp_duration_min(120, 30) == (120, False) and sim.clamp_duration_min(300, 60) == (240, True)
    assert sim.clamp_duration_min(40, 10) == (40, False) and sim.clamp_duration_min(5, 30) == (10, False)


def test_a_in_the_page_a_finer_dt_clamps_the_duration_and_says_so_instead_of_failing_at_run():
    at = _tab().run()
    assert at.number_input(key="wi_duration_min").value == 120 and "longest run is **120 min**" in " ".join(c.value for c in at.caption)
    at.radio(key="wi_dt_s").set_value(10).run()
    assert at.number_input(key="wi_duration_min").value == 40
    assert any("reduced from 120 to 40 min" in w.value for w in at.warning)
    assert "longest run is **40 min**" in " ".join(c.value for c in at.caption)
    assert at.button(key="wi_run").disabled is False and not at.error
    at.radio(key="wi_dt_s").set_value(30).run()
    assert "longest run is **120 min**" in " ".join(c.value for c in at.caption)


def test_a_each_step_type_brings_its_own_default_dt_and_duration_with_the_reason():
    at = _tab().run()
    assert (at.radio(key="wi_dt_s").value, at.number_input(key="wi_duration_min").value) == (30, 120)
    for scenario, dt, duration in (("er", 10, 30), ("T", 15, 30), ("feed", 30, 120)):
        at.radio(key="wi_scenario").set_value(scenario).run()
        assert (at.radio(key="wi_dt_s").value, at.number_input(key="wi_duration_min").value) == (dt, duration), scenario
        assert sim.SCENARIO_DEFAULTS[scenario]["why"] in " ".join(c.value for c in at.caption)
        params = sim.normalise_params({"scenario": scenario, "dt_s": dt, "duration_min": duration, "step_min": at.number_input(key="wi_step_min").value})
        assert sim.validate_params(params) == [] and params["duration_s"] // params["dt_s"] <= sim.MAX_STEPS
        assert not at.error


# ------------------------------------------------------------------------------------------ C: where the ER range comes from
_ER_SYNC_CHILD = """
import json, sys
sys.path.insert(0, {root!r})
from unittest import mock
from python import confirmation_loop as cl, uncertainty as u
if {apply!r}:
    row = {{"status": cl.STATUS_CONFIRMED, "confirmed_range_low": 0.245, "confirmed_range_high": 0.255}}
    with mock.patch.object(cl, "load_status", return_value={{"air_equivalence_ratio": row}}):      # the reader is patched: no database
        cl.sync_confirmed_from_db()
from python import ui_transient_sim as sim              # imported AFTER the sync, as app.py does (Tab 1 runs before Tab 11)
print(json.dumps({{"confirmed": u.is_confirmed("air_equivalence_ratio"), "uncertainty_bounds": list(u.bounds("air_equivalence_ratio")),
                  "er_range": list(sim.ER_RANGE), "er_default": sim.DEFAULTS["er_new"], "er_base": sim.ER_BASE}}))
"""


def _er_child(apply):
    env = sim.child_env(os.environ)
    out = subprocess.run([__import__("sys").executable, "-c", _ER_SYNC_CHILD.format(root=ROOT, apply=apply)], capture_output=True, text=True,
                         cwd=ROOT, env=env, timeout=60)
    assert out.returncode == 0, out.stderr[-400:]
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_c_the_er_range_is_the_same_with_and_without_the_confirmation_sync():
    without, with_sync = _er_child(False), _er_child(True)
    assert without["confirmed"] is False and with_sync["confirmed"] is True
    assert without["uncertainty_bounds"] == [0.2125, 0.2875] and with_sync["uncertainty_bounds"] == [0.245, 0.255]     # the thing the tab no longer follows
    assert without["er_range"] == with_sync["er_range"] == [0.2125, 0.2875]
    assert without["er_default"] == with_sync["er_default"] == 0.2875 and without["er_base"] == with_sync["er_base"] == 0.25


def test_c_the_er_limits_are_fixed_constants_with_the_documented_basis():
    import ast
    import inspect

    from python import uncertainty

    tree = ast.parse(inspect.getsource(sim))
    assigned = {t.id: node.value for node in tree.body if isinstance(node, ast.Assign) for t in node.targets if isinstance(t, ast.Name)}
    for name in ("ER_RANGE", "ER_BASE"):
        value = assigned[name]
        assert all(isinstance(n, ast.Constant) for n in ast.walk(value) if not isinstance(n, (ast.Tuple, ast.Load))), name   # literals only
    cfg = uncertainty.ASSUMPTIONS["air_equivalence_ratio"]
    lo, hi = cfg["point"] * (1 - cfg["fraction"]), cfg["point"] * (1 + cfg["fraction"])
    assert sim.ER_BASE == cfg["point"] and sim.ER_RANGE == pytest.approx((lo, hi), abs=1e-12)          # the basis the docs state
    for p in (sim.normalise_params({"scenario": "er", "er_new": 0.30}), sim.normalise_params({"scenario": "er", "er_new": 0.20})):
        assert any("limits of this tab" in e and "tab limits, not validated ranges" in e for e in sim.validate_params(p))


def test_c_the_slider_is_identical_with_and_without_the_sync_and_the_status_is_shown_from_memory_only():
    from python import confirmation_loop as cl, uncertainty

    def slider_and_caption():
        at = _tab().run()
        at.radio(key="wi_scenario").set_value("er").run()
        s = at.slider(key="wi_er_new")
        return (s.min, s.max, s.value), " ".join(c.value for c in at.caption), at

    fake = FakeSupabase()
    with patched_supabase(fake):
        plain, caption_plain, _ = slider_and_caption()
        row = {"status": cl.STATUS_CONFIRMED, "confirmed_range_low": 0.245, "confirmed_range_high": 0.255}
        try:
            with mock.patch.object(cl, "load_status", return_value={"air_equivalence_ratio": row}):
                cl.sync_confirmed_from_db()
            assert uncertainty.is_confirmed("air_equivalence_ratio")
            synced, caption_synced, at = slider_and_caption()
            assert not at.exception and not at.error
        finally:
            uncertainty.clear_confirmed("air_equivalence_ratio")
    assert plain == synced == (0.2125, 0.2875, 0.2875)
    assert "Air ratio status: Assumed, not confirmed" in caption_plain
    assert "Air ratio status: confirmation recorded" in caption_synced and "0.245-0.255" in caption_synced
    assert fake.calls == [], fake.calls                                           # the status needs no database call
    assert not uncertainty.is_confirmed("air_equivalence_ratio")                  # the test left the process as it found it


def test_c_the_input_limits_are_visibly_labelled_and_the_envelope_question_is_asked():
    at = _tab().run()
    markdown = "\n".join(m.value for m in at.markdown)
    assert f"**Also ask DOK-ING:** {sim.ENVELOPE_QUESTION}" in markdown
    assert "operating envelope for feed rate, air ratio (ER) and gasifier temperature" in sim.ENVELOPE_QUESTION
    for scenario, text in (("feed", "-30 … +30 %"), ("er", "0.2125 … 0.2875"), ("T", "850 … 1000 °C")):
        at.radio(key="wi_scenario").set_value(scenario).run()
        captions = [c.value for c in at.caption if sim.LIMITS_NOTE in c.value]
        assert len(captions) == 1 and text in captions[0], (scenario, captions)
        assert sim.LIMITS_NOTE == "tab limits, not validated ranges"


# ---------------------------------------------------------------------------- the zero-network guard itself is loopback-aware
def _attempt(method, address):
    with socket.socket() as sock:
        sock.settimeout(1)
        return getattr(sock, method)(address)


def test_the_socket_guard_refuses_external_addresses_and_allows_loopback():
    counters = _Counters()
    connect_before, connect_ex_before = socket.socket.connect, socket.socket.connect_ex
    with _refuse_external_sockets(counters):
        # loopback is allowed: a socketpair (what asyncio makes for every event loop) and an explicit connection to 127.0.0.1
        left, right = socket.socketpair()
        left.close(), right.close()
        with socket.socket() as server:
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            with socket.socket() as client:
                client.settimeout(5)
                client.connect(server.getsockname())
        assert counters.sockets == []
        # the path used on Windows / without a native socketpair connects to 127.0.0.1 too; it must not trip the guard
        fallback = getattr(socket, "_fallback_socketpair", None)
        if fallback is not None:
            left, right = fallback()
            left.close(), right.close()
            assert counters.sockets == []
        # external addresses are still refused, before anything is sent: a public IP, a hostname, connect_ex, create_connection
        for call in (lambda: _attempt("connect", ("93.184.216.34", 80)), lambda: _attempt("connect", ("example.com", 80)),
                     lambda: _attempt("connect_ex", ("8.8.8.8", 53)), lambda: socket.create_connection(("93.184.216.34", 443), timeout=1)):
            with pytest.raises(AssertionError, match="opened a socket to"):
                call()
        assert [a[0] for a in counters.sockets] == ["93.184.216.34", "example.com", "8.8.8.8", "93.184.216.34"]
    assert socket.socket.connect is connect_before and socket.socket.connect_ex is connect_ex_before      # the real methods are back
    assert _is_loopback(("127.0.0.1", 1)) and _is_loopback(("::1", 1, 0, 0)) and _is_loopback("/tmp/x.sock")
    assert not _is_loopback(("10.0.0.5", 1)) and not _is_loopback(("example.com", 1))


# ------------------------------------------------------------------------- chart conventions (visual polish; presentation only)
@pytest.mark.parametrize("name", ["feed", "er", "T"])
def test_ui_charts_are_full_width_one_per_row_and_tall_enough(runs, name):
    at, _payload = runs[name]
    charts = at.get("vega_lite_chart")
    specs = [json.loads(c.proto.spec) for c in charts]
    assert len(charts) == 1 + len(sim.PLOT_QUANTITIES)
    assert all(c.proto.use_container_width for c in charts) and all(spec["width"] == "container" for spec in specs)
    assert all(not ({"facet", "hconcat", "vconcat", "columns"} & set(spec)) for spec in specs)                  # one chart per row
    assert specs[0]["height"] >= 360                                                                              # the normalised chart
    assert sum(spec["height"] for spec in specs[1:]) >= 320 and all(spec["height"] >= 150 for spec in specs[1:])  # the absolute panels


def test_ui_markers_follow_the_table_for_the_selected_quantity_and_unresolved_ones_say_so(runs):
    drawn = withheld = 0
    for name in ("feed", "er", "T"):
        at, payload = runs[name]
        assert at.selectbox(key="wi_marker").value == "ga001_dry_flow_nm3_h"                       # the default
        flow = payload["response"][0]
        spec_text = at.get("vega_lite_chart")[0].proto.spec
        caption = " ".join(c.value for c in at.caption)
        for which in ("t63", "t95"):
            text, seconds = ch.time_cell(flow, which)
            assert (f'"{which}_marker"' in spec_text) == (seconds is not None), (name, which)
            if seconds is None:
                withheld += 1
                assert f"{which}: {text} (no marker drawn)" in caption, (name, which, text)
            else:
                drawn += 1
                assert f"{which} = {text} s" in caption, (name, which)
        assert f"Sampling interval dt = {payload['params']['dt_s']} s." in caption
        assert "63.2 %" in caption and "95 %" in caption
    assert drawn >= 2 and withheld >= 1                      # both cases occurred, so the test is not vacuous


def test_ui_choosing_another_quantity_moves_the_markers_without_a_new_run(runs):
    at, payload = runs["feed"]
    fake, before = runs["fake"], len(runs["fake"].calls)
    options = at.selectbox(key="wi_marker").options
    assert "H₂ production" in options                                         # the options are shown with their labels
    try:
        at.selectbox(key="wi_marker").set_value("h2_production_kg_h").run()
        row = next(r for r in payload["response"] if r["key"] == "h2_production_kg_h")
        caption = " ".join(c.value for c in at.caption)
        text63, _s = ch.time_cell(row, "t63")
        assert f"{sim.PLOT_QUANTITIES[7][1].replace('H2', 'H₂')}: " in caption and (f"t63 = {text63} s" in caption or f"t63: {text63}" in caption)
        assert at.session_state["wi_payload"] is payload or at.session_state["wi_payload"] == payload          # no new simulation
    finally:
        at.selectbox(key="wi_marker").set_value("ga001_dry_flow_nm3_h").run()
    assert not at.exception and len(fake.calls) == before


def test_ui_the_table_is_right_aligned_with_units_and_the_csv_is_unchanged(runs):
    at, payload = runs["er"]
    frame = next(d.value for d in at.dataframe if "t63 [s]" in list(d.value.columns))
    assert list(frame.columns)[0] == "Quantity [unit]" and "GA-001 dry gas flow [Nm³/h]" in set(frame["Quantity [unit]"])
    columns = tab._table_columns(frame)
    if not columns:
        pytest.skip("this Streamlit has no column alignment")
    assert set(columns) == set(frame.columns[1:]) and all(c["alignment"] == "right" for c in columns.values())
    header = [line for line in sim.build_response_csv(payload).splitlines() if not line.startswith("#")][0]
    assert header == "quantity,unit,before_step,end_of_run,final_steady_state,change,t63_s,t95_s,peak_pct_of_change,meaningful_change"


def test_ui_the_zoom_note_follows_the_span_and_the_axis_radio_changes_the_domain(runs):
    at, payload = runs["feed"]
    absolute, _n, step_min, duration_min = ch.long_frames(payload)
    expected = [ch.zoom_note(absolute[absolute["key"] == key]) for key in dict.fromkeys(absolute["key"])]
    assert at.radio(key="wi_axis").value == "zoomed"
    specs = [json.loads(c.proto.spec) for c in at.get("vega_lite_chart")[1:]]
    assert [spec["title"].get("subtitle") for spec in specs] == expected
    assert any(expected) and not all(expected)                                  # notes on some panels, none on the others
    try:
        at.radio(key="wi_axis").set_value("from zero").run()
        flat = [json.loads(c.proto.spec) for c in at.get("vega_lite_chart")[1:]]
        assert not any(spec["title"].get("subtitle") for spec in flat)
        assert all(next(l["encoding"]["y"]["scale"] for l in spec["layer"] if l["mark"]["type"] == "line") == {"zero": True} for spec in flat)
    finally:
        at.radio(key="wi_axis").set_value("zoomed").run()
    assert not at.exception


def test_ui_the_tau_sliders_show_whole_seconds_but_pass_the_exact_stored_default_to_the_worker(runs):
    at = runs["default"]
    exact = dy.TAU_SPECS["EU008_cooling_water"].default_s
    assert exact != round(exact)                                                  # the default really is a long fraction (5193.70...)
    slider = at.slider(key="wi_tau_EU008_cooling_water")
    assert slider.value.hex() == exact.hex()                                      # the widget holds the exact stored number ...
    assert slider.proto.format == "%.0f s"                                        # ... and only the label is rounded (about 5194 s)
    for name in dy.TAU_SPECS:
        assert at.slider(key=f"wi_tau_{name}").proto.format == "%.0f s"
    # the numbers sent to the worker: bit-identical defaults, and the same cache key as the engine-side defaults give
    _at, payload = runs["feed"]
    sent = payload["params"]["taus"]
    assert {n: v.hex() for n, v in sent.items()} == {n: s_.default_s.hex() for n, s_ in dy.TAU_SPECS.items()}
    again = sim.normalise_params({"scenario": "feed", "step_min": 3, "duration_min": 10, "dt_s": 30,
                                  "taus": {n: s_.default_s for n, s_ in dy.TAU_SPECS.items()}})
    assert json.dumps(payload["params"], sort_keys=True) == json.dumps(again, sort_keys=True)
    assert next(a["value_s"] for a in payload["assumptions"] if a["name"] == "EU008_cooling_water").hex() == exact.hex()


# the order of the controls on origin/main 28bd143 (before the width cap); the cap must not reorder anything
_CONTROL_ORDER = [("radio", "wi_scenario"), ("number_input", "wi_feed_pct"), ("number_input", "wi_step_min"), ("number_input", "wi_duration_min"),
                  ("radio", "wi_dt_s"), ("slider", "wi_tau_T_gasifier"), ("slider", "wi_tau_tau_conv"), ("slider", "wi_tau_tau_gas"),
                  ("slider", "wi_tau_tau_rec"), ("slider", "wi_tau_EU008_cooling_water"), ("button", "wi_run"), ("button", "wi_reset")]


def _walk(node, under=(), out=None):
    """(element, chain of ancestor block types / weights) for every element below `node`, in page order."""
    out = [] if out is None else out
    for child in getattr(node, "children", {}).values():
        weight = round(child.proto.weight, 3) if child.type == "column" else None
        out.append((child, under))
        _walk(child, under + ((child.type, weight),), out)
    return out


def test_ui_the_controls_are_capped_to_two_thirds_in_the_same_order_and_the_charts_stay_full_width(runs):
    at = runs["default"]
    elements = _walk(at.main)
    order = [(e.type, e.key) for e, _under in elements if e.type in ("radio", "number_input", "slider", "button")]
    assert order == _CONTROL_ORDER                                                    # same controls, same order, Run button after the sliders
    controls = [under for e, under in elements if e.type in ("radio", "number_input", "slider") and e.key != "wi_axis"]
    assert controls and all(under[:2] == (("flex_container", None), ("column", 0.667)) for under in controls)        # the left 2/3 column
    runs_row = next(under for e, under in elements if e.type == "button" and e.key == "wi_run")
    assert ("column", 0.333) in runs_row and ("column", 0.667) not in runs_row                                    # the Run row is outside the cap
    charts_at, _payload = runs["feed"]
    assert all(not under for e, under in _walk(charts_at.main) if e.type == "vega_lite_chart")                      # charts: directly in the page


def test_ui_the_assumed_table_wraps_the_questions_unchanged_and_keeps_numbers_right_aligned(runs):
    for name in ("default", "feed"):
        at = runs[name] if name == "default" else runs[name][0]
        assert len(at.table) == 1                                                       # the Assumed table is an HTML table now ...
        assert any("t63 [s]" in list(d.value.columns) for d in at.dataframe) == (name == "feed")          # ... the response table stays a grid
        frame = at.table[0].value
        assert list(frame.columns) == ["Time constant", "Status", "Value [s]", "Declared range [s]", "Question for DOK-ING"]
        assert list(frame["Question for DOK-ING"]) == [s_.question_for_doking for s_ in dy.TAU_SPECS.values()]       # full text, nothing cut
        assert set(frame["Status"]) == {"Assumed"}
    html_text = tab._assumed_styler(frame).to_html()
    for s_ in dy.TAU_SPECS.values():
        assert s_.question_for_doking in html.unescape(html_text)
    import re
    rule = re.search(r"((?:#T_\w+_row\d+_col\d+,?\s*)+)\{\s*text-align: right", html_text)                  # Styler groups the cells into one CSS rule
    assert rule, html_text[:400]
    aligned = {(int(r), int(c)) for r, c in re.findall(r"_row(\d+)_col(\d+)", rule.group(1))}
    assert aligned == {(r, c) for r in range(len(dy.TAU_SPECS)) for c in (2, 3)}        # Value [s] and the declared range, every row, nothing else
    assert ">5193.7<" in html_text and "5193.702" not in html_text                         # one decimal, as the caption beside the slider
