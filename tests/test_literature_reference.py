"""Literature reference layer (python/literature_reference.py): labelled, sourced, separate from the engine, no network."""
import ast
import importlib
import os
import socket

import pytest

from python import literature_reference as lr
from python import plant_status as ps

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(ROOT, "python", "literature_reference.py")


def test_every_entry_has_an_https_source_an_assumed_status_and_a_caveat():
    assert len(lr.ENTRIES) >= 12
    for e in lr.ENTRIES:
        assert lr.problems(e) == [], (e["key"], lr.problems(e))
        assert e["source_url"].startswith("https://")
        assert e["status"].startswith("Assumed")
        assert e["caveat"].strip()
        assert e["what_the_page_does_not_state"].strip()


def test_the_status_string_is_the_projects_assumed_tag_and_nothing_stronger():
    assert lr.STATUS_ASSUMED == ps.STATUS_ASSUMED                       # the vocabulary has no "Assumed (literature-informed)"; this is the Assumed tag
    for e in lr.ENTRIES:
        for word in ("Confirmed", "Measured", "Calculated", "Estimated"):
            assert word not in e["status"]
        assert "literature-informed" in e["caveat"]


def test_no_numeric_value_exists_without_a_source():
    for e in lr.ENTRIES:
        if e["numeric"]:
            assert e["source_url"].startswith("https://"), e["key"]
            for n in e["numeric"]:
                assert n["low"] is not None or n["high"] is not None, (e["key"], n)
                assert n["unit"], (e["key"], n)


def test_keys_are_unique():
    keys = [e["key"] for e in lr.ENTRIES]
    assert len(keys) == len(set(keys))


def test_stated_figures_keep_the_wording_given():
    assert lr.entry("parrillo_er")["value_text"] == "ER, 0.22–0.25"
    assert "0.7–1.13" in lr.entry("parrillo_steam_to_carbon")["value_text"] and "up to 3.2" in lr.entry("parrillo_steam_to_oxygen")["value_text"]
    assert "59.3 %" in lr.entry("mdpi_performance")["value_text"] and "9.32 MJ/Nm3" in lr.entry("mdpi_performance")["value_text"]
    assert "naphthalene 108–122 ppm" in lr.entry("bates_bench_bfb")["value_text"]
    assert "H2 + CO 72.53 %" in lr.entry("srf_lab_bfb")["value_text"]
    assert "no numerical concentrations on the page" in lr.entry("vtt_sewage_sludge_parametric")["value_text"]
    assert "recovery up to 90 %" in lr.entry("grasys_psa_vendor")["value_text"] and "vendor" in lr.entry("grasys_psa_vendor")["caveat"].lower()


def test_not_found_list_is_present():
    items = " | ".join(n["item"] for n in lr.NOT_FOUND)
    for needle in ("gasifier temperature lag", "tail-gas recycle delay", "cooling-basin lag", "waste-derived chemical-looping"):
        assert needle in items
    assert all(n["note"] for n in lr.NOT_FOUND)


def test_the_vtt_trends_are_available_to_a_script():
    ids = {t["id"] for _k, t in lr.trends()}
    assert ids == {"T_up", "ER_down", "steam_up"}


def test_the_module_imports_nothing_from_the_project_or_a_network_library():
    tree = ast.parse(open(MODULE_PATH, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.level == 0, "relative (engine) import in the reference layer"
        names = []
        if isinstance(node, ast.Import):
            names = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module.split(".")[0]]
        for n in names:
            assert n in {"__future__", "typing", "dataclasses"}, f"unexpected import {n}"


def test_importing_the_module_opens_no_socket(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("the reference layer opened a socket")
    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    importlib.reload(lr)
    assert lr.ENTRIES


def test_nothing_in_the_engine_or_the_app_reads_the_reference_layer():
    for folder in ("python", "."):
        for name in os.listdir(os.path.join(ROOT, folder)):
            path = os.path.join(ROOT, folder, name)
            if not name.endswith(".py") or name == "literature_reference.py" or not os.path.isfile(path):
                continue
            src = open(path, encoding="utf-8").read()
            assert "literature_reference" not in src, f"{name} reads the reference layer"
