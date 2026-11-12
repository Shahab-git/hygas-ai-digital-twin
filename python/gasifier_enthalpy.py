"""
Gasifier enthalpy diagnostic (task A4): a READ-ONLY residual of the gasifier's enthalpy balance at the imposed gas temperature, with the formation and the sensible parts reported separately.

NOT validation against DOK-ING data: none exists. Every number this module produces is the residual of a balance built from Assumed and Estimated inputs, not a prediction of the plant.
It solves no temperature, switches nothing and changes no value; nothing in the engine reads it.

Reference state (the ONE convention): T_ref = 298.15 K, p = 1 bar, ideal gas, elements in their standard states (C = graphite, H2, O2, N2 gas). The enthalpy of species i at T is
    H_i(T) = DHf_i + dHs_i(T),     dHs_i(T) = H_i(T) - H_i(298.15 K)
DHf_i: the standard formation enthalpy at 298.15 K, from balance_audit.HF_KJ_MOL (NIST-JANAF; the one table of the repo, none is added here). dHs_i(T): the sensible enthalpy, by exact integration of the
NASA 9-coefficient polynomials of B. J. McBride, M. J. Zehe, S. Gordon, "NASA Glenn Coefficients for Calculating Thermodynamic Properties of Individual Species", NASA/TP-2002-211556 (2002), stored as
DATA in data/thermo_nasa9.json (not as literals in code). The polynomial's own formation value is never used in a balance; it is only compared with the repo's value (a cross-check of two sources).
"""
import json
import math
import os

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
THERMO_PATH = os.path.join(_ROOT, "data", "thermo_nasa9.json")
SPECIES = ("H2", "CO", "CO2", "H2O", "CH4", "N2", "O2", "C")          # C = graphite
T_REF_K = 298.15
T_MIN_K, T_MAX_K = 200.0, 6000.0                                      # the data's range; outside it the module refuses (no extrapolation)

_CACHE = {}


def _fail(msg):
    raise ValueError(f"thermo data {THERMO_PATH}: {msg}")


def load_thermo(path=None):
    """Loads and validates data/thermo_nasa9.json: {"R": float, "species": {name: [(t_low, t_high, a[7], b[2]), ...]}, "meta": dict}. Fails loudly on a missing species, a malformed or non-contiguous
    interval set, a non-finite number or a range that does not cover 200-6000 K."""
    path = path or THERMO_PATH
    if path in _CACHE:
        return _CACHE[path]
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    meta = doc["_meta"]
    r = meta["R_j_mol_k"]
    if not isinstance(r, (int, float)) or isinstance(r, bool) or not math.isfinite(r) or r <= 0:
        _fail(f"R_j_mol_k {r!r} is not a positive number")
    if (meta["reference_temperature_k"], meta["t_min_k"], meta["t_max_k"]) != (T_REF_K, T_MIN_K, T_MAX_K):
        _fail("reference temperature / range of the file differ from the module's")
    species = {}
    for name in SPECIES:
        if name not in doc["species"]:
            raise LookupError(f"thermo data {path}: species {name!r} is missing (needed: {SPECIES})")
        ivs = []
        for iv in doc["species"][name]["intervals"]:
            nums = list(iv["a"]) + list(iv["b"]) + [iv["t_low_k"], iv["t_high_k"]]
            if len(iv["a"]) != 7 or len(iv["b"]) != 2 or not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in nums):
                _fail(f"{name}: an interval is not 7 + 2 finite coefficients and two finite limits")
            ivs.append((float(iv["t_low_k"]), float(iv["t_high_k"]), tuple(float(x) for x in iv["a"]), tuple(float(x) for x in iv["b"])))
        if not ivs or ivs[0][0] > T_MIN_K or ivs[-1][1] < T_MAX_K or any(ivs[k][1] != ivs[k + 1][0] for k in range(len(ivs) - 1)) or any(lo >= hi for lo, hi, _a, _b in ivs):
            _fail(f"{name}: the intervals are not contiguous or do not cover {T_MIN_K}-{T_MAX_K} K")
        species[name] = tuple(ivs)
    out = {"R": float(r), "species": species, "meta": meta, "raw": doc}
    _CACHE[path] = out
    return out


def _check_t(T_K):
    if isinstance(T_K, bool) or not isinstance(T_K, (int, float)) or not math.isfinite(T_K):
        raise ValueError(f"temperature {T_K!r} is not a finite number")
    if not T_MIN_K <= T_K <= T_MAX_K:
        raise ValueError(f"temperature {T_K} K is outside the data range {T_MIN_K}-{T_MAX_K} K: refusing to extrapolate")
    return float(T_K)


def _interval(species, T_K, thermo=None):
    thermo = thermo or load_thermo()
    if species not in thermo["species"]:
        raise LookupError(f"no thermo data for species {species!r} (have {SPECIES})")
    ivs = thermo["species"][species]
    for lo, hi, a, b in ivs:
        if lo <= T_K < hi:
            return a, b
    return ivs[-1][2], ivs[-1][3]            # T == t_max: the last interval is closed


def cp_j_mol_k(species, T_K, thermo=None):
    """Heat capacity at constant pressure, J/(mol K), NASA-9: Cp/R = a1 T^-2 + a2 T^-1 + a3 + a4 T + a5 T^2 + a6 T^3 + a7 T^4."""
    T = _check_t(T_K)
    thermo = thermo or load_thermo()
    a, _b = _interval(species, T, thermo)
    return thermo["R"] * (a[0] / T**2 + a[1] / T + a[2] + a[3] * T + a[4] * T**2 + a[5] * T**3 + a[6] * T**4)


def polynomial_enthalpy_j_mol(species, T_K, thermo=None):
    """The NASA polynomial's TOTAL enthalpy H(T), J/mol (its own formation value included): H/RT = -a1 T^-2 + a2 ln(T)/T + a3 + a4 T/2 + a5 T^2/3 + a6 T^3/4 + a7 T^4/5 + b1/T.
    Used only for the cross-checks and as the building block of sensible_enthalpy_j_mol; never as a balance term."""
    T = _check_t(T_K)
    thermo = thermo or load_thermo()
    a, b = _interval(species, T, thermo)
    return thermo["R"] * T * (-a[0] / T**2 + a[1] * math.log(T) / T + a[2] + a[3] * T / 2 + a[4] * T**2 / 3 + a[5] * T**3 / 4 + a[6] * T**4 / 5 + b[0] / T)


def sensible_enthalpy_j_mol(species, T_K, thermo=None):
    """dHs(T) = H(T) - H(298.15 K), J/mol, by exact integration of the polynomial (no mean cp). Zero at 298.15 K by construction. Raises ValueError outside 200-6000 K, LookupError for an unknown species."""
    thermo = thermo or load_thermo()
    return polynomial_enthalpy_j_mol(species, T_K, thermo) - polynomial_enthalpy_j_mol(species, T_REF_K, thermo)


# ---------------------------------------------------------------------------------------------------------------------------------------------
# A4.2: the enthalpy of every GA-001 stream, formation and sensible parts separately (READ-ONLY; nothing here is imported by the engine)
# ---------------------------------------------------------------------------------------------------------------------------------------------
# Convention (the ONE of this module): H = formation + sensible, in kW (= kJ/h / 3600), relative to the elements at 298.15 K.
#   gas species : n_i x (DHf_i + dHs_i(T))          DHf from balance_audit.HF_KJ_MOL, dHs by NASA-9 (A4.1). H2O(g) uses DHf(H2O_g); the residual moisture is liquid water at 25 degC (DHf(H2O_l)).
#   graphite    : n x dHs_C(T)                      (DHf = 0)
#   dry feed    : DHf_feed = [n_C x DHf(CO2) + n_H/2 x DHf(H2O_g)] + m_dry x LHV   (complete combustion to CO2(g) + H2O(g) RELEASES the LHV of the dry feed incl. ash, so the reactants sit higher than the products by
#                 exactly that; O, N and ash carry no formation term in that reaction). Its sensible part is 0: the feed temperature after the dryer is not stated (Missing), as in balance_audit.gasifier_energy.
#   ash         : formation 0 (inert), sensible m x cp x (T - 25 degC) with the SAME Assumed solids cp as balance_audit (1.0 kJ/kg.K; no solids cp exists in the repo).
# Stream temperatures are the ones balance_audit uses: air/oxidant 200 degC and steam 350 degC (GA-004 registry values, Unverified (registry)), tail-gas recycle and moisture 25 degC, product gas and
# solids at GA-001's operating temperature (registry 950 degC, Assumed). Status of each row follows its inputs (Assumed / Estimated / Calculated); this is NOT a plant prediction and NOT validation.
# SIMPLIFICATION: NASA-9 sensible enthalpy replaces the repo's constant mean cp for GAS streams only; the solids keep the Assumed mean cp. The residual of the balance is task A4.3, not computed here.
_KW_PER_KJ_H = 1.0 / 3600.0


def _species_kw(species_mol_h, t_c, hf_key=None):
    """(formation_kw, sensible_kw) of a {species: mol/h} gas stream at t_c degC. `hf_key` renames a species for the formation table (H2O -> 'H2O_g' by default; 'H2O_l' for liquid water)."""
    from . import balance_audit as ba
    t_k = t_c + 273.15
    hf = sens = 0.0
    for sp, n in species_mol_h.items():
        key = hf_key.get(sp, sp) if hf_key else ("H2O_g" if sp == "H2O" else sp)
        hf += n * ba.HF_KJ_MOL[key]
        sens += n * sensible_enthalpy_j_mol(sp, t_k) / 1000.0
    return hf * _KW_PER_KJ_H, sens * _KW_PER_KJ_H


def feed_formation_kw(c_mol_h, h_mol_h, dry_feed_kg_h, lhv_mj_kg):
    """Formation enthalpy flow (kW) of the dry feed, DERIVED from its LHV: products' formation PLUS the heat released on complete combustion (see the convention above)."""
    from . import balance_audit as ba
    products_kj_h = c_mol_h * ba.HF_KJ_MOL["CO2"] + 0.5 * h_mol_h * ba.HF_KJ_MOL["H2O_g"]
    return products_kj_h * _KW_PER_KJ_H + dry_feed_kg_h * lhv_mj_kg / 3.6


def stream_enthalpies(snapshot, previous_snapshot, lhv_mj_kg):
    """Every GA-001 inlet and outlet stream of one published snapshot as {name, formation_kw, sensible_kw, total_kw, t_c, status, source}, plus the totals. Reads the SAME terms and flows as
    balance_audit.gasifier_energy (ga001_terms, so the recycle is an external feed). READ-ONLY: it returns numbers and changes nothing. Raises balance_audit.AuditInputMissing when the recycle
    needs the previous snapshot and it was not supplied (same rule as gasifier_energy)."""
    from . import balance_audit as ba
    from . import ga001_gasifier_model as ga001
    from . import plant_status as ps
    ga = ba.ga001_terms(snapshot, previous_snapshot)
    if ga["recycle"] is None:
        raise ba.AuditInputMissing(("HB-009", "TailGas (previous cycle)"))
    inp = ga["inputs"]
    f = inp["dry_feed_rate_kg_h"]
    t_gas = float(inp["operating_temperature_C"])
    by = {t["name"]: t for t in ga["terms"]}
    gas = by["product gas (wet)"]["species"]
    c_in = ga["feed_atoms"]["C"] + ga["recycle_atoms"]["C"]
    c_solid = c_in - (gas["CO"] + gas["CO2"] + gas["CH4"])                           # mol/h graphite not in the gas (the model's implied unconverted carbon)
    kg_ash = ga001.ASH_FRACTION * f
    cp_s = ba.SOLIDS_CP_KJ_KGK[0]

    def row(name, hf, sens, t_c, status, source):
        return {"name": name, "formation_kw": hf, "sensible_kw": sens, "total_kw": hf + sens, "t_c": t_c, "status": status, "source": source}

    o2_name, n2_name = ga["oxidant_names"]
    ox_hf, ox_s = _species_kw({"O2": ga["air_o2_mol_h"], "N2": ga["air_n2_mol_h"]}, ba.GA004_AIR_PREHEAT_C)
    st_hf, st_s = _species_kw(by["gasifier steam"]["species"], ba.GA004_STEAM_C)
    mo_hf, mo_s = _species_kw(by["residual moisture in dry feed"]["species"], ba.T_REF_C, {"H2O": "H2O_l"})
    rc_hf, rc_s = _species_kw(ga["recycle"], ba.T_REF_C)
    ins = [
        row("dry feed (formation derived from LHV)", feed_formation_kw(ga["feed_atoms"]["C"], ga["feed_atoms"]["H"], f, lhv_mj_kg), 0.0, None, ps.STATUS_ASSUMED,
            "composition Assumed, LHV a case in DOK-ING's 15-20 MJ/kg range; feed temperature Missing (sensible taken as 0)"),
        row("residual moisture (liquid water, 25 degC)", mo_hf, mo_s, ba.T_REF_C, ps.STATUS_CALCULATED, "FE-005 residual_water_kg_h"),
        row(f"{o2_name} + {n2_name}", ox_hf, ox_s, ba.GA004_AIR_PREHEAT_C, ps.STATUS_ESTIMATED, "GA-004 preheat temperature (registry, Unverified); for a non-air agent the same temperature is applied and FLAGGED in balance_audit"),
        row("gasifier steam (350 degC vapour)", st_hf, st_s, ba.GA004_STEAM_C, ps.STATUS_ESTIMATED, "GA-004 steam temperature (registry, Unverified)"),
        row("tail-gas recycle (H2, CO, CH4 at 25 degC)", rc_hf, rc_s, ba.T_REF_C, ps.STATUS_CALCULATED, "previous cycle HB-009 tail gas; recycle temperature Assumed 25 degC"),
    ]
    g_hf, g_s = _species_kw(gas, t_gas)
    c_s = c_solid * sensible_enthalpy_j_mol("C", t_gas + 273.15) / 1000.0 * _KW_PER_KJ_H
    outs = [
        row("product gas (wet) at the operating temperature", g_hf, g_s, t_gas, ps.STATUS_CALCULATED, "GA-001 Outputs x NASA-9 sensible enthalpy; T = GA-001-INPUT operating_temperature_C (Assumed 950)"),
        row("carbon not in the gas (graphite)", 0.0, c_s, t_gas, ps.STATUS_CALCULATED, "total C - C in gas; at the operating temperature (NASA-9 graphite)"),
        row("ash", 0.0, kg_ash * cp_s * (t_gas - ba.T_REF_C) * _KW_PER_KJ_H, t_gas, ps.STATUS_ASSUMED, f"cp {cp_s} kJ/kg.K Assumed (balance_audit.SOLIDS_CP_KJ_KGK); no solids cp in the repo"),
    ]
    tot = lambda rows, k: sum(r[k] for r in rows)
    return {"lhv_mj_kg": lhv_mj_kg, "t_gas_c": t_gas, "in": ins, "out": outs, "missing_terms": ["tar (GA-001 tar Missing)", "heat loss through the refractory and shell (no loss model)", "feed and recycle sensible heat (temperatures not stated)"],
            "totals": {"in": {k: tot(ins, k) for k in ("formation_kw", "sensible_kw", "total_kw")}, "out": {k: tot(outs, k) for k in ("formation_kw", "sensible_kw", "total_kw")}},
            "status": "Calculated, read-only, not part of the engine; NOT validation against DOK-ING data"}


# ---------------------------------------------------------------------------------------------------------------------------------------------
# A4.3: the residual of the enthalpy balance at the imposed temperature, reconciled with the existing implied heat duty (READ-ONLY)
# ---------------------------------------------------------------------------------------------------------------------------------------------
# residual Q = H_out - H_in (kW) from the A4.2 stream table: the heat the gasifier would have to ADD (+) or REMOVE (-) to leave at its imposed temperature. GA-001 itself computes no heat duty, so this is
# a diagnostic of the balance built from Assumed and Estimated inputs: NOT a plant prediction, NOT validation against DOK-ING data. Tar, shell/refractory loss and feed/recycle sensible heat are Missing and are
# NOT in it (they are listed, never zero).
# RECONCILIATION with balance_audit.gasifier_energy (the number published as (GA-001, EnergyBalance).implied_gasifier_heat_duty_kw): the two routes use the SAME formation data, so the FORMATION parts agree exactly
# (the A4.2 test proves it). They differ only in how the SENSIBLE parts are built, and that difference splits exactly into four terms, one per stream whose sensible heat the routes compute differently:
#     Q_nasa - Q_audit = d_gas + d_graphite - d_oxidant - d_steam
#   d_gas      = product-gas sensible heat, NASA-9 minus the audit's constant mean cp (300-1200 K, applied from 25 degC)
#   d_graphite = carbon not in the gas, NASA-9 graphite minus the audit's Assumed solids cp (1.0 kJ/kg.K)
#   d_oxidant  = air (or oxidant) sensible heat at the GA-004 preheat temperature, NASA-9 minus the audit's mean cp
#   d_steam    = gasifier steam sensible heat at the GA-004 steam temperature, NASA-9 minus the audit's mean cp
# The ash, the moisture, the feed and the recycle are computed the same way in both (ash: the same Assumed cp; the others are 0 sensible). The identity is exact to round-off, so nothing is left unexplained.
def enthalpy_residual(snapshot, previous_snapshot, lhv_mj_kg):
    """{'residual_kw', 'formation_kw', 'sensible_kw', 'audit_implied_duty_kw', 'difference_kw', 'difference_terms': {...}, 'difference_unexplained_kw', 'residual_pct_of_feed_chemical_energy', 'reading',
    'streams': stream_enthalpies(...), 'missing_terms', 'status'} for one published snapshot and one LHV case. READ-ONLY."""
    from . import balance_audit as ba
    from . import ga001_gasifier_model as ga001
    st = stream_enthalpies(snapshot, previous_snapshot, lhv_mj_kg)
    audit = ba.gasifier_energy(snapshot, previous_snapshot, lhv_mj_kg)
    ga = ba.ga001_terms(snapshot, previous_snapshot)
    by = {t["name"]: t for t in ga["terms"]}
    gas = by["product gas (wet)"]["species"]
    t_gas = st["t_gas_c"]
    f = ga["inputs"]["dry_feed_rate_kg_h"]
    c_solid = ga["feed_atoms"]["C"] + ga["recycle_atoms"]["C"] - (gas["CO"] + gas["CO2"] + gas["CH4"])
    kg_c = c_solid * ba.ATOMIC_MASS["C"] / 1000.0
    cp_s = ba.SOLIDS_CP_KJ_KGK[0]
    rows_in = {r["name"]: r for r in st["in"]}
    rows_out = {r["name"]: r for r in st["out"]}
    d_gas = rows_out["product gas (wet) at the operating temperature"]["sensible_kw"] - ba._sens_kw(gas, t_gas)
    d_graphite = rows_out["carbon not in the gas (graphite)"]["sensible_kw"] - kg_c * cp_s * (t_gas - ba.T_REF_C) * _KW_PER_KJ_H
    ox_name = [n for n in rows_in if n.startswith(("air O2", "oxidant O2"))][0]
    d_ox = rows_in[ox_name]["sensible_kw"] - ba._sens_kw({"O2": ga["air_o2_mol_h"], "N2": ga["air_n2_mol_h"]}, ba.GA004_AIR_PREHEAT_C)
    d_steam = rows_in["gasifier steam (350 degC vapour)"]["sensible_kw"] - ba._sens_kw({"H2O": by["gasifier steam"]["species"]["H2O"]}, ba.GA004_STEAM_C)
    q = st["totals"]["out"]["total_kw"] - st["totals"]["in"]["total_kw"]
    q_audit = audit["implied_heat_duty_kw"]
    diff = q - q_audit
    explained = d_gas + d_graphite - d_ox - d_steam
    feed_chem = f * lhv_mj_kg / 3.6
    return {"lhv_mj_kg": lhv_mj_kg, "t_gas_c": t_gas, "residual_kw": q,
            "formation_kw": st["totals"]["out"]["formation_kw"] - st["totals"]["in"]["formation_kw"], "sensible_kw": st["totals"]["out"]["sensible_kw"] - st["totals"]["in"]["sensible_kw"],
            "audit_implied_duty_kw": q_audit, "difference_kw": diff,
            "difference_terms": {"d_gas_kw": d_gas, "d_graphite_kw": d_graphite, "d_oxidant_kw": d_ox, "d_steam_kw": d_steam}, "difference_unexplained_kw": diff - explained,
            "residual_pct_of_feed_chemical_energy": 100.0 * q / feed_chem,
            "reading": "the gasifier would need to ADD heat" if q > 0 else "the gasifier would have to REMOVE heat",
            "streams": st, "missing_terms": st["missing_terms"],
            "status": "Calculated, read-only, not part of the engine; NOT validation against DOK-ING data"}


def enthalpy_residual_cases(snapshot, previous_snapshot):
    """enthalpy_residual at every LHV case of balance_audit.lhv_cases() (DOK-ING's 15 and 20 MJ/kg, the 17.5 midpoint and the model composition's correlation estimate)."""
    from . import balance_audit as ba
    return {name: enthalpy_residual(snapshot, previous_snapshot, lhv) for name, lhv in ba.lhv_cases().items()}


# ---------------------------------------------------------------------------------------------------------------------------------------------
# A4.4: the sensitivity of the residual to the imposed gas temperature (READ-ONLY)
# ---------------------------------------------------------------------------------------------------------------------------------------------
# Input: {T_gas_c: (snapshot, previous_snapshot)}, one pair per temperature, each built by the UNCHANGED engine with ("GA-001-INPUT", "operating_temperature_C") set to that temperature (the caller does this; see
# scripts/run_enthalpy_temperature_sensitivity.py). So the composition changes exactly as the engine lets it (the temperature enters GA-001 only through the water-gas-shift equilibrium constant: no energy balance,
# carbon conversion fixed), and the residual follows from the A4.3 function on each pair. NOTHING is solved or switched: this is a table of what the existing balance gives at each imposed temperature, NOT a
# prediction of the temperature the plant would settle at, and NOT validation against DOK-ING data. The 950 degC point is a registry value tied to earlier project models, not stated by DOK-ING (Assumed).
def temperature_sensitivity(by_temperature, lhv_mj_kg):
    """Rows sorted by temperature: {t_c, residual_kw, formation_kw, sensible_kw, audit_implied_duty_kw, difference_unexplained_kw, h2_mol_pct_dry, dry_flow_nm3_h} plus, per consecutive pair,
    the change in the residual per 100 K ('slope_kw_per_100k', None for the first row). Raises ValueError when a snapshot's imposed temperature is not the key it was given under or fewer than two
    temperatures are supplied."""
    if len(by_temperature) < 2:
        raise ValueError("a sensitivity needs at least two temperatures")
    rows = []
    for t_c in sorted(by_temperature):
        snap, prev = by_temperature[t_c]
        imposed = float(snap[("GA-001-INPUT", "operating_temperature_C")]["value"])
        if abs(imposed - float(t_c)) > 1e-9:
            raise ValueError(f"the snapshot given for {t_c} degC was built at {imposed} degC")
        r = enthalpy_residual(snap, prev, lhv_mj_kg)
        out = snap[("GA-001", "Outputs")]["value"]
        rows.append({"t_c": float(t_c), "residual_kw": r["residual_kw"], "formation_kw": r["formation_kw"], "sensible_kw": r["sensible_kw"],
                     "audit_implied_duty_kw": r["audit_implied_duty_kw"], "difference_unexplained_kw": r["difference_unexplained_kw"],
                     "h2_mol_pct_dry": float(out["H2_mol_pct_dry"]), "dry_flow_nm3_h": float(out["dry_flow_nm3_h"]), "slope_kw_per_100k": None})
    for a, b in zip(rows, rows[1:]):
        b["slope_kw_per_100k"] = 100.0 * (b["residual_kw"] - a["residual_kw"]) / (b["t_c"] - a["t_c"])
    return rows
