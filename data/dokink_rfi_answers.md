# DOK-ING RFI Response — Real, Formal Answers

Received from DOK-ING d.o.o., via Ankica Kovac, in response to the 17-question
RFI in `data/rfi_dokink.md`. These are DOK-ING's own real, verbatim answers —
the first real (not assumed, not reconstructed) confirmation this project has
received for any of these 17 questions. Applied in `python/design_basis.py`
via `set_confirmed()`.

## Feedstock

1. **Feed rate.** Nominal capacity fixed at 1 tonne/day (1,000 kg/day) for
   continuous 24/7 operation, with operational turndown ~70–120%. Larger
   seasonal swings handled by parallel modular units. Other reactor sizes
   exist, up to 25 tonnes/day for the largest.
2. **Composition.** Moisture 5–15(20)%, Ash 5–15%, Volatile Matter >65%,
   Carbon >45%, Hydrogen >5%, LHV 15–20 MJ/kg (dry basis). Trace S/Cl
   captured via downstream scrubbing/dry gas cleaning.
3. **Feedstock form.** Pre-sorted and shredded (<20–30mm particle size) —
   plastic, dried sewage sludge, wood chips, textiles. No RDF/SRF
   pre-production needed. Pre-sorting handled by local waste
   utilities/MRFs before the Looper's inlet hopper.
4. **Supply.** Guaranteed, but system tolerates gaps via hot-standby state
   and accepts substitute feedstocks (RDF, waste biomass, textiles, dried
   sludge).
5. **Source.** Flexible by deployment site — single municipal utility,
   wastewater treatment facility (sludge), or local industrial/commercial
   waste streams.

## Hydrogen product

6. **H2 output.** ~50 kg/day from 1 tpd of standard high-calorific plastic
   waste, varying with feedstock C/H ratio and moisture.
7. **Purity.** 99.97% (ISO 14687 Grade D), suitable for mobility/fuel-cell
   vehicle use.
8. **Pressure.** PSA discharges at 3–10 bar. Multi-stage booster
   compression to 350/700 bar for mobility dispensing/tube trailers.
   Alternative: a liquid carrier storing H2 at room temperature/pressure
   also exists as an option.
9. **End use.** No fixed limitation — depends entirely on contracts and
   contracted prices.
10. **Co-products.** H2 is primary; CHP using excess heat/syngas is
    optional, not fixed. Ash residue recovered for construction
    applications (aggregate/brick). Carbon black recovered as a raw
    material.

## Site and infrastructure

11. **Utilities.** Grid power connection and water supply both available.
12. **Nearby infrastructure.** No.

## Regulatory and commercial

13. **Project driver.** Dual commercial/environmental model — gate fees
    for processing waste, plus revenue from green H2 sales, process heat,
    and upcycled mineral residues.
14. **RFNBO/green requirement.** Not required — but increases hydrogen's
    economic value/price if achieved.
15. **Jurisdiction/permits.** Holds a waste processing permit (specific
    jurisdiction not stated).
16. **Landfill diversion.** No general tonnage target — this phase
    specifically targets high-value contaminated waste streams (oiled
    plastic, contaminated construction packaging) that currently go to
    specialized processing or incineration (e.g., Vienna), not landfill.

## Project scope

17. **Budget.** No fixed capital cost goal or limit — the modular,
    factory-assembled design is inherently intended to minimize cost
    versus traditional large-scale plants.

---

# RFI 2 — short-form replies (received 2026-11-25)

DOK-ING's replies to the 10-question short form (`RFI2_short_form_DOK-ING-2.docx`), recorded verbatim. Appended at the end so the line
numbers cited above do not move. Only what is written here is DOK-ING-stated. Where the reply does not say something (basis of the
moisture, whether the char share includes ash, the syngas composition), the twin's value stays Assumed. The switchable basis built from these
replies is `python/rfi2_basis.py`; the default model is not changed by them.

1. **Gasifying agent.** During operation, waste feed is the only feed to the reactor. No gasifying agent is added. Nitrogen is used for
   inerting the reactor before waste feeding begins.
2. **Oxygen supply.** No air separation unit is used to supply oxygen to the reactor. Nitrogen is used for inerting before feeding begins.
3. **Carrier loop.** There is no oxygen carrier loop or separate air reactor. The tubular reactor is heated externally by electric heaters.
4. **Air and steam flows.** No air or steam is added to reactor. The corresponding inlet flows are 0 Nm³/h for air and 0 kg/h for injected steam.
5. **Feed basis.** Feed of up to 15% moisture can be used and the feed is not dried.
6. **External energy.** Around 100 kW of electrical energy is used for heating and propulsion of the facility.
7. **PSA recovery.** DOK-ING facility does not yet separate hydrogen from the syngas using PSA.
8. **Carbon black or char.** 40 to 50% of the 41.67 kg/h feed is expected as carbon black / char.
9. **Ash and tar.** Ash is separated at the reactor exit and pulled out with spindle in the separate container.
10. **Preheat temperatures.** Preheat temperatures do not apply because neither stream is supplied to the reactor. Feed with a moisture
    content of up to 15% can be fed directly into the reactor without preheating.
