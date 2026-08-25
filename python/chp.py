"""
CHP part-load efficiency curves for the 4 technologies.
Verified: at load_factor=1.0, each curve reduces exactly to its rated
efficiency (SOFC 55%, Gas Engine 35%, Microturbine 28%, PEM 50%).
"""

UNIT_TYPES = {
    "SOFC": 1,
    "Gas Engine": 2,
    "Microturbine": 3,
    "PEM Fuel Cell": 4,
}
RATED_EFFICIENCY = {
    "SOFC": 0.55,
    "Gas Engine": 0.35,
    "Microturbine": 0.28,
    "PEM Fuel Cell": 0.50,
}


def chp_efficiency(load_factor, unit_name):
    x = min(max(load_factor, 0.01), 1.0)
    eta_rated = RATED_EFFICIENCY[unit_name]

    if unit_name == "SOFC":
        eta = eta_rated * (1 + 0.06 * (1 - x) - 0.35 * (1 - x) ** 2)
    elif unit_name == "Gas Engine":
        eta = eta_rated * (1 - 0.30 * (1 - x) ** 1.5)
    elif unit_name == "Microturbine":
        eta = eta_rated * (1 - 0.55 * (1 - x) ** 2)
    elif unit_name == "PEM Fuel Cell":
        eta = eta_rated * (1 + 0.03 * (1 - x) - 0.40 * (1 - x) ** 2)
    else:
        eta = eta_rated

    return max(eta, 0.01)


if __name__ == "__main__":
    for name in UNIT_TYPES:
        eta = chp_efficiency(1.0, name)
        print(f"{name}: eta(1.0)={eta:.4f} (expect {RATED_EFFICIENCY[name]})")
