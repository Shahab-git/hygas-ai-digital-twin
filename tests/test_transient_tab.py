"""Tests of the "Transient What-If" tab (Tab 11): python/ui_transient_tab.py + python/ui_transient_sim.py.

The tab is rendered ALONE through Streamlit's AppTest (a three-line script), so every database / network count below belongs to the
new code path and to nothing else. The full app (header, Tab 2 sum of 91, 11 tabs) is covered by tests/test_app_smoke.py.

Offline: the Supabase client is the counting fake (tests/_fakes.py), urlopen and socket connections are counted and refused.
Real simulations run in the tab's child process (that is the production path); each costs a few seconds, so the scenario runs are
done once, in one module-scoped fixture, and shared between the tests.
"""
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
from python import cycle_clock, dynamics as dy, ui_transient_sim as sim
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


def _tab(counters=None):
    """A fresh AppTest of the tab alone, offline."""
    return AppTest.from_string(SCRIPT, default_timeout=120)


def _quick(at, scenario, **extra):
    """Short run: 10 min at dt = 30 s with the step at 3 min (20 steps)."""
    at.radio(key="wi_scenario").set_value(scenario)
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

    def refuse_connect(self, *args, **kwargs):
        counters.sockets.append(args)
        raise AssertionError("the what-if tab opened a socket")

    out = {"fake": fake, "counters": counters}
    started = time.perf_counter()
    with patched_supabase(fake), mock.patch("urllib.request.urlopen", side_effect=refuse_urlopen), \
            mock.patch.object(socket.socket, "connect", refuse_connect):
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
    assert len(at.get("vega_lite_chart")) == 2                                    # absolute + normalised
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
    sockets = []

    def refuse(self, *args, **kwargs):
        sockets.append(args)
        raise AssertionError("socket connect")

    params = sim.normalise_params({"duration_min": 10, "step_min": 3})
    with patched_supabase(fake), mock.patch.object(socket.socket, "connect", refuse):
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
    assert fake.calls == [] and sockets == []
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
    for p, text in ((sim.normalise_params({"scenario": "er", "er_new": 0.30}), "declared Assumed range"),
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


def test_added_test_time_is_reported(runs):
    # the fixture's four real runs (child processes) are the bulk of this file; the budget is 45 s for the whole module
    assert runs["seconds"] < 45, runs["seconds"]
