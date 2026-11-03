"""Ledger D2 and wording pass W1: persisted snapshot notes that were reworded, text only (they called a registry value "Confirmed" or "independently validated").

Older tests compare the live snapshot with fixtures that were made BEFORE the rewording (tests/fixtures/snapshot_origin_main_71e92cc / 198bfcb / f628406 / 701de71). The mapping here is the
ONE exemption list. Every pair is (new phrase, old phrase). `forward(entries)` applies old -> new to a fixture, so a test that compares the live snapshot with `forward(fixture)` still fails when an
old phrase returns or any other text changes; `undo(entries)` maps new -> old (the reverse) for the tests that still compare with an older fixture. Only the entries listed in ENTRIES are touched.

  PAIRS_D2   4 pairs in 3 entry prefixes, added by task A3 item D2 (commit ac4fe79).
  PAIRS_W1   88 pairs in 43 entries (89 when added; 88 since A3d, see PAIRS_A3D), added by commit 0420d32 "Wording W1.1: registry rows called Confirmed in persisted notes are named with their status" (task W1).
  The 3 pairs of the EU-008 "independently validated" notes (W1.2) are part of PAIRS_W1; they were added by commit 87e4950 "Wording W1.2: EU-008 ... notes say what the repo supports".
  PAIRS_A3D  2 pairs, one entry each, added by task A3d (Gate 5 corrections, branch a3-gate5-wording): the HB-012 compressor note (P2 = 701 bar(a): the 350/700 bar is DOK-ING's, the bar(g) designation
             is the registry's, the +1 bar offset is the project's) and the EU-CHP dispatch note (the 100 % WGS/PSA claim fraction is a model choice, DOK-ING's RFI #10 states only the priority).
             The HB-012 pair REPLACES the W1 pair for the same sentence (its old phrase is the fixture's, so PAIRS_W1 went from 89 to 88 pairs); the EU-CHP pair is new. Each A3d pair is applied
             only in its own entry (ENTRIES_A3D[i] for PAIRS_A3D[i]); both entries are also in ENTRIES_W1."""
import hashlib
import json

# (new phrase, old phrase)
PAIRS_D2 = (
    ("registry '>98% removal efficiency' (Unverified (registry), not DOK-ING-confirmed)", "own Confirmed '>98% removal efficiency'"),
    ("registry >90% efficiency (>d50=15um; Unverified (registry))", "own Confirmed >90% efficiency (>d50=15um)"),
    ("ACTUAL/DOK-ING VALUE: Unverified (registry), not DOK-ING-confirmed -- 20 kW", "ACTUAL/DOK-ING VALUE: Confirmed -- 20 kW"),
    ("Unverified (registry), not DOK-ING-confirmed -- 20 kW, scoped to EU-004 jacket cooling only (per EU-008's own", "Confirmed -- 20 kW, scoped to EU-004 jacket cooling only (per EU-008's own"),
)
PAIRS_W1 = (
    ("The default delivery rate, set equal to DOK-ING's confirmed nominal capacity (RFI answer 1, data/dokink_rfi_answers.md:11; wet or dry not stated; 1,000 kg/day = ",
     "DOK-ING's own confirmed nominal AS-RECEIVED delivery rate (RFI #1, 1,000 kg/day = "),
    ("GA-002's own registry 'Operating pressure range' (50-150 mbar(g); Unverified (registry), not DOK-ING-confirmed) midpoint, read ",
     "GA-002's own Confirmed 'Operating pressure range' (50-150 mbar(g)) midpoint, read "),
    ('compressor power (each calculated from Unverified (registry) inputs; none validated against plant data), running peak x 15% margin',
     'compressor power (each independently already-validated), running peak x 15% margin'),
    ("module constant, an Assumed value: GA-005's registry row is Unverified (registry), not DOK-ING-confirmed, and is a discharge rate, not this fraction) ",
     "module constant, itself independently Confirmed from GA-005's own registry data) "),
    ("SA-011's/SA-009's/SA-010's own registry temperature (Unverified (registry), not DOK-ING-confirmed) at this late-train ",
     "SA-011's/SA-009's/SA-010's own Confirmed registry temperature at this late-train "),
    ("from HB-010's own registry 85% recovery / 95-98% purity (Unverified (registry), not DOK-ING-confirmed) at their own registry ",
     "from HB-010's own Confirmed 85% recovery / 95-98% purity at their own Confirmed "),
    ("GC-003's own registry inlet (2 g/Nm3) and efficiency (>95% > 10um), both Unverified (registry), not DOK-ING-confirmed, ",
     "GC-003's own Confirmed inlet (2 g/Nm3) and Confirmed efficiency (>95% > 10um), "),
    ("Sum of three duties calculated by this project's own models from Unverified (registry) inputs, none validated against plant data (GC-004 quench sensible heat, ",
     'Sum of three independently-validated real duties (GC-004 quench sensible heat, '),
    ('agrees arithmetically (it is itself 0.4 x 37.5, Assumed, so not an independent check) with 15 kg/h steam / 37.5 kg/h feed = 0.4 exactly, the same ',
     'independently confirms 15 kg/h steam / 37.5 kg/h feed = 0.4 exactly, the same '),
    ("GC-001's own registry outlet temperature (880 degC; Unverified (registry), not DOK-ING-confirmed), read directly.",
     "GC-001's own Confirmed registry outlet temperature (880 degC), read directly."),
    ("GC-009's OWN registry inlet (150 ppm, Unverified (registry), not DOK-ING-confirmed; itself flagged 'Estimate') and outlet ",
     "GC-009's OWN Confirmed inlet (150 ppm, itself flagged 'Estimate') and outlet "),
    ("GC-003's own registry inlet temperature (870 degC; Unverified (registry), not DOK-ING-confirmed), read directly.",
     "GC-003's own Confirmed registry inlet temperature (870 degC), read directly."),
    ("GC-008's OWN registry inlet (200 ppm, Unverified (registry), not DOK-ING-confirmed; itself flagged 'Estimate' in its own ",
     "GC-008's OWN Confirmed inlet (200 ppm, itself flagged 'Estimate' in its own "),
    ("GA-001's own registry value (resolved status Assumed, not DOK-ING-confirmed; 'Operating temperature (typical)' = ",
     "GA-001's own Confirmed registry value ('Operating temperature (typical)' = "),
    ("HB-011's own separately registry-stated (Unverified (registry)) 'H2 production rate (rated)=0.18 Nm3/h' ",
     "HB-011's own separately-Confirmed 'H2 production rate (rated)=0.18 Nm3/h' "),
    ("HB-016's own registry round-trip efficiency ratio (6.0/6.2 wt%, Unverified (registry)) as a target CONVERSION ",
     "HB-016's own confirmed round-trip efficiency ratio as a target CONVERSION "),
    ("GC-010's OWN registry inlet (300 mg/Nm3; Unverified (registry), not DOK-ING-confirmed) and outlet target (<5 mg/Nm3): ",
     "GC-010's OWN Confirmed inlet (300 mg/Nm3) and outlet target (<5 mg/Nm3): "),
    ("Back-derived from HB-010's own registry recovery (85%; Unverified (registry), not DOK-ING-confirmed) and purity range ",
     "Back-derived from HB-010's own Confirmed recovery (85%) and purity range "),
    ("HB-010's own registry recovery/purity design-point figures (Unverified (registry), not DOK-ING-confirmed) AT their own ",
     "HB-010's own Confirmed recovery/purity design-point figures AT their own "),
    ("SA-012's own registry pressure (50 mbar(g); Unverified (registry), not DOK-ING-confirmed), directly matching ",
     "SA-012's own Confirmed registry pressure (50 mbar(g)), directly matching "),
    ("Medium -- each summed duty is calculated by this project's own model from Unverified (registry) inputs (none validated against plant data), and their ",
     'Medium -- each summed duty is independently real/validated, but their '),
    ("closely matching HB-010's own registry 50 GPU, Unverified (registry), not DOK-ING-confirmed) reports a measured ",
     "closely matching HB-010's own Confirmed 50 GPU) reports a measured "),
    ("same 'registry design constant as live placeholder' treatment as ",
     "same 'Confirmed design constant as live placeholder' treatment as "),
    ("LHV in DOK-ING's Confirmed 15-20 MJ/kg dry range (RFI answer 2, data/dokink_rfi_answers.md:15-16), point is a case",
     "LHV in DOK-ING's Confirmed 15-20 MJ/kg dry range, point is a case"),
    ('AT the registry design-point feed H2 fraction (Unverified (registry)) those figures are ',
     'AT the Confirmed design-point feed H2 fraction those figures are '),
    ("GC-005's own registry blowdown rate (0.05 m3/h; Unverified (registry), not DOK-ING-confirmed), read directly.",
     "GC-005's own Confirmed blowdown rate (0.05 m3/h), read directly."),
    ('AND its own registry operating conditions (170 degC/40 bar; Unverified (registry)) at ',
     'AND its own Confirmed operating conditions (170 degC/40 bar) at '),
    ("five real inflow streams' own registry (Unverified (registry))/interpolated source ",
     "five real inflow streams' own Confirmed/interpolated source "),
    ("HB-014's own registry states catalyst type (Pt/Pd/Al2O3), ",
     "HB-014's own registry confirms catalyst type (Pt/Pd/Al2O3), "),
    ("GA-001's own registry data states (Unverified (registry), not DOK-ING-confirmed) the reactor TECHNOLOGY ",
     "GA-001's own registry data confirms the reactor TECHNOLOGY "),
    ("differs materially from GA-001's own registry-stated technology (Unverified (registry), not DOK-ING-confirmed) ",
     "differs materially from GA-001's own confirmed technology "),
    ("blowdown = circulating x GC-005's own registry-stated 10% ratio (Unverified (registry)).",
     "blowdown = circulating x GC-005's own Confirmed 10% ratio."),
    ('(neither registry figure is altered to force agreement).',
     '(neither Confirmed figure is altered to force agreement).'),
    ("HB-014's own registry Pt/Pd/Al2O3, Unverified (registry)) and an unretrievable ",
     "HB-014's own Confirmed Pt/Pd/Al2O3) and an unretrievable "),
    ("HB-016's own registry states catalyst type (Pt/Al2O3), ",
     "HB-016's own registry confirms catalyst type (Pt/Al2O3), "),
    ("(HB-012's own registry motor rating: 10 kW, Unverified (registry), not DOK-ING-confirmed -- a real, ",
     "(HB-012's own Confirmed motor rating: 10 kW -- a real, "),
    ('instead of its real registry (Unverified (registry), not DOK-ING-confirmed) narrower-scoped 20kW ',
     'instead of its real Confirmed-but-narrower-scoped 20kW '),
    ("HB-010's own registry states H2 permeance (50 GPU), ",
     "HB-010's own registry confirms H2 permeance (50 GPU), "),
    ("(EU-005's own registry 150 Nm3/h rated, Unverified (registry), not DOK-ING-confirmed, x live load).",
     "(EU-005's own Confirmed 150 Nm3/h rated x live load)."),
    ("a LOWER BOUND on GC-013's own registry 1.5 kW motor (Unverified (registry), not DOK-ING-confirmed) ",
     "a LOWER BOUND on GC-013's own Confirmed 1.5 kW motor "),
    ('AND its own registry 300 degC operating temperature (both Unverified (registry), not DOK-ING-confirmed) ',
     'AND its own Confirmed 300 degC operating temperature '),
    ("'Demand' modeled as HB-018's own registry (Unverified (registry), not DOK-ING-confirmed) max rated ",
     "'Demand' modeled as HB-018's own Confirmed max rated "),
    ("(HB-006's own registry target: 55 vol%, Unverified (registry), not DOK-ING-confirmed -- a real, ",
     "(HB-006's own Confirmed target: 55 vol% -- a real, "),
    ("EU-003's/EU-005's own static registry-stated (Unverified (registry), not DOK-ING-confirmed) 9.8 MJ/Nm3",
     "EU-003's/EU-005's own static Confirmed 9.8 MJ/Nm3"),
    ("HB-003's own registry 220 degC hot-side outlet (Unverified (registry), not DOK-ING-confirmed), ",
     "HB-003's own Confirmed 220 degC hot-side outlet, "),
    ('Quenching to the registry 65 degC outlet target (GC-004, Unverified (registry), not DOK-ING-confirmed) ',
     'Quenching to the Confirmed 65 degC outlet target '),
    ("HB-010's OWN registry design-point numbers, Unverified (registry), not DOK-ING-confirmed (not ",
     "HB-010's OWN confirmed design-point numbers (not "),
    ("scaled to GA-001's own dry feed rate (an Assumed input); ",
     "scaled to GA-001's own confirmed dry feed rate; "),
    ("blowdown = circulating x GC-005's own registry-stated (Unverified (registry), not DOK-ING-confirmed) ",
     "blowdown = circulating x GC-005's own Confirmed "),
    ("sum of every stage's own registry design dP (Unverified (registry), not DOK-ING-confirmed) = ",
     "sum of every stage's own Confirmed design dP = "),
    ("from) this project's own computed O2 demand",
     "from) this project's own confirmed O2 demand"),
    ('registry 4-stage, intercooled design, Unverified (registry)). P1=',
     'Confirmed 4-stage, intercooled design). P1='),
    ("than GA-001's own registry-stated BFB technology (Unverified (registry), not DOK-ING-confirmed)",
     "than GA-001's own confirmed BFB technology"),
    ("of HB-016's own registry Pt/Al2O3 (Unverified (registry); exact ",
     "of HB-016's own Confirmed Pt/Al2O3 (exact "),
    ("from GC-007's own registry inlet figure (Unverified (registry), not DOK-ING-confirmed) ",
     "from GC-007's own Confirmed inlet figure "),
    ("vs. HB-014's own registry Pt/Pd/Al2O3, Unverified (registry), not DOK-ING-confirmed); ",
     "vs. HB-014's own Confirmed Pt/Pd/Al2O3); "),
    ("GC-014's own registry (Unverified (registry), not DOK-ING-confirmed) design discharge=",
     "GC-014's own Confirmed design discharge="),
    ("matching HB-006's own registry feed H2 ",
     "matching HB-006's own Confirmed feed H2 "),
    ("(FE-001's own registry live capacity: Unverified (registry), not DOK-ING-confirmed)",
     "(FE-001's own Confirmed live capacity)"),
    ("to HB-010's own registry 50 GPU, Unverified (registry), not DOK-ING-confirmed) -- ",
     "to HB-010's own Confirmed 50 GPU) -- "),
    ("BOTH HB-014's own registry catalyst (Unverified (registry), not DOK-ING-confirmed) ",
     "BOTH HB-014's own Confirmed catalyst "),
    ("both matching HB-016's own registry ",
     "both matching HB-016's own Confirmed "),
    ('(2) Evaluated AT the registry 55% ',
     '(2) Evaluated AT the Confirmed 55% '),
    ('registry 4:1 steam-to-CO ratio (Unverified (registry), not DOK-ING-confirmed) = ',
     'Confirmed 4:1 steam-to-CO ratio = '),
    ("(HB-013's own registry capacity, Unverified (registry), not DOK-ING-confirmed).",
     "(HB-013's own Confirmed capacity)."),
    ('cumulative registry-stage (Unverified (registry)) train ',
     'cumulative confirmed-stage train '),
    ('at its own registry 170 degC/40 ',
     'at its own confirmed 170 degC/40 '),
    ('300 degC (matches the registry 300 degC, Unverified (registry)); Park',
     '300 degC (Confirmed match); Park'),
    ('at its own registry 300 degC/2 ',
     'at its own confirmed 300 degC/2 '),
    ("to reach HB-016's own registry-stated (Unverified (registry)) ",
     "to reach HB-016's own Confirmed "),
    ("FE-003's own Confirmed (DOK-ING RFI answer 1, data/dokink_rfi_answers.md:11) nominal(",
     "FE-003's own Confirmed nominal("),
    ("bound = GC-005's own registry (Unverified (registry), not DOK-ING-confirmed) ",
     "bound = GC-005's own Confirmed "),
    ("GA-001's own registry-stated BFB (Unverified (registry), not DOK-ING-confirmed) -- ",
     "GA-001's own confirmed BFB -- "),
    ('(spans the registry 300 degC, Unverified (registry))',
     '(spans the Confirmed 300 degC)'),
    ('registry 55% feed-H2 basis ',
     'Confirmed 55% feed-H2 basis '),
    ("HB-003's own registry (Unverified (registry), not DOK-ING-confirmed) 150 ",
     "HB-003's own Confirmed 150 "),
    ("at EU-007's own Assumed (not DOK-ING-confirmed; no registry row states it) ",
     "at EU-007's own Confirmed "),
    ('gap against the registry (Unverified (registry)) ',
     'gap against the Confirmed '),
    ('dry feed rate (an Assumed input; DOK-ING RFI #1 gives 1,000 kg/day without saying wet or dry) (',
     'confirmed dry feed rate ('),
    ('L/G(2.5 L/Nm3, registry, Unverified (registry))',
     'L/G(2.5 L/Nm3, Confirmed)'),
    ("EU-008's own registry (Unverified (registry), not DOK-ING-confirmed) ",
     "EU-008's own Confirmed "),
    ('L/G(2 L/Nm3, registry, Unverified (registry))',
     'L/G(2 L/Nm3, Confirmed)'),
    ('L/G(3 L/Nm3, registry, Unverified (registry))',
     'L/G(3 L/Nm3, Confirmed)'),
    ("GC-012's own registry-stated (Unverified (registry), not DOK-ING-confirmed) ",
     "GC-012's own Confirmed "),
    ("GA-002's own registry-stated (GA-001 'Operating pressure (typical)', Unverified (registry), not DOK-ING-confirmed) ",
     "GA-002's own Confirmed "),
    ("HB-011's own registry-stated (Unverified (registry), not DOK-ING-confirmed) ",
     "HB-011's own Confirmed "),
    ("H2's own Assumed (not DOK-ING-confirmed) ",
     "H2's own Confirmed "),
    ('registry (Unverified (registry), not DOK-ING-confirmed) [',
     'Confirmed ['),
)
PAIRS_A3D = (
    (", P2 = 701 bar(a): DOK-ING RFI answer 8 (data/dokink_rfi_answers.md:35-36) states 350/700 bar without gauge or absolute; the bar(g) designation is the registry's and the +1 bar offset is this project's assumption, "
     "P1 = HB-012's registry inlet pressure (7 bar(g) + 1; Unverified (registry), not DOK-ING-confirmed). Computed power: ",
     ", both HB-008's/HB-012's own Confirmed values. Computed power: "),
    ("(100% -- a model choice (Assumed); DOK-ING's RFI #10 states only that 'H2 is primary; CHP ... optional, not fixed', see ",
     "(100% -- DOK-ING's own confirmed RFI #10 priority, 'H2 is primary; CHP ... optional, not fixed', see "),
)
ENTRIES_A3D = ("HB-012|Compressor", "EU-CHP|Dispatch")          # PAIRS_A3D[i] is applied only in the snapshot entries whose key starts with ENTRIES_A3D[i]
PAIRS = PAIRS_D2 + PAIRS_W1 + PAIRS_A3D
ENTRIES_D2 = ("FE-002|", "GC-001|", "EU-008|")      # the snapshot keys (prefixes) whose text carries the D2 pairs
ENTRIES_W1 = (
    'AI-003|BedPressureDrop',
    'AI-004|EU-009-State-IfResized',
    'EU-005|Microturbine',
    'EU-007|Flare',
    'EU-008|CoolingSupply',
    'EU-008|RecommendedCapacityEstimate',
    'EU-CHP|Dispatch',
    'FE-001-INPUT|msw_delivery_rate_kg_h',
    'FE-001|Inventory',
    'FE-003|Weighing',
    'GA-001-INPUT|feedstock_composition',
    'GA-001-INPUT|operating_temperature_C',
    'GA-001-INPUT|steam_to_feed_ratio',
    'GA-001|EnergyBalance',
    'GA-001|OxygenCarrierCirculationEstimate',
    'GC-001|Temperature',
    'GC-003|Dust',
    'GC-003|Temperature',
    'GC-004|Gas',
    'GC-005|Blowdown',
    'GC-006|Tar outlet',
    'GC-007|Blowdown',
    'GC-008|Blowdown',
    'GC-008|H2S',
    'GC-009|Blowdown',
    'GC-009|HCl',
    'GC-010|Dust',
    'GC-012|H2S/COS',
    'GC-013|Fan power',
    'GC-014|Pressure',
    'GC-015|OperatingConditions',
    'HB-004|LTS',
    'HB-005|Steam',
    'HB-006|PSA',
    'HB-010|SelectivityEstimate',
    'HB-011|Electrolyser',
    'HB-012|Compressor',
    'HB-013|Storage',
    'HB-014|KineticsBaselineEstimate',
    'HB-016|KineticsBaselineEstimate',
    'HB-018|Dispensing',
    'SA-011|Reading',
    'SA-012|Reading',
)
ENTRIES = ENTRIES_D2 + ENTRIES_W1


def w1_fingerprint():
    """sha256 of PAIRS_W1 and ENTRIES_W1: tests/test_design_basis_ledger.py pins it, so the list cannot grow without a visible decision."""
    return hashlib.sha256(json.dumps([PAIRS_W1, ENTRIES_W1]).encode("utf-8")).hexdigest()


def a3d_fingerprint():
    """sha256 of PAIRS_A3D and ENTRIES_A3D (task A3d), pinned the same way."""
    return hashlib.sha256(json.dumps([PAIRS_A3D, ENTRIES_A3D]).encode("utf-8")).hexdigest()


# forward (old -> new) is applied longest old phrase first, so that a phrase that contains a shorter one is not cut up; undo is the exact reverse order
_FORWARD = sorted(PAIRS_D2 + PAIRS_W1, key=lambda p: -len(p[1]))


def _forward_text(s, pairs=None):
    for new, old in (_FORWARD if pairs is None else pairs):
        s = s.replace(old, new)
    return s


def _undo_text(s, pairs=None):
    for new, old in reversed(_FORWARD if pairs is None else pairs):
        s = s.replace(new, old)
    return s


def _walk(x, fn):
    if isinstance(x, str):
        return fn(x)
    if isinstance(x, dict):
        return {k: _walk(v, fn) for k, v in x.items()}
    if isinstance(x, list):
        return [_walk(v, fn) for v in x]
    return x


def _a3d_for(key):
    return [pair for pair, entry in zip(PAIRS_A3D, ENTRIES_A3D) if key.startswith(entry)]          # an A3d pair is only ever applied in its own entry


def forward(serialised):
    """serialised = {"A|B": entry}, as stored in a fixture. Returns the same with the old phrases replaced by the new ones, in the entries that can carry them."""
    out = {}
    for k, v in serialised.items():
        if k.startswith(ENTRIES):
            for pair in _a3d_for(k):
                v = _walk(v, lambda s: _forward_text(s, (pair,)))
            v = _walk(v, _forward_text)
        out[k] = v
    return out


def undo(serialised):
    """serialised = {"A|B": entry}. Returns the same with the reworded phrases mapped back to the old text, in the entries that can carry them."""
    out = {}
    for k, v in serialised.items():
        if k.startswith(ENTRIES):
            v = _walk(v, _undo_text)
            for pair in reversed(_a3d_for(k)):
                v = _walk(v, lambda s: _undo_text(s, (pair,)))
        out[k] = v
    return out
