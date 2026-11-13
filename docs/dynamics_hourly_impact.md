# Would wiring the dynamics layer into the hourly runtime change anything? (DYN-1)

**Status: a measurement with ASSUMED time constants, on the existing what-if layer. Not validated against plant data. No runtime, engine, app or dynamics code changed; the decision it supports is "do not wire it in at the hourly cadence".**

Code: `scripts/run_hourly_dynamics_impact.py` (read-only, offline, about 1 min) · tests: `tests/test_hourly_dynamics_impact.py` (4 cases) · layer measured: `python/dynamics.py`, `docs/dynamics_v0.md`.

## 1. Question
The hourly runtime (`scripts/run_continuous_cycle.py`) is quasi-steady: one engine cycle per publish, about one hour apart. `python/dynamics.py` adds first-order lags (gasifier temperature 120 s, fuel conversion 1200 s, gas transport 30 s, tail-gas recycle delay 60 s). Would turning them on at the runtime's own step change what is published?

## 2. Method
`dynamics.run_transient` at dt = 3600 s for 8 h, a step applied at hour 1, run twice: lags OFF (the four time constants set to 0) and lags ON (Assumed defaults). The table is the percentage difference of the published value, lags ON against OFF, at each hourly row. Both runs share the engine's own one-cycle couplings and the EU-008 damping (50 % per hour at dt = 1 h by design), so the comparison isolates the four lags.

## 3. Result
Analytic residual of each lag after one hourly step, exp(−3600/τ): τ_conv 1200 s → **4.98 %** unrealised; τ_gas 30 s, T_gasifier 120 s, τ_rec 60 s → effectively 0.

| Step at hour 1 | H2 production | GA-001 dry flow | H2 % dry |
|---|---|---|---|
| Feed −20 % | +1.28 % in the first cycle after the step, +0.06 % the next, then 0 | same | 0.00 % |
| ER 0.25 → 0.28 | 0.00 % at every hour | 0.00 % | 0.00 % |
| Gasifier T 950 → 900 °C | 0.00 % | 0.00 % | 0.00 % |

Only the conversion lag survives an hourly step (and only for a feed change), because ER acts on the gas phase and temperature acts only through the shift equilibrium (`docs/dynamics_v0.md` section 2). The feed and ER rows are guarded by tests; the T row is printed by the script and not guarded by a test.

## 4. Consequence and recommendation
Wiring the lags into the hourly runtime would change a published value by at most about 1.3 % for one cycle after a feed step and not at all after an ER or temperature step. The price would be persisting the lag state between runs in the plant-state store, changing the published numbers and touching the most guarded files of the repo. **Not worth it at this cadence.** It would matter at a sub-hour cadence (a cycle every 1 to 5 minutes) or for a live transient display; that is a different decision, and the time constants (all Assumed; the registry's 20-minute residence time is the only anchor) would first need DOK-ING's real step responses.

## 5. Limits
1. The result is only as good as the Assumed time constants; a longer τ_conv (the tab allows up to 2400 s) leaves a larger residual (exp(−1.5) = 22 %), so the 1.3 % is for the default.
2. One feed step size (−20 %) and one step each for ER and T; the T row is not test-guarded.
3. The dynamics layer itself is a what-if with algebraic downstream blocks (GC, HB, EU, SA have no lag), so this measures GA-001's lags only.
4. It does not test any real wiring; it argues that none is needed at this cadence.
