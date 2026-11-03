"""Wording pass W1.3: the repo has no plant data and no comparison with a plant, so no module, comment or datasheet text may call its own physics, models or ranges "validated" / "already
validated" / "independently validated". A correct use stays: "design-target validated (75.0 % ...)" names the target; "validated against a stated design target"; input validation;
a source paper's own claim; the readiness-gate vocabulary in python/maturity.py and python/readiness_gate.py. This scan lists the unsupported phrasings that W1.2 / W1.3 removed
and fails when one returns in python/, scripts/ or app.py (same idea as the A10b-3 scan in tests/test_ai_maturity_ui.py). Offline; reads source text only."""
import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
EXEMPT = {"python/maturity.py", "python/readiness_gate.py"}              # the vocabulary of the gates (VALIDATED_ON_HELDOUT, physical_model_validated, ...)

UNSUPPORTED = re.compile(
    r"already[- ]validated|independently[- ]validated|independently real/validated|live[- ]validated|genuinely validated|"
    r"real, validated number|repo's validated physics|a validated (?:physics|part-load)|own validated(?! HTS design target)|validated physics results|doubly validated|(?-i:validated RANGE)|modeled/validated|"
    r"full validated (?:domain|range)|(?-i:Validated physical range)|established and validated|that validated|the validated source of truth|already validated(?::| in )|validated output|ACTUAL data\W{1,4}validated",
    re.IGNORECASE)

# the sentences as they read before W1.2 / W1.3 (flattened); every one must be matched by UNSUPPORTED, and none may be in a file
REMOVED = (
    "organize the plant's ACTUAL data — validated physics results", "backed by a real, validated number computed live", "call against this repo's validated physics, not a hardcoded literal",
    "THE ALREADY-VALIDATED WGS REACTION KINETICS", "a validated physics core (WGS kinetics, PSA)", "a validated part-load physics correlation", "sourced from a validated physics module",
    "check chp.py's/dispatch_ga.py's own validated outputs", "a validated physics core (HB-001 through HB-009", "is doubly validated, not a single unchecked source", "the RFI gives a validated RANGE",
    "own validated physics-informed loss", "is the full validated range", "spanning the full validated domain", "already established and validated (this module's",
    "connecting the already-validated,", "real modeled/validated work", "kinetics.py's own validated output", "has already validated: 300-400C", "# Validated physical range (matches",
    "default to the full validated domain", "is the validated source of truth", "own already-validated simulation physics", "loss terms already validated in pinn_kinetics.py",
    "real, already-validated steady-state", "without touching that validated module",
    "independently-validated real duties", "each independently already-validated", "independently real/validated",
    "own already-validated GC-004/HB-003/HB-012 models", "derived from this project's own already-validated models",
    "kinetics.py's WGS reactor, already validated against a stated design target", "own math is deterministic and already validated exactly against their design targets",    # W2.4
)
KEPT = (   # correct uses that must NOT be flagged
    "design-target validated (75.0% at the original default composition",
    "kinetics.py's WGS reactor, checked against the stated design target",
    "own math is deterministic and checked against their stated design targets",
    "NOT validated against a DOK-ING-confirmed design point", "not validated against plant data", "tab limits, not validated ranges", "Cross-validated LIVE against DOK-ING's own",
    "validated against lab-scale transient tests", "VALIDATED_ON_HELDOUT", "physical_model_validated", "none validated against plant data", "kinetics.py's own validated HTS design target", "Tab limits, not a validated range",
)


def _flat(text):
    return re.sub(r"\s*\n\s*(?:#\s*)?", " ", text)


def _sources():
    out = {}
    for folder in ("python", "scripts"):
        for name in sorted(os.listdir(os.path.join(ROOT, folder))):
            if name.endswith(".py") and f"{folder}/{name}" not in EXEMPT:
                out[f"{folder}/{name}"] = open(os.path.join(ROOT, folder, name), encoding="utf-8").read()
    out["app.py"] = open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()
    return out


def _offenders(sources):
    return [(rel, m.group(0)) for rel, src in sources.items() for m in UNSUPPORTED.finditer(_flat(src))]


def test_no_module_calls_its_own_physics_or_models_validated_without_evidence():
    assert _offenders(_sources()) == []


def test_every_removed_sentence_is_matched_by_the_scan_and_is_in_no_file():
    for phrase in REMOVED:
        assert UNSUPPORTED.search(phrase), f"the scan does not recognise {phrase!r}"
    blob = "\n".join(_flat(s) for s in _sources().values())
    assert [p for p in REMOVED if p in blob] == []


def test_the_correct_uses_are_not_flagged():
    for phrase in KEPT:
        assert not UNSUPPORTED.search(phrase), phrase


def test_a_reintroduced_phrase_is_caught_in_a_module_a_comment_and_app_py():
    sources = _sources()
    assert _offenders(sources) == []
    for phrase in REMOVED:
        for rel, add in (("python/kinetics.py", f'\n"""{phrase}"""\n'), ("python/psa.py", f"\n# {phrase}\n"), ("app.py", f'\nst.caption("{phrase}")\n')):
            hits = _offenders(dict(sources, **{rel: sources[rel] + add}))
            assert hits, f"{phrase!r} re-introduced in {rel} was not caught"
    split = sources["python/kinetics.py"] + "\n# a validated\n# physics core\n"                       # across a line break
    assert _offenders(dict(sources, **{"python/kinetics.py": split}))
