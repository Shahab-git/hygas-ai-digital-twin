# Data-replacement layer, step 1: parameter table, precedence rule, replay ingestion, residual report

Written 2026-10-30 on `origin/main` af199c3 (branch `data-layer`). The twin runs today on DOK-ING's first file plus published pilot data; when the plant exists, real measurements must replace assumptions without rewriting the model. **This step builds the plumbing and proves it on synthetic data.** It wires nothing into the engine and calibrates nothing: no plant data exists, so fitting now would be tuning to nothing. New modules, scripts, tests and docs only; no engine equation, default, Confirmed value, registry row, `SharedPlantState`, engine API, `run_continuous_cycle.py`, dynamics layer, what-if tab, workflow or `requirements.txt` changed, and **nothing in the engine, runtime or app imports the new modules** (a test scans for it). Offline throughout: in-memory fake store, no database, no network, the real `secrets.toml` never read.

Files: `python/parameter_table.py`, `python/data_precedence.py`, `python/measurement_replay.py`, `scripts/run_residual_report.py`, `tests/test_data_layer.py` (41 tests, about 1 s, 15 of 15 mutants caught), `docs/measurement_replay_schema.md`.

## 1. What the repo has today (item A, report only)

### 1.1 Where each tunable input lives

Full rows (value, unit, status, range, `file:line`) are generated in section 2. How each is read, in short:

| parameter | read how | status / range | overridable without a code edit? |
|---|---|---|---|
| ER | engine input `("GA-001-INPUT","equivalence_ratio")`, `ga001_gasifier_model.py:460`, value from `uncertainty.ASSUMPTIONS` (`uncertainty.py:85`) | Assumed 0.25; +/-15 % band (`UNCERTAINTY_FRACTION`, "our own assumed default") | yes, `build_live_snapshot(overrides={key: fn})` (`tab1_integration.py:56-78`) |
| steam-to-feed | engine input `steam_to_feed_ratio` (`:480`), `uncertainty.py:80` | Assumed 0.4; +/-15 % | yes |
| carbon conversion | engine input `carbon_conversion_efficiency` (`:505`), constant `:217` | Assumed 0.90; (0.85, 0.98) | yes |
| CH4 carbon fraction | engine input (`:518`), constant `:224` | Assumed 0.05; (0.02, 0.08) | yes |
| temperature | engine input `operating_temperature_C` (`:625`), constant `GA001_OPERATING_TEMPERATURE_C = 950.0` (`:230`); the docstring says it is read from the registry, the code holds a constant | Assumed 950; no range in the repo | yes |
| feed composition | engine input `feedstock_composition` (`:571`), constants `:193-196` | Assumed; no range | yes (as C/H/O/N only) |
| dry feed rate | engine input `dry_feed_rate_kg_h` (`:406`), Calculated from FE-005 (37.5 kg/h), placeholder 41.67 when FE-005 is absent | Calculated / Assumed fallback | yes |
| `tail_gas_mode` | engine input (`:1567`, `:1577`) | Assumed switch, `regasify` default | yes |
| `unconverted_carbon_to_carbon_black` | engine input (`:1612`, `:1622`) | Assumed 1.0; (0.5, 1.0) | yes |
| **ash fraction** | module constant `gasifier_mass_balance.ASH_FRACTION` (`:61`), reused by GA-001 | "Confirmed" in the code's words (GA-005 "10% ash content"); DOK-ING band 5-15 % | **no: code only** |
| **PSA recovery** (`psa.K1`, `VOID_LOSS`, `SELECTIVITY`) | module constants (`psa.py:10-12`); the HB-006 adapter does not pass `k1_scale` | no status tag in the repo (the table assigns Assumed and says so) | **no: code only** |
| **`psa_target_calibration`, `wgs_target_calibration`** | `uncertainty.ASSUMPTIONS` (`:100`, `:105`), Monte-Carlo scaling only | Assumed; +/-15 % | **no: code only** (not read by the engine) |
| dynamics taus | `dynamics.TAU_SPECS` (`dynamics.py:108-157`) | Assumed, with ranges | by a function argument of the what-if layer (`run_transient(taus=...)`), not an engine input |
| GA-003 air 60 Nm3/h, steam 15 kg/h, ER 0.25; GA-004 preheat 200 degC, steam 350 degC | registry rows (`data/equipment_registry.json:648, 654, 660, 712, 718`) | counted Confirmed by default; the air row's own remark says "not DOK-ING-confirmed, treat as an estimate" | rows exist but **the engine does not read them** (the only code mention is a print, `ga001_gasifier_model.py:1329`) |

**Cannot be overridden without editing code:** the ash fraction, the PSA constants, and the two target calibrations. The parameter table lists them under their own heading.

### 1.2 `Measured`, statuses and the protection of Confirmed values

- `Measured` is defined at `plant_status.py:52` ("a real sensor/PLC/lab reading (does not exist yet in this repo)"). The only producer is `measurement_promotion.py:92` `record_measurement()`, which calls `SimulationEngine.promote_to_measurement()` (`simulation_engine.py:139`) to swap a model's function for a reader; it is proven only with a synthetic reading. `operator_setpoints.py` and the input functions deliberately tag Assumed, "never Measured". **This task gives `Measured` its defined meaning: a reading from a replay file (later: a live source) whose quality is `good` and which carries no blocking flag.**
- Snapshot entries carry one of the five tags (`plant_status.ALL_STATUSES`) and the fields `value, unit, status, source, validation_basis, confidence_note, cycle, timestamp, missing_reason`, checked by `validate_entry_shape` (`plant_status.py:85`). **`Confirmed` is not a snapshot status.** It lives in the registry (default for every row without a status key, `equipment_datasheet.py:432`), in `design_basis.py` (`status_of`, `set_confirmed`, `:651-679`) and in `uncertainty.set_confirmed` (`:131`), which sets a confirmed RANGE for a Monte-Carlo assumption.
- **Protection from overwrite:** at the registry level only, and only against estimates: `equipment_rfi_fills.py:482` and `equipment_engineering_estimates.py:2554` refuse to append onto a slot that already holds real rows. **Nothing protects a Confirmed value in the live state**: `promote_to_measurement()` swaps any registered key's function with no status check. That is the gap `data_precedence.resolve()` fills as a pure rule; it is not enforced anywhere until a later step wires it.
- **Cadence:** `.github/workflows/continuous_cycle.yml:30` requests one run per hour (`17 * * * *`), best-effort; the 2026-10-27 audit measured real gaps of 3 to 6 h, and the driver uses the measured elapsed time as the step (`cycle_clock.py`).

### 1.3 What exists for replay

`tests/_fakes.py` offers `FakeSupabase` (select / insert / upsert / update / delete with `eq`, `is_`, `order`, `limit`) and `patched_supabase`. The persisted state is `plant_state_current`, one row per `(equipment_id, category)` with the whole `entry` (`scripts/run_continuous_cycle.py:354-361`); it holds the latest state only, not a history. **No measurement table and no tag naming convention exists** (only `equipment_id` / `category` keys). This step defines a tag convention (`UNIT.quantity_unit`) and a file schema; it creates no table.

### 1.4 Can the table be built without touching engine files?

Yes. Every value is readable from a module attribute, an engine input function (called with a get_input that has nothing behind it) or the registry loader. The risks, all handled: it reads private names (`_input_*`, `_GA001_INPUT_KEYS`), so a rename fails loudly (`LookupError`) and the drift tests catch it; the dry-feed input is shown as its fallback because FE-005 is not running (noted in the row); a status the repo does not carry for a constant (PSA) is assigned by the table and says so in `note`.

## 2. Parameter table (item B)

`parameter_table.build_table()` / `to_markdown()` build the table at call time from the owning sources (nothing is copied); `file_line` is found by searching the owning file for the defining statement; `overridable_via` is checked against the models a fresh engine really registers. The `note` column is an addition to the nine requested columns, used for caveats. Two rows with the same `tag` and different `source` are the candidates the precedence rule chooses between (for example the engine's Assumed 950 degC and the registry's Confirmed 950 degC).

### Parameters that can be replaced without editing code

`engine input` = overridable through the engine's normal input mechanism; `registry` = a registry row the engine does not read; `dynamics argument` = a what-if argument, not an engine input.

| tag | value | unit | status | source | range_low | range_high | overridable_via | file_line | note |
|---|---|---|---|---|---|---|---|---|---|
| EU-008.tau_cooling_water_s | 5193.7 | s | Assumed | dynamics.TAU_SPECS['EU008_cooling_water'] | 1800 | 14400 | dynamics argument | python/dynamics.py:157 | EU-008 tower-water relaxation. Used by the what-if layer only; the hourly engine has no time constants. dynamics.run_transient(taus={name: seconds}) overrides it. |
| GA-001.ER | 0.25 | - | Assumed | engine input GA-001-INPUT/equivalence_ratio via _input_equivalence_ratio (python/ga001_gasifier_model.py:460); basis N/A | 0.2125 | 0.2875 | engine input | python/uncertainty.py:85 | Range is uncertainty.py's default +/-15 % band (UNCERTAINTY_FRACTION, 'our own assumed default'), unless a confirmed range is set. |
| GA-001.ER | 0.25 | — | Confirmed | registry GA-003 'Air-to-fuel equivalence ratio (ER)' | Missing | Missing | registry | data/equipment_registry.json:660 | Registry rows without a status key count as Confirmed (equipment_datasheet.py:432). The engine does not read this row. |
| GA-001.T_gasifier_C | 950 | degC | Assumed | engine input GA-001-INPUT/operating_temperature_C via _input_operating_temperature_c (python/ga001_gasifier_model.py:625); basis N/A | Missing | Missing | engine input | python/ga001_gasifier_model.py:230 | The input's docstring says it is read from the registry; the code holds the 950.0 as a module constant. No range exists in the repo. |
| GA-001.T_gasifier_C | 950 | °C | Confirmed | registry GA-001 'Operating temperature (typical)' | Missing | Missing | registry | data/equipment_registry.json:508 | Registry rows without a status key count as Confirmed (equipment_datasheet.py:432). The engine does not read this row. |
| GA-001.carbon_conversion | 0.9 | - | Assumed | engine input GA-001-INPUT/carbon_conversion_efficiency via _input_carbon_conversion_efficiency (python/ga001_gasifier_model.py:505); basis Literature | 0.85 | 0.98 | engine input | python/ga001_gasifier_model.py:217 |  |
| GA-001.ch4_carbon_fraction | 0.05 | - | Assumed | engine input GA-001-INPUT/ch4_carbon_fraction via _input_ch4_carbon_fraction (python/ga001_gasifier_model.py:518); basis Literature | 0.02 | 0.08 | engine input | python/ga001_gasifier_model.py:224 |  |
| GA-001.dry_feed_kg_h | 41.67 | kg/h | Assumed | engine input GA-001-INPUT/dry_feed_rate_kg_h via _input_dry_feed_rate (python/ga001_gasifier_model.py:406); basis N/A | Missing | Missing | engine input | python/gasifier_mass_balance.py:60 | Shown with FE-005 absent (the fallback placeholder). In the running engine this input is Calculated from FE-005's dry-solids balance (37.5 kg/h dry at the defaults), not this placeholder. |
| GA-001.feedstock_daf_CHON | C 0.5; H 0.06; O 0.43; N 0.01 | mass fraction (dry, ash-free) | Assumed | engine input GA-001-INPUT/feedstock_composition via _input_feedstock_composition (python/ga001_gasifier_model.py:571); basis Literature | Missing | Missing | engine input | python/ga001_gasifier_model.py:193 | A dict of the four fractions; no range exists in the repo for the C/H/O/N split (DOK-ING's RFI #2 gives only open C/H floors). |
| GA-001.steam_to_feed_kg_kg | 0.4 | kg/kg | Assumed | engine input GA-001-INPUT/steam_to_feed_ratio via _input_steam_to_feed_ratio (python/ga001_gasifier_model.py:480); basis N/A | 0.34 | 0.46 | engine input | python/uncertainty.py:80 | Range is uncertainty.py's default +/-15 % band, unless a confirmed range is set. |
| GA-001.tail_gas_mode | regasify | mode | Assumed | engine input GA-001-INPUT/tail_gas_mode via _input_tail_gas_mode (python/ga001_gasifier_model.py:1577); basis N/A | Missing | Missing | engine input | python/ga001_gasifier_model.py:1566 | A switch, not a measurement: one of ('regasify', 'heat_only'). |
| GA-001.tau_T_s | 120 | s | Assumed | dynamics.TAU_SPECS['T_gasifier'] | 30 | 600 | dynamics argument | python/dynamics.py:109 | lag from the gasifier temperature setpoint to the temperature GA-001 uses. Used by the what-if layer only; the hourly engine has no time constants. dynamics.run_transient(taus={name: seconds}) overrides it. |
| GA-001.tau_conv_s | 1200 | s | Assumed | dynamics.TAU_SPECS['tau_conv'] | 600 | 2400 | dynamics argument | python/dynamics.py:120 | fuel conversion / bed inventory lag on the dry feed. Used by the what-if layer only; the hourly engine has no time constants. dynamics.run_transient(taus={name: seconds}) overrides it. |
| GA-001.tau_gas_s | 30 | s | Assumed | dynamics.TAU_SPECS['tau_gas'] | 8 | 120 | dynamics argument | python/dynamics.py:134 | gas-phase transport and mixing lag of GA-001's outlet. Used by the what-if layer only; the hourly engine has no time constants. dynamics.run_transient(taus={name: seconds}) overrides it. |
| GA-001.unconverted_C_to_carbon_black | 1 | fraction | Assumed | engine input GA-001-INPUT/unconverted_carbon_to_carbon_black via _input_carbon_black_split (python/ga001_gasifier_model.py:1622); basis N/A | 0.5 | 1 | engine input | python/ga001_gasifier_model.py:1610 |  |
| GA-003.air_flow_design_Nm3_h | 60 | Nm³/h | Confirmed | registry GA-003 'Primary air flow rate (design)' | Missing | Missing | registry | data/equipment_registry.json:648 | Registry rows without a status key count as Confirmed (equipment_datasheet.py:432). The engine does not read this row. CAVEAT, verbatim from the row's own remark: "Derived from ER=0.25 × stoichiometric air demand for the dry feed rate — not DOK-ING-confirmed, treat as an estimate" (the row still counts as Confirmed by the default). |
| GA-003.steam_flow_design_kg_h | 15 | kg/h | Confirmed | registry GA-003 'Steam flow rate (design)' | Missing | Missing | registry | data/equipment_registry.json:654 | Registry rows without a status key count as Confirmed (equipment_datasheet.py:432). The engine does not read this row. |
| GA-004.air_preheat_C | 200 | °C | Confirmed | registry GA-004 'Air preheat temperature' | Missing | Missing | registry | data/equipment_registry.json:712 | Registry rows without a status key count as Confirmed (equipment_datasheet.py:432). The engine does not read this row. |
| GA-004.steam_T_C | 350 | °C | Confirmed | registry GA-004 'Steam temperature (design)' | Missing | Missing | registry | data/equipment_registry.json:718 | Registry rows without a status key count as Confirmed (equipment_datasheet.py:432). The engine does not read this row. |
| HB-009.tau_rec_s | 60 | s | Assumed | dynamics.TAU_SPECS['tau_rec'] | 10 | 140 | dynamics argument | python/dynamics.py:146 | transport delay of the PSA tail gas back to GA-001. Used by the what-if layer only; the hourly engine has no time constants. dynamics.run_transient(taus={name: seconds}) overrides it. |

### Parameters that CANNOT be overridden without a code edit

| tag | value | unit | status | source | range_low | range_high | overridable_via | file_line | note |
|---|---|---|---|---|---|---|---|---|---|
| GA-001.ash_fraction | 0.1 | mass fraction of dry feed | Confirmed | module constant gasifier_mass_balance.ASH_FRACTION (reused by ga001 as ASH_FRACTION) | 0.05 | 0.15 | code only | python/gasifier_mass_balance.py:61 | Status as the code states it ('GA-005: 10% ash content (dry basis)', ga001_gasifier_model.py comment on ASH_FRACTION). Range = DOK-ING's confirmed ash band 5-15 % (design_basis.FEEDSTOCK_COMPOSITION_CONFIRMED_RANGES). NOT an engine input: a feed with another ash content cannot be represented without a code edit. |
| HB-004.wgs_target_calibration | 1 | - | Assumed | uncertainty.ASSUMPTIONS['wgs_target_calibration'] | 0.85 | 1.15 | code only | python/uncertainty.py:100 | Monte-Carlo scaling only (wired_in=True); the engine's WGS stages do not read it. |
| HB-006.psa_K1 | 0.01742 | - | Assumed | module constant psa.K1 | Missing | Missing | code only | python/psa.py:12 | STATUS ASSIGNED BY THIS TABLE (the repo carries no status tag for this constant): psa.py calls itself 'a simplified first-pass industrial design heuristic' and K1 'calibrated to the established 75% design-point recovery'. The HB-006 engine adapter does not pass k1_scale. |
| HB-006.psa_selectivity | CO2 250; CH4 18; CO 6; N2 3.5 | - | Assumed | module constant psa.SELECTIVITY | Missing | Missing | code only | python/psa.py:10 | STATUS ASSIGNED BY THIS TABLE (the repo carries no status tag for this constant): same module docstring as psa.K1. |
| HB-006.psa_target_calibration | 1 | - | Assumed | uncertainty.ASSUMPTIONS['psa_target_calibration'] | 0.85 | 1.15 | code only | python/uncertainty.py:105 | Scales K1 inside the Monte Carlo only (uncertainty.py, wired_in=True); the engine's HB-006 does not read it. |
| HB-006.psa_void_loss | 0.03 | - | Assumed | module constant psa.VOID_LOSS | Missing | Missing | code only | python/psa.py:11 | STATUS ASSIGNED BY THIS TABLE (the repo carries no status tag for this constant): same module docstring as psa.K1. |

## 3. Precedence rule (item C)

`data_precedence.resolve(candidates)` with candidates `(value, status, timestamp, source)` plus optional `unit`, `quality`, `flags`. A pure function; nothing calls it.

1. **Order:** Measured > Confirmed > Calculated > Estimated > Assumed > Missing.
2. **Ties** within a status: the newest timestamp wins (no timestamp = oldest). Equal newest timestamps are reported as `tie`, the first listed wins.
3. **A Confirmed value is never replaced by Calculated / Estimated / Assumed**, whatever the timestamps (status ranks before time).
4. **A Measured value takes part only if `quality == good` and it carries no blocking flag** (`unit_mismatch`, `non_monotonic_time`, `duplicate`, `bad_timestamp`, `bad_value`, `bad_quality_label`, `physically_impossible`). One that fails is not dropped: it is `rejected` in the audit trail, and when a Confirmed value stays because of it, `blocked_overrides` names it. A non-blocking flag (for example `outside_assumed_range`) does not stop a measurement. **Decision made here, not in the brief:** a failing Measured candidate is ineligible against every status, not only against Confirmed.
5. **A Measured winner over a Confirmed candidate is reported** as `override`, with the measured and the confirmed values, never silently.
6. **A Missing candidate never wins**; with only Missing candidates the result is status Missing, value None.
7. The result carries the winner, the `replaced` candidates and the full audit trail (outcome and reason per candidate).

`dry_run(table, measurements)` lists, per measured parameter tag, the value the model uses today (the row the engine reads, not a registry row it ignores), the resolved value, the change (absolute and relative), the override, the number of rejected readings, and the tags that are not parameters. Of several good readings the newest wins: that is the rule, not an estimator (no averaging, no fit). A reading in another unit is rejected, never converted.

## 4. Replay ingestion (item D)

Schema, tag convention and flags: `docs/measurement_replay_schema.md`. A long-format CSV or JSON `timestamp, tag, value, unit, quality, source`; the validator flags unit mismatch, non-monotonic time, duplicates (identical or conflicting), unknown tags, unparseable timestamps and values, bad quality labels, physically impossible values and values outside a parameter's table range, and **drops nothing** (rows in = rows out is tested). Only `InMemorySource` and `FileSource` exist.

**Adapter interface for a live feed (not implemented):**

```python
class MeasurementSource:
    def read(self, since=None):   # raw readings strictly after `since`, in arrival order; must not write
        ...
```

A later task implements it for a Supabase measurement table or a SCADA export; the rest (validation, precedence, residual report) takes the result unchanged.

## 5. Residual report (item E)

`python scripts/run_residual_report.py` (default: a SYNTHETIC demonstration, about a minute; `--replay FILE` for a real file) writes `outputs/data_layer/residual_report.md` and `.csv`. Residual = measured minus model; the model side is the engine's quasi-steady final snapshot, one value for the whole window. Flagged readings are excluded and counted (`n_used`, `n_flagged`). The synthetic run uses the model's own snapshot plus known offsets (HB-012 H2 +0.5 kg/h, SA-001 H2 -2.0 vol%, dry flow +4.0 Nm3/h, temperature -15 degC) and recovers each offset exactly (to 1e-9, tested): **it proves the plumbing, not the physics.**

Verbatim from that run:

```
**Data: SYNTHETIC: model snapshot + a known offset. Proves the plumbing, not the physics; no plant data exists.**

Residual = measured - model. The model is the engine's quasi-steady final snapshot: one value per tag for the whole window. Nothing is fitted or calibrated.

## 1. Replay validation

No issue found.

Readings in: 48; readings out: 48 (validation drops nothing).

## 2. Model vs measured

| tag | model entry | unit | n used / flagged | window | measured mean | model | residual abs (meas - model) | residual rel | max |residual| | model status | measured status | note |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| GA-001.T_gasifier_C | GA-001-INPUT/operating_temperature_C | degC | 12 / 0 | 2026-10-30T00:00:00+00:00 .. 2026-10-30T11:00:00+00:00 | 935 | 950 | -15 | -0.0157895 | 15 | Assumed | Measured (good 12, suspect 0, bad 0) |  |
| GA-001.dry_flow_nm3_h | GA-001/Outputs.dry_flow_nm3_h | Nm3/h | 12 / 0 | 2026-10-30T00:00:00+00:00 .. 2026-10-30T11:00:00+00:00 | 106.753 | 102.753 | 4 | 0.0389284 | 4 | Calculated | Measured (good 12, suspect 0, bad 0) |  |
| HB-012.h2_kg_h | HB-012/Compressor.h2_kg_h | kg/h | 12 / 0 | 2026-10-30T00:00:00+00:00 .. 2026-10-30T11:00:00+00:00 | 3.75102 | 3.25102 | 0.5 | 0.153798 | 0.5 | Calculated | Measured (good 12, suspect 0, bad 0) |  |
| SA-001.H2_vol_pct | SA-001/Reading | vol% | 12 / 0 | 2026-10-30T00:00:00+00:00 .. 2026-10-30T11:00:00+00:00 | 25.4522 | 27.4522 | -2 | -0.072854 | 2 | Calculated | Measured (good 12, suspect 0, bad 0) |  |
```

### Identifiability: which Assumed parameters a measured tag could constrain

A static map written from the model's structure (engineering judgement, validated only for naming real tags). "Constrained by" says the tags carry information about the parameter; "confounded with" says the tags alone do not separate it from the listed parameters. This is also the list of what data would switch each Assumed parameter to Measured.

| parameter | status now | overridable via | constrained by | how | confounded with | also needed | direct / indirect |
|---|---|---|---|---|---|---|---|
| GA-001.carbon_conversion | Assumed | engine input | GA-008.carbon_black_kg_h, GA-001.dry_flow_nm3_h, GA-001.CO_mol_pct_dry, GA-001.CO2_mol_pct_dry, GA-001.CH4_mol_pct_dry, FE-008.feed_rate_kg_h | carbon balance: carbon in the product gas plus the carbon black against the carbon fed | GA-001.ch4_carbon_fraction | a feed ultimate analysis (lab) and the split of unconverted carbon (carbon black vs bed drain vs fly ash) | indirect |
| GA-001.ch4_carbon_fraction | Assumed | engine input | GA-001.CH4_mol_pct_dry, SA-004.CH4_vol_pct, GA-001.dry_flow_nm3_h | CH4 carbon over converted carbon | GA-001.carbon_conversion | the conversion (above) to turn CH4 volume into a fraction | indirect |
| GA-001.ER | Assumed | engine input | GA-003.air_flow_Nm3_h, FE-008.feed_rate_kg_h, GA-001.N2_mol_pct_dry, SA-005.N2_vol_pct | directly: measured air against the stoichiometric air of the feed; indirectly: the N2 balance (the gasifying-agent study found the registry's 10 % N2 implies ER about 0.04) | GA-001.carbon_conversion | the gasifying agent (air vs oxygen vs carrier; docs/gasifying_agent_study.md) and the feed ultimate analysis | direct |
| GA-001.steam_to_feed_kg_kg | Assumed | engine input | GA-003.steam_flow_kg_h, FE-008.feed_rate_kg_h | directly: measured steam mass flow over the dry feed rate | - | the dry (not as-received) feed rate: FE-005's moisture | direct |
| GA-001.T_gasifier_C | Assumed | engine input | GA-001.T_gasifier_C | directly: a bed / outlet temperature reading | - | which thermocouple position the 950 degC refers to | direct |
| GA-001.dry_feed_kg_h | Assumed | engine input | FE-008.feed_rate_kg_h | directly: ram-feeder / airlock rate | - | the moisture of the feed to convert wet to dry | direct |
| GA-001.feedstock_daf_CHON | Assumed | engine input | no tag | not a time series: a laboratory ultimate analysis of the real feed | - | sampling plan and lab results (no tag exists) | no tag |
| GA-001.ash_fraction | Confirmed | code only | GA-008.carbon_black_kg_h | ash discharge mass over the dry feed (GA-005 rate); no ash-flow tag is defined in this layer | - | an ash mass-flow tag and a lab ash analysis | indirect |
| GA-001.unconverted_C_to_carbon_black | Assumed | engine input | GA-008.carbon_black_kg_h | carbon black mass over the unconverted carbon | GA-001.carbon_conversion | masses of the other unconverted-carbon exits (bed drain, cyclone catch, fly ash): no tag exists, Missing | indirect |
| GA-001.tail_gas_mode | Assumed | engine input | no tag | not identifiable from a measurement: it states where the PSA tail gas goes in the plant | - | DOK-ING's statement of the real tail-gas routing | no tag |
| HB-006.psa_K1 | Assumed | code only | HB-012.h2_kg_h, HB-009.product_flow_nm3_h, HB-009.tail_flow_nm3_h, HB-006.psa_recovery | H2 recovery from the product and tail flows with the PSA feed composition | HB-006.psa_void_loss | PSA feed composition and flow (no PSA-inlet tag is defined in this layer) | indirect |
| HB-006.psa_void_loss | Assumed | code only | HB-006.psa_recovery | only with K1 jointly (recovery = 1 - K1*index/(PR-1) - void loss) | HB-006.psa_K1 | recovery at two or more pressure ratios | indirect |
| HB-006.psa_target_calibration | Assumed | code only | HB-006.psa_recovery | a scale on K1 (Monte-Carlo only): the same data as K1 | HB-006.psa_K1 | see K1 | indirect |
| HB-004.wgs_target_calibration | Assumed | code only | no tag | post-WGS composition: no sensor tag for it is defined in this layer | - | a post-WGS CO / H2 analyser tag | no tag |
| GA-001.tau_conv_s | Assumed | dynamics argument | GA-001.dry_flow_nm3_h, GA-001.H2_mol_pct_dry | transient step response of the gas to a feed-rate step | GA-001.tau_gas_s | time-resolved data at sub-minute spacing around a deliberate feed step (the hourly runtime and a 1-hour log cannot show a 20-minute lag) | indirect |
| GA-001.tau_gas_s | Assumed | dynamics argument | GA-001.dry_flow_nm3_h, GA-001.H2_mol_pct_dry | outlet-gas response to an ER or feed step | GA-001.tau_conv_s | seconds-resolution gas data | indirect |
| GA-001.tau_T_s | Assumed | dynamics argument | GA-001.T_gasifier_C | temperature response to a setpoint change | - | seconds-resolution temperature data and the heating actuator | indirect |
| HB-009.tau_rec_s | Assumed | dynamics argument | HB-009.tail_flow_nm3_h | tail-gas flow response at the recycle point | - | tail-gas flow and buffer-tank data (HB-009) | indirect |
| EU-008.tau_cooling_water_s | Assumed | dynamics argument | no tag | cooling-water temperature step response: no tag is defined in this layer | - | a cooling-water temperature tag | no tag |

## 6. What is deliberately not done

- **No wiring**: the engine, the runtime, the app, the uncertainty module and the dynamics layer do not import or call any new module; the hourly runtime and its shrink guard are untouched.
- **No calibration or fitting**: no parameter value was changed to match anything, and the residual report fits nothing.
- **No live feed, no PLC / SCADA code, no database table.**
- No change to any default, Confirmed value, registry row or existing test.

## 7. Needs your decision

1. **Does the next step wire the precedence resolver into the engine's input mechanism?** The natural seam is `overrides` / `promote_to_measurement` (one function per key), which today swaps a function with no status check. Effects to weigh: it adds a per-cycle read of the measurement store to every hourly run (a new failure mode next to the existing store-read guard); a Measured input changes every downstream number, so the snapshot-determinism tests and the persisted-key count (shrink guard: `SHRINK_MIN_FRACTION = 0.90` of the stored keys) must be re-baselined; and the resolver would have to run with the elapsed-time step `cycle_clock.py` uses, not an assumed hour.
2. **The tag naming convention** (`UNIT.quantity_unit`, for example `GA-001.T_gasifier_C`). Alternatives: PLC tag names verbatim (needs DOK-ING's list), or `equipment_id/category.field` mirroring the snapshot. Changing it later means renaming the catalog, not the logic.
3. **The live-feed design for step 2: Supabase table or SCADA export?** "Real time" has to be defined against the cadence: the workflow requests hourly but the audit measured 3 to 6 h gaps, so the model sees at most one new state per run. A Supabase table written by the plant side fits `read(since)` and the hourly runtime (each run reads what arrived since the last); a SCADA export file fits batch calibration and the replay path already built. Neither gives sub-minute data, so the time constants (`tau_conv`, `tau_gas`) stay unidentifiable from the hourly path; they need a separate high-rate capture around a deliberate step.
4. **Which Assumed parameters are identifiable first when data arrives.** The direct ones need only one tag each: `GA-001.T_gasifier_C` (a thermocouple), `GA-001.dry_feed_kg_h` (the feeder rate), `GA-001.steam_to_feed_kg_kg` (steam mass flow over the dry feed). The ER needs an air-flow tag (or a closed gasifying-agent question, `docs/gasifying_agent_study.md`). Carbon conversion, CH4 fraction and the carbon-black split are confounded in the gas data and need the carbon black mass and a feed analysis. The PSA constants need the PSA inlet composition and flow, for which no tag is defined yet.

**Not verifiable here:** the Python 3.11 / 3.12 CI.

