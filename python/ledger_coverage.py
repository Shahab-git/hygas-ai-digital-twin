"""
Design-basis ledger coverage (task A3): which numeric constants can influence a published key, and is each one a ledger row or a justified exception?

Pure `ast` scan, no Streamlit, no database, no network, no import of the scanned modules (they are only parsed). Three kinds of item are found in the modules
that feed published keys (SCAN_MODULES):

  * `const`     a module-level UPPER_CASE assignment whose value is built only from numeric literals (a float, a tuple/dict of floats, `0.79 / 0.21`);
  * `composite` a module-level UPPER_CASE literal container that mixes numbers with strings / names (for example a dict of {"value": 0.7, "status": ps.STATUS_ASSUMED});
  * `literal`   a numeric literal inside a function body that is not 0, 1 or 2 (index, range / round / len arguments, f-strings, docstrings, `raise` and `assert` are skipped).

Every item has a stable key:  const / composite -> "const|<file>|<NAME>";  literal -> "lit|<file>|<function>|<value>" (all occurrences of the same value in one function are
ONE item, so "1000.0 in this function" is classified once).

An item is accounted for if (a) a ledger row lists it in its `covers`, or (b) `data/ledger_exceptions.json` lists it with a class (PHYSICAL CONSTANT, NUMERICAL, PRESENTATION or
SELF-TEST FIXTURE) and a one-line reason. Whatever is neither is an unregistered PARAMETER: `uncovered()` returns it, and a test fails.

Nothing here is imported by the engine, the runtime or the app.
"""
import ast
import json
import os
import re

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
EXCEPTIONS_FILE = "data/ledger_exceptions.json"

SCAN_MODULES = (
    "ga001_gasifier_model", "ga001_energy_balance", "ga001_carbon_accounting", "gasifier_mass_balance", "gc_gas_cleaning_chain",
    "hb_wgs_psa_storage_chain", "hb_remaining_chain", "eu_utilities_chp", "chp", "kinetics", "psa", "plant_heat_integration",
    "balance_audit", "fe_feed_handling", "circularity", "uncertainty", "reference_feeds",
)

CLASS_PHYSICAL = "PHYSICAL CONSTANT"
CLASS_NUMERICAL = "NUMERICAL"
CLASS_PRESENTATION = "PRESENTATION"
CLASS_FIXTURE = "SELF-TEST FIXTURE"
EXCEPTION_CLASSES = (CLASS_PHYSICAL, CLASS_NUMERICAL, CLASS_PRESENTATION, CLASS_FIXTURE)


def rel_path(module):
    return f"python/{module}.py"


def _is_num(node):
    return isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool)


def _numeric_only(node):
    """True if the expression is built only from numeric literals and arithmetic (a literal constant, not derived from another name)."""
    if _is_num(node):
        return True
    if isinstance(node, ast.UnaryOp):
        return _numeric_only(node.operand)
    if isinstance(node, ast.BinOp):
        return _numeric_only(node.left) and _numeric_only(node.right)
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return bool(node.elts) and all(_numeric_only(e) for e in node.elts)
    if isinstance(node, ast.Dict):
        return bool(node.values) and all(_numeric_only(v) for v in node.values) and all(isinstance(k, ast.Constant) for k in node.keys)
    return False


def _pure_container(node):
    """A literal container whose leaves are constants / names / attributes: no call, lambda or comprehension anywhere inside."""
    if not isinstance(node, (ast.Dict, ast.List, ast.Tuple)):
        return False
    return not any(isinstance(n, (ast.Call, ast.Lambda, ast.comprehension)) for n in ast.walk(node))


def _n_numeric(node):
    return sum(1 for n in ast.walk(node) if _is_num(n))


def _upper(name):
    return name.upper() == name and any(c.isalpha() for c in name)


def norm_value(v):
    """Stable text of a literal for the item key (floats keep repr, so 1000 and 1000.0 stay distinct and cannot collide)."""
    return repr(v)


def const_key(file, name):
    return f"const|{file}|{name}"


def lit_key(file, function, value):
    return f"lit|{file}|{function}|{norm_value(value)}"


class _Literals(ast.NodeVisitor):
    def __init__(self):
        self.found = []       # (lineno, col, function, value)
        self.fn = []

    def visit_FunctionDef(self, n):
        self.fn.append(n.name)
        body = n.body
        if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) and isinstance(body[0].value.value, str):
            body = body[1:]
        for d in n.args.defaults + [x for x in n.args.kw_defaults if x is not None]:
            self.visit(d)
        for b in body:
            self.visit(b)
        self.fn.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_JoinedStr(self, n):
        pass

    def visit_Subscript(self, n):
        self.visit(n.value)                       # an index is not a parameter

    def visit_Call(self, n):
        name = n.func.id if isinstance(n.func, ast.Name) else (n.func.attr if isinstance(n.func, ast.Attribute) else "")
        if name in ("range", "enumerate", "round", "len"):
            self.visit(n.func)
            return
        self.generic_visit(n)

    def visit_Raise(self, n):
        pass

    def visit_Assert(self, n):
        pass

    def visit_Constant(self, n):
        if self.fn and _is_num(n) and n.value not in (0, 1, 2):
            self.found.append((n.lineno, n.col_offset, self.fn[-1], n.value))


def _read(file, sources):
    if sources and file in sources:
        return sources[file]
    with open(os.path.join(_ROOT, file), encoding="utf-8") as f:
        return f.read()


def scan_source(file, source):
    """Items of one file's source text (see the module docstring)."""
    tree = ast.parse(source)
    items = []
    for n in tree.body:
        if isinstance(n, ast.Assign):
            targets, val = [t for t in n.targets if isinstance(t, ast.Name)], n.value
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.value is not None:
            targets, val = [n.target], n.value
        else:
            continue
        for t in targets:
            if not _upper(t.id):
                continue
            if _numeric_only(val):
                kind = "const"
            elif _pure_container(val) and _n_numeric(val):
                kind = "composite"
            else:
                continue
            items.append({"kind": kind, "key": const_key(file, t.id), "file": file, "line": n.lineno, "name": t.id, "function": None,
                          "value": ast.unparse(val)[:120], "count": 1})
    v = _Literals()
    v.visit(tree)
    groups = {}
    for lineno, col, fn, value in sorted(v.found):
        k = lit_key(file, fn, value)
        if k in groups:
            groups[k]["count"] += 1
        else:
            groups[k] = {"kind": "literal", "key": k, "file": file, "line": lineno, "name": None, "function": fn, "value": norm_value(value), "count": 1}
    return items + list(groups.values())


def scan(modules=SCAN_MODULES, sources=None):
    """All items of the scanned modules. `sources` = {relative file: source text} replaces the file on disk (the mutation test adds a constant to a copy)."""
    items = []
    for m in modules:
        f = rel_path(m)
        items += scan_source(f, _read(f, sources))
    return items


def load_exceptions(path=None):
    with open(path or os.path.join(_ROOT, EXCEPTIONS_FILE), encoding="utf-8") as f:
        return json.load(f)["entries"]


def exception_problems(entries):
    """Entries that break the rule (a class outside EXCEPTION_CLASSES, or no reason). Empty list = fine."""
    bad = []
    for e in entries:
        if e.get("class") not in EXCEPTION_CLASSES:
            bad.append((e.get("key"), "class %r is not one of %s" % (e.get("class"), EXCEPTION_CLASSES)))
        if not str(e.get("reason", "")).strip():
            bad.append((e.get("key"), "no reason"))
    return bad


def uncovered(items, covered_keys, exceptions):
    """The unregistered PARAMETERs: scanned items that are neither covered by a ledger row nor listed as an exception."""
    ok = set(covered_keys) | {e["key"] for e in exceptions}
    return [i for i in items if i["key"] not in ok]


def stale(items, covered_keys, exceptions):
    """Keys in `covers` / the exception list that the scan no longer finds (a constant moved or was renamed), and keys that are both a row and an exception."""
    present = {i["key"] for i in items}
    exc = {e["key"] for e in exceptions}
    return {"covers_not_found": sorted(set(covered_keys) - present), "exceptions_not_found": sorted(exc - present),
            "both_row_and_exception": sorted(set(covered_keys) & exc)}


# --- the status rules of the ledger (task A3, C.3) --------------------------------------------------------------------------------------------------

_FORMULA = re.compile(r"(\bformula\b|\d\s*[x\u00d7*/=]\s*[\w(])", re.IGNORECASE)


def status_problems(rows):
    """Rule violations in ledger rows (dicts with ledger_id, status, origin, source_line, note). Empty list = fine.
      * Confirmed needs a non-empty source_line that names DOK-ING and an origin of DOK-ING (Confirmed means DOK-ING source cited);
      * a row whose origin is ASSUMED or UNKNOWN cannot be Confirmed;
      * a Calculated row names its formula (the words 'formula', or an expression such as '0.25 x ...', in its note or source_line)."""
    bad = []
    for r in rows:
        rid, status, origin = r.get("ledger_id"), r.get("status"), r.get("origin")
        if status == "Confirmed":
            line = str(r.get("source_line") or "")
            if not line.strip() or "dok-ing" not in line.lower():
                bad.append((rid, "Confirmed without a source_line that names DOK-ING"))
            if origin in ("ASSUMED", "UNKNOWN"):
                bad.append((rid, "origin %s cannot be Confirmed" % origin))
            elif origin != "DOK-ING":
                bad.append((rid, "Confirmed needs origin DOK-ING, got %r" % origin))
        if status == "Calculated" and not _FORMULA.search(str(r.get("note") or "") + " " + str(r.get("source_line") or "")):
            bad.append((rid, "Calculated without a formula in note or source_line"))
    return bad
