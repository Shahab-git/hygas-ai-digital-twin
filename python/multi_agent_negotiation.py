"""
Multi-agent negotiation v1.

HONEST SCOPING, stated explicitly: this repo represents exactly ONE real
plant. There is no real second or third facility, and no live inter-plant
data anywhere in this project. What this module does: define 2-3
HYPOTHETICAL variants of this plant's own dispatch parameters —
illustrative, not real separate facilities — and simulate them
negotiating over a shared, limited resource (grid export capacity) that
the combined fleet can't exceed even if each variant individually wants
more.

Negotiation mechanism: MERIT-ORDER allocation, not full iterative
bilateral negotiation. Chosen over the iterative alternative because it
is (a) simpler to reason about and verify exactly — one sort plus a
greedy fill, no convergence loop to prove terminates or is stable — and
(b) already grounded in how real grid operators allocate scarce
transmission/export capacity in practice: the most fuel-efficient
generation is dispatched first. This already differentiates allocations
by genuine efficiency (computed from this repo's own dispatch_ga.py
numbers), not an equal split or a raw-ask-size proportional split that
would ignore efficiency entirely — a plant with a more efficient dispatch
is never worse off than a less efficient one asking for the same amount.

Mechanism, step by step:
  1. Each hypothetical plant runs its OWN dispatch_ga.run_dispatch_ga()
     against its own (illustrative) fuel budgets — exactly the same
     optimization already used for the real plant's CHP Dispatch
     section, just called once per variant. This produces each plant's
     "ask": its fuel-optimal electrical export (kW) and the overall
     fuel-to-electricity efficiency of that dispatch.
  2. Plants are ranked by that efficiency, most efficient first.
  3. The shared grid export capacity is allocated greedily in that
     order: each plant gets min(its ask, capacity remaining), then the
     remaining capacity shrinks accordingly.

This guarantees sum(allocations) <= the shared capacity exactly, by
construction (a greedy fill against a hard cap), not by clipping an
already-decided allocation after the fact.
"""
from . import dispatch_ga

# Illustrative variants of THIS plant's own dispatch parameters, scaled
# +/-20% — NOT real separate facilities. Real value: syngas 60kW / H2 15kW
# (this repo's own CHP Dispatch section defaults).
DEFAULT_PLANT_VARIANTS = [
    {"name": "Plant A (this plant, current budgets)", "syngas_budget_kw": 60.0, "h2_budget_kw": 15.0},
    {"name": "Plant B (+20% feed rate, illustrative)", "syngas_budget_kw": 72.0, "h2_budget_kw": 18.0},
    {"name": "Plant C (−20% feed rate, illustrative)", "syngas_budget_kw": 48.0, "h2_budget_kw": 12.0},
]


def _plant_ask(variant, seed=42):
    """Runs this variant's own fuel-optimal dispatch_ga optimization —
    exactly the same function the real plant's CHP Dispatch section
    uses — and summarizes it as an electrical-export 'ask' plus the
    overall efficiency of that dispatch."""
    dispatch = dispatch_ga.run_dispatch_ga(variant["syngas_budget_kw"], variant["h2_budget_kw"], seed=seed)
    total_elec_kw = sum(load * dispatch_ga.ELEC_KW[name] for name, load in dispatch.items())
    total_fuel_kw = sum(load * dispatch_ga.FUEL_KW_FULL[name] for name, load in dispatch.items())
    efficiency = total_elec_kw / total_fuel_kw if total_fuel_kw > 0 else 0.0
    return {
        "name": variant["name"],
        "syngas_budget_kw": variant["syngas_budget_kw"],
        "h2_budget_kw": variant["h2_budget_kw"],
        "dispatch": dispatch,
        "ask_kw": total_elec_kw,
        "fuel_used_kw": total_fuel_kw,
        "efficiency": efficiency,
    }


def negotiate(shared_grid_capacity_kw, variants=None, seed=42):
    """Runs the full negotiation: each variant's individual optimization,
    then merit-order allocation against the shared constraint.

    variants: optional list of {"name", "syngas_budget_kw", "h2_budget_kw"}
    dicts — defaults to DEFAULT_PLANT_VARIANTS.

    Returns a dict: shared_capacity_kw, total_asked_kw, total_allocated_kw,
    merit_order (plant names, most efficient first), and plants (list of
    per-plant results in the ORIGINAL variant order, each with ask_kw,
    efficiency, allocation_kw, fully_served, merit_rank).
    """
    variants = variants if variants is not None else DEFAULT_PLANT_VARIANTS
    asks = [_plant_ask(v, seed=seed) for v in variants]

    ranked = sorted(asks, key=lambda a: a["efficiency"], reverse=True)

    remaining = shared_grid_capacity_kw
    for rank, plant in enumerate(ranked, start=1):
        allocation = min(plant["ask_kw"], remaining)
        remaining = max(0.0, remaining - allocation)
        plant["allocation_kw"] = allocation
        plant["fully_served"] = allocation >= plant["ask_kw"] - 1e-9
        plant["merit_rank"] = rank

    total_asked = sum(p["ask_kw"] for p in ranked)
    total_allocated = sum(p["allocation_kw"] for p in ranked)

    by_name = {p["name"]: p for p in ranked}
    plants_in_original_order = [by_name[v["name"]] for v in variants]

    return {
        "shared_capacity_kw": shared_grid_capacity_kw,
        "total_asked_kw": total_asked,
        "total_allocated_kw": total_allocated,
        "merit_order": [p["name"] for p in ranked],
        "plants": plants_in_original_order,
    }


if __name__ == "__main__":
    result = negotiate(shared_grid_capacity_kw=70.0)
    print(f"Shared grid export capacity: {result['shared_capacity_kw']:.2f} kW")
    print(f"Total asked: {result['total_asked_kw']:.2f} kW  |  Total allocated: {result['total_allocated_kw']:.2f} kW")
    print(f"Merit order (most efficient first): {result['merit_order']}")
    print()
    for p in result["plants"]:
        print(f"  {p['name']}")
        print(f"    budgets: syngas={p['syngas_budget_kw']:.0f}kW, H2={p['h2_budget_kw']:.0f}kW")
        print(f"    efficiency: {p['efficiency']*100:.2f}%  (merit rank #{p['merit_rank']})")
        print(f"    ask: {p['ask_kw']:.2f}kW  ->  allocated: {p['allocation_kw']:.2f}kW  "
              f"({'fully served' if p['fully_served'] else 'PARTIALLY served'})")

    assert abs(result["total_allocated_kw"] - result["shared_capacity_kw"]) < 1e-6, (
        "total allocation should exactly equal the shared capacity when demand exceeds supply"
    )
    print("\nPASS: total allocation exactly equals the shared constraint (demand exceeded supply).")
