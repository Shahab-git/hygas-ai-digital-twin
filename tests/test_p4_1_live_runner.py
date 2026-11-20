"""P4-1: python/live_runner.py. The numeric checks named in its docstring."""
import sys

import test_app_smoke as smoke

sys.path.insert(0, smoke.ROOT)
from python import fe_feed_handling as fe, live_runner, live_trace


def test_ticks_without_a_control_equal_the_plain_trace():
    r = live_runner.LiveRunner()
    for _ in range(6):
        r.tick()
    assert r.history[-1] == live_trace.run_trace(6)[-1]
    assert [h["cycle"] for h in r.history] == [1, 2, 3, 4, 5, 6]


def test_a_feed_change_reaches_the_next_row_and_hydrogen_within_a_cycle_or_two():
    r = live_runner.LiveRunner()
    for _ in range(8):
        r.tick()
    before = r.history[-1]
    assert before["feed_kg_h"] == fe.FE001_DEFAULT_DELIVERY_RATE_KG_H
    r.set_feed(50.0)
    rows = [r.tick() for _ in range(3)]
    assert rows[0]["feed_kg_h"] == 50.0
    assert rows[-1]["h2_kg_h"] > before["h2_kg_h"]
    r.set_feed(None)
    assert r.tick()["feed_kg_h"] == fe.FE001_DEFAULT_DELIVERY_RATE_KG_H


def test_advance_runs_the_due_cycles_with_a_cap_and_a_first_call_cycle():
    r = live_runner.LiveRunner(seconds_per_cycle=3.0)
    assert r.advance(100.0) == 1 and r.advance(101.0) == 0 and r.advance(103.2) == 1
    assert r.advance(10_000.0) == live_runner.MAX_CYCLES_PER_ADVANCE     # a long sleep does not trigger a long catch-up
    assert r.cycle == 1 + 1 + live_runner.MAX_CYCLES_PER_ADVANCE


def test_history_is_bounded_and_the_clock_label_counts_simulated_hours():
    r = live_runner.LiveRunner(history=4)
    for _ in range(26):
        r.tick()
    assert len(r.history) == 4 and r.history[0]["cycle"] == 23
    assert r.sim_clock_label() == "day 1 02:00"


def test_the_runner_does_not_touch_the_global_cycle_clock():
    from python import cycle_clock
    before = cycle_clock.hours_per_cycle()
    r = live_runner.LiveRunner()
    r.tick()
    assert cycle_clock.hours_per_cycle() == before
