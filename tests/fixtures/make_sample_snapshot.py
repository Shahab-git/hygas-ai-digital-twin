"""Regenerates tests/fixtures/sample_snapshot.json from an OFFLINE engine run
(tab1_integration.build_live_snapshot(), 5 cycles, no database).

THIS IS A TEST FIXTURE, NOT PLANT DATA. It is a trimmed copy of a synthetic,
simulated snapshot (confidence_note text removed to keep it small) used only to
exercise Tab 2's counting logic on a stored sample. Run from the repo root:
    python tests/fixtures/make_sample_snapshot.py
"""
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
from _fakes import FakeSupabase, patched_supabase  # noqa: E402
from python import tab1_integration  # noqa: E402

with patched_supabase(FakeSupabase()):
    snap, _state, _engine = tab1_integration.build_live_snapshot()

out = []
for (eq, cat), entry in sorted(snap.items(), key=lambda kv: str(kv[0])):
    e = tab1_integration._native(entry)
    e["confidence_note"] = ""      # trimmed on purpose
    out.append({"key": [eq, cat], "entry": e})
doc = {"_comment": "TEST FIXTURE, NOT PLANT DATA: trimmed copy of an offline simulated snapshot "
                   "(build_live_snapshot(), 5 cycles). Regenerate with tests/fixtures/make_sample_snapshot.py.",
       "entries": out}
path = os.path.join(ROOT, "tests", "fixtures", "sample_snapshot.json")
with open(path, "w", encoding="utf-8") as f:
    json.dump(doc, f, ensure_ascii=False, default=float, separators=(",", ":"))
print("entries:", len(out), "| bytes:", os.path.getsize(path))
