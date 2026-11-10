"""
Enforced versus verified closure (task A5). READ-ONLY: this module only LABELS the closure rows of python/balance_audit.py; it changes no number.

A closure row can say two different things when it reads "closes to numerical precision":

  ENFORCED  the outflow (or the unknown stream) is derived from the inflow by the very equation under test: an atom balance solved for it, a stream computed as
            the remainder of another, or a quantity computed from the same constant on both sides. The row can only be non-zero through an implementation, lag or
            publication error; no change of ER, feed, steam ratio or composition can make it fail. It closes BY CONSTRUCTION: it is not evidence that the model
            conserves anything.
  VERIFIED  the two sides come from independent modules or independent formulas (a pass-through chain, a separately sized stream, an engine-reported figure
            against the audit's own sum). A modelling inconsistency would show as a residual, so a closure is a (limited) piece of evidence and a residual is a finding.
  PARTLY    some streams of the row are enforced (remainders, differences, same-constant terms) and others are independent. The row says which.

The judgement for each row is given with `why` and file:line references. References are stored as (file under python/, snippet); the line is looked up in the
file when asked for (`line_refs()`), so a moved line is found and a vanished snippet fails `check_refs()` instead of leaving a stale number behind.

`annotate_audit(audit)` adds `closure_kind`, `closure_why` and `closure_refs` to the rows of balance_audit.audit_snapshot's output. Nothing else is touched.
"""
import os

ENFORCED, VERIFIED, PARTLY = "ENFORCED", "VERIFIED", "PARTLY"
KINDS = (ENFORCED, VERIFIED, PARTLY)
CONSTRUCTION = "closes by construction -- not evidence"
ELEMENTS = ("C", "H", "O", "N", "ash", "mass")

G, CA, GMB, GC, HB, HR, FE, BA = ("ga001_gasifier_model.py", "ga001_carbon_accounting.py", "gasifier_mass_balance.py", "gc_gas_cleaning_chain.py",
                                  "hb_wgs_psa_storage_chain.py", "hb_remaining_chain.py", "fe_feed_handling.py", "balance_audit.py")

_GA_REREAD = ("The audit's only independent content in this row is its re-read of the feed (FE-005, composition) and of the lagged tail-gas recycle "
              "(previous cycle's HB-009), with the model's own formulas for air and steam: it can expose a lag, publication or transcription error, not a modelling one.")
_CHAIN = "GC-004 / GC-013 copy GA-001's gas, the WGS (HB-001/HB-004) converts CO with its own atom check, the PSA splits species by the recovery fraction (separate modules)"

# (control volume, quantity) -> (kind, why, [(file, snippet), ...])
TABLE = {
    ("ga001", "C"): (ENFORCED, "Gas carbon is `conversion` x the carbon GA-001 read (carbon_gas = carbon_conv_eff per mol fuel C); the rest is published as carbon black = unconverted x split "
                     "and its remainder = unconverted x (1 - split), so out = C used by construction. " + _GA_REREAD,
                     [(G, "carbon_gas = carbon_conv_eff"), (CA, "cb = unconv * split"), (CA, "remainder = unconv * (1.0 - split)")]),
    ("ga001", "H"): (ENFORCED, "solve_product_gas solves the H balance for H2 + H2O (H_RHS) and the O balance for CO2 / CO, with air O2 = ER x stoichiometric O2 on the recycle-augmented fuel; "
                     "the audit re-derives the inflow with the same formulas. " + _GA_REREAD, [(G, "H_RHS = (x + 2.0 * steam_mol_per_molc"), (G, "n2_from_air = o2_actual")]),
    ("ga001", "O"): (ENFORCED, "Same solver: O is closed by the CO / CO2 / H2O unknowns of solve_product_gas given the air O2 it computed itself. " + _GA_REREAD,
                     [(G, "H_RHS = (x + 2.0 * steam_mol_per_molc"), (G, "n2_from_air = o2_actual")]),
    ("ga001", "N"): (ENFORCED, "N2 out = fuel N / 2 + n2_from_air (0.79 / 0.21 x the O2 it computed): no independent side. " + _GA_REREAD,
                     [(G, "n1, n2, n3, n6 = B - n4"), (G, "n2_from_air = o2_actual")]),
    ("ga001", "ash"): (ENFORCED, "Both sides are ASH_FRACTION x dry feed (ga001 uses gasifier_mass_balance.ASH_FRACTION, the byproduct module uses the same constant).",
                       [(GMB, "ASH_FRACTION = 0.10"), (GMB, "def byproduct_mass_flows")]),
    ("ga001", "mass"): (ENFORCED, "Sum of the element rows and ash, which are enforced; the water molar-mass basis (one value since P1-05(b); it was 18.015 versus 18.016) is the only extra term.",
                        [(BA, "def closure(terms")]),
    ("loop", "C"): (PARTLY, "Independent: " + _CHAIN + ", so carbon carried through the gas path is checked. Enforced: the carbon black and its remainder (remainders of the unconverted carbon) and the "
                    "'recycle inventory in transit' (a difference: this cycle's tail gas minus the tail gas GA-001 read).",
                    [(HB, "def verify_wgs_atom_balance"), (HB, "h2_recovered_nm3_h = feed_species_nm3_h"), (BA, "{s: now[s] - used[s] for s in now}")]),
    ("loop", "H"): (PARTLY, "Independent: " + _CHAIN + "; HB-005's steam (4 x CO) against the WGS composition's unreacted H2O are separate formulas. Enforced: GC-004's condensate = wet - dry of "
                    "GA-001's own gas (a difference) and the recycle in-transit term.",
                    [(GC, "condensed_nm3_h = wet_flow - dry_flow"), (HB, "steam_kg_h = steam_mol_h"), (BA, "{s: now[s] - used[s] for s in now}")]),
    ("loop", "O"): (PARTLY, "As H: the WGS oxygen goes through its own atom check, the condensate is a difference, the in-transit term is a difference.",
                    [(GC, "condensed_nm3_h = wet_flow - dry_flow"), (HB, "def verify_wgs_atom_balance")]),
    ("loop", "N"): (VERIFIED, "Inert N2 reaches HB-009's tail only through GC-013 (copy), the WGS composition (N2 untouched) and the PSA species split (100 % of N2 to the tail). There is no "
                    "solver and no remainder term on this path: a module that drops, scales or mis-converts N2 shows as a residual. It checks the pass-through, not any chemistry.",
                    [(HB, "def hb009_tail_gas"), (HB, "h2_recovered_nm3_h = feed_species_nm3_h")]),
    ("loop", "ash"): (ENFORCED, "Both sides are ASH_FRACTION x dry feed.", [(GMB, "ASH_FRACTION = 0.10"), (GMB, "def byproduct_mass_flows")]),
    ("loop", "mass"): (PARTLY, "Equals the sum of the element residuals (the enforced and independent parts above) plus the water molar-mass basis effect.", [(BA, "def closure(terms")]),
    ("plant", "C"): (PARTLY, "As the loop: independent gas path, enforced carbon black / remainder / in-transit; the plant additionally takes the dry solids from FE-003/FE-005, whose moisture "
                     "balance is explicit (dry = wet x (1 - 10 %)).", [(FE, "dry_solids_kg_h = wet_inlet_kg_h"), (HB, "def verify_wgs_atom_balance")]),
    ("plant", "H"): (PARTLY, "As the loop, plus one genuinely independent stream: the electrolyser. HB-011 draws 1 L/Nm3 of water (hb_remaining_chain.py) but 2 H2O -> 2 H2 + O2 needs 0.80, and the "
                     "engine publishes no stream for the excess: that mismatch, not the gas path, is where the plant H and O residual comes from. The dryer evaporation is explicit "
                     "(wet - outlet wet) and the condensate a difference.", [(HR, "water_l_h = h2_nm3_h * HB011_WATER_L_PER_NM3"), (FE, "water_evaporated_kg_h = wet_inlet_kg_h")]),
    ("plant", "O"): (PARTLY, "As plant H: the electrolyser water excess is the independent part; condensate and dryer water are enforced.",
                     [(HR, "water_l_h = h2_nm3_h * HB011_WATER_L_PER_NM3"), (GC, "condensed_nm3_h = wet_flow - dry_flow")]),
    ("plant", "N"): (VERIFIED, "As the loop: the N2 pass-through across independent modules; no remainder term.", [(HB, "def hb009_tail_gas")]),
    ("plant", "ash"): (ENFORCED, "Both sides are ASH_FRACTION x the dry feed.", [(GMB, "def byproduct_mass_flows")]),
    ("plant", "mass"): (PARTLY, "Sum of the element rows (C, H, O, N parts as above) plus the water molar-mass basis effect.", [(BA, "def closure(terms")]),
    ("storage", "h2_created_by_clamp"): (VERIFIED, "level(n) = clamp(level(n-1) + net, 0, capacity) in HB-013 against the level the audit recomputes from the published inflow and outflow: two "
                                         "computations, and the clamp is the difference. It is non-zero whenever the clamp acts.", [(HB, "new_level = min(max(prev_level + net_kg")]),
    ("energy_gasifier", "implied_heat_duty"): (ENFORCED, "The duty IS the remainder q = sum out - sum in: GA-001 computes no heat duty, so there is no independent side. The number is a finding about the "
                                               "model (heat the gasifier would have to add or remove), not a closure.", [(BA, "q = sum_out - sum_in")]),
    ("energy_plant", "closure_residual"): (VERIFIED, "The heat the balance says must be rejected (energy in - known energy out) is compared with the heat rejection the engine itself reports "
                                           "(GC-004 sensible duty + HB-012 power): independent sides. It does not close, and the Missing terms (listed per case) keep the residual from being explained.",
                                           [(BA, '"closure_residual_kw": implied_reject - reported_sum')]),
}


def _lines(fname, cache):
    if fname not in cache:
        with open(os.path.join(os.path.dirname(__file__), fname), encoding="utf-8") as fh:
            cache[fname] = fh.read().splitlines()
    return cache[fname]


_REF_CACHE = {}


def line_refs(key):
    """["file:line", ...] for one TABLE entry (first line of the file that contains the snippet). LookupError if a snippet has vanished."""
    out = []
    for fname, snippet in TABLE[key][2]:
        for i, text in enumerate(_lines(fname, _REF_CACHE), start=1):
            if snippet in text:
                out.append(f"python/{fname}:{i}")
                break
        else:
            raise LookupError(f"{fname}: no line contains {snippet!r}; refresh python/balance_closure_kind.py")
    return out


def check_refs():
    """Broken references (empty list = every judgement still points at its code)."""
    broken = []
    for key, (_k, _w, refs) in TABLE.items():
        for fname, snippet in refs:
            if not any(snippet in t for t in _lines(fname, {})):
                broken.append((key, fname, snippet))
    return broken


def info(cv, quantity):
    kind, why, _ = TABLE[(cv, quantity)]
    return {"closure_kind": kind, "closure_why": why + ("" if kind != ENFORCED else " [" + CONSTRUCTION + "]"), "closure_refs": line_refs((cv, quantity))}


def annotate_rows(cv, rows):
    for q, r in rows.items():
        if (cv, q) in TABLE:
            r.update(info(cv, q))
    return rows


AGENT_CLAUSE = (" [Gasifying agent '{agent}' (task A1): the oxidant is not air. The model and the audit both take O2 = effective ER x stoichiometric O2 and N2 = O2 x (1 - f) / f from the "
                "agent table, so for this agent the audit's oxidant side is the model's own formula, not an independent check; no balance checks the Assumed agent definition itself.]")


def annotate_audit(audit, agent="air"):
    """Adds closure_kind / closure_why / closure_refs to the closure rows of an audit_snapshot() result, in place. No number is read or changed. For a gasifying agent other than 'air'
    (task A1) the H, O and N rows (the ones the oxidant enters) also say what the oxidant side is; the default text is unchanged."""
    for cv in ("ga001", "loop", "plant"):
        if cv in audit:
            annotate_rows(cv, audit[cv]["rows"])
            if agent != "air":
                for q in ("H", "O", "N"):
                    if q in audit[cv]["rows"]:
                        audit[cv]["rows"][q]["closure_why"] += AGENT_CLAUSE.format(agent=agent)
    if "storage" in audit:
        audit["storage"].update(info("storage", "h2_created_by_clamp"))
    for e in audit.get("energy_gasifier", {}).values():
        e.update(info("energy_gasifier", "implied_heat_duty"))
    for e in audit.get("energy_plant", {}).values():
        e.update(info("energy_plant", "closure_residual"))
    return audit


def summary(audit):
    """{quantity: {kind: count}} over the control volumes of the mass rows (ga001, loop, plant), plus the storage / energy rows under their own names."""
    out = {}
    for cv in ("ga001", "loop", "plant"):
        for q, r in audit.get(cv, {}).get("rows", {}).items():
            out.setdefault(q, {}).setdefault(r["closure_kind"], 0)
            out[q][r["closure_kind"]] += 1
    for name in ("storage",):
        if name in audit:
            out.setdefault(name, {}).setdefault(audit[name]["closure_kind"], 0)
            out[name][audit[name]["closure_kind"]] += 1
    for name in ("energy_gasifier", "energy_plant"):
        for e in audit.get(name, {}).values():
            out.setdefault(name, {}).setdefault(e["closure_kind"], 0)
            out[name][e["closure_kind"]] += 1
            break
    return out
