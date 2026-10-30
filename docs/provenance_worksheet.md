# Provenance worksheet (phase 1 of 2: nothing is applied)

Source: `docs/registry_status_audit.md` found that 766 registry rows count as Confirmed only because `python/equipment_datasheet.py:512` defaults a missing status to Confirmed, and only 16 have a DOK-ING line in the repo. The owner has said where the values came from (most from similar MSW / gasification plants, some from DOK-ING, some assumed); **Claude does not guess which row is which.** This phase builds the instrument the owner uses to state the origin of each row, validates the answers, and prepares the overlay a later phase would apply. **No status, default, registry row or UI is changed.** Phase 2, after the worksheet is filled, applies the answers (a separate task).

Files: `scripts/make_provenance_worksheet.py` (generator), `python/provenance_overlay.py` (vocabulary, validator, overlay, effect), `scripts/check_provenance_worksheet.py` (read-only checker), `tests/test_provenance_overlay.py`.

## Origin vocabulary and the status a later phase would apply

| origin | required | would become | notes |
|---|---|---|---|
| `DOK-ING` | `source`: document name, date, page/line or e-mail date | Confirmed | without a source: rejected ("Confirmed needs a citable DOK-ING source") |
| `SIMILAR_PLANT` | `source`: paper, plant, URL (may be the project's literature reference) | Estimated (literature-informed) | never Confirmed; without a source: rejected |
| `ASSUMED` | `note`: the reason | Assumed | `source` optional |
| `CALCULATED` | `source`: the formula or script reference | Calculated | |
| `UNKNOWN` / blank | nothing | stays "Unverified (registry)" | listed as a gap; a blank is never read as DOK-ING |

Any other `origin` is rejected. Duplicate `row_id`s and `row_id`s not in the registry are rejected. A `value` that differs from the registry value is reported as a conflict and ignored (the worksheet never edits a value).

## How to use it

1. `python scripts/make_provenance_worksheet.py` writes `outputs/provenance/provenance_worksheet.csv` and `.xlsx` (the xlsx needs `openpyxl`, which is installed locally but is **not in `requirements.txt`**; the CSV always works).
2. Fill the yellow columns `origin`, `source`, `note` (a drop-down is in the xlsx). Rows are sorted most important first (`priority` 1 = 50 rows, 2 = 38, 3 = 727). **Prefilled:** the 16 E1 rows (origin `DOK-ING`, source = the quoted `data/dokink_rfi_answers.md` line). E2 / E3 rows show their own remark and are left for you; the 690 E4 rows are blank.
3. `python scripts/check_provenance_worksheet.py <filled file>` prints the validation report and what the counts would be (row level and the app's slot level). It changes nothing.

## Fill these first (50 rows)

Priority 1 = rows the parameter table uses, rows whose exact field name the engine / model code cites (a heuristic: the code names them, it does not read them from the registry), the audit's E2/E3 rows in GA-001, GA-003, GA-004, GA-005 to GA-010, HB-007, HB-008, HB-009, HB-012, and the SA-001 to SA-005 Expected compositions.

| # | item | field | value | audit | what the row's own remark / the audit says |
|---|---|---|---|---|---|
| 1 | FE-004 | Throughput capacity | 0.1 t/h | E4 |  |
| 2 | FE-005 | Residence time | 15 min | E4 |  |
| 3 | GA-001 | Operating temperature (typical) | 950 °C | E3 | Matches the value already used in the mass/energy balance dashboard and Simulink thermal-lag model |
| 4 | GA-001 | Design pressure | 500 mbar(g) | E4 |  |
| 5 | GA-001 | Residence time (design) | 20 min | E4 |  |
| 6 | GA-002 | Design pressure | 500 mbar(g) | E4 |  |
| 7 | GA-002 | Operating pressure range | 50-150 mbar(g) | E2 | Band around the 100 mbar(g) typical value, reflecting the 70-120% feed turndown DOK-ING specified |
| 8 | GA-003 | Primary air flow rate (design) | 60 Nm³/h | E3 | Derived from ER=0.25 × stoichiometric air demand for the dry feed rate — not DOK-ING-confirmed, treat as an estimate |
| 9 | GA-003 | Steam flow rate (design) | 15 kg/h | E3 | Directly matches the 0.4 kg steam/kg dry feed ratio already used in the mass/energy balance (37.5 kg/h dry feed x 0.4) |
| 10 | GA-003 | Air-to-fuel equivalence ratio (ER) | 0.25 — | E2 | Partial oxidation for autothermal heat; majority of gasification still driven by steam reactions per DOK-ING's steam-blown spec |
| 11 | GA-004 | Air preheat temperature | 200 °C | E4 |  |
| 12 | GA-004 | Steam temperature (design) | 350 °C | E4 |  |
| 13 | GA-005 | Ash discharge rate (design) | 10 % of feed | E3 | Matches the 10% ash content (dry basis) already used in the mass/energy balance |
| 14 | GA-008 | Design capacity | 3 kg/h | E3 | Margin above the ~1.88 kg/h nominal (2.25 kg/h at 120% turndown) already used in the mass/energy balance |
| 15 | GA-008 | Collection efficiency | >95 % | E4 |  |
| 16 | GA-009 | Design capacity | 5 kg/h | E3 | Margin above the ~3.75 kg/h ash rate (10% of dry feed) already established in the mass/energy balance |
| 17 | GC-001 | Design gas flow rate | 50 Nm³/h | E3 | Matches the ~46.9 kg/h raw syngas mass flow already established in the mass/energy balance, converted at typical syngas density |
| 18 | GC-002 | Collection efficiency (design) | >90 % > d50 | E4 |  |
| 19 | GC-003 | Design gas flow rate | 50 Nm³/h | E4 |  |
| 20 | GC-003 | Dust loading inlet (max) | 2 g/Nm³ | E4 |  |
| 21 | GC-005 | Water supply temperature | 20 °C | E4 |  |
| 22 | GC-009 | Design gas flow | 50 Nm3/h | E4 |  |
| 23 | GC-010 | Inlet dust loading | 300 mg/Nm³ | E4 |  |
| 24 | GC-013 | Design gas flow rate | 50 Nm³/h | E4 |  |
| 25 | SA-001 | Expected H₂ concentration | 32-33 vol% | E3 | Matches the value already used in the mass/energy balance dashboard's gas composition chart |
| 26 | SA-002 | Expected CO concentration | 28 vol% | E3 | Matches the value already used in the mass/energy balance dashboard's gas composition chart |
| 27 | SA-003 | Expected CO₂ concentration | 22 vol% | E3 | Matches the value already used in the mass/energy balance dashboard's gas composition chart |
| 28 | SA-004 | Expected CH₄ concentration | 8 vol% | E3 | Matches the value already used in the mass/energy balance dashboard's gas composition chart |
| 29 | SA-005 | Expected N₂ concentration | 10 vol% | E3 | Matches the value already used in the mass/energy balance dashboard's gas composition chart |
| 30 | SA-010 | Operating pressure | 50 mbar(g) | E4 |  |
| 31 | HB-001 | Inlet temperature (design) | 350 °C | E3 | Matches the value already used in the mass/energy balance dashboard's temperature profile |
| 32 | HB-003 | Hot side outlet temperature | 220 °C | E3 | Matches the WGS-LTS inlet temperature already established in the mass/energy balance dashboard |
| 33 | HB-003 | Cold side outlet temperature | 150 °C | E4 |  |
| 34 | HB-003 | Design heat duty | 5 kW | E3 | Estimated from ~50 kg/h gas flow, ~1.8 kJ/kg路K specific heat, 180°C drop (400°C to 220°C) |
| 35 | HB-004 | Inlet temperature (design) | 220 °C | E4 |  |
| 36 | HB-005 | Steam temperature | 350 °C | E4 |  |
| 37 | HB-007 | H₂ recovery rate (design) | 75 % | E3 | Matches the unconfirmed assumption already flagged and tracked since GC-006 — still pending DOK-ING/vendor confirmation |
| 38 | HB-007 | Product H₂ flow rate | 20.6 Nm³/h | E3 | Calculated: 55% feed H2 content x 50 Nm3/h x 75% recovery — converts to ~1.85 kg/h, modestly below DOK-ING's 50 kg/day (2.083 kg/h) target |
| 39 | HB-007 | Tail gas disposition | Recycled to GA-001 gasifier via HB-009 (PSA Tail Gas Handler) as supplemental fuel — | E3 | Matches the design intent already established for HB-009 — closes a small efficiency loop rather than venting |
| 40 | HB-008 | Adsorption pressure (design) | 7 bar(g) | E2 | Within DOK-ING's actual stated 3-10 bar PSA discharge range — real data, not an assumption |
| 41 | HB-009 | Tail gas disposition | Recycled to GA-001 gasifier as supplemental fuel — | E4 |  |
| 42 | HB-011 | System efficiency | 55 kWh/Nm³ H₂ | E4 |  |
| 43 | HB-011 | Water consumption | ~1 L/Nm³ H₂ | E4 |  |
| 44 | HB-012 | Drive motor power | 10 kW | E3 | Estimated for this flow and compression ratio at small scale |
| 45 | HB-013 | Design pressure | 875 bar(g) | E4 |  |
| 46 | HB-013 | Operating pressure range | 350-700 bar(g) | E1 | data/dokink_rfi_answers.md:36: "350/700 bar" (literal; 350 and 700 bar stated as the two options; the row gives the span between them) |
| 47 | HB-014 | Operating pressure | 40 bar | E4 |  |
| 48 | HB-016 | Operating pressure | 2 bar | E4 |  |
| 49 | HB-017 | Design capacity | 2 kg H₂/h | E4 |  |
| 50 | EU-001 | Stack operating temperature | 750 °C | E4 |  |

## What phase 1 does not do

No status is applied, the default (`equipment_datasheet.py:512`) is unchanged, the registry JSON is unchanged, the app and the what-if tab are unchanged, nothing imports `python/provenance_overlay.py`, and `data/registry_status_overlay.json` is not written (that needs `check_provenance_worksheet.py --write`, not used in this task).

