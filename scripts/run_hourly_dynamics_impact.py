"""
DYN-1: how much would the Assumed lags of python/dynamics.py change what the HOURLY runtime publishes? -- READ-ONLY, offline, writes nothing.

The hourly runtime is quasi-steady (one engine cycle per ~1 h). python/dynamics.py adds Assumed first-order lags (tau_conv 1200 s, tau_gas 30 s, T_gasifier 120 s, recycle delay). This script runs the dynamics layer at the
runtime's own step (dt = 3600 s) twice, lags OFF (all taus 0) and lags ON (the Assumed defaults), for a step applied at hour 1, and prints the per-hour percentage difference of the published values. It also prints the
analytic residual exp(-dt/tau) of each lag after one hourly step. The comparison isolates the four gas/feed/temperature/recycle lags: both runs share the engine's own one-cycle couplings and the EU-008 cooling-water damping (listed in the residual table, 50 % per hour by design, an engine property that is on in both runs), which are identical.

    python scripts/run_hourly_dynamics_impact.py            (about 1 minute; feed -20 %, ER 0.25 -> 0.28, T 950 -> 900 degC)

CONCLUSION it supports (docs/dynamics_hourly_impact.md): at an hourly step the lags change a published value by at most about 1.3 %, for one cycle after a FEED step, and not at all after an ER or T step, so wiring them into the
hourly runtime would not change what is published in any way worth a state-persistence change. The result depends on the ASSUMED time constants (nothing here is validated against plant data) and on the hourly cadence: a
sub-hour cadence is a different question.
"""
import math
import os
import socket
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
os.environ.pop("HYGAS_ALLOW_DB_WRITES", None)

from _fakes import FakeSupabase, patched_supabase       # noqa: E402
from python import dynamics as dyn                      # noqa: E402

_real = socket.getaddrinfo


def _guard(host, *a, **k):
    if "supabase" in str(host).lower():
        raise RuntimeError(f"offline script refused to resolve {host!r}")
    return _real(host, *a, **k)


socket.getaddrinfo = _guard

DT_S = 3600.0
COLUMNS = ("h2_production_kg_h", "ga001_dry_flow_nm3_h", "H2_pct_dry")
LAGS_OFF = {"T_gasifier": 0, "tau_conv": 0, "tau_gas": 0, "tau_rec": 0}
SCENARIOS = {
    "feed -20 %": [{"t_s": 3600, "feed_rel": -0.20}],
    "ER 0.25 -> 0.28": [{"t_s": 3600, "ER": 0.28}],
    "T 950 -> 900 degC": [{"t_s": 3600, "T_setpoint_C": 900}],
}


def residual_after_one_step(dt_s=DT_S):
    """{tau name: fraction of a step still unrealised after one dt} = exp(-dt/tau), for the Assumed defaults (tau <= 0 means no lag)."""
    return {n: (math.exp(-dt_s / s.default_s) if s.default_s > 0 else 0.0) for n, s in dyn.TAU_SPECS.items()}


def impact(scenario, hours=8):
    """{column: [percent difference lags-on vs lags-off at each hourly row]} (row 0 is the steady start)."""
    with patched_supabase(FakeSupabase()):
        off = dyn.run_transient(scenario, dt_s=DT_S, duration_s=hours * DT_S, taus=LAGS_OFF)
        on = dyn.run_transient(scenario, dt_s=DT_S, duration_s=hours * DT_S)
    out = {}
    for col in COLUMNS:
        a, b = off.column(col), on.column(col)
        out[col] = [100.0 * (y - x) / x for x, y in zip(a, b)]
    return out


def main():
    print("Residual of each Assumed lag after one hourly step, exp(-3600 s / tau):")
    for n, r in residual_after_one_step().items():
        print(f"  {n:11s} tau = {dyn.TAU_SPECS[n].default_s:7.0f} s   {100 * r:7.3f} %")
    for name, sc in SCENARIOS.items():
        res = impact(sc)
        print(f"\n{name} (step applied at hour 1): lags ON vs OFF, percent, rows = hour 0..8")
        for col, v in res.items():
            print(f"  {col:22s} " + " ".join(f"{x:+6.2f}" for x in v) + f"   max |.| = {max(abs(x) for x in v):.2f} %")


if __name__ == "__main__":
    main()
