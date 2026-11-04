"""
Question references of the design-basis ledger (task A3b, section 3). Nothing here is imported by the engine, the runtime or the app.

`upgrade_question` of a ledger row is a LIST of references, each one of three forms:

  RFI2-<n>                        question n (1..24) of docs/rfi2_dokink.md (the second RFI to DOK-ING, sent 30 October 2026, section G added 2 November 2026);
  RFI1-<n>                        question n (1..17) of data/rfi_dokink.md (the first RFI, the 17 questions in python/design_basis.py);
  master_open_questions:<s>.<n>   an item of docs/master_open_questions.md: `1.<n>` is item n of Section 1 (DOK-ING), `3.<n>` is item n of the list of specific items of Section 3.

A reference must point to a question that exists (`problems()`; tests/test_design_basis_ledger.py fails otherwise). A row is mapped to an RFI question only when the question really asks for
that quantity (RFI_MAP, with the reason). Where two questions apply, both are listed and none is chosen. Rows that were considered and left empty are in CONSIDERED, with the reason.
The question text is always read from the file, never copied here.
"""
import os
import re

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RFI2_FILE, RFI1_FILE, MASTER_FILE = "docs/rfi2_dokink.md", "data/rfi_dokink.md", "docs/master_open_questions.md"
REF_RE = re.compile(r"^(?:RFI2-(\d+)|RFI1-(\d+)|master_open_questions:([13]\.\d+))$")


def _read(rel):
    with open(os.path.join(_ROOT, rel), encoding="utf-8") as f:
        return f.read().replace("\r\n", "\n")


def _numbered(rel):
    out = {}
    for line in _read(rel).split("\n"):
        m = re.match(r"^\s*(\d+)\.\s+(\S.*)$", line)
        if m:
            out[int(m.group(1))] = m.group(2).strip()
    return out


def rfi2_questions():
    """{n: text} of docs/rfi2_dokink.md (24 numbered questions, sections A to G)."""
    return _numbered(RFI2_FILE)


def rfi1_questions():
    """{n: text} of data/rfi_dokink.md (the 17 questions DOK-ING was sent)."""
    return _numbered(RFI1_FILE)


def master_items():
    """{'1.n': heading} for the numbered items of Section 1 (DOK-ING) and {'3.n': first line} for the specific items listed in Section 3 of docs/master_open_questions.md."""
    text = _read(MASTER_FILE)
    s1 = text[text.index("## Section 1"):text.index("## Section 2")]
    out = {f"1.{m.group(1)}": m.group(2).strip() for m in re.finditer(r"^### (\d+)\. (.+)$", s1, re.M)}
    a = text.index("Specific, already-identified items")
    b = text.index("\n---", a)
    out.update({f"3.{m.group(1)}": re.sub(r"\*\*", "", m.group(2)).strip() for m in re.finditer(r"^(\d+)\. (\*\*.+?\*\*)", text[a:b], re.M)})
    return out


def text_of(ref):
    """The question text a reference points to, or None."""
    m = REF_RE.match(ref)
    if not m:
        return None
    if m.group(1):
        return rfi2_questions().get(int(m.group(1)))
    if m.group(2):
        return rfi1_questions().get(int(m.group(2)))
    return master_items().get(m.group(3))


def problems(refs):
    """References that are malformed or point to a question that does not exist. Empty list = fine."""
    return [r for r in refs if text_of(r) is None]


# tag -> ([references], why this question asks for that quantity). Applies to every ledger row with that tag (a quantity held in two places has two rows).
RFI_MAP = {
    "GA-001.T_gasifier_C": (["RFI2-17"], "RFI2-17 asks the gasifier operating temperature at design point and quotes the twin's 950 degC"),
    "GA-003.steam_flow_design_kg_h": (["RFI2-4"], "RFI2-4 asks whether the GA-003 figures (air 60 Nm3/h, steam 15 kg/h) are design values or estimates"),
    "GA-004.air_preheat_C": (["RFI2-19"], "RFI2-19 asks the air preheat temperature and quotes the twin's 200 degC"),
    "GA-004.steam_T_C": (["RFI2-19"], "RFI2-19 asks the steam temperature and quotes the twin's 350 degC"),
    "PLANT.energy_balance_air_preheat_temperature_C": (["RFI2-19"], "the energy balance's air preheat input is the quantity RFI2-19 asks for (200 degC)"),
    "PLANT.energy_balance_steam_temperature_C": (["RFI2-19"], "the energy balance's steam temperature input is the quantity RFI2-19 asks for (350 degC)"),
    "GA-001.tail_gas_mode": (["RFI2-9", "RFI2-20"], "the switch is whether the PSA tail gas is burned for heat (RFI2-9) or sits behind a burner or boiler (RFI2-20); both questions ask it, none is chosen"),
    "GA-001.agent_air_o2_fraction": (["RFI2-1"], "RFI2-1 asks which agent is the design basis; the air fraction is the label of the 'air' agent"),
    "GA-001.agent_o2_fraction": (["RFI2-1", "RFI2-2"], "RFI2-1 asks whether the design agent is enriched air or oxygen; RFI2-2 asks where the oxygen comes from; the O2 fractions of the study agents are not chosen from an answer"),
    "GA-001.agent_er_override": (["RFI2-1"], "RFI2-1 asks whether the design agent is steam only (no oxidant)"),
    "GA-001.agent_steam_override": (["RFI2-1"], "RFI2-1 asks the design agent; the 0.8 steam-to-feed of the steam_only_0.8 agent is a study value"),
    "GA-001.gasifying_agent": (["RFI2-1", "RFI2-2", "RFI2-3"], "RFI2-1 asks which agent is the design basis (air, enriched air, oxygen plus steam, steam only, carrier); RFI2-2 and RFI2-3 ask the oxygen source and the carrier; the switch is not chosen"),
    "GA-001.tau_T_s": (["RFI2-16"], "RFI2-16 asks the response time of the bed temperature to a feed change"),
    "GA-001.tau_gas_s": (["RFI2-16"], "RFI2-16 asks the response time of the gas composition to a feed change"),
    "GA-008.capacity_kg_h": (["RFI2-14"], "RFI2-14 quotes the GA-008 datasheet capacity of 3 kg/h and asks the expected carbon-black or char flow"),
    "GA-008.nominal_kg_h_at_old_design": (["RFI2-14"], "RFI2-14 quotes the GA-008 1.88 kg/h at the earlier 37.5 kg/h design point"),
    "PLANT.heat_gas_cooler_outlet_c": (["RFI2-21"], "RFI2-21 asks the duty and the outlet temperature of the gas cooler"),
    "PLANT.heat_stack_temperature_c": (["RFI2-22"], "RFI2-22 asks the stack temperature at the burner or boiler"),
    "PLANT.heat_excess_air_ratio": (["RFI2-22"], "RFI2-22 asks the excess air at the burner or boiler"),
    "UNC.feed_sulfur_ppm": (["RFI2-7", "RFI1-2"], "RFI2-7 asks the sulphur content of the real feed; RFI1-2 asked the S content in the first RFI (no sulphur value was given); both apply, none is chosen"),
    "UNC.feed_chlorine_ppm": (["RFI2-7", "RFI1-2"], "RFI2-7 asks the chlorine content of the real feed; RFI1-2 asked the Cl content in the first RFI (no chlorine value was given); both apply, none is chosen"),
}

# rows with a nearby question that was NOT mapped: tag -> (the questions considered, why not). An answer to them would inform the row, but they do not ask for that quantity.
CONSIDERED = {
    "PLANT.heat_recovery_gas_cooler": (["RFI2-10", "RFI2-21"], "RFI2-10 asks whether heat is recovered from the syngas cooler and into what, RFI2-21 the duty: neither asks the recovered fraction (0.7)"),
    "PLANT.heat_recovery_wgs": (["RFI2-10", "RFI2-23"], "RFI2-10 and RFI2-23 ask whether the shift heat is used and at what level, not the recovered fraction (0.7)"),
    "PLANT.heat_recovery_flue": (["RFI2-22"], "RFI2-22 asks stack temperature and excess air, not the recovered fraction (0.8)"),
    "GC-004.inlet_temperature_C": (["RFI2-21"], "RFI2-21 asks whether a dry cooler stands ahead of the quench, which would change this inlet temperature, but it does not ask the quench inlet temperature"),
    "PLANT.audit_quench_inlet_temperature_C": (["RFI2-21"], "same as GC-004.inlet_temperature_C"),
    "GC-004.outlet_temperature_C": (["RFI2-21"], "RFI2-21 asks the GAS COOLER outlet temperature; GC-004 is the quench tower"),
    "GC-004.quench_out_C": (["RFI2-21"], "same as GC-004.outlet_temperature_C"),
    "HB-001.inlet_temperature_C": (["RFI2-24"], "RFI2-24 asks HOW the cleaned gas is heated from about 40 to 350 degC; it takes the 350 degC as given"),
    "PLANT.audit_vent_and_knockout_temperature_C": (["RFI2-24"], "RFI2-24 asks how the gas is heated to the shift reactor, not the knock-out temperature"),
    "GA-001.tau_conv_s": (["RFI2-16"], "RFI2-16 asks response times of gas composition and bed temperature; the carbon-conversion time constant is neither"),
    "GA-001.steam_to_feed_kg_kg": (["RFI2-4", "RFI2-1"], "RFI2-4 asks about the steam FLOW 15 kg/h and RFI2-1 about the agent; the ratio to feed (0.4) is the twin's input, not asked"),
    "GA-001.carbon_conversion": (["RFI2-14"], "RFI2-14 asks the carbon-black flow; the conversion (0.90) is how the twin derives it, not what is asked"),
    "GA-001.carbon_black_fraction_legacy": (["RFI2-14"], "a mass fraction of dry feed; RFI2-14 asks a flow in kg/h"),
    "GA-001.unconverted_C_to_carbon_black": (["RFI2-14", "RFI2-15"], "RFI2-14 and RFI2-15 ask the flows and the ash split, not this carbon split"),
    "GA-001.ch4_carbon_fraction": (["RFI2-5"], "RFI2-5 asks the design gas composition; the CH4 share of carbon is a model parameter that composition would inform, not the quantity asked"),
    "GC-008.h2s_inlet_ppm": (["RFI2-5", "RFI2-7"], "a gas concentration; RFI2-7 asks the feed sulphur and RFI2-5 the gas composition, neither the H2S inlet"),
    "FE-003.min_kg_h": (["RFI2-8", "RFI1-1"], "RFI2-8 and RFI1-1 ask the design feed rate and its variability; this is the feeder's minimum rate"),
    "FE-003.max_kg_h": (["RFI2-8", "RFI1-1"], "same as FE-003.min_kg_h"),
    "HB-006.psa_K1": (["RFI2-13"], "RFI2-13 asks whether the PSA recovery is a vendor figure; K1 is the coefficient of the twin's recovery correlation, not the recovery"),
    "HB-006.psa_target_calibration": (["RFI2-13"], "same as HB-006.psa_K1"),
    "AI-001.illustrative_availability_fraction": (["RFI2-12"], "RFI2-12 asks the plant's availability for the hydrogen output basis; this is an illustration for the AI module"),
    "HB-011.rated_power_kw": (["RFI2-11"], "RFI2-11 asks the external energy inputs at design point; this is the electrolyser's rated power, an equipment rating"),
}
