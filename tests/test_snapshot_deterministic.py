"""Audit fix J1: two offline engine runs must be identical (audit B4 showed 0 of
116 entries differing; this keeps it that way). No database, no network."""
import json

from _fakes import FakeSupabase, patched_supabase
from python import cycle_clock, tab1_integration


def _dump(snapshot):
    return json.dumps({f"{k[0]}|{k[1]}": v for k, v in snapshot.items()}, sort_keys=True, default=str)


def test_two_build_live_snapshot_runs_are_identical():
    cycle_clock.set_elapsed_hours(None)
    with patched_supabase(FakeSupabase()):
        snap1, _s1, _e1 = tab1_integration.build_live_snapshot()
        snap2, _s2, _e2 = tab1_integration.build_live_snapshot()
    # HEAT INTEGRATION (deliberate edit): 121 = the 120 of before + the read-only (PLANT, HeatIntegration) key
    # A1 (deliberate edit): +1 = the switch input (GA-001-INPUT, gasifying_agent); A1.3 adds (GA-001, AgentConsistency): 123 in all
    # A1.3 (deliberate edit): 123 = 122 + the read-only (GA-001, AgentConsistency) key
    assert len(snap1) == 124, f"expected the 124 engine entries (116 + tail_gas_mode + EnergyBalance + split + CarbonAccounting + HeatIntegration + gasifying_agent + AgentConsistency + HB-003 DutyEstimate), got {len(snap1)}"
    assert set(snap1) == set(snap2)
    differing = [k for k in snap1 if json.dumps(snap1[k], sort_keys=True, default=str)
                 != json.dumps(snap2[k], sort_keys=True, default=str)]
    assert differing == [], f"non-deterministic entries: {differing}"
    assert _dump(snap1) == _dump(snap2)
