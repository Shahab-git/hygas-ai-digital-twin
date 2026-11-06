# HYGAS-AI: model values vs published MSW/RDF gasification data (first benchmark)

Date: 2026-11-06. Repository state read: `main` at `6b010de` (PR #28 merged). Placed in the repository on 2026-11-06 as the G5-10 evidence; the text below is the screen as written then (figures about the model are as of `6b010de`; the carbon-black and feed-basis wording predates P0-FB2).

**Status.** Read-only research. No repository file, default or registry value was changed. This is evidence for the harmonisation decision (P0-FB2). **It is a screen, not a validation of the model, and not DOK-ING data.** All published values come from other plants and other feeds and rank at best as *Assumed (literature-informed)*.

**How to read it.**
- *Published* = number as the source reports it.
- *(calc)* = my arithmetic on the source's numbers.
- *Verdict* = where the model value sits relative to the sources I read: **Inside**, **Edge**, **Outside** or **No evidence**. With 2 to 7 sources per parameter this is a screening result, not a proof.
- Sources are read through a page-extraction tool, not from the original PDFs. Secondary sources (reviews) are marked [S]. Values read from charts are not used.

## 1. Summary

| # | Model value (repo) | Published values | Verdict |
|---|---|---|---|
| 1 | Inlet moisture 10 % as-received (FE-005, Assumed). DOK-ING: 5-15(20) %, basis not stated | Pilot SRF 3.7-9.1 % a.r. [2]; RDF 14.9 % a.r. [4]; Lahti SRF 15-25 % [7,S] | **Inside** (low-mid). Depends on DOK-ING's pre-processing |
| 2 | Ash 10 % dry (Assumed). DOK-ING: 5-15 % | Dry MSW 7.76 % dry [3]; MSW cubes 2.6 % dry [6]; pilot SRF 18.5-20.4 % a.r. [2]; RDF 19.1 % a.r. = 22.4 % dry (calc) [4]; Lahti about 10 % [7,S] | **Inside**, but the sources span 2.6-22 %: a weak constraint |
| 3 | Dry ash-free C/H/O/N = 50/6/43/1 % | daf (calc): C 59-62, H 8.6-10, O 26-31 for three prepared fuels [3][4][6]; C 51.5, H 6.4, O 41 for 1974 household refuse [8] | **Outside** the prepared fuels (C low, O high); matches old raw refuse. Against DOK-ING's stated minima (C >45 %, H >5 %, dry basis): H passes (5.4 % dry incl. ash, calc); C is exactly 45.0 % dry incl. ash (calc), i.e. at the limit, not above it |
| 4 | Carbon conversion 0.90; Monte Carlo range 0.85-0.98 | 93.75 % (MSW pilot, ER 0.25) [6]; 63.7-84.9 % across lab/pilot MSW studies [1,S] | **Inside**, upper half. The 0.85-0.98 range excludes the lower reported values |
| 5 | Carbon black 5 % of feed (static rule; live engine derives it from unconverted carbon) | No source gave a char or carbon-black yield in the text I could read | **No evidence** |
| 6 | Air equivalence ratio 0.25 (Assumed) | Optimum ER 0.25 in MSW pilot [6]; 0.24-0.36 in SRF pilot [2]; 0.21-0.36 and 0.25-0.30 in RDF studies [1,S] | **Inside** (well supported) |
| 7 | Syngas N2 about 40 vol % (live, air-blown); registry "Expected" 10 vol % | 61.7 vol % N2 (mean over the MSW pilot's air runs; ER schedule 0.2-0.4, optimum 0.25) [6]; air-blown bubbling-bed gas heating value 3.7-8.4 MJ/Nm3 [1,S] | **Registry 10 % is Outside** for any air-blown case. Live 39.6 % is Inside the "heavily diluted" regime and lower than the one measured value |
| 8 | Steam-to-feed 0.4 kg/kg (Assumed) | Steam/RDF 0.4-2.67 in rotary kiln, steam only [5]; steam-to-MSW 0.77-1.33 in catalytic studies [1,S] | **Edge** (lower bound) |
| 9 | Gasifier temperature 950 degC (registry value tied to earlier project models) | Fluidised beds 700-1000, bubbling 800-1000 [1,S]; Lahti 850-900 [7,S]; MSW pilot optimum about 725 [6]; RDF pilots 700-800 [4], 700-950 [2] | **Edge** (upper bound) |
| 10 | Feed sulfur 200 ppm, chlorine 150 ppm (Assumed; not wired into the model) | S 0.2 % = 2000 ppm and Cl 0.4 % = 4000 ppm as received [4]; S 0.26 % dry [3]; S 0.08 % [6]; S 0.20 % [8] | **Outside** (4-27 times lower than every feed read) if the figures mean mass in the feed. Definition unclear |
| 11 | H2 yield 78 g/kg feed with tail-gas regasify; 56 g/kg heat_only; DOK-ING about 50 (calc from 78.0, 55.7 and 50 kg/day over 1,000 kg/day) | 24.8-141 g H2/kg MSW across studies; semi-industrial 81.7 g/kg at 900 degC [1,S] | **Edge** (regasify at the top of the range even though air-blown) |

## 2. Detail and caveats per parameter

**1-2. Moisture and ash.** The repo's 10 %/10 % sit inside what the sources show, but the sources do not narrow them: moisture 3.7-25 %, ash 2.6-22 % dry, depending on how the waste was sorted and dried. What this supports is *keep 10 % and 10 % as labelled assumptions with these spans recorded*. It does not support any one value. No source I read gives the moisture of raw, unprocessed MSW, so the 10 % is only checked for prepared feed.

**3. Composition.** The calc is C/(100 - ash - moisture) on each source's own numbers: dry MSW sample [3] C 59.4, H 8.6, O 30.8, N 0.94; RDF [4] C 62.1, H 8.6, O 26.5, N 1.8; MSW cubes [6] C 62.4, H 10.0, O 27.5 (cubes are plastic-rich: ash 2.6 %); household refuse 1974 [8] C 51.5, H 6.4, O 41.1, N 0.6. The model's 50/6/43/1 corresponds to the oldest source. For modern prepared fuels the carbon and hydrogen are higher and the oxygen lower, which would raise the heating value and the hydrogen potential. This is the largest *direction-of-bias* finding in the screen, but DOK-ING stated only minima (C >45 %, H >5 %, dry basis, and not whether that is with or without ash). On a dry-including-ash basis the model's C is 45.0 % (0.90 x 50 %), at the stated limit; on a dry ash-free basis it is 50 %. So the model sits at the low end of what DOK-ING stated, not outside it. A sensitivity run with C about 60, H about 8.6, O about 27 would quantify it (not done; it would need a model run).

**4. Carbon conversion.** The 93.75 % comes from one pilot (about 100 kg/h, segregated MSW cubes, air, ER 0.25, about 725 degC) [6]. The 63.7-84.9 % values come from a secondary review of lab and pilot studies [1]. The repo's Monte Carlo range (0.85-0.98) therefore leaves out values that the literature reports. The repo cites Basu (2010) for it; I did not check that reference.

**5. Carbon black.** The unconverted carbon at CCE 0.90 is 1.69 kg C/h (calc: 33.753 x 0.50 x 0.10), the 5 % rule gives 1.875 kg/h on the live feed, and the engine's derived value is 2.013 kg/h. The MSW pilot dissertation [6] weighed and analysed its char but the char results were not in the text I could read. Follow-up: obtain that chapter.

**7. Nitrogen.** The registry's 10 vol % N2 cannot be reached by air gasification at ER 0.25. In the measured MSW pilot the mean was 61.7 vol % (net heating value 7.94 MJ/Nm3, cold gas efficiency 59 %) [6]. This supports the earlier finding that the registry "Expected" table describes steam- or oxygen-blown operation. It does not say which the plant uses. Basis (wet or dry gas) is not stated for the repo's 39.6 %, so the two numbers may not be comparable.

**8-9. Steam and temperature.** Both are at the edge of the published ranges, not outside them. Both would normally be held as Assumed with a sensitivity.

**10. Sulfur and chlorine.** If "200 ppm" means mass of S in the feed, it is 0.02 wt %, against 0.08-0.26 wt % S and 0.4 wt % Cl in the feeds read. If it means H2S in the gas, then 0.2 wt % S in 37.5 kg/h feed is about 0.075 kg S/h (about 2.3 mol/h), which would be roughly 500-1,000 ppmv in 50-100 Nm3/h of gas (calc, assuming all S as H2S). Either way 200 ppm looks low, but the repo's label is ambiguous. The parameter is flagged `wired_in: False`, so it changes no current output; it matters for gas-cleaning sizing.

**11. Hydrogen yield.** Per-kg values in the literature use different feeds, bases (rarely stated), catalysts and steam ratios; the comparison only shows plausibility. Air-only runs reported far lower yields than steam/catalyst runs (about 32 g/kg at ER 0.24 [1,S]). The live 78 g/kg at the top of the range for an air-blown case supports the earlier concern about the tail-gas regasify behaviour.

## 3. What this means for the harmonisation decision

1. **Feed basis (41.67 / 37.503 / 33.753).** Nothing here contradicts the 10 % moisture and 10 % ash assumptions, and nothing here narrows them. The sources span too much. The basis question stays with DOK-ING; the project can carry them as labelled assumptions.
2. **Items to raise with the owner as candidates for review (no change made):** the dry ash-free composition (row 3), the carbon-conversion Monte Carlo range (row 4), the feed S/Cl definition and value (row 10).
3. **Items to leave as labelled assumptions:** ER 0.25, steam 0.4, 950 degC (rows 6, 8, 9), with the sensitivity already in the model.
4. **No evidence yet:** carbon black (row 5).

## 4. Limits of this screen

- Four to eight sources were read, almost all through a page-extraction tool. Several are abstracts or partial texts. None was cross-checked against its original paper.
- Feeds differ strongly (plastic-rich cubes, sorted residue, rotary-kiln steam gasification, oxygen-blown with plasma). Reactor scales run from lab to about 500 kWth.
- Some values appear in a source's abstract and body with different numbers; I used body tables where I could and did not use values that conflicted.
- A wood-waste lab study and a wood pilot that surfaced in the search were excluded as not MSW or RDF.
- Nothing here is DOK-ING-specific. Their plant data, when shared, would replace these assumptions.

## 5. Sources

[1] Hydrogen from waste gasification (review). MDPI, Hydrogen 5(1):6. https://MDPI.com/2673-4141/5/1/6  [secondary; Tables 3-4 not read]
[2] Pilot-scale bubbling fluidised bed gasification of SRF (FluGas, 100 kg/h). https://core.ac.uk/download/185670371.pdf  [proximate/ultimate in text; gas results only as charts, not used]
[3] Uler-Zefikj et al., Characterization of Municipal Solid Waste as Potential Fuel for Energy Needs. Materials 2025, 18, 2103. https://doi.org/10.3390/ma18092103
[4] Materazzi et al., Production of BioSNG from waste derived syngas: pilot plant operation and preliminary assessment (UCL). https://discovery.ucl.ac.uk/id/eprint/10059154/1/Materazzi_Manuscript%20Clean%20%28with%20Fig%29.pdf
[5] Molino et al., Steam Gasification of Refuse-Derived Fuel in a Rotary Kiln Pilot Plant: Experimental Tests. Chemical Engineering Transactions 32 (2013). https://www.aidic.it/cet/13/32/057.pdf
[6] Maglinao, Development of a Segregated Municipal Solid Waste Gasification System for Electrical Power Generation. PhD dissertation, Texas A&M University, 2013. https://core.ac.uk/download/17050345.pdf  [char tables not in the text read]
[7] Waste Gasification Technologies: A Brief Overview. https://www.mdpi.com/2813-0391/1/1/11  [secondary; Kymijarvi II, Pio 2020, Nobre 2020, Hervy 2019 cited there]
[8] Alter, Ingle and Kaiser, Chemical Analyses of the Organic Portions of Household Refuse. Solid Wastes Management 64(12), 1974. https://wtert.org/wp-content/uploads/2020/10/Incinerator-and-Solid-Waste-Technology-43.pdf  [1972 samples, Delaware]
[9] Arena, Process and technological aspects of municipal solid waste gasification. A review. Waste Management 32 (2012). https://www.osti.gov/biblio/21612953  [abstract only; no numbers used]

## 6. Owner dispositions (G5-10, 2026-11-06)

The owner accepted the proposed dispositions below, on the principle: keep the numbers unchanged and make the evidence visible. **No value, default or registry row was changed.** Allowed dispositions: fix, sensitivity run, label, accept.

| Row | Verdict | Disposition |
|---|---|---|
| 1 Moisture 10 % | Inside | accept (label Assumed kept) |
| 2 Ash 10 % | Inside | accept (label Assumed kept) |
| 3 Dry ash-free composition 50/6/43/1 | Outside modern prepared fuels | label: Assumed, matches old raw refuse, outside prepared fuels; a read-only sensitivity run may follow later |
| 4 Carbon conversion 0.90, range 0.85-0.98 | Inside, range excludes lower reported values | label; widening the range is a Phase 1 change |
| 5 Carbon black 5 % | No evidence | label: No evidence, Assumed; the char chapter of source [6] is still to be obtained; DOK-ING asked in RFI #2 (short form) |
| 6 ER 0.25 | Inside | accept |
| 7 Syngas N2 (registry 10 %) | Registry Outside for air-blown | covered by the cross-module list (G5-07, rows 1-5), pending DOK-ING |
| 8 Steam 0.4 | Edge | accept (existing sensitivity) |
| 9 Temperature 950 degC | Edge | accept (existing sensitivity) |
| 10 Feed S 200 ppm / Cl 150 ppm | Outside if mass in feed; definition unclear | label as ambiguous; ask DOK-ING what the figure means |
| 11 H2 yield 78 g/kg | Edge | covered by the cross-module list (G5-07, row 7) |

Every verdict stays Assumed (literature-informed). None of this validates the model.
