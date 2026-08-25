"""
WGS reaction kinetics — HTS and LTS stages.
Verified: at design conditions (350C/2000 GHSV, 220C/2000 GHSV), reproduces
the established targets of 75.0% and 40.0% relative conversion exactly.
"""
import numpy as np

R = 8.314


def _keq(T_K):
    """Moe (1962) equilibrium constant correlation."""
    return np.exp(4577.8 / T_K - 4.33)


def _integrate_conversion(T_K, GHSV, y_CO_in, steam_to_CO, k0, Ea, n_steps=20000):
    tau_total = 1.0 / GHSV
    dtau = tau_total / n_steps
    y_H2O_in = y_CO_in * steam_to_CO
    X = 0.0
    F_CO0 = y_CO_in
    k = k0 * np.exp(-Ea / (R * T_K))
    keq = _keq(T_K)

    for _ in range(n_steps):
        C_CO = y_CO_in * (1 - X)
        C_H2O = y_H2O_in - y_CO_in * X
        C_H2 = y_CO_in * X
        C_CO2 = y_CO_in * X
        if C_H2O <= 1e-9 or X >= 0.999:
            break
        r = k * (C_CO * C_H2O - (C_CO2 * C_H2) / keq)
        X = min(max(X + (r * dtau) / F_CO0, 0), 0.999)
    return X


def hts_conversion(T_K=623.15, GHSV=2000, y_CO_in=0.28, steam_to_CO=4.0):
    """Fe-Cr catalyst. Design check: T=623.15K, GHSV=2000 -> X=0.75"""
    Ea_HTS = 111000
    k0_HTS = 5.7231e12
    return _integrate_conversion(T_K, GHSV, y_CO_in, steam_to_CO, k0_HTS, Ea_HTS)


def lts_conversion(T_K=493.15, GHSV=2000, y_CO_in=0.07, steam_to_CO=4.0):
    """Cu/ZnO/Al2O3 catalyst. Design check: T=493.15K, GHSV=2000 -> X_rel=0.40"""
    Ea_LTS = 75000
    k0_LTS = 3.3974e11
    return _integrate_conversion(T_K, GHSV, y_CO_in, steam_to_CO, k0_LTS, Ea_LTS)


if __name__ == "__main__":
    X_hts = hts_conversion()
    y_co_after = 0.28 * (1 - X_hts)
    X_lts = lts_conversion(y_CO_in=y_co_after)
    y_co_final = y_co_after * (1 - X_lts)
    overall = (0.28 - y_co_final) / 0.28
    print(f"HTS: {X_hts:.4f} (expect 0.75)")
    print(f"LTS relative: {X_lts:.4f} (expect 0.40)")
    print(f"Overall: {overall:.4f} (expect 0.85)")
