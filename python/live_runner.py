"""P4-1: a resident, in-process "live" run of the unchanged engine, for the Summary tab's Live section. CLASS: simulated output of the quasi-steady
engine; no plant data, nothing validated, NOT the published hourly runtime (scripts/run_continuous_cycle.py + Supabase) and not connected to it.

What "live" means here, honestly: a LiveRunner keeps ONE registered engine and advances it by calling run_cycle() (the same unchanged method), either
on demand (`tick()`) or as many cycles as wall-clock time has elapsed (`advance(now_s)`, one cycle per `seconds_per_cycle`). One cycle is the model's
default step, ONE simulated hour (cycle_clock.hours_per_cycle(), this module never sets it), so at 3 s per cycle the simulated clock runs about 1200x
faster than the wall clock. The engine has no time-domain dynamics (CLAUDE.md, known limitations): a feed step shows up within one cycle, the hydrogen
storage level and other inventories accumulate per simulated hour. The operator control is the as-received feed rate (an Assumed what-if input, the same
FE-001 override pattern as live_trace); nothing else is controllable.

Numeric check (comment, project convention): after n ticks with no control, the last row equals live_trace.run_trace(n)'s last row (asserted in
tests/test_p4_1_live_runner.py); setting the feed changes feed_kg_h in the next row (asserted there as well).
"""
import collections

from . import fe_feed_handling as fe
from . import live_trace
from . import plant_status as ps
from . import sim_sections
from . import tab1_integration as t1

FEED_KEY = ("FE-001-INPUT", "msw_delivery_rate_kg_h")
DEFAULT_SECONDS_PER_CYCLE = 3.0
MAX_CYCLES_PER_ADVANCE = 5      # a browser tab that slept does not trigger a long catch-up
HISTORY = 120
SIM_START = (2026, 1, 1)         # the simulated clock's origin: a fixed label, not a real date


class LiveRunner:
    def __init__(self, seconds_per_cycle=DEFAULT_SECONDS_PER_CYCLE, history=HISTORY):
        self.seconds_per_cycle = float(seconds_per_cycle)
        self.history = collections.deque(maxlen=int(history))
        self.section_history = collections.deque(maxlen=int(history))      # per-section series for the Simulation tab (python/sim_sections.py)
        self.feed_kg_h = None            # None = the nominal as-received feed (no override)
        self._state, self._engine = t1.build_engine(overrides={FEED_KEY: self._feed_fn})
        self.cycle = 0
        self._last_s = None              # wall-clock seconds at the last advance()

    def _feed_fn(self, get_input):
        v = fe.FE001_DEFAULT_DELIVERY_RATE_KG_H if self.feed_kg_h is None else float(self.feed_kg_h)
        return {"value": v, "status": ps.STATUS_ASSUMED, "inputs": [], "validation_basis": ps.VALIDATION_NA,
                "confidence_note": "Feed rate of the Live section (Assumed what-if input)."}

    def set_feed(self, kg_h):
        """The as-received feed for the following cycles; None restores the nominal."""
        self.feed_kg_h = None if kg_h is None else float(kg_h)

    def sim_clock_label(self):
        """'Day D hh:00' of the simulated clock (cycle N = N simulated hours after the start)."""
        return f"day {self.cycle // 24} {self.cycle % 24:02d}:00"

    def tick(self):
        """Runs exactly one cycle and returns its row (also appended to `history`)."""
        self.cycle += 1
        self._engine.run_cycle(now=f"{SIM_START[0]}-{SIM_START[1]:02d}-{SIM_START[2]:02d}T{(self.cycle - 1) % 24:02d}:00:00Z")
        snap = self._state.get_snapshot()
        row = live_trace.row_from_snapshot(self.cycle, snap)
        self.history.append(row)
        self.section_history.append({"cycle": self.cycle, **sim_sections.extract_all(snap)})
        return row

    def advance(self, now_s):
        """Runs the cycles due since the last call (at least one on the first call), at most MAX_CYCLES_PER_ADVANCE. now_s: wall-clock seconds."""
        if self._last_s is None:
            due = 1
        else:
            due = int((now_s - self._last_s) // self.seconds_per_cycle)
        due = max(0, min(due, MAX_CYCLES_PER_ADVANCE))
        if due:
            self._last_s = now_s if self._last_s is None or due == MAX_CYCLES_PER_ADVANCE else self._last_s + due * self.seconds_per_cycle
        for _ in range(due):
            self.tick()
        return due

    def snapshot(self):
        return self._state.get_snapshot()
