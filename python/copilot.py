"""
Rule-based operator copilot — v1 ("walking, not running").

No LLM call, no API key. Matches a question against a small set of known
patterns (WGS kinetics, PSA recovery, CHP dispatch GA) and answers using
the actual current slider values and computed results passed in via
`state`, re-running the real physics functions for any "what if" question
rather than fabricating numbers. Anything outside these three topics gets
an honest "I don't cover that yet" instead of a guess.

`state` shape expected by `answer_question`:
{
    "hts": {"X": float, "T_C": float, "GHSV": float},
    "lts": {"X": float, "T_C": float, "GHSV": float, "y_CO_in": float},
    "overall": float,
    "psa": {"recovery": float, "p_high": float, "p_low": float,
            "y_co2": float, "y_ch4": float, "y_co": float, "y_n2": float},
    "dispatch": None | {"result": {unit_name: load_factor, ...},
                         "syngas_budget": float, "h2_budget": float},
}
"""
import re

from . import kinetics, psa, chp, dispatch_ga

_INCREASE_WORDS = ("increase", "increasing", "raise", "raising", "higher", "more", "up", "boost")
_DECREASE_WORDS = ("decrease", "decreasing", "lower", "lowering", "reduce", "reducing", "less", "down", "drop")


def _direction(q_lower):
    """Return +1 for an 'increase' question, -1 for 'decrease', 0 if neither is mentioned."""
    if any(w in q_lower for w in _INCREASE_WORDS):
        return 1
    if any(w in q_lower for w in _DECREASE_WORDS):
        return -1
    return 0


def _answer_kinetics(q_lower, state, stage):
    info = state["hts"] if stage == "HTS" else state["lts"]
    X, T_C, GHSV = info["X"], info["T_C"], info["GHSV"]
    target = 0.75 if stage == "HTS" else 0.40
    catalyst = "Fe-Cr" if stage == "HTS" else "Cu/ZnO/Al2O3"

    verdict = (
        "at the design target" if abs(X - target) < 0.005
        else "below the design target" if X < target
        else "above the design target"
    )
    base = (
        f"{stage} conversion is currently {X*100:.1f}% ({catalyst} catalyst), "
        f"{verdict} of {target*100:.0f}%, at T={T_C:.0f}°C and GHSV={GHSV:.0f} 1/h. "
        f"In this Arrhenius/Van't Hoff model, conversion rises with temperature "
        f"(faster reaction rate) and falls as GHSV increases (less residence time "
        f"per unit of catalyst)."
    )

    direction = _direction(q_lower)
    wants_temp = "temperature" in q_lower or "°c" in q_lower or " c " in q_lower
    wants_ghsv = "ghsv" in q_lower or "space velocity" in q_lower

    if direction and (wants_temp or wants_ghsv or not (wants_temp or wants_ghsv)):
        delta_T = 30 if direction == 1 else -30
        delta_G = 500 if direction == 1 else -500
        new_T_C, new_GHSV = T_C, GHSV
        changes = []
        if wants_ghsv and not wants_temp:
            new_GHSV = max(1000, min(4000, GHSV + delta_G))
            changes.append(f"GHSV {GHSV:.0f} -> {new_GHSV:.0f} 1/h")
        else:
            new_T_C = max(300, min(400, T_C + delta_T)) if stage == "HTS" else max(180, min(260, T_C + delta_T))
            changes.append(f"temperature {T_C:.0f}°C -> {new_T_C:.0f}°C")

        if stage == "HTS":
            new_X = kinetics.hts_conversion(T_K=new_T_C + 273.15, GHSV=new_GHSV)
        else:
            new_X = kinetics.lts_conversion(T_K=new_T_C + 273.15, GHSV=new_GHSV, y_CO_in=info["y_CO_in"])

        base += (
            f" If you {'increase' if direction == 1 else 'decrease'} {' and '.join(changes)}, "
            f"conversion moves from {X*100:.1f}% to {new_X*100:.1f}% "
            f"(recomputed with the actual {stage} kinetics function)."
        )

    return base


def _answer_psa(q_lower, state):
    p = state["psa"]
    recovery, p_high, p_low, y_co2 = p["recovery"], p["p_high"], p["p_low"], p["y_co2"]
    y_ch4 = p.get("y_ch4", 0.03)
    y_co = p.get("y_co", 0.042)
    y_n2 = p.get("y_n2", 0.028)

    verdict = (
        "at the design target" if abs(recovery - 0.75) < 0.005
        else "below the design target" if recovery < 0.75
        else "above the design target"
    )
    base = (
        f"PSA recovery is currently {recovery*100:.1f}%, {verdict} of 75.0%, "
        f"at an adsorption/purge pressure ratio of {p_high:.1f}/{p_low:.1f} bar(a) "
        f"and feed CO2 fraction {y_co2:.2f}. Recovery falls as the pressure ratio "
        f"drops (more gas lost in the purge step) and as the feed carries more "
        f"strongly-adsorbed impurities (CO2 especially — selectivity 250x vs H2)."
    )

    direction = _direction(q_lower)
    if direction and "pressure" in q_lower:
        if "purge" in q_lower or "low" in q_lower:
            delta = -0.5 if direction == 1 else 0.5  # raising purge pressure lowers the ratio
            new_p_low = max(0.5, min(3.0, p_low - delta))
            new_recovery = psa.psa_recovery(y_CO2=y_co2, y_CH4=y_ch4, y_CO=y_co, y_N2=y_n2,
                                             P_high_bar_a=p_high, P_low_bar_a=new_p_low)
            base += (
                f" If you {'increase' if direction == 1 else 'decrease'} purge pressure "
                f"({p_low:.1f} -> {new_p_low:.1f} bar(a)), recovery moves from "
                f"{recovery*100:.1f}% to {new_recovery*100:.1f}% "
                f"(recomputed with the actual PSA correlation)."
            )
        else:
            delta = 2.0 if direction == 1 else -2.0
            new_p_high = max(4.0, min(14.0, p_high + delta))
            new_recovery = psa.psa_recovery(y_CO2=y_co2, y_CH4=y_ch4, y_CO=y_co, y_N2=y_n2,
                                             P_high_bar_a=new_p_high, P_low_bar_a=p_low)
            base += (
                f" If you {'increase' if direction == 1 else 'decrease'} adsorption pressure "
                f"({p_high:.1f} -> {new_p_high:.1f} bar(a)), recovery moves from "
                f"{recovery*100:.1f}% to {new_recovery*100:.1f}% "
                f"(recomputed with the actual PSA correlation)."
            )

    return base


_UNIT_ALIASES = {
    "sofc": "SOFC",
    "gas engine": "Gas Engine",
    "microturbine": "Microturbine",
    "pem": "PEM Fuel Cell",
    "pem fuel cell": "PEM Fuel Cell",
    "fuel cell": "PEM Fuel Cell",
}


def _named_unit(q_lower):
    for alias, name in _UNIT_ALIASES.items():
        if alias in q_lower:
            return name
    return None


def _answer_dispatch(q_lower, state):
    dispatch = state.get("dispatch")
    if not dispatch:
        return (
            "You haven't run the dispatch optimisation yet this session — click "
            "'Run dispatch optimisation (genetic algorithm)' above, then ask me again "
            "and I can explain the result."
        )

    result = dispatch["result"]
    loads = {name: result.get(name, 0.0) for name in dispatch_ga.UNIT_NAMES}
    effs = {name: chp.chp_efficiency(loads[name], name) for name in dispatch_ga.UNIT_NAMES}
    rated = dispatch_ga.EFF
    syngas_budget = dispatch["syngas_budget"]
    h2_budget = dispatch["h2_budget"]

    syngas_used = sum(loads[n] * dispatch_ga.FUEL_KW_FULL[n]
                       for n in dispatch_ga.UNIT_NAMES if dispatch_ga.FUEL_TYPE[n] == "syngas")
    h2_used = sum(loads[n] * dispatch_ga.FUEL_KW_FULL[n]
                  for n in dispatch_ga.UNIT_NAMES if dispatch_ga.FUEL_TYPE[n] == "H2")

    unit = _named_unit(q_lower)
    if unit:
        others = [n for n in dispatch_ga.UNIT_NAMES if n != unit]
        least_efficient = min(dispatch_ga.UNIT_NAMES, key=lambda n: rated[n])
        return (
            f"{unit} was dispatched at {loads[unit]*100:.1f}% load "
            f"({effs[unit]*100:.1f}% efficiency at that load, {rated[unit]*100:.0f}% rated). "
            f"The GA maximises useful energy delivered per kW of fuel consumed, under separate "
            f"syngas ({syngas_used:.1f}/{syngas_budget:.0f} kW used) and H2 "
            f"({h2_used:.1f}/{h2_budget:.0f} kW used) budgets. {rated[least_efficient]*100:.0f}% "
            f"is the lowest rated efficiency of the four units — a unit that low-efficiency "
            f"burns more fuel budget per kW of useful output than "
            + ", ".join(f"{n} ({rated[n]*100:.0f}%)" for n in others)
            + f", so the GA gives it load only if fuel budget remains after the more efficient "
            f"units are satisfied."
        )

    summary = ", ".join(f"{n}: {loads[n]*100:.1f}% load ({effs[n]*100:.1f}% eff.)" for n in dispatch_ga.UNIT_NAMES)
    return (
        f"Last dispatch result — {summary}. Syngas used {syngas_used:.1f}/{syngas_budget:.0f} kW, "
        f"H2 used {h2_used:.1f}/{h2_budget:.0f} kW. The GA maximises useful energy per kW of fuel "
        f"under those two separate budgets, so it favours the highest-efficiency unit for each "
        f"fuel type first."
    )


def answer_question(question, state):
    """Rule-based Q&A. Returns None if the question doesn't match any known pattern."""
    q_lower = question.lower().strip()
    if not q_lower:
        return None

    if re.search(r"\bhts\b", q_lower) or "high-temperature shift" in q_lower or "high temperature shift" in q_lower:
        return _answer_kinetics(q_lower, state, "HTS")

    if re.search(r"\blts\b", q_lower) or "low-temperature shift" in q_lower or "low temperature shift" in q_lower:
        return _answer_kinetics(q_lower, state, "LTS")

    if any(w in q_lower for w in ("psa", "pressure swing", "h2 recovery", "hydrogen recovery")):
        return _answer_psa(q_lower, state)

    if (re.search(r"\bga\b", q_lower) or "genetic algorithm" in q_lower or "dispatch" in q_lower
            or _named_unit(q_lower)):
        return _answer_dispatch(q_lower, state)

    if any(w in q_lower for w in ("kinetics", "conversion", "shift reaction")) and "psa" not in q_lower:
        # Ambiguous between HTS/LTS with no stage named — default to HTS, the primary stage.
        return _answer_kinetics(q_lower, state, "HTS")

    return None


UNKNOWN_QUESTION_MESSAGE = (
    "I don't have a rule for that one yet. Right now I can only answer questions about: "
    "WGS kinetics (HTS/LTS conversion, temperature/GHSV effects), PSA hydrogen recovery "
    "(pressure/composition effects), and the CHP dispatch GA (which unit got how much load, "
    "and why). Try rephrasing around one of those."
)
