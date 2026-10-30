# Gasifying agent: where the 39.6 % N2 comes from, and what each agent would give

Written 2026-10-30 on `origin/main` 0ad2403 (branch `gasifying-agent-study`). **Read-only on the engine:** new files only (`scripts/run_agent_comparison.py`, `tests/test_agent_comparison.py`, this document, one `CLAUDE.md` line). No default, Confirmed value, registry entry, `SharedPlantState`, engine API, runtime, dynamics layer, what-if tab, workflow or `requirements.txt` changed. Nothing here is tuned to a composition, and nothing is ranked or recommended: the document lists what the sources say, what the model does, and what each agent gives in the same model. Offline throughout: in-memory fake store, no database, no network, the real `secrets.toml` never read.

## 1. What the sources say about the gasifying agent (item A1)

Quoted as written, with the field name. Contradictions are listed in 1.2 and **not resolved**.

### 1.1 Statements

| # | where | field | verbatim |
|---|---|---|---|
| 1 | `data/equipment_registry.json:568-569` (GA-001) | "Gasifier technology type" | "Bubbling Fluidized Bed (BFB), steam-blown, Fe2O3/Fe3O4 chemical looping oxygen carrier". The entry carries no status field; `docs/master_open_questions.md:272` calls it GA-001's "own Confirmed registry data". |
| 2 | `data/equipment_registry.json:648-651` (GA-003) | "Primary air flow rate (design)" | 60 Nm³/h; remark: "Derived from ER=0.25 × stoichiometric air demand for the dry feed rate — not DOK-ING-confirmed, treat as an estimate" |
| 3 | `data/equipment_registry.json:654-657` (GA-003) | "Steam flow rate (design)" | 15 kg/h; remark: "Directly matches the 0.4 kg steam/kg dry feed ratio already used in the mass/energy balance (37.5 kg/h dry feed x 0.4)" |
| 4 | `data/equipment_registry.json:660-663` (GA-003) | "Air-to-fuel equivalence ratio (ER)" | 0.25; remark: "Partial oxidation for autothermal heat; majority of gasification still driven by steam reactions per DOK-ING's steam-blown spec" |
| 5 | `data/equipment_registry.json:712-715` (GA-004) | "Air preheat temperature" | 200 °C; remark: "Sourced from recovered process heat (same integration approach as FE-007) rather than dedicated fuel-fired preheat" |
| 6 | `data/equipment_registry.json:718-721` (GA-004) | "Steam temperature (design)" | 350 °C; remark: "Superheated — avoids condensation in injection lines and local bed quenching at injection points" |
| 7 | `data/equipment_registry.json:1959-1962`, `2022-2025`, SA-001..004 | "Expected H₂ / CO / CO₂ / CH₄ concentration" | H2 "32-33", CO "28" (CO2 22 and CH4 8 in SA-003 / SA-004), vol%; remark on each: "Matches the value already used in the mass/energy balance dashboard's gas composition chart" |
| 8 | `data/equipment_registry.json:2184-2191` (SA-005) | "Expected N₂ concentration" / "Measurement principle" | "10" vol%, same remark; principle: "Calculated by difference (100% minus sum of SA-001/002/003/004)" |
| 9 | `data/equipment_registry.json:2224-2227` (SA-006) | "Expected LHV" | 9.8 MJ/Nm³; remark: "Calculated from the established gas composition (SA-001/002/004) using standard component LHV values" |
| 10 | `docs/master_open_questions.md:272-281` (item 5) | question text | "not a conventional simple air-blown gasifier. This project's own live gasifier model captures the real, confirmed air (ER=0.25) partial-oxidation contribution and the real, confirmed steam addition ... but it does NOT, and cannot, model the oxygen carrier's own separate reduction/regeneration chemistry and circulation loop" |
| 11 | `docs/master_open_questions.md:359-363` (item 5, 2026-09-08 update) | root cause | "a true carrier-mediated process keeps combustion air confined to a separate air reactor, so the FUEL-side product gas stays close to N₂-free" |
| 12 | `CLAUDE.md:147-153` | known finding | "the registry's own 'Expected' figures are consistent with GA-001's own Confirmed **steam-blown** chemical-looping technology description ... while the live model implements a stated, documented simplification — real Confirmed air (ER=0.25) added directly as a partial-oxidation reactant, not carrier-mediated" |
| 13 | `docs/audit_2026-10-27.md:123` | D4 | "`python/ga001_gasifier_model.py:299–301` gasifying agent is air (see D4); the GA-001 Confirmed technology text says \"steam-blown\"." |
| 14 | `docs/audit_2026-10-27.md:305` | action list | "Decide the composition basis: re-derive registry \"Expected\" from the live model, or re-calibrate the model to the registry (and then decide on steam-blown vs air)." |
| 15 | `docs/digital_twin_engineering_plan.md:440` | GA-001 row | "air-blown/steam gasification" (inputs: "GA-003/004 air+steam flow/temp") |
| 16 | `data/dokink_rfi_answers.md`, `data/rfi_dokink.md` | whole files | **Silent.** A search for air, steam, oxygen, carrier finds no statement in DOK-ING's answers; the RFI asks nothing about the agent. |
| 17 | the registry unit list | whole registry | No unit models an oxygen-carrier loop, an air reactor or an air separation / oxygen supply. |

### 1.2 Contradictions (listed, not resolved)

1. **Technology text vs the rest of GA-001/003/004.** #1 says steam-blown with an oxygen carrier; #2, #4, #5 specify an air flow, an air-to-fuel ER and an air preheat. #4's own remark reads both ways ("partial oxidation" and "steam-blown spec").
2. **"Confirmed" air vs "not DOK-ING-confirmed".** #10 calls the air (ER 0.25) "real, confirmed"; #2 says the air flow is "not DOK-ING-confirmed, treat as an estimate", derived from the ER. The ER's own provenance is not stated in #4.
3. **Three different N2 figures.** The registry Expected set says 10 % (#8); the item-5 argument says the fuel-side gas "stays close to N₂-free" (#11); the model gives 39.6 % (section 2). #12 states the registry set is consistent with the steam-blown description; an N2-free carrier gas would give about 0.4 % (S3 below), not 10 %.
4. **Air flow: registry vs model.** #2 gives 60 Nm³/h; the model's own air at ER 0.25 is 479.9 mol/h O2 = 51.2 Nm³/h air (section 2). The remark says 60 derives from ER 0.25 and the dry feed rate; the two figures differ by 17 %.
5. **The Expected set does not sum to 100.** 32.5 (midpoint of 32-33) + 28 + 22 + 8 + 10 = 100.5, although #8 says N2 is "calculated by difference".
6. **Its LHV.** #9 says 9.8 MJ/Nm³; the repo's own component table gives 9.91 for the same set (section 3).
7. **Provenance of the Expected set.** Every remark points to "the mass/energy balance dashboard's gas composition chart", which is not in the repository; the entries carry no status field, so the remark is the only provenance.

## 2. How the model makes N2 (item A2)

`solve_product_gas` (`python/ga001_gasifier_model.py:292`) has no oxidant argument: the oxidant is air by construction, `o2_actual = er * o2_stoich` (:300), `n2_from_air = o2_actual * (0.79 / 0.21)` (:301), and the product N2 is `z / 2.0 + n2_from_air` (:320, `z` = fuel N per fuel C). N2 never enters the WGS equilibrium or the element equations that fix H2, CO, CO2, CH4, H2O; it only dilutes.

At the default (ER 0.25, steam 0.4 kg/kg, 950 degC, conversion 0.90, 30 cycles):

| N2 source | mol/h | share |
|---|---|---|
| air N2 (O2 479.9 mol/h x 79/21) | 1805.26 | 99.34 % |
| fuel nitrogen (feed N 0.01 daf) | 12.05 | 0.66 % |
| total | 1817.3 | N2 = 39.64 % of the dry gas (dry flow 102.75 Nm³/h) |

So **the 39.6 % is the air**. The model does not make it from the carrier, from steam or from anything the tuning could reach other than ER.

## 3. The registry Expected composition and ER 0.25 (item A3)

- **Origin and status.** See 1.1 #7-#9 and 1.2 #7: a dashboard chart outside the repository; no status field. The set sums to 100.5; its LHV by the repo's component table is 9.91 MJ/Nm³ (registry: 9.8).
- **Is it reachable with air at ER 0.25?** Not by the nitrogen balance. Take 100 mol of dry gas with the Expected 10 mol N2. Carbon in the gas is CO + CO2 + CH4 = 28 + 22 + 8 = 58 mol, so the carbon fed is 58 / 0.90 = 64.4 mol. Fuel nitrogen supplies z/2 = 0.00858 mol N2 per mol C fed, i.e. 0.55 mol. The rest, 10 - 0.55 = 9.45 mol N2, would have to come with 9.45 x 21/79 = 2.51 mol O2. The stoichiometric O2 for this feed is 1.0345 mol per mol C fed (x = H/C = 1.430, y = O/C = 0.646), so the implied ER is 2.51 / (64.4 x 1.0345) = **0.038**, not 0.25. Conversely, ER 0.25 puts 39.6 % N2 in the gas (section 2).
- Scenario S1b (50 % O2) is the nearest the swept agents come to 10 % N2 (15.1 %); S2/S3/S4 are below it (0.3 to 0.6 %). None of them reproduces the full Expected set (section 5.3).

## 4. Can `solve_product_gas` run with an N2-free oxidant without editing GA-001? (item A4)

**Yes**, by an argument and a check, not by an edit. The oxidant enters the solver only through `o2_actual` (O atoms) and `n2_from_air` (inert N2). Because N2 does not enter the WGS equilibrium or the element equations of the other species, replacing the oxidant N2 after the unchanged solver leaves H2/CO/CO2/CH4/H2O exactly as they are for the same oxygen amount. The study overrides `("GA-001", "Outputs")` through the engine's own `build_live_snapshot(overrides=...)`, calls the unchanged `ga001_model`, swaps only the oxidant N2 (fuel N2 stays), and the downstream chain (GC, WGS, PSA, HB-009 recycle) runs for real. Checks in `tests/test_agent_comparison.py`: at the air fraction the wrapper changes nothing (values to 1e-12); the swap is verified by hand; C/H/O/N close below 1e-9 in every scenario. The limit: the swap holds the oxygen amount, so S2/S3 are "the same O2 as S0, no N2", not a re-sized oxygen demand.

## 5. Scenarios and measured results (items B, C)

Scenarios (all on the default stand-in feed, 950 degC, conversion 0.90, 37.5 kg/h dry feed), each in both `tail_gas_mode` values:

| id | agent | what is varied |
|---|---|---|
| S0 | air ER 0.25 + steam 0.4 | the current default |
| S1a | O2-enriched air, 30 % O2 | oxidant N2 only |
| S1b | O2-enriched air, 50 % O2 | oxidant N2 only |
| S2 | oxygen-blown + steam 0.4 | the same O2 as S0, no N2 (O2 source and cost **Missing**) |
| S3 | chemical-looping equivalent | the fuel-side gas of S2 by construction; no gas-phase oxidant energy; air reactor, carrier circulation and oxygen-transfer enthalpy **Missing** |
| S4a / S4b | steam only (allothermal), steam 0.4 / 0.8 | ER = 0; the duty would have to be supplied externally |

Cold-gas efficiency uses the existing `balance_audit` definition only. Energy reuses `balance_audit.gasifier_energy` / `heat_demands` with only the oxidant sensible heat replaced. The tables below are generated by `python scripts/run_agent_comparison.py` (about 80 s; writes `outputs/agents/agent_comparison.md` and `.csv`, git-ignored).

What the numbers show (facts about this model, not about the plant):

- **N2 follows the oxidant.** 39.6 % (air) -> 29.0 % (30 % O2) -> 15.1 % (50 % O2) -> 0.4 % (O2 or carrier). Enriching does not change the hydrogen yield in `regasify` much (78.0, 78.0, 77.7, 77.3 kg/day) (the likely reason, not separately tested: the same carbon, hydrogen and O2 are converted and the tail gas is re-gasified); it raises the LHV (6.26 -> 10.43 MJ/Nm³) and cuts the dry flow and the PSA feed (102.8 -> 64.2 and 120.4 -> 82.9 Nm³/h).
- **In `heat_only` hydrogen is lower** (55.7 -> 50.3 kg/day across S0 to S2) and the tail gas covers more of the demand as the gas gets richer (49.0 -> 55.8 kW used); the net heat is -18.3 kW (S0) to -0.8 kW (S2) at the DOK-ING midpoint LHV 17.5 MJ/kg, with the 15..20 range straddling zero for S0, S1, S2 and S3 (-44.4..+7.7, -26.8..+25.3).
- **Steam-only (S4) gives the most hydrogen** (124.9 / 80.3 kg/day) because no feed is burned, with a gasifier duty of +42 to +58 kW that nothing in the model supplies; its cold-gas efficiency (1.01 to 1.02) is above 1 **because external heat is added**, not because the gas holds more than the feed.
- **S3 equals S2 in gas by construction.** The model cannot tell a carrier from a pure-oxygen blow at the level of the fuel-side gas; what differs is the energy (no oxidant sensible heat) and what is unmodelled.
- **Closure.** C, H, O, N close to below 5e-16 relative in every scenario and both modes.
- **Composition vs the registry.** In `regasify`, the largest deviation from the Expected set is 29.6 pp (S0), 19.0 (S1a), 9.3 (S1b), 17.0 (S2/S3), 27.7 (S4a), 29.1 (S4b). No scenario reproduces the set; the CH4 shortfall (-5.5 to -6.4 pp) is the same in every one, i.e. it is not an agent question.

What the numbers do **not** show:

- Nothing about which agent the plant uses (section 1 is contradictory and the RFI silent).
- Nothing about the cost of the oxygen (S2), the air reactor and the carrier loop (S3), or a heat source for S4: those terms are Missing, not zero, so the net heat of S2/S3 is not a closed plant balance.
- Nothing about tar, temperature-dependent conversion, heat loss or a boiler: the same model gaps as in the feeds study (`docs/reference_feeds.md`).
- The scenarios are not a ranking, and no ER, steam ratio, conversion or temperature was adjusted to a composition.

## 6. Needs your decision

1. **Which agent should the twin represent as the primary design case?** It changes N2 (39.6 vs 29 / 15 / 0.4 %), LHV (6.3 to 10.4 MJ/Nm³), the hydrogen in `heat_only`, the gasifier heat duty and the PSA load (120 vs 83 Nm³/h). The sources do not decide it (section 1).
2. **Should the model expose the agent as a switch** like `tail_gas_mode` (default unchanged)? Today the oxidant is air by construction at `ga001_gasifier_model.py:300-301`; the study reaches the other agents only through an override, outside the live app.
3. **What to ask DOK-ING:** (a) the gasifying agent in the real plant (air, enriched air, oxygen, steam only, carrier); (b) if oxygen or a carrier, where the oxygen comes from (air separation, an air reactor, bottled) and at what duty; (c) the carrier, its circulation rate and conversion per pass (this is also item 5 of the open questions); (d) the steam source and temperature, and whether the 15 kg/h and 60 Nm³/h of GA-003 are design values or estimates.

**Not verifiable here:** Python 3.11 / 3.12 CI; the dashboard chart that the Expected set is said to match.

## Appendix: measured tables (generated by `scripts/run_agent_comparison.py`)

### 1. Gas, hydrogen and load

| scenario | mode | dry mol % H2/CO/CO2/CH4/N2 | dry flow Nm3/h | LHV MJ/Nm3 (dry) | H2 kg/day | carbon black kg/h | PSA feed Nm3/h | N2 vs registry 10 % (pp) |
|---|---|---|---|---|---|---|---|---|
| S0 current: air ER 0.25 + steam 0.4 | regasify | 27.5/21.5/9.8/1.6/39.6 | 102.8 | 6.26 | 78.0 | 2.01 | 120.4 | +29.6 |
| S0 current: air ER 0.25 + steam 0.4 | heat_only | 24.8/22.1/12.1/1.8/39.2 | 78.8 | 6.10 | 55.7 | 1.69 | 92.8 | +29.2 |
| S1a O2-enriched air, 30 % O2 + steam 0.4 | regasify | 33.2/24.8/11.1/1.9/29.0 | 88.0 | 7.38 | 78.0 | 1.98 | 106.0 | +19.0 |
| S1a O2-enriched air, 30 % O2 + steam 0.4 | heat_only | 29.1/25.9/14.2/2.1/28.7 | 67.1 | 7.16 | 54.4 | 1.69 | 81.7 | +18.7 |
| S1b O2-enriched air, 50 % O2 + steam 0.4 | regasify | 41.0/29.0/12.7/2.2/15.1 | 74.3 | 8.87 | 77.7 | 1.94 | 92.7 | +5.1 |
| S1b O2-enriched air, 50 % O2 + steam 0.4 | heat_only | 34.7/30.9/17.0/2.5/15.0 | 56.3 | 8.54 | 52.4 | 1.69 | 71.3 | +5.0 |
| S2 oxygen-blown + steam 0.4 (same O2 as S | regasify | 49.5/33.3/14.3/2.5/0.4 | 64.2 | 10.43 | 77.3 | 1.91 | 82.9 | -9.6 |
| S2 oxygen-blown + steam 0.4 (same O2 as S | heat_only | 40.6/36.1/19.8/2.9/0.6 | 48.1 | 9.99 | 50.3 | 1.69 | 63.6 | -9.4 |
| S3 chemical-looping equivalent (carrier o | regasify | 49.5/33.3/14.3/2.5/0.4 | 64.2 | 10.43 | 77.3 | 1.91 | 82.9 | -9.6 |
| S3 chemical-looping equivalent (carrier o | heat_only | 40.6/36.1/19.8/2.9/0.6 | 48.1 | 9.99 | 50.3 | 1.69 | 63.6 | -9.4 |
| S4a steam only (allothermal), steam 0.4 | regasify | 60.2/34.2/3.4/2.0/0.3 | 83.1 | 11.51 | 124.9 | 1.96 | 108.2 | -9.7 |
| S4a steam only (allothermal), steam 0.4 | heat_only | 51.2/39.5/6.4/2.4/0.5 | 58.7 | 11.37 | 80.3 | 1.69 | 79.5 | -9.5 |
| S4b steam only (allothermal), steam 0.8 | regasify | 61.6/29.0/7.2/1.9/0.3 | 86.8 | 10.98 | 124.8 | 1.97 | 108.3 | -9.7 |
| S4b steam only (allothermal), steam 0.8 | heat_only | 54.2/31.1/12.1/2.3/0.4 | 62.4 | 10.57 | 80.0 | 1.69 | 79.2 | -9.6 |

### 2. Heat balance (kW; + surplus / - deficit; implied gasifier duty + = heat must be added)

| scenario | mode | implied gasifier duty at 17.5 (15 .. 20) | heat demand total (steam + preheat + drying) | tail-gas heat used | NET at 17.5 (15 .. 20) | cold-gas efficiency incl. / net of recycle (existing balance_audit definition) |
|---|---|---|---|---|---|---|
| S0 | regasify | -3.3 (+22.8 .. -29.3) | 80.6 | 0.0 | -77.3 (-103.3 .. -51.3) | 0.73 / 0.64 |
| S0 | heat_only | +0.6 (+26.7 .. -25.4) | 66.7 | 49.0 | -18.3 (-44.4 .. +7.7) | 0.73 / 0.73 |
| S1a | regasify | -7.6 (+18.5 .. -33.6) | 78.8 | 0.0 | -71.2 (-97.3 .. -45.2) | 0.74 / 0.64 |
| S1a | heat_only | -2.7 (+23.4 .. -28.7) | 66.0 | 50.7 | -12.6 (-38.7 .. +13.4) | 0.73 / 0.73 |
| S1b | regasify | -11.8 (+14.3 .. -37.8) | 77.2 | 0.0 | -65.4 (-91.4 .. -39.3) | 0.74 / 0.64 |
| S1b | heat_only | -5.8 (+20.3 .. -31.8) | 65.2 | 53.1 | -6.3 (-32.4 .. +19.7) | 0.73 / 0.73 |
| S2 | regasify | -15.2 (+10.9 .. -41.2) | 75.9 | 0.0 | -60.8 (-86.8 .. -34.7) | 0.74 / 0.64 |
| S2 | heat_only | -8.1 (+18.0 .. -34.1) | 64.7 | 55.8 | -0.8 (-26.8 .. +25.3) | 0.73 / 0.73 |
| S3 | regasify | -14.4 (+11.6 .. -40.5) | 75.2 | 0.0 | -60.8 (-86.8 .. -34.7) | 0.74 / 0.64 |
| S3 | heat_only | -7.5 (+18.5 .. -33.6) | 64.2 | 55.8 | -0.8 (-26.8 .. +25.3) | 0.73 / 0.73 |
| S4a | regasify | +53.8 (+79.8 .. +27.7) | 94.9 | 0.0 | -148.7 (-174.7 .. -122.6) | 1.01 / 1.02 |
| S4a | heat_only | +42.2 (+68.2 .. +16.2) | 80.3 | 63.2 | -59.2 (-85.3 .. -33.2) | 1.02 / 1.02 |
| S4b | regasify | +57.5 (+83.6 .. +31.5) | 98.8 | 0.0 | -156.3 (-182.4 .. -130.3) | 1.01 / 1.01 |
| S4b | heat_only | +45.8 (+71.9 .. +19.8) | 82.7 | 63.8 | -64.8 (-90.8 .. -38.7) | 1.01 / 1.01 |

S3's oxidant sensible heat is zero (no gas-phase oxidant) and the carrier's heat transfer is Missing, so its duty is the duty the circulating solids would have to bring from the air reactor, an unknown not modelled. S4's duty is the heat an external source must supply at 950 degC.

### 3. Registry 'Expected' composition: deviation of each scenario (pp, dry mol %; model minus expected H2 32.5 / CO 28 / CO2 22 / CH4 8 / N2 10)

| scenario (regasify) | H2 | CO | CO2 | CH4 | N2 | largest |deviation| |
|---|---|---|---|---|---|---|
| S0 | -5.0 | -6.5 | -12.2 | -6.4 | +29.6 | 29.6 |
| S1a | +0.7 | -3.2 | -10.9 | -6.1 | +19.0 | 19.0 |
| S1b | +8.5 | +1.0 | -9.3 | -5.8 | +5.1 | 9.3 |
| S2 | +17.0 | +5.3 | -7.7 | -5.5 | -9.6 | 17.0 |
| S3 | +17.0 | +5.3 | -7.7 | -5.5 | -9.6 | 17.0 |
| S4a | +27.7 | +6.2 | -18.6 | -6.0 | -9.7 | 27.7 |
| S4b | +29.1 | +1.0 | -14.8 | -6.1 | -9.7 | 29.1 |

The expected set sums to 100.5 (H2 given as 32-33); it implies, by the nitrogen balance, an air ER of about 0.04 for this feed (this document, section 3). No scenario here is tuned to it.

### 4. Closure (GA-001 control volume and gasification loop, scenario oxidant in the inflow)

| scenario | mode | C max |rel| | H max |rel| | O max |rel| | N max |rel| |
|---|---|---|---|---|---|
| S0 | regasify | 0.0e+00 | 3.7e-16 | 1.6e-16 | 1.3e-16 |
| S0 | heat_only | 0.0e+00 | 2.4e-16 | 1.8e-16 | 0.0e+00 |
| S1a | regasify | 1.6e-16 | 1.8e-16 | 1.6e-16 | 2.0e-16 |
| S1a | heat_only | 1.6e-16 | 2.4e-16 | 0.0e+00 | 0.0e+00 |
| S1b | regasify | 1.6e-16 | 1.8e-16 | 3.2e-16 | 4.5e-16 |
| S1b | heat_only | 3.2e-16 | 1.8e-16 | 1.4e-16 | 1.5e-16 |
| S2 | regasify | 3.2e-16 | 1.7e-16 | 1.6e-16 | 1.5e-16 |
| S2 | heat_only | 0.0e+00 | 1.2e-16 | 0.0e+00 | 1.5e-16 |
| S3 | regasify | 3.2e-16 | 1.7e-16 | 1.6e-16 | 1.5e-16 |
| S3 | heat_only | 0.0e+00 | 1.2e-16 | 0.0e+00 | 1.5e-16 |
| S4a | regasify | 1.6e-16 | 1.3e-16 | 3.6e-16 | 2.9e-16 |
| S4a | heat_only | 1.6e-16 | 1.2e-16 | 0.0e+00 | 0.0e+00 |
| S4b | regasify | 1.6e-16 | 2.5e-16 | 1.7e-16 | 2.9e-16 |
| S4b | heat_only | 1.6e-16 | 0.0e+00 | 1.8e-16 | 0.0e+00 |

### 5. Which scenario is consistent with which source statement (facts about the sources; not a ranking)

| source statement | consistent with | not consistent with |
|---|---|---|
| GA-001 'Gasifier technology type': "Bubbling Fluidized Bed (BFB), steam-blown, Fe2O3/Fe3O4 chemical looping oxygen carrier" (registry) | S3 (carrier oxygen, steam); S4 (steam-blown) | S0, S1, S2 use gas-phase oxidant; the model's own S0 is air-blown |
| GA-003 'Primary air flow rate (design)' 60 Nm3/h, 'Air-to-fuel equivalence ratio (ER)' 0.25, 'Steam flow rate (design)' 15 kg/h (registry) | S0, S1 (an air or air-based oxidant) | S2, S3, S4 have no air flow |
| GA-003 ER remark: "Partial oxidation for autothermal heat; majority of gasification still driven by steam reactions per DOK-ING's steam-blown spec" | S0, S1, S2 (partial oxidation + steam) | S3 (oxygen from the carrier, not partial oxidation by gas), S4 (no oxidation) |
| GA-004 'Air preheat temperature' 200 degC (registry) | S0, S1 (air or enriched air) | S2, S3, S4 |
| SA-005 'Expected N2 concentration' 10 vol %, 'Measurement principle': by difference; SA-001..004 expected H2 32-33, CO 28, CO2 22, CH4 8 (registry; 'Matches the value already used in the mass/energy balance dashboard') | none reproduces the full set (see the deviation table); N2 near 10 % needs an oxidant N2 share far below air's | see the deviation table |
| RFI answers (data/dokink_rfi_answers.md) | silent: no statement on air, steam, oxygen, carrier | - |
| Registry equipment inventory | S0 (GA-003 air injection exists) | S2: no air-separation / O2 unit is registered; S3: no air reactor, cyclone loop or carrier handling unit is registered |
