# Literature reference layer and trend comparison (step 2 of the validation plan)

Written 2026-10-30 on `origin/main` c9d1847 (branch `literature-reference`). DOK-ING cannot answer the technical questions at this stage, so published pilot and lab values are
recorded as a labelled reference layer next to the model, and the model's trends are compared with the published trends. **No model default, equation, Confirmed value,
`uncertainty.ASSUMPTIONS` bound or point value changed.** Every published figure was read by the project owner on the cited page (mostly abstracts); none was fetched or added here.
Offline throughout: in-memory fake store, no database, no network, the real `secrets.toml` never read, `HYGAS_ALLOW_DB_WRITES` unset.

**The reference layer is not wired into the app, the uncertainty module, the engine or the what-if tab in this task.** `python/literature_reference.py` imports nothing from the project and
a test checks that no other module reads it.

Files: `python/literature_reference.py` (data), `tests/test_literature_reference.py`, `scripts/run_literature_trend_check.py` (writes `outputs/literature/trend_check.md` and `.csv`, git-ignored).
Reproduce the tables: `python scripts/run_literature_trend_check.py` (about 50 s).

**Status tag chosen.** The repo's vocabulary (`python/plant_status.py:52-56`) has Measured / Calculated / Estimated / Assumed / Missing and no "Assumed (literature-informed)" string, so every
entry carries the project's `Assumed` tag and the words "literature-informed" are in its caveat. None is Confirmed (they are not DOK-ING's), Measured or Calculated.

## 1. Read first (item A)

### 1.1 What `steam_to_feed_ratio` means

| point | file:line | what it does |
|---|---|---|
| default and its bounds | `python/uncertainty.py:80-84` | `ASSUMPTIONS["steam_to_feed_ratio"]`: point 0.4, +/-15 % (bounds 0.34-0.46), no confirmed range |
| input function | `python/ga001_gasifier_model.py:458-480` `_input_steam_to_feed_ratio` | returns the point value 0.4, status Assumed; unit registered as `kg/kg` (:1140) |
| read by the model | `ga001_gasifier_model.py:742` | `steam_ratio = get_input(("GA-001-INPUT","steam_to_feed_ratio"))` |
| conversion | `ga001_gasifier_model.py:752` | `steam_mol_per_molc = (steam_ratio / n_C_per_kg) * 1000.0 / M_H2O` |
| `n_C_per_kg` | `ga001_gasifier_model.py:246` (`elemental_atomic_ratios`) | mol C per kg of **total dry feed including ash**: `(1 - ash) x C_fraction x 1000 / M_C` = 37.466 mol/kg at the default |
| used by the solver | `ga001_gasifier_model.py:307-308` (inside `solve_product_gas`, :292) | adds `steam_mol_per_molc` to the H and O balances of the gas |
| feed moisture | `ga001_gasifier_model.py:697-715, 761-763` | FE-005's residual water (about 0.38 kg/h, 1 % of the dried feed) is **added to the same water pool, on top of** the ratio; it is not part of the ratio |
| recycle rescale | `ga001_gasifier_model.py:776-783` | the absolute steam flow is kept when the recycle adds carbon |
| other users | `ga001_gasifier_model.py:1184, 1198, 1244` (Monte Carlo); `python/uncertainty.py:190` | the Monte Carlo also scales the **WGS** steam-to-CO ratio (4.0) by `s/0.4`, which the engine itself does not do |

**Meaning, exactly:** kilograms of gasifier steam per kilogram of **dry** feed (the FE-005 outlet dry solids, ash included), not per kg as-received, not per mol of carbon. Absolute steam is
`ratio x dry feed` = 0.4 x 37.503 = 15.0 kg/h; per mole of feed carbon it is `ratio x 1000 / M_H2O / n_C_per_kg` = 1.482 x ratio = **0.593 mol steam / mol feed C at 0.4** (without recycle).
The definition in the code is not ambiguous. What is ambiguous is the basis of the **published** ratios: VTT's "steam/fuel" and Bates' "steam/biomass" do not state mass or dry basis, Parrillo's
"steam-to-carbon" does not state mol/mol or kg/kg. They are compared as if kg steam per kg dry fuel (sweeps 0.5 / 1.0 / 1.5) and that assumption is stated wherever it is used.

**Where 0.4 comes from.** In the repo: GA-003's registry remark ("Steam flow rate (design) = 15 kg/h ... matches the 0.4 kg steam/kg dry feed ratio already used in the mass/energy balance
(37.5 kg/h dry feed x 0.4)"; quoted at `ga001_gasifier_model.py:24-26, 462-467`), and `uncertainty.py:80`. The "mass/energy balance dashboard" it refers to is not in this repository. The
`assumption_confirmations` note ("working design value 0.4, source not documented"): **NOT VERIFIED**, it is in the database, which this task may not read; `docs/audit_2026-10-27.md:196` records the row as
"confirmed 0.4 (blank note)". So the 0.4 is a design value with no documented derivation.

### 1.2 Defaults used

| quantity | value | file:line |
|---|---|---|
| gasifier operating temperature | 950 degC | `ga001_gasifier_model.py:230` (`GA001_OPERATING_TEMPERATURE_C`), input function :603-618 (Assumed) |
| equivalence ratio | 0.25 | `uncertainty.py:86` (point), input function `ga001_gasifier_model.py:438-455` (Assumed) |
| carbon conversion / CH4 fraction | 0.90 / 0.05 of converted carbon | `ga001_gasifier_model.py:217, 224` (Assumed) |
| feed composition (dry, ash-free) | C 0.50, H 0.06, O 0.43, N 0.01; ash 0.10 of the dry feed | `ga001_gasifier_model.py:193-196, 211`; input function :549-600 (Assumed) |

### 1.3 What can be varied from outside, without editing GA-001

All of ER, steam ratio, temperature, carbon conversion and CH4 fraction are separate engine input models registered without dependencies (`ga001_gasifier_model.py:1139-1144`):
`("GA-001-INPUT","equivalence_ratio" | "steam_to_feed_ratio" | "operating_temperature_C" | "carbon_conversion_efficiency" | "ch4_carbon_fraction")`. The engine's normal override
(`tab1_integration.build_live_snapshot(n_cycles, overrides={key: fn})`, the pattern its own perturbation tests use at :564) replaces the function before the first cycle. The sweeps use it for ER, temperature
and steam ratio; nothing in GA-001 changed.

## 2. Findings from the trend check (item C)

Converged state (30 cycles, tail-gas recycle settled) and, as a check, a single cycle without recycle. Full tables are in the appendix; the verdicts are direction-only.

| published trend (VTT sewage-sludge BFB; directions only, no concentrations on the page) | model | verdict |
|---|---|---|
| higher temperature raises H2 and CO, lowers CO2 and CH4 (750 -> 950 degC) | CO **+3.86 pp** up, CO2 **-2.92 pp** down: agree. H2 **-2.27 pp**: opposite. CH4 +0.05 pp: no effect | **DISAGREES** (2 of 4 species; same with no recycle: H2 -2.60 pp, CH4 +0.06 pp) |
| higher steam ratio raises H2 | H2 +3.75 pp (0.5 -> 1.5 kg/kg), +5.72 pp (0.2 -> 1.5) | **AGREES** |
| lower ER (0.2 against 0.4) gives more H2 and CO | H2 32.43 vs 15.87 %, CO 23.82 vs 14.84 % dry | **AGREES** (mostly N2 dilution: N2 33.5 -> 54.5 %) |
| steam ratio default 0.4 against the published 0.5-1.5 | the default is 0.1 kg/kg below the lowest published value; as steam-to-carbon it is 0.593 mol/mol against Parrillo's 0.7-1.13 (unit unstated) | plain comparison, no verdict |

What the table shows, stated plainly:

1. **Temperature does move the raw gas composition, through the water-gas-shift equilibrium only** (`_wgs_keq`, `ga001_gasifier_model.py:233-237`; carbon conversion fixed at 0.90, CH4 a fixed
   5 % of converted carbon, no energy balance). The shift is exothermic, so more temperature gives more CO, less CO2 and **less H2**, the opposite of the published H2 trend. The published
   H2 rise at higher temperature needs char gasification and reforming that respond to temperature, which this model does not have; CH4 cannot fall for the same reason (it is a constant fraction).
2. **The plant's hydrogen output is nearly insensitive to temperature**: PSA product 3.2464 kg/h at 750 degC to 3.2510 at 950 (+0.14 %), consistent with the audit's "temperature barely matters". My
   expectation in the task brief that temperature would have almost no effect was too strong for the raw gas (CO and CO2 move by 3-4 pp) and right for production.
3. **Steam raises the raw H2 fraction as published, but not the hydrogen produced**: gas H2 31.8 % at 1.5 kg/kg against 26.1 % at 0.2, yet PSA product 3.2551 -> 3.2458 kg/h (-0.29 %) over 0.2 -> 1.5. The downstream
   shift (fixed 4:1 steam-to-CO) converts the CO that extra gasifier steam would have shifted anyway. A published steam effect on H2 **yield** is not reproduced; the page states only the direction of H2 in the gas.
4. **ER**: the direction agrees; the size is dominated by N2 dilution from air. The default 0.25 is at the upper end of Parrillo's 0.22-0.25 and equals the MDPI value.
5. **The default temperature 950 degC is above every bubbling-bed range in the reference layer** (VTT 650-850, Bates 750-850, MDPI 861-902, SRF best 900) and inside the chemical-looping fuel-reactor range (850-980).
6. **Not testable**: cold-gas efficiency (the repo computes none; nothing was added), tar (GA-001 tar is Missing), transient time scales (steady-state check), the SRF H2 + CO 72.53 % (basis unstated).
7. Magnitudes were not compared and nothing was tuned to make a row agree.

## 3. Needs your decision

(a) **Steam ratio default 0.4.** Its definition is now known (kg per kg dry feed) and its origin is a design remark in the registry, not a derivation. The published range, read as kg/kg, is 0.5-1.5; the current uncertainty
bounds are 0.34-0.46 and do not reach it. The effect of revisiting it, from the sweep: 0.4 -> 0.5 changes raw H2 by +0.59 pp and PSA hydrogen by -0.05 %; 0.4 -> 1.0 by +2.82 pp and -0.16 %. I recommend **not** changing it until
the basis of the published ratios is known and a plant steam figure exists; nothing was changed.

(b) **Wiring the reference band into `uncertainty.py` or the UI.** Proposal, not implemented: show the reference ranges as a read-only column next to each assumption in the assumptions table, labelled "published, other plants,
literature-informed Assumed". Effect on the existing bounds if shown only: none. If the bands were *used* as bounds: ER 0.22-0.25 sits inside the current 0.2125-0.2875, so it would narrow, not widen, the ER band; the steam band
0.5-1.5 would move the steam bound well past the current 0.34-0.46 and, because `uncertainty.py:190` scales the **WGS** steam-to-CO ratio by `s/0.4`, would push it to 4 x 1.5/0.4 = 15, which is not a meaningful value. So the steam band
should not be used as a Monte Carlo bound unless gasifier steam and WGS steam are first separated.

(c) **A tar model and a heat-duty model.** Item C supports both but with different readiness. A heat duty is cheap and read-only (the closure audit on branch `balance-audit` already computes one as an implied number) and is the missing
piece for any temperature response. A tar model has no usable reference here: the layer holds only a relative change (-94.5 %, olivine) and a naphthalene concentration, not a tar yield, so tar should stay Missing until data exists.
The temperature disagreement (H2 and CH4) will not be resolved by a heat duty alone; it needs temperature-dependent carbon conversion and CH4, which in turn need data.

## 4. Not verified

- Python 3.11 / 3.12: the new code uses no syntax newer than 3.11 (checked with `ast.parse(..., feature_version=(3, 11))`); CI has not run it.
- The published figures themselves: taken as given from the owner's reading of the pages; not re-read or fetched.
- The `assumption_confirmations` note: in the database, not read.
- The basis (mass or mole, dry or wet) of VTT's steam/fuel, Bates' steam/biomass and Parrillo's steam-to-carbon, and the basis of SRF's gas percentages: not stated on the pages.

## 5. The reference entries (item B)

Wording of the stated figures is as given by the owner; `numeric` in the module carries the low/high/unit where the page states numbers. Status of every entry: `Assumed` (literature-informed, see caveat).

| key | parameter | stated (as given) | scale / feed / agent | source | the page does not state | caveat |
|---|---|---|---|---|---|---|
| parrillo_er | equivalence ratio (ER) | ER, 0.22–0.25 | large pilot-scale fluidised bed / mixed plastic waste from separate collection of MSW / steam + O2-enriched air | Parrillo et al., SSRN preprint (title not given in the task file) -- https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4737155 | bed temperature, gas composition, LHV | literature-informed Assumed: a value from another plant and feed, not DOK-ING's and not validated for GA-001. Preprint abstract; plastic-rich feed, O2-enriched air. |
| parrillo_steam_to_carbon | steam-to-carbon ratio | Steam-to-carbon ratio, 0.7–1.13 | large pilot-scale fluidised bed / mixed plastic waste from separate collection of MSW / steam + O2-enriched air | Parrillo et al., SSRN preprint (title not given in the task file) -- https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4737155 | whether the ratio is molar or mass based, bed temperature, gas composition, LHV | literature-informed Assumed: a value from another plant and feed, not DOK-ING's and not validated for GA-001. The basis of the ratio (mol/mol or kg/kg) is not stated, so it is not converted here. |
| parrillo_steam_to_oxygen | steam-to-oxygen ratio | steam-to-oxygen up to 3.2 | large pilot-scale fluidised bed / mixed plastic waste from separate collection of MSW / steam + O2-enriched air | Parrillo et al., SSRN preprint (title not given in the task file) -- https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4737155 | the lower end of the range, whether the ratio is molar or mass based, bed temperature, gas composition, LHV | literature-informed Assumed: a value from another plant and feed, not DOK-ING's and not validated for GA-001. One-sided statement ('up to'). |
| mdpi_er_bed_temperature | ER, bed temperature and test rig | ER, 0.25 fixed; lab BFB 1–4 kg/h, 0.10 m ID; pellets of 50 % brown coal, 30 % recycled polyolefin plastics, 20 % wood; air reference with silica sand at 861 °C, O2-enriched air up to 902 °C | lab bubbling fluidised bed, 1–4 kg/h, 0.10 m ID / pellets of 50 % brown coal, 30 % recycled polyolefin plastics, 20 % wood / air (reference, silica sand) and O2-enriched air | Sustainability 2023, 15(9), 7547 (title not given in the task file) -- https://www.mdpi.com/2071-1050/15/9/7547 | absolute gas compositions (the abstract gives changes and maxima) | literature-informed Assumed: a value from another plant and feed, not DOK-ING's and not validated for GA-001. Coal-plastic-wood pellets, not MSW. |
| mdpi_performance | cold-gas efficiency, LHV, tar and gas yield | Cold-gas efficiency 59.3 % (air) → 68.6 % (O2-enriched air); LHV up to 9.32 MJ/Nm3; air/steam with olivine: tar −94.5 % and gas yield 2.98 Nm3/kg against air with silica sand | lab bubbling fluidised bed, 1–4 kg/h, 0.10 m ID / pellets of 50 % brown coal, 30 % recycled polyolefin plastics, 20 % wood / air, O2-enriched air, air/steam; silica sand and olivine bed | Sustainability 2023, 15(9), 7547 (title not given in the task file) -- https://www.mdpi.com/2071-1050/15/9/7547 | absolute compositions (the abstract gives these as changes or maxima); the cold-gas-efficiency definition is not given here | literature-informed Assumed: a value from another plant and feed, not DOK-ING's and not validated for GA-001. Changes and maxima, not absolute compositions; the basis of the cold-gas efficiency is not given. |
| bates_bench_bfb | ER, steam/biomass ratio, bed temperature, residence time, char build-up, naphthalene | ER 0–0.157 (air runs 0, 0.052, 0.104, 0.157), steam/biomass ratio 1 (steam only) and 1.091→0.545 (air runs), bed 750–850 °C, 3 kg olivine, gas residence time 0.5–0.7 s in the bed and 4–30 s in the freeboard, char build-up "may take several hours"; naphthalene 108–122 ppm | 5 kWth bench-scale bubbling fluidised bed / biomass / steam only and air + steam, olivine bed | Bates et al., multi-scale models and experimental validation (title as given; year not confirmed) -- https://www.osti.gov/servlets/purl/1364050 | publication year; basis of the steam/biomass ratio; gas composition | literature-informed Assumed: a value from another plant and feed, not DOK-ING's and not validated for GA-001. Bench scale (5 kWth), olivine bed, biomass; year not confirmed. |
| vtt_sewage_sludge_parametric | temperature, ER and steam/fuel effects on gas composition | Sewage sludge BFB: bed 650/750/850 °C, ER 0.2/0.3/0.4, steam/fuel 0.5/1/1.5, 36 experiments; stated trends: higher temperature raises H2 and CO and lowers CO2 and CH4; ER 0.2 best for H2 and CO; higher steam/fuel favours H2; no numerical concentrations on the page | bubbling fluidised bed (size not stated here) / sewage sludge / air and steam | Parametric study of sewage sludge gasification in air and steam e… (title truncated on the page) -- https://cris.vtt.fi/en/publications/parametric-study-of-sewage-sludge-gasification-in-air-and-steam-e/ | numerical gas concentrations, the basis of the steam/fuel ratio, the bed size, the full title | literature-informed Assumed: a value from another plant and feed, not DOK-ING's and not validated for GA-001. Directions only; sewage sludge, not MSW. Trends are for the ranges tested. |
| srf_lab_bfb | ER, temperature, H2 + CO, LHV, cold-gas efficiency | Solid refuse fuel, lab BFB: ER 0.2–0.6, best at ER 0.4 and 900 °C; H2 + CO 72.53 %; LHV 14.43 MJ/Nm3; cold-gas efficiency 67.31 %; basis of the gas percentages not stated | lab bubbling fluidised bed / solid refuse fuel / not stated in the task file | Springer article s12649-018-0431-6 (title not given in the task file) -- https://link.springer.com/article/10.1007/s12649-018-0431-6 | the basis of the gas percentages (dry or wet, N2-free or not), the gasifying agent in the task file | literature-informed Assumed: a value from another plant and feed, not DOK-ING's and not validated for GA-001. The basis of the gas percentages is not stated, so H2 + CO 72.53 % cannot be compared with a model fraction without a guess. |
| clg_5mwth_pilot | chemical looping gasification, temperatures, oxygen-to-fuel ratio, CH4, cold-gas efficiency, tar | Chemical looping gasification, 5 MWth pilot, wood pellets, ilmenite: fuel reactor 850–980 °C, air reactor 900–1020 °C, oxygen-to-fuel ratio 0.4–0.8, over 40 h continuous, CH4 5–10 vol %, cold-gas efficiency over 50 %, almost no tar | 5 MWth pilot / wood pellets / ilmenite oxygen carrier (chemical looping), air reactor | ScienceDirect S0016236125021970 (title not given in the task file) -- https://www.sciencedirect.com/science/article/abs/pii/S0016236125021970 | any waste-derived feed; the basis of the CH4 vol % | literature-informed Assumed: a value from another plant and feed, not DOK-ING's and not validated for GA-001. Wood pellets, not waste; dual-reactor chemical looping, a different configuration from a single BFB. |
| suarez_almeida_transient | transient time scales of a fluidised-bed gasifier | transient response can extend for more than an hour, attributed to the char inventory (validated against lab-scale transient tests); optimised start-up can cut the transient by up to 75 % | fluidised-bed gasifier model, validated against lab-scale transient tests / not stated in the task file / not stated in the task file | Suárez-Almeida et al., Fuel 274, 2020 -- https://research.chalmers.se/en/publication/516472 | individual time constants, the feed, the scale of the plant | literature-informed Assumed: a value from another plant and feed, not DOK-ING's and not validated for GA-001. Gives an order of magnitude for the char-inventory transient, not a time constant for any single model lag. |
| chalmers_devolatilisation_transient | devolatilisation and char accommodation time scales | Devolatilisation transient "a few seconds"; char accommodation "minutes to hours"; no specific time constants (simulation, no validation stated) | simulation / not stated in the task file / not stated in the task file | Chalmers research record 503301 (title not given in the task file) -- https://research.chalmers.se/en/publication/503301 | specific time constants, any validation | literature-informed Assumed: a value from another plant and feed, not DOK-ING's and not validated for GA-001. Qualitative time scales from a simulation with no validation stated; no number to compare with. |
| grasys_psa_vendor | PSA recovery, purity and pressure | PSA (vendor page): recovery up to 90 %, purity up to 99.999 %, pressure up to 5.5 MPa | vendor product page / not stated / not applicable | grasys.com, hydrogen adsorption product page -- https://grasys.com/products/gas/hydrogen/adsorption | feed composition, the conditions at which the maxima hold | literature-informed Assumed: a value from another plant and feed, not DOK-ING's and not validated for GA-001. Vendor marketing, not independent; maxima, not typical values. |
| nrel_station_throughput_2015 | hydrogen station throughput, 2015 data | Hydrogen stations, 2015 data: highest station average 35 kg/day; no hourly values in the text | hydrogen fuelling stations, 2015 data / not applicable / not applicable | NREL report fy16osti/65485 -- https://www.nrel.gov/docs/fy16osti/65485.pdf | hourly values | literature-informed Assumed: a value from another plant and feed, not DOK-ING's and not validated for GA-001. A dispensing demand scale, not a gasifier quantity; 2015 data. |

## 6. Not found

- **gasifier temperature lag**: no published value found.
- **tail-gas recycle delay**: no published value found.
- **cooling-basin lag**: no published value found.
- **waste-derived chemical-looping gasification data**: no readable source; the 5 MWth pilot used wood pellets.

## Appendix: trend-check tables (generated by `scripts/run_literature_trend_check.py`)

Offline run, 0 database / network calls. Dry mol % at the GA-001 outlet; LHV is SA-006's dry composition-weighted LHV; H2 product is HB-012. No cold-gas efficiency (the repo computes none).

### Sweep: ER

| sweep | value | cycles | H2 % dry | CO % dry | CO2 % dry | CH4 % dry | N2 % dry | dry flow Nm3/h | H2O % wet | LHV dry MJ/Nm3 | H2 in gas mol/h | H2 product kg/h | note |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ER | 0.2 | 30 | 32.43 | 23.82 | 8.56 | 1.70 | 33.49 | 98.70 | 17.33 | 7.115 | 1427.8 | 3.6217 | recycle active |
| ER | 0.25 | 30 | 27.45 | 21.46 | 9.80 | 1.65 | 39.64 | 102.75 | 18.40 | 6.259 | 1258.5 | 3.2510 | recycle active |
| ER | 0.3 | 30 | 23.08 | 19.18 | 11.01 | 1.59 | 45.14 | 106.87 | 19.25 | 5.480 | 1100.4 | 2.8891 | recycle active |
| ER | 0.4 | 30 | 15.87 | 14.84 | 13.35 | 1.48 | 54.45 | 115.20 | 20.44 | 4.117 | 815.7 | 2.1916 | recycle active |
| ER | 0.2 | 1 | 28.76 | 25.11 | 11.00 | 1.90 | 33.24 | 82.86 | 18.48 | 6.952 | 1063.0 | 2.8213 | no recycle |
| ER | 0.25 | 1 | 24.70 | 22.21 | 12.01 | 1.80 | 39.29 | 87.44 | 19.37 | 6.112 | 963.4 | 2.5811 | no recycle |
| ER | 0.3 | 1 | 21.08 | 19.53 | 12.97 | 1.71 | 44.71 | 92.07 | 20.12 | 5.352 | 866.1 | 2.3363 | no recycle |
| ER | 0.4 | 1 | 14.98 | 14.73 | 14.75 | 1.55 | 53.98 | 101.48 | 21.26 | 4.031 | 678.3 | 1.8369 | no recycle |

### Sweep: temperature degC

| sweep | value | cycles | H2 % dry | CO % dry | CO2 % dry | CH4 % dry | N2 % dry | dry flow Nm3/h | H2O % wet | LHV dry MJ/Nm3 | H2 in gas mol/h | H2 product kg/h | note |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| temperature degC | 750 | 30 | 29.72 | 17.60 | 12.72 | 1.60 | 38.37 | 106.30 | 15.68 | 5.998 | 1409.5 | 3.2464 | recycle active |
| temperature degC | 800 | 30 | 29.07 | 18.70 | 11.89 | 1.61 | 38.73 | 105.28 | 16.47 | 6.072 | 1365.5 | 3.2474 | recycle active |
| temperature degC | 850 | 30 | 28.48 | 19.70 | 11.13 | 1.62 | 39.06 | 104.35 | 17.18 | 6.140 | 1326.0 | 3.2485 | recycle active |
| temperature degC | 900 | 30 | 27.94 | 20.62 | 10.44 | 1.63 | 39.36 | 103.51 | 17.82 | 6.203 | 1290.4 | 3.2498 | recycle active |
| temperature degC | 950 | 30 | 27.45 | 21.46 | 9.80 | 1.65 | 39.64 | 102.75 | 18.40 | 6.259 | 1258.5 | 3.2510 | recycle active |
| temperature degC | 750 | 1 | 27.29 | 17.99 | 15.04 | 1.74 | 37.93 | 90.56 | 16.50 | 5.838 | 1102.7 | 2.5755 | no recycle |
| temperature degC | 800 | 1 | 26.56 | 19.18 | 14.19 | 1.76 | 38.31 | 89.66 | 17.33 | 5.915 | 1062.6 | 2.5768 | no recycle |
| temperature degC | 850 | 1 | 25.89 | 20.27 | 13.40 | 1.77 | 38.66 | 88.84 | 18.08 | 5.986 | 1026.2 | 2.5781 | no recycle |
| temperature degC | 900 | 1 | 25.27 | 21.28 | 12.68 | 1.79 | 38.99 | 88.11 | 18.76 | 6.052 | 993.2 | 2.5796 | no recycle |
| temperature degC | 950 | 1 | 24.70 | 22.21 | 12.01 | 1.80 | 39.29 | 87.44 | 19.37 | 6.112 | 963.4 | 2.5811 | no recycle |

### Sweep: steam/feed kg/kg dry

| sweep | value | cycles | H2 % dry | CO % dry | CO2 % dry | CH4 % dry | N2 % dry | dry flow Nm3/h | H2O % wet | LHV dry MJ/Nm3 | H2 in gas mol/h | H2 product kg/h | note |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| steam/feed kg/kg dry | 0.2 | 30 | 26.07 | 23.83 | 7.99 | 1.68 | 40.43 | 100.64 | 13.59 | 6.421 | 1170.7 | 3.2551 | recycle active |
| steam/feed kg/kg dry | 0.4 | 30 | 27.45 | 21.46 | 9.80 | 1.65 | 39.64 | 102.75 | 18.40 | 6.259 | 1258.5 | 3.2510 | recycle active |
| steam/feed kg/kg dry | 0.5 | 30 | 28.04 | 20.46 | 10.56 | 1.63 | 39.31 | 103.66 | 20.65 | 6.192 | 1296.6 | 3.2495 | recycle active |
| steam/feed kg/kg dry | 0.8 | 30 | 29.49 | 17.99 | 12.42 | 1.60 | 38.50 | 105.93 | 26.80 | 6.025 | 1393.5 | 3.2467 | recycle active |
| steam/feed kg/kg dry | 1 | 30 | 30.27 | 16.68 | 13.41 | 1.58 | 38.07 | 107.16 | 30.45 | 5.937 | 1447.0 | 3.2458 | recycle active |
| steam/feed kg/kg dry | 1.2 | 30 | 30.94 | 15.55 | 14.25 | 1.57 | 37.70 | 108.21 | 33.78 | 5.861 | 1493.7 | 3.2455 | recycle active |
| steam/feed kg/kg dry | 1.5 | 30 | 31.79 | 14.13 | 15.30 | 1.55 | 37.24 | 109.55 | 38.25 | 5.767 | 1553.8 | 3.2458 | recycle active |
| steam/feed kg/kg dry | 0.2 | 1 | 22.62 | 25.57 | 9.59 | 1.85 | 40.37 | 85.10 | 13.24 | 6.331 | 858.9 | 2.5874 | no recycle |
| steam/feed kg/kg dry | 0.4 | 1 | 24.70 | 22.21 | 12.01 | 1.80 | 39.29 | 87.44 | 19.37 | 6.112 | 963.4 | 2.5811 | no recycle |
| steam/feed kg/kg dry | 0.5 | 1 | 25.52 | 20.87 | 12.97 | 1.78 | 38.86 | 88.41 | 22.20 | 6.025 | 1006.6 | 2.5790 | no recycle |
| steam/feed kg/kg dry | 0.8 | 1 | 27.45 | 17.75 | 15.22 | 1.74 | 37.85 | 90.75 | 29.75 | 5.822 | 1111.2 | 2.5753 | no recycle |
| steam/feed kg/kg dry | 1 | 1 | 28.42 | 16.17 | 16.36 | 1.71 | 37.34 | 91.98 | 34.09 | 5.719 | 1166.2 | 2.5744 | no recycle |
| steam/feed kg/kg dry | 1.2 | 1 | 29.22 | 14.87 | 17.30 | 1.69 | 36.93 | 93.03 | 37.95 | 5.635 | 1212.7 | 2.5744 | no recycle |
| steam/feed kg/kg dry | 1.5 | 1 | 30.20 | 13.28 | 18.44 | 1.67 | 36.42 | 94.33 | 43.00 | 5.531 | 1270.8 | 2.5753 | no recycle |

### Direction comparison (published trend vs model)

Threshold: a change below 0.05 percentage points of dry mol % counts as 'no effect'. AGREES needs every named species to move the stated way; magnitude is not compared. The published page states directions only (no concentrations).

| published trend | model compared | state | verdict | reason |
|---|---|---|---|---|
| higher temperature raises H2 and CO, lowers CO2 and CH4 (VTT sludge study) | 750 -> 950 degC | converged | DISAGREES | H2: stated up, model down (-2.27 pp) DIFFERS; CO: stated up, model up (+3.86 pp) ok; CO2: stated down, model down (-2.92 pp) ok; CH4: stated down, model no effect (+0.05 pp) DIFFERS |
| higher temperature raises H2 and CO, lowers CO2 and CH4 (VTT sludge study) | 750 -> 950 degC | no recycle | DISAGREES | H2: stated up, model down (-2.60 pp) DIFFERS; CO: stated up, model up (+4.21 pp) ok; CO2: stated down, model down (-3.03 pp) ok; CH4: stated down, model up (+0.06 pp) DIFFERS |
| higher steam ratio raises H2 (VTT sludge study) | 0.5 -> 1.5 kg/kg | converged | AGREES | H2: stated up, model up (+3.75 pp) ok |
| higher steam ratio raises H2 (VTT sludge study) | 0.5 -> 1.5 kg/kg | no recycle | AGREES | H2: stated up, model up (+4.68 pp) ok |
| higher steam ratio raises H2 (VTT sludge study) | 0.2 -> 1.5 kg/kg | converged | AGREES | H2: stated up, model up (+5.72 pp) ok |
| higher steam ratio raises H2 (VTT sludge study) | 0.2 -> 1.5 kg/kg | no recycle | AGREES | H2: stated up, model up (+7.57 pp) ok |
| lower ER (0.2 against 0.4) gives more H2 and CO (VTT sludge study) | ER 0.40 vs 0.20 | converged | AGREES | H2: stated lower at 0.40 than at 0.20, model down (-16.55 pp) ok; CO: stated lower at 0.40 than at 0.20, model down (-8.98 pp) ok |
| lower ER (0.2 against 0.4) gives more H2 and CO (VTT sludge study) | ER 0.40 vs 0.20 | no recycle | AGREES | H2: stated lower at 0.40 than at 0.20, model down (-13.77 pp) ok; CO: stated lower at 0.40 than at 0.20, model down (-10.38 pp) ok |

### Plain comparisons (no trend claimed)

| quantity | model | published | comment |
|---|---|---|---|
| steam ratio default vs published steam/fuel 0.5-1.5 (VTT, basis unstated) | model 0.4 kg steam / kg dry feed | published 0.5, 1.0, 1.5 (kg/kg assumed; the page states no basis) | the default is below the lowest published value by 0.1 kg/kg; the three published values were run (sweep above) |
| steam ratio default vs published steam-to-carbon 0.7-1.13 (Parrillo, unit unstated) | model 0.593 mol steam / mol feed carbon (= 0.4 kg/kg x conversion) | published 0.7-1.13 | if the page's ratio is mol/mol the default is below the range; if it is kg/kg it cannot be compared; unit not stated, so no verdict |
| ER default vs published ER | model 0.25 | Parrillo 0.22-0.25; MDPI 0.25; Bates 0-0.157; VTT 0.2-0.4; SRF best 0.4 | inside Parrillo's range (at its upper end) and equal to the MDPI value |
| temperature default vs published | model 950 degC | VTT 650-850; Bates 750-850; MDPI 861-902; SRF best 900; CLG fuel reactor 850-980 | above every bubbling-bed lab range; inside the CLG fuel-reactor range |
| dry LHV | model 6.26 MJ/Nm3 (dry, H2+CO+CH4) | MDPI up to 9.32; SRF 14.43 (basis not stated) | model is below both; different feeds, agents and bases, no verdict |
| CH4 | model 1.65 vol % dry | CLG pilot 5-10 vol % | different configuration; CH4 in the model is a fixed 5 % of converted carbon, not a result |
| PSA recovery | model 0.79 (HB-006) | vendor page: up to 90 % | within the vendor maximum; vendor marketing |

### Not testable here

| published item | verdict | reason |
|---|---|---|
| cold-gas efficiency 59.3 -> 68.6 % (MDPI), 67.31 % (SRF), > 50 % (CLG) | NOT TESTABLE | the repo computes no cold-gas efficiency; adding a definition is outside this task |
| tar -94.5 % with olivine; naphthalene 108-122 ppm; CLG 'almost no tar' | NOT TESTABLE | GA-001 tar is permanently Missing (ga001_gasifier_model.py:842) |
| transient > 1 h (char inventory); devolatilisation seconds; char minutes to hours | NOT TESTABLE | steady-state check only; the dynamics layer is a separate, Assumed model |
| H2 + CO 72.53 % (SRF) | NOT TESTABLE | the basis of the percentage is not stated |
