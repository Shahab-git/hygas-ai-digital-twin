# Dynamics layer v0.1 — a transient what-if simulation

**Status: what-if, ASSUMED time constants, not validated against plant data.** Nothing in this layer is
Measured or Confirmed. The hourly runtime (`scripts/run_continuous_cycle.py`) is **unchanged and still
quasi-steady** (see `CLAUDE.md`, Known limitations).

Code: `python/dynamics.py` · tests: `tests/test_dynamics.py` · demo: `scripts/run_transient_demo.py`
(writes `outputs/transient/index.html`, a single page you can double-click).

## 1. What is dynamic now, and what is not

| | Dynamic in v0.1? |
|---|---|
| Gasifier temperature seen by GA-001 (`T_gasifier`) | **Yes** — first-order lag behind the setpoint |
| Fuel conversion / bed inventory (`tau_conv`) | **Yes** — first-order lag on the dry feed rate entering the reaction zone (ER is **not** routed through it, since the what-if-tab round) |
| Gas-phase transport and mixing (`tau_gas`) | **Yes** — first-order lag on GA-001's outlet flow and composition |
| HB-009 → GA-001 tail-gas recycle (`tau_rec`) | **Yes** — a transport *delay* replaces the engine's one-cycle lag |
| EU-008 supply temperature | its per-cycle damping is converted to continuous time (identity at 1 h) |
| Feed (FE), gas cleaning (GC), hydrogen/BoP (HB), electrical/utilities (EU), sensors (SA) | **No** — algebraic; they follow the lagged GA-001 output with no inertia of their own |
| Feed and ER steps | instantaneous (no conveyor/actuator dynamics) |
| HB-013, EU-010, FE-001 inventories | integrate their flows over the real `dt` (audit fix A) |

Anything else you see changing slowly in a transient is an inventory or one of the engine's remaining
one-cycle lagged couplings (section 8). It is **not** a modelled physical lag.

## 2. Method and equations (v0.1: the lag split)

The wrapper calls the steady-state engine as a black box once per sub-step and sets
`cycle_clock.set_elapsed_hours(dt/3600)` (always reset in a `finally`). GA-001's own equations are called
unchanged (`ga001_gasifier_model.ga001_model`) with a *wrapped* `get_input`; inputs are replaced through the
engine's public `promote_to_measurement()`. No physics equation, Confirmed value, `SharedPlantState`,
`simulation_engine` API or `run_continuous_cycle.py` was modified; no database or network is used.

**Which input change goes through which lag**

| change | path |
|---|---|
| feed step | `tau_conv` (fuel inventory), then `tau_gas` (gas transport) |
| ER step | `tau_gas` **only** — air acts on the gas-phase reactions (partial oxidation, burn-out of the volatiles) in seconds to tens of seconds; the 1200 s `tau_conv` maps the *solids* inventory (bed residence time), which an air-flow change does not have to refill. This is a **structural assumption, not model-derived**: the steady model has no ER-dependent conversion (carbon conversion is a fixed 0.90), so it can neither confirm nor refute it. (v0.1 as first released routed ER through `tau_conv` too; that gave an ER t95 of 3602 s.) `ga001_ER_effective` in the series now equals the raw ER. |
| T step | `T_gasifier`, then `tau_gas` (temperature acts on the gas through the water-gas-shift equilibrium, a gas-phase effect; no `tau_conv`) |

**One lag** (exact, stable at any `dt`): `x ← target + (x − target)·exp(−dt/tau)`; `tau ≤ 0` means no lag.

**Cascade** (`tau_conv` on the feed, `tau_gas` on the outputs). The conversion state follows its input exactly.
Inside a sub-step the conv-lagged input (the feed) moves along an exponential and ER is constant at its new value
(it bypasses `tau_conv`; when a feed and an ER change fall in the same sub-step the start state `y0` already contains the new ER,
which is exact for an ER applied from the start of the sub-step), so GA-001's response is
`y(s) = y0 + (y1 − y0)·φ(s)`, `φ(s) = (1 − e^(−s/τc))/(1 − e^(−dt/τc))`, where `y0`/`y1` are the steady-state model
evaluated at the sub-step's start/end conversion state. The gas state then solves `dx/dt = (y(s) − x)/τg` exactly:

```
x(dt) = y0 + (x0 − y0)·e^(−dt/τg) + (y1 − y0)·ψ
ψ     = [ (1 − e^(−dt/τg)) − (e^(−dt/τc) − e^(−dt/τg))/(1 − τg/τc) ] / (1 − e^(−dt/τc))        (τg = τc: dt·e^(−dt/τ)/τ)
```

This is the exact two-lag cascade for a response that is linear in the conv-lagged inputs (the model's
non-linearity inside one sub-step is neglected). If only the temperature moved, the T-lag exponential is used for
`φ`; if only the delayed recycle moved, a ramp (also exact). **Verified** (tests): a lag *probe* (a unit step through
`tau_conv`, `tau_gas` and the cascade with the very same update functions) equals the analytic responses to 1e-12
(single lags `1 − e^(−t/τ)`; cascade `1 − (τc·e^(−t/τc) − τg·e^(−t/τg))/(τc − τg)`, equal-τ limit included); the
recorded gas-state steps equal an independent DOP853 integration of the ODE to 1e-9.

EU-008's damping is converted with `damping(dt) = exp(−dt/τe) = 0.5 ** (dt / 1 h)`, `τe = 1 h / ln 2`, **exactly 0.5
at dt = 1 h** (bit-exact; tested). A scenario step at `t_s` acts from the first sub-step that starts at or after
`t_s`; steps with `t_s ≤ 0` are initial conditions (applied before a 24-cycle, 1 h warm-up, so row 0 is a converged
steady state). Rows are recorded at the **end** of each sub-step.

## 3. Time constants (all Assumed; defaults strictly inside their ranges — a test fails otherwise)

| tau | default | range | status | derivation |
|---|---|---|---|---|
| `T_gasifier` | 120 s | 30–600 s | **Assumed**, engineering placeholder, no source | see below |
| `tau_conv` | 1200 s | 600–2400 s | **Assumed** (CSTR mapping of a registry figure) | see below |
| `tau_gas` | 30 s | 8–120 s | **Assumed** (lower bound derived, allowance is a placeholder) | see below |
| `tau_rec` | 60 s | 10–140 s | **Assumed** (derived from a registry volume) | see section 5 |
| `EU008_cooling_water` | 5193.7 s (= 1 h/ln 2) | 1800–14400 s | **Assumed** (derived from the existing 0.5 per hour) | see below |

* **`T_gasifier`.** `data/equipment_registry.json` (GA-001, "Operating temperature (typical)") remarks that 950 °C "matches
  the value already used in the mass/energy balance dashboard and Simulink thermal-lag model". That model is **not in this
  repository** and no lag value is documented anywhere in it, so 120 s is only the figure proposed in earlier work. The
  range brackets a hot, insulated bed responding to a setpoint change (seconds to minutes) and excludes the hours-long
  thermal soak of the 150 mm refractory lining, which one lag cannot represent.
* **`tau_conv`.** The registry (GA-001) gives "Residence time (design)" = 20 min, described as the **solids** residence
  time in the bed. A bubbling bed is well mixed in its solids and behaves like a CSTR; a CSTR's inventory answers a change
  in its input with a first-order lag equal to its residence time → 1200 s. The 20 min is a datasheet design value
  ("typical … at this scale"); **the CSTR mapping is the assumption**. Range ×2 either side (dead zones and plug-flow regions
  shorten the effective time, a carbon inventory can lengthen it).
* **`tau_gas`.** Registry geometry (GA-001: ID 600 mm, total height 4000 mm incl. bed and freeboard) → vessel volume
  1.131 m³. At the audited flow (125.9 Nm³/h wet → 513 m³/h actual at 950 °C and 1.11 bar = 0.1426 m³/s, superficial
  velocity 0.50 m/s, consistent with the registry's 0.5–1.5 m/s remark) the whole-vessel **plug-flow gas residence time is
  7.9 s** — a minimum (it ignores the solids volume). Mixing allowance, **engineering placeholder, no source**: gas back-mixing
  in a bubbling bed, freeboard recirculation and the outlet duct to GC-001 (volume Missing) are taken as a factor ≈ 4 →
  30 s; the range runs from no allowance (8 s) to a factor ≈ 15 (120 s).
* **`EU008_cooling_water`.** Derived, not new: the existing model relaxes the supply temperature by 0.5 per 1 h cycle
  (`EU008_DAMPING`, itself Assumed). `τe = 1 h / ln 2` makes `exp(−dt/τe)` equal 0.5 exactly at 1 h. The range is a placeholder.

## 4. EU-006 hydrogen draw: the cap was assessed, not implemented

**Finding being tested:** "the EU-006 H₂ budget is `stored energy ÷ dt` (`eu_utilities_chp.py:296`), so at short steps the
fuel cell can draw the whole inventory in one step; this drives the HB-013 chatter."

* **Rating (read-only).** `data/equipment_registry.json`, EU-006 *H₂ Fuel Cell (Stationary)*: "Rated electrical output" = **15 kWe**;
  "Electrical efficiency (LHV)" = **50 %**; "H₂ consumption (rated)" = **10 Nm³/h**, whose own remark says *Calculated:
  (15 kWe / 50 % efficiency) / 10.8 MJ/Nm³*. The first two are datasheet values (Confirmed in the project's sense); the
  10 Nm³/h is derived from them. In kW of H₂ fuel: 15/0.5 = **30 kW** = 10 Nm³/h = **0.8994 kg/h**.
* **The draw is already capped at that rating.** The dispatch (`dispatch_ga.py`, untouched) bounds every unit's load factor
  to ≤ 1, so the fuel cell cannot take more than `FUEL_KW_FULL["PEM Fuel Cell"]` = 30 kW whatever the budget; the
  budget only sets a penalty threshold. The 0.8994 kg/h seen in the audit's HB-013 outflow is exactly that full-load draw.
* **Would a cap `min(stored/dt, 30 kW)` bind at 1 h? Yes** (all 116 entries, five default cycles, cap tried in-process):

  | cycle | uncapped `h2_budget_kw` | binds? | entries that differ |
  |---|---|---|---|
  | 1 | 86.1 kW | yes | `EU-CHP/Dispatch` (field `h2_budget_kw` only; `units` identical) |
  | 2 | 161.5 kW | yes | same |
  | 3 | 153.4 kW | yes | same |
  | 4 | 70.3 kW | yes | same |
  | 5 | 0.0 kW | no | none |

  The final snapshot is identical, but a bit-identical-at-every-cycle requirement is not met, so **no change was made** and the
  decision is listed in the report ("Needs your decision").
* **It would not remove the chatter anyway.** Throw-away trials (nothing committed), 2 h at 60 s, no scenario:

  | trial | HB-013 level | outflow | sign changes (of 119) |
  |---|---|---|---|
  | as committed | 0–3.83 kg | 0–72.9 kg/h | **41** |
  | EU-006 budget capped at 30 kW | 0–3.83 kg | 0–72.9 kg/h | **41** (identical) |
  | HB-018 dispensing forced to 0 | 50 kg (full) | 0.899 kg/h constant | **0** |
  | EU-006 H₂ budget forced to 0 | 0–0.157 kg | 0–9.4 kg/h | **1** |

  (The earlier "0.9–6.5 kg/h" was a sample every 10 min; the per-step outflow swings 0–72.9 kg/h.)
  **Cause:** `HB-018` dispenses `min(rate·dt, previous-cycle level)` (`hb_remaining_chain.py:986–989`; rated 1.2 kg/min = 72 kg/h),
  i.e. it empties whatever stock exists each step; the stock is then tiny, so EU-006's `stored ÷ dt` budget (`eu_utilities_chp.py:296`) is
  stock-limited (far below 30 kW) and the fuel-cell draw swings with it; both read HB-013 one cycle late
  (`hb_wgs_psa_storage_chain.py:608`, `hb_remaining_chain.py:1051`). The cap binds only when the stock is large, which is not the
  chattering regime. Options (not done): limit HB-018's draw to a fraction of the stock per step; let HB-018/EU-006 act on the
  same-cycle level; give HB-013 a minimum reserve. Each edits a model file.

## 5. Recycle: `tau_rec` (v0.1)

GA-001 reads the HB-009 tail gas through `lagged_depends_on` (`ga001_gasifier_model.py:1148`) in `_recycle_atom_moles()`
(`:673`); the engine serves lagged keys from the previously published state (`simulation_engine.py:269–271`) — one **cycle** late
(60 s at `dt = 60 s`), which closes a positive feedback around the lag. `ga001_model` receives `get_input` as an argument, so
the wrapper hands it a different one: a buffer of published HB-009 entries is read at `t_end − tau_rec` (linear interpolation;
exactly on a node → the entry object unchanged; never shorter than one sub-step). **No engine or model file changes.**

`tau_rec` = 60 s, range 10–140 s, Assumed. Registry (HB-009): "Tail gas buffer tank volume" = **1 m³** "ahead of the gasifier feed".
V/Q at the audited tail flow (84.3 Nm³/h, ~0.2 bar(g), 25–60 °C) = **42–47 s**; at the registry's design tail flow (29.4 Nm³/h)
= **120–134 s**. 60 s lies between them; the 10 s lower bound (piping only, buffer bypassed) is an engineering placeholder.
A well-mixed tank would be a lag rather than a delay; v0.1 models the delay that was asked for.

**Results** (cubic-spline time to 95 % of the GA-001 flow response, dt = 30 / 60 / 120 s, `tau_rec` = 240 s so the delay is resolved):

| step | engine one-cycle lag | with `tau_rec` |
|---|---|---|
| T 950 → 930 | 3.80 % spread | **0.71 %** |
| ER 0.25 → 0.30 | 6.14 % | **0.83 %** |
| feed +10 % | 13.5 % | 8.3 % (not fixed, see below) |

Identity: a delay of one cycle at `dt = 1 h` (and the default 60 s, which clamps to one cycle) gives the empty 116-entry diff
against `build_live_snapshot(5)`. **ER overshoot:** the steady-state *target* still jumps to ≈ 130 % of its final change
(the recycle's own settling), but the lagged flow now peaks at 99.6 % — the overshoot is not passed on. **The feed step keeps
a dt-dependence** because the feed GA-001 reads comes through the engine's one-cycle FE-005 lag
(`ga001_gasifier_model.py:1137,1148`); a test shows it is exactly one sub-step late. The wrapper cannot replace that read
(the current-cycle FE-005 value is not a declared dependency).

## 6. Running it

```
python scripts/run_transient_demo.py        # from the repo root; ~1.5 minutes; no database, no network
python -m pytest -q tests/test_dynamics.py  # 24 tests, ~50 s (the 12 added in v0.1 take ~26 s)
```

The script prints the absolute path of `outputs/transient/index.html` (self-contained, no external resources). Programmatic use:

```python
from python import dynamics as dy
r = dy.run_transient([{"t_s": 600, "feed_rel": 0.10}], dt_s=60, duration_s=7200)   # also "feed_kg_h", "ER", "T_setpoint_C"
r.status, r.assumptions, r.limits   # honesty metadata; r.verify_honesty() raises if a tau is used but not listed
r.series                            # list of dicts (see SERIES_UNITS), incl. the lag probe and the recycle delay actually used
```

Demo output (v0.1 defaults, dt = 60 s, 2 h, step at 10 min; seconds after the step):

| scenario | quantity | before | final steady | t63 | t95 |
|---|---|---|---|---|---|
| feed +10 % | GA-001 dry flow, Nm³/h | 102.75 | 113.03 | 1318 | 3713 |
| | H₂ production, kg/h | 3.251 | 3.576 | 1324 | 3719 |
| | EU-008 demand, kW | 51.99 | 57.19 | 1317 | 3713 |
| ER 0.25 → 0.30 | GA-001 dry flow | 102.75 | 106.87 | 34 | 51 |
| | H₂ production | 3.251 | 2.889 | 54 | 163 |
| | EU-008 demand | 51.99 | 51.82 | 207 | 324 |
| T 900 → 930 °C | GA-001 dry flow | 103.51 | 103.05 | 162 | 408 |
| | H₂ production | 3.2498 | 3.2505 | 115 | 192 |
| | EU-008 demand | 51.98 | 51.99 | 54 | 83 |

The t63 of the feed response sits at `tau_conv` (+ the FE-005 sub-step), instead of the 1626 s of v0 that came from the one-cycle
recycle loop. The ER rows changed with the lag-routing follow-up (ER through `tau_gas` only; was 1204 / 3602 s for GA-001 flow).

**Read the ER rows with care — overshoot.** An ER step moves the steady-state target of GA-001's flow to 108.09 Nm³/h at once and the
recycle loop then relaxes it to 106.87. The lagged flow therefore peaks at about 107.4 (≈ 114 % of the final change) before settling,
so the *first crossing* of 95 % (the definition used here, the same as in the demo script and in the what-if tab) happens within one
60 s sub-step even though the signal is not settled. t95 here means "first reaches 95 %", not "settled within 5 %"; the what-if tab's
table shows the peak (% of final change) next to it. The EU-008 demand t63/t95 of 207 / 324 s is the EU-008 supply-temperature
damping, not a plant lag.

## 7. Findings the layer exposes (reported, not fixed)

1. **Gasifier temperature barely moves the steady-state model.** T enters GA-001 only through the water-gas-shift equilibrium
   constant (`ga001_gasifier_model.py:746` → `:787` → `_wgs_keq`, `:314`); there is no energy balance, the carbon conversion is a fixed
   0.90 and tar is Missing. Over 850 → 950 °C: dry flow −1.6 %, H₂ fraction −3.7 %, CO +8.2 %, CO₂ −13.6 %, LHV +1.9 %,
   **H₂ production +0.08 %**, EU-008 demand +0.05 %. The thermal lag is nearly decorative until that changes.
2. **HB-013 chatters at a 60 s step with no disturbance** — cause and trials in section 4 (HB-018's whole-stock draw plus EU-006's
   `stored ÷ dt` budget, both reading the level one cycle late). HB-013, EU-010 and anything derived from them are non-physical in a
   transient; the algebraic outputs (H₂ production, EU-008 demand) still converge to the steady engine to ~1e-16.
3. **Remaining one-cycle couplings** become dt-long delays at a short step: FE-005 → GA-001 feed read (`ga001_gasifier_model.py:1137,1148`),
   HB-013/HB-018/EU-006 (`hb_wgs_psa_storage_chain.py:608`, `hb_remaining_chain.py:1051`), the EU-008 pair (`eu_utilities_chp.py:887,892,897`),
   EU-010 (`:907`), FE-001 (`fe_feed_handling.py:377`), AI-004 states (`ai_automation_layer.py:640–662`). `STARTING` (AI-004's first-cycle
   state) is meaningless in a transient.

## 8. Questions that replace each Assumed parameter

* **`T_gasifier`:** real step response of the bed/outlet temperature to a setpoint or air-flow change (time to 63 %/95 %); the heating actuator.
* **`tau_conv`:** bed solids inventory (kg) and fuel feed rate (solids turnover time); measured gas-composition response to a feed-rate step;
  whether ER acts on the solids/carbon inventory (as assumed in v0 and removed in the what-if-tab round) or only on the gas phase
  (as assumed now) — the measured gas-composition response to an air-flow (ER) step settles this.
* **`tau_gas`:** freeboard and outlet-duct volumes (gas residence time); measured outlet-gas response to a feed or ER step.
* **`tau_rec`:** the real tail-gas path (buffer-tank volume and whether it is bypassed, blower flow, pipe length, actual tail-gas flow and temperature).
* **`EU008_cooling_water`:** cooling-tower basin water volume and circulation rate.
* Also: the Simulink thermal-lag model's real parameters (if DOK-ING can supply the files); start-up and setpoint-step curves; bed thermal mass.

## 9. Using the what-if tab (Tab 11, "Transient What-If")

A throw-away simulation in the Streamlit app (`python/ui_transient_tab.py`, logic in `python/ui_transient_sim.py`). It is the 11th and last tab;
Tabs 1–10, the header and the runtime status line are unchanged. **It is not the live plant:** an always-visible red banner says so, it never
reads or changes the plant state published by the hourly runtime, opens no database client and makes no network call. The only things it keeps
are the last result in the viewer's session and `st.cache_data` entries keyed on all parameters.

**Controls** (nothing runs until **Run what-if simulation** is pressed; moving a slider never starts a run):

| control | range | note |
|---|---|---|
| Step type | feed / ER / gasifier T setpoint | one step per run |
| Feed-rate change | −30 … +30 % | **tab limit, not a validated range** (base 41.67 kg/h as received) |
| New ER | 0.2125 … 0.2875 | **tab limit, not a validated range**; fixed constants (see "Where the ER range comes from"); base 0.25 |
| New T setpoint | 850 … 1000 °C | **tab limit, not a validated range**: below the Confirmed 1050 °C design temperature; 850 °C is the low end of section 7; base 950 °C |
| Step time, duration | duration 10 … 240 min, **at most the longest run the caps allow at the chosen dt** | the step is snapped to a sub-step boundary; a duration above the maximum is reduced with a visible notice, not refused at Run |
| dt | 10 / 15 / 30 / 60 / 120 s | see the dt rule and the defaults below |
| the five time constants | each limited to its range in section 3 | each shows an `Assumed` tag, the reasoning (tooltip) and the question for DOK-ING |

**dt rule.** A time constant shorter than 2·dt gets a visible warning (poorly resolved). A time constant shorter than dt **blocks** the run (the
Run button is disabled and the message says which tau and what to change): its response would fit inside one step and t63/t95 could not be read.
Measured in `tests/test_dynamics.py`: with tau = dt/2 the t95 spread across dt was 24 %, with tau = dt it was 0.3 %. Blocking at tau < 2·dt would
leave **no** runnable combination at the Assumed defaults (`tau_gas` = 30 s), so the defaults use dt ≤ 30 s; at dt = 60 s raise `tau_gas` to ≥ 60 s
and `tau_rec` to ≥ 120 s.

**Defaults per step type** (changing the step type applies them; the reason is shown next to the controls): feed dt 30 s, 2 h (the slowest lag,
`tau_conv` = 1200 s, dominates); **ER dt 10 s, 30 min** (an ER step passes through `tau_gas` = 30 s only and the GA-001 flow reaches 63 % in about 20 s, so only
dt = 10 s samples it twice; at 15 s that t63 is correctly shown as unresolved); **T dt 15 s, 30 min** (the EU-008 demand reaches 63 % of a T step in about
54 s, which needs dt ≤ 15 s). The longest run at each dt: 10 s → 40 min, 15 s → 60 min, 30 s → 120 min, 60 s and 120 s → 4 h (240 steps at 60 s).

**"Not resolved".** A t63 or t95 shorter than 2·dt lies inside one or two samples, so it is an interpolation, not a measurement. The table and the response
CSV then show **"not resolved (< 2 steps)"** instead of the number (the CSV header and a caption give the sampling interval); a time of at least 2·dt is
always shown as a number. Choose a smaller dt to resolve it.

**Caps** (protect the Streamlit server): at most **240 steps** per run (duration ÷ dt) and **4 h**; either one shows a "Cap hit" message and
disables Run. Each step is one full engine cycle (~0.1 s on the development machine) plus a fixed ~6 s (24 warm-up cycles, the independent
steady-state engine for the final values, process start). One run at a time per server process; a second press meanwhile says "another run is in progress".
The worker is killed after 300 s. Measured on the development machine (Windows, Python 3.14), wall time of a run through the worker:

| run | steps | wall time |
|---|---|---|
| feed, dt 30 s, 2 h (default) | 240 | 29.9 s |
| ER, dt 10 s, 30 min (default) | 180 | 23.1 s |
| T, dt 15 s, 30 min (default) | 120 | 17.5 s |
| ER, dt 15 s, 60 min (longest at 15 s) | 240 | 29.0 s |
| ER, dt 10 s, 40 min (longest at 10 s) | 240 | 29.0 s |
| T, dt 15 s, 60 min (longest at 15 s) | 240 | 29.4 s |
| dt 60 s, 4 h, `tau_gas` 60, `tau_rec` 120 (longest allowed) | 240 | 29.3 s |
| the same parameters again | – | 0.05 s (cache) |

No default scenario exceeds 60 s here. **Run times on Streamlit Community Cloud may be 2–3× slower than these local numbers (not measured; the app is not deployed from this branch).**

**Memory.** Method: Windows `GetProcessMemoryInfo` through `ctypes` (peak working set = peak resident memory; no new dependency). The server was started with the offline
fake store (never the real `secrets.toml`) and a real session rendered every tab: server process peak **271.9 MiB** (244.8–253.8 MiB current after one or two more
sessions). The worker, running the real entry point (`worker_main`): **67.1 MiB** right after import, **68.0 MiB** peak after the default feed run, **68.1 MiB** after
the longest allowed run (4 h at dt 60 s), **68.0 MiB** after the ER default. Sum of the peaks about **340 MiB**, below the 700 MiB threshold and about a third of the ~1 GB
limit of a Community Cloud app, so no mitigation is proposed. A result payload is about 135 kB, and at most 8 are cached. Caveats: Windows / Python 3.14 here against Linux /
Python 3.11 there; each further viewer session adds a few MiB; **real Community Cloud memory and CPU are NOT VERIFIED until deployed**. The Windows commit figure (peak
pagefile usage, 819 MiB worker, 1744 MiB server) is reserved address space, not resident memory, and is not comparable to the cloud limit. A "refuse to run when memory is
low" guard was **not** added: reading available memory portably without a new dependency (cgroup files on Linux, `GlobalMemoryStatusEx` on Windows) could not be verified for the
cloud container, and the rule is not to guess.

**Why a child process.** `run_transient` has to move two module-level globals while it runs (`cycle_clock`'s elapsed-hours override and
`EU008_DAMPING`). The server runs every viewer in one process and `app.py`'s own cached engine runs read the same globals, so a run inside the server
process could leak a 30 s clock into other viewers' cached numbers for up to 300 s. The run therefore happens in `python -m python.ui_transient_sim`:
the server's globals are never touched, the child gets no credentials (`child_env`: no variable whose name contains SUPABASE, SECRET, TOKEN, KEY,
PASSWORD, AUTH, …; `HYGAS_ALLOW_DB_WRITES` forced to 0), its database clients and socket connections raise, and a crash is a one-line message, not a traceback.

**What is shown.** A normalised chart (0 % = old, 100 % = new steady state) with the t63 / t95 markers, absolute charts (one panel per quantity) with the step
marker and the old/new steady-state values,
the response-time table (before / end of run / final steady state, t63, t95, peak % of the change; same definitions as the demo script, final = the
independent steady-state engine at the final inputs; a change below 0.01 % is shown as "≈ 0, not meaningful"), the three findings, the Assumed
parameters with the question each becomes, and two CSV downloads (the series carries the banner and the Assumed time constants as `#` header rows).

**Chart conventions** (presentation only; `python/ui_transient_charts.py`). Every plotted quantity has one fixed **colour, dash and point shape**, the same in the normalised chart,
its legend and its absolute panel: 11 colours with a single blue and a CIE-Lab distance of at least 25 between any two (checked by a test), so the chart also reads for colour-blind
viewers and in greyscale print through the dash and the shape. The legend sits at the right, outside the plot; clicking an entry highlights that curve. Charts use the full container width,
one per row: the normalised chart is 360 px high; the absolute figure is one panel per quantity (170 px each), each with its own y scale because the quantities differ by up to three
orders of magnitude (flow ~100 Nm³/h, CH₄ ~1.6 mol %, T_gasifier 950 °C), so there is no shared or dual axis, and the time axis is identical in every panel. The time axis is titled
"time since start, min" and its ticks follow the duration: every 1 min up to 30 min, every 5 min up to 60 min, every 10 min up to 2 h, every 15 min up to 3 h, every 30 min above.
The step is a thin black rule labelled "step at … min"; old / new steady states are grey / red dashed rules. On the normalised chart, horizontal guides mark 63.2 % and 95 %, and a
selectbox (default GA-001 dry flow) chooses the quantity whose **t63 / t95** are drawn as dotted verticals at the step time plus the value in the response table; a time the table shows
as "not resolved (< 2 steps)" (or "not reached in this run") gets no marker, and the caption under the chart prints that text and the sampling interval. An absolute panel whose whole excursion (steady-state lines included) is under 0.1 % of the quantity's value prints
"axis zoomed: total change is X % of the value" under its title (the Axis radio offers "from zero"), and a caption under the normalised chart appears when two or more curves stay within 2 percentage points of each other at every sampled time.

**Not valid in transients** (red box, never plotted or exported; the worker does not even send them): HB-013 storage, HB-018 dispensing, EU-010 and what
derives from them (EU-006, EU-009 grid balance, AI-004 states). Reason: the dispensing demand is Missing and the stock is drained each step (section 4).
In a quiet run the plotted quantities are flat to 1e-14 while HB-013 swings, which is why the split is safe. Ask DOK-ING for the real dispensing profile.

**Where the ER range comes from.** `ER_RANGE = (0.2125, 0.2875)` and `ER_BASE = 0.25` in `python/ui_transient_sim.py` are **literals** (the default Assumed band of
`air_equivalence_ratio`, 0.25 ± 15 %, copied; tab limits, not validated ranges). They used to be `uncertainty.bounds()` read when the module was first imported, which in the app
happens after Tab 1's confirmation sync (`app.py:481`): with a confirmation row replayed into memory the slider would have narrowed to that row's range (checked in memory with the
reader patched: 0.245–0.255 and default 0.255 with the sync, 0.2125–0.2875 and 0.2875 without). Now both give 0.2125–0.2875; a test pins this in child processes. Next to the slider the tab
shows the air-ratio status ("Assumed, not confirmed" or "confirmation recorded, range …") read from the already-synced in-memory `ASSUMPTIONS`; it adds no database read.

**Question for DOK-ING (also shown in the tab):** what is the real operating envelope for feed rate, air ratio (ER) and gasifier temperature? The input limits of this tab are not validated ranges.

**Reading ER-step results.** An ER step overshoots (section 6): "t95" is the first crossing and can happen within a few steps; use the peak column, and note that times under 2·dt are shown as not resolved.

**Not in the tab:** a "Replay" animation (optional; not built — a client-side animation could not be verified headlessly here), connecting a transient to
live shared state, sensor ingestion, calibration, any change to the hourly runtime.

## 10. Not in v0.1

An always-on process, sensor ingestion, calibration against plant data, lags in GC/HB/EU/SA models,
a GA-001 energy balance or temperature-dependent conversion, conversion of the remaining per-cycle couplings, and any change to the hourly runtime.
