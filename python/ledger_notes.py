"""
The prose sections of docs/design_basis_ledger.md that are not rows (task A3b): known undeclared reads, constants nothing uses, inconsistencies that are recorded and NOT fixed, the note on inline
literals, the question references and the RFI mapping. Every file:line is looked up from a token at generation time (`locate`), so it cannot go stale silently, and
tests/test_design_basis_ledger.py checks that each token is still found. Nothing here is imported by the engine, the runtime or the app.
"""
import os

from . import ledger_questions as lq

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def locate(file, token, after=None):
    """'file:line' of the first line of `file` that contains `token` (searching from the first line that contains `after`, if given), or None."""
    started = after is None
    with open(os.path.join(_ROOT, file), encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            if not started:
                started = after in line
            if started and token in line:
                return f"{file}:{i}"
    return None


# (reader, the key it reads without declaring it, [(file, token)], why, fix)
KNOWN_UNDECLARED_READS = [
    {"reader": ("GA-001", "EnergyBalance"), "reads": ("GA-001", "CarbonAccounting"),
     "where": [("python/balance_audit.py", 'snapshot.get(("GA-001", "CarbonAccounting"))'), ("python/ga001_energy_balance.py", "DEPENDS_ON = [")],
     "why": "balance_audit.carbon_black_flows (called through ga001_terms from ga001_energy_balance.energy_balance) reads the derived carbon black; ga001_energy_balance declares it neither in DEPENDS_ON nor in LAGGED."},
    {"reader": ("HB-009", "TailGas"), "reads": ("WGS", "Composition"),
     "where": [("python/hb_wgs_psa_storage_chain.py", 'wgs = get_input(("WGS", "Composition"))["value"]', "def hb009_tail_gas"), ("python/hb_wgs_psa_storage_chain.py", 'engine.register_model(("HB-009", "TailGas")')],
     "why": "hb009_tail_gas reads the WGS composition; its registration declares only HB-006 PSA and GC-013 Gas."},
]
KNOWN_UNDECLARED_FIX = "The fix is deferred to the output-status-inheritance task (A9), which needs the real read graph; tests/test_design_basis_ledger.py pins exactly these two, so a third hidden read fails."

INLINE_LITERAL_NOTE = ("A number that is hard-coded inside a function (for example `efficiency = 0.95` in `gc003_dust`) is read from the function's `ast` (`via` = `code only`, source `literal ... inside f() (read from its ast)`). "
                       "It stays inline: extraction into a named constant happens only when a later task edits that function anyway.")

# (name, file, token on its definition line, what the code says about it)
UNUSED_CONSTANTS = [
    ("FE001_TOTAL_CAPACITY_T", "python/fe_feed_handling.py", "FE001_TOTAL_CAPACITY_T = 2.0",
     "Defined under the comment '# --- FE-001 Hopper (Confirmed figures)'; no other line of the repository names it. The FE-001 behaviour uses FE001_LIVE_CAPACITY_T (1.7 t). Nothing documents why the total is kept."),
    ("FE002_REMOVAL_EFFICIENCY", "python/fe_feed_handling.py", "FE002_REMOVAL_EFFICIENCY = 0.98",
     "Its own comment: 'informational; a polishing duty, negligible mass removed'. No other line of the repository names it. The documented reason is that the removal is not modelled."),
    ("HB010_CONFIRMED_RECOVERY", "python/hb_remaining_chain.py", "HB010_CONFIRMED_RECOVERY = 0.85",
     "Comment: 'registry-stated [Unverified (registry)] (registry: \"H2 recovery rate\")'. Only a comment on HB010_CONFIRMED_DESIGN_FEED_H2_FRACTION mentions it. The documented reason is that it states the basis of the purity range and the feed H2 fraction."),
]

# id, what, [(label, file, token)], who reads each, how big, why it is not hidden or hidden
INCONSISTENCIES = [
    {"id": "H2 lower heating value, three places",
     "values": [("10.783 MJ/Nm3 (SYNGAS_SPECIES_LHV_MJ_PER_NM3['H2'])", "python/eu_utilities_chp.py", 'SYNGAS_SPECIES_LHV_MJ_PER_NM3 = {"H2": 10.783'),
                ("10.8 MJ/Nm3 (H2_LHV_MJ_PER_NM3, EU-006's stated basis)", "python/eu_utilities_chp.py", "H2_LHV_MJ_PER_NM3 = 10.8"),
                ("10.8 MJ/Nm3 (a literal in balance_audit.efficiency_check)", "python/balance_audit.py", "h2_kw_engine = n_h2 * NM3_PER_MOL * 10.8 / 3.6")],
     "affects": "10.8 feeds the H2 energy and efficiency KPIs (`eu_utilities_chp._h2_budget_kw`, `eu006_fuel_cell`, `eu_chp_dispatch`, `tab1_integration.compute_tab1_kpis`, i.e. the EU-006 / EU-010 / Tab 1 values); 10.783 feeds the syngas LHV "
                "(`eu_utilities_chp._syngas_lhv_mj_per_nm3`, EU-003); the audit literal only `balance_audit.efficiency_check`.",
     "size": "10.8 against 10.783 is +0.158 %.",
     "hidden": "No verdict compares the two: balance_audit.TOL_STATED (1e-3) is applied only to relative mass residuals (`balance_audit.verdict`), so it neither hides nor tests this difference (and 1.58e-3 is above it anyway). It is measured in task A5, not fixed."},
    {"id": "molar mass of water, 18.015 against 18.016",
     "values": [("18.015 g/mol (M_H2O)", "python/ga001_gasifier_model.py", "M_H2O = 18.015"),
                ("M_H = 1.008", "python/ga001_gasifier_model.py", "M_H = 1.008"),
                ("M_O = 16.00 (so H2O from atoms = 18.016)", "python/ga001_gasifier_model.py", "M_O = 16.00"),
                ("the atom sum, used by the audit", "python/balance_audit.py", "return sum(ATOMIC_MASS[e] * n for e, n in FORMULA[species].items())")],
     "affects": "18.015 converts water between kg and mol in `ga001_gasifier_model` (steam and moisture, GA-001 outputs), `gc_gas_cleaning_chain.gc004_condensed_water` (GC-004) and `hb_wgs_psa_storage_chain.hb005_steam_generation` (HB-005); the atom "
                "masses (18.016) are used by `ga001_gasifier_model.elemental_atomic_ratios` and, in the audit, `balance_audit.molar_mass`. Both values are defined in ga001_gasifier_model.py; the atom sum is a second route to the same molecule.",
     "size": "5.5e-5 of the water mass; in scenario S4a it equals the whole A5 loop-mass residual (3.2e-5 of the loop inflow).",
     "hidden": "Yes: balance_audit.TOL_STATED = 1e-3 (used in balance_audit.verdict) classes a mass residual below 1e-3 as 'closes to a stated tolerance', and 3.2e-5 is far below it, so the verdict does not show it. Not fixed."},
]


def _loc(file, token, after=None):
    """`file` (`token`): where the text is, named by the text itself. The line number is looked up only to prove the text is there; it is NOT printed (it would go stale, task A3c)."""
    if locate(file, token, after) is None:
        return f"{file} NOT FOUND ({token.strip()[:50]})"
    return f"{file} ({token.strip()[:70]})"


def render_prose():
    """The 'Known undeclared reads', 'Constants nothing uses', 'Inconsistencies' and 'Inline literals' sections, as markdown lines."""
    L = ["## Known undeclared reads", "",
         "Engine models whose code reads another published key that their registration does not declare (found by the instrumented run against `declared_readers`). " + KNOWN_UNDECLARED_FIX, ""]
    for u in KNOWN_UNDECLARED_READS:
        L.append(f"- `{u['reader'][0]}|{u['reader'][1]}` reads `{u['reads'][0]}|{u['reads'][1]}`: {u['why']} Where: " + ", ".join(f"`{_loc(w[0], w[1], *w[2:])}`" for w in u["where"]) + ".")
    L += ["", "## Inline literals", "", INLINE_LITERAL_NOTE, "", "## Constants nothing uses", "",
          "Ledger rows with no consumer. They are reported, not removed.", ""]
    for name, f, tok, says in UNUSED_CONSTANTS:
        L.append(f"- `{name}` (`{_loc(f, tok)}`): {says}")
    L += ["", "## Inconsistencies recorded, not fixed", ""]
    for i in INCONSISTENCIES:
        L.append(f"### {i['id']}")
        L.append("")
        for label, f, tok in i["values"]:
            L.append(f"- {label}: `{_loc(f, tok)}`")
        L += ["", f"- Affects: {i['affects']}", f"- Size: {i['size']}", f"- Hidden by the tolerance: {i['hidden']}", ""]
    return L


def render_questions(ledger):
    """'Question references' (the text of every reference in use, read from the files) and 'RFI mapping' (rows mapped, and the rows considered and left empty)."""
    used = {}
    for r in ledger:
        for ref in r["upgrade_question"]:
            used.setdefault(ref, []).append(r["ledger_id"])
    esc = lambda s: str(s).replace("|", "/").replace("\n", " ")
    L = ["## Question references", "",
         "`upgrade_question` is a list of references (`python/ledger_questions.py`): `RFI2-<n>` = question n of `docs/rfi2_dokink.md`, `RFI1-<n>` = question n of `data/rfi_dokink.md`, "
         "`master_open_questions:<s>.<n>` = item n of Section s of `docs/master_open_questions.md` (Section 1 = DOK-ING, Section 3 = the specific items listed there). The text is read from those files.", "",
         "| reference | question | rows |", "|---|---|---|"]
    for ref in sorted(used):
        L.append(f"| {ref} | {esc(lq.text_of(ref))} | {len(used[ref])} |")
    L += ["", "## RFI mapping", "",
          "A row is mapped to an RFI question only when the question really asks for that quantity; where two questions apply both are listed and none is chosen. "
          f"{len(lq.RFI_MAP)} quantities are mapped; the rows that stay without a question are listed below with the question that was considered.", "",
          "| tag | references | why |", "|---|---|---|"]
    for tag, (refs, why) in lq.RFI_MAP.items():
        L.append(f"| {tag} | {', '.join(refs)} | {esc(why)} |")
    L += ["", "### Considered and left empty", "", "| tag | question(s) considered | why not mapped |", "|---|---|---|"]
    for tag, (refs, why) in lq.CONSIDERED.items():
        L.append(f"| {tag} | {', '.join(refs)} | {esc(why)} |")
    return L


def render_confirmed():
    """The 'Confirmed mentions' section: lines of the 18 engine modules that mention "confirmed", per file. The split into classes is NOT printed here: it is decided by the three lines that follow a
    mention, so a line inserted between a mention and its source would change this file for a reason that is not a change of the ledger (task A3c). The classes and their counts per file are pinned in
    tests/test_design_basis_ledger.py (CONFIRMED_PIN) and reported by python/ledger_coverage.mention_counts()."""
    from . import ledger_coverage as lc
    mentions = lc.confirmed_mentions()
    per = {}
    for m in mentions:
        per[m["file"]] = per.get(m["file"], 0) + 1
    L = ["## Confirmed mentions in the engine modules", "",
         f"{len(mentions)} lines of the {len(lc.CONFIRMED_SCOPE)} engine modules mention \"confirmed\" (case-insensitive). Each is classified by `python/ledger_coverage.classify_mention` as DOK-ING-SOURCED (a DOK-ING source is "
         "named in the line or the next 3 lines), GENERIC (explanatory use that states no value as Confirmed) or REGISTRY-STATED (a registry value called Confirmed with no source named next to it), and the counts per class and "
         "file are pinned by `tests/test_design_basis_ledger.py::test_the_confirmed_mentions_are_pinned_per_class_and_file`, so a new REGISTRY-STATED use fails. They are not rewritten here.", "",
         "| file | lines mentioning \"confirmed\" |", "|---|---|"]
    for file in sorted(per):
        L.append(f"| {file} | {per[file]} |")
    L.append(f"| **all** | {len(mentions)} |")
    L += ["", "**The pinned counts changed in the wording pass W1 (commits 0420d32 and 87e4950).** Lines mentioning \"confirmed\": 476 to 449; DOK-ING-sourced 46 to 49, generic 115 to 159, "
          "registry-stated 315 to 241; registry-stated lines that reach a persisted note: 88 to 14. Why: W1.1 reworded the persisted notes that called a registry value Confirmed (they now say "
          "\"Unverified (registry), not DOK-ING-confirmed\", or name the DOK-ING source next to the word), so those lines left the registry-stated class (most became generic, because the new text "
          "says \"not DOK-ING-confirmed\"); W1.2 reworded the EU-008 \"independently validated\" notes. The 14 persisted lines that remain are pinned in `tests/test_design_basis_ledger.py` "
          "(`PERSISTED_REGISTRY_STATED`) and none calls a registry value Confirmed (DOK-ING's confirmed composition ranges with RFI #2 named, negations, questions to DOK-ING, a self-test message, a code check). "
          "The 241 registry-stated lines that remain do not reach a persisted note in the live snapshot (docstrings, comments, other strings) and were not rewritten."]
    return L


def _value(module, name):
    import importlib
    return getattr(importlib.import_module("python." + module), name)


def render_refused(ledger):
    """The 'Refused borrowings' section: every row that has a registry row nearby but does not take its status, with both values side by side, the registry row's resolved status and the reason."""
    from . import ledger_rows as lr
    esc = lambda s: str(s).replace("|", "/").replace(chr(10), " ")
    rows = {r["tag"]: r for r in ledger}                      # the rows of parameter_table.build_ledger(), passed in by the export (this module does not import parameter_table)
    reg_of = {n["tag"]: n["reg"] for n in lr.build_rows() if n["reg"]}
    reg_of["GA-001.ash_fraction"] = ("GA-005", "Ash discharge rate (design)")
    L = ["## Refused borrowings", "",
         "A row takes the status of a registry row only for the SAME quantity in the SAME basis (`status_via`). These rows have a registry row nearby and do not: they are Assumed. "
         "One line each: the engine value, the registry value as written in the registry, the registry row's resolved status, and why.", "",
         "| ledger row | engine value | registry row | registry value | registry status | kind | reason |", "|---|---|---|---|---|---|---|"]
    for tag in lr.NOT_BORROWED:
        src = rows[tag]
        item, param = reg_of[tag]
        res, p = lr._registry_status((item, param))
        L.append(f"| {tag} | {esc(src['value'])} {esc(src['unit'])} | {item} / {esc(param)} | {esc(p['value'])} {esc(p['unit'])} | {res['status']} | {lr.REFUSAL_KIND[tag]} | {esc(lr.NOT_BORROWED[tag])} |")
    L += ["", "### FE-001 default delivery rate against FE-003 nominal feed rate", "",
          f"Engine: `FE001_DEFAULT_DELIVERY_RATE_KG_H` = {_value('fe_feed_handling', 'FE001_DEFAULT_DELIVERY_RATE_KG_H')} kg/h, the default of the engine input `FE-001-INPUT/msw_delivery_rate_kg_h` (the rate at which MSW arrives in the hopper; "
          "a scenario knob). Registry: FE-003 'Nominal feed rate' = 0.042 t/h (remark: \"Matches DOK-ING's 1 tpd (41.7 kg/h) nominal basis directly\"), Confirmed by the owner's worksheet with the DOK-ING line "
          "`data/dokink_rfi_answers.md:11` (RFI answer 1: 'Nominal capacity fixed at 1 tonne/day (1,000 kg/day) for continuous 24/7 operation'). They are not one quantity in one basis that differ by a unit conversion: "
          "(1) the registry row is the rate at which the plant FEEDS the process, the engine value is the rate at which feed is DELIVERED to the hopper (the hopper level changes by delivery minus feed, `fe001_inventory`); "
          "DOK-ING's answer is the processing capacity and says nothing about deliveries; (2) the basis of the 1,000 kg/day (as received or dry) is not stated in DOK-ING's line and is an open question "
          "(`docs/master_open_questions.md` Section 1 item 2) while the code comment says AS-RECEIVED; (3) 0.042 t/h x 1000 = 42 kg/h, not 41.67: the registry value is the same number rounded to two digits, so the engine value "
          "is not a unit conversion of it either (1,000 kg/day / 24 h = 41.667). The row stays Assumed.", "",
          "### GA-002 typical pressure", "",
          f"Engine: `GA002_TYPICAL_PRESSURE_MBAR_G` = {_value('gc_gas_cleaning_chain', 'GA002_TYPICAL_PRESSURE_MBAR_G')} mbar(g), the typical gasifier pressure used by the suction cross-check of GC-014. Registry rows of the gasifier vessel: "
          "GA-001 'Design pressure' 500 mbar(g) (a design quantity); GA-001 'Operating pressure (typical)' 100 mbar(g) (remark: 'Matches ~1.1 bar absolute already used in the pressure profile chart'); "
          "GA-002 'Design pressure' 500 mbar(g) ('Matches GA-001's design pressure directly'); GA-002 'Operating pressure range' 50-150 mbar(g) ('Band around the 100 mbar(g) typical value'). "
          "Design pressure and typical or operating pressure are different quantities and nothing is borrowed across them. The only row that is the same quantity (typical operating gauge pressure of the gasifier vessel, "
          "mbar(g), same value) is GA-001 'Operating pressure (typical)'; GA-002's own row is a band, not a typical value. So `GA-002.typical_pressure_mbar_g` borrows from GA-001 'Operating pressure (typical)' "
          "(Unverified (registry)); `ledger_rows.quantity_class` and a test refuse any borrowing across a design row and a typical or operating row."]
    return L
