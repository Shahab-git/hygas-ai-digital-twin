# Calibration core, step 2 — tracking drifting Assumed inputs with a Kalman filter

**Status: a twin experiment on SYNTHETIC data. Not validation against DOK-ING data (none exists). It calibrates nothing in the model, and nothing (engine, runtime, app, uncertainty module) imports it.**

Code: `python/state_estimation.py` · tests: `tests/test_state_estimation.py` (11 cases) · builds on `python/calibration.py` (CAL-1, `docs/calibration_core_step1.md`).

## 1. What it does
CAL-1 answered "which Assumed inputs can the gas-train data pin down, once". CAL-2 asks the next question: if those inputs **drift** (feed quality, bed fouling, air-meter offset), can a filter follow them from a stream of measurements, so the twin corrects itself over time instead of staying at its nominal values?

* **State:** the four CAL-1 parameters (ER, steam-to-feed, carbon conversion, CH4 carbon fraction).
* **Process model:** random walk, standard deviation per step 2 % of each parameter's prior range (`DRIFT_FRACTION`, Assumed tuning number).
* **Measurement model:** the unchanged engine (`calibration.forward`) at the predicted state; sensitivity from CAL-1's finite-difference Jacobian, frozen at the nominal point (`relinearise_every` re-computes it at the estimate, 5 engine runs each time). Joseph-form covariance update; estimate clipped to the prior bounds.
* **Noise:** the CAL-1 sigmas (Assumed). Initial standard deviation 50 % of the prior range (Assumed).
* `drift_experiment(path)` synthesises noisy measurements from a truth path, runs the filter and a **static twin** (nominal parameters, never updated) side by side.

## 2. Results (8 steps, noise seed 1, mean over the last 3 steps)

| Truth path | Observable error, static twin | Observable error, filter | Main parameter error: static → filter | Mean NIS (expected 6) |
|---|---|---|---|---|
| No drift (control) | 0.0 σ | 0.30 σ | none: 0 → 0.002–0.007 (all four) | 4.0 |
| ER ramp 0.25 → 0.28 | 3.13 σ | 0.57 σ | ER 0.026 → 0.005 | 6.8 |
| Carbon conversion step 0.90 → 0.86 (after step 4) | 1.54 σ | 0.51 σ | conversion 0.040 → 0.022 | 7.1 |

Observable errors are RMS over the six observables in units of their assumed noise. NIS is the normalised innovation squared; its mean should be near the number of observables (6) if the filter's model of the noise and drift is consistent. A constant ER offset of 0.27 (12-step run, not guarded by a test) gave ER error 0.0007 and observable error 0.15 σ against 2.4 σ for the static twin.

What this says: the filter follows a slow ER ramp and a conversion step, cuts the observable misfit from several noise sigmas to about half a sigma, and on a no-drift control it does not invent drift. The step itself shows up as an innovation spike (a test checks it), so the same quantity is a drift detector.

What it does NOT say: conversion is only weakly identifiable (CAL-1), and four steps after the step the filter has recovered about 45 % of the parameter error, not all of it. Observables fit much better than parameters do: the data constrain combinations, and the poorly constrained parameters (steam-to-feed in particular, 0.007 of its range wandering even with no drift) move inside their prior.

## 3. Limits (stated)
1. Synthetic: the filter tracks the engine's own output, so the model is assumed perfect. A real plant adds model error that no step here measures.
2. Random-walk size, initial covariance and noise sigmas are Assumed. The NIS band in the test is a heuristic (1.5 to 12), not a chi-square test.
3. Quasi-steady engine: one measurement per step is a steady value. This tracks drift, not transients (`python/dynamics.py` is a separate what-if layer).
4. The Jacobian is frozen at the nominal point unless `relinearise_every` is set; large excursions are linearised badly (the NIS would rise).
5. Clipping to the bounds is a heuristic and biases an estimate pinned at a bound (a test checks it stays inside).
6. Four parameters only; nothing here changes the model, the live state or the app.

## 4. What is not done
Wiring into the hourly runtime; using real measurements (needs DOK-ING data, the flow meter first, see CAL-1); an unscented or batch-window variant; handling sensor faults or missing observables (a missing observable is refused, not guessed).
