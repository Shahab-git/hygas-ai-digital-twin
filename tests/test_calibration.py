"""Task CAL-1: the calibration core (python/calibration.py). A TWIN EXPERIMENT on SYNTHETIC data: the measurements are the unchanged engine's own output at a known truth plus seeded noise.
Proves the loop and exposes the identifiability structure; NOT validation against DOK-ING data (none exists); nothing in the model is calibrated; nothing imports the module.

What is guarded: the parameter specs come from the repo's own table, the forward model is the engine (qualitative sensitivities pinned), the information-matrix diagnostics (rank, condition, the ER /
carbon-conversion correlation), the per-instrument value table (the flow meter matters most), exact recovery of a known truth without noise, recovery within the stated standard errors with seeded noise,
that the engine's output is the same after a fit as before, and that nothing in the engine, the runtime, the app or a script imports the module."""
import os

import numpy as np
import pytest

from python import calibration as cal
from python import parameter_table as pt

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TRUTH = {"ER": 0.28, "steam_to_feed": 0.43, "carbon_conversion": 0.92, "ch4_carbon_fraction": 0.06}


@pytest.fixture(scope="module")
def jac():
    return cal.jacobian_report()


@pytest.fixture(scope="module")
def clean_fit():
    return cal.twin_experiment(TRUTH, noise_scale=0.0)


@pytest.fixture(scope="module")
def noisy_fit():
    return cal.twin_experiment(TRUTH, noise_seed=1, noise_scale=1.0)


# ---------------------------------------------------------------- specs and the forward model
def test_the_parameter_specs_are_the_repos_own_table_rows():
    specs = cal.parameter_specs()
    assert [s["name"] for s in specs] == ["ER", "steam_to_feed", "carbon_conversion", "ch4_carbon_fraction"]
    rows = {r["tag"]: r for r in pt.build_table() if r["overridable_via"] == pt.VIA_ENGINE}
    for s in specs:
        r = rows[s["tag"]]
        assert (s["nominal"], s["low"], s["high"]) == (float(r["value"]), float(r["range_low"]), float(r["range_high"]))
        assert r["status"] == "Assumed" and s["low"] < s["nominal"] < s["high"]


def test_the_forward_model_with_no_parameters_is_the_default_engine_and_unknown_names_are_refused():
    nominal = {s["name"]: s["nominal"] for s in cal.parameter_specs()}
    a, b = cal.forward({}), cal.forward(nominal)
    assert set(a) == set(cal.OBSERVABLE_NAMES)
    for k in a:
        assert b[k] == pytest.approx(a[k], rel=1e-9)
    with pytest.raises(KeyError):
        cal.forward({"not_a_parameter": 1.0})


def test_the_cycle_count_of_the_forward_model_is_enough_for_the_gas_to_have_settled():
    """The forward model runs N_CYCLES cycles for speed; the GA-001 gas must equal the 20-cycle value, at the default and at a perturbed point."""
    for p in ({}, {"ER": 0.28, "carbon_conversion": 0.92}):
        short, long_ = cal.forward(p), cal.forward(p, n_cycles=20)
        for k in short:
            assert short[k] == pytest.approx(long_[k], abs=1e-9)


def test_the_sensitivities_have_the_signs_the_physics_gives():
    base = cal.forward({})
    hi_er = cal.forward({"ER": 0.27})
    assert hi_er["N2_mol_pct_dry"] > base["N2_mol_pct_dry"] and hi_er["H2_mol_pct_dry"] < base["H2_mol_pct_dry"]        # more air: more N2, burns H2
    hi_s = cal.forward({"steam_to_feed": 0.44})
    assert hi_s["H2_mol_pct_dry"] > base["H2_mol_pct_dry"] and hi_s["CO_mol_pct_dry"] < base["CO_mol_pct_dry"]          # more steam: shifts CO to H2
    hi_ch4 = cal.forward({"ch4_carbon_fraction": 0.06})
    assert hi_ch4["CH4_mol_pct_dry"] > base["CH4_mol_pct_dry"]


# ---------------------------------------------------------------- identifiability (no data)
def test_the_information_matrix_has_full_rank_and_a_moderate_condition_number_with_all_six_observables(jac):
    assert jac["rank"] == 4 == jac["n_parameters"]
    assert 5 < jac["condition_number"] < 50
    assert all(p["verdict"] in ("identifiable", "weakly identifiable") for p in jac["parameters"].values())
    assert jac["parameters"]["ER"]["verdict"] == "identifiable" and jac["parameters"]["ch4_carbon_fraction"]["verdict"] == "identifiable"


def test_the_correlation_matrix_is_symmetric_unit_diagonal_and_er_is_confounded_with_conversion(jac):
    c = jac["correlation"]
    names = list(c)
    for a in names:
        assert c[a][a] == pytest.approx(1.0, abs=1e-9)
        for b in names:
            assert c[a][b] == pytest.approx(c[b][a], abs=1e-9)
            assert -1.0 - 1e-9 <= c[a][b] <= 1.0 + 1e-9
    assert c["ER"]["carbon_conversion"] > 0.5            # measured about 0.73: more air and more conversion shift the gas the same way


def test_the_flow_meter_is_the_instrument_that_matters_most(jac):
    loo = cal.leave_one_observable_out(jac)
    ref = loo["none removed"]
    assert set(loo) == {"none removed", *cal.OBSERVABLE_NAMES}
    # without the dry-flow meter the composition alone leaves ER, steam and conversion practically unidentifiable (standard error above the whole prior range)
    nf = loo["dry_flow_nm3_h"]
    for n in ("ER", "steam_to_feed", "carbon_conversion"):
        assert nf[n] > 1.0 and nf[n] > 5 * ref[n]
    assert nf["condition_number"] > 100
    # every single composition analyser is worth far less: the table stays at rank 4 with the parameters still below the prior range
    for o in ("H2_mol_pct_dry", "CO_mol_pct_dry", "CO2_mol_pct_dry", "N2_mol_pct_dry", "CH4_mol_pct_dry"):
        assert loo[o]["rank"] == 4 and max(loo[o][n] for n in ("ER", "steam_to_feed", "carbon_conversion", "ch4_carbon_fraction")) < 0.5
    # the CH4 analyser is what pins the CH4 carbon fraction
    assert loo["CH4_mol_pct_dry"]["ch4_carbon_fraction"] > 2 * ref["ch4_carbon_fraction"]


# ---------------------------------------------------------------- the twin experiment
def test_a_noise_free_twin_experiment_recovers_the_known_truth(clean_fit):
    assert clean_fit["converged"] and clean_fit["at_bound"] == []
    for n, t in TRUTH.items():
        assert clean_fit["estimate"][n] == pytest.approx(t, abs=1e-4)
    assert clean_fit["chi2"] < 1e-8


def test_a_noisy_twin_experiment_recovers_the_truth_within_its_own_standard_errors(noisy_fit):
    assert noisy_fit["converged"] and noisy_fit["at_bound"] == []
    for n in TRUTH:
        assert abs(noisy_fit["error_in_sigma"][n]) < 4.0, (n, noisy_fit["error_in_sigma"][n])
    # 6 observations, 4 parameters: 2 degrees of freedom; a seeded draw stays far below the 99.9 % point (13.8)
    assert noisy_fit["chi2"] < 13.8
    assert noisy_fit["n_obs"] == 6
    # the optimiser's own cost is the weighted sum of squares of the residuals the report computes separately (so the weights really are 1/sigma)
    assert noisy_fit["cost"] == pytest.approx(0.5 * sum(v * v for v in noisy_fit["residuals_sigma"].values()), rel=1e-4, abs=1e-9)
    assert noisy_fit["start"] != noisy_fit["truth"]


def test_the_fit_changes_nothing_in_the_model(clean_fit):
    before = cal.forward({})
    cal.fit(clean_fit["measured"], max_nfev=2)
    assert cal.forward({}) == before


def test_a_missing_observable_is_refused_not_guessed():
    with pytest.raises(KeyError):
        cal.fit({"H2_mol_pct_dry": 25.0})


def test_nothing_in_the_engine_the_runtime_the_app_or_a_script_imports_the_module():
    hits = []
    for base in ("python", "scripts"):
        for dp, _dn, fn in os.walk(os.path.join(ROOT, base)):
            for f in fn:
                if f.endswith(".py") and f != "calibration.py":
                    with open(os.path.join(dp, f), encoding="utf-8") as fh:
                        text = fh.read()
                    if "import calibration" in text or "from python import calibration" in text or "from . import calibration" in text or "python.calibration" in text:
                        hits.append(os.path.relpath(os.path.join(dp, f), ROOT))
    with open(os.path.join(ROOT, "app.py"), encoding="utf-8") as fh:
        text = fh.read()
    if "import calibration" in text or "from python import calibration" in text or "python.calibration" in text:
        hits.append("app.py")
    assert sorted(hits) == []
