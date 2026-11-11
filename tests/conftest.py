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


@pytest.fixture(scope="session", autouse=True)
def _no_real_step_summary():
    """On GitHub Actions $GITHUB_STEP_SUMMARY is the real job summary; the driver appends to it when set. Unset it for the whole session
    (session scope, so it is also gone while module-scoped fixtures run the driver) so a CI test run cannot add test blocks to the real
    summary. Tests that exercise the summary set their own temp path with monkeypatch.setenv."""
    with pytest.MonkeyPatch.context() as mp:
        mp.delenv("GITHUB_STEP_SUMMARY", raising=False)
        yield


@pytest.fixture(scope="module", autouse=True)
def _legacy_tail_gas_default(request):
    """P1-06 (owner decision 2026-11-10) made "heat_only" the engine default; P1-06b inverted the arrangement of that task. Every test module runs on the REAL default unless it
    declares `LEGACY_REGASIFY_DEFAULT = True` at module level, with the reason next to the line. Such a module was written and its fixtures and pins were measured on the "regasify"
    path that used to be the default, and is run with that default restored (module scope, so module-scoped snapshot fixtures see it). The list of declaring modules is the list of
    what is still NOT exercised on the real default (docs/phase0_gate_record.md section 3l); tests/test_p1_06_tail_gas_default.py proves that the restored default is the only
    difference (with it the snapshot equals the committed pre-flip fixture) and pins the real default as "heat_only"."""
    if not getattr(request.module, "LEGACY_REGASIFY_DEFAULT", False):
        yield
        return
    from python import ga001_gasifier_model as ga
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(ga, "TAIL_GAS_MODE_DEFAULT", "regasify")
        yield


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
