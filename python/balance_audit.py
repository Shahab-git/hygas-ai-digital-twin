"""
Mass and energy closure audit (step 1 of the validation plan) -- READ-ONLY.

Pure functions that take a PUBLISHED snapshot (the {key: entry} dict that
tab1_integration.build_live_snapshot() returns and the UI reads) and measure how
well the twin closes its own balances: C, H, O, N and total mass across GA-001
and across the whole plant, and energy across GA-001 and the whole plant.

Ground rules this module keeps (task "Mass and energy closure audit"):
  * It MEASURES. It never changes a model equation, adds a balancing term, a
    closing factor or an unexplained constant. A residual is a finding.
  * No Streamlit, no database, no network, no engine edit. It only reads the
    snapshot (and, for the lagged recycle, the PREVIOUS cycle's snapshot) and
    calls public, side-effect-free helpers of the existing models.
  * Every number is read from the snapshot, read from the repo (file:line in the
    term's `source`), derived from the standard constants named below, or marked
    Assumed with a range. Whatever cannot be determined is a Missing term: it is
    LISTED, never treated as zero.

A "term" is a dict:
    name, direction ("in"/"out"), species ({species: mol/h} or None when Missing),
    ash_kg_h, mass_kg_h, status (one of plant_status' five tags), source, note,
    affects (elements a Missing term would change), blocking (a Missing term the
    model's own arithmetic needs, so no residual can be computed at all).
Species may be molecules (H2, CO, CO2, CH4, N2, O2, H2O) or the atomic
pseudo-species C/H/O/N used for the elemental feed. Moles are the primary unit
(the engine publishes Nm3/h and mol%); mass is derived with ONE self-consistent
atomic-mass table (ga001_gasifier_model.M_C/M_H/M_O/M_N) unless the engine itself
publishes a mass, which is then used as published.
"""
import math

from . import cycle_clock
from . import design_basis
from . import ga001_gasifier_model as ga001
from . import gasifier_mass_balance as gmb
from . import gc_gas_cleaning_chain as gc
from . import hb_wgs_psa_storage_chain as hbchain
from . import plant_status as ps

# --- tolerances (audit choices, NOT project specifications) -------------------
TOL_NUMERICAL = 1e-6    # same order as verify_atom_balance's 1e-8 plus margin: "numerical precision"
TOL_STATED = 1e-3       # 0.1 % of inflow: "closes to a stated tolerance"

VERDICT_NUMERICAL = "closes to numerical precision (< 1e-6 relative)"
VERDICT_STATED = "closes to a stated tolerance (< 0.1 % of inflow)"
VERDICT_NO = "does not close"
VERDICT_NA = "cannot be evaluated (Missing term)"

ELEMENTS = ("C", "H", "O", "N")

# --- atomic / molecular masses: ONE table, the repo's own atomic masses --------
ATOMIC_MASS = {"C": ga001.M_C, "H": ga001.M_H, "O": ga001.M_O, "N": ga001.M_N}   # ga001_gasifier_model.py:161-164
FORMULA = {
    "C": {"C": 1}, "H": {"H": 1}, "O": {"O": 1}, "N": {"N": 1},
    "H2": {"H": 2}, "O2": {"O": 2}, "N2": {"N": 2}, "CO": {"C": 1, "O": 1}, "CO2": {"C": 1, "O": 2},
    "CH4": {"C": 1, "H": 4}, "H2O": {"H": 2, "O": 1},
}
M_H2O_ENGINE = ga001.M_H2O      # 18.015 (ga001_gasifier_model.py:165); atomic sum is 18.016 -- see audit finding F-M1
M_H2_ENGINE = hbchain.M_H2      # 2.016 (hb_wgs_psa_storage_chain.py:93)
NM3_PER_MOL = ga001.NM3_PER_MOL  # 0.022414 (ga001_gasifier_model.py:172)


def molar_mass(species):
    """g/mol from the single atomic-mass table above."""
    return sum(ATOMIC_MASS[e] * n for e, n in FORMULA[species].items())


# --- standard thermochemical constants (named; 25 degC, 1 bar, ideal gas) ------
# Standard enthalpies of formation, kJ/mol (NIST-JANAF / CRC standard values).
HF_KJ_MOL = {"H2": 0.0, "N2": 0.0, "O2": 0.0, "C": 0.0,           # elements in their standard state (C = graphite)
             "CO": -110.525, "CO2": -393.509, "CH4": -74.873,
             "H2O_g": -241.826, "H2O_l": -285.830}
# Lower heating values derived from them (products CO2(g) + H2O(g)): kJ/mol
LHV_KJ_MOL = {
    "H2": -HF_KJ_MOL["H2O_g"],
    "CO": HF_KJ_MOL["CO"] - HF_KJ_MOL["CO2"],
    "CH4": HF_KJ_MOL["CH4"] - (HF_KJ_MOL["CO2"] + 2.0 * HF_KJ_MOL["H2O_g"]),
    "C": -HF_KJ_MOL["CO2"],
}
DH_VAP_KJ_MOL = HF_KJ_MOL["H2O_g"] - HF_KJ_MOL["H2O_l"]    # 44.004 kJ/mol at 25 degC
T_REF_C = 25.0
CP_J_MOLK = dict(gc.CP_MEAN_J_MOLK)                          # gc_gas_cleaning_chain.py:106 (mean 300-1200 K)
CP_J_MOLK_O2_NOTE = "O2 uses the N2 mean cp (same diatomic, within a few %): Estimated"
CP_J_MOLK["O2"] = CP_J_MOLK["N2"]
CP_LIQUID_WATER_J_MOLK = hbchain.CP_WATER_KJ_KGK * M_H2O_ENGINE   # hb_wgs_psa_storage_chain.py:94 x 18.015 g/mol
KW_PER_KJ_H = 1.0 / 3600.0

# --- registry static values used as stream temperatures (data/equipment_registry.json) ---
GA004_AIR_PREHEAT_C = 200.0          # GA-004 "Air preheat temperature" (registry, Confirmed static design value)
GA004_STEAM_C = 350.0                # GA-004 "Steam temperature (design)"
FE005_DRYER_OPERATING_C = 100.0      # FE-005 "Operating temperature"
GC004_QUENCH_OUT_C = 65.0            # gc_gas_cleaning_chain.py:295
GA008_OPERATING_C = 180.0            # GA-008 "Operating temperature"

# Solids sensible heat: no cp for ash/char exists anywhere in the repo -> Assumed with a range.
SOLIDS_CP_KJ_KGK = (1.0, 0.8, 1.4)   # (point, low, high) Assumed, ash/char mean cp; NOT from the repo


def tail_gas_mode(snapshot):
    """'regasify' (today) or 'heat_only' (tail-gas-heat task). Snapshots from before the switch existed have no such key: regasify."""
    e = snapshot.get(("GA-001-INPUT", "tail_gas_mode"))
    return "regasify" if e is None or e["status"] == ps.STATUS_MISSING else e["value"]


class AuditInputMissing(Exception):
    """A snapshot entry the audit needs is absent or Missing."""


# =============================================================================
# snapshot access
# =============================================================================

def _entry(snapshot, key):
    e = snapshot.get(key)
    if e is None or e["status"] == ps.STATUS_MISSING:
        return None
    return e


def _val(snapshot, key, required=True):
    e = _entry(snapshot, key)
    if e is None:
        if required:
            raise AuditInputMissing(key)
        return None
    return e["value"]


# =============================================================================
# terms and the generic closure
# =============================================================================

def make_term(name, direction, species=None, ash_kg_h=0.0, mass_kg_h=None, status=ps.STATUS_CALCULATED,
              source="", note="", affects=ELEMENTS, blocking=False):
    """One stream. species=None => a Missing term (value unknown, never zero)."""
    if direction not in ("in", "out"):
        raise ValueError(direction)
    if species is not None:
        species = {sp: float(n) for sp, n in species.items()}
    t = {"name": name, "direction": direction, "species": species, "ash_kg_h": float(ash_kg_h),
         "status": status, "source": source, "note": note, "affects": tuple(affects), "blocking": bool(blocking),
         "mass_published": mass_kg_h is not None}
    if species is None:
        t["mass_kg_h"] = None
        t["status"] = ps.STATUS_MISSING
    elif mass_kg_h is not None:
        t["mass_kg_h"] = float(mass_kg_h)
    else:
        t["mass_kg_h"] = sum(n * molar_mass(sp) for sp, n in species.items()) / 1000.0 + float(ash_kg_h)
    return t


def element_moles(term, element):
    if term["species"] is None:
        return 0.0
    return sum(n * FORMULA[sp].get(element, 0) for sp, n in term["species"].items())


def classify(rel):
    """rel = |residual| / inflow."""
    r = abs(rel)
    if r < TOL_NUMERICAL:
        return VERDICT_NUMERICAL
    if r < TOL_STATED:
        return VERDICT_STATED
    return VERDICT_NO


def closure(terms, elements=ELEMENTS):
    """Element balances (mol/h and kg/h), ash, and total mass for a list of terms.

    Missing terms are never summed: they are returned in `missing_terms`, and an element/mass row they affect is flagged
    `complete=False`. A BLOCKING Missing term makes the affected rows `cannot be evaluated`."""
    missing = [t for t in terms if t["species"] is None]
    blocking = [t for t in missing if t["blocking"]]
    rows = {}
    for el in elements:
        i = sum(element_moles(t, el) for t in terms if t["direction"] == "in")
        o = sum(element_moles(t, el) for t in terms if t["direction"] == "out")
        m = ATOMIC_MASS[el] / 1000.0
        res = i - o
        rel = res / i if i else float("nan")
        aff = [t["name"] for t in missing if el in t["affects"]]
        blk = [t["name"] for t in blocking if el in t["affects"]]
        rows[el] = {"in_mol_h": i, "out_mol_h": o, "residual_mol_h": res, "in_kg_h": i * m, "out_kg_h": o * m, "residual_kg_h": res * m,
                    "rel": rel, "rel_pct": 100.0 * rel, "missing_terms": aff, "complete": not aff,
                    "verdict": VERDICT_NA if blk or not i else classify(rel)}
    ash_in = sum(t["ash_kg_h"] for t in terms if t["direction"] == "in")
    ash_out = sum(t["ash_kg_h"] for t in terms if t["direction"] == "out")
    rows["ash"] = {"in_kg_h": ash_in, "out_kg_h": ash_out, "residual_kg_h": ash_in - ash_out,
                   "rel": (ash_in - ash_out) / ash_in if ash_in else float("nan"), "missing_terms": [], "complete": True,
                   "verdict": classify((ash_in - ash_out) / ash_in) if ash_in else VERDICT_NA}
    rows["ash"]["rel_pct"] = 100.0 * rows["ash"]["rel"]
    m_in = sum(t["mass_kg_h"] for t in terms if t["direction"] == "in" and t["species"] is not None)
    m_out = sum(t["mass_kg_h"] for t in terms if t["direction"] == "out" and t["species"] is not None)
    res = m_in - m_out
    rel = res / m_in if m_in else float("nan")
    rows["mass"] = {"in_kg_h": m_in, "out_kg_h": m_out, "residual_kg_h": res, "rel": rel, "rel_pct": 100.0 * rel,
                    "missing_terms": [t["name"] for t in missing], "complete": not missing,
                    "verdict": VERDICT_NA if blocking or not m_in else classify(rel)}
    return {"rows": rows, "missing_terms": [t["name"] for t in missing], "terms": terms}


# =============================================================================
# GA-001 control volume
# =============================================================================

def _recycle(snapshot, previous_snapshot):
    """The tail-gas atoms GA-001 actually used THIS cycle: the PREVIOUS cycle's HB-009 TailGas H2/CO/CH4
    (ga001_gasifier_model.py:660-694, lagged read). Returns (species_mol_h | None, label, status)."""
    out = _val(snapshot, ("GA-001", "Outputs"))
    if not out["recycle_active"]:
        if tail_gas_mode(snapshot) == "heat_only":
            return {}, "none (tail_gas_mode = heat_only: the tail gas is heat, no atoms re-enter GA-001)", ps.STATUS_CALCULATED
        return {}, "none (first cycle: no previous tail gas)", ps.STATUS_CALCULATED
    if previous_snapshot is None:
        return None, "recycle is active but the previous cycle's snapshot was not supplied", ps.STATUS_MISSING
    tail = _val(previous_snapshot, ("HB-009", "TailGas"))
    sp = {s: float(tail["species_nm3_h"][s]) / NM3_PER_MOL for s in ("H2", "CO", "CH4")}
    return sp, "previous cycle's HB-009 tail gas (H2, CO, CH4; CO2 and N2 are not recycled, ga001_gasifier_model.py:654-657)", ps.STATUS_CALCULATED


def ga001_inputs(snapshot, previous_snapshot=None):
    """Every GA-001 input from the snapshot (ga001_gasifier_model.py:740-746) plus FE-005's residual moisture (:711-715).

    GA-001 reads FE-005 LAGGED (one cycle old) and only adds the moisture when FE-005 already existed: the published
    GA-001 'inputs' list names FE-005 exactly when it did (ga001:820). On cycle 1 it did not, and the dry feed rate is the
    41.67 kg/h placeholder (ga001:418-435), so the audit reads no moisture there."""
    g = {k: _val(snapshot, ("GA-001-INPUT", k)) for k in ("dry_feed_rate_kg_h", "equivalence_ratio", "steam_to_feed_ratio",
                                                          "carbon_conversion_efficiency", "ch4_carbon_fraction",
                                                          "feedstock_composition", "operating_temperature_C")}
    g["dry_feed_rate_kg_h"] = float(g["dry_feed_rate_kg_h"])
    used = ("FE-005", "MoistureBalance") in [tuple(k) for k in snapshot[("GA-001", "Outputs")]["source"]["inputs"]]
    g["moisture_lag_note"] = "none (FE-005 did not exist when GA-001 ran)"
    g["residual_water_kg_h"] = 0.0
    if used:
        src = previous_snapshot if previous_snapshot is not None else snapshot
        g["residual_water_kg_h"] = float(_val(src, ("FE-005", "MoistureBalance"))["residual_water_kg_h"])
        g["moisture_lag_note"] = ("previous cycle's FE-005 (lagged, as GA-001 read it)" if previous_snapshot is not None
                                  else "current-cycle FE-005 (previous snapshot not supplied; identical unless the feed changed)")
    return g


def feed_atoms_mol_h(inp):
    """Elemental feed, re-derived from the mass fractions (independent of ga001.elemental_atomic_ratios)."""
    a = ga001.ASH_FRACTION
    comp, f = inp["feedstock_composition"], inp["dry_feed_rate_kg_h"]
    return {el: (1.0 - a) * comp[el] * f * 1000.0 / ATOMIC_MASS[el] for el in ELEMENTS}


def gas_species_mol_h(out):
    """GA-001 Outputs -> mol/h per species (wet): dry species from dry_flow x mol%, H2O from wet - dry."""
    dry, wet = out["dry_flow_nm3_h"], out["wet_flow_nm3_h"]
    sp = {s: float(dry * out[f"{s}_mol_pct_dry"] / 100.0 / NM3_PER_MOL) for s in ("H2", "CO", "CO2", "CH4", "N2")}
    sp["H2O"] = float((wet - dry) / NM3_PER_MOL)
    return sp


def ga001_terms(snapshot, previous_snapshot=None):
    """Terms for the GA-001 control volume with the recycle counted as an EXTERNAL feed."""
    inp = ga001_inputs(snapshot, previous_snapshot)
    out = _val(snapshot, ("GA-001", "Outputs"))
    f = inp["dry_feed_rate_kg_h"]
    feed = feed_atoms_mol_h(inp)
    rec, rec_label, rec_status = _recycle(snapshot, previous_snapshot)
    rec_atoms = {el: 0.0 for el in ELEMENTS}
    if rec:
        for s, n in rec.items():
            for el, k in FORMULA[s].items():
                rec_atoms[el] += n * k
    c_tot, h_tot, o_tot = feed["C"] + rec_atoms["C"], feed["H"] + rec_atoms["H"], feed["O"] + rec_atoms["O"]
    o2_air = inp["equivalence_ratio"] * (c_tot + h_tot / 4.0 - o_tot / 2.0)    # er x (1 + x/4 - y/2) x C_total, ga001:253-258,299-300
    n2_air = o2_air * (0.79 / 0.21)                                              # ga001_gasifier_model.py:301
    steam = inp["steam_to_feed_ratio"] * f * 1000.0 / M_H2O_ENGINE               # ga001_gasifier_model.py:752
    moist = inp["residual_water_kg_h"] * 1000.0 / M_H2O_ENGINE                   # ga001_gasifier_model.py:715
    byp = gmb.byproduct_mass_flows(f)                                            # gasifier_mass_balance.py:65-71

    terms = [
        make_term("dry feed (C,H,O,N + ash)", "in", feed, ash_kg_h=ga001.ASH_FRACTION * f, status=ps.STATUS_ASSUMED,
                  source="GA-001-INPUT dry_feed_rate_kg_h (Calculated, FE-005) x feedstock_composition (Assumed, ga001:193-196); ash 10 % (gasifier_mass_balance.py:61, GA-005)",
                  note="composition is the literature stand-in, not DOK-ING data"),
        make_term("residual moisture in dry feed", "in", {"H2O": moist}, status=ps.STATUS_CALCULATED,
                  source="FE-005 MoistureBalance.residual_water_kg_h (fe_feed_handling.py:290), folded in at ga001:761-763"),
        make_term("air O2", "in", {"O2": o2_air}, status=ps.STATUS_CALCULATED,
                  source="ER x stoichiometric O2 on the recycle-augmented fuel (ga001:299-300, :776-778); ER Assumed 0.25",
                  note="not a published stream: re-derived with the model's own formula"),
        make_term("air N2", "in", {"N2": n2_air}, status=ps.STATUS_CALCULATED,
                  source="O2 x 0.79/0.21 (ga001:301); argon and CO2 in air ignored by the model"),
        make_term("gasifier steam", "in", {"H2O": steam}, status=ps.STATUS_ASSUMED,
                  source="steam_to_feed_ratio 0.4 kg/kg (Assumed, ga001:458-480) x dry feed; GA-003 registry 15 kg/h"),
    ]
    if rec is None:
        terms.append(make_term("tail-gas recycle (HB-009)", "in", None, status=ps.STATUS_MISSING, source=rec_label,
                               affects=("C", "H", "O"), blocking=True))
    else:
        terms.append(make_term("tail-gas recycle (HB-009)", "in", rec, status=rec_status, source=rec_label, note="external feed to this control volume"))
    terms += [
        make_term("product gas (wet)", "out", gas_species_mol_h(out), status=ps.STATUS_CALCULATED,
                  source="GA-001 Outputs dry_flow_nm3_h x mol% and (wet - dry) water (ga001:793-803)"),
        make_term("ash", "out", {}, ash_kg_h=byp["ash_kg_h"], mass_kg_h=byp["ash_kg_h"], status=ps.STATUS_ASSUMED,
                  source="ASH_FRACTION x dry feed, gasifier_mass_balance.py:65-71 (GA-005 'Ash discharge rate 10 % of feed')"),
        make_term("carbon black (taken as pure C)", "out", {"C": byp["carbon_black_kg_h"] * 1000.0 / ATOMIC_MASS["C"]}, status=ps.STATUS_ASSUMED,
                  source="CARBON_BLACK_FRACTION 5 % x dry feed (gasifier_mass_balance.py:62, derived from GA-008 1.88 kg/h / 37.5 kg/h); pure carbon is an audit assumption (GA-008 'product ash < 1 wt%')"),
        make_term("tar", "out", None, affects=("C", "H", "O"), source="GA-001 'Tar content' is permanently Missing (ga001_gasifier_model.py:842-857)"),
        make_term("sulfur, chlorine, argon and trace species", "out", None, affects=(), source="no S/Cl/Ar in the feed composition (ga001:193-196); GC-008/GC-009 inlets are fixed ppm (Assumed), not tied to the feed"),
    ]
    return {"terms": terms, "inputs": inp, "recycle": rec, "recycle_label": rec_label, "feed_atoms": feed,
            "recycle_atoms": rec_atoms, "air_o2_mol_h": o2_air, "air_n2_mol_h": n2_air}


def ga001_carbon_detail(snapshot, previous_snapshot=None):
    """Where the carbon that does not leave in the gas goes: the model's implied unconverted carbon, (1 - conversion) x total C
    (ga001_gasifier_model.py:303), against the carbon-black stream the byproduct module reports (5 % of dry feed)."""
    d = ga001_terms(snapshot, previous_snapshot)
    inp, rec = d["inputs"], d["recycle_atoms"]
    c_tot = d["feed_atoms"]["C"] + rec["C"]
    conv = inp["carbon_conversion_efficiency"]
    out = _val(snapshot, ("GA-001", "Outputs"))
    gas = gas_species_mol_h(out)
    c_gas = gas["CO"] + gas["CO2"] + gas["CH4"]
    implied_unconverted = (1.0 - conv) * c_tot
    cb = gmb.byproduct_mass_flows(inp["dry_feed_rate_kg_h"])["carbon_black_kg_h"] * 1000.0 / ATOMIC_MASS["C"]
    k = ATOMIC_MASS["C"] / 1000.0
    return {"C_total_mol_h": c_tot, "C_in_gas_mol_h": c_gas, "C_not_in_gas_mol_h": c_tot - c_gas,
            "implied_unconverted_C_mol_h": implied_unconverted, "carbon_black_C_mol_h": cb,
            "unassigned_C_mol_h": implied_unconverted - cb,
            "C_total_kg_h": c_tot * k, "C_in_gas_kg_h": c_gas * k, "C_not_in_gas_kg_h": (c_tot - c_gas) * k,
            "implied_unconverted_C_kg_h": implied_unconverted * k, "carbon_black_C_kg_h": cb * k,
            "unassigned_C_kg_h": (implied_unconverted - cb) * k,
            "unconverted_share_of_recycle_C_kg_h": (1.0 - conv) * rec["C"] * k}


def ga001_recycle_cross_check(snapshot, previous_snapshot=None):
    """Independent check of the recycle the audit read from the previous cycle: back out the total carbon GA-001 must have
    seen from its OWN published gas (C_gas / conversion) and compare. Differences point at a publication/lag problem."""
    d = ga001_terms(snapshot, previous_snapshot)
    if d["recycle"] is None:
        return None
    conv = d["inputs"]["carbon_conversion_efficiency"]
    gas = gas_species_mol_h(_val(snapshot, ("GA-001", "Outputs")))
    c_tot_implied = (gas["CO"] + gas["CO2"] + gas["CH4"]) / conv
    c_tot_read = d["feed_atoms"]["C"] + d["recycle_atoms"]["C"]
    return {"C_total_implied_by_published_gas_mol_h": c_tot_implied, "C_total_from_feed_plus_read_recycle_mol_h": c_tot_read,
            "rel_diff": (c_tot_implied - c_tot_read) / c_tot_read if c_tot_read else float("nan")}


def ga001_balance(snapshot, previous_snapshot=None):
    return closure(ga001_terms(snapshot, previous_snapshot)["terms"])


def atom_balance_like_verify(snapshot, previous_snapshot=None):
    """The GA-001 H and O residuals expressed the way ga001.verify_atom_balance reports them (per mol of total fuel C,
    tolerance 1e-8 x max(1, target)), so D1(a) uses the SAME tolerance rule. Returns (ok, detail)."""
    d = ga001_terms(snapshot, previous_snapshot)
    inp = d["inputs"]
    out = _val(snapshot, ("GA-001", "Outputs"))
    c_tot = d["feed_atoms"]["C"] + d["recycle_atoms"]["C"]
    h_f, o_f = d["feed_atoms"]["H"] + d["recycle_atoms"]["H"], d["feed_atoms"]["O"] + d["recycle_atoms"]["O"]
    x, y, z = h_f / c_tot, o_f / c_tot, d["feed_atoms"]["N"] / c_tot
    steam_per_c = (inp["steam_to_feed_ratio"] * inp["dry_feed_rate_kg_h"] * 1000.0 / M_H2O_ENGINE + inp["residual_water_kg_h"] * 1000.0 / M_H2O_ENGINE) / c_tot
    gas = {s: n / c_tot for s, n in gas_species_mol_h(out).items()}
    return ga001.verify_atom_balance(x, y, z, inp["equivalence_ratio"], steam_per_c, gas)


# =============================================================================
# whole plant / gasification-loop control volumes
# =============================================================================

def _kg_to_mol_water(kg_h):
    return kg_h * 1000.0 / M_H2O_ENGINE


def plant_terms(snapshot, previous_snapshot=None, scope="plant"):
    """Terms for the whole-plant control volume (scope='plant': wet MSW in, dryer, electrolyser included) or for the
    gasification loop (scope='loop': dry feed in; GA-001 + gas cleaning + WGS + PSA + HB-009 tail-gas recycle, with the
    recycle INSIDE the volume, so it is neither an input nor an output).

    The recycle is lagged one cycle (ga001:660-694), so the loop holds a small inventory in transit: this cycle's HB-009 tail
    gas minus the tail gas GA-001 read. It appears as an explicit `accumulation` OUT term (zero once the loop has converged)."""
    ga = ga001_terms(snapshot, previous_snapshot)
    inp = ga["inputs"]
    f = inp["dry_feed_rate_kg_h"]
    a = ga001.ASH_FRACTION
    byp = gmb.byproduct_mass_flows(f)
    wgs = _val(snapshot, ("WGS", "Composition"))
    gc013 = _val(snapshot, ("GC-013", "Gas"))
    tail = _val(snapshot, ("HB-009", "TailGas"))
    hb005 = _val(snapshot, ("HB-005", "Steam"))
    comp = inp["feedstock_composition"]
    terms = []

    if scope == "plant":
        wet = float(_val(snapshot, ("FE-003", "Weighing"))["confirmed_wet_feed_kg_h"])
        fe5 = _val(snapshot, ("FE-005", "MoistureBalance"))
        dry_fe = float(fe5["dry_solids_kg_h"])
        atoms = {el: (1.0 - a) * comp[el] * dry_fe * 1000.0 / ATOMIC_MASS[el] for el in ELEMENTS}
        terms.append(make_term("MSW dry solids (FE-005 outlet)", "in", atoms, ash_kg_h=a * dry_fe, mass_kg_h=dry_fe, status=ps.STATUS_ASSUMED,
                               source="FE-003 confirmed wet feed x (1 - 10 % moisture) (fe_feed_handling.py:288); composition Assumed (ga001:193-196)"))
        terms.append(make_term("MSW moisture (10 % of wet feed)", "in", {"H2O": _kg_to_mol_water(wet - dry_fe)}, mass_kg_h=wet - dry_fe,
                               status=ps.STATUS_CALCULATED, source="FE-003 wet feed - FE-005 dry solids (fe_feed_handling.py:288); 10 % is FE-005's design inlet moisture"))
        terms.append(make_term("dryer vapour (FE-005)", "out", {"H2O": _kg_to_mol_water(float(fe5["water_evaporated_kg_h"]))},
                               mass_kg_h=float(fe5["water_evaporated_kg_h"]), source="FE-005 water_evaporated_kg_h (fe_feed_handling.py:291)"))
    else:
        terms.append(ga["terms"][0])                       # dry feed as GA-001 receives it
        terms.append(ga["terms"][1])                       # residual moisture

    by_name = {t["name"]: t for t in ga["terms"]}
    terms.append(by_name["air O2"])
    terms.append(by_name["air N2"])
    terms.append(by_name["gasifier steam"])
    terms.append(make_term("WGS steam (HB-005)", "in", {"H2O": _kg_to_mol_water(float(hb005["steam_kg_h"]))}, mass_kg_h=float(hb005["steam_kg_h"]),
                           status=ps.STATUS_CALCULATED, source="HB-005 Steam.steam_kg_h = 4 x CO mol/h (hb_wgs_psa_storage_chain.py:187-189)",
                           note="where this steam comes from (boiler fuel, feedwater make-up) is not modelled"))
    if scope == "plant":
        hb011 = _val(snapshot, ("HB-011", "Electrolyser"))
        water_kg = float(hb011["water_l_h"])            # 1 L/Nm3 (hb_remaining_chain.py:170,307), 1 kg/L Assumed
        n_h2 = float(hb011["h2_kg_h"]) * 1000.0 / M_H2_ENGINE
        terms.append(make_term("electrolyser feed water (HB-011)", "in", {"H2O": _kg_to_mol_water(water_kg)}, mass_kg_h=water_kg, status=ps.STATUS_CALCULATED,
                               source="HB-011 water_l_h (hb_remaining_chain.py:307), 1 kg/L assumed"))
        terms.append(make_term("electrolyser H2 (HB-011)", "out", {"H2": n_h2}, mass_kg_h=float(hb011["h2_kg_h"]), source="HB-011 h2_kg_h"))
        terms.append(make_term("electrolyser O2 (stoichiometric, not published)", "out", {"O2": n_h2 / 2.0}, status=ps.STATUS_CALCULATED,
                               source="audit: 2 H2O -> 2 H2 + O2; the engine publishes no O2 stream"))

    terms.append(make_term("ash", "out", {}, ash_kg_h=byp["ash_kg_h"], mass_kg_h=byp["ash_kg_h"], status=ps.STATUS_ASSUMED, source=by_name["ash"]["source"]))
    terms.append(by_name["carbon black (taken as pure C)"])
    cond_kg = float(_val(snapshot, ("GC-004", "Condensed water"))) * 1000.0
    terms.append(make_term("quench condensate (GC-004)", "out", {"H2O": _kg_to_mol_water(cond_kg)}, mass_kg_h=cond_kg, source="GC-004 'Condensed water' m3/h x 1000 kg/m3 (gc_gas_cleaning_chain.py:265-268)"))
    n_wgs_h2o = float(wgs["H2O"]) * float(gc013["dry_flow_nm3_h"]) / NM3_PER_MOL
    terms.append(make_term("WGS unreacted steam (knocked out, no equipment)", "out", {"H2O": n_wgs_h2o}, status=ps.STATUS_CALCULATED,
                           source="WGS Composition.H2O x GC-013 dry flow (hb_wgs_psa_storage_chain.py:262-270)",
                           note="the engine has no condensate stream or unit for this water"))
    sp = tail["species_nm3_h"]
    terms.append(make_term("tail-gas CO2 + N2 to flare/vent (HB-009 -> EU-007)", "out", {"CO2": float(sp["CO2"]) / NM3_PER_MOL, "N2": float(sp["N2"]) / NM3_PER_MOL},
                           source="HB-009 TailGas.species_nm3_h; EU-007 inert_in (eu_utilities_chp.py:485)"))
    h2_prod = float(_val(snapshot, ("HB-012", "Compressor"))["h2_kg_h"])
    terms.append(make_term("H2 product to storage (HB-012)", "out", {"H2": h2_prod * 1000.0 / M_H2_ENGINE}, mass_kg_h=h2_prod,
                           source="HB-012 h2_kg_h (hb_wgs_psa_storage_chain.py:467); PSA product taken as 100 % H2 (HB-009 docstring)"))

    # recycle inside the volume: the tail-gas H2/CO/CH4 produced this cycle minus what GA-001 read (one cycle old) = inventory in transit
    if tail_gas_mode(snapshot) == "heat_only":
        # the tail combustibles are not recycled: they are burned for heat (audit convention: complete combustion, no burner exists in the engine)
        h2, co, ch4 = (float(sp[k]) / NM3_PER_MOL for k in ("H2", "CO", "CH4"))
        terms.append(make_term("air O2 for burning the tail-gas combustibles", "in", {"O2": 0.5 * h2 + 0.5 * co + 2.0 * ch4}, status=ps.STATUS_CALCULATED,
                               source="audit convention for tail_gas_mode = heat_only: H2 + 1/2 O2, CO + 1/2 O2, CH4 + 2 O2 (complete combustion); the engine has no burner",
                               note="the combustion air's N2 passes through and is not counted"))
        terms.append(make_term("tail-gas combustion products (CO2, H2O) to the stack", "out", {"CO2": co + ch4, "H2O": h2 + 2.0 * ch4}, status=ps.STATUS_CALCULATED,
                               source="same convention; the heat released is the tail gas LHV (see (GA-001, EnergyBalance))"))
    elif ga["recycle"] is None:
        terms.append(make_term("recycle inventory in transit (lag)", "out", None, affects=("C", "H", "O"), blocking=True, source=ga["recycle_label"]))
    else:
        now = {s: float(sp[s]) / NM3_PER_MOL for s in ("H2", "CO", "CH4")}
        used = {s: ga["recycle"].get(s, 0.0) for s in now}
        terms.append(make_term("recycle inventory in transit (lag)", "out", {s: now[s] - used[s] for s in now}, status=ps.STATUS_CALCULATED,
                               source="HB-009 tail gas this cycle - tail gas GA-001 read (lagged, ga001:660-694); zero when the loop has converged",
                               note="stored, not lost: the recycle is read one cycle late"))
    terms.append(make_term("tar", "out", None, affects=("C", "H", "O"), source="GA-001 'Tar content' Missing (ga001_gasifier_model.py:842-857)"))
    terms.append(make_term("dust / fly ash, S and Cl species, argon", "out", None, affects=(),
                           source="GC-001 Dust Missing; GC-003 2 g/Nm3 and GC-008/009 ppm are fixed registry values, not tied to the feed"))
    terms.append(make_term("quench / scrubber / cooling-tower water loops (make-up, blowdown, evaporation)", "out", None, affects=(),
                           source="GC-005/007/008/009 blowdowns (Assumed m3/h) have no make-up stream; EU-008 evaporation not modelled"))
    terms.append(make_term("PSA product impurities (purity 99.97 % taken as 100 %)", "out", None, affects=("C", "H", "O", "N"),
                           source="HB-006 purity is a design target only (tab1_integration.py:159-165)"))
    terms.append(make_term("FE-002 tramp metal reject", "out", None, affects=(), source="FE-002 TrampMetalReject Missing (fe_feed_handling.py:194)"))
    terms.append(make_term("membrane (HB-010) and LOHC (HB-014..017) branches", "out", None, affects=(),
                           source="HB-010 separation, HB-014/016/017 mass balances and HB-015 inventory are Missing"))
    return {"terms": terms, "ga001": ga}


def plant_balance(snapshot, previous_snapshot=None, scope="plant"):
    return closure(plant_terms(snapshot, previous_snapshot, scope)["terms"])


def fe_clipped_surplus_kg_h(snapshot):
    """Mass delivered by FE-001/002 but not accepted by FE-003's 29-50 kg/h window (fe_feed_handling.py:221-224: 'this simplified chain does not model where the surplus goes')."""
    delivered = float(_val(snapshot, ("FE-002", "MassBalance"))["outlet_kg_h"])
    accepted = float(_val(snapshot, ("FE-003", "Weighing"))["confirmed_wet_feed_kg_h"])
    return delivered - accepted


def storage_inventory_check(snapshot, previous_snapshot):
    """HB-013 H2 inventory: level(n) should be level(n-1) + (inflow - outflow) x dt. The clamp to [0, 50] kg
    (hb_wgs_psa_storage_chain.py:537) creates H2 when the store would go below zero and destroys it above capacity."""
    st = _val(snapshot, ("HB-013", "Storage"))
    prev = _val(previous_snapshot, ("HB-013", "Storage"))["level_kg"] if previous_snapshot is not None else 0.0
    dt = cycle_clock.hours_per_cycle()
    expected = prev + (st["inflow_kg_h"] - st["outflow_kg_h"]) * dt
    created = st["level_kg"] - expected
    inflow = st["inflow_kg_h"] * dt
    return {"previous_level_kg": float(prev), "inflow_kg": float(inflow), "outflow_kg": float(st["outflow_kg_h"] * dt), "level_kg": float(st["level_kg"]),
            "expected_level_without_clamp_kg": float(expected), "h2_created_by_clamp_kg": float(created),
            "rel_of_inflow": float(created / inflow) if inflow else float("nan"),
            "verdict": classify(created / inflow) if inflow else VERDICT_NA}


# =============================================================================
# explaining the residuals from the code (an identity, not a gate)
# =============================================================================

def explain_carbon_residual(snapshot, previous_snapshot=None):
    """The GA-001 carbon residual is exactly  (1 - conversion) x (C_feed + C_recycle)  -  carbon_black,  because
    ga001_gasifier_model.py:303 sends only `conversion` of the carbon to the gas (the rest has no stream) while the carbon-black
    stream is an independent 5 % of dry feed (gasifier_mass_balance.py:62). Returns the identity's two sides (kg/h)."""
    d = ga001_terms(snapshot, previous_snapshot)
    inp = d["inputs"]
    k = ATOMIC_MASS["C"] / 1000.0
    conv = inp["carbon_conversion_efficiency"]
    c_feed, c_rec = d["feed_atoms"]["C"], d["recycle_atoms"]["C"]
    cb_kg = gmb.byproduct_mass_flows(inp["dry_feed_rate_kg_h"])["carbon_black_kg_h"]
    predicted = (1.0 - conv) * (c_feed + c_rec) * k - cb_kg
    measured = closure(d["terms"])["rows"]["C"]["residual_kg_h"]
    # the conversion at which a FEED-ONLY (no recycle) carbon balance would match the carbon-black stream exactly
    conv_matching_cb = 1.0 - cb_kg / (c_feed * k) if c_feed else float("nan")
    return {"measured_kg_h": measured, "predicted_kg_h": predicted, "difference_kg_h": measured - predicted,
            "unconverted_from_feed_kg_h": (1.0 - conv) * c_feed * k, "unconverted_from_recycle_kg_h": (1.0 - conv) * c_rec * k,
            "carbon_black_kg_h": cb_kg, "conversion_used": conv, "conversion_that_would_match_carbon_black_feed_only": conv_matching_cb}


def explain_plant_mass_residual(snapshot, previous_snapshot=None):
    """Decomposes the whole-plant total-mass residual into causes that can be read from the code:
       mass residual = (C + H + O + N residuals in kg, from the exact mole balances) + (published-mass basis effect)
       1. carbon: see explain_carbon_residual;
       2. the electrolyser's water: HB-011 draws 1 L/Nm3 (hb_remaining_chain.py:170,307) but 2 H2O -> 2 H2 + O2 needs 0.80 L/Nm3, and the
          engine publishes no stream for the excess (H residual 2e, O residual e, with e = water mol/h - H2 mol/h);
       3. the water molar-mass basis: the engine converts water with 18.015 (ga001_gasifier_model.py:165) while the atomic masses give 18.016, so a
          term whose mass is the engine's published kg differs from its mole-based mass by ~5.5e-5 of the water (signed sum over such terms)."""
    pt = plant_terms(snapshot, previous_snapshot, "plant")
    bal = closure(pt["terms"])
    r = bal["rows"]
    hb011 = _val(snapshot, ("HB-011", "Electrolyser"))
    n_w = float(hb011["water_l_h"]) * 1000.0 / M_H2O_ENGINE
    n_h2 = float(hb011["h2_kg_h"]) * 1000.0 / M_H2_ENGINE
    e = n_w - n_h2
    carbon = explain_carbon_residual(snapshot, previous_snapshot)["predicted_kg_h"]
    electrolyser_kg = (2.0 * e * ATOMIC_MASS["H"] + e * ATOMIC_MASS["O"]) / 1000.0
    basis = 0.0
    for t in pt["terms"]:
        if t["species"] is not None and t["mass_published"]:
            mol_based = sum(n * molar_mass(sp) for sp, n in t["species"].items()) / 1000.0 + t["ash_kg_h"]
            basis += (1.0 if t["direction"] == "in" else -1.0) * (t["mass_kg_h"] - mol_based)
    measured = r["mass"]["residual_kg_h"]
    return {"electrolyser_excess_water_mol_h": e, "H_residual_expected_kg_h": 2.0 * e * ATOMIC_MASS["H"] / 1000.0, "H_residual_measured_kg_h": r["H"]["residual_kg_h"],
            "O_residual_expected_kg_h": e * ATOMIC_MASS["O"] / 1000.0, "O_residual_measured_kg_h": r["O"]["residual_kg_h"],
            "mass_residual_measured_kg_h": measured, "carbon_part_kg_h": carbon, "electrolyser_part_kg_h": electrolyser_kg,
            "water_molar_mass_basis_kg_h": basis, "mass_unexplained_kg_h": measured - carbon - electrolyser_kg - basis}


# =============================================================================
# energy
# =============================================================================
# Every enthalpy below is on ONE basis: lower heating value + sensible heat above 25 degC, with water VAPOUR at 25 degC as the
# zero for H2O (so liquid water at 25 degC is -DH_VAP). Species LHVs come from the standard enthalpies of formation above;
# sensible heat uses the repo's own mean heat capacities (gc_gas_cleaning_chain.py:106) and liquid-water cp
# (hb_wgs_psa_storage_chain.py:94). All terms in kW. Nothing here enters the engine.

def _sens_kw(species, t_c):
    """Sensible heat (kW) of a {species: mol/h} gas stream from 25 degC to t_c, mean cp."""
    return sum(n * CP_J_MOLK[sp] * (t_c - T_REF_C) for sp, n in species.items()) / 1000.0 * KW_PER_KJ_H


def _lhv_kw(species):
    return sum(n * LHV_KJ_MOL.get(sp, 0.0) for sp, n in species.items()) * KW_PER_KJ_H


def _liquid_water_kw(n_mol_h, t_c=T_REF_C):
    """Liquid water at t_c on the vapour-at-25-degC zero: -DH_VAP + cp_liq x (t - 25)."""
    return n_mol_h * (-DH_VAP_KJ_MOL + CP_LIQUID_WATER_J_MOLK * (t_c - T_REF_C) / 1000.0) * KW_PER_KJ_H


def _vapour_water_kw(n_mol_h, t_c):
    return n_mol_h * CP_J_MOLK["H2O"] * (t_c - T_REF_C) / 1000.0 * KW_PER_KJ_H


def feedstock_lhv_estimates(composition=None):
    """Dry-basis LHV (MJ/kg dry feed incl. ash) of the model's own C/H/O/N + ash composition from two published
    ultimate-analysis correlations (S = 0):
        Channiwala & Parikh (2002), Fuel 81: HHV = 0.3491 C + 1.1783 H + 0.1005 S - 0.1034 O - 0.0151 N - 0.0211 ASH
        Dulong:                              HHV = 0.3383 C + 1.443 (H - O/8)
    (C, H, O, N, ASH as wt % of the DRY feed, HHV in MJ/kg). LHV = HHV - 2.442 MJ/kg x (water formed = 9 H / 100), with the
    latent heat from DH_VAP above. Status Estimated: correlations applied to an Assumed composition; the two disagree, which is
    the stated range."""
    comp = composition or {"C": ga001.FEEDSTOCK_C_FRACTION, "H": ga001.FEEDSTOCK_H_FRACTION, "O": ga001.FEEDSTOCK_O_FRACTION, "N": ga001.FEEDSTOCK_N_FRACTION}
    a = ga001.ASH_FRACTION
    c, h, o, n = ((1.0 - a) * comp[k] * 100.0 for k in ("C", "H", "O", "N"))
    ash = a * 100.0
    hhv_cp = 0.3491 * c + 1.1783 * h - 0.1034 * o - 0.0151 * n - 0.0211 * ash
    hhv_du = 0.3383 * c + 1.443 * (h - o / 8.0)
    latent = DH_VAP_KJ_MOL / M_H2O_ENGINE                        # MJ/kg
    lhv_cp = hhv_cp - latent * 9.0 * h / 100.0
    lhv_du = hhv_du - latent * 9.0 * h / 100.0
    return {"dry_wt_pct": {"C": c, "H": h, "O": o, "N": n, "ash": ash}, "HHV_channiwala_parikh_MJ_kg": hhv_cp, "HHV_dulong_MJ_kg": hhv_du,
            "LHV_channiwala_parikh_MJ_kg": lhv_cp, "LHV_dulong_MJ_kg": lhv_du, "range_MJ_kg": (min(lhv_cp, lhv_du), max(lhv_cp, lhv_du)),
            "status": ps.STATUS_ESTIMATED}


def dokink_lhv_range():
    """DOK-ING's Confirmed dry LHV range, read live (design_basis.py; RFI #2). None if not confirmed."""
    r = design_basis.get_feedstock_composition_ranges()
    return None if r is None else tuple(r["lhv_mj_per_kg"])


def lhv_cases():
    """The feed-LHV values every energy balance is evaluated at: DOK-ING's Confirmed range ends (15, 20 MJ/kg dry), the midpoint
    (Assumed 17.5), and the model composition's own correlation estimate (midpoint of the two correlations)."""
    lo, hi = dokink_lhv_range()
    est = feedstock_lhv_estimates()["range_MJ_kg"]
    return {"DOK-ING low (Confirmed range end)": lo, "DOK-ING midpoint (Assumed point)": 0.5 * (lo + hi), "DOK-ING high (Confirmed range end)": hi,
            "model composition (Estimated, correlation midpoint)": 0.5 * (est[0] + est[1])}


def _en(name, kw, status, source, note=""):
    return {"name": name, "kw": float(kw), "status": status, "source": source, "note": note}


def gasifier_energy(snapshot, previous_snapshot, lhv_mj_kg):
    """GA-001 energy balance, recycle as an external feed. GA-001 computes NO heat duty (temperature enters only the WGS
    equilibrium constant, ga001_gasifier_model.py:314, and the registry value is read at :230): so the heat the gasifier
    would have to add (+) or remove (-) to leave at its stated temperature is IMPLIED here from the enthalpies below.
    Status: Calculated, not part of the engine."""
    ga = ga001_terms(snapshot, previous_snapshot)
    if ga["recycle"] is None:
        raise AuditInputMissing(("HB-009", "TailGas (previous cycle)"))
    inp = ga["inputs"]
    f = inp["dry_feed_rate_kg_h"]
    t_gas = float(inp["operating_temperature_C"])
    by = {t["name"]: t for t in ga["terms"]}
    gas = by["product gas (wet)"]["species"]
    c_not_gas = ga["feed_atoms"]["C"] + ga["recycle_atoms"]["C"] - (gas["CO"] + gas["CO2"] + gas["CH4"])      # mol/h solid carbon
    kg_c_not_gas = c_not_gas * ATOMIC_MASS["C"] / 1000.0
    ash_kg = ga001.ASH_FRACTION * f
    cp_s = SOLIDS_CP_KJ_KGK[0]
    feed_chem = f * lhv_mj_kg / 3.6
    ins = [
        _en("dry feed chemical energy (dry mass x LHV)", feed_chem, ps.STATUS_ASSUMED, "FE-005 dry solids x LHV; LHV in DOK-ING's Confirmed 15-20 MJ/kg dry range, point is a case",
            "feed taken at 25 degC: its temperature after the dryer is not stated (cp of the feed is Missing)"),
        _en("residual moisture (liquid water, 25 degC)", _liquid_water_kw(by["residual moisture in dry feed"]["species"]["H2O"]), ps.STATUS_CALCULATED, "FE-005 residual_water_kg_h"),
        _en("air sensible heat (preheated to 200 degC)", _sens_kw({"O2": ga["air_o2_mol_h"], "N2": ga["air_n2_mol_h"]}, GA004_AIR_PREHEAT_C), ps.STATUS_ESTIMATED,
            "GA-004 air preheat 200 degC (registry); cp O2 = cp N2 (Estimated)"),
        _en("gasifier steam sensible heat (350 degC vapour)", _sens_kw({"H2O": by["gasifier steam"]["species"]["H2O"]}, GA004_STEAM_C), ps.STATUS_ESTIMATED,
            "GA-004 steam 350 degC (registry); mean cp 300-1200 K applied from 25 degC"),
        _en("tail-gas recycle chemical energy (H2, CO, CH4)", _lhv_kw(ga["recycle"]), ps.STATUS_CALCULATED, "previous cycle HB-009 tail gas x species LHV",
            "recycle gas taken at 25 degC (temperature not stated: Assumed)"),
    ]
    outs = [
        _en("product gas chemical energy (H2, CO, CH4)", _lhv_kw(gas), ps.STATUS_CALCULATED, "GA-001 Outputs x species LHV"),
        _en("product gas sensible heat (at operating temperature, wet)", _sens_kw(gas, t_gas), ps.STATUS_ESTIMATED, f"GA-001 {t_gas:.0f} degC (ga001:230); repo mean cp"),
        _en("carbon not in the gas: chemical energy (graphite LHV)", c_not_gas * LHV_KJ_MOL["C"] * KW_PER_KJ_H, ps.STATUS_CALCULATED,
            "total C - C in gas (the model's implied unconverted carbon, ga001:303)"),
        _en("char + ash sensible heat at bed temperature", (kg_c_not_gas + ash_kg) * cp_s * (t_gas - T_REF_C) * KW_PER_KJ_H, ps.STATUS_ASSUMED,
            f"cp {SOLIDS_CP_KJ_KGK[0]} kJ/kg.K, range {SOLIDS_CP_KJ_KGK[1]}-{SOLIDS_CP_KJ_KGK[2]} (Assumed; no solids cp in the repo)"),
    ]
    missing = ["tar chemical and sensible energy (GA-001 tar Missing)", "heat loss through the 150 mm refractory and shell (no loss model; GA-001 registry gives geometry only)",
               "feed and recycle sensible heat (feed/recycle temperatures not stated)"]
    sum_in, sum_out = sum(t["kw"] for t in ins), sum(t["kw"] for t in outs)
    q = sum_out - sum_in
    heat_cap_kw_per_k = (sum(n * CP_J_MOLK[sp] for sp, n in gas.items()) / 1000.0 + (kg_c_not_gas + ash_kg) * cp_s) * KW_PER_KJ_H
    chem_out = outs[0]["kw"] + outs[2]["kw"]
    t_ad = T_REF_C + (sum_in - chem_out) / heat_cap_kw_per_k      # sensible terms are linear in (T - 25) at fixed composition
    return {"lhv_mj_kg": lhv_mj_kg, "in": ins, "out": outs, "sum_in_kw": sum_in, "sum_out_kw": sum_out, "implied_heat_duty_kw": q,
            "implied_heat_duty_pct_of_feed": 100.0 * q / feed_chem, "reading": ("the gasifier would need to ADD heat" if q > 0 else "the gasifier would have to REMOVE heat"),
            "adiabatic_temperature_c_fixed_composition": t_ad, "missing_terms": missing, "status": "Calculated, not part of the engine",
            "cold_gas_efficiency_incl_recycle": _lhv_kw(gas) / (feed_chem + ins[4]["kw"]), "cold_gas_efficiency_net_of_recycle": (_lhv_kw(gas) - ins[4]["kw"]) / feed_chem,
            "cold_gas_efficiency_formula": "gas LHV (H2+CO+CH4) / (feed LHV + recycle LHV); net of recycle: (gas LHV - recycle LHV) / feed LHV"}


def heat_demands(n_gasifier_steam_mol_h, wgs_steam_kg_h, air_o2_mol_h, air_n2_mol_h, evaporated_kg_h):
    """Heat the plant needs that no engine term sources (kW): raise the gasifier and WGS steam from liquid at 25 degC to vapour at the GA-004 /
    HB-005 350 degC, preheat the air to the GA-004 200 degC, evaporate the feed moisture in the dryer. Named constants above; Estimated.
    Shared by plant_energy and the engine's read-only (GA-001, EnergyBalance) key so the two cannot drift apart."""
    steam_raise = lambda n, t_c: n * (DH_VAP_KJ_MOL + CP_J_MOLK["H2O"] * (t_c - T_REF_C) / 1000.0) * KW_PER_KJ_H
    n_ws = wgs_steam_kg_h * 1000.0 / M_H2O_ENGINE
    return [
        _en("raise gasifier steam: liquid 25 degC -> vapour 350 degC", steam_raise(n_gasifier_steam_mol_h, GA004_STEAM_C), ps.STATUS_ESTIMATED, "DH_VAP + mean cp x (350-25); source of this heat is not in the engine"),
        _en("raise WGS steam: liquid 25 degC -> vapour 350 degC", steam_raise(n_ws, GA004_STEAM_C), ps.STATUS_ESTIMATED, "HB-005 conditions 350 degC / 5 bar(g); the engine counts only HB-003's 20->150 degC sensible duty"),
        _en("preheat air to 200 degC", _sens_kw({"O2": air_o2_mol_h, "N2": air_n2_mol_h}, GA004_AIR_PREHEAT_C), ps.STATUS_ESTIMATED, "GA-004 'recovered process heat'"),
        _en("evaporate feed moisture in the dryer", float(evaporated_kg_h) * 1000.0 / M_H2O_ENGINE * (DH_VAP_KJ_MOL + CP_J_MOLK["H2O"] * (FE005_DRYER_OPERATING_C - T_REF_C) / 1000.0) * KW_PER_KJ_H,
            ps.STATUS_ESTIMATED, "FE-005 heat source 'recovered process heat ... electric/gas trim backup'"),
    ]


def plant_energy(snapshot, previous_snapshot, lhv_mj_kg, vent_temp_c=40.0, knockout_temp_c=40.0):
    """Whole-plant energy balance, steady state, kW, boundary crossings only (internal heat recovery cancels).

    The unknown on the output side is the heat leaving to cooling water, stack and environment. The audit therefore reports the heat
    the balance IMPLIES must be rejected (energy in - known energy out) and compares it with the heat rejection the engine itself reports."""
    ga = ga001_terms(snapshot, previous_snapshot)
    inp = ga["inputs"]
    f = inp["dry_feed_rate_kg_h"]
    fe5 = _val(snapshot, ("FE-005", "MoistureBalance"))
    wet = float(_val(snapshot, ("FE-003", "Weighing"))["confirmed_wet_feed_kg_h"])
    dry = float(fe5["dry_solids_kg_h"])
    grid = _val(snapshot, ("EU-009", "GridBalance"))
    fe4 = _val(snapshot, ("FE-004", "ShredderPower"))
    hb005 = _val(snapshot, ("HB-005", "Steam"))
    hb011 = _val(snapshot, ("HB-011", "Electrolyser"))
    hb012 = _val(snapshot, ("HB-012", "Compressor"))
    wgs = _val(snapshot, ("WGS", "Composition"))
    gc013 = _val(snapshot, ("GC-013", "Gas"))
    tail = _val(snapshot, ("HB-009", "TailGas"))
    cond_kg = float(_val(snapshot, ("GC-004", "Condensed water"))) * 1000.0
    by = {t["name"]: t for t in ga["terms"]}
    cb_kg = gmb.byproduct_mass_flows(f)["carbon_black_kg_h"]
    cd = ga001_carbon_detail(snapshot, previous_snapshot)
    n_h2_psa = float(hb012["h2_kg_h"]) * 1000.0 / M_H2_ENGINE
    n_h2_el = float(hb011["h2_kg_h"]) * 1000.0 / M_H2_ENGINE
    sp = tail["species_nm3_h"]
    n_vent = {"CO2": float(sp["CO2"]) / NM3_PER_MOL, "N2": float(sp["N2"]) / NM3_PER_MOL}
    n_ko = float(wgs["H2O"]) * float(gc013["dry_flow_nm3_h"]) / NM3_PER_MOL
    elec_load = float(grid["consumption_kw"])
    chp_generation = float(grid["generation_kw"])

    ins = [
        _en("dry feed chemical energy (dry mass x LHV)", dry * lhv_mj_kg / 3.6, ps.STATUS_ASSUMED, "FE-005 dry solids x LHV (DOK-ING Confirmed 15-20 MJ/kg dry; point is a case)"),
        _en("feed moisture (liquid water, 25 degC)", _liquid_water_kw((wet - dry) * 1000.0 / M_H2O_ENGINE), ps.STATUS_CALCULATED, "FE-003 wet - FE-005 dry"),
        _en("make-up water for gasifier steam (liquid, 25 degC)", _liquid_water_kw(by["gasifier steam"]["species"]["H2O"]), ps.STATUS_ASSUMED, "ratio 0.4 kg/kg x dry feed"),
        _en("make-up water for WGS steam (liquid, 25 degC)", _liquid_water_kw(hb005["steam_kg_h"] * 1000.0 / M_H2O_ENGINE), ps.STATUS_CALCULATED, "HB-005 steam_kg_h"),
        _en("electrolyser feed water (liquid, 25 degC)", _liquid_water_kw(float(hb011["water_l_h"]) * 1000.0 / M_H2O_ENGINE), ps.STATUS_CALCULATED, "HB-011 water_l_h"),
        _en("electricity consumed, as summed by EU-009", elec_load, ps.STATUS_CALCULATED, "EU-009 consumption_kw = HB-012 + HB-011 + GC-013 fan + EU-008 fan",
            f"CHP/fuel-cell generation this cycle ({chp_generation:.3f} kW) is NOT subtracted: it burns hydrogen already counted as product"),
        _en("shredder FE-004 electricity (computed by the engine, NOT in EU-009)", float(fe4["power_kw"]), ps.STATUS_CALCULATED, "FE-004 ShredderPower.power_kw (fe_feed_handling.py:243)"),
    ]
    outs = [
        _en("PSA hydrogen product, LHV", _lhv_kw({"H2": n_h2_psa}), ps.STATUS_CALCULATED, "HB-012 h2_kg_h x LHV(H2)"),
        _en("electrolyser hydrogen, LHV", _lhv_kw({"H2": n_h2_el}), ps.STATUS_CALCULATED, "HB-011 h2_kg_h x LHV(H2)"),
        _en("carbon black, chemical energy (taken as pure carbon)", cb_kg * 1000.0 / ATOMIC_MASS["C"] * LHV_KJ_MOL["C"] * KW_PER_KJ_H, ps.STATUS_ASSUMED, "5 % of dry feed (gasifier_mass_balance.py:62), graphite LHV"),
        _en("carbon black, sensible heat at 180 degC", cb_kg * SOLIDS_CP_KJ_KGK[0] * (GA008_OPERATING_C - T_REF_C) * KW_PER_KJ_H, ps.STATUS_ASSUMED, "GA-008 operating 180 degC (registry); cp Assumed"),
        _en("model-implied carbon beyond the carbon-black stream (chemical)", cd["unassigned_C_mol_h"] * LHV_KJ_MOL["C"] * KW_PER_KJ_H, ps.STATUS_CALCULATED,
            "(1 - 0.90) x total C minus carbon black; signed (see the GA-001 carbon finding)"),
        _en("vent gas CO2 + N2 sensible heat", _sens_kw(n_vent, vent_temp_c), ps.STATUS_ASSUMED, f"vent at {vent_temp_c:.0f} degC (Assumed 25-65); no combustibles leave (EU-007)"),
        _en("quench condensate (liquid, 65 degC)", _liquid_water_kw(cond_kg * 1000.0 / M_H2O_ENGINE, GC004_QUENCH_OUT_C), ps.STATUS_CALCULATED, "GC-004 condensed water at the 65 degC quench outlet"),
        _en("WGS knocked-out water (liquid)", _liquid_water_kw(n_ko, knockout_temp_c), ps.STATUS_ASSUMED, f"WGS unreacted steam at {knockout_temp_c:.0f} degC (Assumed 25-65)"),
        _en("dryer vapour (100 degC)", _vapour_water_kw(float(fe5["water_evaporated_kg_h"]) * 1000.0 / M_H2O_ENGINE, FE005_DRYER_OPERATING_C), ps.STATUS_CALCULATED, "FE-005 water_evaporated_kg_h at 100 degC"),
    ]
    sum_in, sum_out = sum(t["kw"] for t in ins), sum(t["kw"] for t in outs)
    implied_reject = sum_in - sum_out

    quench_sens = float(_val(snapshot, ("GC-004", "Cooling duty")))
    eu008 = _val(snapshot, ("EU-008", "CoolingSupply"))
    hb003 = _val(snapshot, ("HB-003", "HeatExchanger"))
    reported = [
        _en("GC-004 quench, sensible heat of the dry gas only", quench_sens, ps.STATUS_CALCULATED, "GC-004 Cooling duty (gc_gas_cleaning_chain.py:296; latent heat excluded by the model's own docstring)"),
        _en("HB-012 compressor shaft power (rejected at the intercoolers)", float(hb012["power_kW"]), ps.STATUS_CALCULATED, "HB-012 power_kW"),
    ]
    reported_sum = sum(t["kw"] for t in reported)
    # heat rejection the engine does not compute, from the same constants (Calculated, not part of the engine)
    n_cond = cond_kg * 1000.0 / M_H2O_ENGINE
    h_in_vapour = _vapour_water_kw(n_cond, 860.0)
    h_out_liquid = _liquid_water_kw(n_cond, GC004_QUENCH_OUT_C)
    quench_water = h_in_vapour - h_out_liquid
    ko_in = _vapour_water_kw(n_ko, 220.0)       # unreacted steam leaves the LTS at >= its 220 degC inlet (HB-003 outlet); LTS outlet temperature is not stated
    ko_out = _liquid_water_kw(n_ko, knockout_temp_c)
    candidates = [
        _en("WGS knock-out: cool and condense the unreacted steam (from 220 degC, Assumed)", ko_in - ko_out, ps.STATUS_ESTIMATED,
            "n_H2O x [cp_vap (220-25) + DH_VAP - cp_liq (T-25)]; no unit in the engine rejects this heat"),
        _en("quench: water vapour sensible + condensation (not in GC-004 duty)", quench_water, ps.STATUS_CALCULATED, "n_H2O x [cp_vap (860-25) + DH_VAP - cp_liq (65-25)]; GC-004 docstring says it is omitted"),
        _en("electrolyser: electricity not converted to hydrogen LHV", float(hb011["power_kw"]) - _lhv_kw({"H2": n_h2_el}), ps.STATUS_CALCULATED, "HB-011 power_kw - H2 LHV; no heat-rejection stream exists"),
        _en("shredder FE-004 electricity becomes heat", float(fe4["power_kw"]), ps.STATUS_CALCULATED, "FE-004 power_kw; not in EU-009 nor EU-008"),
    ]
    # internal heat demands the engine does not source (steam raising to the GA-004 / HB-005 conditions)
    internal = heat_demands(by["gasifier steam"]["species"]["H2O"], hb005["steam_kg_h"], ga["air_o2_mol_h"], ga["air_n2_mol_h"], fe5["water_evaporated_kg_h"])
    return {"lhv_mj_kg": lhv_mj_kg, "in": ins, "out": outs, "sum_in_kw": sum_in, "sum_out_known_kw": sum_out, "implied_heat_rejected_kw": implied_reject,
            "engine_reported_rejection": reported, "engine_reported_rejection_kw": reported_sum,
            "eu008_cooling_demand_kw": float(eu008["demand_kw"]), "eu008_includes_hb003_cold_side_kw": float(hb003["Q_cold_side_kW"]),
            "closure_residual_kw": implied_reject - reported_sum, "closure_residual_pct_of_input": 100.0 * (implied_reject - reported_sum) / sum_in,
            "residual_candidates_not_in_engine": candidates, "candidates_sum_kw": sum(t["kw"] for t in candidates),
            "unexplained_after_candidates_kw": implied_reject - reported_sum - sum(t["kw"] for t in candidates),
            "internal_heat_demands_not_sourced_in_engine": internal, "internal_heat_demand_sum_kw": sum(t["kw"] for t in internal),
            "missing_terms": ["heat loss from vessels and piping (no model)", "tar and dust energy (Missing)", "ash sensible heat (discharge temperature not stated)",
                              "nameplate loads outside EU-009 and FE-004: FE-003 0.37, FE-005 5, FE-007 5.5, FE-008 0.75, GA-005 1.1, GA-006 0.55, HB-009 blower 0.5 kW (utilisation not stated)",
                              "boiler / trim fuel for steam raising and drying (not modelled)", "make-up water and cooling-tower evaporation energy"],
            "status": "Calculated from engine outputs + named constants; the balance itself is not part of the engine"}


def efficiency_check(snapshot, previous_snapshot, kpis, lhv_range=None):
    """The efficiencies the Integrated Plant Status reports (tab1_integration.py:173-269), re-derived from their formulas, against what
    the balance implies. `kpis` is tab1_integration.compute_tab1_kpis(snapshot), passed in so this module stays Streamlit-free."""
    lhv_range = lhv_range or dokink_lhv_range()
    fe5 = _val(snapshot, ("FE-005", "MoistureBalance"))
    dry = float(fe5["dry_solids_kg_h"])
    h2_kg_h = float(_val(snapshot, ("HB-012", "Compressor"))["h2_kg_h"])
    n_h2 = h2_kg_h * 1000.0 / M_H2_ENGINE
    h2_kw_balance = _lhv_kw({"H2": n_h2})
    h2_kw_engine = n_h2 * NM3_PER_MOL * 10.8 / 3.6                    # EU-006 10.8 MJ/Nm3 (eu_utilities_chp.py:167), as tab1_integration.py:213
    feed_lo, feed_hi = dry * lhv_range[0] / 3.6, dry * lhv_range[1] / 3.6
    ov = kpis["overall_efficiency"]["value"]
    el_total = float(_val(snapshot, ("EU-009", "GridBalance"))["consumption_kw"]) + float(_val(snapshot, ("FE-004", "ShredderPower"))["power_kw"])
    ga = ga001_terms(snapshot, previous_snapshot)
    c_feed_mol = ga["feed_atoms"]["C"]
    x = ga["feed_atoms"]["H"] / c_feed_mol
    y = ga["feed_atoms"]["O"] / c_feed_mol
    h2_max_mol = c_feed_mol * (2.0 + x / 2.0 - y)                     # CHxOy + (2-y) H2O -> CO2 + (2 + x/2 - y) H2, complete conversion, unlimited steam
    h2_max_kg_h = h2_max_mol * M_H2_ENGINE / 1000.0
    return {
        "reported_overall_efficiency_pct_range": tuple(ov["h2_conversion_efficiency_range_pct"]),
        "reported_formula": "100 x H2 LHV (HB-012 h2_kg_h at 10.8 MJ/Nm3) / (FE-005 dry feed x 15..20 MJ/kg); feed energy is the ONLY denominator term (tab1_integration.py:213-233)",
        "re_derived_pct_range": (100.0 * h2_kw_engine / feed_hi, 100.0 * h2_kw_engine / feed_lo),
        "h2_kw_engine_basis": h2_kw_engine, "h2_kw_balance_basis": h2_kw_balance,
        "h2_lhv_basis_difference_pct": 100.0 * (h2_kw_engine - h2_kw_balance) / h2_kw_balance,
        "balance_implied_pct_range_feed_only": (100.0 * h2_kw_balance / feed_hi, 100.0 * h2_kw_balance / feed_lo),
        "balance_implied_pct_range_incl_electricity": (100.0 * h2_kw_balance / (feed_hi + el_total), 100.0 * h2_kw_balance / (feed_lo + el_total)),
        "electricity_counted_kw": el_total,
        "reported_h2_yield_kg_per_kg_dry": float(kpis["h2_yield_per_feed_mass"]["value"]),
        "h2_yield_formula": "HB-012 h2_kg_h / FE-005 dry_solids_kg_h (tab1_integration.py:266)",
        "h2_yield_stoichiometric_maximum_kg_per_kg_dry": h2_max_kg_h / dry,
        "h2_yield_fraction_of_maximum": h2_kg_h / h2_max_kg_h,
        "h2_yield_maximum_formula": "feed C x (2 + H/C/2 - O/C) mol H2 (complete steam reforming to CO2, unlimited steam), x 2.016 g/mol; N and ash ignored",
    }


# =============================================================================
# one call for everything
# =============================================================================

def audit_snapshot(snapshot, previous_snapshot=None, kpis=None):
    """All mass balances, the storage check and (when `kpis` is given) the energy balances for one published snapshot.
    `previous_snapshot` is the snapshot of the cycle before (needed for the lagged recycle; build_live_snapshot(n_cycles=N-1))."""
    out = {"missing_inputs": []}
    try:
        out["ga001"] = ga001_balance(snapshot, previous_snapshot)
        out["ga001_carbon"] = ga001_carbon_detail(snapshot, previous_snapshot)
        out["explain_carbon"] = explain_carbon_residual(snapshot, previous_snapshot)
        out["explain_plant_mass"] = explain_plant_mass_residual(snapshot, previous_snapshot)
        out["ga001_recycle_cross_check"] = ga001_recycle_cross_check(snapshot, previous_snapshot)
        out["loop"] = plant_balance(snapshot, previous_snapshot, "loop")
        out["plant"] = plant_balance(snapshot, previous_snapshot, "plant")
        out["clipped_surplus_kg_h"] = fe_clipped_surplus_kg_h(snapshot)
        out["storage"] = storage_inventory_check(snapshot, previous_snapshot)
    except AuditInputMissing as exc:
        out["missing_inputs"].append(exc.args[0])
    if kpis is not None and previous_snapshot is not None and not out["missing_inputs"]:
        try:
            out["energy_gasifier"] = {k: gasifier_energy(snapshot, previous_snapshot, v) for k, v in lhv_cases().items()}
            out["energy_plant"] = {k: plant_energy(snapshot, previous_snapshot, v) for k, v in lhv_cases().items()}
            out["efficiencies"] = efficiency_check(snapshot, previous_snapshot, kpis)
        except AuditInputMissing as exc:
            out["missing_inputs"].append(exc.args[0])
    return out
