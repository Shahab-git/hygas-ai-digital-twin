"""python/rfi2_basis.py: the switchable DOK-ING RFI2 basis. The default engine must be untouched."""
import os

import pytest

from python import rfi2_basis as rb

RFI2_DEFAULT = True          # this module tests the new default (tests/conftest.py)
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def cmp45():
    return rb.compare(10, 0.45)


def test_the_model_side_is_the_default_engine(cmp45):
    m = cmp45["model"]
    assert abs(m["N2 (mol% dry)"] - 39.24) < 0.05 and abs(m["Hydrogen (kg/day)"] - 55.75) < 0.2


def test_the_rfi2_side_has_no_air_n2_and_much_less_hydrogen_and_gas(cmp45):
    r, m = cmp45["rfi2"], cmp45["model"]
    assert r["N2 (mol% dry)"] < 5 and r["H2 (mol% dry)"] > 55
    assert r["Hydrogen (kg/day)"] < 0.4 * m["Hydrogen (kg/day)"] and r["Raw syngas, dry (Nm3/h)"] < 0.3 * m["Raw syngas, dry (Nm3/h)"]
    assert abs(r["Hydrogen (kg/day)"] - 13.5) < 0.5          # numeric check of the module docstring


def test_the_derived_carbon_conversion_closes_to_the_char_share():
    conv, _ = rb.derived_carbon_conversion(0.45, 0.10)
    feed, dry = 41.67, 41.67 * 0.9
    ash = dry * 0.10
    carbon = dry * 0.9 * 0.5
    assert abs((1 - conv) * carbon + ash - 0.45 * feed) < 1e-9
    assert rb.derived_carbon_conversion(0.50, 0.10)[0] == 0.0          # clamped, the note says so
    assert "clamped" in rb.derived_carbon_conversion(0.50, 0.10)[1]


def test_char_share_orders_the_hydrogen():
    h = [rb.kpis(rb.run("rfi2", 8, c))["Hydrogen (kg/day)"] for c in (0.40, 0.45)]
    assert h[0] > h[1]


def test_bad_basis_is_refused_and_nothing_is_written():
    with pytest.raises(ValueError):
        rb.run("both")
    src = open(os.path.join(HERE, "python", "rfi2_basis.py"), encoding="utf-8").read()
    assert "HeatIntegration" not in src and "supabase" not in src.lower() and "to_csv" not in src


def test_the_answers_are_recorded_verbatim_and_appended():
    t = open(os.path.join(HERE, "data", "dokink_rfi_answers.md"), encoding="utf-8").read()
    assert "No air or steam is added to reactor." in t and "40 to 50% of the 41.67 kg/h feed is expected as carbon black / char" in t
    assert t.split("\n")[14].startswith("2. **Composition.**")          # earlier line numbers did not move
