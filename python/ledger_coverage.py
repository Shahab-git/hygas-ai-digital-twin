"""
Design-basis ledger coverage (task A3): which numeric constants can influence a published key, and is each one a ledger row or a justified exception?

Pure `ast` scan, no Streamlit, no database, no network, no import of the scanned modules (they are only parsed). Three kinds of item are found in the modules
that feed published keys (SCAN_MODULES):

  * `const`     a module-level UPPER_CASE assignment whose value is built only from numeric literals (a float, a tuple/dict of floats, `0.79 / 0.21`);
  * `composite` a module-level UPPER_CASE literal container that mixes numbers with strings / names (for example a dict of {"value": 0.7, "status": ps.STATUS_ASSUMED});
  * `literal`   a numeric literal inside a function body that is not 0, 1 or 2 (index, range / round / len arguments, f-strings, docstrings, `raise` and `assert` are skipped).

Every item has a stable key:  const / composite -> "const|<file>|<NAME>";  literal -> "lit|<file>|<function>|<value>" (all occurrences of the same value in one function are
ONE item, so "1000.0 in this function" is classified once).

An item is accounted for if (a) a ledger row lists it in its `covers`, or (b) `data/ledger_exceptions.json` lists it with a class (PHYSICAL CONSTANT, NUMERICAL, PRESENTATION,
SELF-TEST FIXTURE or PUBLISHED CORRELATION COEFFICIENT) and a one-line reason. A PUBLISHED CORRELATION COEFFICIENT names the correlation and its source as the repo names it (author and
year), or says `source NOT STATED in repo`; the rule is enforced by exception_problems(). Whatever is neither is an unregistered PARAMETER: `uncovered()` returns it, and a test fails.

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
CLASS_CORRELATION = "PUBLISHED CORRELATION COEFFICIENT"      # a coefficient of a published empirical correlation (not a physical constant, not a model parameter)
EXCEPTION_CLASSES = (CLASS_PHYSICAL, CLASS_NUMERICAL, CLASS_PRESENTATION, CLASS_FIXTURE, CLASS_CORRELATION)
NO_SOURCE = "source NOT STATED in repo"


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
        if e.get("class") == CLASS_CORRELATION:
            reason = str(e.get("reason", ""))
            if "correlation" not in reason.lower():
                bad.append((e.get("key"), "a correlation coefficient must name the correlation"))
            if NO_SOURCE not in reason and not re.search(r"\((19|20)\d\d\)", reason):
                bad.append((e.get("key"), "a correlation coefficient must name its source with a year, e.g. 'Moe (1962)', or say '%s'" % NO_SOURCE))
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


# --- the "Confirmed" mention guard (task A3b 2.2) --------------------------------------------------------------------------------------------------
# Every line of the engine modules that mentions "confirmed" (case-insensitive) is classified, and tests/test_design_basis_ledger.py pins the counts per class and file, so a NEW
# REGISTRY-STATED use fails. The ~450 existing mentions are not rewritten here. Classes (the line decides; the sentence and the next 3 lines are looked at for a source):
#   DOK-ING-SOURCED  the line or one of the next 3 lines names a DOK-ING source: an RFI (RFI / RFI #n / dokink_rfi_answers / rfi_dokink), a DOK-ING answer, response, reply or email;
#   GENERIC          explanatory use that states no value as Confirmed: a negation ("not confirmed", "none of this is confirmed"), the status vocabulary ("Confirmed / Calculated",
#                    "status is Confirmed", STATUS_CONFIRMED, set_confirmed, a name such as HB010_CONFIRMED_*), a line that itself says Unverified, or the verb ("confirmed by", "(confirmed:");
#   REGISTRY-STATED  everything else: the word is used for a value or a design figure that the registry states, with no DOK-ING source named next to it.
# `where` says what the line is: docstring, comment, string (a literal that may be published or shown) or code (an identifier).
CONFIRMED_SCOPE = SCAN_MODULES + ("tab1_integration",)
MENTION_SOURCED, MENTION_GENERIC, MENTION_REGISTRY = "DOK-ING-SOURCED", "GENERIC", "REGISTRY-STATED"
MENTION_CLASSES = (MENTION_SOURCED, MENTION_GENERIC, MENTION_REGISTRY)
_RFI = re.compile(r"\bRFI\b|dokink_rfi|rfi_dokink|rfi_answers|Ankica|DOK-ING'?s? (?:own |real |verbatim )?(?:answer|response|reply|email)|data/dokink", re.IGNORECASE)
_NEG = re.compile(r"\b(?:not|never|no|none|nor|without|hasn't|isn't|doesn't|cannot|can't)\b[^.\n]{0,70}\bconfirm|\bunconfirm|\bnon-?confirm|DOK-ING-confirmed|DOK-ING confirmed\?", re.IGNORECASE)
_CODE_NAME = re.compile(r"STATUS_CONFIRMED|set_confirmed|clear_confirmed|get_confirmed|_confirmed\b|confirmed_|[A-Z0-9]_CONFIRMED|CONFIRMED_[A-Z]|confirmation_loop|is_confirmed")
_VOCAB = re.compile(r"Confirmed\s*[/,|]\s*(?:Calculated|Estimate|Assumed|Missing|Unverified)|(?:Calculated|Estimate\w*|Assumed|Missing|Unverified)\s*[/,|]\s*Confirmed|"
                    r"\bConfirmed\b\s*(?:means|=)|status\s+(?:is\s+|of\s+)?Confirmed|Unverified", re.IGNORECASE)
_VERB = re.compile(r"\bconfirmed\s+(?:by|that|via)\b|\(confirmed:|\b(?:was|were|been) confirmed\b", re.IGNORECASE)


def classify_mention(lines, i):
    """Class of the mention on line index `i` (0-based) of `lines`; the line and the next 3 lines are searched for a DOK-ING source."""
    if _RFI.search("\n".join(lines[i:i + 4])):
        return MENTION_SOURCED
    cur = lines[i]
    if _NEG.search(cur) or _CODE_NAME.search(cur) or _VOCAB.search(cur) or _VERB.search(cur):
        return MENTION_GENERIC
    return MENTION_REGISTRY


def _line_kinds(text):
    """(docstring lines, string-literal lines, comment lines) of a source text."""
    import io
    import tokenize
    tree = ast.parse(text)
    doc, strs, comments = set(), set(), set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            b = node.body
            if b and isinstance(b[0], ast.Expr) and isinstance(getattr(b[0], "value", None), ast.Constant) and isinstance(b[0].value.value, str):
                doc.update(range(b[0].lineno, b[0].end_lineno + 1))
        if isinstance(node, ast.JoinedStr) or (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            strs.update(range(node.lineno, node.end_lineno + 1))
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type == tokenize.COMMENT:
            comments.add(tok.start[0])
    return doc, strs - doc, comments


def confirmed_mentions(sources=None):
    """Every line of the CONFIRMED_SCOPE modules that mentions "confirmed": [{file, line, text, class, where}]. `sources` = {relative file: text} replaces a file (tests)."""
    out = []
    for mod in CONFIRMED_SCOPE:
        file = rel_path(mod)
        text = (sources or {}).get(file)
        if text is None:
            with open(os.path.join(_ROOT, file), encoding="utf-8") as f:
                text = f.read()
        text = text.replace("\r\n", "\n")
        lines = text.split("\n")
        doc, strs, comments = _line_kinds(text)
        for i, line in enumerate(lines):
            if re.search("confirmed", line, re.IGNORECASE):
                n = i + 1
                where = "docstring" if n in doc else "string" if n in strs else "comment" if n in comments else "code"
                out.append({"file": file, "line": n, "text": line.strip(), "class": classify_mention(lines, i), "where": where})
    return out


def mention_counts(mentions=None):
    """{file: {class: n}} of confirmed_mentions()."""
    counts = {}
    for m in (mentions if mentions is not None else confirmed_mentions()):
        counts.setdefault(m["file"], {c: 0 for c in MENTION_CLASSES})[m["class"]] += 1
    return counts


_QUOTED = re.compile(r"""(?:[fFrRbBuU]{0,2})("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')""")


def persisted_mentions(mentions, texts):
    """The mentions that are published: those on a string-literal line whose literal text around the word "confirmed" (the parts between f-string fields, at least 8 characters) occurs
    in one of `texts` (the strings of a live snapshot, joined). A mention can be published without being found here only if its text is assembled from several literals on other lines."""
    blob = "\n".join(texts)
    out = []
    for m in mentions:
        if m["where"] != "string":
            continue
        hit = False
        for q in _QUOTED.finditer(m["text"]):
            body = q.group(1)[1:-1].replace('\\"', '"').replace("\\'", "'")
            for part in re.split(r"\{[^{}]*\}", body):
                if re.search("confirmed", part, re.IGNORECASE) and len(part.strip()) >= 8 and part.strip() in blob:
                    hit = True
        if hit:
            out.append(m)
    return out
