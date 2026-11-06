"""
Cross-module disagreement figures (G5-07) -- READ-ONLY, offline.

Runs the existing engine in-process (tab1_integration.build_live_snapshot, 30 cycles, defaults) against the in-memory fake store of tests/_fakes.py: no
database, no network, the real secrets.toml is never read. Prints the live figures next to the registry / DOK-ING figures they disagree with
(python/disagreement_rows.py). Nothing is tuned and no value is chosen from a difference.

    python scripts/run_disagreement_report.py             (from the repo root, about 1 minute)
"""
import os
import socket
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
if os.environ.get("HYGAS_ALLOW_DB_WRITES") == "1":
    sys.exit("Refusing to run: HYGAS_ALLOW_DB_WRITES=1 is set. This script never writes to a database; unset it.")

from _fakes import FakeSupabase, patched_supabase       # noqa: E402
from python import cycle_clock, disagreement_rows as dr, tab1_integration as t1   # noqa: E402

_real_getaddrinfo = socket.getaddrinfo


def _guard(host, *a, **k):
    if "supabase" in str(host).lower():
        raise RuntimeError(f"offline script refused to resolve {host!r}")
    return _real_getaddrinfo(host, *a, **k)


socket.getaddrinfo = _guard


def main():
    cycle_clock.set_elapsed_hours(None)
    with patched_supabase(FakeSupabase()):
        snap = t1.build_live_snapshot(n_cycles=30)[0]
    print(dr.format_table(dr.rows(snap, dr.load_registry())))
    print("\nNo tolerance is set: a difference is reported, not judged. Registry values are 'Unverified (registry)' unless a DOK-ING line says otherwise.")


if __name__ == "__main__":
    main()
