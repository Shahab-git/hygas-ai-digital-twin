"""
RFNBO compliance documentation v2 — an OPTIONAL value-add pathway, NOT a
project requirement.

CORRECTED per DOK-ING's real, formal RFI response (data/dokink_rfi_answers.md,
RFI #14, received via Ankica Kovac — applied in python/design_basis.py's
rfnbo_requirement entry): "Not required — but increases hydrogen's
economic value/price if achieved." Earlier versions of this module (and
of the app.py UI, and this project's own top-line tagline) treated RFNBO
qualification as this project's implicit target/goal, organizing the
whole checklist around it as if it were something the plant NEEDED to
satisfy. That framing is now known to be wrong: DOK-ING's own answer is
explicit that RFNBO/green-hydrogen certification is entirely OPTIONAL —
pursued, if at all, because it increases the hydrogen's commercial value
and sale price, not because of any compliance obligation this project is
under. This module's checklist remains genuinely useful for exactly that
reason: an OPTIONAL certification-readiness tracker for a real economic
decision DOK-ING may choose to make, not a "must comply" tracker for an
obligation that doesn't exist. Nothing else about what this module DOES
changes because of this — the checklist's data, sourcing, and honesty
discipline are unaffected; only the FRAMING of why it exists is corrected.

HARD LIMITATION, stated explicitly here and in the app.py UI: this does
NOT perform actual legal RFNBO (Renewable Fuel of Non-Biological Origin)
certification. Real RFNBO certification requires an accredited
third-party auditor assessing the plant against the specific criteria in
EU Delegated Regulation (EU) 2023/1184 and the related methodology
regulation (EU) 2023/1185 — additionality and temporal/geographic
correlation for renewable electricity inputs, greenhouse-gas savings
thresholds, mass-balance chain-of-custody, and more. This repo cannot
implement that process or make that legal determination, and this module
makes no such claim. This limitation statement is unchanged by the
optionality correction above — it was already true regardless of whether
RFNBO qualification is required or optional.

What this module DOES do: organize the plant's ACTUAL data — validated
physics results, stated design assumptions with their real uncertainty
ranges, and what documentation genuinely does or doesn't exist yet — into
the checklist shape a real compliance review would start from. So a real
auditor's first questions get real, sourced answers (or an honest "not
yet documented"), never invented placeholder data.

Every checklist item carries one of four statuses:
  - "Evidenced"                          — backed by a real, validated
    number computed live from this repo's own physics functions.
  - "Confirmed"                          — a design assumption that
    confirmation_loop.py has recorded a real DOK-ING-confirmed range
    for (via uncertainty.set_confirmed()). Checked live against
    uncertainty.is_confirmed() — this status appears automatically the
    moment a confirmation is recorded, with no separate flag to update
    here.
  - "Assumption — pending confirmation"  — a stated design assumption
    with an explicit uncertainty range (from uncertainty.py), not yet
    confirmed by DOK-ING.
  - "Not yet documented"                 — genuinely absent from this
    repo. Reported honestly; nothing here is fabricated to fill the gap.

Everything numeric below is computed by calling kinetics.py/psa.py/
uncertainty.py directly at checklist-build time, not hardcoded — if
those modules' calibration or assumed ranges change, this checklist
reflects the change on the next call, with no separate copy to keep in
sync.
"""
from . import kinetics, psa, uncertainty

EVIDENCED = "Evidenced"
CONFIRMED = "Confirmed"
ASSUMPTION_PENDING = "Assumption — pending confirmation"
NOT_DOCUMENTED = "Not yet documented"


def _mass_energy_balance_items():
    """Live-computed conversion/recovery numbers — each a real function
    call against this repo's validated physics, not a hardcoded literal."""
    X_hts = kinetics.hts_conversion()
    X_lts = kinetics.lts_conversion()
    overall = 1 - (1 - X_hts) * (1 - kinetics.lts_conversion(y_CO_in=0.28 * (1 - X_hts)))
    recovery = psa.psa_recovery()

    return [
        {
            "category": "Mass/Energy Balance Traceability",
            "item": "HTS (high-temperature shift) conversion",
            "status": EVIDENCED,
            "value": f"{X_hts * 100:.1f}%",
            "source": "python/kinetics.py: hts_conversion() — Arrhenius/Van't Hoff kinetics, Fe-Cr catalyst",
            "notes": "Design check embedded in kinetics.py's own __main__ self-test.",
        },
        {
            "category": "Mass/Energy Balance Traceability",
            "item": "LTS (low-temperature shift) relative conversion",
            "status": EVIDENCED,
            "value": f"{X_lts * 100:.1f}%",
            "source": "python/kinetics.py: lts_conversion() — Cu/ZnO/Al2O3 catalyst",
            "notes": "Design check embedded in kinetics.py's own __main__ self-test.",
        },
        {
            "category": "Mass/Energy Balance Traceability",
            "item": "Overall WGS (water-gas shift) conversion",
            "status": EVIDENCED,
            "value": f"{overall * 100:.1f}%",
            "source": "python/kinetics.py: hts_conversion() + lts_conversion(), combined",
            "notes": "1 − (1 − X_HTS)(1 − X_LTS), computed live from both stages.",
        },
        {
            "category": "Mass/Energy Balance Traceability",
            "item": "PSA (pressure swing adsorption) H2 recovery",
            "status": EVIDENCED,
            "value": f"{recovery * 100:.1f}%",
            "source": "python/psa.py: psa_recovery() — selectivity + pressure-ratio correlation",
            "notes": "Explicitly a first-pass design heuristic (documented in psa.py), not a full multi-bed cycle simulation — stated there, repeated here.",
        },
    ]


def _design_basis_assumption_items():
    """Pulled directly from uncertainty.ASSUMPTIONS — the live source of
    truth for range/point values, not a copy. Status flips to CONFIRMED
    automatically the moment confirmation_loop.py records a confirmation
    (uncertainty.is_confirmed() is checked live, not cached)."""
    items = []
    for key, cfg in uncertainty.ASSUMPTIONS.items():
        lo, hi = uncertainty.bounds(key)
        confirmed = uncertainty.is_confirmed(key)
        if confirmed:
            status = CONFIRMED
            value_str = f"CONFIRMED range [{lo:.3g}, {hi:.3g}]"
            source = "python/uncertainty.py: ASSUMPTIONS (confirmed via python/confirmation_loop.py)"
        else:
            status = ASSUMPTION_PENDING
            value_str = f"point {cfg['point']:g}, range [{lo:.3g}, {hi:.3g}] (±{cfg['fraction']*100:.0f}%)"
            source = "python/uncertainty.py: ASSUMPTIONS"
        items.append({
            "category": "Design-Basis Assumptions",
            "item": cfg["label"],
            "status": status,
            "value": value_str,
            "source": source,
            "notes": (
                "Propagated into kinetics.py/psa.py's forward model via Monte Carlo — see Uncertainty Analysis."
                if cfg["wired_in"] else
                "NOT propagated into kinetics.py/psa.py — no catalyst-poisoning/corrosion model exists in this "
                "repo yet, so this range is defined and reported but has no quantitative pathway to any output."
            ),
        })
    return items


def _feedstock_traceability_items():
    """Checked honestly: nothing in this repo documents waste feedstock
    sourcing or composition as of this call. If that changes (a real
    feedstock spec, sourcing chain-of-custody doc, or composition
    analysis gets added to this repo), this item should be rewritten to
    cite it — not have placeholder data invented in the meantime."""
    return [{
        "category": "Feedstock Traceability",
        "item": "Waste feedstock sourcing and composition documentation",
        "status": NOT_DOCUMENTED,
        "value": None,
        "source": "— none found in this repo —",
        "notes": (
            "A real RFNBO/mass-balance audit needs: waste stream classification, sourcing chain-of-custody, "
            "and a composition analysis (feeding the gasifier model's own feed-composition assumptions). None "
            "of that exists in this repo yet. This is reported honestly rather than inventing placeholder "
            "feedstock data to make the checklist look more complete than it is."
        ),
    }]


def build_checklist():
    """Full compliance-documentation checklist, grouped by category.
    Every item is computed live at call time — see module docstring."""
    return (
        _mass_energy_balance_items()
        + _design_basis_assumption_items()
        + _feedstock_traceability_items()
    )


def summarize_checklist(checklist=None):
    """Counts by status, for a quick overview."""
    checklist = checklist if checklist is not None else build_checklist()
    counts = {EVIDENCED: 0, CONFIRMED: 0, ASSUMPTION_PENDING: 0, NOT_DOCUMENTED: 0}
    for item in checklist:
        counts[item["status"]] += 1
    return counts


if __name__ == "__main__":
    checklist = build_checklist()
    for item in checklist:
        value_str = f"  value={item['value']}" if item["value"] else ""
        print(f"[{item['status']}] {item['category']} — {item['item']}{value_str}")
        print(f"    source: {item['source']}")

    print()
    print("Summary:", summarize_checklist(checklist))
