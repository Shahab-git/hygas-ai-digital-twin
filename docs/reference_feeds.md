# Reference feeds: published analyses and a heat-balance comparison across feeds

Written 2026-10-30 on `origin/main` 9f4a0bd (branch `reference-feeds`). Published analyses of plastics, textiles, an RDF and two sewage sludges are stored as a labelled reference layer, and the existing closure / energy
functions are run across the feeds the engine can take. **The default feed (C/H/O/N 0.50/0.06/0.43/0.01 dry ash-free, ash 0.10, a wood-like stand-in) is unchanged**, as is every default, Confirmed value, the registry, `SharedPlantState`, the engine API, the runtime,
the dynamics layer, the what-if tab, the workflows and `requirements.txt`. The reference layer (`python/reference_feeds.py`) is not read by the engine, the app or the uncertainty module. Offline throughout: in-memory fake store, no database, no network, the real `secrets.toml` never read.

Files: `python/reference_feeds.py`, `tests/test_reference_feeds.py` (14 tests, 9 of 9 mutants caught), `scripts/run_feed_comparison.py` (writes `outputs/feeds/feed_comparison.md` and `.csv`, git-ignored; about 3 minutes).

## 1. How a feed enters the engine (item A)

- **Composition input.** `_input_feedstock_composition` (`python/ga001_gasifier_model.py:571`) returns dry ash-free mass fractions `{"C","H","O","N"}` built from the module constants `FEEDSTOCK_*_FRACTION` (:193-196), status Assumed. It is consumed by `ga001_model` (:767) and the oxygen-carrier estimate (:994) through `get_input(("GA-001-INPUT","feedstock_composition"))`. **It can be overridden through the normal input mechanism** (`build_live_snapshot(overrides={key: fn})`); nothing checks that the fractions sum to 1 (only the module constants are asserted at import, :197-199), so the script renormalises.
- **Ash is not an input.** `ASH_FRACTION = gasifier_mass_balance.ASH_FRACTION` (:211, 0.10) is a module constant applied to every feed in `elemental_atomic_ratios` (:240). A feed with another ash content cannot be represented through the inputs.
- **Sulphur and chlorine are not carried.** Only C, H, O, N exist; GC-008 / GC-009 use fixed ppm (Assumed) not tied to the feed. S, Cl, and any daf mass the analysis does not report are dropped and C/H/O/N renormalised.
- **The DOK-ING cross-check** (`feedstock_composition_dokink_cross_check`, :531) compares the MODULE constants (C 50 %, H 6 %, ash 10 %) with DOK-ING's floors and ash band, not an overridden input. `balance_audit.feedstock_lhv_estimates()` and the "model composition" LHV case of `(GA-001, EnergyBalance)` also use the default constants, so for another feed they describe the default; the comparison script therefore uses each feed's own LHV.
- **Basis (A2), confirmed.** The model uses dry ash-free C/H/O/N plus an ash fraction of the total dry feed: `n_C = (1 - ash) x C_daf x 1000 / M_C` (:246). A feed's energy in the model is therefore `LHV_daf x (1 - 0.10)` per kg of model dry feed.
- **Cannot be taken (NOT TESTABLE):** RDF (ash 25.2 % dry, S, Cl), both sewage sludges (ash 36.5 / 44.2 %; the page's O is "by difference" and apparently includes the ash, so no daf C/H/O/N exists), PVC alone (Cl 55 % daf would be dropped, leaving 44.5 % of the mass). PVC appears only inside the illustrative blend M1, where 5.2 % of the dry mass (the Cl) is dropped.

## 2. What is stored, and what is missing (item B)

Stored analyses carry the status "Assumed (literature-informed)": other studies' values, not DOK-ING's. Everything computed here is "Calculated" with its formula: dry basis `X_dry = X_daf x (1 - Ad/100)` (RDF: `X_dry = X_ad / (1 - moisture/100)`, HHV in kcal/kg x 4.184 kJ/kcal); `LHV = HHV - 2.442 x 9 x H_dry/100 x 1000` kJ/kg (2.442 MJ/kg = latent heat of water at 25 degC);
stoichiometric polymers from the atomic masses 12.011 / 1.008 / 16.00 (PE and PP CH2, PS CH, PET C10H8O4): a cross-check against the literature means (PE 85.63 % C stoichiometric against 85.59 % stated), not a source. The mixed-plastic blend M1 (40 % PE, 25 % PP, 15 % PS, 10 % PET, 10 % PVC by mass) is an illustrative `Assumed` mix for sensitivity only, not DOK-ING data.
**Missing:** wood (no source opened, nothing added from memory), the Chalmers cotton / polyester thesis (abstract only, no values), Moliner et al., Energies 17(5) 1206 (not readable: NOT VERIFIED). The Werle sludge O-by-difference oddity is flagged in the caveat, not corrected.

### 2.1 Stored entries (as stated)

| key | material | basis | values | source | status | the page does not state | caveat |
|---|---|---|---|---|---|---|---|
| zhou_pe | polyethylene (PE) | Ad dry; C/H/O/N(/Cl) dry ash-free; HHV dry (kJ/kg) | Ad_pct 0.33; C_daf_pct 85.59; H_daf_pct 14.15; O_daf_pct 0.07; N_daf_pct 0.12; HHV_d_kJ_kg 42845 | Zhou et al., J. Air & Waste Manage. Assoc. 64(5), 2014, 597-616 (literature means across the studies it cites) -- https://www.awma.org/files/2020Stern.pdf | Assumed (literature-informed) | volatile matter, fixed carbon, sulphur (not in the values given to this task) | literature-informed Assumed: another plant / study, not DOK-ING's, not validated for GA-001. Table 9 literature mean; the paper gives no mixed-MSW ultimate analysis. |
| zhou_pp | polypropylene (PP) | Ad dry; C/H/O/N(/Cl) dry ash-free; HHV dry (kJ/kg) | Ad_pct 0.44; C_daf_pct 85.02; H_daf_pct 13.93; O_daf_pct 0.96; N_daf_pct 0.08; HHV_d_kJ_kg 46004 | Zhou et al., J. Air & Waste Manage. Assoc. 64(5), 2014, 597-616 (literature means across the studies it cites) -- https://www.awma.org/files/2020Stern.pdf | Assumed (literature-informed) | volatile matter, fixed carbon, sulphur (not in the values given to this task) | literature-informed Assumed: another plant / study, not DOK-ING's, not validated for GA-001. Table 9 literature mean; the paper gives no mixed-MSW ultimate analysis. |
| zhou_ps | polystyrene (PS) | Ad dry; C/H/O/N(/Cl) dry ash-free; HHV dry (kJ/kg) | Ad_pct 0.19; C_daf_pct 90.37; H_daf_pct 8.64; O_daf_pct 0.9; N_daf_pct 0.0; HHV_d_kJ_kg 39523 | Zhou et al., J. Air & Waste Manage. Assoc. 64(5), 2014, 597-616 (literature means across the studies it cites) -- https://www.awma.org/files/2020Stern.pdf | Assumed (literature-informed) | volatile matter, fixed carbon, sulphur (not in the values given to this task) | literature-informed Assumed: another plant / study, not DOK-ING's, not validated for GA-001. Table 9 literature mean; the paper gives no mixed-MSW ultimate analysis. |
| zhou_pvc | polyvinyl chloride (PVC) | Ad dry; C/H/O/N(/Cl) dry ash-free; HHV dry (kJ/kg) | Ad_pct 5.86; C_daf_pct 39.56; H_daf_pct 4.85; O_daf_pct 0.02; N_daf_pct 0.11; HHV_d_kJ_kg 20848; Cl_daf_pct 55.18 | Zhou et al., J. Air & Waste Manage. Assoc. 64(5), 2014, 597-616 (literature means across the studies it cites) -- https://www.awma.org/files/2020Stern.pdf | Assumed (literature-informed) | volatile matter, fixed carbon, sulphur (not in the values given to this task) | literature-informed Assumed: another plant / study, not DOK-ING's, not validated for GA-001. Table 9 literature mean; the paper gives no mixed-MSW ultimate analysis. Cl is not carried by the engine. |
| zhou_pet | polyethylene terephthalate (PET) | Ad dry; C/H/O/N(/Cl) dry ash-free; HHV dry (kJ/kg) | Ad_pct 0.2; C_daf_pct 62.3; H_daf_pct 4.43; O_daf_pct 33.13; N_daf_pct 0.09; HHV_d_kJ_kg 23090 | Zhou et al., J. Air & Waste Manage. Assoc. 64(5), 2014, 597-616 (literature means across the studies it cites) -- https://www.awma.org/files/2020Stern.pdf | Assumed (literature-informed) | volatile matter, fixed carbon, sulphur (not in the values given to this task) | literature-informed Assumed: another plant / study, not DOK-ING's, not validated for GA-001. Table 9 literature mean; the paper gives no mixed-MSW ultimate analysis. |
| zhou_cotton | cotton | Ad, Vd dry; C/H/O/N dry ash-free; HHV dry (kJ/kg) | Ad_pct 1.05; Vd_pct 87.93; C_daf_pct 47.55; H_daf_pct 6.3; O_daf_pct 45.14; N_daf_pct 0.82; HHV_d_kJ_kg 17083 | Zhou et al., J. Air & Waste Manage. Assoc. 64(5), 2014, 597-616 (literature means across the studies it cites) -- https://www.awma.org/files/2020Stern.pdf | Assumed (literature-informed) | fixed carbon, sulphur, chlorine (not in the values given to this task) | literature-informed Assumed: another plant / study, not DOK-ING's, not validated for GA-001. Table 7 literature mean. |
| zhou_wool | wool | Ad, Vd dry; C/H/O/N dry ash-free; HHV dry (kJ/kg) | Ad_pct 1.24; Vd_pct 84.76; C_daf_pct 59.3; H_daf_pct 5.36; O_daf_pct 24.85; N_daf_pct 8.89; HHV_d_kJ_kg 22276 | Zhou et al., J. Air & Waste Manage. Assoc. 64(5), 2014, 597-616 (literature means across the studies it cites) -- https://www.awma.org/files/2020Stern.pdf | Assumed (literature-informed) | fixed carbon, sulphur, chlorine (not in the values given to this task) | literature-informed Assumed: another plant / study, not DOK-ING's, not validated for GA-001. Table 7 literature mean. |
| zhou_chemical_fibres | chemical fibres | Ad, Vd dry; C/H/O/N dry ash-free; HHV dry (kJ/kg) | Ad_pct 2.15; Vd_pct 87.09; C_daf_pct 59.28; H_daf_pct 5.25; O_daf_pct 27.4; N_daf_pct 7.56; HHV_d_kJ_kg 23667 | Zhou et al., J. Air & Waste Manage. Assoc. 64(5), 2014, 597-616 (literature means across the studies it cites) -- https://www.awma.org/files/2020Stern.pdf | Assumed (literature-informed) | fixed carbon, sulphur, chlorine (not in the values given to this task) | literature-informed Assumed: another plant / study, not DOK-ING's, not validated for GA-001. Table 7 literature mean. |
| zhou_msw_combustible_fractions | mean Chinese MSW combustible fractions | mass %, Fig. 1 | food_residue_pct 55.86; plastics_pct 11.15; paper_pct 8.52; textiles_pct 3.16; wood_pct 2.94; rubber_pct 0.84 | Zhou et al., J. Air & Waste Manage. Assoc. 64(5), 2014, 597-616 (literature means across the studies it cites) -- https://www.awma.org/files/2020Stern.pdf | Assumed (literature-informed) | a mixed-MSW ultimate analysis (the paper gives none) | literature-informed Assumed: another plant / study, not DOK-ING's, not validated for GA-001. Composition of the combustible fraction by material, not an elemental analysis. |
| teerawattana_rdf | refuse-derived fuel (RDF), Thailand | air-dry (moisture 2.93 %); HHV in kcal/kg | moisture_pct 2.93; ash_pct 24.48; ash_range_pct (19.76, 29.31); C_pct 55.16; H_pct 7.89; O_pct 10.32; N_pct 1.3; S_pct 0.12; Cl_pct 0.73; HHV_kcal_kg 6888.1; HHV_range_kcal_kg (5811.4, 7958.0) | Teerawattana et al., Environment and Natural Resources J. 9(1), 2011, Table 1 -- https://ph02.tci-thaijo.org/index.php/ennrj/article/download/82440/65520/199529 | Assumed (literature-informed) | volatile matter and fixed carbon (not reported); the basis of the HHV (taken as the same air-dry basis); the O figure is 'by difference' | literature-informed Assumed: another plant / study, not DOK-ING's, not validated for GA-001. C/H/O/N/S/Cl are as air-dry fractions of the whole fuel (ash included), not daf. Ash 24 % is far outside the engine's 10 %. |
| werle_sewage_sludge_ss1 | sewage sludge SS1 | moisture, VM, ash as listed; C/H/N/O/S dry; LHV dry (MJ/kg) | moisture_ar_pct 5.3; VM_pct 51.0; ash_pct 36.5; C_d_pct 31.79; H_d_pct 4.36; N_d_pct 4.88; O_d_pct 57.07; S_d_pct 1.67; LHV_d_MJ_kg 12.96 | Werle, sewage sludge gasification, Table 1 -- https://yadda.icm.edu.pl/baztech/element/bwmeta1.element.baztech-4a966c39-792b-43c0-ae51-f021241b04ce/c/werle_gasification_2013_11.pdf | Assumed (literature-informed) | the basis of VM and ash (listed with the as-received moisture); ash as a separate dry figure | literature-informed Assumed: another plant / study, not DOK-ING's, not validated for GA-001. The text layout of the page is garbled and the mapping follows the label order. O is 'by difference', so it apparently includes the ash (C+H+N+O+S = 99.77 %): the O-by-difference oddity is flagged here and NOT corrected. |
| werle_sewage_sludge_ss2 | sewage sludge SS2 | as SS1 | moisture_ar_pct 5.3; VM_pct 49.0; ash_pct 44.2; C_d_pct 27.72; H_d_pct 3.81; N_d_pct 3.59; O_d_pct 63.04; S_d_pct 1.81; LHV_d_MJ_kg 10.75 | Werle, sewage sludge gasification, Table 1 -- https://yadda.icm.edu.pl/baztech/element/bwmeta1.element.baztech-4a966c39-792b-43c0-ae51-f021241b04ce/c/werle_gasification_2013_11.pdf | Assumed (literature-informed) | the basis of VM and ash; ash as a separate dry figure | literature-informed Assumed: another plant / study, not DOK-ING's, not validated for GA-001. Same layout caveat as SS1. O by difference apparently includes the ash (27.72+3.81+3.59+63.04+1.81 = 99.97 %); not corrected. |
| wood_pellets_or_chips | wood | - | - | no source opened for this task | Missing (source not opened) | everything | NOT VERIFIED: no analysis was opened and none is added from memory. The engine's default feed (C/H/O/N 0.50/0.06/0.43/0.01 daf, ash 0.10) is a wood-like stand-in, not this entry. |
| chalmers_cotton_polyester_thesis | cotton / polyester | - | - | Chalmers thesis (abstract only) | Missing | any analysis values (the page is an abstract) | NOT VERIFIED: the page gives no analysis values. |
| moliner_energies_17_5_1206 | textile / mixed waste (Moliner et al.) | - | - | Moliner et al., Energies 17(5) 1206 (PMC7663054) | Missing | not readable (blocked) | NOT VERIFIED: the page could not be read; no values. |
| dokink_feed_bands | DOK-ING stated feed bands (RFI #2) | dry basis for LHV; the basis of the others is not stated | carbon_min_pct 45.0; hydrogen_min_pct 5.0; volatile_matter_min_pct 65.0; ash_pct_range (5.0, 15.0); lhv_MJ_kg_dry_range (15.0, 20.0); moisture_pct_range (5.0, 15.0); feed_forms plastic, dried sewage sludge, wood chips, textiles | data/dokink_rfi_answers.md lines 15-18 (RFI #2 'Composition' and #3 'Feedstock form') | Assumed (DOK-ING-stated band, kept as a band) | the basis of C, H, VM and ash; any upper limit on C or H; sulphur and chlorine limits ('trace S/Cl captured via downstream scrubbing') | DOK-ING's stated figures, quoted from the repo's copy of its RFI response (file:line above). design_basis.py records RFI #2 as confirmed; this layer does not upgrade or downgrade that, it only applies the bands to DRY-BASIS numbers as the task specifies. |

### 2.2 Derived (Calculated) and DOK-ING bands (dry basis)

| material | C dry % | H dry % | ash dry % | LHV dry MJ/kg | LHV daf MJ/kg | C > 45 | H > 5 | VM > 65 | ash 5-15 % | LHV 15-20 |
|---|---|---|---|---|---|---|---|---|---|---|
| zhou_pe | 85.31 | 14.10 | 0.33 | 39.75 | 39.88 | ok | ok | n/t | FAILS | FAILS |
| zhou_pp | 84.65 | 13.87 | 0.44 | 42.96 | 43.15 | ok | ok | n/t | FAILS | FAILS |
| zhou_ps | 90.20 | 8.62 | 0.19 | 37.63 | 37.70 | ok | ok | n/t | FAILS | FAILS |
| zhou_pet | 62.18 | 4.42 | 0.20 | 22.12 | 22.16 | ok | FAILS | n/t | FAILS | FAILS |
| zhou_cotton | 47.05 | 6.23 | 1.05 | 15.71 | 15.88 | ok | ok | ok | FAILS | ok |
| zhou_wool | 58.56 | 5.29 | 1.24 | 21.11 | 21.38 | ok | ok | ok | FAILS | FAILS |
| zhou_chemical_fibres | 58.01 | 5.14 | 2.15 | 22.54 | 23.03 | ok | ok | ok | FAILS | FAILS |
| teerawattana_rdf | 56.82 | 8.13 | 25.22 | 27.90 | 37.31 | ok | ok | n/t | FAILS | FAILS |
| werle_sewage_sludge_ss1 | 31.79 | 4.36 | 36.50 | 12.96 | 20.41 | FAILS | FAILS | FAILS | FAILS | FAILS |
| werle_sewage_sludge_ss2 | 27.72 | 3.81 | 44.20 | 10.75 | 19.27 | FAILS | FAILS | FAILS | FAILS | FAILS |
| blend M1 (illustrative) | 78.76 | 11.30 | 0.88 | 36.48 | 36.80 | ok | ok | n/t | FAILS | FAILS |

DOK-ING's bands: `data/dokink_rfi_answers.md:15-17` -- "Moisture 5-15(20)%, Ash 5-15%, Volatile Matter >65%, Carbon >45%, Hydrogen >5%, LHV 15-20 MJ/kg (dry basis)". The sludge / RDF readings use the ash as stated (the sludge ash basis is not stated); VM is not given for the plastics, the RDF, nor blend M1 (n/t). Expected readings confirmed: sludge and RDF fail the ash band; PE / PP have H about 14 % dry, far above the floor.

## 3. Comparison across feeds (item C): what it shows

Converged (30 cycles), ER 0.25, feed mass rate the model's 37.50 kg/h dry, ash fixed at 10 %. Tables in the appendix; the points that matter:

- **Hydrogen depends on the feed far more than on tail-gas handling.** `regasify` / `heat_only`: default stand-in 78.0 / 55.7 kg/day; cotton 74.7 / 53.4; PET 94.8 / 67.3; wool 103.1 / 75.7; PS 184.5 / 140.8; PP 206.5 / 163.0; PE 209.4 / 165.5; blend M1 191.8 / 149.7. The polyolefins give 0.18 to 0.23 kg H2 per kg dry feed against 0.06 to 0.09 for the stand-in and 0.0556 implied by DOK-ING's "about 50 kg/day from 1 tpd".
  If the plant really gasifies plastic at the model's feed rate, the twin predicts **three to four times** DOK-ING's figure, while the stand-in is only 1.1 to 1.6 times it. This is a finding about the model (fixed conversion, fixed ER, no energy coupling), not evidence about the plant.
- **No feed closes the heat balance in either mode.** Net heat (`tail-gas heat used - gasifier duty - steam / air / drying demand`, with each feed's own LHV): stand-in -95.5 / -36.5 kW; cotton -99.3 / -43.0; PET -110.8 / -39.0; wool -132.2 / -60.4; PS -202.9 / -91.9; PP -178.8 / -64.6; PE -216.3 / -100.9; M1 -208.5 / -98.8. The deficit grows with the feed because the model raises more WGS steam (4 x CO) the richer the gas is; the tail gas covers 65 to 75 % of the demand in `heat_only`. No feed is energetically self-consistent without a boiler / heat-integration model.
- **Gasifier duty at ER 0.25:** +6 kW (PET, regasify) to +60 kW (PE, heat_only): the gasifier would have to be heated for every feed, and by more for the plastics.
- **GA-008's 3 kg/h carbon-black capacity is exceeded** for PE, PP, PS and M1 in `regasify` (3.48 to 3.70 kg/h) and for PS also in `heat_only` (3.05 kg/h): the unconverted carbon is 10 % of a carbon-rich feed. Not changed (registry untouched).
- **Closure holds for every feed:** carbon closes to |residual| < 1.1e-14 kg/h; H, O, N below 6e-16; ash closes (the same constant on both sides, which is also why a feed's own ash cannot show up). No balance fails.
- **DOK-ING bands (dry-basis numbers):** the stand-in's C is exactly 45.0 % (at the floor, not above it) and passes ash and LHV; cotton passes C, H, VM and LHV and fails ash (too clean, 1.05 %); wool and PET fail the LHV band (and PET the H floor, 4.4 %); the polyolefins and M1 satisfy C and H by a wide margin (H about 14 %: the band has no upper limit), and fail ash (too clean) and LHV (39 to 43 MJ/kg dry, above 20). Sludge and RDF fail the ash band (and the sludges C, H, VM and LHV).
- **ER sweep (PE and cotton, 0.20 / 0.25 / 0.30; reported, not chosen):** PE 230.6 / 209.4 / 188.5 kg/day (`regasify`) and 179.5 / 165.5 / 151.2 (`heat_only`); cotton 83.2 / 74.7 / 66.4 and 58.3 / 53.4 / 48.3. Hydrogen falls about 8 to 11 % per 0.05 of ER for both; the net heat deficit shrinks with ER but stays negative everywhere.

## 4. What it does not show

- Nothing about the real plant: the feeds are other studies' literature means (some from abstracts / garbled tables), run through a model whose conversion (0.90), CH4 fraction, ER and WGS are Assumed, with ash fixed at 10 % and S / Cl dropped. A feed's low real ash (0.2 to 2 %) is replaced by 10 % inert, which understates the combustible rate by about 10 %.
- Not that DOK-ING's 50 kg/day is wrong: it is "gross or net unstated", from "standard high-calorific plastic waste" that is never specified (polyolefin-rich, PVC- and PET-containing, wet, dirty), at an availability and a net basis we do not know.
- Not a ranking of feeds: the model has no tar, no heat-loss, no temperature-dependent conversion, and no boiler, so the heat deficits are model gaps as much as feed properties.

## 5. Needs your decision

1. **Which feed is the "plastic-waste case" for the ~50 kg/day comparison?** The stored data cannot decide it (no mixed-plastic analysis exists in the sources; the paper gives no mixed-MSW ultimate analysis). Candidates: blend M1 (illustrative, polyolefin-heavy: 150 to 192 kg/day, a factor 3 to 4 over 50), PET (67 to 95 kg/day), or a diluted mix. I recommend not choosing M1 for any claim: its weights are my owner-specified illustration, not data. A DOK-ING analysis (or at least the plastic type split and moisture / ash of the real feed) is the unblocker.
2. **Should the model carry sulphur, chlorine and a feed-specific ash fraction?** Ash is the one that matters for these comparisons (fixed 10 % hides the polyolefin / sludge / RDF differences, and the carbon-black capacity flag depends on it); S and Cl matter for scrubber loads and for PVC-containing blends. Carrying them is an engine change (composition input plus ash as an input), outside this task.

## Appendix: measured tables (generated by `scripts/run_feed_comparison.py`)

### 1. Feeds, what was dropped, DOK-ING band compliance (dry-basis numbers)

| feed | model composition (daf %, renormalised) | dropped | unreported daf % | LHV daf MJ/kg | feed energy in the model, MJ/kg dry (x 0.9) | DOK-ING bands (ok / FAILS / n/t = not testable) |
|---|---|---|---|---|---|---|
| default stand-in (C/H/O/N 0.50/0.06/0.43/0.01 daf, ash 0.10) | default | - | 0.00 | 17.50 | 15.75 | C FAILS, H ok, VM n/t, ash ok, LHV ok |
| cotton | C 47.6, H 6.3, O 45.2, N 0.8 | - | 0.19 | 15.88 | 14.29 | C ok, H ok, VM ok, ash FAILS, LHV ok |
| wool | C 60.3, H 5.4, O 25.3, N 9.0 | - | 1.60 | 21.38 | 19.24 | C ok, H ok, VM ok, ash FAILS, LHV FAILS |
| polyethylene (PE) | C 85.6, H 14.2, O 0.1, N 0.1 | - | 0.07 | 39.88 | 35.89 | C ok, H ok, VM n/t, ash FAILS, LHV FAILS |
| polypropylene (PP) | C 85.0, H 13.9, O 1.0, N 0.1 | - | 0.01 | 43.15 | 38.83 | C ok, H ok, VM n/t, ash FAILS, LHV FAILS |
| polystyrene (PS) | C 90.5, H 8.6, O 0.9, N 0.0 | - | 0.09 | 37.70 | 33.93 | C ok, H ok, VM n/t, ash FAILS, LHV FAILS |
| PET | C 62.3, H 4.4, O 33.1, N 0.1 | - | 0.05 | 22.16 | 19.95 | C ok, H FAILS, VM n/t, ash FAILS, LHV FAILS |
| blend M1 (illustrative: 40 PE / 25 PP / 15 PS / 10 PET / 10 PVC) | C 83.9, H 12.0, O 4.0, N 0.1 | Cl 5.24 % daf | 0.08 | 36.80 | 33.12 | C ok, H ok, VM n/t, ash FAILS, LHV FAILS |

Bands: C > 45, H > 5, VM > 65, ash 5-15 %, LHV 15-20 MJ/kg dry (`data/dokink_rfi_answers.md:15-17`). The default stand-in's C is exactly 45.0 % dry (the floor, not above it); plastics and textiles are too clean for the 5-15 % ash band and mostly above the LHV band; the H floor says nothing about an upper limit (PE/PP are at about 14 %).

### 2. Hydrogen, gas and carbon

| feed | mode | H2 kg/day | kg H2 / kg dry feed | kg H2 / kg combustible | gas dry mol % H2/CO/CO2/CH4/N2 | dry gas Nm3/h | gas LHV MJ/Nm3 | carbon black kg/h (GA-008 cap 3) | GA-001 carbon residual |
|---|---|---|---|---|---|---|---|---|---|
| default stand-in (C/H/O/N 0.50/0.0 | regasify | 78.0 | 0.0867 | 0.0963 | 27.5/21.5/9.8/1.6/39.6 | 102.8 | 6.26 | 2.01 | +0e+00 (closes to numerical precision) |
| default stand-in (C/H/O/N 0.50/0.0 | heat_only | 55.7 | 0.0619 | 0.0688 | 24.8/22.1/12.1/1.8/39.2 | 78.8 | 6.10 | 1.69 | +0e+00 (closes to numerical precision) |
| cotton | regasify | 74.7 | 0.0829 | 0.0922 | 27.9/20.8/10.3/1.6/39.4 | 98.7 | 6.22 | 1.92 | -3e-15 (closes to numerical precision) |
| cotton | heat_only | 53.4 | 0.0593 | 0.0659 | 25.4/21.1/12.7/1.8/38.9 | 75.8 | 6.05 | 1.61 | +3e-15 (closes to numerical precision) |
| wool | regasify | 103.1 | 0.1146 | 0.1273 | 26.7/23.6/6.4/1.6/41.8 | 129.9 | 6.42 | 2.44 | +5e-15 (closes to numerical precision) |
| wool | heat_only | 75.7 | 0.0841 | 0.0935 | 23.7/25.1/7.3/1.7/42.1 | 100.0 | 6.34 | 2.03 | +0e+00 (closes to numerical precision) |
| polyethylene (PE) | regasify | 209.4 | 0.2326 | 0.2585 | 32.7/22.1/2.7/1.3/41.3 | 231.0 | 6.78 | 3.58 EXCEEDS 3 | +5e-15 (closes to numerical precision) |
| polyethylene (PE) | heat_only | 165.5 | 0.1839 | 0.2043 | 31.8/23.2/2.1/1.3/41.6 | 182.3 | 6.84 | 2.89 | -5e-15 (closes to numerical precision) |
| polypropylene (PP) | regasify | 206.5 | 0.2294 | 0.2549 | 32.6/22.1/2.7/1.3/41.2 | 228.2 | 6.78 | 3.55 EXCEEDS 3 | +0e+00 (closes to numerical precision) |
| polypropylene (PP) | heat_only | 163.0 | 0.1811 | 0.2012 | 31.7/23.3/2.2/1.3/41.5 | 179.9 | 6.83 | 2.87 | +0e+00 (closes to numerical precision) |
| polystyrene (PS) | regasify | 184.5 | 0.2050 | 0.2277 | 28.7/25.5/2.5/1.5/41.8 | 210.2 | 6.84 | 3.70 EXCEEDS 3 | -5e-15 (closes to numerical precision) |
| polystyrene (PS) | heat_only | 140.8 | 0.1564 | 0.1738 | 25.9/28.4/1.7/1.6/42.4 | 161.8 | 6.94 | 3.05 EXCEEDS 3 | +0e+00 (closes to numerical precision) |
| PET | regasify | 94.8 | 0.1053 | 0.1170 | 25.2/24.9/7.7/1.7/40.5 | 122.1 | 6.47 | 2.49 | +0e+00 (closes to numerical precision) |
| PET | heat_only | 67.3 | 0.0747 | 0.0831 | 21.4/26.9/9.4/1.9/40.4 | 92.5 | 6.39 | 2.10 | +5e-15 (closes to numerical precision) |
| blend M1 (illustrative: 40 PE / 25 | regasify | 191.8 | 0.2131 | 0.2368 | 31.5/22.9/2.9/1.4/41.3 | 214.8 | 6.78 | 3.48 EXCEEDS 3 | +0e+00 (closes to numerical precision) |
| blend M1 (illustrative: 40 PE / 25 | heat_only | 149.7 | 0.1663 | 0.1848 | 30.1/24.4/2.4/1.4/41.7 | 168.2 | 6.83 | 2.83 | -1e-14 (closes to numerical precision) |

Reference: DOK-ING about 50 kg/day (plastic waste, gross or net unstated); registry 44.4 kg/day. Per kg dry feed those are 0.0556 and 0.0493 kg/kg on the model's 37.5 kg/h dry feed.

### 3. Heat balance (kW; feed-specific LHV; `(GA-001, EnergyBalance)` terms)

| feed | mode | feed chem. kW | gas chem. kW | gasifier duty kW (+ add heat) | steam raising kW | heat demand total kW | tail-gas heat used kW | NET kW (+ surplus / - deficit) | net if tail gas were heat |
|---|---|---|---|---|---|---|---|---|---|
| default stand-in (C/H/O/N 0.50/0.0 | regasify | 164.1 | 178.7 | +14.9 | 74.4 | 80.6 | 0.0 | -95.5 | -34.1 |
| default stand-in (C/H/O/N 0.50/0.0 | heat_only | 164.1 | 133.6 | +18.8 | 61.4 | 66.7 | 49.0 | -36.5 | -36.5 |
| cotton | regasify | 148.9 | 170.6 | +23.2 | 70.1 | 76.1 | 0.0 | -99.3 | -40.7 |
| cotton | heat_only | 148.9 | 127.5 | +27.0 | 57.7 | 62.9 | 46.9 | -43.0 | -43.0 |
| wool | regasify | 200.4 | 231.7 | +26.8 | 98.3 | 105.4 | 0.0 | -132.2 | -56.5 |
| wool | heat_only | 200.4 | 176.3 | +31.9 | 83.0 | 89.1 | 60.6 | -60.4 | -60.4 |
| polyethylene (PE) | regasify | 373.9 | 435.1 | +50.5 | 155.0 | 165.7 | 0.0 | -216.3 | -92.9 |
| polyethylene (PE) | heat_only | 373.9 | 346.2 | +59.8 | 130.8 | 139.9 | 98.8 | -100.9 | -100.9 |
| polypropylene (PP) | regasify | 404.5 | 429.6 | +14.6 | 153.5 | 164.2 | 0.0 | -178.8 | -56.6 |
| polypropylene (PP) | heat_only | 404.5 | 341.6 | +23.8 | 129.6 | 138.6 | 97.8 | -64.6 | -64.6 |
| polystyrene (PS) | regasify | 353.5 | 399.6 | +30.4 | 162.4 | 172.5 | 0.0 | -202.9 | -82.2 |
| polystyrene (PS) | heat_only | 353.5 | 312.1 | +39.2 | 140.9 | 149.4 | 96.7 | -91.9 | -91.9 |
| PET | regasify | 207.8 | 219.6 | +6.2 | 97.7 | 104.6 | 0.0 | -110.8 | -35.6 |
| PET | heat_only | 207.8 | 164.2 | +10.9 | 82.3 | 88.2 | 60.1 | -39.0 | -39.0 |
| blend M1 (illustrative: 40 PE / 25 | regasify | 345.0 | 404.4 | +48.2 | 150.1 | 160.3 | 0.0 | -208.5 | -90.9 |
| blend M1 (illustrative: 40 PE / 25 | heat_only | 345.0 | 319.4 | +56.9 | 127.5 | 136.2 | 94.2 | -98.8 | -98.8 |

### 4. Closure checks (closure audit functions)

| feed | mode | GA-001 H,O,N max |rel| | loop H,O,N max |rel| | ash | GA-001 carbon residual kg/h | unconverted carbon from the recycle kg/h |
|---|---|---|---|---|---|---|
| default stand-in (C/H/O/N 0.50/0.0 | regasify | 3.7e-16 | 1.6e-16 | closes to numerical precision | +0.0e+00 | 0.326 |
| default stand-in (C/H/O/N 0.50/0.0 | heat_only | 2.4e-16 | 1.8e-16 | closes to numerical precision | +0.0e+00 | 0.000 |
| cotton | regasify | 1.8e-16 | 1.4e-16 | closes to numerical precision | -2.7e-15 | 0.312 |
| cotton | heat_only | 3.6e-16 | 5.2e-16 | closes to numerical precision | +2.7e-15 | 0.000 |
| wool | regasify | 1.9e-16 | 1.9e-16 | closes to numerical precision | +5.5e-15 | 0.406 |
| wool | heat_only | 3.6e-16 | 3.6e-16 | closes to numerical precision | +0.0e+00 | 0.000 |
| polyethylene (PE) | regasify | 2.1e-16 | 2.1e-16 | closes to numerical precision | +5.5e-15 | 0.689 |
| polyethylene (PE) | heat_only | 3.4e-16 | 1.7e-16 | closes to numerical precision | -5.5e-15 | 0.000 |
| polypropylene (PP) | regasify | 4.2e-16 | 4.3e-16 | closes to numerical precision | +0.0e+00 | 0.682 |
| polypropylene (PP) | heat_only | 3.4e-16 | 1.7e-16 | closes to numerical precision | +0.0e+00 | 0.000 |
| polystyrene (PS) | regasify | 4.6e-16 | 4.6e-16 | closes to numerical precision | -5.5e-15 | 0.644 |
| polystyrene (PS) | heat_only | 5.5e-16 | 1.7e-16 | closes to numerical precision | +0.0e+00 | 0.000 |
| PET | regasify | 2.1e-16 | 1.3e-16 | closes to numerical precision | +0.0e+00 | 0.390 |
| PET | heat_only | 5.7e-16 | 2.7e-16 | closes to numerical precision | +5.5e-15 | 0.000 |
| blend M1 (illustrative: 40 PE / 25 | regasify | 1.3e-16 | 0.0e+00 | closes to numerical precision | +0.0e+00 | 0.647 |
| blend M1 (illustrative: 40 PE / 25 | heat_only | 5.2e-16 | 1.6e-16 | closes to numerical precision | -1.1e-14 | 0.000 |

### 5. ER sweep for PE and cotton only (0.20 / 0.25 / 0.30; reported, not chosen)

| feed | mode | ER | H2 kg/day | net heat kW | gas dry mol % H2/CO/N2 |
|---|---|---|---|---|---|
| polyethylene (PE) | regasify | 0.2 | 230.6 | -246.9 | 38.3/24.1/34.7 |
| polyethylene (PE) | heat_only | 0.2 | 179.5 | -122.2 | 36.8/25.8/35.1 |
| polyethylene (PE) | regasify | 0.25 | 209.4 | -216.3 | 32.7/22.1/41.3 |
| polyethylene (PE) | heat_only | 0.25 | 165.5 | -100.9 | 31.8/23.2/41.6 |
| polyethylene (PE) | regasify | 0.3 | 188.5 | -185.2 | 27.7/20.1/47.1 |
| polyethylene (PE) | heat_only | 0.3 | 151.2 | -79.0 | 27.3/20.7/47.4 |
| cotton | regasify | 0.2 | 83.2 | -112.9 | 32.9/23.1/33.3 |
| cotton | heat_only | 0.2 | 58.3 | -51.3 | 29.6/23.9/32.9 |
| cotton | regasify | 0.25 | 74.7 | -99.3 | 27.9/20.8/39.4 |
| cotton | heat_only | 0.25 | 53.4 | -43.0 | 25.4/21.1/38.9 |
| cotton | regasify | 0.3 | 66.4 | -85.7 | 23.5/18.6/44.9 |
| cotton | heat_only | 0.3 | 48.3 | -34.4 | 21.8/18.6/44.4 |

### 6. NOT TESTABLE through the engine's inputs

| feed | reason |
|---|---|
| RDF (Teerawattana) | ash 25.2 % dry against the engine's fixed 10 % (ash is a module constant, not an input); S 0.12 % and Cl 0.73 % would be dropped; the feed would be a different fuel, not RDF |
| sewage sludge SS1 / SS2 (Werle) | ash 36.5 / 44.2 % against the fixed 10 %; the page's O is 'by difference' and apparently includes the ash, so no dry ash-free C/H/O/N exists to enter; S 1.7-1.8 % and N 3.6-4.9 % dry (N is carried, S is not) |
| PVC alone | Cl 55.18 % daf would be dropped, leaving C+H+O+N = 44.5 % of the mass: not the same material (PVC enters only inside blend M1, where 5.2 % of the dry mass, the Cl, is dropped) |
| wood, Chalmers thesis, Moliner et al. | no values (Missing / NOT VERIFIED) |
