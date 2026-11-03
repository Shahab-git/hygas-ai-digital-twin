"""Maturity registry (task A10): every AI / optimisation / virtual-sensing module has a declared class, shown in its docstring; the code of those modules is unchanged.

Offline; reads source files and (for the 'only the docstring changed' check) `git show origin/main:`, which is skipped when git or origin/main is unavailable."""
import ast
import glob
import os
import subprocess

import pytest

from python import maturity as mt

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULES = ("copilot", "optimizer", "predictive_maintenance", "root_cause", "pinn_kinetics", "federated_learning", "multi_agent_negotiation", "multi_module_orchestration", "sim_to_real",
           "time_series_sim", "tda_analysis", "novelty_audit", "safety_flags", "regulatory_drafting", "performance_guarantee", "sa_virtual_sensors", "ai_automation_layer", "uncertainty",
           "operator_setpoints")
PINNED_CLASS = {"copilot": "RULE_BASED", "optimizer": "PHYSICS_ESTIMATE", "predictive_maintenance": "RULE_BASED", "root_cause": "RULE_BASED", "pinn_kinetics": "SYNTHETIC_BENCHMARK",
                "federated_learning": "ILLUSTRATION", "multi_agent_negotiation": "ILLUSTRATION", "multi_module_orchestration": "ILLUSTRATION", "sim_to_real": "ILLUSTRATION",
                "time_series_sim": "SYNTHETIC_BENCHMARK", "tda_analysis": "SYNTHETIC_BENCHMARK", "novelty_audit": "RULE_BASED", "safety_flags": "RULE_BASED",
                "regulatory_drafting": "RULE_BASED", "performance_guarantee": "PHYSICS_ESTIMATE", "sa_virtual_sensors": "RULE_BASED", "ai_automation_layer": "RULE_BASED",
                "uncertainty": "PHYSICS_ESTIMATE", "operator_setpoints": "RULE_BASED"}


def _source(module):
    with open(os.path.join(ROOT, "python", module + ".py"), encoding="utf-8") as fh:
        return fh.read()


def maturity_line(source):
    """The `MATURITY:` line of a module docstring, or None."""
    doc = ast.get_docstring(ast.parse(source)) or ""
    found = [l for l in doc.splitlines() if l.startswith("MATURITY:")]
    return found[0] if len(found) == 1 else None


def test_every_listed_module_has_an_entry_a_valid_class_and_no_evidence():
    assert set(mt.MATURITY) == set(MODULES) and len(MODULES) == 19
    for m, e in mt.MATURITY.items():
        assert e["class"] in mt.CLASSES, m
        assert e["evidence"] is None, m                                  # no plant data exists: nothing may claim evidence
        assert e["rationale"].strip() and e["ui_reason"].strip() and isinstance(e["docstring_line"], int), m
    assert mt.CLASSES == ("ILLUSTRATION", "RULE_BASED", "PHYSICS_ESTIMATE", "SYNTHETIC_BENCHMARK", "TRAINED_ON_PLANT_DATA", "VALIDATED_ON_HELDOUT")


def test_the_classes_are_the_pinned_ones_and_none_claims_plant_data():
    assert {m: mt.class_of(m) for m in MODULES} == PINNED_CLASS
    assert all(mt.rank(mt.class_of(m)) <= mt.rank(mt.SYNTHETIC_BENCHMARK) for m in MODULES), "no module is TRAINED_ON_PLANT_DATA or VALIDATED_ON_HELDOUT today"


def test_predictive_maintenance_takes_the_lower_of_its_two_classes_and_says_why():
    """A10b: two classes fit (the inversion is a PHYSICS_ESTIMATE, the status labels are our own thresholds = RULE_BASED); the stated rule takes the lower."""
    e = mt.MATURITY["predictive_maintenance"]
    assert e["class"] == "RULE_BASED" and mt.rank("RULE_BASED") < mt.rank("PHYSICS_ESTIMATE")
    assert "typed-in conversion" in e["rationale"] and "our own thresholds (0.95 / 0.85)" in e["rationale"] and "no plant data" in e["rationale"] and "the lower is taken" in e["rationale"]
    assert "0.95 / 0.85" in e["ui_reason"] and "typed-in" in e["ui_reason"]
    assert mt.caption("predictive_maintenance").startswith("Maturity: RULE_BASED — ")
    from python import predictive_maintenance as pm
    assert (pm.HEALTHY_THRESHOLD, pm.WATCH_THRESHOLD) == (0.95, 0.85)


def test_operator_setpoints_stays_in_the_registry_and_says_it_is_not_an_ai_method():
    e = mt.MATURITY["operator_setpoints"]
    assert e["class"] == "RULE_BASED" and "request mechanism, not an AI method; included because it is a path towards plant setpoints" in e["rationale"]


def test_a_module_missing_from_the_registry_is_an_error():
    with pytest.raises(KeyError):
        mt.class_of("not_a_module")
    with pytest.raises(KeyError):
        mt.describe("not_a_module")


def test_describe_and_caption_carry_the_class_and_the_reason():
    d = mt.describe("pinn_kinetics")
    assert d["class"] == "SYNTHETIC_BENCHMARK" and d["rank"] == 3 and d["evidence"] is None
    c = mt.caption("pinn_kinetics")
    assert c.startswith("Maturity: SYNTHETIC_BENCHMARK — ") and "not validated against plant data" in c
    assert all(mt.caption(m).startswith("Maturity: " + PINNED_CLASS[m]) for m in MODULES)


@pytest.mark.parametrize("module", MODULES)
def test_each_module_docstring_ends_with_its_maturity_line(module):
    line = maturity_line(_source(module))
    assert line == mt.docstring_line(module) and line.startswith(f"MATURITY: {PINNED_CLASS[module]} — ")
    assert ast.get_docstring(ast.parse(_source(module))).splitlines()[-1] == line


def test_a_module_without_the_line_fails_the_scan():
    src = _source("copilot")
    stripped = src.replace("\n" + mt.docstring_line("copilot"), "")
    assert maturity_line(src) is not None and maturity_line(stripped) is None
    assert maturity_line(src.replace('"""', '"""\nMATURITY: RULE_BASED — duplicate\n', 1)) is None          # two lines are not allowed either


def test_no_other_module_carries_a_maturity_line_without_a_registry_entry():
    extra = []
    for path in glob.glob(os.path.join(ROOT, "python", "*.py")):
        name = os.path.splitext(os.path.basename(path))[0]
        if name not in MODULES and name not in ("maturity", "readiness_gate"):
            with open(path, encoding="utf-8") as fh:
                if maturity_line(fh.read()):
                    extra.append(name)
    assert extra == []


@pytest.mark.parametrize("module", MODULES)
def test_the_supporting_docstring_line_says_what_the_entry_quotes(module):
    e = mt.MATURITY[module]
    lines = _source(module).splitlines()
    assert e["docstring_quote"] in lines[e["docstring_line"] - 1], (module, e["docstring_line"])
    assert e["docstring_line"] < len(lines)


def _code_dump(src):
    tree = ast.parse(src)
    if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(getattr(tree.body[0], "value", None), ast.Constant) and isinstance(tree.body[0].value.value, str):
        tree.body = tree.body[1:]
    return ast.dump(tree)


def test_only_the_docstring_of_each_module_changed_versus_origin_main():
    for module in MODULES:
        try:
            old = subprocess.run(["git", "show", f"origin/main:python/{module}.py"], cwd=ROOT, capture_output=True, text=True, check=True, encoding="utf-8").stdout
        except Exception:                                    # noqa: BLE001 -- shallow checkout / no git
            pytest.skip("origin/main not available")
        if maturity_line(old):
            pytest.skip("origin/main already carries the maturity lines (this branch has been merged)")
        assert _code_dump(old) == _code_dump(_source(module)), module


def test_the_registry_and_the_gate_are_not_imported_by_the_engine_or_the_runtime():
    """Only app.py (captions) imports maturity; only python/readiness_gate.py imports it among the modules; nothing imports readiness_gate. The engine, the snapshot, the runtime and the
    dynamics layer never read either."""
    importers = {"maturity": set(), "readiness_gate": set()}
    files = glob.glob(os.path.join(ROOT, "python", "*.py")) + glob.glob(os.path.join(ROOT, "scripts", "*.py")) + [os.path.join(ROOT, "app.py")]
    for path in files:
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        names = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom):
                names |= {a.name for a in n.names} | {(n.module or "").split(".")[-1]}
            elif isinstance(n, ast.Import):
                names |= {a.name.split(".")[-1] for a in n.names}
        rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
        for k in importers:
            if k in names:
                importers[k].add(rel)
    assert importers["maturity"] == {"app.py", "python/readiness_gate.py"}
    assert importers["readiness_gate"] == set()
