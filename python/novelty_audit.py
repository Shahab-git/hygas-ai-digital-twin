"""
Novelty audit v1 — coverage, not a genuine novelty judgment.

HONEST SCOPING, stated explicitly here and in the app.py UI: code cannot
judge genuine engineering novelty — that needs real domain-expert
judgment against prior art (patents, published literature, competing
commercial designs), which this tool does not attempt and does not
claim to. What this DOES do: map the 8-lens framework (Design, Dynamics,
Math, Physics, Economics, Safety, Data & Control Intelligence,
Circularity) against what this repo can OBJECTIVELY VERIFY — which of
the 91 equipment registry items actually have real, working Python code
behind them in THIS codebase, and which don't yet.

A high coverage score means "this item has real modeled/validated work
behind it in this repo" — it does NOT mean "this item is more innovative"
in any absolute sense, and says nothing about the equipment's real-world
novelty. Real novelty analysis (the kind implied by the equipment
registry's own FE-001/FE-008-style engineering documentation) requires
actual domain-expert judgment against prior art, which is out of scope
for a Python script and always will be.

Three of the eight lenses currently have ZERO code coverage across all
91 items — an honest finding about this repo's current gaps, not a bug:
  - Design   — no code here analyzes equipment sizing/selection.
  - Dynamics — no code here models transient/time-domain behavior; every
    physics module in this repo is explicitly steady-state (see e.g.
    optimizer.py's and uncertainty.py's own scoping statements).
  - Safety   — no hazard/ATEX/explosion-protection analysis code exists,
    even though several datasheets (GA-008, GA-010, GC-010...) carry
    real ATEX parameters.

EVIDENCE_RECORDS below is built from what this repo's modules ACTUALLY
reference or compute for a given equipment ID — not a plausible-sounding
guess. Each record states its source module and the concrete reasoning
for why that module counts as evidence for that lens, for that specific
item. Judgment calls on lens assignment per module are stated inline.
"""
from . import equipment_registry

LENSES = [
    "Design", "Dynamics", "Math", "Physics", "Economics", "Safety",
    "Data & Control Intelligence", "Circularity",
]

_HTS_LTS = ["HB-001", "HB-002", "HB-004"]  # WGS Reactor HTS (Temp/CO Conv.), WGS Reactor LTS
_PSA = ["HB-006", "HB-007", "HB-008"]      # PSA Unit (H2 Purity/Recovery/Pressure)
_CHP = ["EU-001", "EU-002", "EU-003", "EU-004", "EU-005", "EU-006"]  # SOFC/Gas Engine/Microturbine/H2 FC
_BYPRODUCT = ["GA-005", "GA-008", "GA-009"]  # Bed Drain/Ash Discharge, Carbon Black Recovery, Ash Aggregate

EVIDENCE_RECORDS = [
    {
        "lens": "Math", "source": "python/kinetics.py", "equipment_ids": _HTS_LTS,
        "reasoning": "WGS reaction kinetics — Arrhenius/Van't Hoff ODE integration for the HTS and LTS stages.",
    },
    {
        "lens": "Physics", "source": "python/psa.py", "equipment_ids": _PSA,
        "reasoning": "PSA selectivity + pressure-ratio physical separation correlation.",
    },
    {
        "lens": "Physics", "source": "python/chp.py", "equipment_ids": _CHP,
        "reasoning": "Thermodynamic part-load efficiency curves (SOFC / Gas Engine / Microturbine / PEM Fuel Cell).",
    },
    {
        "lens": "Economics", "source": "python/dispatch_ga.py", "equipment_ids": _CHP,
        "reasoning": "Fuel-constrained genetic-algorithm dispatch optimisation across the CHP units.",
    },
    {
        "lens": "Data & Control Intelligence", "source": "python/dispatch_ga.py", "equipment_ids": _CHP,
        "reasoning": "The genetic-algorithm dispatch itself is an AI/heuristic control technique, distinct from the economic allocation it produces.",
    },
    {
        "lens": "Data & Control Intelligence", "source": "python/optimizer.py",
        "equipment_ids": _HTS_LTS + _PSA + ["AI-012"],
        "reasoning": "Central setpoint optimizer (scipy.optimize) over WGS/PSA operating points — this repo's 'MPC + RL, central optimiser' innovation, and AI-012's own equipment (AI Model Server, MPC/RL).",
    },
    {
        "lens": "Data & Control Intelligence", "source": "python/predictive_maintenance.py", "equipment_ids": _HTS_LTS,
        "reasoning": "Inverse-kinetics catalyst activity monitoring for the WGS reactors.",
    },
    {
        "lens": "Data & Control Intelligence", "source": "python/root_cause.py", "equipment_ids": _HTS_LTS,
        "reasoning": "Root-cause reasoning over predictive_maintenance.py's WGS reactor readings.",
    },
    {
        "lens": "Data & Control Intelligence", "source": "python/copilot.py", "equipment_ids": _HTS_LTS + _PSA + _CHP,
        "reasoning": "Rule-based operator copilot answers questions grounded directly in kinetics.py/psa.py/dispatch_ga.py for these exact subsystems.",
    },
    {
        "lens": "Data & Control Intelligence", "source": "python/multi_module_orchestration.py",
        "equipment_ids": _HTS_LTS + ["AI-014"],
        "reasoning": "Coordinates hypothetical parallel WGS-train modules toward a shared output target — AI-014's own equipment (Multi-Module Orchestration Controller).",
    },
    {
        "lens": "Data & Control Intelligence", "source": "python/multi_agent_negotiation.py", "equipment_ids": _CHP,
        "reasoning": "Merit-order negotiation over dispatch_ga.py CHP allocations across hypothetical plant variants.",
    },
    {
        "lens": "Data & Control Intelligence",
        "source": "python/compliance.py + python/regulatory_drafting.py + python/confirmation_loop.py",
        "equipment_ids": ["AI-015"],
        "reasoning": "RFNBO compliance checklist, draft generation, and design-assumption confirmation tracking — AI-015's own equipment (RFNBO Compliance & Guarantee-of-Origin Monitor).",
    },
    {
        "lens": "Circularity", "source": "python/gasifier_mass_balance.py + python/circularity.py",
        "equipment_ids": _BYPRODUCT,
        "reasoning": "Ash/carbon-black mass balance and diversion-from-landfill scoring, sourced from these items' own real datasheet design fractions (GA-005's stated 10% ash content; GA-008/GA-009's stated design capacities).",
    },
    {
        "lens": "Economics", "source": "python/circularity.py", "equipment_ids": _BYPRODUCT,
        "reasoning": "Byproduct revenue-potential estimate (assumption-based placeholder pricing, stated as such).",
    },
]


def _build_coverage_index():
    """equipment_id -> {lens -> [ {source, reasoning}, ... ]}"""
    index = {}
    for record in EVIDENCE_RECORDS:
        for eq_id in record["equipment_ids"]:
            index.setdefault(eq_id, {}).setdefault(record["lens"], []).append(
                {"source": record["source"], "reasoning": record["reasoning"]}
            )
    return index


def audit_item(equipment_id, coverage_index=None):
    coverage_index = coverage_index if coverage_index is not None else _build_coverage_index()
    lens_evidence = coverage_index.get(equipment_id, {})
    covered = [lens for lens in LENSES if lens in lens_evidence]
    return {
        "equipment_id": equipment_id,
        "lenses_covered": covered,
        "coverage_count": len(covered),
        "evidence": lens_evidence,
    }


def build_audit(registry=None):
    """Full audit across every item in the equipment registry (91 items)."""
    registry = registry if registry is not None else equipment_registry.load_registry()
    coverage_index = _build_coverage_index()
    return [audit_item(item["id"], coverage_index) for item in registry]


def summarize_audit(audit=None):
    audit = audit if audit is not None else build_audit()
    total = len(audit)
    items_with_coverage = sum(1 for a in audit if a["coverage_count"] > 0)
    lens_totals = {lens: sum(1 for a in audit if lens in a["lenses_covered"]) for lens in LENSES}
    return {
        "total_items": total,
        "items_with_coverage": items_with_coverage,
        "items_with_zero_coverage": total - items_with_coverage,
        "lens_totals": lens_totals,
    }


if __name__ == "__main__":
    audit = build_audit()
    summary = summarize_audit(audit)
    print(f"Total items: {summary['total_items']}")
    print(f"Items with >=1 lens covered: {summary['items_with_coverage']}")
    print(f"Items with zero coverage: {summary['items_with_zero_coverage']}")
    print("Per-lens totals:")
    for lens in LENSES:
        print(f"  {lens}: {summary['lens_totals'][lens]} item(s)")

    print()
    print("Items with the highest coverage:")
    for a in sorted(audit, key=lambda a: -a["coverage_count"])[:5]:
        print(f"  {a['equipment_id']}: {a['coverage_count']}/8 lenses — {', '.join(a['lenses_covered'])}")
