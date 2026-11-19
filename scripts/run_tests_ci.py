"""CI test runner: the same tests as `python -m pytest -q tests`, in two steps so the hosted runner finishes well inside its time limit.

Step 1 runs, serially and in file-name order, every test file that renders the Streamlit app or loads app.py with runpy (the files for which
test order matters: the repository's known test-pollution rule, see CLAUDE.md). Step 2 runs all other test files in parallel with pytest-xdist
(`-n 2 --dist loadfile`, one file never split across workers). If pytest-xdist is not installed, step 2 runs serially, so the script
works anywhere and only gets faster where xdist exists. A plain `python -m pytest -q tests` still works and runs the same tests.

Measured in a 2-core container on Python 3.12: serial 1202 s; this split 707 s (184 s + 523 s), 1186 passed and 6 skipped in both.
Plain `-n 2` over the whole suite was tried and is NOT used: it gave 15 failures and 11 errors (app tests depend on order).
"""
import importlib.util
import os
import re
import subprocess
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
TESTS = os.path.join(ROOT, "tests")
ORDER_SENSITIVE = re.compile(r"AppTest|runpy|test_app_smoke|from streamlit")


def split_test_files(tests_dir=TESTS):
    """-> (order_sensitive_files, other_files), both sorted, covering every tests/test_*.py exactly once."""
    names = sorted(n for n in os.listdir(tests_dir) if n.startswith("test_") and n.endswith(".py"))
    first, rest = [], []
    for n in names:
        with open(os.path.join(tests_dir, n), encoding="utf-8") as fh:
            (first if ORDER_SENSITIVE.search(fh.read()) else rest).append(os.path.join("tests", n))
    return first, rest


def main(argv=None):
    extra = list(sys.argv[1:] if argv is None else argv)
    first, rest = split_test_files()
    base = [sys.executable, "-m", "pytest", "-q"] + extra
    code1 = subprocess.call(base + first, cwd=ROOT)
    parallel = ["-n", "2", "--dist", "loadfile"] if importlib.util.find_spec("xdist") else []
    code2 = subprocess.call(base + parallel + rest, cwd=ROOT)
    return code1 or code2


if __name__ == "__main__":
    sys.exit(main())
