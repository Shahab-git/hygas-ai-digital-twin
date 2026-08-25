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

Neither directory exists yet in this repo — see "Not yet built" below.
When adding a new physics module, implement it in both languages and
cross-check that they agree numerically before considering it done.

## Validated milestones (design targets — not yet reproduced in this repo)

These numbers come from prior MATLAB/Simulink modelling work on this
project and are the targets any new implementation here should match.
They are not yet confirmed live in this repo's code.

| Subsystem | Result | Target |
|---|---|---|
| Gasifier mass balance | 46.88 kg/h | 46.9 kg/h |
| Gas cleaning | 45.94 kg/h | ~45.9 kg/h |
| WGS HTS (Arrhenius/Van't Hoff kinetics, Fe-Cr catalyst) | 75.0% conversion | 75.0% |
| Interstage HX | 4.134 kW | ~4.1 kW |
| WGS LTS (Cu/ZnO/Al2O3 catalyst) | 40.0% relative conversion | 40.0% |
| WGS overall | 85.0% | 85.0% |
| PSA recovery (selectivity + pressure-ratio correlation) | 75.0% | 75.0% |
| CHP part-load efficiency (4 technologies) | verified at rated + part-load | — |
| CHP dispatch GA | SOFC 76.9%, GasEngine 81.3%, Microturbine 0%, PEM 49.9% | fuel-constrained optimum |

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

This repo is a fresh start — none of the following exist here yet:

1. `/matlab` — the physics model itself.
2. `/python` — the cross-check implementation / Streamlit backend.
3. Digital twin data layer — time-series logging of simulation runs.
4. MPC controller (central optimiser / AI reasoning layer).
5. AI agents — start with operator copilot and vendor-sourcing agent.
6. Everything in the "Rare methods" category above.
7. Monte Carlo uncertainty propagation for the 6 unconfirmed assumptions.
