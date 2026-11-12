"""
A4.4: the sensitivity of the GA-001 enthalpy residual to the imposed gas temperature -- READ-ONLY, offline.

Runs the unchanged engine in-process (tab1_integration.build_live_snapshot) against the in-memory fake store of tests/_fakes.py (no database, no network, HYGAS_ALLOW_DB_WRITES unset), once per temperature with
("GA-001-INPUT", "operating_temperature_C") overridden, and prints the table of python/gasifier_enthalpy.temperature_sensitivity at the chosen LHV case(s). Writes nothing.

    python scripts/run_enthalpy_temperature_sensitivity.py                       (heat_only, 850..950 degC step 25, LHV 15 / 17.5 / 20 MJ/kg)
    python scripts/run_enthalpy_temperature_sensitivity.py --mode regasify --temps 850 900 950 --lhv 17.5

NOT a prediction of the temperature the plant would settle at and NOT validation against DOK-ING data: the temperature is imposed, GA-001 has no energy balance, and 950 degC is an Assumed registry value.
"""
import argparse
import os
import socket
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
os.environ.pop("HYGAS_ALLOW_DB_WRITES", None)

from _fakes import FakeSupabase, patched_supabase       # noqa: E402
from python import cycle_clock                          # noqa: E402
from python import gasifier_enthalpy as ge              # noqa: E402
from python import plant_status as ps                   # noqa: E402
from python import tab1_integration as t1               # noqa: E402

_real = socket.getaddrinfo


def _guard(host, *a, **k):
    if "supabase" in str(host).lower():
        raise RuntimeError(f"offline script refused to resolve {host!r}")
    return _real(host, *a, **k)


socket.getaddrinfo = _guard
N_CONV = 20             # the tail-gas recycle has converged by cycle 20


def _const(value):
    def fn(get_input):
        return {"value": value, "status": ps.STATUS_ASSUMED, "inputs": [], "validation_basis": ps.VALIDATION_NA, "confidence_note": "A4.4 sensitivity run"}
    return fn


def build(temps, mode):
    cycle_clock.set_elapsed_hours(None)
    out = {}
    with patched_supabase(FakeSupabase()):
        for t in temps:
            ov = {("GA-001-INPUT", "operating_temperature_C"): _const(float(t)), ("GA-001-INPUT", "tail_gas_mode"): _const(mode)}
            out[float(t)] = (t1.build_live_snapshot(n_cycles=N_CONV, overrides=ov)[0], t1.build_live_snapshot(n_cycles=N_CONV - 1, overrides=ov)[0])
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=("heat_only", "regasify"), default="heat_only")
    ap.add_argument("--temps", type=float, nargs="+", default=[850.0, 875.0, 900.0, 925.0, 950.0])
    ap.add_argument("--lhv", type=float, nargs="+", default=[15.0, 17.5, 20.0])
    a = ap.parse_args(argv)
    snaps = build(a.temps, a.mode)
    print(f"tail_gas_mode = {a.mode}; READ-ONLY; not a prediction, not validation against DOK-ING data")
    for lhv in a.lhv:
        print(f"\nLHV {lhv} MJ/kg dry")
        print("| T (degC) | residual (kW) | formation (kW) | sensible (kW) | audit duty (kW) | unexplained (kW) | H2 (mol% dry) | dry flow (Nm3/h) | change per 100 K (kW) |")
        print("|---|---|---|---|---|---|---|---|---|")
        for r in ge.temperature_sensitivity(snaps, lhv):
            sl = "" if r["slope_kw_per_100k"] is None else f"{r['slope_kw_per_100k']:+.3f}"
            print(f"| {r['t_c']:.0f} | {r['residual_kw']:+.3f} | {r['formation_kw']:+.3f} | {r['sensible_kw']:+.3f} | {r['audit_implied_duty_kw']:+.3f} | {r['difference_unexplained_kw']:+.1e} | {r['h2_mol_pct_dry']:.3f} | {r['dry_flow_nm3_h']:.3f} | {sl} |")


if __name__ == "__main__":
    main()
