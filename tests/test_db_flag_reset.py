"""The conftest resets HYGAS_ALLOW_DB_WRITES to "0" before every test, so a test that pops it (as the scripts/run_*.py scripts do on import)
cannot make a later test see None. The first test pollutes on purpose; the second runs after it in the same file (same worker, also under xdist)."""
import os


def test_a_test_that_pops_the_flag_leaves_it_unset_for_itself_only():
    os.environ.pop("HYGAS_ALLOW_DB_WRITES", None)
    assert os.environ.get("HYGAS_ALLOW_DB_WRITES") is None


def test_the_next_test_sees_the_flag_off_again():
    assert os.environ.get("HYGAS_ALLOW_DB_WRITES") == "0"
