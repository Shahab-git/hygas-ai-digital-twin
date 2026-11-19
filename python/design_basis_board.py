"""P2-3: data for the decision board at the top of the Design Basis tab. CLASS: presentation of existing
records; no model, no new claim.

Computed from code each call: RFI #1 counts (design_basis.summarize), registry rows by evidence label (the same
chain the app's datasheet sections use), the Measured count (snapshot), and the model's dry N2 against the
registry's SA-005 expected N2 (10 vol%, read from the registry file; GA-001 Outputs for the model value).
Typed, with their source named here: RFI #2's state ("reply pending": a manual status, change it when DOK-ING
answers; the questions are in docs/rfi2_dokink.md, dated 30 Oct 2026), the 'why it matters' lines
(docs/master_open_questions.md, docs/gasifying_agent_study.md, docs/design_basis_ledger.md) and the data priority
(docs/calibration_core_step1.md, a result on SYNTHETIC data with ASSUMED noise).
"""
import json
import os

from . import design_basis, equipment_datasheet as ed
from . import equipment_engineering_estimates as ee, equipment_rfi_fills

RFI2_STATE = "reply pending"            # manual: update when DOK-ING answers (docs/rfi2_dokink.md)
RFI2_DATE = "30 Oct 2026"

# (question, why it matters, what it blocks); the first 'why' is completed with the live N2 figures.
OPEN_QUESTIONS = (
    ("Gasifying agent: steam-blown chemical looping, or air at ER 0.25", None, "Gas composition, hydrogen yield"),
    ("Feed heating value (15 to 20 MJ/kg)", "Sets the sign of the gasifier heat balance (docs/balance_closure_audit.md).", "Energy balance"),
    ("Feed basis: wet or dry for the 1 t/day figure", "The model treats 41.67 kg/h as as-received (project decision, not DOK-ING-confirmed).", "Mass balance"),
    ("HB-016 rate constant", "No source for the value in use.", "Hydrogen storage chain"),
)
DATA_PRIORITY = (
    ("Clean-gas flow meter (SA-010), dry Nm3/h", "Most valuable"),
    ("Gas analysers: H2, CO, CO2, CH4, N2 (SA-001 to 005)", "High"),
    ("CH4 analyser, to pin the CH4 carbon fraction", "High"),
)


def registry_expected_n2_pct():
    """SA-005 'Expected N2 concentration' (vol%, basis not stated) read from the registry file, or None."""
    path = os.path.join(os.path.dirname(__file__), "..", "data", "equipment_registry.json")
    try:
        with open(path, encoding="utf-8") as fh:
            reg = json.load(fh)
        items = reg if isinstance(reg, list) else next(v for v in reg.values() if isinstance(v, list))
        for it in items:
            if it.get("id") == "SA-005":
                for prm in it["parameters"]:
                    if str(prm["parameter"]).startswith("Expected N"):
                        return float(prm["value"])
    except Exception:
        return None
    return None


def registry_rows_by_label():
    ds = ed.resolve_datasheets(ee.apply_estimates(equipment_rfi_fills.apply_rfi_fills(ed.build_all_datasheets())))
    return ed.summarize(ds)["evidence_label_rows"]


def board_data(snapshot):
    rfi1 = design_basis.summarize()
    rows = registry_rows_by_label()
    measured = sum(1 for e in snapshot.values() if e.get("status") == "Measured")
    n2 = None
    out = snapshot.get(("GA-001", "Outputs"))        # the published gas composition (not the report-only agent entry)
    reg_n2 = registry_expected_n2_pct()
    if out and out.get("status") != "Missing" and reg_n2 is not None:
        n2 = (float(out["value"]["N2_mol_pct_dry"]), reg_n2)
    qs = []
    for q, why, blocks in OPEN_QUESTIONS:
        if why is None:
            why = ("Dry N2 is %.0f %% in the model and %.0f %% in the registry (basis of the registry value not stated)." % n2
                   if n2 and None not in n2 else "Dry N2 in the model against the registry's 10 % could not be read this cycle.")
        qs.append((q, why, blocks))
    return {
        "rfi1_confirmed": rfi1[design_basis.STATUS_CONFIRMED], "rfi1_total": sum(rfi1.values()),
        "rfi2_state": RFI2_STATE, "rfi2_date": RFI2_DATE,
        "registry_doking": rows.get("Confirmed", 0), "registry_unverified": rows.get("Unverified (registry)", 0),
        "registry_total": sum(rows.values()), "measured": measured,
        "open_questions": tuple(qs), "data_priority": DATA_PRIORITY,
    }
