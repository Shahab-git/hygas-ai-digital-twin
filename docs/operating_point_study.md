# Operating-point study (Phase 1, task P1-01)

Date: 2026-11-09. Basis: `main` at `90c99a9`. Reproduce: `python scripts/run_operating_point_study.py` (about 15 minutes; `--quick` about 3 minutes). Read-only and offline: the engine runs in-process against the in-memory fake store, with 0 database calls; it writes `outputs/operating_point/operating_point_study.md` and `.csv` (git-ignored). **Nothing was tuned, no default changed, and no engine file was touched.** This is a scenario study, not a calibration.

## 1. Question

Which combinations of the levers the engine already has bring the hydrogen product near DOK-ING's "about 50 kg/day" (RFI #6, plastic waste; gross or net, availability and start-up not stated), and what does each combination do to the other numbers?

## 2. Levers (all Assumed; none is a DOK-ING value)

| lever | low | default point | high | source |
|---|---|---|---|---|
| equivalence ratio (ER) | 0.2125 | 0.25 | 0.2875 | `uncertainty.ASSUMPTIONS`, point +/-15 % |
| steam-to-feed ratio | 0.34 | 0.40 | 0.46 | `uncertainty.ASSUMPTIONS`, point +/-15 % |
| carbon conversion | 0.85 | 0.90 | 0.98 | `ga001_gasifier_model.CARBON_CONVERSION_EFFICIENCY_RANGE` (Basu 2010) |
| PSA recovery | n/a | model, about 78 % | fixed 75 % | HB-007 "H2 recovery rate (design)", Unverified (registry) |
| tail-gas mode | n/a | `regasify` | `heat_only` | `GA-001-INPUT tail_gas_mode` |

The grid is 2 modes x 3 ER x 3 steam x 3 conversion x 2 PSA = 108 cases, all inside the documented ranges, plus two labelled out-of-range cases (ER 0.35 and 0.40, `heat_only`) for context. Each case is the converged state (30 cycles). "Near 50" means within +/-10 % of 50, a reporting convention only.

## 3. Result (measured, 30 cycles, 2026-11-09)

- The default point gives **78.0 kg/day** (`regasify`), as in `docs/tail_gas_heat.md`.
- With the tail gas re-gasified (`regasify`), no in-range case is near 50: the in-range range is **63.2 to 96.4 kg/day**.
- With `heat_only`, the in-range range is **45.7 to 66.6 kg/day**, and **24 of the 54 in-range `heat_only` cases are near 50**. The fewest levers moved from the default is 2 (the tail-gas mode plus one of: carbon conversion 0.85, ER 0.2875, or PSA recovery fixed at 75 %).
- Steam-to-feed ratio, inside its +/-15 % range, moves hydrogen by at most 0.13 kg/day. ER and carbon conversion move it most, after the tail-gas mode.
- The out-of-range cases (`heat_only`, ER 0.35 and 0.40, other levers at default) give 45.1 and 39.7 kg/day.

## 4. What reaching 50 costs elsewhere

Every near-50 case moves the other outputs further from the registry, not closer. In the near-50 cases the PSA feed hydrogen is 31 to 39 vol% (the registry expects 55) and the dry syngas N2 is 36 to 45 vol% (the registry expects about 10). The net heat (at the 17.5 MJ/kg midpoint) is a deficit of 4 to 20 kW in every near-50 case, so the heat balance still has no source for the steam raising and drying duty. Matching one number worsens others, which is why the study does not choose a default.

## 5. What this does not show

- It does not show that the twin is correct at ~50 kg/day. The 50 is a DOK-ING statement for plastic waste whose basis is unknown; the twin runs MSW at 100 % availability with no leaks, purges or losses.
- It does not choose or recommend an operating point. Changing a default is a separate owner decision (draft task P1-06; G5-07 row 9).
- It varies only existing levers. The gasifying agent (G5-07 row 5, the root cause of rows 1 to 4) is not varied here; `docs/gasifying_agent_study.md` covers the agent scenarios, and DOK-ING's answer is pending.

## 6. Checks

`tests/test_operating_point_study.py` pins the lever ranges, the grid sizes, the lever count, the +/-10 % convention, the default 78.0 kg/day, the 54.3 kg/day case (`heat_only` with PSA fixed at 75 %), that the study's overrides do not leak into a later default run, and that no database call is made. The 15-minute grid is not run by the tests.
