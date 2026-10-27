import os
import sys

# Make `python.*` and `tests._fakes` importable regardless of the cwd pytest is
# started from, and make sure no test can ever write to a real database:
# HYGAS_ALLOW_DB_WRITES must be unset unless a test sets it on purpose.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for p in (ROOT, os.path.join(ROOT, "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)
os.environ.pop("HYGAS_ALLOW_DB_WRITES", None)
