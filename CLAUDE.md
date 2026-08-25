# HYGAS-AI Digital Twin — Project Context for Claude Code

## What this project is

A digital twin for a municipal-solid-waste (MSW) gasification plant that
produces hydrogen via water-gas-shift conversion, PSA purification, and
CHP utilisation. NACHIP pilot project (DOK-ING d.o.o., Zagreb, Croatia).

Two parallel implementations are planned and should both be maintained:
- **MATLAB/Simulink** (`/matlab`) — the rigorous, engineering-grade physics
  model. This is intended as the validated source of truth for every number
  below, once built.
- **Python** (`/python`) — verified cross-check implementations of the same
  physics, used as the backend for a live Streamlit dashboard, since
  Streamlit Cloud can't run Simulink.

`/matlab` doesn't exist yet in this repo. `/python` now exists, but only
covers the WGS/PSA/CHP/dispatch subset below — the gasifier, gas cleaning,
and interstage HX are not yet implemented in either language. When adding
a new physics module, implement it in both languages and cross-check that
they agree numerically before considering it done.

## Repository structure (verified against actual code)

- `app.py` — Streamlit dashboard entry point. Interactive WGS kinetics
  and PSA recovery (recompute on every slider move), on-demand CHP
  dispatch GA (button-triggered, since 150 generations takes a few
  seconds), and a static validated-milestones reference table.
- `python/kinetics.py` — `hts_conversion()` / `lts_conversion()`. Finite
  volume integration of Arrhenius/Van't Hoff WGS kinetics (Moe 1962
  equilibrium correlation) for the Fe-Cr (HTS) and Cu/ZnO/Al2O3 (LTS)
  catalysts — separate `Ea`/`k0` per stage, so the LTS-reusing-HTS-kinetics
  bug noted below cannot recur structurally.
- `python/psa.py` — `psa_recovery()`. Selectivity + pressure-ratio
  correlation (Ruthven/Farooq/Knaebel), explicitly documented in-file as
  a first-pass design heuristic, not a full multi-bed cycle simulation.
- `python/chp.py` — `chp_efficiency()`. Empirical part-load curves for
  SOFC, Gas Engine, Microturbine, and PEM Fuel Cell, each reducing to its
  rated efficiency at load_factor=1.0.
- `python/dispatch_ga.py` — `run_dispatch_ga()`. Genetic algorithm
  (tournament selection, blend crossover, Gaussian mutation) dispatching
  the 4 CHP units under separate syngas/H2 fuel budgets.
- `requirements.txt` — `streamlit`, `numpy`.

## Validated milestones

The WGS/PSA/CHP rows are now confirmed live in this repo's Python code
(each module's `__main__` block reproduces its target exactly; `app.py`
runs end-to-end under `streamlit run`, checked 2026-08-25). The gasifier,
gas cleaning, and interstage HX rows are prior MATLAB/Simulink results —
targets for future implementation, not yet built here in either language.

| Subsystem | Result | Target | Live in this repo? |
|---|---|---|---|
| Gasifier mass balance | 46.88 kg/h | 46.9 kg/h | No — not yet built |
| Gas cleaning | 45.94 kg/h | ~45.9 kg/h | No — not yet built |
| WGS HTS (Arrhenius/Van't Hoff kinetics, Fe-Cr catalyst) | 75.0% conversion | 75.0% | Yes — `python/kinetics.py` |
| Interstage HX | 4.134 kW | ~4.1 kW | No — not yet built |
| WGS LTS (Cu/ZnO/Al2O3 catalyst) | 40.0% relative conversion | 40.0% | Yes — `python/kinetics.py` |
| WGS overall | 85.0% | 85.0% | Yes — `python/kinetics.py` |
| PSA recovery (selectivity + pressure-ratio correlation) | 75.0% | 75.0% | Yes — `python/psa.py` |
| CHP part-load efficiency (4 technologies) | verified at rated + part-load | — | Yes — `python/chp.py` |
| CHP dispatch GA | correctly deprioritises the least-efficient unit (Microturbine) under fuel constraints | fuel-constrained optimum | Yes — `python/dispatch_ga.py` |

Two real bugs were found and fixed in prior development on this project
(worth guarding against when rebuilding):
1. Gasifier mass balance originally double-counted gasification air.
2. LTS reaction reused HTS's catalyst kinetics, giving ~0% conversion —
   correctly revealed that LTS needs its own catalyst-specific kinetics
   (Cu/ZnO/Al2O3, not Fe-Cr, Ea=75 kJ/mol vs Ea=111 kJ/mol).

Six design-basis parameters remain unconfirmed by DOK-ING: steam-to-feed
ratio (0.4), air equivalence ratio (0.25), feed sulfur/H2S (200 ppm),
feed chlorine/HCl (150 ppm) — treat these as assumptions, not established
facts, in any new work.

## The 19 innovations and what equipment each belongs to

Organise new modules around these, grouped by category. Each maps to a
specific plant subsystem — build accordingly rather than as a monolith.
A starting equipment registry (AI-001 through AI-015) exists as
spreadsheets outside this repo and should be brought in as the data
layer is built.

**Engineering & Product**
- Novelty audit → applies across the full equipment set
- Circularity scoring → ash & carbon black recovery
- Multi-module orchestration → multi-plant coordinator
- RFNBO compliance → compliance tracker
- Predictive maintenance → bed pressure sensor

**Mathematical**
- Reaction kinetics → shift reactors (design targets above)
- MPC + RL → central optimiser (not yet built — next major piece)
- Monte Carlo uncertainty → shift reactors (propagate the 6 unconfirmed
  assumptions into confidence intervals, not point values)

**Rare methods**
- Physics-informed neural nets → gasifier
- Sim-to-real transfer → central optimiser
- Federated learning → cloud data hub
- Performance guarantee → hydrogen purifier
- Topological data analysis → plant control screen

**AI agents** (none built yet — genuinely the least-started category)
- Operator copilot → plant control screen (most demoable, no real plant
  data needed to build a first version)
- Root-cause diagnosis → bed pressure sensor
- Multi-agent negotiation → multi-plant coordinator
- Confirmation-loop agent → shift reactors (automates re-confirming the
  6 unconfirmed assumptions with DOK-ING)
- Regulatory drafting agent → compliance tracker
- Vendor-sourcing agent → full equipment set (also very demoable — every
  item in the registry needs a real vendor quote)

## Coding conventions for this project

- Prefer complete, ready-to-run code over structural advice or pseudocode.
- Every new physics module needs a numeric check against its established
  design target before being considered done — state the check explicitly
  in a comment, the way the existing MATLAB blocks do.
- Be explicit about simplifications. If something is a first-pass
  correlation rather than a rigorous model (like the PSA recovery
  correlation), say so in the code comments — don't present a
  simplification as more rigorous than it is.
- MATLAB Simulink errors are usually diagnosable from the exact error
  message text (line/column references) without needing to see the block's
  code directly.

## Not yet built (the actual current state)

`python/kinetics.py`, `python/psa.py`, `python/chp.py`,
`python/dispatch_ga.py`, and `app.py` exist and are verified (see above).
Still missing:

1. `/matlab` — the physics model itself; nothing in this repo has been
   cross-checked against Simulink yet, only against the documented targets.
2. Gasifier, gas cleaning, and interstage HX — no Python or MATLAB
   implementation yet.
3. Digital twin data layer — time-series logging of simulation runs.
4. MPC controller (central optimiser / AI reasoning layer).
5. AI agents — start with operator copilot and vendor-sourcing agent.
6. Everything in the "Rare methods" category above.
7. Monte Carlo uncertainty propagation for the 6 unconfirmed assumptions.
