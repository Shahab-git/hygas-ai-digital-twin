"""Reference feed analyses (python/reference_feeds.py): sourced, labelled, arithmetic reproducible, separate from the engine, no network."""
import ast
import importlib
import os
import socket

import pytest

from python import ga001_gasifier_model as ga001
from python import reference_feeds as rf

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(ROOT, "python", "reference_feeds.py")
STORED = [e["key"] for e in rf.ENTRIES if not e["status"].startswith("Missing") and e["key"] != "dokink_feed_bands"]


def test_every_entry_is_sourced_labelled_and_has_a_caveat():
    assert len(rf.ENTRIES) == 16
    for e in rf.ENTRIES:
        assert rf.problems(e) == [], (e["key"], rf.problems(e))
        assert e["status"].startswith(("Assumed", "Calculated", "Missing"))
        assert "Confirmed" not in e["status"] and "Measured" not in e["status"]
    for k in STORED:
        e = rf.entry(k)
        assert e["source_url"].startswith("https://") and e["status"] == "Assumed (literature-informed)", k
        assert e["values"], k


def test_unread_sources_are_missing_with_no_values_and_a_not_verified_note():
    for k in ("wood_pellets_or_chips", "chalmers_cotton_polyester_thesis", "moliner_energies_17_5_1206"):
        e = rf.entry(k)
        assert e["status"].startswith("Missing") and e["values"] == {} and "NOT VERIFIED" in e["caveat"], k


def test_keys_are_unique():
    keys = [e["key"] for e in rf.ENTRIES]
    assert len(keys) == len(set(keys))


def test_stated_values_are_exactly_as_given():
    assert rf.entry("zhou_pe")["values"] == {"Ad_pct": 0.33, "C_daf_pct": 85.59, "H_daf_pct": 14.15, "O_daf_pct": 0.07, "N_daf_pct": 0.12, "HHV_d_kJ_kg": 42845}
    assert rf.entry("zhou_pvc")["values"]["Cl_daf_pct"] == 55.18 and rf.entry("zhou_pvc")["values"]["HHV_d_kJ_kg"] == 20848
    assert rf.entry("zhou_wool")["values"]["N_daf_pct"] == 8.89 and rf.entry("zhou_cotton")["values"]["Vd_pct"] == 87.93
    r = rf.entry("teerawattana_rdf")["values"]
    assert (r["ash_pct"], r["C_pct"], r["H_pct"], r["O_pct"], r["N_pct"], r["S_pct"], r["Cl_pct"], r["HHV_kcal_kg"]) == (24.48, 55.16, 7.89, 10.32, 1.30, 0.12, 0.73, 6888.1)
    s1, s2 = rf.entry("werle_sewage_sludge_ss1")["values"], rf.entry("werle_sewage_sludge_ss2")["values"]
    assert (s1["C_d_pct"], s1["O_d_pct"], s1["ash_pct"], s1["LHV_d_MJ_kg"]) == (31.79, 57.07, 36.50, 12.96)
    assert (s2["C_d_pct"], s2["O_d_pct"], s2["ash_pct"], s2["LHV_d_MJ_kg"]) == (27.72, 63.04, 44.20, 10.75)
    assert "by difference" in rf.entry("werle_sewage_sludge_ss1")["caveat"] and "NOT corrected" in rf.entry("werle_sewage_sludge_ss1")["caveat"]
    assert rf.entry("zhou_msw_combustible_fractions")["values"]["food_residue_pct"] == 55.86


# ---------------------------------------------------------------- arithmetic by hand
def test_daf_to_dry_reproduces_a_hand_case():
    d = rf.dry_basis("zhou_pe")
    assert d["C_dry_pct"] == pytest.approx(85.59 * (1 - 0.33 / 100.0)) == pytest.approx(85.3075, abs=1e-4)
    assert rf.dry_basis("zhou_cotton")["H_dry_pct"] == pytest.approx(6.30 * 0.9895)
    assert rf.dry_basis("zhou_pvc")["Cl_dry_pct"] == pytest.approx(55.18 * (1 - 0.0586))
    r = rf.dry_basis("teerawattana_rdf")
    assert r["C_dry_pct"] == pytest.approx(55.16 / (1 - 0.0293)) and r["HHV_dry_kJ_kg"] == pytest.approx(6888.1 * 4.184 / (1 - 0.0293))


def test_lhv_from_hhv_by_hand():
    assert rf.lhv_from_hhv(42845.0, 14.0) == pytest.approx(42845.0 - 2.442 * 1000.0 * 9.0 * 14.0 / 100.0)
    d = rf.derived("zhou_pe")
    assert d["LHV_dry_MJ_kg"] == pytest.approx((42845.0 - 2442.0 * 9.0 * d["H_dry_pct"] / 100.0) / 1000.0)
    assert d["LHV_daf_MJ_kg"] == pytest.approx(d["LHV_dry_MJ_kg"] / (1 - 0.0033))


def test_stoichiometric_polyethylene_is_ch2():
    assert rf.ATOMIC_MASS["C"] == ga001.M_C and rf.ATOMIC_MASS["H"] == ga001.M_H and rf.ATOMIC_MASS["O"] == ga001.M_O and rf.ATOMIC_MASS["N"] == ga001.M_N
    m = rf.stoichiometric(rf.STOICHIOMETRIC["PE"])
    assert m["C"] == pytest.approx(100 * 12.011 / (12.011 + 2 * 1.008)) and sum(m.values()) == pytest.approx(100.0)
    assert (m["H"] / 1.008) / (m["C"] / 12.011) == pytest.approx(2.0)                      # CH2: two H per C
    assert (rf.stoichiometric(rf.STOICHIOMETRIC["PS"])["H"] / 1.008) / (rf.stoichiometric(rf.STOICHIOMETRIC["PS"])["C"] / 12.011) == pytest.approx(1.0)
    pet = rf.stoichiometric(rf.STOICHIOMETRIC["PET"])
    assert (pet["C"] / 12.011, pet["H"] / 1.008, pet["O"] / 16.00) == pytest.approx((10 * pet["C"] / 12.011 / 10, 8 * pet["C"] / 12.011 / 10, 4 * pet["C"] / 12.011 / 10))
    assert abs(m["C"] - rf.entry("zhou_pe")["values"]["C_daf_pct"]) < 1.0               # within a point of the literature mean: a cross-check, not a source


def test_model_composition_renormalises_and_reports_what_is_dropped():
    c = rf.model_composition("zhou_pe")
    assert sum(c["composition_daf"].values()) == pytest.approx(1.0) and c["daf_pct_before_renormalising"] == pytest.approx(99.93)
    w = rf.model_composition("zhou_wool")
    assert w["unaccounted_daf_pct"] == pytest.approx(100 - (59.30 + 5.36 + 24.85 + 8.89))
    assert rf.model_composition("zhou_pvc")["dropped_daf_pct"]["Cl"] == 55.18
    assert c["LHV_model_dry_MJ_kg"] == pytest.approx(rf.derived("zhou_pe")["LHV_daf_MJ_kg"] * 0.9)


def test_blend_m1_is_an_illustrative_mass_weighted_mix():
    b = rf.blend()
    assert sum(rf.BLEND_M1.values()) == pytest.approx(1.0) and rf.BLEND_M1 == {"zhou_pe": 0.40, "zhou_pp": 0.25, "zhou_ps": 0.15, "zhou_pet": 0.10, "zhou_pvc": 0.10}
    assert b["illustrative"] is True and b["status"] == "Calculated"
    assert b["ash_dry_pct"] == pytest.approx(0.40 * 0.33 + 0.25 * 0.44 + 0.15 * 0.19 + 0.10 * 0.20 + 0.10 * 5.86)
    assert b["HHV_dry_kJ_kg"] == pytest.approx(0.40 * 42845 + 0.25 * 46004 + 0.15 * 39523 + 0.10 * 23090 + 0.10 * 20848)
    assert b["Cl_dry_pct"] == pytest.approx(0.10 * 55.18 * (1 - 0.0586))


# ---------------------------------------------------------------- DOK-ING bands
def test_the_bands_quote_the_repos_copy_of_the_rfi_answer():
    lines = open(os.path.join(ROOT, "data", "dokink_rfi_answers.md"), encoding="utf-8").read().splitlines()
    text = " ".join(lines[14:17])                         # lines 15-17
    for needle in ("Ash 5–15%", "Volatile Matter >65%", "Carbon >45%", "Hydrogen >5%", "LHV 15–20 MJ/kg (dry basis)"):
        assert needle in text, needle
    assert rf.BANDS == {"C_dry_pct": (">", 45.0), "H_dry_pct": (">", 5.0), "VM_dry_pct": (">", 65.0), "ash_dry_pct": ("range", (5.0, 15.0)), "LHV_dry_MJ_kg": ("range", (15.0, 20.0))}


def test_expected_band_readings():
    sludge, rdf = rf.bands_for("werle_sewage_sludge_ss1"), rf.bands_for("teerawattana_rdf")
    assert sludge["ash_dry_pct"][1] == "fails" and rdf["ash_dry_pct"][1] == "fails"
    assert sludge["C_dry_pct"][1] == "fails" and sludge["LHV_dry_MJ_kg"][1] == "fails"
    pe = rf.bands_for("zhou_pe")
    assert pe["H_dry_pct"][1] == "satisfied" and pe["H_dry_pct"][0] > 13.0                 # far above the floor; the band has no upper limit
    assert pe["VM_dry_pct"][1] == "not testable" and pe["ash_dry_pct"][1] == "fails"       # too clean for 5-15 %
    assert rf.bands_for("zhou_cotton")["LHV_dry_MJ_kg"][1] == "satisfied" and rf.bands_for("zhou_pet")["H_dry_pct"][1] == "fails"
    assert rf.check_bands({"C_dry_pct": 45.0})["C_dry_pct"][1] == "fails"                 # strictly greater than


# ---------------------------------------------------------------- separation from the engine, no network
def test_the_module_imports_nothing_from_the_project_or_a_network_library():
    tree = ast.parse(open(MODULE_PATH, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.level == 0, "relative (engine) import"
        names = [a.name.split(".")[0] for a in node.names] if isinstance(node, ast.Import) else \
                [node.module.split(".")[0]] if isinstance(node, ast.ImportFrom) and node.module else []
        for n in names:
            assert n in {"__future__", "typing"}, f"unexpected import {n}"


def test_importing_the_module_opens_no_socket(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("the reference feeds opened a socket")
    for fn in ("socket", "getaddrinfo", "create_connection"):
        monkeypatch.setattr(socket, fn, refuse)
    importlib.reload(rf)
    assert rf.ENTRIES


def test_nothing_in_the_engine_or_the_app_reads_the_reference_feeds():
    for folder in ("python", "."):
        for name in os.listdir(os.path.join(ROOT, folder)):
            path = os.path.join(ROOT, folder, name)
            if name.endswith(".py") and name != "reference_feeds.py" and os.path.isfile(path):
                assert "reference_feeds" not in open(path, encoding="utf-8").read(), name
