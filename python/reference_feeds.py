"""
Reference feed analyses (task 2 of 3) -- pure data and small helpers, READ-ONLY, not used by the engine.

Published analyses of plastics, textiles, an RDF and two sewage sludges, recorded next to the model so the heat balance and the hydrogen yield can be
compared across feeds (scripts/run_feed_comparison.py). Every stored figure was read by the project owner on the cited page and is reproduced as stated:
nothing was added from memory and no paper was fetched. This module imports nothing from the project (tests enforce it) and nothing reads it.

STATUS. Stored analyses: "Assumed (literature-informed)" -- values from other plants / studies, not DOK-ING's, not Confirmed, not Measured.
Anything derived by arithmetic in this module (daf -> dry, stoichiometric polymer composition, LHV from HHV, the illustrative blend) is "Calculated",
with the formula and the named constants. Sources that were not opened or not readable are "Missing" and carry a NOT VERIFIED note.

Basis words: "daf" = dry ash-free, "d" = dry (ash included), "ad" = air-dry, "ar" = as received.
"""

STATUS_ASSUMED = "Assumed (literature-informed)"
STATUS_CALCULATED = "Calculated"
STATUS_MISSING = "Missing"

# Named constants of the arithmetic (standard values)
LATENT_HEAT_WATER_MJ_KG = 2.442      # latent heat of water at 25 degC (MJ/kg); LHV = HHV - 2.442 x (mass of water formed per kg) with 9 kg water per kg H
KJ_PER_KCAL = 4.184                  # thermochemical calorie
ATOMIC_MASS = {"C": 12.011, "H": 1.008, "O": 16.00, "N": 14.007, "Cl": 35.45}      # g/mol (the same C/H/O/N values the engine uses; checked by a test)

_ZHOU = ("Zhou et al., J. Air & Waste Manage. Assoc. 64(5), 2014, 597-616 (literature means across the studies it cites)", "https://www.awma.org/files/2020Stern.pdf")
_OTHER = "literature-informed Assumed: another plant / study, not DOK-ING's, not validated for GA-001."


def _entry(key, material, basis, values, source, not_stated, caveat, status=STATUS_ASSUMED):
    title, url = source
    return {"key": key, "material": material, "basis": basis, "values": values, "source_title": title, "source_url": url,
            "what_the_page_does_not_state": not_stated, "status": status, "caveat": caveat}


def _plastic(key, name, ad, c, h, o, n, hhv, cl=None):
    v = {"Ad_pct": ad, "C_daf_pct": c, "H_daf_pct": h, "O_daf_pct": o, "N_daf_pct": n, "HHV_d_kJ_kg": hhv}
    if cl is not None:
        v["Cl_daf_pct"] = cl
    return _entry(key, name, "Ad dry; C/H/O/N(/Cl) dry ash-free; HHV dry (kJ/kg)", v, _ZHOU,
                  "volatile matter, fixed carbon, sulphur (not in the values given to this task)",
                  _OTHER + " Table 9 literature mean; the paper gives no mixed-MSW ultimate analysis." + (" Cl is not carried by the engine." if cl is not None else ""))


def _textile(key, name, ad, vd, c, h, o, n, hhv):
    return _entry(key, name, "Ad, Vd dry; C/H/O/N dry ash-free; HHV dry (kJ/kg)",
                  {"Ad_pct": ad, "Vd_pct": vd, "C_daf_pct": c, "H_daf_pct": h, "O_daf_pct": o, "N_daf_pct": n, "HHV_d_kJ_kg": hhv}, _ZHOU,
                  "fixed carbon, sulphur, chlorine (not in the values given to this task)", _OTHER + " Table 7 literature mean.")


ENTRIES = [
    _plastic("zhou_pe", "polyethylene (PE)", 0.33, 85.59, 14.15, 0.07, 0.12, 42845),
    _plastic("zhou_pp", "polypropylene (PP)", 0.44, 85.02, 13.93, 0.96, 0.08, 46004),
    _plastic("zhou_ps", "polystyrene (PS)", 0.19, 90.37, 8.64, 0.90, 0.00, 39523),
    _plastic("zhou_pvc", "polyvinyl chloride (PVC)", 5.86, 39.56, 4.85, 0.02, 0.11, 20848, cl=55.18),
    _plastic("zhou_pet", "polyethylene terephthalate (PET)", 0.20, 62.30, 4.43, 33.13, 0.09, 23090),
    _textile("zhou_cotton", "cotton", 1.05, 87.93, 47.55, 6.30, 45.14, 0.82, 17083),
    _textile("zhou_wool", "wool", 1.24, 84.76, 59.30, 5.36, 24.85, 8.89, 22276),
    _textile("zhou_chemical_fibres", "chemical fibres", 2.15, 87.09, 59.28, 5.25, 27.40, 7.56, 23667),
    _entry("zhou_msw_combustible_fractions", "mean Chinese MSW combustible fractions", "mass %, Fig. 1",
           {"food_residue_pct": 55.86, "plastics_pct": 11.15, "paper_pct": 8.52, "textiles_pct": 3.16, "wood_pct": 2.94, "rubber_pct": 0.84}, _ZHOU,
           "a mixed-MSW ultimate analysis (the paper gives none)", _OTHER + " Composition of the combustible fraction by material, not an elemental analysis."),
    _entry("teerawattana_rdf", "refuse-derived fuel (RDF), Thailand", "air-dry (moisture 2.93 %); HHV in kcal/kg",
           {"moisture_pct": 2.93, "ash_pct": 24.48, "ash_range_pct": (19.76, 29.31), "C_pct": 55.16, "H_pct": 7.89, "O_pct": 10.32, "N_pct": 1.30, "S_pct": 0.12,
            "Cl_pct": 0.73, "HHV_kcal_kg": 6888.1, "HHV_range_kcal_kg": (5811.4, 7958.0)},
           ("Teerawattana et al., Environment and Natural Resources J. 9(1), 2011, Table 1",
            "https://ph02.tci-thaijo.org/index.php/ennrj/article/download/82440/65520/199529"),
           "volatile matter and fixed carbon (not reported); the basis of the HHV (taken as the same air-dry basis); the O figure is 'by difference'",
           _OTHER + " C/H/O/N/S/Cl are as air-dry fractions of the whole fuel (ash included), not daf. Ash 24 % is far outside the engine's 10 %."),
    _entry("werle_sewage_sludge_ss1", "sewage sludge SS1", "moisture, VM, ash as listed; C/H/N/O/S dry; LHV dry (MJ/kg)",
           {"moisture_ar_pct": 5.30, "VM_pct": 51.00, "ash_pct": 36.50, "C_d_pct": 31.79, "H_d_pct": 4.36, "N_d_pct": 4.88, "O_d_pct": 57.07, "S_d_pct": 1.67, "LHV_d_MJ_kg": 12.96},
           ("Werle, sewage sludge gasification, Table 1", "https://yadda.icm.edu.pl/baztech/element/bwmeta1.element.baztech-4a966c39-792b-43c0-ae51-f021241b04ce/c/werle_gasification_2013_11.pdf"),
           "the basis of VM and ash (listed with the as-received moisture); ash as a separate dry figure",
           _OTHER + " The text layout of the page is garbled and the mapping follows the label order. O is 'by difference', so it apparently includes the ash (C+H+N+O+S = 99.77 %): "
           "the O-by-difference oddity is flagged here and NOT corrected."),
    _entry("werle_sewage_sludge_ss2", "sewage sludge SS2", "as SS1",
           {"moisture_ar_pct": 5.30, "VM_pct": 49.00, "ash_pct": 44.20, "C_d_pct": 27.72, "H_d_pct": 3.81, "N_d_pct": 3.59, "O_d_pct": 63.04, "S_d_pct": 1.81, "LHV_d_MJ_kg": 10.75},
           ("Werle, sewage sludge gasification, Table 1", "https://yadda.icm.edu.pl/baztech/element/bwmeta1.element.baztech-4a966c39-792b-43c0-ae51-f021241b04ce/c/werle_gasification_2013_11.pdf"),
           "the basis of VM and ash; ash as a separate dry figure",
           _OTHER + " Same layout caveat as SS1. O by difference apparently includes the ash (27.72+3.81+3.59+63.04+1.81 = 99.97 %); not corrected."),
    {"key": "wood_pellets_or_chips", "material": "wood", "basis": "-", "values": {}, "source_title": "no source opened for this task", "source_url": None,
     "what_the_page_does_not_state": "everything", "status": STATUS_MISSING + " (source not opened)",
     "caveat": "NOT VERIFIED: no analysis was opened and none is added from memory. The engine's default feed (C/H/O/N 0.50/0.06/0.43/0.01 daf, ash 0.10) is a wood-like stand-in, not this entry."},
    {"key": "chalmers_cotton_polyester_thesis", "material": "cotton / polyester", "basis": "-", "values": {}, "source_title": "Chalmers thesis (abstract only)", "source_url": None,
     "what_the_page_does_not_state": "any analysis values (the page is an abstract)", "status": STATUS_MISSING,
     "caveat": "NOT VERIFIED: the page gives no analysis values."},
    {"key": "moliner_energies_17_5_1206", "material": "textile / mixed waste (Moliner et al.)", "basis": "-", "values": {}, "source_title": "Moliner et al., Energies 17(5) 1206 (PMC7663054)",
     "source_url": None, "what_the_page_does_not_state": "not readable (blocked)", "status": STATUS_MISSING,
     "caveat": "NOT VERIFIED: the page could not be read; no values."},
    {"key": "dokink_feed_bands", "material": "DOK-ING stated feed bands (RFI #2)", "basis": "dry basis for LHV; the basis of the others is not stated",
     "values": {"carbon_min_pct": 45.0, "hydrogen_min_pct": 5.0, "volatile_matter_min_pct": 65.0, "ash_pct_range": (5.0, 15.0), "lhv_MJ_kg_dry_range": (15.0, 20.0),
                "moisture_pct_range": (5.0, 15.0), "feed_forms": "plastic, dried sewage sludge, wood chips, textiles"},
     "source_title": "data/dokink_rfi_answers.md lines 15-18 (RFI #2 'Composition' and #3 'Feedstock form')", "source_url": None,
     "what_the_page_does_not_state": "the basis of C, H, VM and ash; any upper limit on C or H; sulphur and chlorine limits ('trace S/Cl captured via downstream scrubbing')",
     "status": "Assumed (DOK-ING-stated band, kept as a band)",
     "caveat": "DOK-ING's stated figures, quoted from the repo's copy of its RFI response (file:line above). design_basis.py records RFI #2 as confirmed; this layer does not upgrade or downgrade that, it only applies the bands to DRY-BASIS numbers as the task specifies."},
]

# --- DOK-ING bands (quoted: data/dokink_rfi_answers.md:15-17 "Moisture 5-15(20)%, Ash 5-15%, Volatile Matter >65%, Carbon >45%, Hydrogen >5%, LHV 15-20 MJ/kg (dry basis)")
BANDS = {"C_dry_pct": (">", 45.0), "H_dry_pct": (">", 5.0), "VM_dry_pct": (">", 65.0), "ash_dry_pct": ("range", (5.0, 15.0)), "LHV_dry_MJ_kg": ("range", (15.0, 20.0))}

NOT_FOUND = [
    {"item": "wood analysis", "note": "no source opened for this task"},
    {"item": "cotton / polyester thesis analysis", "note": "abstract only"},
    {"item": "Moliner et al. 2024", "note": "NOT VERIFIED: not readable"},
]
REQUIRED_FIELDS = ("key", "material", "basis", "values", "source_title", "source_url", "what_the_page_does_not_state", "status", "caveat")
_ALLOWED_STATUS_PREFIX = ("Assumed", "Calculated", "Missing")


def entry(key):
    for e in ENTRIES:
        if e["key"] == key:
            return e
    raise KeyError(key)


# =============================================================================
# derived (Calculated) quantities
# =============================================================================

def dry_basis(key):
    """Dry-basis (ash included) composition from daf: X_dry = X_daf x (1 - Ad/100), for C, H, O, N, Cl; ash = Ad. Calculated.
    Entries stored on another basis (RDF air-dry, sludge dry) are converted/returned as stated: RDF X_dry = X_ad / (1 - moisture/100)."""
    e = entry(key)
    v = e["values"]
    out = {"formula": "X_dry = X_daf x (1 - Ad/100)", "status": STATUS_CALCULATED}
    if "Ad_pct" in v:
        f = 1.0 - v["Ad_pct"] / 100.0
        for el in ("C", "H", "O", "N", "Cl"):
            if f"{el}_daf_pct" in v:
                out[f"{el}_dry_pct"] = v[f"{el}_daf_pct"] * f
        out["ash_dry_pct"] = v["Ad_pct"]
        if "Vd_pct" in v:
            out["VM_dry_pct"] = v["Vd_pct"]
        out["HHV_dry_kJ_kg"] = v["HHV_d_kJ_kg"]
    elif key == "teerawattana_rdf":
        g = 1.0 - v["moisture_pct"] / 100.0
        out["formula"] = "X_dry = X_ad / (1 - moisture/100); HHV_dry = HHV_kcal x 4.184 / (1 - moisture/100)"
        for el in ("C", "H", "O", "N", "S", "Cl"):
            out[f"{el}_dry_pct"] = v[f"{el}_pct"] / g
        out["ash_dry_pct"] = v["ash_pct"] / g
        out["HHV_dry_kJ_kg"] = v["HHV_kcal_kg"] * KJ_PER_KCAL / g
    elif key.startswith("werle_sewage_sludge"):
        out["formula"] = "as stated (dry); VM_dry = VM / (1 - moisture/100) if VM is on the as-received basis (its basis is not stated)"
        for el in ("C", "H", "N", "O", "S"):
            out[f"{el}_dry_pct"] = v[f"{el}_d_pct"]
        out["ash_dry_pct"] = v["ash_pct"]                       # basis not stated; used as stated
        out["VM_dry_pct"] = v["VM_pct"] / (1.0 - v["moisture_ar_pct"] / 100.0)
        out["LHV_dry_MJ_kg"] = v["LHV_d_MJ_kg"]
    else:
        raise ValueError(f"no dry-basis conversion for {key}")
    return out


def lhv_from_hhv(hhv_kj_kg, h_dry_pct):
    """LHV (kJ/kg, dry basis) = HHV - 2.442 MJ/kg x 9 x H_dry/100 x 1000 (9 kg water per kg H; 2.442 MJ/kg water at 25 degC). Calculated."""
    return hhv_kj_kg - LATENT_HEAT_WATER_MJ_KG * 1000.0 * 9.0 * h_dry_pct / 100.0


def derived(key):
    """dry-basis composition and LHV (MJ/kg dry and daf) of a stored material. Calculated."""
    d = dry_basis(key)
    if "LHV_dry_MJ_kg" not in d:
        d["LHV_dry_MJ_kg"] = lhv_from_hhv(d["HHV_dry_kJ_kg"], d["H_dry_pct"]) / 1000.0
        d["LHV_formula"] = "LHV = HHV - 2.442 x 9 x H_dry/100 (MJ/kg); constant 2.442 MJ/kg = latent heat of water at 25 degC"
    if "ash_dry_pct" in d:
        d["LHV_daf_MJ_kg"] = d["LHV_dry_MJ_kg"] / (1.0 - d["ash_dry_pct"] / 100.0)
    return d


def model_composition(key_or_values, ash_model=0.10):
    """Dry ash-free C/H/O/N mass fractions in the form the engine takes (GA-001-INPUT feedstock_composition), and what had to be dropped.
    Only C, H, O, N exist in the engine: S and Cl (and any unreported daf mass) are dropped and C/H/O/N are renormalised to sum to 1.
    Also the feed energy of a MODEL feed (dry, with the engine's fixed ash fraction): LHV_daf x (1 - ash_model). Calculated."""
    if isinstance(key_or_values, str):
        v = entry(key_or_values)["values"]
        daf = {el: v[f"{el}_daf_pct"] for el in ("C", "H", "O", "N")}
        dropped = {el: v.get(f"{el}_daf_pct", 0.0) for el in ("Cl",)}
        lhv_daf = derived(key_or_values)["LHV_daf_MJ_kg"]
    else:
        daf = {el: key_or_values[el] for el in ("C", "H", "O", "N")}
        dropped = {el: key_or_values.get(el, 0.0) for el in ("Cl", "S")}
        lhv_daf = key_or_values["LHV_daf_MJ_kg"]
    total = sum(daf.values())
    comp = {el: daf[el] / total for el in daf}
    unaccounted = 100.0 - total - sum(dropped.values())
    return {"composition_daf": comp, "daf_pct_before_renormalising": total, "dropped_daf_pct": dropped, "unaccounted_daf_pct": unaccounted,
            "LHV_daf_MJ_kg": lhv_daf, "LHV_model_dry_MJ_kg": lhv_daf * (1.0 - ash_model),
            "note": "renormalised over C+H+O+N; the engine's ash fraction is fixed (0.10), so the feed energy is LHV_daf x (1 - 0.10)"}


def stoichiometric(formula):
    """Mass fractions (daf) of a pure polymer repeat unit, e.g. {'C':1,'H':2} for PE / PP (CH2), {'C':1,'H':1} for PS (CH), {'C':10,'H':8,'O':4} for PET.
    Calculated from the named atomic masses; a cross-check against the literature means, NOT a source."""
    mass = {el: n * ATOMIC_MASS[el] for el, n in formula.items()}
    tot = sum(mass.values())
    return {el: 100.0 * m / tot for el, m in mass.items()}


STOICHIOMETRIC = {"PE": {"C": 1, "H": 2}, "PP": {"C": 1, "H": 2}, "PS": {"C": 1, "H": 1}, "PET": {"C": 10, "H": 8, "O": 4}}
BLEND_M1 = {"zhou_pe": 0.40, "zhou_pp": 0.25, "zhou_ps": 0.15, "zhou_pet": 0.10, "zhou_pvc": 0.10}      # ILLUSTRATIVE, Assumed, not DOK-ING data


def blend(weights=None):
    """Mass-weighted DRY-basis blend (weights by mass of the materials as they are): composition, ash, VM(not available), HHV, LHV. Status Calculated
    from Assumed weights; blend M1 (40 % PE, 25 % PP, 15 % PS, 10 % PET, 10 % PVC) is an illustrative mix for sensitivity only, not DOK-ING data."""
    w = weights or BLEND_M1
    assert abs(sum(w.values()) - 1.0) < 1e-12
    acc = {"C": 0.0, "H": 0.0, "O": 0.0, "N": 0.0, "Cl": 0.0, "ash": 0.0, "HHV": 0.0}
    for k, wt in w.items():
        d = dry_basis(k)
        for el in ("C", "H", "O", "N", "Cl"):
            acc[el] += wt * d.get(f"{el}_dry_pct", 0.0)
        acc["ash"] += wt * d["ash_dry_pct"]
        acc["HHV"] += wt * d["HHV_dry_kJ_kg"]
    daf_f = 1.0 - acc["ash"] / 100.0
    out = {"weights": dict(w), "status": STATUS_CALCULATED, "illustrative": True, "ash_dry_pct": acc["ash"], "HHV_dry_kJ_kg": acc["HHV"],
           **{f"{el}_dry_pct": acc[el] for el in ("C", "H", "O", "N", "Cl")},
           **{f"{el}_daf_pct": acc[el] / daf_f for el in ("C", "H", "O", "N", "Cl")}}
    out["LHV_dry_MJ_kg"] = lhv_from_hhv(acc["HHV"], acc["H"]) / 1000.0
    out["LHV_daf_MJ_kg"] = out["LHV_dry_MJ_kg"] / daf_f
    out["formula"] = "mass-weighted sum of the dry-basis values; daf = dry / (1 - ash/100); LHV from HHV as in lhv_from_hhv"
    return out


# =============================================================================
# DOK-ING band check
# =============================================================================

def check_bands(values):
    """values: dict with any of C_dry_pct, H_dry_pct, VM_dry_pct, ash_dry_pct, LHV_dry_MJ_kg (dry basis). Returns {band: (value, 'satisfied'|'fails'|'not testable')}.
    The bands are one-sided for C, H and VM (the band says nothing about an upper limit) and two-sided for ash and LHV."""
    out = {}
    for band, (kind, lim) in BANDS.items():
        x = values.get(band)
        if x is None:
            out[band] = (None, "not testable")
        elif kind == ">":
            out[band] = (x, "satisfied" if x > lim else "fails")
        else:
            out[band] = (x, "satisfied" if lim[0] <= x <= lim[1] else "fails")
    return out


def bands_for(key):
    d = derived(key)
    return check_bands({"C_dry_pct": d.get("C_dry_pct"), "H_dry_pct": d.get("H_dry_pct"), "VM_dry_pct": d.get("VM_dry_pct"),
                        "ash_dry_pct": d.get("ash_dry_pct"), "LHV_dry_MJ_kg": d.get("LHV_dry_MJ_kg")})


def problems(e):
    """Rule violations of one stored entry (empty = fine)."""
    out = [f"missing field {f}" for f in REQUIRED_FIELDS if f not in e]
    if out:
        return out
    if not str(e["status"]).startswith(_ALLOWED_STATUS_PREFIX):
        out.append("status does not start with Assumed / Calculated / Missing")
    if any(w in str(e["status"]) for w in ("Confirmed", "Measured")):
        out.append("status claims Confirmed / Measured")
    if not str(e["status"]).startswith("Missing") and e["key"] != "dokink_feed_bands":
        if not str(e["source_url"] or "").startswith("https://"):
            out.append("no https source_url")
    if str(e["status"]).startswith("Missing") and e["source_url"] is not None and not str(e["source_url"]).startswith("https://"):
        out.append("bad source_url")
    if not str(e["caveat"]).strip():
        out.append("empty caveat")
    return out
