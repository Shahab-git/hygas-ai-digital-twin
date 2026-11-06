# DOK-ING-dependent items (G5-11)

Date: 2026-11-06. Repository state: `main` at `ab5ad41` (merge of PR #36). **This list changes no value, default or registry row.** Statuses are the ledger's (`docs/design_basis_ledger.md`); nothing here is Confirmed or validated.

## 1. RFI #2 status (owner statement; the repo cannot show it: NOT VERIFIED from the repo)

- DOK-ING's first RFI (17 questions) is answered (`data/dokink_rfi_answers.md`).
- RFI #2 full list: `docs/rfi2_dokink.md`, 24 questions in sections A-G. **Not sent in this form.**
- A short form of 10 points was sent by the owner on **2026-11-06** (the Word file is outside the repo). Its points, mapped by topic to the full list: agent (Q1), oxygen supply (Q2), carrier loop (Q3), air and steam flows (Q4), feed basis dry or as received (Q8), external energy (Q11), PSA recovery (Q13), carbon black and char (Q14), ash and tar (Q15), preheat temperatures (Q19). The mapping is by topic; check it against the Word file.
- **No reply has been received.** The 14 full-list questions the short form does not cover (Q5, Q6, Q7, Q9, Q10, Q12, Q16-Q18, Q20-Q24) are unsent.
- A provisional answer sheet (literature and other-plant experience) exists outside the repo; no value from it is applied to the model.

## 2. Assumed headline values and the question that would resolve each

"Effect if unanswered" is what stays true while the value remains an assumption, using figures already measured in the repo. "Not quantified" means no run in the repo isolates it.

| Value in the model | Status | RFI #2 question | In the short form? | Effect if unanswered |
|---|---|---|---|---|
| Gasifying agent: air, ER 0.25 | Assumed | Q1, Q2, Q3 | yes | Syngas composition (N2 39.6 % vs registry 10 %), flow (102.8 vs 50 Nm3/h), PSA feed H2 (38.1 vs 55 %) and hydrogen (78.0 vs about 50 kg/day) stay in disagreement (G5-07 rows 1-4, 7) |
| Design gas composition, registry "Expected" table | Unverified (registry) | Q5 | no | same rows; the registry values stay unexplained |
| GA-003 air 60 Nm3/h, steam 15 kg/h | air Calculated, steam Assumed | Q4 | yes | model needs 38.8 Nm3/h at ER 0.25 (37.5 kg/h feed basis); the 60 vs 38.8 gap stays open (G5-07 row 6) |
| Steam-to-feed 0.4 kg/kg | Assumed | Q4, Q1 (neither asks the ratio) | partly | literature screen: at the lower edge of published values; effect not quantified |
| Feed rate basis: 41.67 kg/h as-received, moisture 10 % | basis a project decision; moisture Unverified (registry) | Q8, Q6 | Q8 yes | if DOK-ING says "dry", the static modules (circularity, datasheet fills) would have to follow; until then the +11.1 % cycle-1 difference is documented |
| Ash 10 % of dry feed | Assumed | Q6, Q15 | Q15 only | ash and carbon black outputs scale with it; sources span 2.6-22 % |
| Dry ash-free composition C/H/O/N = 50/6/43/1 | Assumed | Q6, Q7 | no | literature screen: outside modern prepared fuels; reference-feed runs give other feeds 3 to 4 times DOK-ING's 50 kg/day; not resolved without DOK-ING's analysis |
| Feed sulfur 200 ppm, chlorine 150 ppm | Assumed, not wired into the model | Q7 | no | no numeric effect today (not wired in); the S/Cl-dependent items (GC-008, GC-009 loads) stay assumptions |
| Carbon conversion 0.90 (Monte Carlo 0.85-0.98) | Assumed | Q14 (asks the flow, not the conversion) | yes | hydrogen 51.4 to 62.7 kg/day across 0.85-0.98 in `heat_only`; carbon black derived 2.013 vs 5 % rule 1.875 kg/h |
| Carbon black and char flow | Calculated / Assumed | Q14, Q15 | yes | GA-008 sizing (capacity 3 kg/h) and the circularity revenue stay unconfirmed; literature screen found no evidence for the 5 % rule |
| Gasifier temperature 950 degC | Assumed (registry value from earlier models) | Q17 | no | over 850-950 degC hydrogen changes by 0.08 % (temperature enters only the shift equilibrium constant); little numeric effect today |
| PSA recovery 75 % target, K1 0.01742 | Assumed | Q13 | yes | hydrogen 54.3 vs 55.7 kg/day if fixed at 75 % (`heat_only`); model value 78.8 % |
| PSA tail gas: re-gasified or burned (`tail_gas_mode`) | Assumed (default `regasify`) | Q9, Q20 | Q9 not; Q20 not | hydrogen 78.0 vs 55.7 kg/day; heat deficit 52 vs 13 kW (G5-07 row 9, decision open) |
| Air preheat 200 degC, steam 350 degC | Assumed | Q19 | yes | steam and preheat duties in the energy balance (13.0 + 61.4 + 3.4 kW) have no heat source in the engine |
| Gas cooler outlet 65 degC, stack 180 degC, excess air 1.2 | Assumed | Q21, Q22 | no | heat deficit moves by +6.7 to +8.5 kW (cooler outlet to 300 degC) and by -2.3 to +2.7 kW (stack 120-250 degC) |
| Heat recovery fractions 0.7 / 0.7 / 0.8 / 0.5 | Assumed | **no question asks them** (considered in the ledger: Q10, Q22, Q23) | no | heat deficit moves by up to about 7 to 8 kW (gas cooler, flue gas), 1.4 kW (shift) and 0.2 kW (ash) across 0.5 to 0.9 (`heat_only`); a new question is needed |
| External energy (electricity, gas) at design point | not modelled | Q11 | yes | plant energy does not close (G5-07 rows 15-17); omitted terms stay Missing |
| Hydrogen output basis (gross or net, availability) | the model reports 100 % availability, gross | Q12 | no | the 78.0 vs about 50 kg/day comparison has an unknown basis |
| Response times (120 s, 1200 s, 30 s) | Assumed | Q16 | no | transient what-if only; no effect on the steady results |

## 3. DOK-ING-dependent items that no RFI #2 question asks (gap)

These are open in `docs/master_open_questions.md` section 1 (the DOK-ING list) but are not in RFI #2, full or short. They would need a further request.

| Item | Model vs registry | Reference |
|---|---|---|
| EU-008 cooling duty | live demand 52.0 kW (baseline 55-60 kW) vs 20 kW (registry, scoped to EU-004 jacket cooling) | master_open_questions 1.1; G5-07 row 10 |
| HB-003 design heat duty | 5 kW (registry) vs 7.38 / 10.72 kW (live hot / cold side) | master_open_questions 1.7; G5-07 row 11 |
| GC-009 HCl removal | 96.67 % computed vs ">97 %" stated | master_open_questions 1.8; G5-07 row 12 |
| HB-007 LOHC branch split | not modelled | master_open_questions 1.9 |
| HB-010 membrane selectivity | Assumed | master_open_questions 1.10 |
| HB-014/016 LOHC catalyst kinetics | Assumed | master_open_questions 1.11 |
| Heat recovery fractions | see section 2 | ledger "considered and left empty" |
| Feeder minimum and maximum rate (FE-003) | Assumed | ledger (RFI2-8 considered, asks the design rate only) |

## 4. Limits

The list maps what the repo documents; it does not predict what DOK-ING will answer. Effects marked with a number come from existing repo reports (`docs/tail_gas_heat.md`, `docs/plant_heat_integration.md`, `docs/balance_closure_audit.md`, the G5-07 list); effects that are not quantified say so. The status of the short-form points rests on the owner's statement and the topic mapping above.
