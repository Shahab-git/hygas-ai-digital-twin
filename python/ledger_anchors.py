"""
Stable anchors for the design-basis ledger (task A3c, section 1). Nothing here is imported by the engine, the runtime or the app.

`file_line` ("python/psa.py:12") moves whenever someone adds a line above the constant, which made the committed export stale for reasons that have nothing to do with the ledger. The committed
`docs/design_basis_ledger.md` / `.csv` therefore carry `anchor` instead; `build_ledger()` keeps `file_line` for interactive use.

An anchor names WHERE the value lives by symbol, never by line:

  module:NAME                        a module-level constant (`psa:K1`); a dict entry adds its keys (`uncertainty:ASSUMPTIONS['feed_sulfur_ppm']['point']`); an entry of a list of
                                     named dicts is addressed by its `name` (`ga001_energy_balance:ASSUMED_INPUTS['air preheat temperature (degC)']['value']`), not by its position;
  module:function:variable           a numeric literal inside a function, named by what it is assigned to (`gc_gas_cleaning_chain:gc003_dust:efficiency`), by its keyword argument
                                     or by the parameter it is the default of; several literals of one row are joined with `+` (`kinetics:hts_conversion:T_K+GHSV+y_CO_in+steam_to_CO`);
  module:function:variable#k         the k-th literal of that name in that function when the function has several of the same name (an ordinal, reported as AMBIGUOUS);
  module:function#n                  a literal with no stable name (not assigned to anything, not a keyword, not a default): n counts the scanned numeric literals of THAT FUNCTION in source
                                     order, starting at 1 (reported as a FALLBACK);
  registry:ITEM/parameter            a registry row;
  module:symbol                      for an engine input, the module-level symbol that holds its default (`uncertainty:ASSUMPTIONS['equivalence_ratio']`).
"""
import ast
import re

from . import ledger_coverage as lc

_CONST_SRC = re.compile(r"^(?:module constant )?(\w+)\.(\w+)((?:\[[^\]]*\])*)")
_REG_SRC = re.compile(r"^registry (\S+) '(.+)'$")
_LINE_REF = re.compile(r"(\.(?:py|json)):\d+(?:-\d+)?")


def strip_code_lines(text):
    """The text with the line numbers of code and registry references removed (`psa.py:12` becomes `psa.py`): used for the committed export, where a line number would go stale."""
    return _LINE_REF.sub(r"\1", text) if isinstance(text, str) else text


def module_of(file):
    return file.rsplit("/", 1)[-1][:-3]


class _Nodes(lc._Literals):
    """lc._Literals, but remembering the node of every literal."""

    def __init__(self):
        super().__init__()
        self.nodes = []

    def visit_Constant(self, n):
        if self.fn and lc._is_num(n) and n.value not in (0, 1, 2):
            self.found.append((n.lineno, n.col_offset, self.fn[-1], n.value))
            self.nodes.append(n)


def _name_of(node, parents):
    """What the literal is assigned to: an assignment target, a keyword argument, a parameter default or a dict key. None when it has no stable name."""
    child, p = node, parents.get(node)
    while p is not None:
        if isinstance(p, ast.keyword):
            return p.arg
        if isinstance(p, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            t = p.targets[0] if isinstance(p, ast.Assign) else p.target
            return t.id if isinstance(t, ast.Name) else (t.attr if isinstance(t, ast.Attribute) else None)
        if isinstance(p, ast.arguments):
            pos = p.posonlyargs + p.args
            if child in p.defaults:
                return pos[len(pos) - len(p.defaults) + p.defaults.index(child)].arg
            if child in p.kw_defaults:
                return p.kwonlyargs[p.kw_defaults.index(child)].arg
            return None
        if isinstance(p, ast.Dict) and child in p.values:
            k = p.keys[p.values.index(child)]
            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                return k.value
        if isinstance(p, ast.stmt):
            return None
        child, p = p, parents.get(p)
    return None


def function_literals(source, function):
    """[(name_or_None, value_key, node)] for every scanned numeric literal of `function`, in source order (the same literals lc.scan_source counts)."""
    tree = ast.parse(source)
    parents = {c: p for p in ast.walk(tree) for c in ast.iter_child_nodes(p)}
    v = _Nodes()
    v.visit(tree)
    rows = sorted(zip(v.found, v.nodes), key=lambda t: (t[0][0], t[0][1]))
    return [(_name_of(n, parents), lc.norm_value(f[3]), n) for f, n in rows if f[2] == function]


def literal_anchor(file, source, function, values):
    """(anchor, flags) of a ledger row that covers the numeric literals `values` of `function`. flags: set of 'ambiguous' / 'fallback'."""
    occ = function_literals(source, function)
    tokens, flags = [], set()
    for val in values:
        key = lc.norm_value(val)
        pos = next((i for i, (_, k, _) in enumerate(occ) if k == key), None)
        if pos is None:
            raise LookupError(f"{file}: {function}() has no scanned literal {val!r}")
        name = occ[pos][0]
        if name is None:
            tokens.append(f"#{pos + 1}")
            flags.add("fallback")
            continue
        same = [i for i, (nm, _, _) in enumerate(occ) if nm == name]
        if len(same) > 1:
            tokens.append(f"{name}#{same.index(pos) + 1}")
            flags.add("ambiguous")
        else:
            tokens.append(name)
    mod = module_of(file)
    if len(tokens) == 1 and tokens[0].startswith("#"):
        return f"{mod}:{function}{tokens[0]}", flags
    return f"{mod}:{function}:" + "+".join(tokens), flags


def path_anchor(module, name, path, obj):
    """`module:NAME['k']...` for a dict entry; an integer step into a list of dicts that have a `name` is written as that name."""
    out = f"{module}:{name}"
    cur = obj
    for step in path:
        if isinstance(step, int) and isinstance(cur, (list, tuple)) and isinstance(cur[step], dict) and isinstance(cur[step].get("name"), str):
            out += f"[{cur[step]['name']!r}]"
        else:
            out += f"[{step!r}]"
        cur = cur[step]
    return out


def symbol_at(source, file, line):
    """`module:NAME` or `module:NAME['key']` of the module-level assignment that covers `line` (a dict entry is followed down by its string keys). None if there is none."""
    tree = ast.parse(source)
    for n in tree.body:
        if not isinstance(n, (ast.Assign, ast.AnnAssign)) or not (n.lineno <= line <= n.end_lineno):
            continue
        t = n.targets[0] if isinstance(n, ast.Assign) else n.target
        if not isinstance(t, ast.Name):
            continue
        out, val = f"{module_of(file)}:{t.id}", n.value
        while isinstance(val, ast.Dict):
            hit = next(((k, v) for k, v in zip(val.keys, val.values) if v.lineno <= line <= v.end_lineno), None)
            if hit is None or not (isinstance(hit[0], ast.Constant) and isinstance(hit[0].value, str)):
                break
            out += f"[{hit[0].value!r}]"
            val = hit[1]
        return out
    return None


def table_anchor(row, read):
    """Anchor of a row of parameter_table.build_table(); `read(file)` returns a source file's text."""
    src = row["source"]
    m = _REG_SRC.match(src)
    if m:
        return f"registry:{m.group(1)}/{m.group(2)}"
    if src.startswith("engine input"):
        file, line = row["file_line"].rsplit(":", 1)
        return symbol_at(read(file), file, int(line)) or f"{module_of(file)}:line-{line}"
    m = _CONST_SRC.match(src)
    if m:
        return f"{m.group(1)}:{m.group(2)}{m.group(3)}"
    file, line = row["file_line"].rsplit(":", 1)
    return symbol_at(read(file), file, int(line)) or src


def anchor_report(ledger):
    """Counts for the report: rows, ambiguous anchors (an ordinal `#k` after a name), fallback anchors (`function#n`), and anchors shared by two rows (must be none)."""
    anchors = [r["anchor"] for r in ledger]
    flags = {r["anchor"]: r.get("anchor_flags", set()) for r in ledger}
    return {"rows": len(anchors), "ambiguous": sorted(a for a in set(anchors) if "ambiguous" in flags[a]), "fallback": sorted(a for a in set(anchors) if "fallback" in flags[a]),
            "shared": sorted({a for a in anchors if anchors.count(a) > 1})}
