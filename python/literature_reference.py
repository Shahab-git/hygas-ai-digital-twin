"""
Literature reference layer (step 2 of the validation plan) -- pure data, READ-ONLY, not used by the engine.

Published values from OTHER plants (pilot and lab papers, one vendor page), recorded next to the model so a trend or a range can be compared
by a person or a script. Nothing in the engine, the uncertainty module, the app or the what-if tab reads this module, and it imports nothing
from the project (tests/test_literature_reference.py enforces both).

Every figure below was read on the cited page by the project owner (mostly abstracts) and is reproduced as given: no digit was added, no
paper was fetched, nothing was inferred. A figure the page does not state is not here; `what_the_page_does_not_state` says so.

STATUS. The repo's tag vocabulary (plant_status.py) has the five tags Measured / Calculated / Estimated / Assumed / Missing and no
"Assumed (literature-informed)" string. The project's `Assumed` tag is therefore used for every entry, and "literature-informed" is carried in
`caveat`. None of these values is Confirmed (they are not DOK-ING's), Measured or Calculated.

`numeric` is a list of {"label", "low", "high", "unit"} dicts, present only where the page states numbers (low/high may be None for a one-sided
statement such as "up to 9.32"). `trends` lists directional statements a script may test.
"""

STATUS_ASSUMED = "Assumed"          # same string as plant_status.STATUS_ASSUMED (checked by a test); "literature-informed" is in each caveat

_OTHER_PLANT = "literature-informed Assumed: a value from another plant and feed, not DOK-ING's and not validated for GA-001."


def _n(label, low, high, unit):
    return {"label": label, "low": low, "high": high, "unit": unit}


ENTRIES = [
    {
        "key": "parrillo_er",
        "parameter": "equivalence ratio (ER)",
        "value_text": "ER, 0.22–0.25",
        "numeric": [_n("ER", 0.22, 0.25, "-")],
        "scale": "large pilot-scale fluidised bed",
        "feed": "mixed plastic waste from separate collection of MSW",
        "agent": "steam + O2-enriched air",
        "source_title": "Parrillo et al., SSRN preprint (title not given in the task file)",
        "source_url": "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4737155",
        "what_the_page_does_not_state": "bed temperature, gas composition, LHV",
        "status": STATUS_ASSUMED,
        "caveat": _OTHER_PLANT + " Preprint abstract; plastic-rich feed, O2-enriched air.",
    },
    {
        "key": "parrillo_steam_to_carbon",
        "parameter": "steam-to-carbon ratio",
        "value_text": "Steam-to-carbon ratio, 0.7–1.13",
        "numeric": [_n("steam-to-carbon ratio", 0.7, 1.13, "unit not stated on the page")],
        "scale": "large pilot-scale fluidised bed",
        "feed": "mixed plastic waste from separate collection of MSW",
        "agent": "steam + O2-enriched air",
        "source_title": "Parrillo et al., SSRN preprint (title not given in the task file)",
        "source_url": "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4737155",
        "what_the_page_does_not_state": "whether the ratio is molar or mass based, bed temperature, gas composition, LHV",
        "status": STATUS_ASSUMED,
        "caveat": _OTHER_PLANT + " The basis of the ratio (mol/mol or kg/kg) is not stated, so it is not converted here.",
    },
    {
        "key": "parrillo_steam_to_oxygen",
        "parameter": "steam-to-oxygen ratio",
        "value_text": "steam-to-oxygen up to 3.2",
        "numeric": [_n("steam-to-oxygen ratio", None, 3.2, "unit not stated on the page")],
        "scale": "large pilot-scale fluidised bed",
        "feed": "mixed plastic waste from separate collection of MSW",
        "agent": "steam + O2-enriched air",
        "source_title": "Parrillo et al., SSRN preprint (title not given in the task file)",
        "source_url": "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4737155",
        "what_the_page_does_not_state": "the lower end of the range, whether the ratio is molar or mass based, bed temperature, gas composition, LHV",
        "status": STATUS_ASSUMED,
        "caveat": _OTHER_PLANT + " One-sided statement ('up to').",
    },
    {
        "key": "mdpi_er_bed_temperature",
        "parameter": "ER, bed temperature and test rig",
        "value_text": ("ER, 0.25 fixed; lab BFB 1–4 kg/h, 0.10 m ID; pellets of 50 % brown coal, 30 % recycled polyolefin plastics, 20 % wood; "
                       "air reference with silica sand at 861 °C, O2-enriched air up to 902 °C"),
        "numeric": [_n("ER (fixed)", 0.25, 0.25, "-"), _n("lab BFB throughput", 1, 4, "kg/h"), _n("bed inner diameter", 0.10, 0.10, "m"),
                    _n("air reference with silica sand, temperature", 861, 861, "°C"), _n("O2-enriched air, temperature", None, 902, "°C")],
        "scale": "lab bubbling fluidised bed, 1–4 kg/h, 0.10 m ID",
        "feed": "pellets of 50 % brown coal, 30 % recycled polyolefin plastics, 20 % wood",
        "agent": "air (reference, silica sand) and O2-enriched air",
        "source_title": "Sustainability 2023, 15(9), 7547 (title not given in the task file)",
        "source_url": "https://www.mdpi.com/2071-1050/15/9/7547",
        "what_the_page_does_not_state": "absolute gas compositions (the abstract gives changes and maxima)",
        "status": STATUS_ASSUMED,
        "caveat": _OTHER_PLANT + " Coal-plastic-wood pellets, not MSW.",
    },
    {
        "key": "mdpi_performance",
        "parameter": "cold-gas efficiency, LHV, tar and gas yield",
        "value_text": ("Cold-gas efficiency 59.3 % (air) → 68.6 % (O2-enriched air); LHV up to 9.32 MJ/Nm3; air/steam with olivine: tar −94.5 % "
                       "and gas yield 2.98 Nm3/kg against air with silica sand"),
        "numeric": [_n("cold-gas efficiency, air → O2-enriched air", 59.3, 68.6, "%"), _n("LHV", None, 9.32, "MJ/Nm3"),
                    _n("tar change, air/steam with olivine vs air with silica sand", -94.5, -94.5, "%"),
                    _n("gas yield, air/steam with olivine", 2.98, 2.98, "Nm3/kg")],
        "scale": "lab bubbling fluidised bed, 1–4 kg/h, 0.10 m ID",
        "feed": "pellets of 50 % brown coal, 30 % recycled polyolefin plastics, 20 % wood",
        "agent": "air, O2-enriched air, air/steam; silica sand and olivine bed",
        "source_title": "Sustainability 2023, 15(9), 7547 (title not given in the task file)",
        "source_url": "https://www.mdpi.com/2071-1050/15/9/7547",
        "what_the_page_does_not_state": "absolute compositions (the abstract gives these as changes or maxima); the cold-gas-efficiency definition is not given here",
        "status": STATUS_ASSUMED,
        "caveat": _OTHER_PLANT + " Changes and maxima, not absolute compositions; the basis of the cold-gas efficiency is not given.",
    },
    {
        "key": "bates_bench_bfb",
        "parameter": "ER, steam/biomass ratio, bed temperature, residence time, char build-up, naphthalene",
        "value_text": ("ER 0–0.157 (air runs 0, 0.052, 0.104, 0.157), steam/biomass ratio 1 (steam only) and 1.091→0.545 (air runs), bed 750–850 °C, "
                       "3 kg olivine, gas residence time 0.5–0.7 s in the bed and 4–30 s in the freeboard, char build-up \"may take several hours\"; "
                       "naphthalene 108–122 ppm"),
        "numeric": [_n("ER", 0, 0.157, "-"), _n("steam/biomass ratio, steam-only run", 1, 1, "unit not stated on the page"),
                    _n("steam/biomass ratio, air runs", 0.545, 1.091, "unit not stated on the page"), _n("bed temperature", 750, 850, "°C"),
                    _n("olivine bed", 3, 3, "kg"), _n("gas residence time in the bed", 0.5, 0.7, "s"), _n("gas residence time in the freeboard", 4, 30, "s"),
                    _n("naphthalene", 108, 122, "ppm")],
        "scale": "5 kWth bench-scale bubbling fluidised bed",
        "feed": "biomass",
        "agent": "steam only and air + steam, olivine bed",
        "source_title": "Bates et al., multi-scale models and experimental validation (title as given; year not confirmed)",
        "source_url": "https://www.osti.gov/servlets/purl/1364050",
        "what_the_page_does_not_state": "publication year; basis of the steam/biomass ratio; gas composition",
        "status": STATUS_ASSUMED,
        "caveat": _OTHER_PLANT + " Bench scale (5 kWth), olivine bed, biomass; year not confirmed.",
    },
    {
        "key": "vtt_sewage_sludge_parametric",
        "parameter": "temperature, ER and steam/fuel effects on gas composition",
        "value_text": ("Sewage sludge BFB: bed 650/750/850 °C, ER 0.2/0.3/0.4, steam/fuel 0.5/1/1.5, 36 experiments; stated trends: higher temperature raises "
                       "H2 and CO and lowers CO2 and CH4; ER 0.2 best for H2 and CO; higher steam/fuel favours H2; no numerical concentrations on the page"),
        "numeric": [_n("bed temperature", 650, 850, "°C"), _n("ER", 0.2, 0.4, "-"), _n("steam/fuel", 0.5, 1.5, "unit not stated on the page"),
                    _n("experiments", 36, 36, "-")],
        "trends": [
            {"id": "T_up", "variable": "temperature", "direction": "up", "raises": ["H2", "CO"], "lowers": ["CO2", "CH4"]},
            {"id": "ER_down", "variable": "ER", "direction": "down (0.2 best of 0.2/0.3/0.4)", "raises": ["H2", "CO"], "lowers": []},
            {"id": "steam_up", "variable": "steam/fuel", "direction": "up", "raises": ["H2"], "lowers": []},
        ],
        "scale": "bubbling fluidised bed (size not stated here)",
        "feed": "sewage sludge",
        "agent": "air and steam",
        "source_title": "Parametric study of sewage sludge gasification in air and steam e… (title truncated on the page)",
        "source_url": "https://cris.vtt.fi/en/publications/parametric-study-of-sewage-sludge-gasification-in-air-and-steam-e/",
        "what_the_page_does_not_state": "numerical gas concentrations, the basis of the steam/fuel ratio, the bed size, the full title",
        "status": STATUS_ASSUMED,
        "caveat": _OTHER_PLANT + " Directions only; sewage sludge, not MSW. Trends are for the ranges tested.",
    },
    {
        "key": "srf_lab_bfb",
        "parameter": "ER, temperature, H2 + CO, LHV, cold-gas efficiency",
        "value_text": ("Solid refuse fuel, lab BFB: ER 0.2–0.6, best at ER 0.4 and 900 °C; H2 + CO 72.53 %; LHV 14.43 MJ/Nm3; cold-gas efficiency 67.31 %; "
                       "basis of the gas percentages not stated"),
        "numeric": [_n("ER tested", 0.2, 0.6, "-"), _n("best ER", 0.4, 0.4, "-"), _n("best temperature", 900, 900, "°C"), _n("H2 + CO", 72.53, 72.53, "%"),
                    _n("LHV", 14.43, 14.43, "MJ/Nm3"), _n("cold-gas efficiency", 67.31, 67.31, "%")],
        "scale": "lab bubbling fluidised bed",
        "feed": "solid refuse fuel",
        "agent": "not stated in the task file",
        "source_title": "Springer article s12649-018-0431-6 (title not given in the task file)",
        "source_url": "https://link.springer.com/article/10.1007/s12649-018-0431-6",
        "what_the_page_does_not_state": "the basis of the gas percentages (dry or wet, N2-free or not), the gasifying agent in the task file",
        "status": STATUS_ASSUMED,
        "caveat": _OTHER_PLANT + " The basis of the gas percentages is not stated, so H2 + CO 72.53 % cannot be compared with a model fraction without a guess.",
    },
    {
        "key": "clg_5mwth_pilot",
        "parameter": "chemical looping gasification, temperatures, oxygen-to-fuel ratio, CH4, cold-gas efficiency, tar",
        "value_text": ("Chemical looping gasification, 5 MWth pilot, wood pellets, ilmenite: fuel reactor 850–980 °C, air reactor 900–1020 °C, "
                       "oxygen-to-fuel ratio 0.4–0.8, over 40 h continuous, CH4 5–10 vol %, cold-gas efficiency over 50 %, almost no tar"),
        "numeric": [_n("fuel reactor temperature", 850, 980, "°C"), _n("air reactor temperature", 900, 1020, "°C"), _n("oxygen-to-fuel ratio", 0.4, 0.8, "-"),
                    _n("continuous operation", 40, None, "h (over)"), _n("CH4", 5, 10, "vol %"), _n("cold-gas efficiency", 50, None, "% (over)")],
        "scale": "5 MWth pilot",
        "feed": "wood pellets",
        "agent": "ilmenite oxygen carrier (chemical looping), air reactor",
        "source_title": "ScienceDirect S0016236125021970 (title not given in the task file)",
        "source_url": "https://www.sciencedirect.com/science/article/abs/pii/S0016236125021970",
        "what_the_page_does_not_state": "any waste-derived feed; the basis of the CH4 vol %",
        "status": STATUS_ASSUMED,
        "caveat": _OTHER_PLANT + " Wood pellets, not waste; dual-reactor chemical looping, a different configuration from a single BFB.",
    },
    {
        "key": "suarez_almeida_transient",
        "parameter": "transient time scales of a fluidised-bed gasifier",
        "value_text": ("transient response can extend for more than an hour, attributed to the char inventory (validated against lab-scale transient tests); "
                       "optimised start-up can cut the transient by up to 75 %"),
        "numeric": [_n("transient response", 1, None, "h (more than)"), _n("transient cut by optimised start-up", None, 75, "%")],
        "scale": "fluidised-bed gasifier model, validated against lab-scale transient tests",
        "feed": "not stated in the task file",
        "agent": "not stated in the task file",
        "source_title": "Suárez-Almeida et al., Fuel 274, 2020",
        "source_url": "https://research.chalmers.se/en/publication/516472",
        "what_the_page_does_not_state": "individual time constants, the feed, the scale of the plant",
        "status": STATUS_ASSUMED,
        "caveat": _OTHER_PLANT + " Gives an order of magnitude for the char-inventory transient, not a time constant for any single model lag.",
    },
    {
        "key": "chalmers_devolatilisation_transient",
        "parameter": "devolatilisation and char accommodation time scales",
        "value_text": "Devolatilisation transient \"a few seconds\"; char accommodation \"minutes to hours\"; no specific time constants (simulation, no validation stated)",
        "numeric": [],
        "scale": "simulation",
        "feed": "not stated in the task file",
        "agent": "not stated in the task file",
        "source_title": "Chalmers research record 503301 (title not given in the task file)",
        "source_url": "https://research.chalmers.se/en/publication/503301",
        "what_the_page_does_not_state": "specific time constants, any validation",
        "status": STATUS_ASSUMED,
        "caveat": _OTHER_PLANT + " Qualitative time scales from a simulation with no validation stated; no number to compare with.",
    },
    {
        "key": "grasys_psa_vendor",
        "parameter": "PSA recovery, purity and pressure",
        "value_text": "PSA (vendor page): recovery up to 90 %, purity up to 99.999 %, pressure up to 5.5 MPa",
        "numeric": [_n("recovery", None, 90, "%"), _n("purity", None, 99.999, "%"), _n("pressure", None, 5.5, "MPa")],
        "scale": "vendor product page",
        "feed": "not stated",
        "agent": "not applicable",
        "source_title": "grasys.com, hydrogen adsorption product page",
        "source_url": "https://grasys.com/products/gas/hydrogen/adsorption",
        "what_the_page_does_not_state": "feed composition, the conditions at which the maxima hold",
        "status": STATUS_ASSUMED,
        "caveat": _OTHER_PLANT + " Vendor marketing, not independent; maxima, not typical values.",
    },
    {
        "key": "nrel_station_throughput_2015",
        "parameter": "hydrogen station throughput, 2015 data",
        "value_text": "Hydrogen stations, 2015 data: highest station average 35 kg/day; no hourly values in the text",
        "numeric": [_n("highest station average", None, 35, "kg/day")],
        "scale": "hydrogen fuelling stations, 2015 data",
        "feed": "not applicable",
        "agent": "not applicable",
        "source_title": "NREL report fy16osti/65485",
        "source_url": "https://www.nrel.gov/docs/fy16osti/65485.pdf",
        "what_the_page_does_not_state": "hourly values",
        "status": STATUS_ASSUMED,
        "caveat": _OTHER_PLANT + " A dispensing demand scale, not a gasifier quantity; 2015 data.",
    },
]

NOT_FOUND = [
    {"item": "gasifier temperature lag", "note": "no published value found"},
    {"item": "tail-gas recycle delay", "note": "no published value found"},
    {"item": "cooling-basin lag", "note": "no published value found"},
    {"item": "waste-derived chemical-looping gasification data",
     "note": "no readable source; the 5 MWth pilot used wood pellets"},
]

REQUIRED_FIELDS = ("key", "parameter", "value_text", "numeric", "scale", "feed", "agent", "source_title", "source_url",
                   "what_the_page_does_not_state", "status", "caveat")


def entry(key):
    for e in ENTRIES:
        if e["key"] == key:
            return e
    raise KeyError(key)


def trends():
    """Directional statements (entry key, trend dict) a script may test."""
    return [(e["key"], t) for e in ENTRIES for t in e.get("trends", [])]


def problems(e):
    """List of rule violations of one entry (empty = fine). Used by the tests."""
    out = [f"missing field {f}" for f in REQUIRED_FIELDS if f not in e]
    if out:
        return out
    if not str(e["source_url"]).startswith("https://"):
        out.append("source_url is not https://")
    if not str(e["status"]).startswith(STATUS_ASSUMED):
        out.append("status does not start with Assumed")
    if any(w in str(e["status"]) for w in ("Confirmed", "Measured", "Calculated")):
        out.append("status claims Confirmed / Measured / Calculated")
    if not str(e["caveat"]).strip():
        out.append("empty caveat")
    if "literature-informed" not in e["caveat"]:
        out.append("caveat does not say literature-informed")
    if e["numeric"] and not str(e["source_url"]).strip():
        out.append("numeric value without a source")
    return out
