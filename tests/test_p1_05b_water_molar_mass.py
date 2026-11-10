"""P1-05(b): the molar mass of water is computed from the atomic masses (M_H2O = 2 M_H + M_O = 18.016), not a separate literal 18.015 (5.5e-5 lower).

Pins (1) the constant and its consistency with the audit's atom-sum route; (2) ATTRIBUTION: with M_H2O put back to 18.015 the live snapshot equals the 701de71 fixture again (values, status, unit,
inputs; floats within 1e-12) except the keys other decisions moved on purpose (P1-05(a) H2 LHV, P1-12 HB-010 Separation) and keys the fixture does not have; (3) the exact set of persisted
entries that move because of the change, in both tail-gas modes, and the largest relative move (7e-5 default, 3.6e-4 heat_only energy report); (4) HB-005 steam moves by about the molar-mass ratio."""
import gzip
import json
import os

import pytest

from _fakes import FakeSupabase, patched_supabase
import _d2_wording
from _intentional_changes import INTENTIONAL, P1_05B_KEYS
from python import balance_audit as ba
from python import ga001_gasifier_model as ga
from python import tab1_integration as t1
from test_tail_gas_mode import _mode

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "snapshot_origin_main_701de71.json.gz")
OLD_M_H2O = 18.015
OTHER_DECISIONS = ("EU-CHP|Dispatch", "SA-006|Reading", "HB-010|Separation")        # moved on purpose by P1-05(a) and P1-12; their own pins cover them

MOVED_DEFAULT = (
    "AI-007|ScadaSnapshot",
    "AI-011|LoggingStatus",
    "EU-007|Flare",
    "EU-008|ConsumerAdequacy",
    "EU-008|CoolingSupply",
    "EU-008|RecommendedCapacityEstimate",
    "EU-009|GridBalance",
    "EU-010|UPS",
    "EU-CHP|Dispatch",
    "GA-001|AgentConsistency",
    "GA-001|CarbonAccounting",
    "GA-001|EnergyBalance",
    "GA-001|Outputs",
    "GC-001|Gas",
    "GC-003|Gas",
    "GC-004|Condensed water",
    "GC-004|Cooling duty",
    "GC-004|Gas",
    "GC-007|Blowdown",
    "GC-008|Blowdown",
    "GC-009|Blowdown",
    "GC-013|Fan power",
    "GC-013|Gas",
    "GC-015|Condensate",
    "GC-015|OperatingConditions",
    "HB-001|HTS",
    "HB-003|DutyEstimate",
    "HB-003|HeatExchanger",
    "HB-004|LTS",
    "HB-005|Steam",
    "HB-006|PSA",
    "HB-009|TailGas",
    "HB-010|Feed",
    "HB-010|SelectivityEstimate",
    "HB-010|Separation",
    "HB-012|Compressor",
    "HB-013|Storage",
    "HB-018|Dispensing",
    "PLANT|HeatIntegration",
    "SA-001|Reading",
    "SA-002|Reading",
    "SA-003|Reading",
    "SA-004|Reading",
    "SA-005|Reading",
    "SA-006|Reading",
    "SA-010|Reading",
    "WGS|Composition",
)

MOVED_HEAT_ONLY = (
    "AI-007|ScadaSnapshot",
    "AI-011|LoggingStatus",
    "EU-007|Flare",
    "EU-008|ConsumerAdequacy",
    "EU-008|CoolingSupply",
    "EU-008|RecommendedCapacityEstimate",
    "EU-009|GridBalance",
    "EU-010|UPS",
    "EU-CHP|Dispatch",
    "GA-001|AgentConsistency",
    "GA-001|EnergyBalance",
    "GA-001|Outputs",
    "GC-001|Gas",
    "GC-003|Gas",
    "GC-004|Condensed water",
    "GC-004|Cooling duty",
    "GC-004|Gas",
    "GC-007|Blowdown",
    "GC-008|Blowdown",
    "GC-009|Blowdown",
    "GC-013|Fan power",
    "GC-013|Gas",
    "GC-015|Condensate",
    "GC-015|OperatingConditions",
    "HB-001|HTS",
    "HB-003|DutyEstimate",
    "HB-003|HeatExchanger",
    "HB-004|LTS",
    "HB-005|Steam",
    "HB-006|PSA",
    "HB-009|TailGas",
    "HB-010|Feed",
    "HB-010|SelectivityEstimate",
    "HB-010|Separation",
    "HB-012|Compressor",
    "HB-013|Storage",
    "HB-018|Dispensing",
    "PLANT|HeatIntegration",
    "SA-001|Reading",
    "SA-002|Reading",
    "SA-003|Reading",
    "SA-004|Reading",
    "SA-005|Reading",
    "SA-006|Reading",
    "SA-010|Reading",
    "WGS|Composition",
)


def _ser(snap):
    return {f"{k[0]}|{k[1]}": json.loads(json.dumps(v, sort_keys=True, default=str)) for k, v in snap.items()}


def _run(mode):
    with patched_supabase(FakeSupabase()):
        return _ser(t1.build_live_snapshot(n_cycles=20, overrides=None if mode == "default" else _mode(mode))[0])


@pytest.fixture(scope="module")
def runs():
    # P1-05(c) (deliberate edit): these pins isolate the water molar mass, so the cycle-1 dry feed is put back to the old 41.67 (P1-05(c) moves entries separately, tests/test_p1_05c_feed_basis.py).
    from python import gasifier_mass_balance as gmb
    mp_feed = pytest.MonkeyPatch()
    mp_feed.setattr(gmb, "DEFAULT_DRY_FEED_KG_H", 41.67)
    new = {m: _run(m) for m in ("default", "heat_only")}
    mp = pytest.MonkeyPatch()
    mp.setattr(ga, "M_H2O", OLD_M_H2O)
    mp.setattr(ba, "M_H2O_ENGINE", OLD_M_H2O)                                   # captured at import by balance_audit (and read by plant_heat_integration)
    mp.setattr(ba, "CP_LIQUID_WATER_J_MOLK", ba.hbchain.CP_WATER_KJ_KGK * OLD_M_H2O)
    try:
        old = {m: _run(m) for m in ("default", "heat_only")}
    finally:
        mp.undo()
        mp_feed.undo()
    return new, old


@pytest.fixture(scope="module")
def fixture_entries():
    with gzip.open(FIXTURE, "rb") as fh:
        return json.loads(fh.read().decode("utf-8"))


def _flat(v, p=""):
    out = {}
    if isinstance(v, dict):
        for k, x in v.items():
            out.update(_flat(x, f"{p}.{k}"))
    elif isinstance(v, list):
        for i, x in enumerate(v):
            out.update(_flat(x, f"{p}[{i}]"))
    elif isinstance(v, (int, float)) and not isinstance(v, bool):
        out[p] = float(v)
    else:
        out[p] = v
    return out


def _same(a, b):
    """Exact for non-floats, 1e-12 relative for floats; returns the differing paths."""
    fa, fb = _flat(a), _flat(b)
    if set(fa) != set(fb):
        return ["<structure>"]
    bad = []
    for p, x in fa.items():
        y = fb[p]
        if isinstance(x, float) or isinstance(y, float):
            if not (isinstance(x, (int, float)) and isinstance(y, (int, float)) and abs(x - y) <= 1e-12 * max(1.0, abs(x))):
                bad.append(p)
        elif x != y:
            bad.append(p)
    return bad


def test_the_constant_is_the_atom_sum_and_the_audit_route_agrees_exactly():
    assert ga.M_H2O == 2 * ga.M_H + ga.M_O and ga.M_H2O == pytest.approx(18.016, abs=1e-12)
    assert ba.molar_mass("H2O") == ga.M_H2O == ba.M_H2O_ENGINE


def test_the_intentional_list_holds_exactly_the_moved_fixture_keys():
    assert set(P1_05B_KEYS) <= set(INTENTIONAL)
    assert not set(P1_05B_KEYS) & set(OTHER_DECISIONS)


@pytest.mark.parametrize("mode", ["default", "heat_only"])
def test_with_the_old_water_mass_the_snapshot_equals_the_fixture_so_the_change_is_the_only_cause(runs, fixture_entries, mode):
    _, old = runs
    fx = _d2_wording.forward(fixture_entries[f"{mode}|20"])                      # notes reworded since the fixture was made: the old -> new phrase pairs are applied to the fixture
    bad = {}
    for k, e in fx.items():
        if k in OTHER_DECISIONS or k == "GA-001-INPUT|tail_gas_mode":      # P1-06 (deliberate edit): the switch note names the new default; pinned by tests/test_p1_06_tail_gas_default.py
            continue
        for field in ("value", "status", "unit", "confidence_note"):
            r = _same(e.get(field), old[mode][k].get(field))
            if r:
                bad[(k, field)] = r[:3]
    assert bad == {}, bad


@pytest.mark.parametrize("mode,moved,limit", [("default", MOVED_DEFAULT, 7.0e-5), ("heat_only", MOVED_HEAT_ONLY, 3.6e-4)])
def test_exactly_these_entries_move_and_by_at_most_this_much(runs, mode, moved, limit):
    new, old = runs
    got, worst = [], 0.0
    for k in old[mode]:
        a, b = _flat(old[mode][k].get("value")), _flat(new[mode][k].get("value"))
        assert set(a) == set(b), k
        rel = [abs((b[p] - a[p]) / a[p]) if a[p] else 1e9 for p in a if isinstance(a[p], float) and abs(a[p] - b[p]) > 1e-12 * max(1.0, abs(a[p]))]
        assert all(old[mode][k].get(f) == new[mode][k].get(f) for f in ("status", "unit")), k
        if rel:
            got.append(k)
            worst = max(worst, max(rel))
    assert sorted(got) == list(moved)
    assert 0 < worst < limit


def test_hb005_steam_moves_by_about_the_molar_mass_ratio(runs):
    new, old = runs
    a = old["default"]["HB-005|Steam"]["value"]["steam_kg_h"]
    b = new["default"]["HB-005|Steam"]["value"]["steam_kg_h"]
    assert 1.00005 < b / a < 1.00007
