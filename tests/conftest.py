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


@pytest.fixture(autouse=True)
def _db_write_flag_is_off_for_every_test():
    """Reset the guard flag to "0" before each test. Some tests run scripts that pop the flag (scripts/run_*.py do
    `os.environ.pop("HYGAS_ALLOW_DB_WRITES", None)`) and nothing put it back, so the tests that assert it is "0" passed in the serial order only
    because test_store_read_guard.py happened to run before them; with pytest-xdist (CI-1) they failed on a worker that had not. Tests that need
    the flag ON or unset still set it themselves (monkeypatch), which is undone at the end of that test."""
    os.environ["HYGAS_ALLOW_DB_WRITES"] = "0"
    yield


@pytest.fixture(scope="session", autouse=True)
def _no_real_step_summary():
    """On GitHub Actions $GITHUB_STEP_SUMMARY is the real job summary; the driver appends to it when set. Unset it for the whole session
    (session scope, so it is also gone while module-scoped fixtures run the driver) so a CI test run cannot add test blocks to the real
    summary. Tests that exercise the summary set their own temp path with monkeypatch.setenv."""
    with pytest.MonkeyPatch.context() as mp:
        mp.delenv("GITHUB_STEP_SUMMARY", raising=False)
        yield


# P1-06h: the fixture that restored the old "regasify" tail-gas default for modules declaring LEGACY_REGASIFY_DEFAULT is gone (no module declares it any more). Every test runs on
# the real default ("heat_only" since P1-06); a test about the recycle selects "regasify" explicitly through the engine override.


# RFI2 (DOK-ING, 2026-11-25): the engine default is now the RFI2 basis (no gasifying agent, feed not dried, char-derived carbon conversion). The ~1000 older tests pin
# numbers and texts of the EARLIER basis (air at ER 0.25, feed dried to 1 %, conversion 0.90); they keep characterizing it by running with the earlier basis restored.
# A module that tests the new default declares `RFI2_DEFAULT = True` at module level and then runs on the real default. (Same pattern as the old LEGACY_REGASIFY_DEFAULT.)
@pytest.fixture(scope="module", autouse=True)
def _earlier_basis_unless_module_declares_rfi2_default(request):
    """Module scope on purpose: module-scoped fixtures of the older tests build snapshots before any function-scoped fixture runs."""
    if getattr(request.module, "RFI2_DEFAULT", False):
        yield
        return
    from python import fe_feed_handling, ga001_gasifier_model
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(ga001_gasifier_model, "GASIFYING_AGENT_DEFAULT", ga001_gasifier_model.AIR_AGENT)
        mp.setattr(fe_feed_handling, "FE005_DRYING_ACTIVE", True)
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
