"""Nothing moved (task A10): the maturity labels, the gate and the captions change no persisted value. Every entry of both tail_gas_modes equals the unmodified origin/main snapshot
(tests/fixtures/snapshot_origin_main_701de71.json.gz), the persisted key count is unchanged, and no database or network call is made. Offline: counting fake store.

D2 (task A3, merged) and W1 (wording pass): phrase pairs in the entries listed in tests/_d2_wording.py were reworded because they called Unverified registry values "Confirmed" (or
"independently validated"). The 701de71 fixture is the OLD text, so the comparison is made against the fixture with exactly those pairs applied FORWARD (old text -> new text, _d2_wording.forward).
The live snapshot must equal that expectation: if an old phrase comes back, or any other text or number changes, the comparison fails (test_the_mapped_comparison_fails_...)."""
import gzip
import json
import math
import os

import pytest

import _d2_wording
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


def _expected(old):
    """The 701de71 entries as they must read now: the phrase pairs of tests/_d2_wording applied forward (old -> new) in the entries that carry them, every other entry exactly as stored."""
    return _d2_wording.forward(old)


def _differences(expected, new):
    bad = {k: _same(expected[k], new[k]) for k in expected if k != "GA-001-INPUT|tail_gas_mode"}
    return {k: v for k, v in bad.items() if v is not True}


@pytest.fixture(scope="module")
def fake():
    return FakeSupabase()


def _live(fake, mode):
    with patched_supabase(fake):
        snap = t1.build_live_snapshot(20, overrides=None if mode == "default" else {("GA-001-INPUT", "tail_gas_mode"): _const("heat_only")})[0]
    return _ser(snap)


def _old(key):
    with gzip.open(FIXTURE, "rb") as fh:
        return json.loads(fh.read().decode("utf-8"))[key]


@pytest.mark.parametrize("mode,key", [("default", "default|20"), ("heat_only", "heat_only|20")])
def test_every_persisted_entry_equals_origin_main_and_the_key_count_is_unchanged(fake, mode, key):
    old = _old(key)
    new = _live(fake, mode)
    assert set(new) == set(old) and len(new) == 121
    expected = _expected(old)
    text = json.dumps(expected)
    assert all(n in text for n, _ in _d2_wording.PAIRS), "the mapping is not vacuous: each of the four new phrases is in the expectation"
    assert not any(o in json.dumps(new) for _, o in _d2_wording.PAIRS), "no old phrase is in the live snapshot"
    # OLD assertion: bad = {k: _same(old[k], new[k]) ...} == {} (the fixture as stored, before D2). NEW: the same comparison, against the fixture with the four D2 pairs applied.
    assert _differences(expected, new) == {}


def test_the_mapped_comparison_fails_if_the_old_phrase_returns_or_any_other_text_or_number_changes(fake):
    import copy
    old = _old("default|20")
    new = _live(fake, "default")
    expected = _expected(old)
    assert _differences(expected, new) == {}

    for n, o in _d2_wording.PAIRS:                                   # 1) each old phrase coming back
        back = json.loads(json.dumps(new).replace(n, o))
        assert back != new, n
        assert _differences(expected, back), f"the old phrase {o!r} came back and the comparison did not notice"
    assert _differences(expected, _d2_wording.undo(new))             # all four at once (what the old, unmapped fixture expected)

    other = copy.deepcopy(new)                                       # 2) one character of other text, in a D2 entry and in a non-D2 entry
    other["EU-008|RecommendedCapacityEstimate"]["confidence_note"] += "x"
    assert _differences(expected, other)
    other = copy.deepcopy(new)
    other["HB-013|Storage"]["confidence_note"] += "x"
    assert _differences(expected, other)

    num = copy.deepcopy(new)                                         # 3) a number: 1e-9 relative fails, 1e-13 (a 3.11 last-bit difference) passes
    v = num["HB-013|Storage"]["value"]["level_kg"]
    num["HB-013|Storage"]["value"]["level_kg"] = v * (1.0 + 1e-9)
    assert _differences(expected, num)
    num["HB-013|Storage"]["value"]["level_kg"] = v * (1.0 + 1e-13)
    assert _differences(expected, num) == {}


def test_no_database_or_network_call_was_made(fake):
    assert [c for c in fake.calls if c[0] != "select"] == []
