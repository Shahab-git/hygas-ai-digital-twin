"""P1-05(c): DEFAULT_DRY_FEED_KG_H is DRY solids (41.67 x (1 - 0.10) = 37.503 kg/h), no longer the as-received 41.67 under a dry name.

Pins (1) the constants and their equality with the feed chain; (2) ATTRIBUTION: with the constant put back to 41.67 the live snapshot equals the committed pre-change snapshot
(tests/fixtures/snapshot_origin_main_be7a92a.json.gz, the tip of the P1-05(d) branch, be7a92a) in every entry, in five runs; (3) the exact set of persisted entries that move in each run, and
that converged GA-001 outputs do not move; (4) the cycle-1 effect (dry flow -10 %); (5) the static default of byproduct_mass_flows()."""
import gzip
import json
import os
import re

import pytest

from _fakes import FakeSupabase, patched_supabase
from _intentional_changes import INTENTIONAL, P1_05C_KEYS
from python import circularity
from python import fe_feed_handling as fe
from python import gasifier_mass_balance as gmb
from python import tab1_integration as t1
from test_tail_gas_mode import _mode

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "snapshot_origin_main_be7a92a.json.gz")
SWITCH = "GA-001-INPUT|tail_gas_mode"          # P1-06 (deliberate edit): its note names the new default, so it differs from this older fixture; pinned by tests/test_p1_06_tail_gas_default.py
RUNS = ("default|1", "default|5", "default|20", "default|30", "heat_only|20")
MOVED = {
    "default|1": 34, "default|5": 50, "default|20": 8,       # at 9 significant digits in text; 16 entries differ if long floats in notes are compared exactly (convergence residue)
    "default|30": 8, "heat_only|20": 13,
}
UNION = {
    "AI-004|EU-009-State-IfResized", "AI-007|ScadaSnapshot", "AI-011|LoggingStatus", "EU-006|FuelCell", "EU-007|Flare", "EU-008|ConsumerAdequacy", "EU-008|CoolingSupply",
    "EU-008|RecommendedCapacityEstimate", "EU-009|GridBalance", "EU-010|UPS", "EU-CHP|Dispatch", "GA-001-INPUT|dry_feed_rate_kg_h", "GA-001|AgentConsistency", "GA-001|CarbonAccounting",
    "GA-001|EnergyBalance", "GA-001|Outputs", "GA-001|OxygenCarrierCirculationEstimate", "GC-001|Gas", "GC-003|Gas", "GC-004|Condensed water", "GC-004|Cooling duty", "GC-004|Gas",
    "GC-007|Blowdown", "GC-008|Blowdown", "GC-009|Blowdown", "GC-013|Fan power", "GC-013|Gas", "GC-015|Condensate", "GC-015|OperatingConditions", "HB-001|HTS", "HB-003|DutyEstimate",
    "HB-003|HeatExchanger", "HB-004|LTS", "HB-005|Steam", "HB-006|PSA", "HB-009|TailGas", "HB-010|Feed", "HB-010|SelectivityEstimate", "HB-010|Separation", "HB-012|Compressor",
    "HB-013|Storage", "HB-018|Dispensing", "PLANT|HeatIntegration", "SA-001|Reading", "SA-002|Reading", "SA-003|Reading", "SA-004|Reading", "SA-005|Reading", "SA-006|Reading",
    "SA-010|Reading", "WGS|Composition",
}


def _ser(snap):
    return {f"{k[0]}|{k[1]}": json.loads(json.dumps(v, sort_keys=True, default=str)) for k, v in snap.items()}


_LONG_FLOAT = re.compile(r"-?\d+\.\d{9,}(?:e[-+]?\d+)?")


def _norm(text):
    """Notes quote floats with 16-17 digits; the last digits differ between Python 3.11/3.12/3.13 (summation order), so long floats in TEXT are compared at 9 significant digits."""
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


def _run(name):
    mode, n = name.split("|")
    with patched_supabase(FakeSupabase()):
        return _ser(t1.build_live_snapshot(n_cycles=int(n), overrides=None if mode == "default" else _mode(mode))[0])


@pytest.fixture(scope="module")
def fixture_entries():
    with gzip.open(FIXTURE, "rb") as fh:
        return json.loads(fh.read().decode("utf-8"))


@pytest.fixture(scope="module")
def new_runs():
    return {r: _run(r) for r in RUNS}


@pytest.fixture(scope="module")
def old_runs():
    mp = pytest.MonkeyPatch()
    mp.setattr(gmb, "DEFAULT_DRY_FEED_KG_H", 41.67)
    try:
        return {r: _run(r) for r in RUNS}
    finally:
        mp.undo()


def test_the_constants():
    assert gmb.DEFAULT_AS_RECEIVED_FEED_KG_H == fe.FE001_DEFAULT_DELIVERY_RATE_KG_H == fe.FE003_NOMINAL_KG_H == 41.67
    assert gmb.DEFAULT_INLET_MOISTURE_FRACTION == fe.FE005_INLET_MOISTURE_FRACTION == 0.10
    assert gmb.DEFAULT_DRY_FEED_KG_H == circularity.DEFAULT_DRY_SOLIDS_FEED_KG_H == pytest.approx(37.503, abs=1e-12)


def test_the_static_default_of_the_byproduct_flows_is_now_on_the_dry_solids():
    f = gmb.byproduct_mass_flows()
    assert f["ash_kg_h"] == pytest.approx(3.7503, abs=1e-9) and f["carbon_black_kg_h"] == pytest.approx(1.87515, abs=1e-9)        # was 4.167 / 2.0835


def test_the_intentional_list_has_the_five_new_keys():
    assert set(P1_05C_KEYS) <= set(INTENTIONAL)


@pytest.mark.parametrize("run", RUNS)
def test_with_the_old_constant_the_snapshot_equals_the_pre_change_fixture_so_the_change_is_the_only_cause(old_runs, fixture_entries, run):
    fx = fixture_entries[run]
    assert set(fx) == set(old_runs[run])
    bad = [k for k, e in fx.items() if k != SWITCH and _differs(e, old_runs[run][k])]
    assert bad == []


@pytest.mark.parametrize("run", RUNS)
def test_exactly_these_entries_move_and_all_are_in_the_pinned_set(new_runs, fixture_entries, run):
    fx = fixture_entries[run]
    moved = {k for k, e in fx.items() if k != SWITCH and _differs(e, new_runs[run][k])}
    assert len(moved) == MOVED[run]
    assert moved <= UNION
    assert moved <= set(INTENTIONAL)             # every moved key is excluded from the Gate 4 comparisons and pinned here


def test_the_union_is_what_moves_in_the_five_runs(new_runs, fixture_entries):
    moved = set()
    for run in RUNS:
        moved |= {k for k, e in fixture_entries[run].items() if k != SWITCH and _differs(e, new_runs[run][k])}
    assert moved == UNION


def test_converged_gasifier_outputs_do_not_move(new_runs, fixture_entries):
    assert not _differs(fixture_entries["default|30"]["GA-001|Outputs"], new_runs["default|30"]["GA-001|Outputs"])


def test_cycle_one_now_feeds_the_dry_solids_and_the_dry_flow_drops_ten_percent(new_runs, fixture_entries):
    assert new_runs["default|1"]["GA-001-INPUT|dry_feed_rate_kg_h"]["value"] == pytest.approx(37.503, abs=1e-9)
    assert fixture_entries["default|1"]["GA-001-INPUT|dry_feed_rate_kg_h"]["value"] == pytest.approx(41.67, abs=1e-9)
    old = fixture_entries["default|1"]["GA-001|Outputs"]["value"]["dry_flow_nm3_h"]
    new = new_runs["default|1"]["GA-001|Outputs"]["value"]["dry_flow_nm3_h"]
    assert new / old == pytest.approx(37.503 / 41.67, rel=2e-2) and new < old


LEGACY_REGASIFY_DEFAULT = True      # P1-06b: not yet exercised on the real default (heat_only): compares against the pre-flip fixture whose 'default' runs are regasify; tests/conftest.py restores the old default for this module
