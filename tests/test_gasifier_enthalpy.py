"""Task A4: the gasifier enthalpy diagnostic (python/gasifier_enthalpy.py). READ-ONLY; not validation against DOK-ING data (none exists); not a plant prediction.

A4.1 (this part): the thermodynamic DATA. Sensible enthalpy dHs(T) = H(T) - H(298.15 K) is computed by exact integration of NASA 9-coefficient polynomials (NASA/TP-2002-211556, McBride, Zehe, Gordon 2002),
stored in data/thermo_nasa9.json. They are checked here against the NIST-JANAF tables, typed below as INDEPENDENT literals (downloaded 2026-11-05 from https://janaf.nist.gov/tables/<id>.html), and against
the repo's formation enthalpies (balance_audit.HF_KJ_MOL). Offline: reads the data file only.
"""
import copy
import json
import math
import os
import re

import pytest

from python import balance_audit as ba
from python import gasifier_enthalpy as ge

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data", "thermo_nasa9.json")

# kJ/mol, column 'H - H(Tr)' of the NIST-JANAF table, Tr = 298.15 K, standard state pressure 0.1 MPa (1 bar); typed from the tables downloaded 2026-11-05 (https://janaf.nist.gov/tables/<id>.html)
JANAF_H_MINUS_H298 = {
    "H2": ('H-050', {500.0: 5.882, 1000.0: 20.680, 1200.0: 26.797}),   # Hydrogen (H2) H2(ref)
    "CO": ('C-093', {500.0: 5.931, 1000.0: 21.690, 1200.0: 28.430}),   # Carbon Monoxide (CO) C1O1(g)
    "CO2": ('C-095', {500.0: 8.305, 1000.0: 33.397, 1200.0: 44.473}),   # Carbon Dioxide (CO2) C1O2(g)
    "H2O": ('H-064', {500.0: 6.925, 1000.0: 26.000, 1200.0: 34.506}),   # Water (H2O) H2O1(g)
    "CH4": ('C-067', {500.0: 8.200, 1000.0: 38.179, 1200.0: 53.270}),   # Methane (CH4) C1H4(g)
    "N2": ('N-023', {500.0: 5.911, 1000.0: 21.463, 1200.0: 28.109}),   # Nitrogen (N2) N2(ref)
    "O2": ('O-029', {500.0: 6.084, 1000.0: 22.703, 1200.0: 29.761}),   # Oxygen (O2) O2(ref)
    "C": ('C-002', {500.0: 2.365, 1000.0: 11.795, 1200.0: 16.240}),   # Carbon (C) C1(ref), graphite
}
# Tolerance (kJ/mol) of dHs(T) against the JANAF table: JANAF tabulates to 0.001 kJ/mol; the NASA-9 fits follow the Gurvich-type evaluations of the 1990s, JANAF its own 1998 evaluations, so a fit and a
# table differ by a few 0.001 kJ/mol (largest of the seven species: 0.012 kJ/mol, H2O at 1200 K, 0.03 % of the value). 0.02 kJ/mol is the stated tolerance (0.05 % of the largest value, CO2 at 1200 K).
# METHANE IS THE ONE KNOWN DISAGREEMENT, REPORTED AND NOT FORCED: its NASA record (Gurvich 1991) has a larger Cp than the JANAF 1998 table above 500 K (73.68 against 71.80 J/mol K at 1000 K),
# so dHs differs by 0.03 / 0.51 / 0.97 kJ/mol at 500 / 1000 / 1200 K. The record is internally consistent (its two intervals join to 1e-6 kJ/mol and its H(298.15) equals its own formation value), so it
# is a source difference, not a transcription error. The CH4 tolerance is 1.0 kJ/mol and CH4 is a few vol% of the product gas.
TOL = 0.02
TOL_SPECIES = {"CH4": 1.0}
TOL_FORMATION = 0.3          # kJ/mol: polynomial H(298.15 K) against the repo's HF_KJ_MOL; the largest difference is methane (-74.600 against -74.873, 0.273); every other species is within 0.02
HF_REPO = {"H2": 0.0, "CO": ba.HF_KJ_MOL["CO"], "CO2": ba.HF_KJ_MOL["CO2"], "H2O": ba.HF_KJ_MOL["H2O_g"], "CH4": ba.HF_KJ_MOL["CH4"], "N2": 0.0, "O2": 0.0, "C": 0.0}
CASES = [(sp, T) for sp in ge.SPECIES for T in (500.0, 1000.0, 1200.0)]


# ---------------------------------------------------------------- 1: data integrity, against the independent JANAF literals

@pytest.mark.parametrize("species,T", CASES)
def test_the_sensible_enthalpy_matches_the_nist_janaf_table(species, T):
    poly = ge.sensible_enthalpy_j_mol(species, T) / 1000.0
    table = JANAF_H_MINUS_H298[species][1][T]
    assert abs(poly - table) <= TOL_SPECIES.get(species, TOL), (species, T, poly, table, poly - table)


def test_every_species_is_covered_at_three_temperatures_and_the_table_ids_are_the_ones_the_data_file_cites():
    assert set(JANAF_H_MINUS_H298) == set(ge.SPECIES)
    raw = ge.load_thermo()["raw"]["species"]
    for sp, (tid, rows) in JANAF_H_MINUS_H298.items():
        assert set(rows) == {500.0, 1000.0, 1200.0}
        assert raw[sp]["cross_check_table"]["table_id"] == tid and raw[sp]["cross_check_table"]["url"] == f"https://janaf.nist.gov/tables/{tid}.html"


def test_the_one_known_disagreement_is_methane_and_it_is_the_size_that_was_measured():
    dev = {T: ge.sensible_enthalpy_j_mol("CH4", T) / 1000.0 - JANAF_H_MINUS_H298["CH4"][1][T] for T in (500.0, 1000.0, 1200.0)}
    assert 0.01 < dev[500.0] < 0.05 and 0.4 < dev[1000.0] < 0.6 and 0.8 < dev[1200.0] < 1.1, dev
    others = [abs(ge.sensible_enthalpy_j_mol(sp, T) / 1000.0 - JANAF_H_MINUS_H298[sp][1][T]) for sp, T in CASES if sp != "CH4"]
    assert max(others) <= TOL and max(others) > 0.005, max(others)        # the seven others agree to a few 0.001 kJ/mol (and the check is not vacuous)


@pytest.mark.parametrize("species", ge.SPECIES)
def test_the_polynomial_formation_value_equals_its_own_record_and_agrees_with_the_repo_table(species):
    raw = ge.load_thermo()["raw"]["species"][species]
    poly_hf = ge.polynomial_enthalpy_j_mol(species, 298.15) / 1000.0
    assert abs(poly_hf - raw["formation_enthalpy_298_15_j_mol_in_record"] / 1000.0) < 1e-3, "the transcribed coefficients reproduce the record's own formation enthalpy"
    assert abs(poly_hf - HF_REPO[species]) <= TOL_FORMATION, (species, poly_hf, HF_REPO[species])
    if species != "CH4":
        assert abs(poly_hf - HF_REPO[species]) <= 0.02, (species, poly_hf, HF_REPO[species])


@pytest.mark.parametrize("species", ge.SPECIES)
def test_neighbouring_intervals_join_continuously_in_enthalpy_and_heat_capacity(species):
    thermo = ge.load_thermo()
    ivs = thermo["species"][species]
    for (lo1, hi1, a1, b1), (lo2, hi2, a2, b2) in zip(ivs, ivs[1:]):
        T = hi1
        h1 = thermo["R"] * T * (-a1[0] / T**2 + a1[1] * math.log(T) / T + a1[2] + a1[3] * T / 2 + a1[4] * T**2 / 3 + a1[5] * T**3 / 4 + a1[6] * T**4 / 5 + b1[0] / T)
        h2 = thermo["R"] * T * (-a2[0] / T**2 + a2[1] * math.log(T) / T + a2[2] + a2[3] * T / 2 + a2[4] * T**2 / 3 + a2[5] * T**3 / 4 + a2[6] * T**4 / 5 + b2[0] / T)
        c1 = thermo["R"] * (a1[0] / T**2 + a1[1] / T + a1[2] + a1[3] * T + a1[4] * T**2 + a1[5] * T**3 + a1[6] * T**4)
        c2 = thermo["R"] * (a2[0] / T**2 + a2[1] / T + a2[2] + a2[3] * T + a2[4] * T**2 + a2[5] * T**3 + a2[6] * T**4)
        assert abs(h1 - h2) < 1e-2 and abs(c1 - c2) < 1e-4 * abs(c1), (species, T, h1, h2, c1, c2)      # J/mol: the fits are given to 10 digits


@pytest.mark.parametrize("species", ge.SPECIES)
def test_the_sensible_enthalpy_is_zero_at_the_reference_temperature_and_rises_with_temperature(species):
    assert ge.sensible_enthalpy_j_mol(species, 298.15) == 0.0
    grid = [200.0, 298.15, 400.0, 600.0, 800.0, 1000.0, 1223.15, 1500.0, 2000.0, 3000.0, 6000.0]
    vals = [ge.sensible_enthalpy_j_mol(species, T) for T in grid]
    assert vals[0] < 0.0 and all(a < b for a, b in zip(vals, vals[1:])), vals
    assert all(ge.cp_j_mol_k(species, T) > 0 for T in grid)


# ---------------------------------------------------------------- loader: out of range, missing species, malformed data

@pytest.mark.parametrize("bad", [199.9, 6000.1, 0.0, -300.0, float("nan"), float("inf"), True, None, "300", [300.0]])
def test_a_temperature_outside_the_data_range_or_not_a_number_is_refused(bad):
    with pytest.raises(ValueError):
        ge.sensible_enthalpy_j_mol("N2", bad)
    with pytest.raises(ValueError):
        ge.cp_j_mol_k("N2", bad)


def test_the_limits_themselves_are_allowed_and_an_unknown_species_is_refused():
    assert math.isfinite(ge.sensible_enthalpy_j_mol("N2", 200.0)) and math.isfinite(ge.sensible_enthalpy_j_mol("N2", 6000.0))
    for bad in ("AR", "", "h2", None):
        with pytest.raises(LookupError):
            ge.sensible_enthalpy_j_mol(bad, 500.0)


def _variant(tmp_path, edit):
    doc = json.load(open(DATA, encoding="utf-8"))
    edit(doc)
    p = tmp_path / "thermo.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return str(p)


def test_a_data_file_that_lacks_a_species_fails_loudly(tmp_path):
    path = _variant(tmp_path, lambda d: d["species"].pop("CH4"))
    with pytest.raises(LookupError, match="CH4"):
        ge.load_thermo(path)


def test_malformed_or_non_contiguous_data_fails_loudly(tmp_path):
    cases = {
        "six coefficients": lambda d: d["species"]["N2"]["intervals"][0]["a"].pop(),
        "a non-finite coefficient": lambda d: d["species"]["N2"]["intervals"][0]["a"].__setitem__(2, float("nan")),
        "a gap between intervals": lambda d: d["species"]["N2"]["intervals"][1].__setitem__("t_low_k", 1100.0),
        "the range stops short of 6000 K": lambda d: d["species"]["N2"]["intervals"].pop(),
        "R not positive": lambda d: d["_meta"].__setitem__("R_j_mol_k", 0.0),
    }
    for label, edit in cases.items():
        with pytest.raises(ValueError):
            ge.load_thermo(_variant(tmp_path, edit))
            pytest.fail(label)


def test_the_coefficients_are_data_not_literals_of_the_code():
    src = open(os.path.join(ROOT, "python", "gasifier_enthalpy.py"), encoding="utf-8").read()
    assert not re.findall(r"\d\.\d{6,}", src), "no coefficient-like literal in the module"
    assert os.path.basename(ge.THERMO_PATH) == "thermo_nasa9.json"


def test_the_data_file_cites_its_sources_retrieval_date_and_pages_for_every_species():
    doc = json.load(open(DATA, encoding="utf-8"))
    src = doc["_meta"]["source"]
    assert src["report_number"].startswith("NASA/TP-2002-211556") and src["retrieved"] == "2026-11-05"
    assert src["ntrs_record"] == "https://ntrs.nasa.gov/citations/20020085330" and src["pdf"].endswith("/20020085330/downloads/20020085330.pdf")
    assert doc["_meta"]["R_j_mol_k"] == 8.314510 and doc["_meta"]["reference_temperature_k"] == 298.15 and doc["_meta"]["standard_state_pressure_bar"] == 1.0
    assert "Estimated" in doc["_meta"]["status"] and "Confirmed" not in doc["_meta"]["status"].replace("not Confirmed", "")
    assert set(doc["species"]) == set(ge.SPECIES)
    for sp, d in doc["species"].items():
        loc = d["source_location"]
        assert loc["retrieved"] == "2026-11-05" and loc["url"] == src["pdf"] and loc["printed_pages"] and loc["appendix"].startswith("Appendix D")
        assert d["record_reference_in_source"] and d["cross_check_table"]["retrieved"] == "2026-11-05" and all(len(iv["a"]) == 7 and len(iv["b"]) == 2 for iv in d["intervals"])
    assert [iv["t_high_k"] for iv in doc["species"]["C"]["intervals"]] == [600.0, 2000.0, 6000.0]
