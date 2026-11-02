"""Nothing moved (task A10): the maturity labels, the gate and the captions change no persisted value. Every entry of both tail_gas_modes equals the unmodified origin/main snapshot
(tests/fixtures/snapshot_origin_main_701de71.json.gz), the persisted key count is unchanged, and no database or network call is made. Offline: counting fake store."""
import gzip
import json
import math
import os

import pytest

from _fakes import FakeSupabase, patched_supabase
from python import plant_status as ps
from python import tab1_integration as t1

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "snapshot_origin_main_701de71.json.gz")


def _const(v):
    def fn(get_input):
        return {"value": v, "status": ps.STATUS_ASSUMED, "inputs": [], "validation_basis": ps.VALIDATION_NA, "confidence_note": "test"}
    return fn


def _ser(snapshot):
    return {f"{k[0]}|{k[1]}": json.loads(json.dumps(v, sort_keys=True, default=str)) for k, v in snapshot.items()}


def _same(a, b, path=""):
    if isinstance(a, float) or isinstance(b, float):
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-15) or [path]
        return [path]
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            return [path + "/<keys>"]
        bad = []
        for k in a:
            r = _same(a[k], b[k], f"{path}/{k}")
            bad += [] if r is True else r
        return bad or True
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [path + "/<len>"]
        bad = []
        for i, (x, y) in enumerate(zip(a, b)):
            r = _same(x, y, f"{path}[{i}]")
            bad += [] if r is True else r
        return bad or True
    return True if a == b else [path]


@pytest.fixture(scope="module")
def fake():
    return FakeSupabase()


@pytest.mark.parametrize("mode,key", [("default", "default|20"), ("heat_only", "heat_only|20")])
def test_every_persisted_entry_equals_origin_main_and_the_key_count_is_unchanged(fake, mode, key):
    with gzip.open(FIXTURE, "rb") as fh:
        old = json.loads(fh.read().decode("utf-8"))[key]
    with patched_supabase(fake):
        snap = t1.build_live_snapshot(20, overrides=None if mode == "default" else {("GA-001-INPUT", "tail_gas_mode"): _const("heat_only")})[0]
    new = _ser(snap)
    assert set(new) == set(old) and len(new) == 121
    bad = {k: _same(old[k], new[k]) for k in old if k != "GA-001-INPUT|tail_gas_mode"}
    assert {k: v for k, v in bad.items() if v is not True} == {}


def test_no_database_or_network_call_was_made(fake):
    assert [c for c in fake.calls if c[0] != "select"] == []
