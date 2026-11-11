"""P1-05(a): ONE hydrogen LHV (10.8 MJ/Nm3 = eu_utilities_chp.H2_LHV_MJ_PER_NM3) instead of 10.8 and 10.783.

The species table H2 entry now IS the constant, and balance_audit.efficiency_check reads the constant instead of repeating a literal. The two persisted entries that depend on the
H2 term of the SYNGAS LHV (EU-CHP|Dispatch total_syngas_kw / wgs_psa_claim_kw and the SA-006 reading) move by the same ratio; every other persisted value equals the 701de71 fixture
(the Gate 4 comparisons skip exactly these two keys through tests/_intentional_changes.py, so they are pinned here)."""
import gzip
import json
import os
import re

import pytest

from _fakes import FakeSupabase, patched_supabase
from _intentional_changes import INTENTIONAL
from python import eu_utilities_chp as eu
from python import tab1_integration as t1

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "snapshot_origin_main_701de71.json.gz")
OLD_H2 = 10.783          # the species-table value before P1-05(a)
KEYS = ("EU-CHP|Dispatch", "SA-006|Reading")


@pytest.fixture(scope="module")
def snap():
    # P1-05(b) (deliberate edit): these pins isolate the H2 LHV change, so the water molar mass is put back to its old 18.015 here (P1-05(b) moves the same entries by <= 7e-6 more;
    # tests/test_p1_05b_water_molar_mass.py pins that separately).
    from python import ga001_gasifier_model as ga
    from python import gasifier_mass_balance as gmb
    mp = pytest.MonkeyPatch()
    mp.setattr(ga, "M_H2O", 18.015)
    mp.setattr(gmb, "DEFAULT_DRY_FEED_KG_H", 41.67)         # P1-05(c) (deliberate edit): likewise the cycle-1 dry feed is put back to the old 41.67 (tests/test_p1_05c_feed_basis.py pins that change)
    try:
        with patched_supabase(FakeSupabase()):
            return t1.build_live_snapshot(20)[0]
    finally:
        mp.undo()


@pytest.fixture(scope="module")
def old():
    with gzip.open(FIXTURE, "rb") as fh:
        return json.loads(fh.read().decode("utf-8"))["default|20"]


def _approx_equal(a, b):
    """Exact for everything but floats; floats within 1e-12 relative (a last-bit difference between Python 3.11 and 3.12 sums is tolerated)."""
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return a == pytest.approx(b, rel=1e-12, abs=1e-15)
    if isinstance(a, dict) and isinstance(b, dict):
        return set(a) == set(b) and all(_approx_equal(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_approx_equal(x, y) for x, y in zip(a, b))
    return a == b


def test_there_is_one_hydrogen_lhv_and_the_audit_reads_it():
    assert eu.SYNGAS_SPECIES_LHV_MJ_PER_NM3["H2"] is eu.H2_LHV_MJ_PER_NM3 or eu.SYNGAS_SPECIES_LHV_MJ_PER_NM3["H2"] == eu.H2_LHV_MJ_PER_NM3 == 10.8
    src = open(os.path.join(ROOT, "python", "balance_audit.py"), encoding="utf-8").read()
    assert not re.search(r"NM3_PER_MOL \* 10\.8", src) and "eu.H2_LHV_MJ_PER_NM3" in src


def test_the_two_dependent_entries_are_intentional_exceptions_and_nothing_else_is():
    assert set(KEYS) <= set(INTENTIONAL)


def _lhv(snap, h2):
    g = snap[("GC-013", "Gas")]["value"]
    return (g["H2_mol_pct_dry"] * h2 + g["CO_mol_pct_dry"] * eu.SYNGAS_SPECIES_LHV_MJ_PER_NM3["CO"]
            + g["CH4_mol_pct_dry"] * eu.SYNGAS_SPECIES_LHV_MJ_PER_NM3["CH4"]) / 100.0


def test_sa006_reading_moved_by_exactly_the_h2_term(snap, old):
    new_v, old_v = snap[("SA-006", "Reading")]["value"], old["SA-006|Reading"]["value"]
    assert new_v == pytest.approx(_lhv(snap, 10.8), rel=1e-12)
    assert old_v == pytest.approx(_lhv(snap, OLD_H2), rel=1e-9)
    assert new_v / old_v == pytest.approx(_lhv(snap, 10.8) / _lhv(snap, OLD_H2), rel=1e-9)


def test_the_dispatch_entry_moved_only_in_the_two_syngas_fields_by_the_same_ratio(snap, old):
    ratio = _lhv(snap, 10.8) / _lhv(snap, OLD_H2)
    n, o = snap[("EU-CHP", "Dispatch")]["value"], old["EU-CHP|Dispatch"]["value"]
    assert set(n) == set(o)
    for k in o:
        if k in ("total_syngas_kw", "wgs_psa_claim_kw"):
            assert n[k] == pytest.approx(o[k] * ratio, rel=1e-9)
        else:
            assert _approx_equal(json.loads(json.dumps(n[k], default=str)), o[k]), k
    assert 1.0007 < ratio < 1.0008                      # +0.0745 %, the size quoted in the PR


LEGACY_REGASIFY_DEFAULT = True      # P1-06b: not yet exercised on the real default (heat_only): its moved-entry pins were measured on regasify; tests/conftest.py restores the old default for this module
