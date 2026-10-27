import os
import socket
import sys

import pytest

# Make `python.*` and `tests._fakes` importable regardless of the cwd pytest is
# started from.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for p in (ROOT, os.path.join(ROOT, "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

# No test may write to a real database: the guard flag is forced OFF ("0"; only
# the exact value "1" enables writes). Tests that need it ON set it themselves.
os.environ["HYGAS_ALLOW_DB_WRITES"] = "0"


class RealSupabaseAttempt(BaseException):
    """Deliberately a BaseException so that the repo's own `except Exception`
    fallbacks cannot swallow it: a test that reaches a REAL Supabase client or
    host fails loudly."""


@pytest.fixture(autouse=True)
def _no_real_supabase(monkeypatch):
    """Fail any test that builds a real Supabase client or resolves a Supabase
    host (audit follow-up: 'fail the job if a test makes a Supabase network
    call'). The fake client in tests/_fakes.py is the only way to a 'database'."""
    import supabase
    from python import confirmation_loop, vendor_log

    def refuse(*args, **kwargs):
        raise RealSupabaseAttempt("a test tried to construct a REAL Supabase client")

    monkeypatch.setattr(supabase, "create_client", refuse)
    for module in (vendor_log, confirmation_loop):
        if hasattr(module, "create_client"):
            monkeypatch.setattr(module, "create_client", refuse)
        monkeypatch.setattr(module, "_client", None, raising=False)

    real_getaddrinfo = socket.getaddrinfo

    def guarded(host, *args, **kwargs):
        if "supabase" in str(host).lower():
            raise RealSupabaseAttempt(f"a test tried to resolve the Supabase host {host!r}")
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", guarded)
    yield
