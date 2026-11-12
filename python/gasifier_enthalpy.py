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
