"""The CI runner's split covers every test file exactly once and keeps the app tests in the serial step."""
import os
import sys

import test_app_smoke as smoke

sys.path.insert(0, os.path.join(smoke.ROOT, "scripts"))
import run_tests_ci


def test_the_split_covers_every_test_file_exactly_once():
    first, rest = run_tests_ci.split_test_files()
    every = sorted(os.path.join("tests", n) for n in os.listdir(os.path.join(smoke.ROOT, "tests"))
                   if n.startswith("test_") and n.endswith(".py"))
    assert sorted(first + rest) == every and not set(first) & set(rest)


def test_app_rendering_tests_are_in_the_serial_step_and_in_file_order():
    first, rest = run_tests_ci.split_test_files()
    for name in ("test_app_smoke.py", "test_app_db_down.py", "test_a2_summary_tab.py", "test_a6_plant_3d.py"):
        assert os.path.join("tests", name) in first, name
    assert first == sorted(first) and rest == sorted(rest)
