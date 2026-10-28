"""The test suite must never write to the real job summary.

On GitHub Actions $GITHUB_STEP_SUMMARY points at the real summary of the job and the driver appends to it when it is set. tests/conftest.py unsets
it for the whole session. This proves it from OUTSIDE the suite's fixtures: a child pytest process is started with the variable set to a real
temp file (already holding a marker), runs the driver tests, and the file must come back byte-for-byte unchanged. No database, no network.
"""
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MARKER = b"### marker written by the parent test, before the child suite ran\n"


def _child_suite(summary_path):
    env = dict(os.environ, GITHUB_STEP_SUMMARY=str(summary_path))
    # 7d runs the driver through the module-scoped `seeded_rows` fixture (the case a function-scoped guard would miss); 8c runs it without
    # setting the variable itself. The 8a/8b tests set their own temp path on purpose and are not selected.
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_store_read_guard.py", "-k", "test_7d or test_8c"],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=300)


def test_the_suite_never_writes_to_the_real_step_summary(tmp_path):
    summary = tmp_path / "real_job_summary.md"
    summary.write_bytes(MARKER)
    result = _child_suite(summary)
    assert result.returncode == 0, result.stdout[-800:] + result.stderr[-400:]
    assert "2 passed" in result.stdout, result.stdout[-400:]               # the driver tests really ran (and drove main())
    assert summary.read_bytes() == MARKER, "the suite wrote into $GITHUB_STEP_SUMMARY"


def test_the_variable_is_unset_while_the_suite_runs():
    assert "GITHUB_STEP_SUMMARY" not in os.environ
