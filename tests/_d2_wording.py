"""Ledger D2 (task A3, deliberate): three persisted snapshot notes were reworded, text only (they called a registry value "Confirmed").

Older tests compare the live snapshot with fixtures that were made BEFORE that rewording (tests/fixtures/snapshot_origin_main_71e92cc / 198bfcb / f628406). Those
tests pass the live serialised snapshot through `undo()`, which maps exactly these six phrases back to the old text and nothing else, so every other character of
every persisted value is still compared exactly. tests/test_design_basis_ledger.py compares against the 701de71 fixture and asserts the NEW text is present."""

# (new phrase, old phrase): applied in this order
PAIRS = (
    ("registry '>98% removal efficiency' (Unverified (registry), not DOK-ING-confirmed)", "own Confirmed '>98% removal efficiency'"),
    ("registry >90% efficiency (>d50=15um; Unverified (registry))", "own Confirmed >90% efficiency (>d50=15um)"),
    ("ACTUAL/DOK-ING VALUE: Unverified (registry), not DOK-ING-confirmed -- 20 kW", "ACTUAL/DOK-ING VALUE: Confirmed -- 20 kW"),
    ("Unverified (registry), not DOK-ING-confirmed -- 20 kW, scoped to EU-004 jacket cooling only (per EU-008's own", "Confirmed -- 20 kW, scoped to EU-004 jacket cooling only (per EU-008's own"),
)
ENTRIES = ("FE-002|", "GC-001|", "EU-008|")      # the only snapshot keys whose text carries them


def _undo_text(s):
    for new, old in PAIRS:
        s = s.replace(new, old)
    return s


def _walk(x):
    if isinstance(x, str):
        return _undo_text(x)
    if isinstance(x, dict):
        return {k: _walk(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_walk(v) for v in x]
    return x


def undo(serialised):
    """serialised = {"A|B": entry}. Returns the same with the D2 rewording mapped back to the old text, in the entries that can carry it."""
    return {k: (_walk(v) if k.startswith(ENTRIES) else v) for k, v in serialised.items()}
