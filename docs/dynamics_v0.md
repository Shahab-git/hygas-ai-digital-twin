# Dynamics layer v0 — a transient what-if simulation

**Status: what-if, ASSUMED time constants, not validated against plant data.** Nothing in this layer is
Measured or Confirmed. The hourly runtime (`scripts/run_continuous_cycle.py`) is **unchanged and still
quasi-steady** (see `CLAUDE.md`, Known limitations).

Code: `python/dynamics.py` · tests: `tests/test_dynamics.py` · demo: `scripts/run_transient_demo.py`.

## 1. What is dynamic now, and what is not

| | Dynamic in v0? |
|---|---|
| Gasifier temperature seen by GA-001 (`T_gasifier`) | **Yes** — first-order lag behind the setpoint |
| GA-001 outlet flow and composition (`GasHoldup`) | **Yes** — first-order lag behind GA-001's own steady-state result |
| EU-008 supply temperature | its existing per-cycle damping is converted to continuous time (identity at 1 h) |
| Feed (FE), gas cleaning (GC), hydrogen/BoP (HB), electrical/utilities (EU), sensors (SA) | **No** — algebraic; they follow the lagged GA-001 output with no inertia of their own |
| Feed and ER steps | instantaneous (no conveyor/actuator dynamics) |
| HB-013, EU-010, FE-001 inventories | integrate their flows over the real `dt` (already true since audit fix A) |

Anything else you see changing slowly in a transient is one of: an inventory, or one of the engine's existing
one-cycle lagged couplings (section 5). It is **not** a modelled physical lag.

## 2. Method

The wrapper calls the steady-state engine as a black box once per sub-step and sets
`cycle_clock.set_elapsed_hours(dt/3600)` (always reset in a `finally`). GA-001's own equations are called
unchanged (`ga001_gasifier_model.ga001_model`); inputs are replaced through the engine's public
`promote_to_measurement()`. No physics equation, Confirmed value, `SharedPlantState`, `simulation_engine`
API or `run_continuous_cycle.py` was modified; no database or network is used.

Every lag is a first-order state solved with the exact exponential update (stable at any `dt`):

```
dx/dt = (x_target - x) / tau        ->        x <- x_target + (x - x_target) * exp(-dt / tau)
```

`tau <= 0` means no lag (that is how the layer is switched off). Per sub-step: (1) the scenario inputs for the
step are fixed; (2) `T_gasifier` is relaxed toward the setpoint; (3) the clock is set to `dt`; (4) the engine runs
one cycle with the lagged `T_gasifier`; (5) inside that cycle GA-001's outputs are relaxed toward the steady-state
target just computed; (6) the row is recorded at the **end** of the sub-step. A step at `t_s` acts from the first
sub-step that starts at or after `t_s`; steps with `t_s <= 0` are initial conditions (applied before a 24-cycle,
1 h warm-up, so row 0 is a converged steady state).

EU-008's per-cycle damping `EU008_DAMPING = 0.5` is converted with `damping(dt) = exp(-dt/tau_e) = 0.5 ** (dt / 1 h)`,
`tau_e = 1 h / ln 2`, which is **exactly 0.5 at dt = 1 h** (bit-exact; tested). The module constant is set per
sub-step and restored in a `finally`; `eu_utilities_chp.py` is not edited.

## 3. Time constants (all Assumed)

| tau | default | range | status | question for DOK-ING |
|---|---|---|---|---|
| `T_gasifier` | 120 s | 30–600 s | **Assumed** — engineering placeholder, no source | Real step response of the bed/outlet temperature to a setpoint or air-flow change (time to 63 %/95 %)? What is the heating actuator? |
| `GasHoldup` | 1200 s | 8–1200 s | **Assumed** | Bed solids inventory (kg) and fuel feed rate (solids turnover time); measured outlet-gas response to a feed step; freeboard gas residence time. |
| `EU008_cooling_water` | 5193.7 s (= 1 h / ln 2) | 1800–14400 s | **Assumed** (derived from the existing 0.5 per hour; range = placeholder, no source) | Cooling-tower basin water volume and circulation rate. |

**Reasoning**

* **`T_gasifier`.** `data/equipment_registry.json` (GA-001, "Operating temperature (typical)") remarks that 950 °C
  "matches the value already used in the mass/energy balance dashboard and Simulink thermal-lag model". That
  model is **not in this repository** and no lag value is documented anywhere in it, so 120 s is only the figure
  proposed in earlier work — an engineering placeholder, no source. The range brackets a hot, insulated bed
  responding to a setpoint change (seconds to minutes) and does **not** include the hours-long thermal soak of
  the 150 mm refractory lining, which a single lag cannot represent.
* **`GasHoldup`.** Registry geometry (GA-001: ID 600 mm, total height 4000 mm incl. bed and freeboard) gives a
  vessel volume of 1.131 m³. At the audited flow (125.9 Nm³/h wet → 513 m³/h actual at 950 °C and 1.11 bar;
  superficial velocity 0.50 m/s, consistent with the registry's 0.5–1.5 m/s remark) the whole-vessel **gas**
  residence time is ≈ 8 s — an upper bound that ignores the solids volume, and the lower end of the range. A
  bubbling bed is well mixed in its solids, and the registry's "Residence time (design)" = 20 min is the
  **solids** residence time; a well-mixed (CSTR) inventory answers a change in fuel input with a first-order lag
  equal to its residence time, so the default is 1200 s. The 20 min is a DOK-ING datasheet design value
  ("typical … at this scale"); **the CSTR mapping is the assumption**. 1200 s is the *upper* end: right for feed
  steps, too slow for ER/air steps (gas-phase, seconds). v0 has one tau for every cause.

## 4. Running it

```
python scripts/run_transient_demo.py        # from the repo root; ~1 minute; no database, no network
python -m pytest -q tests/test_dynamics.py  # 12 tests, ~25 s
```

The demo writes `outputs/transient/<scenario>.csv` (and a PNG per scenario only if matplotlib is already
installed; it is not a requirement). Programmatic use:

```python
from python import dynamics as dy
r = dy.run_transient([{"t_s": 600, "feed_rel": 0.10}], dt_s=60, duration_s=7200)   # also "feed_kg_h", "ER", "T_setpoint_C"
r.status, r.assumptions, r.limits   # honesty metadata; r.verify_honesty() raises if a tau is used but not listed
r.series                            # list of dicts: T_gasifier_C, ga001_dry_flow_nm3_h, H2/CO/CO2/CH4/N2 %, lhv_mj_nm3,
                                    # h2_production_kg_h, hb013_storage_kg, eu008_demand_kw, eu008_supply_temp_c, eu010_soc_kwh, ai004_eu009_state
```

First-run demo output (dt = 60 s, 2 h, step at 10 min; times in seconds after the step):

| scenario | quantity | before | final steady | t63 | t95 |
|---|---|---|---|---|---|
| feed +10 % | GA-001 dry flow, Nm³/h | 102.75 | 113.03 | 1626 | 4708 |
| | H₂ production, kg/h | 3.251 | 3.576 | 1715 | 4891 |
| | EU-008 demand, kW | 51.99 | 57.19 | 1621 | 4698 |
| ER 0.25 → 0.30 | GA-001 dry flow | 102.75 | 106.87 | 882 | 2320 |
| | H₂ production | 3.251 | 2.889 | 1494 | 4277 |
| | EU-008 demand | 51.99 | 51.82 | 4577 | not reached |
| T 900 → 930 °C | GA-001 dry flow | 103.51 | 103.05 | 1370 | 4001 |
| | H₂ production | 3.2498 | 3.2505 | 911 | 1710 |
| | EU-008 demand | 51.98 | 51.99 | 393 | 604 |

## 5. Findings the layer exposes (reported, not fixed)

1. **Gasifier temperature barely moves the steady-state model.** T enters GA-001 only through the water-gas-shift
   equilibrium constant (`ga001_gasifier_model.py:746` → `:787` → `_wgs_keq`, `:314`); there is no energy balance,
   the carbon conversion is a fixed 0.90 and tar is Missing. Over 850 → 950 °C (steady engine): dry flow −1.6 %,
   H₂ fraction −3.7 %, CO +8.2 %, CO₂ −13.6 %, LHV +1.9 %, **H₂ production +0.08 %**, EU-008 demand +0.05 %.
   A temperature transient therefore shows up mainly in the gas composition, not in H₂ production.
2. **Effective response time ≠ the stated tau.** The existing GA-001 ← HB-009 tail-gas recycle reads the
   (already lagged) GA-001 output one cycle later, which closes a positive feedback around `GasHoldup`: the
   steady-state *target* is not a clean step (feed +10 %: it jumps to 78 % of its final change then creeps up; ER:
   it overshoots to 129 % then relaxes), so the effective time is about `tau_g / (1 − g)` (measured t63 = 1626 s
   vs `tau_g` = 1200 s for the feed step; 882 s for ER). Read the tables as "tau plus the recycle loop", not as the tau.
3. **The engine's lagged couplings are one *cycle* long, not one second.** At `dt = 60 s` each becomes a 60 s
   delay or loop gain: FE-005 → GA-001 feed read (`ga001_gasifier_model.py:1137,1148`), GA-001 ↔ HB-009 recycle
   (`:1148`), HB-013 ↔ HB-018 ↔ EU-006 (`hb_wgs_psa_storage_chain.py:608`, `hb_remaining_chain.py:1051`), the EU-008
   pair (`eu_utilities_chp.py:887,892,897`), EU-010 (`:907`), FE-001 (`fe_feed_handling.py:377`), AI-004 states
   (`ai_automation_layer.py:640–662`). They are **not converted** in v0; the response time of coupled outputs
   depends weakly on `dt` (GA-001 flow t95 = 573 / 567 / 561 s for dt = 30 / 60 / 120 s, a ≈ 2.2 % spread, above the 1 %
   target; the exponential lags themselves are exact — `T_gasifier` agrees within 0.1 %).
4. **HB-013 chatters at a 60 s step with no disturbance at all** (`hb_wgs_psa_storage_chain.py:608` loop with HB-018 and
   EU-006, whose H₂ budget is stored energy ÷ dt, `eu_utilities_chp.py:296`): storage stays between 0 and 0.08 kg
   while its outflow swings between 0.9 and 6.5 kg/h around a constant 3.26 kg/h inflow (41 sign changes of the level
   in 120 steps; 1 h cycles showed the same non-settling behaviour in the 2026-10-27 audit). It does not feed back
   into the algebraic outputs listed above (H₂ production, EU-008 demand), which is why those still converge to the
   steady-state engine to ~1e-16; HB-013, EU-010 and anything derived from them should not be read as physical.
5. `STARTING` (AI-004, first published cycle) is a per-cycle notion and is not meaningful in a transient.

## 6. Data needed to calibrate (and replace each Assumed tau)

* Bed thermal mass: bed inventory (kg, material), refractory mass/thickness/conductivity, shell losses.
* Start-up and setpoint-step response curves of the bed/outlet temperature (time to 63 % and 95 %).
* Heating/air-preheat actuator: type, power, response.
* Gasifier volume split (bed, freeboard), bed solids inventory and fuel feed rate (solids turnover time); the
  registry's "20 min" confirmed as solids residence time and at what feed rate.
* Any measured step response of outlet gas flow/composition to feed, ER or temperature changes.
* Cooling-tower basin volume and circulation rate (EU-008).
* The Simulink thermal-lag model's real parameters, if DOK-ING can supply the model files.

## 7. Not in v0

Wiring into the Streamlit tabs, an always-on process, sensor ingestion, calibration against plant data, lags in
GC/HB/EU/SA models, changes to the hourly runtime, conversion of the other per-cycle couplings.
