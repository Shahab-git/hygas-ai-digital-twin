"""
Loader for the real MSW equipment registry (91 items).

Source of truth: data/MSW_Equipment_Datasheets_Interactive.xlsx (the actual
DOK-ING equipment datasheet workbook). data/equipment_registry.json is a
one-time flattened extract of that workbook (see scripts/build_registry.py),
committed so the deployed app doesn't need openpyxl/pandas as a runtime
dependency just to read a static registry.

Every item already carries real technical parameters from the source
workbook. What's genuinely NOT known for any of the 91 items (except one,
SA-005, which is explicitly marked not applicable) is vendor/model and a
datasheet reference — that gap is exactly what python/vendor_log.py tracks.
"""
import json
import os

_REGISTRY_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "equipment_registry.json")

_NOT_APPLICABLE_MARKERS = ("n/a", "not applicable")


def load_registry():
    """Returns the list of 91 equipment dicts: id, name, category, parameters,
    vendor_model, datasheet_reference, parameters_filled."""
    with open(_REGISTRY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def needs_vendor_sourcing(item):
    """False for the rare item explicitly marked not applicable in the source
    workbook (e.g. SA-005, a calculated value with no physical unit to source).
    True for every other item that has no vendor_model on file yet."""
    vm = item.get("vendor_model")
    if vm and any(marker in vm.lower() for marker in _NOT_APPLICABLE_MARKERS):
        return False
    return not vm
