"""
Who reads a ledger value (task A3). Derived from the code, never typed in by hand:

  * `engine_input_readers(build_snapshot)` runs the engine once with every registered model wrapped so that each get_input(dep) call is recorded, and returns
    {input key: sorted [keys of the models that really called get_input(input key)]}. This is TEST-ONLY instrumentation: it wraps `SimulationEngine.register_model` for the
    duration of the `with`, changes no model and no published value, and restores the original afterwards. The caller supplies `build_snapshot` (a callable that builds a
    snapshot), so this module holds no database or network code; tests and the export script call it with the in-memory fake in place.
  * `declared_readers()` is the cheap static cousin: the `depends_on` / `lagged_depends_on` declarations of a freshly registered engine (no cycle is run). A model that reads an
    input without declaring it would show in the first and not in the second, so a test compares them.
  * `referrers(module, NAME)` is an `ast` search for the code that names a module constant: Name or Attribute nodes inside the functions of python/*.py, app.py and
    scripts/*.py (tests are excluded). Inside the defining module a bare name counts; elsewhere only an attribute access or an import of that name counts.

Not imported by the engine, the runtime or the app.
"""
import ast
import contextlib
import functools
import glob
import os

from . import simulation_engine as se

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_PARSED = {}
# the code that only READS constants to build tables / reports about them is not a consumer of the plant value
_MACHINERY = {"parameter_table", "ledger_rows", "ledger_consumers", "ledger_coverage", "data_precedence", "measurement_replay", "export_design_basis_ledger",
              "run_residual_report", "make_provenance_worksheet", "run_registry_status_audit", "check_provenance_worksheet"}


def _files():
    return sorted(glob.glob(os.path.join(_ROOT, "python", "*.py"))) + [os.path.join(_ROOT, "app.py")] + sorted(glob.glob(os.path.join(_ROOT, "scripts", "*.py")))


def _tree(path):
    if path not in _PARSED:
        with open(path, encoding="utf-8") as f:
            _PARSED[path] = ast.parse(f.read())
    return _PARSED[path]


def _function_nodes(tree):
    """(name, node) of every top-level function and class method."""
    out = []
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append((n.name, n))
        elif isinstance(n, ast.ClassDef):
            for m in n.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out.append((f"{n.name}.{m.name}", m))
    return out


_INDEX = {}


def _index():
    """One pass over every scanned file: {label: (names imported from a module, [(unit, {Name ids}, {attribute names}, assigned name or None)])}. A unit is a function,
    or one module-level statement (named '<module level>'), so a constant used in another constant's definition is found too."""
    if _INDEX:
        return _INDEX
    for path in _files():
        base = os.path.splitext(os.path.basename(path))[0]
        if base in _MACHINERY:
            continue
        tree = _tree(path)
        imports = {(((n.module or "").split(".")[-1]), a.name) for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names}
        units = []
        for fname, node in _function_nodes(tree):
            units.append((fname, {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}, {n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)}, None))
        for n in tree.body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)):
                continue
            assigned = {t.id for t in getattr(n, "targets", []) if isinstance(t, ast.Name)} | ({n.target.id} if isinstance(getattr(n, "target", None), ast.Name) else set())
            units.append(("<module level>", {x.id for x in ast.walk(n) if isinstance(x, ast.Name)}, {x.attr for x in ast.walk(n) if isinstance(x, ast.Attribute)}, assigned))
        _INDEX[base] = (imports, units)
    return _INDEX


def referrers(module, name):
    """Sorted ["module.function", ...] of the code that names `<module>.<name>` (see the module docstring)."""
    found = set()
    for label, (imports, units) in _index().items():
        in_own = label == module
        imports_name = (module, name) in imports
        for fname, names, attrs, assigned in units:
            if assigned and name in assigned:
                continue                                             # the definition itself is not a use
            if (name in names and (in_own or imports_name)) or name in attrs:
                found.add(f"{label}.{fname}")
    return sorted(found)


@contextlib.contextmanager
def record_reads(reads):
    """While active, every model registered with a SimulationEngine is wrapped so that its get_input(dep) calls are added to `reads` as {dep: set(model keys)}."""
    original = se.SimulationEngine.register_model

    def register_model(self, key, fn, unit, depends_on=(), lagged_depends_on=()):
        @functools.wraps(fn)
        def wrapper(get_input, _key=key, _fn=fn):
            def recording(dep):
                reads.setdefault(dep, set()).add(_key)
                return get_input(dep)
            return _fn(recording)
        return original(self, key, wrapper, unit, depends_on, lagged_depends_on)

    se.SimulationEngine.register_model = register_model
    try:
        yield reads
    finally:
        se.SimulationEngine.register_model = original


def engine_input_readers(build_snapshot):
    """{input key: sorted list of the model keys that called get_input(input key)} over everything `build_snapshot()` runs."""
    reads = {}
    with record_reads(reads):
        build_snapshot()
    return {k: sorted(v) for k, v in reads.items()}


def declared_readers():
    """{dep key: sorted list of model keys that DECLARE it in depends_on / lagged_depends_on} for a freshly registered full engine (no cycle is run)."""
    from . import (ai_automation_layer as ai, eu_utilities_chp as eu, fe_feed_handling as fe, ga001_gasifier_model as ga001, gc_gas_cleaning_chain as gc,
                   hb_remaining_chain as hbrem, hb_wgs_psa_storage_chain as hbchain, sa_virtual_sensors as sa, shared_plant_state as sps)
    engine = se.SimulationEngine(sps.SharedPlantState())
    for reg in (fe.register_fe_chain, ga001.register_ga001, gc.register_gc_chain, hbchain.register_hb_chain, hbrem.register_hb_remaining,
                eu.register_eu_chain, sa.register_sa_sensors, ai.register_ai_layer):
        reg(engine)
    out = {}
    for key, spec in engine._models.items():
        for dep in list(spec["depends_on"]) + list(spec["lagged_depends_on"]):
            out.setdefault(dep, set()).add(key)
    return {k: sorted(v) for k, v in out.items()}
