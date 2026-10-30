"""
Registry status audit -- READ-ONLY and OFFLINE. It changes no registry row, no status, no default and no engine file; it only reports and proposes.

Why: equipment_datasheet.slot_status() counts a registry row WITHOUT a "status" key as Confirmed (python/equipment_datasheet.py:512, STATUS_CONFIRMED :432). The registry JSON has no status key
on any of its rows, so every row with a value is "Confirmed" by default, including rows whose own remark says "not DOK-ING-confirmed, treat as an estimate". The owner's rule is that
Confirmed means confirmed by DOK-ING. This script measures the gap.

Universe (every row the datasheet view can show): the registry JSON rows, python/equipment_rfi_fills.py RFI_FILLS (no status key -> default Confirmed) and
python/equipment_engineering_estimates.py ESTIMATE_FILLS (explicit Engineering Estimate).

Evidence classes for every row whose effective status is Confirmed (explicit or defaulted):
  E1  a DOK-ING document line in this repo states the value. The ONLY DOK-ING data file in the repo is data/dokink_rfi_answers.md; E1 rows are curated below with file:line and the quoted text
      (a test reads every quote back from the file). `match` says whether the figure appears literally or is an exact unit conversion of a stated figure.
  E2  the row's remark names DOK-ING but no DOK-ING line in the repo states this value. (`related_line` quotes a DOK-ING line on the same subject where one exists.)
  E3  the row's own remark says estimate / not confirmed / assumption / design intent / placeholder / derived in this project / taken from the project's own dashboard (internal-model origin).
  E4  no evidence found in the repo. Not "Assumed": the audit does not assign a status by judgment.
Priority when several apply: E1 > E3 > E2 > E4; the other matches are listed in `also`.

    python scripts/run_registry_status_audit.py        (from the repo root, about 2 seconds)

Writes outputs/registry_audit/registry_status_audit.md and .csv (outputs/ is git-ignored). Applies nothing.
"""
import csv
import hashlib
import io
import json
import os
import re
import socket
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
if os.environ.get("HYGAS_ALLOW_DB_WRITES") == "1":
    sys.exit("Refusing to run: HYGAS_ALLOW_DB_WRITES=1 is set. This script never writes to a database; unset it.")

from python import equipment_datasheet as eds                   # noqa: E402
from python import equipment_engineering_estimates as eee       # noqa: E402
from python import equipment_registry                           # noqa: E402
from python import equipment_rfi_fills as erf                   # noqa: E402
from python import parameter_table as pt                        # noqa: E402

OUT_DIR = os.path.join(ROOT, "outputs", "registry_audit")
REGISTRY_REL = "data/equipment_registry.json"
RFI_REL = "data/dokink_rfi_answers.md"
STATUS_DEFAULT = eds.STATUS_CONFIRMED          # the code's own default for a row without a status key (equipment_datasheet.py:512)
CLASSES = ("E1", "E2", "E3", "E4")

_real_getaddrinfo = socket.getaddrinfo


def _guard(host, *a, **k):
    if "supabase" in str(host).lower():
        raise RuntimeError(f"offline script refused to resolve {host!r}")
    return _real_getaddrinfo(host, *a, **k)


socket.getaddrinfo = _guard


# --- curated DOK-ING evidence (data/dokink_rfi_answers.md; line numbers are 1-based) ----------------------------------------------------------
# key: (source, item id, parameter) -> (line, quoted text that must be on that line, match, why it counts)
L_FEED, L_TURN, L_ASH, L_FORM, L_H2, L_PURITY, L_PRESS, L_GRID, L_STREAMS = 11, 12, 15, 18, 31, 33, 36, 48, 61
E1_EVIDENCE = {
    ("RFI_FILLS", "FE-001", "Confirmed feed rate"): (L_FEED, "1,000 kg/day", "unit conversion", "1,000 kg/day = 41.67 kg/h"),
    ("RFI_FILLS", "GA-001", "Confirmed feed rate"): (L_FEED, "1,000 kg/day", "unit conversion", "1,000 kg/day = 41.67 kg/h"),
    ("RFI_FILLS", "FE-001", "Confirmed feedstock form"): (L_FORM, "Pre-sorted and shredded (<20", "literal", "form and particle size stated"),
    ("RFI_FILLS", "GA-001", "Confirmed feedstock form"): (L_FORM, "Pre-sorted and shredded (<20", "literal", "form and particle size stated"),
    ("RFI_FILLS", "GA-001", "Confirmed target feedstock streams (this phase)"): (L_STREAMS, "high-value contaminated waste streams", "literal", "stream type stated"),
    ("RFI_FILLS", "GA-001", "Confirmed operational turndown"): (L_TURN, "turndown ~70", "literal", "turndown ~70-120 % stated"),
    ("RFI_FILLS", "GA-005", "Confirmed feedstock ash content range"): (L_ASH, "Ash 5", "literal", "ash 5-15 % stated"),
    ("RFI_FILLS", "GA-009", "Confirmed ash content of processed material"): (L_ASH, "Ash 5", "literal", "ash 5-15 % stated"),
    ("RFI_FILLS", "EU-009", "Confirmed grid power connection"): (L_GRID, "Grid power connection", "literal", "grid connection available"),
    ("RFI_FILLS", "HB-013", "Confirmed H2 production rate feeding storage"): (L_H2, "~50 kg/day", "literal", "~50 kg/day stated"),
    ("registry", "FE-003", "Nominal feed rate"): (L_FEED, "1,000 kg/day", "unit conversion", "1 t/day = 0.0417 t/h, row rounds to 0.042"),
    ("registry", "FE-004", "Output particle size (max)"): (L_FORM, "<20", "literal", "DOK-ING states <20-30 mm; the row takes the 20 mm end"),
    ("registry", "HB-006", "H₂ purity (design)"): (L_PURITY, "99.97%", "literal", "99.97 % (ISO 14687 Grade D) stated"),
    ("registry", "HB-012", "Discharge pressure (design)"): (L_PRESS, "350/700 bar", "literal", "350/700 bar stated; the row takes 700"),
    ("registry", "HB-013", "Operating pressure range"): (L_PRESS, "350/700 bar", "literal", "350 and 700 bar stated as the two options; the row gives the span between them"),
    ("registry", "HB-018", "Dispensing pressure"): (L_PRESS, "350/700 bar", "literal", "350/700 bar stated"),
}
# A DOK-ING line on the same subject that does NOT state the row's value (for E2 rows): quoted and read back by the test, never used to call a row confirmed.
E2_RELATED = {
    ("registry", "FE-003", "Min feed rate"): (L_TURN, "turndown ~70", "70 % of nominal: derived, value not stated"),
    ("registry", "FE-003", "Max feed rate"): (L_TURN, "turndown ~70", "120 % of nominal: derived, value not stated"),
    ("registry", "GA-002", "Operating pressure range"): (L_TURN, "turndown ~70", "turndown stated, the pressure band is not"),
    ("registry", "GC-013", "Min flow rate"): (L_TURN, "turndown ~70", "turndown stated, the flow is derived"),
    ("registry", "GC-013", "Max flow rate"): (L_TURN, "turndown ~70", "turndown stated, the flow is derived"),
    ("registry", "HB-008", "Adsorption pressure (design)"): (35, "PSA discharges at 3", "DOK-ING states a 3-10 bar range; 7 bar(g) is inside it, not stated"),
    ("registry", "HB-013", "Storage capacity"): (L_H2, "~50 kg/day", "DOK-ING states a production RATE (kg/day); the row is a capacity (kg)"),
    ("registry", "AI-014", "Max modules supported"): (14, "25 tonnes/day", "DOK-ING states reactor sizes up to 25 t/day; the row counts modules"),
    ("registry", "FE-001", "Total hopper capacity"): (22, "hot-standby state", "DOK-ING states a hot-standby state; the 2 t capacity is not stated"),
    ("registry", "FE-006", "Measurement range"): (15, "Moisture 5", "DOK-ING states moisture 5-15(20) %; the 0-25 % range is not"),
}

# --- remark patterns for E3 / E2 / E4 notes -----------------------------------------------------------------------------------------------
_NEG = r"(?<!not an )(?<!not a )(?<!not a generic )(?<!not a separate )(?<!just a design )"
E3_PATTERNS = [
    ("not confirmed", r"not (?:yet )?(?:DOK-ING[- ])?confirmed|unconfirmed|never specified|pending (?:real|DOK-ING|vendor)|needs real confirmation", "Assumed"),
    ("project's own dashboard / balance / Simulink model", r"mass/energy balance|dashboard|thermal-lag model|simulink", "Assumed"),
    ("estimate", r"\bestimat(?:e|ed|ion)\b", "Estimated"),
    ("derived in this project", r"(?<![-\w])derived\b|\bcalculated\b|\bback-calculated\b", "Calculated"),
    ("assumption", _NEG + r"\bassum(?:ed|ption)\b", "Assumed"),
    ("design intent", r"design intent", "Assumed"),
    ("placeholder", _NEG + r"\bplaceholder\b", "Assumed"),
]
# Remarks that match an E3 pattern in words but do not disclaim the row's own value (reviewed by hand; the reason is printed in the output).
E3_EXCLUDE = {
    ("registry", "AI-012", "Training data requirement"): "mentions the Simulink model as a training resource, not as the value's origin",
    ("registry", "FE-003", "Weighing accuracy"): "'calculated' describes how downstream efficiencies use the number, not where the value comes from",
    ("registry", "SA-005", "Output signal"): "'Calculated value' describes the signal path of the row, not the origin of a number",
    ("registry", "AI-005", "Number of OPC-UA tags (max)"): "'calculated/derived values' are tags the system will carry, not the origin of the value 1000",
}
E2_PATTERN = r"DOK-?ING"
E2_AS_SOURCE = r"per DOK-?ING|DOK-?ING(?:'s)? (?:actual(?:ly)? )?(?:stated|spec|specified|hot-standby requirement)|DOK-?ING spec|(?:stated|specified) by DOK-?ING|DOK-?ING's .{0,25}(?:spec|target|requirement)"
E4_PRACTICE = r"\btypical\b|\bstandard\b|\bindustry\b|\bconventional\b"


def _sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def registry_sha():
    return _sha(os.path.join(ROOT, REGISTRY_REL))


def _quote_ok(rel, line, quote):
    with io.open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        lines = f.read().splitlines()
    return 1 <= line <= len(lines) and quote in lines[line - 1]


def evidence_lines():
    """[(rel path, line, quote)] for every curated quote (E1 and E2 related), for the test to read back."""
    out = [(RFI_REL, v[0], v[1]) for v in E1_EVIDENCE.values()]
    out += [(RFI_REL, v[0], v[1]) for v in E2_RELATED.values()]
    return out


# --- the universe -------------------------------------------------------------------------------------------------------------------------

def _fill_line(rel, table_name, item_id, parameter):
    start = pt._find_line(rel, r"^%s = \{" % table_name)
    item = pt._find_line(rel, r'^    "%s": \{' % re.escape(item_id), after=start)
    return f"{rel}:{pt._find_line(rel, chr(34) + 'parameter' + chr(34) + ': ' + chr(34) + re.escape(parameter) + chr(34), after=item)}"


def universe():
    rows = []
    for item in equipment_registry.load_registry():
        for p in item["parameters"]:
            rows.append({"source": "registry", "item_id": item["id"], "item_name": item["name"], "category": eds.classify(p["parameter"]), "parameter": p["parameter"],
                         "value": p.get("value"), "unit": p.get("unit"), "explicit_status": p.get("status"), "remark": p.get("remarks") or "",
                         "file_line": f"{REGISTRY_REL}:{pt._registry_line(item['id'], p['parameter'])}"})
    for item_id, cats in erf.RFI_FILLS.items():
        for cat, prows in cats.items():
            for p in prows:
                rows.append({"source": "RFI_FILLS", "item_id": item_id, "item_name": "", "category": cat, "parameter": p["parameter"], "value": p.get("value"), "unit": p.get("unit"),
                             "explicit_status": p.get("status"), "remark": p.get("remarks") or "", "file_line": _fill_line("python/equipment_rfi_fills.py", "RFI_FILLS", item_id, p["parameter"])})
    for item_id, cats in eee.ESTIMATE_FILLS.items():
        for cat, prows in cats.items():
            for p in prows:
                rows.append({"source": "ESTIMATE_FILLS", "item_id": item_id, "item_name": "", "category": cat, "parameter": p["parameter"], "value": p.get("value"), "unit": p.get("unit"),
                             "explicit_status": p.get("status"), "remark": p.get("remarks") or "", "file_line": _fill_line("python/equipment_engineering_estimates.py", "ESTIMATE_FILLS", item_id, p["parameter"])})
    return rows


def effective_status(r):
    """What the code uses. A row with no value is not a datasheet row at all (build_datasheet skips it)."""
    if r["value"] is None:
        return "Missing (null value; skipped by build_datasheet)"
    return r["explicit_status"] if r["explicit_status"] is not None else STATUS_DEFAULT


def classify_row(r):
    key = (r["source"], r["item_id"], r["parameter"])
    also = []
    e3 = None
    if key not in E3_EXCLUDE:
        for name, rx, status in E3_PATTERNS:
            m = re.search(rx, r["remark"], re.I)
            if m:
                e3 = e3 or (name, m.group(0), status)
                also.append("E3:" + name)
    has_named = bool(re.search(E2_PATTERN, r["remark"], re.I)) or (r["source"] == "RFI_FILLS")
    out = {"class": None, "subreason": "", "matched": "", "evidence_file_line": "", "evidence_quote": "", "match": "", "related_line": "", "also": "", "proposed_status": "", "proposal_reason": ""}
    if key in E1_EVIDENCE:
        line, quote, match, why = E1_EVIDENCE[key]
        out.update({"class": "E1", "subreason": why, "evidence_file_line": f"{RFI_REL}:{line}", "evidence_quote": quote, "match": match,
                    "proposed_status": "Confirmed (keep)", "proposal_reason": f"DOK-ING line states it ({match}): {why}"})
        out["also"] = "; ".join(sorted(set(also)))
        return out
    if e3:
        name, snippet, status = e3
        out.update({"class": "E3", "subreason": name, "matched": snippet, "also": "; ".join(sorted(set(a for a in also if a != "E3:" + name) | ({"E2"} if has_named else set()))),
                    "proposed_status": status, "proposal_reason": f"the row's own remark says '{snippet}' ({name}); status taken from that wording, the owner decides"})
        return out
    if has_named:
        rel = E2_RELATED.get(key)
        as_source = bool(re.search(E2_AS_SOURCE, r["remark"], re.I)) or r["source"] == "RFI_FILLS"
        out.update({"class": "E2", "subreason": ("remark cites DOK-ING as a source" if as_source else "remark mentions DOK-ING as context") + "; no DOK-ING line states this value", "matched": (re.search(E2_PATTERN, r["remark"], re.I) or re.search("x", "x")).group(0),
                    "proposed_status": "owner decision (not Confirmed unless a DOK-ING line is supplied)",
                    "proposal_reason": "cites DOK-ING by name but the value is not in any DOK-ING file in the repo"})
        if rel:
            out["related_line"] = f"{RFI_REL}:{rel[0]} \"{rel[1]}\" ({rel[2]})"
        return out
    practice = re.search(E4_PRACTICE, r["remark"], re.I)
    out.update({"class": "E4", "subreason": "remark cites typical / standard / industry practice" if practice else "no provenance in the remark",
                "matched": practice.group(0) if practice else "", "proposed_status": "owner decision (not Confirmed unless a DOK-ING line is supplied)",
                "proposal_reason": "no DOK-ING evidence found in the repo"})
    return out


def build_rows():
    rows = []
    for r in universe():
        r = dict(r)
        r["effective_status"] = effective_status(r)
        if r["effective_status"] == STATUS_DEFAULT:
            r.update(classify_row(r))
        else:
            r.update({"class": "", "subreason": "", "matched": "", "evidence_file_line": "", "evidence_quote": "", "match": "", "related_line": "", "also": "",
                      "proposed_status": "(explicit status, not audited as Confirmed)" if r["explicit_status"] else "(no value)", "proposal_reason": ""})
        rows.append(r)
    return rows


def counts(rows):
    c = {"rows": len(rows), "registry": sum(r["source"] == "registry" for r in rows), "RFI_FILLS": sum(r["source"] == "RFI_FILLS" for r in rows),
         "ESTIMATE_FILLS": sum(r["source"] == "ESTIMATE_FILLS" for r in rows),
         "explicit_confirmed": sum(r["explicit_status"] == eds.STATUS_CONFIRMED for r in rows),
         "explicit_other": sum(r["explicit_status"] is not None and r["explicit_status"] != eds.STATUS_CONFIRMED for r in rows),
         "no_status": sum(r["explicit_status"] is None for r in rows),
         "no_value": sum(r["value"] is None for r in rows),
         "effective_confirmed": sum(r["effective_status"] == STATUS_DEFAULT for r in rows)}
    for k in CLASSES:
        c[k] = sum(r["class"] == k for r in rows)
    c["E1_literal"] = sum(r["class"] == "E1" and r["match"] == "literal" for r in rows)
    c["E1_conversion"] = sum(r["class"] == "E1" and r["match"] == "unit conversion" for r in rows)
    c["E3_by_reason"] = {}
    for r in rows:
        if r["class"] == "E3":
            c["E3_by_reason"][r["subreason"]] = c["E3_by_reason"].get(r["subreason"], 0) + 1
    return c


# --- cross-check against the data-layer parameter table -----------------------------------------------------------------------------------------

# table tag -> the audit row(s) that describe the same quantity: (source, item, parameter)
TABLE_TO_AUDIT = {
    "GA-001.T_gasifier_C": ("registry", "GA-001", "Operating temperature (typical)"),
    "GA-003.air_flow_design_Nm3_h": ("registry", "GA-003", "Primary air flow rate (design)"),
    "GA-003.steam_flow_design_kg_h": ("registry", "GA-003", "Steam flow rate (design)"),
    "GA-001.ER": ("registry", "GA-003", "Air-to-fuel equivalence ratio (ER)"),
    "GA-004.air_preheat_C": ("registry", "GA-004", "Air preheat temperature"),
    "GA-004.steam_T_C": ("registry", "GA-004", "Steam temperature (design)"),
    "GA-001.ash_fraction": ("registry", "GA-005", "Ash discharge rate (design)"),
}


def cross_check(rows):
    by_key = {(r["source"], r["item_id"], r["parameter"]): r for r in rows}
    out = []
    table = pt.build_table()
    for t in table:
        key = TABLE_TO_AUDIT.get(t["tag"])
        if key is None:
            continue
        if t["overridable_via"] == pt.VIA_ENGINE or (t["overridable_via"] == pt.VIA_CODE and t["tag"] != "GA-001.ash_fraction") or t["overridable_via"] == pt.VIA_DYNAMICS:
            continue                                   # an engine-side row of the same tag: compared below as 'same tag, two statuses'
        a = by_key[key]
        agree = (t["status"] == "Confirmed") == (a["class"] == "E1")
        out.append({"tag": t["tag"], "table_row": t["source"], "table_status": t["status"], "audit_row": f"{key[1]} '{key[2]}'", "audit_class": a["class"], "audit_subreason": a["subreason"],
                    "agree": agree, "note": a["proposal_reason"] if not agree else ""})
    tags = {}
    for t in table:
        tags.setdefault(t["tag"], set()).add(t["status"])
    for tag, st in sorted(tags.items()):
        if "Confirmed" in st and len(st) > 1:
            out.append({"tag": tag, "table_row": "(all rows of the tag)", "table_status": " / ".join(sorted(st)), "audit_row": "", "audit_class": "", "audit_subreason": "", "agree": False,
                        "note": "the same parameter is Confirmed in the registry row and Assumed as the engine input"})
    return out


# --- output -------------------------------------------------------------------------------------------------------------------------------------

CSV_COLS = ["source", "item_id", "category", "parameter", "value", "unit", "explicit_status", "effective_status", "remark", "class", "subreason", "matched", "evidence_file_line",
            "evidence_quote", "match", "related_line", "also", "proposed_status", "proposal_reason", "file_line"]


def _cell(v):
    return str(v if v is not None else "").replace("|", "/").replace("\n", " ")


def md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(_cell(c) for c in r) + " |" for r in rows]
    return out


def render(rows):
    c = counts(rows)
    L = ["# Registry status audit -- measured output (read-only; nothing applied)", "",
         f"Default applied at python/equipment_datasheet.py:512 (`r.get(\"status\", STATUS_CONFIRMED)`). Registry sha256 {registry_sha()[:16]}...", "",
         "## 1. Counts", ""]
    L += md_table(["measure", "rows"], [["all rows audited (registry + RFI_FILLS + ESTIMATE_FILLS)", c["rows"]], ["  registry JSON rows", c["registry"]], ["  RFI_FILLS rows", c["RFI_FILLS"]],
                                        ["  ESTIMATE_FILLS rows", c["ESTIMATE_FILLS"]], ["explicit status Confirmed", c["explicit_confirmed"]], ["explicit status other (Engineering Estimate)", c["explicit_other"]],
                                        ["NO status key (defaulted)", c["no_status"]], ["rows with a null value (not datasheet rows)", c["no_value"]], ["effective status Confirmed", c["effective_confirmed"]]])
    L += ["", "### Evidence class of the rows whose effective status is Confirmed", ""]
    L += md_table(["class", "rows", "meaning"], [["E1", c["E1"], f"a DOK-ING line states the value ({c['E1_literal']} literal, {c['E1_conversion']} exact unit conversion)"],
                                                 ["E2", c["E2"], "remark names DOK-ING, no DOK-ING line states the value"], ["E3", c["E3"], "the row's own remark disclaims it (estimate / not confirmed / assumption / design intent / derived / the project's own dashboard)"],
                                                 ["E4", c["E4"], "no evidence found in the repo"], ["sum", c["E1"] + c["E2"] + c["E3"] + c["E4"], f"= effective Confirmed {c['effective_confirmed']}"]])
    L += ["", "E3 by reason (a row is counted once, at its first matching reason): " + "; ".join(f"{k} {v}" for k, v in sorted(c["E3_by_reason"].items())), ""]
    conf = [r for r in rows if r["class"]]
    L += ["## 2. E1: DOK-ING line states the value", ""]
    L += md_table(["source", "item", "parameter", "value", "evidence", "quote", "match"], [[r["source"], r["item_id"], r["parameter"], f"{r['value']} {r['unit']}", r["evidence_file_line"], r["evidence_quote"], r["match"]] for r in conf if r["class"] == "E1"])
    L += ["", "## 3. E2: remark names DOK-ING, value not in a DOK-ING file", ""]
    L += md_table(["item", "parameter", "value", "remark", "related DOK-ING line (does not state the value)", "registry line"],
                  [[r["item_id"], r["parameter"], f"{r['value']} {r['unit']}", r["remark"], r["related_line"], r["file_line"]] for r in conf if r["class"] == "E2"])
    L += ["", "## 4. E3: the row's own remark disclaims it", ""]
    L += md_table(["item", "parameter", "value", "matched wording", "reason", "also", "proposed", "remark", "registry line"],
                  [[r["item_id"], r["parameter"], f"{r['value']} {r['unit']}", r["matched"], r["subreason"], r["also"], r["proposed_status"], r["remark"], r["file_line"]] for r in conf if r["class"] == "E3"])
    L += ["", "## 5. E4: no evidence found in the repo (every row)", ""]
    L += md_table(["item", "parameter", "value", "note", "remark", "registry line"],
                  [[r["item_id"], r["parameter"], f"{r['value']} {r['unit']}", r["subreason"], r["remark"], r["file_line"]] for r in conf if r["class"] == "E4"])
    L += ["", "## 6. Hand-reviewed exclusions from E3", ""] + md_table(["row", "why not E3"], [[f"{k[1]} {k[2]}", v] for k, v in E3_EXCLUDE.items()])
    L += ["", "## 7. Data-layer parameter table vs this audit", ""]
    cc = cross_check(rows)
    L += md_table(["tag", "table row", "table status", "audit row", "audit class", "agree", "note"], [[x["tag"], x["table_row"], x["table_status"], x["audit_row"], x["audit_class"], x["agree"], x["note"]] for x in cc])
    return "\n".join(L) + "\n"


def write_outputs(rows, out_dir=OUT_DIR):
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "registry_status_audit.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(render(rows))
    with open(os.path.join(out_dir, "registry_status_audit.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLS)
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in CSV_COLS})


def main():
    before = registry_sha()
    rows = build_rows()
    write_outputs(rows)
    assert registry_sha() == before, "the audit modified the registry"
    c = counts(rows)
    print(json.dumps({k: v for k, v in c.items()}, indent=1, ensure_ascii=False))
    print("registry unchanged:", registry_sha() == before)


if __name__ == "__main__":
    main()
