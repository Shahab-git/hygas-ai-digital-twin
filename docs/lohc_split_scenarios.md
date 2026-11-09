# Liquid-carrier (LOHC) split scenarios (Phase 1, task P1-14)

Date: 2026-11-09. Basis: `main` at `0396c2b`. Reproduce: `python scripts/run_lohc_split_scenarios.py` (about 1 minute; read-only, offline, in-memory fake store, no database or network). **This is a scenario sweep. It does not choose a split.** The engine is unchanged: `("HB-007","H2SplitFraction")` and the chain behind it (HB-014 mass balance, HB-015, HB-016, HB-017) stay Missing.

## 1. Why a sweep and not a number

No source states what share of the PSA hydrogen goes to the carrier branch (`docs/master_open_questions.md` item 9). Literature cannot say: it is a plant design and operating choice. The owner asked for explicit scenario parameters instead of one invented number (gate record 3e). So the split is swept over 0 to 1 and the consequences are shown with the registry's own capacities and efficiencies. When DOK-ING states its split, the matching row is the answer.

## 2. What the sweep uses (all registry values, Unverified (registry), not DOK-ING-confirmed, unless stated)

| quantity | value | source |
|---|---|---|
| capacity of loading, release and purification | 2 kg H2/h | HB-014, HB-016, HB-017 |
| loading, release, polishing recovery | 6.2 wt%, 6.0 wt%, 0.99 | HB-014, HB-016, HB-017 |
| carrier throughput at capacity | 0.031 m3/h | HB-015 remark |
| carrier density | about 1041 kg/m3 | **Estimated**, derived from the line above and the 6.2 wt% loading |
| dehydrogenation enthalpy | 67 kJ/mol H2 | HB-016 remark; the same magnitude is assumed for the exothermic hydrogenation (**Assumed**) |
| rich tank | 1 m3 | HB-015 |
| PSA hydrogen basis | 3.251 kg/h (live, `regasify`), 2.323 (live, `heat_only`), 1.85 (registry) | engine HB-012 at 30 cycles; HB-014 remark |

Model: hydrogen to the branch = min(split x PSA hydrogen, 2 kg/h); carrier = hydrogen / loading; hydrogen released = loaded x (6.0 / 6.2) x 0.99; heat = moles x 67 kJ/mol. At capacity it reproduces the registry's own numbers: 0.031 m3/h (by construction), 18.5 kW (registry 19 kW for 1,000 mol/h; 2 kg/h is 992 mol/h) and a rich tank of about 32 hours ("roughly a day's buffer").

## 3. Result (measured 2026-11-09)

| basis | split 0 | 0.25 | 0.5 | 0.75 | 1.0 |
|---|---|---|---|---|---|
| live `regasify`, H2 loaded (kg/h) | 0 | 0.81 | 1.63 | 2.00 (clipped) | 2.00 (clipped) |
| live `regasify`, to compressed route | 3.25 | 2.44 | 1.63 | 1.25 | 1.25 |
| live `heat_only`, H2 loaded | 0 | 0.58 | 1.16 | 1.74 | 2.00 (clipped) |
| registry 1.85 kg/h, H2 loaded | 0 | 0.46 | 0.93 | 1.39 | 1.85 |
| hydrogenation heat (kW), range over bases | 0 | 4.3 to 7.5 | 8.5 to 15.0 | 12.8 to 18.5 | 17.1 to 18.5 |
| dehydrogenation heat (kW), range over bases | 0 | 4.1 to 7.2 | 8.2 to 14.4 | 12.3 to 17.7 | 16.4 to 17.7 |

- Round trip: 95.8 % of the loaded hydrogen is released (6.0 / 6.2 x 0.99); the rest is lost in the sweep's own assumptions.
- On the live `regasify` hydrogen (3.25 kg/h) any split above about 0.62 saturates the 2 kg/h branch; the registry's 1.85 kg/h basis never saturates. The two hydrogen bases (live 3.25 against registry 1.85) are the known hydrogen disagreement (`docs/tail_gas_heat.md`); the sweep shows both.
- The carrier branch is a heat source on loading (about 4 to 18 kW) that the twin does not integrate anywhere (`docs/plant_heat_integration.md` lists the dehydrogenation heat as a Missing sink).

## 4. What this does not show

- It does not choose a split or say how DOK-ING will operate the branch.
- It does not model reaction kinetics (Missing), start-up, carrier losses or ageing, heat integration, or the off-site transport of rich oil.
- The 67 kJ/mol for hydrogenation, the carrier density and the equality of loading and release capacity are assumptions or derivations from registry text, not data.
- It does not change the Missing status of any key. Wiring a chosen split into the engine would be a separate task with its own Gate 4 statement.

## 5. Question for DOK-ING

Draft request #3, question 4: what share of the PSA hydrogen goes to the carrier branch, and is it fixed or controlled? The answer replaces this sweep by one row.
