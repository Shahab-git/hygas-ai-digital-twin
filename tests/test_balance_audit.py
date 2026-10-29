"""Mass and energy closure audit (python/balance_audit.py): the audit must measure, never hide.

These tests do NOT gate on today's residuals (the carbon and energy residuals are findings, recorded in
docs/balance_audit_baseline.json). They guard the AUDIT: that it reproduces a hand-checkable case, that a broken input shows up as a
residual, that Missing terms are listed and never read as zero, that every residual it reports is explained by an identity read
from the code, and that it touches no database or network. Offline: counting fake store, no credentials."""
import ast
import json
import math
import os

import pytest

from _fakes import FakeSupabase, patched_supabase
from python import balance_audit as ba
from python import balance_audit_inventory as inv
from python import cycle_clock, gasifier_mass_balance as gmb, ga001_gasifier_model as ga001
from python import eu_utilities_chp as eu
from python import plant_status as ps
from python import tab1_integration as t1

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
N_CONV = 20     # the tail-gas recycle has converged to < 1e-9 by cycle 20 (tests are kept fast)


def _const(value):
    def fn(get_input):
        return {"value": value, "status": ps.STATUS_ASSUMED, "inputs": [], "validation_basis": ps.VALIDATION_NA, "confidence_note": "test"}
    return fn


@pytest.fixture(scope="module")
def fake():
    return FakeSupabase()


@pytest.fixture(scope="module")
def snaps(fake):
    cycle_clock.set_elapsed_hours(None)
    out = {}
    with patched_supabase(fake):
        for n in (1, 4, 5, N_CONV - 1, N_CONV):
            out[n] = t1.build_live_snapshot(n_cycles=n)[0]
    return out


# ---------------------------------------------------------------- D1(a): GA-001 atom balance at the verify_atom_balance tolerance
@pytest.mark.parametrize("n", [5, N_CONV])
def test_ga001_h_o_n_balances_close_at_verify_atom_balance_tolerance(snaps, n):
    bal = ba.ga001_balance(snaps[n], snaps[n - 1])
    for el in ("H", "O", "N"):
        row = bal["rows"][el]
        assert abs(row["rel"]) < 1e-8, f"{el}: {row['rel']}"        # verify_atom_balance's own tol=1e-8 (x max(1, target))
        assert abs(row["rel"]) < ba.TOL_NUMERICAL
        assert row["verdict"] == ba.VERDICT_NUMERICAL
    ok, detail = ba.atom_balance_like_verify(snaps[n], snaps[n - 1])
    assert ok, detail                                                  # the model's own checker agrees on the same inputs
    assert bal["rows"]["ash"]["verdict"] == ba.VERDICT_NUMERICAL


def test_ga001_cycle_one_has_no_recycle_and_uses_the_placeholder_feed(snaps):
    out = snaps[1][("GA-001", "Outputs")]["value"]
    assert out["recycle_active"] is False
    assert snaps[1][("GA-001-INPUT", "dry_feed_rate_kg_h")]["value"] == gmb.DEFAULT_DRY_FEED_KG_H     # 41.67 wet figure used as dry (ga001:418-435)
    bal = ba.ga001_balance(snaps[1], None)
    for el in ("H", "O", "N"):
        assert abs(bal["rows"][el]["rel"]) < 1e-12


# ---------------------------------------------------------------- D1(b): hand-checkable synthetic case
def test_methane_combustion_closes_to_zero_and_matches_hand_numbers():
    assert ba.molar_mass("CH4") == pytest.approx(12.011 + 4 * 1.008)          # 16.043 g/mol
    assert ba.molar_mass("O2") == pytest.approx(32.00)
    assert ba.molar_mass("CO2") == pytest.approx(44.011)
    assert ba.molar_mass("H2O") == pytest.approx(18.016)
    terms = [ba.make_term("CH4", "in", {"CH4": 1.0}), ba.make_term("O2", "in", {"O2": 2.0}),
             ba.make_term("CO2", "out", {"CO2": 1.0}), ba.make_term("H2O", "out", {"H2O": 2.0})]
    rows = ba.closure(terms)["rows"]
    assert rows["C"]["in_mol_h"] == 1.0 and rows["H"]["in_mol_h"] == 4.0 and rows["O"]["in_mol_h"] == 4.0
    for key in ("C", "H", "O", "N"):
        assert abs(rows[key]["residual_mol_h"]) < 1e-12
    assert rows["mass"]["in_kg_h"] == pytest.approx((16.043 + 64.0) / 1000.0)
    assert rows["mass"]["out_kg_h"] == pytest.approx((44.011 + 36.032) / 1000.0)
    assert abs(rows["mass"]["residual_kg_h"]) < 1e-15
    assert rows["mass"]["verdict"] == ba.VERDICT_NUMERICAL


def test_a_known_imbalance_in_a_hand_case_is_reported_with_the_right_size_and_sign():
    terms = [ba.make_term("CH4", "in", {"CH4": 1.0}), ba.make_term("O2", "in", {"O2": 2.0}),
             ba.make_term("CO2", "out", {"CO2": 0.9}), ba.make_term("H2O", "out", {"H2O": 2.0})]
    rows = ba.closure(terms)["rows"]
    assert rows["C"]["residual_mol_h"] == pytest.approx(0.1)                    # in - out: positive = more in than out
    assert rows["C"]["residual_kg_h"] == pytest.approx(0.1 * 12.011 / 1000.0)
    assert rows["C"]["rel"] == pytest.approx(0.1)
    assert rows["C"]["verdict"] == ba.VERDICT_NO
    assert rows["O"]["residual_mol_h"] == pytest.approx(0.2)
    assert rows["H"]["verdict"] == ba.VERDICT_NUMERICAL


# ---------------------------------------------------------------- D1(c): a broken input must not report closure
def test_removing_a_product_component_gives_a_nonzero_residual(snaps):
    d = ba.ga001_terms(snaps[N_CONV], snaps[N_CONV - 1])
    good = ba.closure(d["terms"])["rows"]
    broken_terms = []
    for t in d["terms"]:
        if t["name"] == "product gas (wet)":
            sp = {k: v for k, v in t["species"].items() if k != "CH4"}
            t = ba.make_term(t["name"], "out", sp, status=t["status"], source=t["source"])
        broken_terms.append(t)
    bad = ba.closure(broken_terms)["rows"]
    ch4 = ba.gas_species_mol_h(snaps[N_CONV][("GA-001", "Outputs")]["value"])["CH4"]
    assert good["H"]["verdict"] == ba.VERDICT_NUMERICAL
    assert bad["H"]["verdict"] == ba.VERDICT_NO
    assert bad["H"]["residual_mol_h"] == pytest.approx(4.0 * ch4)               # CH4 carries 4 H
    assert bad["C"]["residual_mol_h"] - good["C"]["residual_mol_h"] == pytest.approx(ch4)
    assert bad["mass"]["verdict"] == ba.VERDICT_NO


def test_a_wrong_recycle_is_not_silently_absorbed(snaps):
    """Counting the recycle twice (or not at all) must break the exactly-closing H/O balances."""
    d = ba.ga001_terms(snaps[N_CONV], snaps[N_CONV - 1])
    twice = []
    for t in d["terms"]:
        if t["name"].startswith("tail-gas recycle"):
            t = ba.make_term(t["name"], "in", {k: 2.0 * v for k, v in t["species"].items()}, status=t["status"], source=t["source"])
        twice.append(t)
    rows = ba.closure(twice)["rows"]
    assert rows["H"]["verdict"] == ba.VERDICT_NO and rows["O"]["verdict"] == ba.VERDICT_NO


# ---------------------------------------------------------------- D1(d): Missing terms are listed, never zero
def test_missing_terms_are_listed_and_never_counted_as_zero(snaps):
    bal = ba.ga001_balance(snaps[N_CONV], snaps[N_CONV - 1])
    assert "tar" in bal["missing_terms"]
    tar = [t for t in bal["terms"] if t["name"] == "tar"][0]
    assert tar["species"] is None and tar["mass_kg_h"] is None and tar["status"] == ps.STATUS_MISSING
    assert bal["rows"]["C"]["complete"] is False and "tar" in bal["rows"]["C"]["missing_terms"]
    assert bal["rows"]["N"]["complete"] is True
    assert bal["rows"]["mass"]["complete"] is False
    plant = ba.plant_balance(snaps[N_CONV], snaps[N_CONV - 1], "plant")
    for name in ("tar", "FE-002 tramp metal reject", "membrane (HB-010) and LOHC (HB-014..017) branches"):
        assert name in plant["missing_terms"]


def test_a_missing_term_changes_no_sum_and_a_blocking_one_stops_the_verdict():
    base = [ba.make_term("CH4", "in", {"CH4": 1.0}), ba.make_term("O2", "in", {"O2": 2.0}),
            ba.make_term("CO2", "out", {"CO2": 1.0}), ba.make_term("H2O", "out", {"H2O": 2.0})]
    with_missing = base + [ba.make_term("tar", "out", None, affects=("C", "H"))]
    a, b = ba.closure(base)["rows"], ba.closure(with_missing)["rows"]
    assert a["C"]["out_mol_h"] == b["C"]["out_mol_h"] and a["mass"]["out_kg_h"] == b["mass"]["out_kg_h"]
    assert b["C"]["missing_terms"] == ["tar"] and b["O"]["missing_terms"] == [] and b["C"]["complete"] is False
    blocking = base + [ba.make_term("recycle", "in", None, affects=("C", "H"), blocking=True)]
    c = ba.closure(blocking)["rows"]
    assert c["C"]["verdict"] == ba.VERDICT_NA and c["H"]["verdict"] == ba.VERDICT_NA and c["O"]["verdict"] != ba.VERDICT_NA


def test_active_recycle_without_the_previous_cycle_cannot_be_evaluated(snaps):
    bal = ba.ga001_balance(snaps[N_CONV], None)
    assert snaps[N_CONV][("GA-001", "Outputs")]["value"]["recycle_active"] is True
    for el in ("C", "H", "O"):
        assert bal["rows"][el]["verdict"] == ba.VERDICT_NA
    assert bal["rows"]["mass"]["verdict"] == ba.VERDICT_NA


# ---------------------------------------------------------------- every reported residual has an explanation read from the code
@pytest.mark.parametrize("n", [5, N_CONV])
def test_the_carbon_residual_is_exactly_the_conversion_versus_carbon_black_identity(snaps, n):
    x = ba.explain_carbon_residual(snaps[n], snaps[n - 1])
    assert abs(x["difference_kg_h"]) < 1e-9
    assert x["unconverted_from_recycle_kg_h"] > 0.0                               # the recycled CO/CH4 carbon is also cut by 10 %
    assert x["conversion_that_would_match_carbon_black_feed_only"] == pytest.approx(1.0 - 0.05 / 0.45)
    cycle_one = ba.explain_carbon_residual(snaps[1], None)
    assert abs(cycle_one["difference_kg_h"]) < 1e-9 and cycle_one["measured_kg_h"] < 0.0     # sign flips without recycle


@pytest.mark.parametrize("n", [5, N_CONV])
def test_the_loop_closes_h_o_n_with_the_recycle_inside_even_before_convergence(snaps, n):
    loop = ba.plant_balance(snaps[n], snaps[n - 1], "loop")["rows"]
    for el in ("H", "O", "N"):
        assert abs(loop[el]["rel"]) < 1e-12, (n, el, loop[el]["rel"])
    assert abs(loop["C"]["residual_kg_h"] - ba.explain_carbon_residual(snaps[n], snaps[n - 1])["measured_kg_h"]) < 1e-9


@pytest.mark.parametrize("n", [5, N_CONV])
def test_the_whole_plant_residuals_are_fully_explained(snaps, n):
    x = ba.explain_plant_mass_residual(snaps[n], snaps[n - 1])
    assert abs(x["H_residual_measured_kg_h"] - x["H_residual_expected_kg_h"]) < 1e-9
    assert abs(x["O_residual_measured_kg_h"] - x["O_residual_expected_kg_h"]) < 1e-9
    assert abs(x["mass_unexplained_kg_h"]) < 1e-9
    assert x["electrolyser_excess_water_mol_h"] > 0.0                             # 1.0 L/Nm3 drawn vs 0.80 L/Nm3 stoichiometric


def test_the_storage_clamp_is_measured_from_the_inventory_change(snaps):
    s = ba.storage_inventory_check(snaps[5], snaps[4])
    assert s["h2_created_by_clamp_kg"] == pytest.approx(s["level_kg"] - s["expected_level_without_clamp_kg"])
    assert s["h2_created_by_clamp_kg"] > 0.0 and s["verdict"] == ba.VERDICT_NO       # the default five-cycle state sits on the lower clamp
    quiet = ba.storage_inventory_check(snaps[N_CONV], snaps[N_CONV - 1])
    assert quiet["h2_created_by_clamp_kg"] == pytest.approx(quiet["level_kg"] - quiet["expected_level_without_clamp_kg"])
    assert quiet["previous_level_kg"] == snaps[N_CONV - 1][("HB-013", "Storage")]["value"]["level_kg"]


# ---------------------------------------------------------------- operation dependence (normal entry points only)
def test_er_range_and_feed_cases_run_through_the_normal_entry_point(fake):
    cases = {"ER lo": {("GA-001-INPUT", "equivalence_ratio"): _const(0.2125)},
             "ER hi": {("GA-001-INPUT", "equivalence_ratio"): _const(0.2875)},
             "feed +30 % at FE-001": {("FE-001-INPUT", "msw_delivery_rate_kg_h"): _const(41.67 * 1.3)}}
    with patched_supabase(fake):
        for name, ov in cases.items():
            s, _st, _en = t1.build_live_snapshot(n_cycles=5, overrides=ov)
            p, _st, _en = t1.build_live_snapshot(n_cycles=4, overrides=ov)
            a = ba.audit_snapshot(s, p)
            assert not a["missing_inputs"], name
            for el in ("H", "O", "N"):
                assert abs(a["ga001"]["rows"][el]["rel"]) < 1e-12, (name, el)
            assert abs(a["explain_carbon"]["difference_kg_h"]) < 1e-9
            if name.startswith("feed"):
                assert a["clipped_surplus_kg_h"] == pytest.approx(41.67 * 1.3 - 50.0)   # FE-003 clips at 50 kg/h and the surplus goes nowhere


# ---------------------------------------------------------------- energy: constants, conventions, missing terms
def test_standard_constants_and_sensible_heat_by_hand():
    assert ba.LHV_KJ_MOL["H2"] == pytest.approx(241.826) and ba.LHV_KJ_MOL["CO"] == pytest.approx(282.984)
    assert ba.LHV_KJ_MOL["CH4"] == pytest.approx(802.288) and ba.LHV_KJ_MOL["C"] == pytest.approx(393.509)
    assert ba.DH_VAP_KJ_MOL == pytest.approx(44.004)
    for sp in ("H2", "CO", "CH4"):                                               # the repo's own MJ/Nm3 table, derived independently, agrees < 0.3 %
        derived = ba.LHV_KJ_MOL[sp] / ga001.NM3_PER_MOL / 1000.0
        assert derived == pytest.approx(eu.SYNGAS_SPECIES_LHV_MJ_PER_NM3[sp], rel=3e-3)
    assert ba._sens_kw({"N2": 100.0}, 125.0) == pytest.approx(100.0 * 30.6 * 100.0 / 1000.0 / 3600.0)
    assert ba._lhv_kw({"H2": 3600.0}) == pytest.approx(241.826)                  # 3600 mol/h x 241.826 kJ/mol / 3600 s
    assert ba._liquid_water_kw(3600.0) == pytest.approx(-44.004)                 # liquid at 25 degC sits 44 kJ/mol below the vapour zero
    assert ba._liquid_water_kw(3600.0, 25.0 + 100.0) == pytest.approx(-44.004 + 75.4 * 100.0 / 1000.0, rel=2e-3)


def test_feedstock_lhv_estimate_is_reported_with_its_range_and_status():
    est = ba.feedstock_lhv_estimates()
    assert est["status"] == ps.STATUS_ESTIMATED
    assert est["dry_wt_pct"]["C"] == pytest.approx(45.0) and est["dry_wt_pct"]["ash"] == pytest.approx(10.0)
    lo, hi = est["range_MJ_kg"]
    assert lo < hi and 14.0 < lo and hi < 17.5
    assert set(ba.lhv_cases()) >= {"DOK-ING low (Confirmed range end)", "DOK-ING high (Confirmed range end)"}


@pytest.fixture(scope="module")
def energy(snaps):
    kpis = t1.compute_tab1_kpis(snaps[N_CONV])
    return {"kpis": kpis, "audit": ba.audit_snapshot(snaps[N_CONV], snaps[N_CONV - 1], kpis)}


def test_gasifier_has_no_heat_duty_in_the_engine_so_the_audit_reports_an_implied_one(snaps, energy):
    out = snaps[N_CONV][("GA-001", "Outputs")]["value"]
    assert not any("duty" in k.lower() or "heat" in k.lower() for k in out), "if GA-001 ever publishes a duty, this audit must use it"
    g = energy["audit"]["energy_gasifier"]
    lo, mid, hi = (g[k] for k in ("DOK-ING low (Confirmed range end)", "DOK-ING midpoint (Assumed point)", "DOK-ING high (Confirmed range end)"))
    for e in (lo, mid, hi):
        assert e["status"] == "Calculated, not part of the engine"
        assert e["implied_heat_duty_kw"] == pytest.approx(e["sum_out_kw"] - e["sum_in_kw"])
        assert e["missing_terms"]
    f = snaps[N_CONV][("GA-001-INPUT", "dry_feed_rate_kg_h")]["value"]
    slope = (hi["implied_heat_duty_kw"] - lo["implied_heat_duty_kw"]) / (20.0 - 15.0)
    assert slope == pytest.approx(-f / 3.6, rel=1e-9)                              # +1 MJ/kg of feed LHV = -f/3.6 kW of duty
    assert lo["implied_heat_duty_kw"] > 0.0 > hi["implied_heat_duty_kw"]            # the sign flips inside DOK-ING's own LHV range


def test_plant_energy_lists_missing_terms_and_defines_the_residual_explicitly(snaps, energy):
    for e in energy["audit"]["energy_plant"].values():
        assert e["missing_terms"] and e["status"].startswith("Calculated from engine outputs")
        assert e["implied_heat_rejected_kw"] == pytest.approx(e["sum_in_kw"] - e["sum_out_known_kw"])
        assert e["closure_residual_kw"] == pytest.approx(e["implied_heat_rejected_kw"] - e["engine_reported_rejection_kw"])
        assert e["closure_residual_pct_of_input"] == pytest.approx(100.0 * e["closure_residual_kw"] / e["sum_in_kw"])
    mid = energy["audit"]["energy_plant"]["DOK-ING midpoint (Assumed point)"]
    shredder = [t for t in mid["in"] if t["name"].startswith("shredder FE-004")]      # computed by the engine but not in EU-009
    assert len(shredder) == 1 and shredder[0]["kw"] == pytest.approx(snaps[N_CONV][("FE-004", "ShredderPower")]["value"]["power_kw"])
    assert [t for t in mid["in"] if t["name"].startswith("electricity consumed")][0]["kw"] == pytest.approx(
        snaps[N_CONV][("EU-009", "GridBalance")]["value"]["consumption_kw"])
    assert mid["internal_heat_demand_sum_kw"] > mid["eu008_includes_hb003_cold_side_kw"]


def test_efficiency_check_reproduces_what_the_twin_reports(energy):
    e = energy["audit"]["efficiencies"]
    assert e["re_derived_pct_range"] == pytest.approx(e["reported_overall_efficiency_pct_range"], rel=1e-12)
    assert abs(e["h2_lhv_basis_difference_pct"]) < 0.3
    assert 0.0 < e["h2_yield_fraction_of_maximum"] < 1.0
    assert e["balance_implied_pct_range_incl_electricity"][1] < e["balance_implied_pct_range_feed_only"][1]


# ---------------------------------------------------------------- inventory references stay true
def test_every_file_line_reference_in_the_inventory_still_points_at_its_code(snaps):
    assert inv.check_refs() == []
    cache = {}
    for row in inv.unaccounted_items(snaps[N_CONV]):
        fname, line, snippet = row[4]
        if line == 0:
            continue
        lines = cache.setdefault(fname, open(os.path.join(ROOT, "python", fname), encoding="utf-8").read().splitlines())
        assert snippet in lines[line - 1], (row[0], fname, line)


def test_the_baseline_file_if_present_is_dated_and_tied_to_a_commit():
    path = os.path.join(ROOT, "docs", "balance_audit_baseline.json")
    if not os.path.exists(path):
        pytest.skip("baseline not yet generated (scripts/run_balance_audit.py --write-baseline)")
    data = json.load(open(path, encoding="utf-8"))
    assert data["date"] and len(data["commit"]) >= 7 and "default" in data["cases"]
    assert "NOT a CI gate" in data["note"]


# ---------------------------------------------------------------- D1(e): no database, no network
def test_the_audit_makes_no_database_call_and_imports_no_client(snaps, fake, energy):
    assert fake.calls == [], fake.calls
    assert os.environ.get("HYGAS_ALLOW_DB_WRITES") == "0"
    forbidden = {"streamlit", "supabase", "requests", "urllib", "http", "socket", "httpx", "psycopg2"}
    for name in ("balance_audit.py", "balance_audit_inventory.py"):
        tree = ast.parse(open(os.path.join(ROOT, "python", name), encoding="utf-8").read())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported.add(node.module.split(".")[0])
        assert not (imported & forbidden), (name, imported & forbidden)
    source = open(os.path.join(ROOT, "python", "balance_audit.py"), encoding="utf-8").read()
    assert "get_client" not in source and "secrets" not in source


def test_the_audit_modules_change_no_engine_state(snaps):
    """Auditing twice gives identical results and the snapshot it was handed is unchanged."""
    before = json.dumps({f"{k[0]}|{k[1]}": v["value"] for k, v in snaps[N_CONV].items()}, sort_keys=True, default=str)
    a = ba.audit_snapshot(snaps[N_CONV], snaps[N_CONV - 1])
    b = ba.audit_snapshot(snaps[N_CONV], snaps[N_CONV - 1])
    after = json.dumps({f"{k[0]}|{k[1]}": v["value"] for k, v in snaps[N_CONV].items()}, sort_keys=True, default=str)
    assert before == after
    assert {k: v["residual_kg_h"] for k, v in a["plant"]["rows"].items()} == {k: v["residual_kg_h"] for k, v in b["plant"]["rows"].items()}
