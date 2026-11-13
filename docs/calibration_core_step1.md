# Calibration core, step 1 (task CAL-1): fitting Assumed GA-001 inputs to gas-train measurements, on synthetic data

Written 2026-11-13 on `origin/main` e20c6ce. Files: `python/calibration.py`, `tests/test_calibration.py` (12 cases, about 1.5 min). Chosen by the owner on 2026-11-13 as the first improvement of the twin that does not wait for DOK-ING.

**Status in one paragraph.** A TWIN EXPERIMENT tool proven on SYNTHETIC data only. Every "measurement" here is the unchanged engine's own output at a known parameter set plus seeded Gaussian noise, so the loop is proven (the truth is recovered, the structure of what can and cannot be identified is exposed). It is **not** validation against DOK-ING data (none exists), it calibrates nothing in the model, and nothing in the engine, the runtime, the app, the uncertainty module or any script imports it. It is the first small part of the question the data-replacement layer left open (`docs/data_replacement_layer.md` section 7, item 4: which Assumed parameters are identifiable first).

## 1. What it does

- `forward(params)`: the engine's GA-001 gas outputs (H2, CO, CO2, CH4, N2 in mol % dry, and the dry gas flow) for a dict of Assumed inputs, through the engine's own override mechanism, in-process, against the in-memory fake store (offline). Default `heat_only` mode and 2 cycles: GA-001's gas is identical to its 20-cycle value (measured; a test guards it).
- `jacobian_report()`: sensitivities of the six observables to four parameters at the nominal point, scaled by the observation noise: singular values, condition number, the parameter correlation implied by the information matrix, and a per-parameter standard error with a verdict.
- `fit(measured)`: bounded least squares (`scipy.optimize.least_squares`, trust-region reflective, bounds = the repo's own ranges from `python/parameter_table.py`).
- `twin_experiment(truth, noise_seed, noise_scale)`: synthesise measurements at a known truth, fit from the nominal start, report the recovery.
- `leave_one_observable_out()`: what each instrument is worth (no new engine runs).

Parameters (all Assumed engine inputs): ER 0.25 (0.2125-0.2875), steam-to-feed 0.40 (0.34-0.46), carbon conversion 0.90 (0.85-0.98), CH4 carbon fraction 0.05 (0.02-0.08). Observation noise (**Assumed sensor accuracies, not DOK-ING's**): gas analysers 0.5 mol % absolute (CH4 0.2), dry flow 1.6 Nm3/h (2 % of about 80).

## 2. Results (nominal point, six observables, `heat_only`)

| | ER | steam-to-feed | carbon conversion | CH4 carbon fraction |
|---|---|---|---|---|
| standard error (1 sigma) | 0.0057 | 0.0292 | 0.0203 | 0.0047 |
| as a fraction of the prior range | 0.076 | 0.243 | 0.156 | 0.079 |
| verdict (threshold 0.25, a stated heuristic) | identifiable | identifiable (borderline) | identifiable | identifiable |

Singular values of the noise-scaled Jacobian 360 / 191 / 62 / 31, condition number 11.5, rank 4. The parameters are not independent: the correlation of ER with carbon conversion is **+0.73** (more air and more conversion shift the gas the same way), steam with conversion +0.53, ER with steam +0.41.

**What each instrument is worth** (identifiability, as a fraction of the prior range, when ONLY that observable is dropped; same Jacobian):

| dropped | ER | steam | conversion | CH4 fraction | condition number |
|---|---|---|---|---|---|
| none | 0.076 | 0.243 | 0.156 | 0.079 | 11.5 |
| H2 | 0.081 | 0.265 | 0.157 | 0.086 | 10.0 |
| CO | 0.077 | 0.330 | 0.163 | 0.079 | 13.2 |
| CO2 | 0.076 | 0.273 | 0.156 | 0.080 | 12.2 |
| CH4 | 0.080 | 0.252 | 0.190 | **0.194** | 12.3 |
| N2 | 0.089 | 0.265 | 0.163 | 0.083 | 10.1 |
| **dry flow** | **1.45** | **3.23** | **3.09** | 0.089 | **205** |

**Reading.** The clean-gas flow meter (registry SA-010) is by far the most valuable single instrument for this model: without it the composition fractions alone leave ER, steam-to-feed and carbon conversion practically unidentifiable (standard errors above the whole prior range), because a fraction carries no information about the absolute carbon and air throughput. The CH4 analyser is what pins the CH4 carbon fraction. Any single composition analyser can be lost with little harm. This is a statement about THIS model at THIS point with the ASSUMED noise levels, and it is useful for what to ask DOK-ING to log: composition AND the flow, time-aligned.

**Twin experiments** (truth ER 0.28, steam 0.43, conversion 0.92, CH4 fraction 0.06; start at the nominal): without noise the truth is recovered to better than 1e-4 in all four (chi2 below 1e-8, converged, no bound active). With seeded noise (seed 1, noise at the assumed sigmas) the estimates are ER 0.2846 (+0.74 sigma), steam 0.4210 (-0.29), conversion 0.9191 (-0.04), CH4 fraction 0.0530 (-1.45); chi2 1.04 on 2 degrees of freedom, 10 model evaluations of the Jacobian-assisted fit.

## 3. Limits (read these before quoting a number)

1. **The model is fitted to itself.** This is the most optimistic possible case: no model error, no correlated noise, no drift. With real data the model error (GA-001 has no energy balance; the gas composition disagrees with the registry's expected table) will dominate the noise, and the standard errors here are lower bounds, not forecasts.
2. **The noise levels are Assumed.** The verdicts depend on them linearly.
3. **Quasi-steady.** One value per observable per run. A real time series would have to be reduced to a steady point first.
4. **Four parameters only.** The ash fraction, the PSA constants and the target calibrations are code-only constants that cannot be overridden without an edit (`docs/data_replacement_layer.md` section 1.1); they are not fitted here. The temperature, the feed composition, the gasifying agent and `tail_gas_mode` have no useful gas-train signature (identifiability map, section 5 there).
5. **A fit does not change the model.** Nothing is promoted to a Measured or Calibrated status; no precedence rule is enforced.
6. The verdict threshold (25 % of the prior range) is a heuristic, not a statistical test.

## 4. What this is not, and what comes next (not done here)

Not wired to the replay validator (`python/measurement_replay.py`): a later step takes a validated replay window, reduces it to a steady point per observable and calls `fit`. Not wired to the precedence rule. Not the PSA constants (`HB-012` and `HB-009` tags). None of that needs DOK-ING's reply to build; all of it needs real data to mean anything.
