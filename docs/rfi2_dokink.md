# RFI #2 for DOK-ING: gasifier agent, feed and heat integration (MSW-H2)

Prepared by Shahab, University of Zagreb, for the HYGAS-AI digital twin of the MSW-H2 1 tpd plant. Dated 30 October 2026; section G added 2 November 2026. Source of truth for the numbering: the Claude Docs document of the same name. Questions are quoted as written there; an answer is Confirmed only with a dated DOK-ING source line.

## A. Gasifying agent and oxygen supply (highest priority)
1. Which agent is the design basis: air, oxygen-enriched air, oxygen plus steam, steam only, or a chemical-looping oxygen carrier?
2. If oxygen or enriched air: where does it come from (air separation unit, bottled, other) and what is its energy demand?
3. If a carrier: which material, circulation rate, oxygen transfer per pass, and does the air reactor deliver heat to the gasifier?
4. Are the GA-003 figures (air 60 Nm3/h, steam 15 kg/h) design values or estimates? The twin computes about 51 Nm3/h of air at ER 0.25.
5. What is the design gas composition at the gasifier outlet (dry basis), even approximate? The registry shows about 10 % N2; we cannot reproduce that with air.

## B. Feedstock
6. What is the plastic-waste composition by type (PE, PP, PS, PET, PVC, other), with moisture and ash?
7. Is there a typical ultimate analysis (C, H, O, N, S, Cl) for the real feed, and its sulphur and chlorine content?
8. What is the design feed rate, dry or as received, and the expected variability?

## C. Heat integration and steam
9. What fuels the steam generator and the air preheater, and is the PSA tail gas burned for heat?
10. Is there heat recovery from the syngas cooler, the shift reactor or the carrier loop, and into what?
11. What are the external energy inputs (electricity, gas) at design point?

## D. Hydrogen output basis
12. Is the ~50 kg/day gross at the PSA outlet, or net after the plant's own hydrogen use? Does it assume continuous operation (hours per day, availability)?
13. Is the PSA recovery (the twin uses a correlation) a vendor figure?

## E. Solid by-products
14. What is the expected carbon-black or char flow? The twin derives about 2.0 kg/h from conversion 0.90; the GA-008 datasheet gives 1.88 kg/h at an earlier 37.5 kg/h design point and a capacity of 3 kg/h.
15. How is ash split between bed drain, cyclone and fly ash, and what is tar handling?

## F. Operation and dynamics (optional)
16. Typical start-up time to steady gas quality, and any known response times of gas composition or bed temperature to a feed change.
17. Gasifier operating temperature at design point (the twin uses 950 degrees C from an earlier project dashboard, not from you).

## G. Gasifier design values and heat integration (added 2 November 2026)
18. What are the gasifier design pressure (the twin uses 500 mbar(g)) and the design residence time (the twin uses 20 min)?
19. What are the air preheat temperature (the twin uses 200 degrees C) and the steam temperature (the twin uses 350 degrees C)?
20. What fuel does the steam generator burn today, and is there a burner or boiler behind the PSA tail gas?
21. What are the duty and the outlet temperature of the gas cooler, and is there a dry cooler ahead of the quench (GC-004)?
22. What are the stack temperature and the excess air at the burner or boiler, if there is one?
23. Is the heat of the water-gas shift reaction used, and at what temperature level?
24. How is the cleaned gas heated from about 40 degrees C to 350 degrees C before the shift reactor?

## What we will do with the answers
Every value you confirm will be stored as Confirmed and will never be overwritten by a model result. Anything not answered stays labelled Assumed or Missing in the twin and in any publication.
