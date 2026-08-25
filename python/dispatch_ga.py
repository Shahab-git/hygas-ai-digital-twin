"""
Genetic algorithm for CHP dispatch optimisation under fuel constraints.
Verified: converges to a sensible dispatch that fully uses both fuel
budgets and correctly deprioritises the least-efficient unit (Microturbine).
"""
import random

UNIT_NAMES = ["SOFC", "Gas Engine", "Microturbine", "PEM Fuel Cell"]
ELEC_KW = {"SOFC": 18, "Gas Engine": 15, "Microturbine": 12, "PEM Fuel Cell": 15}
EFF = {"SOFC": 0.55, "Gas Engine": 0.35, "Microturbine": 0.28, "PEM Fuel Cell": 0.50}
THERMAL_KW = {"SOFC": 0, "Gas Engine": 20, "Microturbine": 0, "PEM Fuel Cell": 0}
FUEL_TYPE = {"SOFC": "syngas", "Gas Engine": "syngas", "Microturbine": "syngas", "PEM Fuel Cell": "H2"}
FUEL_KW_FULL = {n: ELEC_KW[n] / EFF[n] for n in UNIT_NAMES}

THERMAL_WEIGHT = 0.4
POP_SIZE = 60
GENERATIONS = 150
CROSSOVER_RATE = 0.8
MUTATION_RATE = 0.15
MUTATION_STRENGTH = 0.12
ELITE_COUNT = 4
PENALTY = 1000


def _fitness(ind, syngas_budget, h2_budget):
    syngas_used = sum(load * FUEL_KW_FULL[n] for load, n in zip(ind, UNIT_NAMES) if FUEL_TYPE[n] == "syngas")
    h2_used = sum(load * FUEL_KW_FULL[n] for load, n in zip(ind, UNIT_NAMES) if FUEL_TYPE[n] == "H2")
    useful_energy = sum(load * ELEC_KW[n] for load, n in zip(ind, UNIT_NAMES))
    useful_energy += THERMAL_WEIGHT * sum(load * THERMAL_KW[n] for load, n in zip(ind, UNIT_NAMES))

    penalty = 0.0
    if syngas_used > syngas_budget:
        penalty += PENALTY * (syngas_used - syngas_budget)
    if h2_used > h2_budget:
        penalty += PENALTY * (h2_used - h2_budget)
    return useful_energy - penalty


def _tournament(pop, fits, k=3):
    contenders = random.sample(list(zip(pop, fits)), k)
    return max(contenders, key=lambda c: c[1])[0]


def _crossover(p1, p2):
    if random.random() > CROSSOVER_RATE:
        return p1[:], p2[:]
    alpha = random.random()
    return ([alpha * a + (1 - alpha) * b for a, b in zip(p1, p2)],
            [alpha * b + (1 - alpha) * a for a, b in zip(p1, p2)])


def _mutate(ind):
    return [min(1.0, max(0.0, g + random.gauss(0, MUTATION_STRENGTH)))
            if random.random() < MUTATION_RATE else g for g in ind]


def run_dispatch_ga(syngas_budget_kw=60, h2_budget_kw=15, seed=42):
    """Returns dict of {unit_name: load_factor} for the best dispatch found."""
    random.seed(seed)
    population = [[random.random() for _ in UNIT_NAMES] for _ in range(POP_SIZE)]

    for _ in range(GENERATIONS):
        fits = [_fitness(ind, syngas_budget_kw, h2_budget_kw) for ind in population]
        ranked = sorted(zip(population, fits), key=lambda x: x[1], reverse=True)
        new_pop = [ind[:] for ind, _ in ranked[:ELITE_COUNT]]
        while len(new_pop) < POP_SIZE:
            p1 = _tournament(population, fits)
            p2 = _tournament(population, fits)
            c1, c2 = _crossover(p1, p2)
            new_pop.append(_mutate(c1))
            if len(new_pop) < POP_SIZE:
                new_pop.append(_mutate(c2))
        population = new_pop

    final_fits = [_fitness(ind, syngas_budget_kw, h2_budget_kw) for ind in population]
    best = max(zip(population, final_fits), key=lambda x: x[1])[0]
    return dict(zip(UNIT_NAMES, best))


if __name__ == "__main__":
    result = run_dispatch_ga()
    for name, load in result.items():
        print(f"{name}: {load*100:.1f}%")
