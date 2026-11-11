"""Operating-point study (P1-01, scripts/run_operating_point_study.py): a read-only scenario study of the engine's EXISTING levers.

Guards: the grid and the documented ranges are what the document says; the lever count and the in-range test are right; the "near the target" convention is
the stated +/-10 %; the default point of the study reproduces the engine's own default (78.0 kg/day) and the study's overrides do not leak into a later
default run; the script makes no database call. It does not run the 15-minute grid. Offline: counting fake store."""
import importlib.util
import os

import pytest

from _fakes import FakeSupabase, patched_supabase
from python import tab1_integration as t1

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(ROOT, "scripts", "run_operating_point_study.py")


@pytest.fixture(scope="module")
def study():
    spec = importlib.util.spec_from_file_location("run_operating_point_study", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_documented_ranges_are_the_stated_assumed_ranges(study):
    r = study.documented_ranges()
    for key, expect in (("er", (0.2125, 0.25, 0.2875)), ("steam", (0.34, 0.40, 0.46)), ("conv", (0.85, 0.90, 0.98))):
        assert r[key] == pytest.approx(expect, abs=1e-9), key


def test_grid_sizes(study):
    assert len(study.build_grid(quick=False)) == 2 * 3 * 3 * 3 * 2          # modes x ER x steam x conversion x PSA (model / fixed 75 %)
    assert len(study.build_grid(quick=True)) == 2 * (1 + 8 + 1)             # default point + 8 corners + PSA fixed, per mode
    assert len(study.out_of_range_cases()) == 2
    assert {c["mode"] for c in study.build_grid(False)} == {"regasify", "heat_only"}


def test_in_range_and_levers_moved(study):
    r = study.documented_ranges()
    default = {"mode": "regasify", "er": r["er"][1], "steam": r["steam"][1], "conv": r["conv"][1], "psa": None}
    assert study.in_range(default) and study.levers_moved(default) == 0
    assert study.levers_moved(dict(default, mode="heat_only")) == 1
    assert study.levers_moved(dict(default, mode="heat_only", psa=0.75)) == 2
    assert not study.in_range(dict(default, er=0.35)) and not study.in_range(dict(default, conv=0.7))
    assert all(not study.in_range(c) for c in study.out_of_range_cases())
    assert all(study.in_range(c) for c in study.build_grid(False))


def test_near_target_is_plus_minus_ten_percent_of_fifty(study):
    assert study.TARGET_KG_DAY == 50.0 and study.BAND == 0.10
    assert study.near_target(54.3) and study.near_target(45.0) and study.near_target(55.0)
    assert not study.near_target(78.0) and not study.near_target(44.9) and not study.near_target(55.1)


def test_summarise_uses_only_in_range_cases(study):
    res = [{"h2_kg_day": 40.0, "in_range": False}, {"h2_kg_day": 52.0, "in_range": True}, {"h2_kg_day": 78.0, "in_range": True}]
    s = study.summarise(res)
    assert s["n_in_range"] == 2 and s["min"]["h2_kg_day"] == 52.0 and s["max"]["h2_kg_day"] == 78.0 and len(s["near"]) == 1
    assert study.summarise([{"h2_kg_day": 1.0, "in_range": False}])["n_in_range"] == 0


def test_default_point_reproduces_the_engine_default_and_overrides_do_not_leak(study):
    """Pins the starting point quoted in docs/tail_gas_heat.md (78.0 kg/day) and shows the study leaves the engine's defaults alone."""
    r = study.documented_ranges()
    default = {"mode": "regasify", "er": r["er"][1], "steam": r["steam"][1], "conv": r["conv"][1], "psa": None}
    fake = FakeSupabase()
    with patched_supabase(fake):
        via_study = study.run_case(default)
        shifted = study.run_case(dict(default, mode="heat_only", psa=0.75))
        plain = t1.build_live_snapshot(n_cycles=study.N_CONV)[0]
    assert fake.calls == []
    h2_plain = 24.0 * float(plain[("HB-012", "Compressor")]["value"]["h2_kg_h"])
    assert via_study["h2_kg_day"] == pytest.approx(h2_plain, rel=1e-12)
    assert h2_plain == pytest.approx(78.0, abs=0.05)
    assert shifted["h2_kg_day"] == pytest.approx(54.3, abs=0.05) and shifted["levers_moved"] == 2
    assert shifted["psa_recovery_pct"] == pytest.approx(75.0, abs=1e-9)


LEGACY_REGASIFY_DEFAULT = True      # P1-06b: not yet exercised on the real default (heat_only): reproduces the engine default of the study (regasify); tests/conftest.py restores the old default for this module
