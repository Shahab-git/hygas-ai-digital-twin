"""P1-06 (owner decision 2026-11-10): the engine's default tail-gas mode is "heat_only" (the PSA tail gas is a heat source; nothing is re-gasified), no longer "regasify".

REAL_TAIL_GAS_DEFAULT = True below tells tests/conftest.py NOT to restore the old default for this module. Pins (1) the constant and that both modes stay selectable; (2) ATTRIBUTION: with the
old default put back the snapshot equals the committed pre-flip fixture (tests/fixtures/snapshot_origin_main_8282f4a.json.gz, origin/main after P1-05(c)) in every entry; (3) the new default
snapshot equals that fixture's explicit heat_only runs in every entry except the mode switch's own note; (4) the headline hydrogen (78.0 -> 55.7 kg/day); (5) nothing was tuned: every other
Assumed default is unchanged."""
import gzip
import json
import os
import re

import pytest

REAL_TAIL_GAS_DEFAULT = True

from _fakes import FakeSupabase, patched_supabase
from python import ga001_gasifier_model as ga
from python import tab1_integration as t1
from test_tail_gas_mode import _mode

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "snapshot_origin_main_8282f4a.json.gz")
SWITCH = "GA-001-INPUT|tail_gas_mode"
RUNS = (5, 20, 30)
_LONG_FLOAT = re.compile(r"-?\d+\.\d{9,}(?:e[-+]?\d+)?")


def _norm(text):
    return _LONG_FLOAT.sub(lambda m: f"{float(m.group()):.9g}", text)


def _flat(v, p=""):
    out = {}
    if isinstance(v, dict):
        for k, x in v.items():
            out.update(_flat(x, f"{p}.{k}"))
    elif isinstance(v, list):
        for i, x in enumerate(v):
            out.update(_flat(x, f"{p}[{i}]"))
    else:
        out[p] = float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else (_norm(v) if isinstance(v, str) else v)
    return out


def _differs(a, b):
    fa, fb = _flat(a), _flat(b)
    if set(fa) != set(fb):
        return True
    for p, x in fa.items():
        y = fb[p]
        if isinstance(x, float) and isinstance(y, float):
            if abs(x - y) > 1e-12 * max(1.0, abs(x)):
                return True
        elif x != y:
            return True
    return False


def _ser(snap):
    return {f"{k[0]}|{k[1]}": json.loads(json.dumps(v, sort_keys=True, default=str)) for k, v in snap.items()}


def _run(n, mode=None):
    with patched_supabase(FakeSupabase()):
        return _ser(t1.build_live_snapshot(n_cycles=n, overrides=None if mode is None else _mode(mode))[0])


@pytest.fixture(scope="module")
def fixture_entries():
    with gzip.open(FIXTURE, "rb") as fh:
        return json.loads(fh.read().decode("utf-8"))


@pytest.fixture(scope="module")
def new_default():
    return {n: _run(n) for n in RUNS}


@pytest.fixture(scope="module")
def old_default():
    mp = pytest.MonkeyPatch()
    mp.setattr(ga, "TAIL_GAS_MODE_DEFAULT", "regasify")
    try:
        return {n: _run(n) for n in RUNS}
    finally:
        mp.undo()


def test_the_default_is_heat_only_and_both_modes_stay_selectable():
    assert ga.TAIL_GAS_MODE_DEFAULT == "heat_only" and ga.TAIL_GAS_MODES == ("regasify", "heat_only")
    assert ga.check_tail_gas_mode("regasify") == "regasify" and ga.check_tail_gas_mode("heat_only") == "heat_only"
    with pytest.raises(ValueError):
        ga.check_tail_gas_mode("recycle")


@pytest.mark.parametrize("n", RUNS)
def test_with_the_old_default_the_snapshot_equals_the_pre_flip_fixture_so_the_flip_is_the_only_cause(old_default, fixture_entries, n):
    fx = fixture_entries[f"default|{n}"]
    assert set(fx) == set(old_default[n])
    assert [k for k, e in fx.items() if k != SWITCH and _differs(e, old_default[n][k])] == []          # the switch entry only differs in its note (the default is named there)


@pytest.mark.parametrize("n", RUNS)
def test_the_new_default_equals_the_explicit_heat_only_run_except_the_switch_entry(new_default, fixture_entries, n):
    fx = fixture_entries[f"heat_only|{n}"]
    moved = [k for k, e in fx.items() if _differs(e, new_default[n][k])]
    assert moved == [SWITCH] or moved == [], moved          # only the switch's own entry (its note) may differ


@pytest.mark.parametrize("n", RUNS)
def test_the_explicit_modes_still_give_the_same_entries_as_before(fixture_entries, n):
    got = _run(n, "heat_only")
    fx = fixture_entries[f"heat_only|{n}"]
    assert [k for k, e in fx.items() if _differs(e, got[k])] == []


def test_how_many_entries_the_flip_moves(new_default, fixture_entries):
    moved = {n: {k for k, e in fixture_entries[f"default|{n}"].items() if _differs(e, new_default[n][k])} for n in RUNS}
    assert (len(moved[5]), len(moved[20]), len(moved[30])) == (50, 50, 49)
    assert "GA-001|Outputs" in moved[30] and "HB-012|Compressor" in moved[30]


def test_the_headline_hydrogen_moves_from_78_to_55_7_kg_per_day(new_default, fixture_entries):
    old = fixture_entries["default|30"]["HB-012|Compressor"]["value"]["h2_kg_h"] * 24.0
    new = new_default[30]["HB-012|Compressor"]["value"]["h2_kg_h"] * 24.0
    assert old == pytest.approx(78.0, abs=0.05) and new == pytest.approx(55.7, abs=0.05)
    assert new < old and new / 50.0 == pytest.approx(1.11, abs=0.01)       # still about 11 % above DOK-ING's "about 50"; not tuned


def test_nothing_else_was_tuned():
    assert ga.CARBON_CONVERSION_EFFICIENCY == 0.90
    assert ga.CARBON_BLACK_SPLIT_DEFAULT == 1.0


def test_the_switch_entry_names_the_new_default(new_default):
    e = new_default[5][SWITCH]
    assert e["value"] == "heat_only" and "since P1-06" in e["confidence_note"] and "Default unchanged" not in e["confidence_note"]
