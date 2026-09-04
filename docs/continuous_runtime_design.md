# Continuous Simulation Runtime Layer — Design

**STATUS: DESIGN ONLY. Nothing in this document has been implemented.** No
code, schema, or workflow file described here exists yet. This is a
specification for review before any of it is built.

## 0. Purpose and scope

Today the Digital Twin only computes when something asks it to: a Streamlit
viewer opens Tab 1 (or its 60-second cache expires) and
`tab1_integration.build_live_snapshot()` builds a **brand-new**
`SharedPlantState` + `SimulationEngine`, registers every phase (FE→GA→GC→
HB→EU→SA→AI), runs `DEFAULT_CYCLES = 5` synthetic-timestamp cycles in a
fraction of a second, and throws the whole thing away when the process
exits or the cache entry expires (`app.py`'s own
`@st.cache_data(ttl=60)` wrapper around `_tab1_integration_snapshot()`).
Nothing persists between renders except whatever a viewer's own Supabase
writes (vendor quotes, confirmations, AI-011's per-cycle log row) leave
behind. This is "runs when triggered," and it is the ONLY mode the app has
ever operated in.

**Target architecture:**

```
Existing Digital Twin models  →  Continuous Simulation Runtime  →  Persistent Plant State / Time-Series  →  Live Dashboard
 (FE→GA→GC→HB→EU→SA→AI,           (a new, small driver script,          (Supabase — reusing the SAME          (Streamlit: reads the
  simulation_engine.py,             run on a real external               project already used for               store, computes nothing,
  shared_plant_state.py --          schedule, independent of              vendor_quotes/assumption_               displays "as of <time>")
  UNCHANGED)                        any Streamlit session)                confirmations/digital_twin_
                                                                            cycle_log/measurement_
                                                                            promotions)
```

**What this design does NOT touch, and why each is safe to leave alone:**

| Existing piece | Stays as-is because |
|---|---|
| Every equipment model (`ga001_gasifier_model.py`, `gc_gas_cleaning_chain.py`, `hb_*`, `eu_utilities_chp.py`, `fe_feed_handling.py`, `sa_virtual_sensors.py`, `ai_automation_layer.py`) | This layer only decides **when** `run_cycle()` is called and **where the result goes** — it never changes what a model computes. |
| `simulation_engine.py`'s execution logic (`register_model`, `_topological_order`, `run_cycle`, `promote_to_measurement`) | Reused exactly as it is, called from a new caller. Confirmed by direct reading (see §6, §8) — no change is needed to make it work from a headless script instead of a Streamlit session; it already has no Streamlit dependency at all. |
| `shared_plant_state.py`'s schema and guarantees (single-writer, atomic publish, Missing-as-first-class) | Reused exactly as it is. §3 below confirms rehydrating persisted state into a fresh process is achievable through the **existing public API only** (`new_writer_handle` / `begin_cycle` / `set_entry` / `publish_cycle`) — no new method is proposed. |
| `measurement_promotion.py` (Phase 6) | Reused, unmodified, for a second purpose (§5) — see §6 for the direct confirmation this needed no change. |
| Every existing self-test | Confirmed unaffected in §8, not assumed. |

Everything genuinely new is additive: one new driver script, two new/extended
Supabase tables, one new tiny reader-factory function (mirroring an
existing one), and a change to **what `app.py`'s cached Tab 1 function
does** (reads a store instead of running the engine) — not to any function
it calls today.

---

## 1. The persistent runtime process

### The real constraint

Streamlit Community Cloud runs exactly one thing: your app's own Python
script, inside one container, woken by viewer traffic. It has no worker
process, no cron primitive, and no guarantee the container stays up absent
viewers — Community Cloud apps are put to sleep after a period of
inactivity and are recycled/restarted on redeploys. Anything that only
lives inside `app.py`'s own process — including a `threading.Thread`
started at import time with a `while True: sleep(3600)` loop — is **not**
independent of the dashboard: it dies when the container sleeps, it
restarts (losing any in-memory state) on every redeploy, and if two
viewers' requests ever get routed to different container instances (or a
redeploy happens mid-loop), you get either zero or duplicate copies of the
loop with no coordination between them. This is worth stating plainly
rather than glossing over: **a background thread inside the Streamlit
process is not a real answer to "independent of the dashboard," and this
design does not use one.**

### Options actually considered

| Option | Feasible on Streamlit Community Cloud (free)? | Verdict |
|---|---|---|
| Background thread inside `app.py` | No — dies with the container, no cross-instance coordination, restarts on every redeploy/sleep cycle. | **Rejected.** Fails the "independent of the dashboard" requirement by construction. |
| A genuinely separate always-on host (a small VM, a Render/Railway background worker, a Raspberry Pi) running `while True: sleep(...); run_cycle()` | Technically feasible, but requires standing up and paying for/maintaining infrastructure **outside** Streamlit Cloud entirely — a second deployment target with its own uptime, secrets, and failure modes. | **Feasible, but the most operationally expensive option** for a project whose stated deployment target is Streamlit Community Cloud specifically. Kept as a documented fallback if the project ever moves off the free tier (§7). |
| Supabase's own `pg_cron` extension triggering something | `pg_cron` schedules SQL/Postgres functions or webhook calls, not arbitrary Python — this project's whole physics stack is Python, so `pg_cron` would only ever be usable to *trigger* an external call, not *run* a cycle itself. | **Rejected as the runner.** Could theoretically fire a webhook to something else, but that something else still needs to be one of the other options, so it adds a layer without removing the real question. |
| **A lightweight external scheduler triggering `SimulationEngine.run_cycle()` on a real interval** — concretely, a **GitHub Actions scheduled workflow** (`on: schedule`, a `cron` expression) running a new headless script | Yes. GitHub Actions is free infrastructure this project's own repo already has access to, requires no new hosting account, and is explicitly decoupled from whether Streamlit Cloud's container is awake, asleep, or mid-redeploy. | **Chosen.** |

### The chosen design

A new script, `scripts/run_continuous_cycle.py` (not yet written — this is
the spec), following the **exact existing pattern** of
`scripts/migrate_vendor_quotes_to_supabase.py` (`sys.path.insert(...)`,
`from python import ...`, a `main()` runnable standalone, no Streamlit
import required to execute). Each invocation:

1. Rehydrates the last persisted `SharedPlantState` from Supabase (§3).
2. Applies any pending operator setpoint changes and measurement
   promotions (§5, §6).
3. Calls `engine.run_cycle(now=<real UTC timestamp>)` **exactly once**.
4. Persists the new published snapshot back to Supabase (§3).
5. Exits. The process does not stay resident — it is triggered, it runs
   for a few seconds, it stops. This matches the task's own "lightweight
   external scheduler... on a real interval" framing precisely: GitHub
   Actions is a **trigger**, not a **daemon**, and that is sufficient here
   because a steady-state cycle has no reason to be a long-running process
   (§2).

A new workflow file, `.github/workflows/continuous_cycle.yml` (not yet
written):

```yaml
on:
  schedule:
    - cron: "0 * * * *"   # once per real hour — see §2 for why this exact cadence
  workflow_dispatch: {}    # manual "run it now" button in the GitHub UI, for testing
```

**Two honest, documented GitHub Actions limitations, stated now rather than
discovered later:**

- Scheduled workflows are **not** guaranteed to fire at exactly the top of
  the hour — GitHub's own documentation states scheduled runs can be
  delayed, sometimes by several minutes, during periods of high platform
  load, and a run can occasionally be skipped. For an hourly steady-state
  tick this jitter is immaterial (§2's own honest framing already treats
  "one tick ≈ one hour," not "one tick ≈ exactly :00"), but it would matter
  if a much tighter cadence were ever chosen.
- GitHub **automatically disables** a scheduled workflow after 60 days of
  no repository activity (any commit/PR/etc. counts, not just this
  workflow running). For an actively-developed repo this is a non-issue;
  it is flagged here so a long quiet period doesn't silently stop the
  runtime without anyone noticing — worth an occasional check, not a
  reason to add an artificial keep-alive commit.

---

## 2. What "continuous" means for a steady-state model

This project's own standing, honest limitation (stated in
`ga001_gasifier_model.py` and repeated throughout) is that every model is a
**steady-state snapshot**: given a set of inputs, it solves the same
algebraic/stoichiometric/equilibrium equations to a converged answer, with
no ramping, no thermal inertia, no startup/shutdown transient, and no
memory of "how it got here" beyond whatever a small number of models
explicitly, deliberately track as an accumulating quantity via
`lagged_depends_on` (HB-013 H₂ storage level, EU-010 battery SOC, FE-001
hopper inventory — the ones that already use
`hb_wgs_psa_storage_chain.ASSUMED_HOURS_PER_CYCLE`). **This design does not
change that, and does not claim to.** "Continuous" here means exactly one
thing: **the same steady-state equations get re-solved, on a real
wall-clock interval, with the accumulating quantities correctly carried
forward hour-over-hour** — not that the underlying physics becomes
transient/dynamic.

### What one tick means, concretely

`ASSUMED_HOURS_PER_CYCLE = 1.0` already exists in
`hb_wgs_psa_storage_chain.py` and already defines, for every
accumulation-style model, "one `run_cycle()` = one real hour" — it is used,
unmodified per this design's own constraint, by HB-013's storage-level
update, FE-001's hopper-inventory update, and EU-010's battery-SOC update.
**The continuous runtime's own tick interval is therefore not a free
choice — it must be exactly 1 hour, to keep matching what those three
models already, silently, assume.** Any other real-world tick interval
(say, once every 10 minutes) would make their own accumulation math wrong
without any code change ever making that wrongness visible — inventory
would appear to grow/drain six times too fast relative to the real elapsed
time between ticks. Choosing `cron: "0 * * * *"` (§1) is not an arbitrary
scheduling choice; it is the one interval that keeps every existing
accumulation model correct, unmodified, for free.

(An earlier open item already on this project's own list —
`docs/master_open_questions.md`'s "ASSUMED_HOURS_PER_CYCLE mapping...a
control/automation engineer should set the real intended PLC
scan-to-digital-twin-cycle mapping once the actual control architecture is
designed" — is the longer-term version of this same question. This design
does not resolve that; it adopts the value already in the code, honestly,
as the only choice consistent with not touching the models.)

### What does NOT carry over between ticks

Every non-accumulating value (flows, compositions, temperatures,
pressures, conversions, efficiencies) is **recomputed from scratch each
tick** from whatever inputs are live at that moment — it has no "previous
value" influence at all beyond what an explicit `lagged_depends_on` edge
declares. Two consecutive hourly snapshots can differ only because (a) an
operator setpoint changed (§5), (b) a promoted measurement's live reading
changed (§6), or (c) one of the three accumulating quantities crossed a
threshold that changes which branch a model takes (e.g. HB-013's storage
level hitting a clamp). There is deliberately no interpolation, no
ramp-limiting, and no claim that the plant "was doing something" between
two published hours — only that the steady-state equations were evaluated
twice, an hour apart, with three specific numbers carried forward.

### The existing 5-cycle dashboard warm-up is a separate, still-valid thing

`tab1_integration.build_live_snapshot(n_cycles=5)`'s own synthetic
5-minute-apart bootstrap remains exactly what it is today — a fast,
self-contained way to get the three accumulating quantities past their
"cycle 1, no history yet" bootstrap default so a demo/offline view of Tab 1
isn't showing a degenerate first-tick state. It is **not** replaced by this
design; §4 proposes it becomes a documented fallback (used when the
persisted store is empty or unreachable), not the live path once the
persisted store exists.

---

## 3. The persistent store

**Reused, not reinvented**, per the task's own instruction: the same
Supabase project already holding `vendor_quotes`, `assumption_
confirmations`, `digital_twin_cycle_log` (AI-011), and
`measurement_promotions`, accessed through the same, already-proven
`vendor_log._get_client()` / `_get_secret()` pattern every one of those
tables already uses. No new persistence technology, no new client library.

### What already exists and is reused as-is

`digital_twin_cycle_log` (`data/supabase_schema.sql`, AI-011's table) is
**already** a real, append-only, per-cycle time-series log — it is written
every cycle by `ai_automation_layer.get_ai011_logging_status()`, which is
already registered as part of `register_ai_layer(engine)` and therefore
already runs inside every `run_cycle()` this design calls. **Once the
continuous runtime is the thing calling `run_cycle()` on a real hourly
schedule, this table automatically becomes the real KPI-level history —
with zero new code.** Today it only fills up when a viewer happens to have
Tab 1 open and the 60-second cache expires, so its row cadence is
accidental (however often a session re-renders); under this design its
cadence becomes exactly hourly and meaningful.

### What is genuinely missing today, and needs a new table

Nothing today persists the **full** Shared Plant State (all ~130 registered
engine keys — one row per `register_model()` call across every phase, not
just AI-011's 4 headline numbers) anywhere durable. This is the real gap
this design fills:

```sql
-- plant_state_current: the latest published Shared Plant State, one row
-- per (equipment_id, category) engine key, upserted every cycle. This is
-- a literal, structural mirror of shared_plant_state.py's own
-- SharedPlantState._published dict -- {(equipment_id, category): entry},
-- not a new shape invented for this table. `entry` is stored verbatim as
-- shared_plant_state.py already produces it (value/unit/status/source/
-- validation_basis/confidence_note/cycle/timestamp/missing_reason) --
-- supabase-py accepts a plain Python dict for a jsonb column directly, no
-- new serialization code needed beyond the existing _native() numpy-safety
-- helper tab1_integration.py already has for exactly this reason.
create table if not exists plant_state_current (
    id            bigint generated always as identity primary key,
    equipment_id  text not null,
    category      text not null,
    entry         jsonb not null,
    cycle         bigint not null,
    published_at  timestamptz not null,
    updated_at    timestamptz not null default now(),
    unique (equipment_id, category)
);
create index if not exists plant_state_current_key_idx
    on plant_state_current (equipment_id, category);

-- RLS + grants, same pattern as every existing table in this project.
alter table plant_state_current enable row level security;
create policy "plant_state_current_select_all" on plant_state_current
    for select using (true);
create policy "plant_state_current_upsert_all" on plant_state_current
    for insert with check (true);
create policy "plant_state_current_update_all" on plant_state_current
    for update using (true) with check (true);
grant select, insert, update on plant_state_current to anon;
grant usage, select on sequence plant_state_current_id_seq to anon;
```

`{(row.equipment_id, row.category): row.entry for row in <all rows>}` is
then, by construction, exactly what `SharedPlantState.get_snapshot()`
already returns — the dashboard's read side (§4) needs no new logic to
interpret it beyond that one reconstruction.

### What is deliberately NOT built now

A full-fidelity historical archive (every key's own entry, every hour,
forever — `plant_state_history` in the task's own phrasing) is **not**
proposed as part of this design's first cut. Reasoning made explicit,
not hidden, per §7: `plant_state_current` is bounded (~130 rows, upserted,
never grows) and `digital_twin_cycle_log` is small even after years
(4 numeric columns × 8,760 rows/year ≈ trivial), but a full JSONB snapshot
of every key every hour would genuinely grow (roughly 130 keys × ~1–2 KB
each × 8,760 hours/year — plausibly hundreds of MB/year), which is worth
respecting rather than committing to before it's needed. **Recommendation:
ship without it; add it later, with an explicit retention cap (e.g. a
scheduled prune of rows older than N days), only if a real need for
per-key historical trend charts (beyond the 4 AI-011 headline numbers)
shows up.** This is flagged here so the decision is visible now, not
discovered as a storage bill later.

### Rehydration: existing public API only, no new method

The critical continuity requirement: a fresh `SharedPlantState` built by
each new GitHub Actions run has never published anything, so on its first
`run_cycle()`, every `lagged_depends_on` read (HB-013 storage, EU-010 SOC,
FE-001 inventory) would see Missing and every model would fall back to its
own "cycle 1" bootstrap default — **every single hour**, which would make
those three quantities perpetually reset instead of genuinely
accumulating. `plant_state_current` exists specifically to prevent this.

The rehydration step uses **only the existing public write API**
(`new_writer_handle`, `begin_cycle`, `set_entry`, `publish_cycle`) —
no new method is added to `shared_plant_state.py`:

```
state = SharedPlantState()
boot_handle = state.new_writer_handle()
state.begin_cycle(boot_handle, now=<real UTC now>)
for (equipment_id, category), entry in <rows from plant_state_current>:
    state.set_entry(
        boot_handle, (equipment_id, category),
        value=entry["value"], unit=entry["unit"], status=entry["status"],
        model=entry["source"]["model"], inputs=entry["source"]["inputs"],
        validation_basis=entry["validation_basis"],
        confidence_note=entry["confidence_note"],
        missing_reason=entry["missing_reason"],
    )
state.publish_cycle(boot_handle)   # boot_handle is now spent

engine = SimulationEngine(state)   # issues its OWN fresh handle,
                                    # correctly invalidating boot_handle --
                                    # the SAME single-writer discipline
                                    # already enforces this, unmodified.
```

**One honest, explicitly-accepted trade-off**, not swept under the rug:
`SharedPlantState._published_cycle` (an internal bookkeeping counter,
used only for same-run staging/publish sequencing) restarts low
(1, then 2) every time a new GitHub Actions run starts a fresh process —
it is **not** the same thing as "how many real hours the plant has been
running," and this design does not try to make it one. The real,
ever-growing, meaningful count already lives durably in
`digital_twin_cycle_log`'s own row history (its `logged_at` timestamps, or
simply `count(*)`) — that is the number worth showing a viewer as "N hours
of continuous operation," not `SharedPlantState`'s own per-process
counter. Keeping these two concerns separate is exactly why no change to
`shared_plant_state.py` is needed at all.

---

## 4. The dashboard as a pure observer

### The change, precisely scoped

`app.py`'s existing `_tab1_integration_snapshot()` (currently:
`@st.cache_data(ttl=60)` wrapping a call to
`tab1_integration.build_live_snapshot()`, which **runs** the whole engine)
is replaced by a function with the **same cached-call shape** but a
different body: **read** `plant_state_current` from Supabase and
reconstruct the snapshot dict, instead of running anything.
`render_tab1_section(snapshot)` itself — the actual rendering code — needs
**zero changes**, because it already only consumes a plain snapshot dict
(`tab1_integration.py`'s own module docstring: "`compute_tab1_kpis(snapshot)`
is a PURE function of that snapshot"); it has never cared whether that
dict was just computed or just read back.

```python
@st.cache_data(ttl=300, show_spinner="Reading the latest published plant state...")
def _tab1_integration_snapshot():
    rows = vendor_log._get_client().table("plant_state_current").select("*").execute().data
    if not rows:
        # Fallback: the persisted store is empty (first-ever deploy, before
        # the runtime has ticked even once) -- degrade to today's own
        # in-process bootstrap rather than showing nothing.
        snap, _, _ = tab1_integration.build_live_snapshot()
        return snap
    return {(r["equipment_id"], r["category"]): r["entry"] for r in rows}
```

### Detecting a new cycle's data has arrived: cache TTL + an explicit manual refresh, not auto-polling

Streamlit's real constraints, stated honestly: there is no built-in
"push me a browser update when a Postgres row changes" primitive in plain
Streamlit, and true auto-refresh needs either a third-party component
(`streamlit-autorefresh`, not currently a dependency of this project) or a
client-side JS trick — either way, it forces **every open browser tab** to
keep polling on a timer even when nobody is looking, which spends Streamlit
Community Cloud's own limited shared compute for a check that can only
possibly find something new once an hour (§2). That cost is
disproportionate to the value here.

**Chosen: keep the exact idiom already used for this same cached function
today** (`@st.cache_data(ttl=...)`), just re-pointed at a store-read
instead of an engine-run, with the TTL loosened from 60s to something
generous relative to the real hourly cadence (300s / 5 minutes is proposed
— tight enough that an impatient viewer rarely waits long, loose enough
that repeat viewers aren't all hammering Supabase every page interaction),
**plus** an explicit "🔄 Refresh now" button that calls
`_tab1_integration_snapshot.clear()` to force an immediate re-read on
demand. This adds no new dependency, matches an idiom this codebase
already trusts, and is honest about the actual data cadence rather than
implying a live/real-time feel the underlying hourly tick doesn't have.

**A visible freshness indicator is part of this design, not an
afterthought**: the rendered snapshot's own `published_at` (already a real
field on every entry) is surfaced prominently, e.g. *"Plant state as of
2026-09-04 14:00 UTC (published by the continuous runtime; next tick
≈15:00 UTC)"* — so nobody ever mistakes "the last hourly number" for
"right now," consistent with this project's own no-false-precision,
no-overclaiming standard used throughout.

---

## 5. Operator-initiated changes

### What exists today, checked directly rather than assumed

There is currently **no** operator-adjustable setpoint wired into Tab 1's
own engine-driven path at all — `_tab1_integration_snapshot()` calls
`build_live_snapshot()` with no `overrides`, every time. The `overrides=`
mechanism exists and is exercised, but only inside self-tests (the EU-008
dual-scenario ER=0.25-vs-0.35 comparison). The sliders that DO exist in
`app.py` (HTS/LTS temperature, PSA pressures, Monte Carlo run count, etc.)
belong to a separate, older, pre-Digital-Twin-Engine part of the app that
calls `kinetics.py`/`psa.py`/`chp.py` directly and was never wired through
`SimulationEngine`/`SharedPlantState` at all. So this section is not
"preserve an existing wiring" — it is a clean, from-scratch specification
for how a **future** operator-setpoint control on Tab 1 should reach a
process that isn't the one rendering the page.

### The mechanism: reuse `promote_to_measurement()`, unmodified, for a second purpose

`_topological_order()`'s own existing docstring already names exactly this
case: *"a same-cycle dependency on a key nobody registered a model for is
not itself an error here — it may be an external input (an operator
setpoint, a design-basis constant) that simply already exists in the
published state."* And `SimulationEngine.promote_to_measurement(key,
reader_fn)` is already general enough to swap **any** registered key's
function for a new one, without forcing `status=Measured` (§6 confirms
this directly) — it is not, despite its name, exclusively a
sensor-promotion mechanism; it is a generic "swap which function computes
this key" primitive that Phase 6 happened to be built to serve first.

**Design:**

1. A new, small Supabase table, `plant_operator_setpoints`
   (upsert-on-key, same pattern as `assumption_confirmations`/
   `measurement_promotions`):

   ```sql
   create table if not exists plant_operator_setpoints (
       id            bigint generated always as identity primary key,
       engine_key    text not null unique,  -- e.g. 'GA-001-INPUT|equivalence_ratio'
       value         jsonb not null,
       requested_by  text default '',
       requested_at  timestamptz not null default now(),
       applied_at    timestamptz            -- null until the runtime has picked it up
   );
   -- RLS + grants: same select/insert/update pattern as every table above.
   ```

2. Tab 1 gains a new, explicitly-labeled operator-input widget (e.g. an ER
   number input) with its own **"Apply setpoint"** button — deliberately
   not a live-dragging slider that writes on every pixel of movement, the
   same discipline this project already applies to its Monte Carlo
   `st.button` ("Run") rather than firing on every slider tick. Clicking it
   upserts one row into `plant_operator_setpoints`.

3. A new, tiny reader-factory function, mirroring
   `measurement_promotion.make_synthetic_measurement_reader()`'s own
   existing shape exactly (same return-dict contract, different status):

   ```python
   def make_operator_setpoint_reader(value, source_note):
       def reader_fn(get_input):
           return {
               "value": value, "status": ps.STATUS_ASSUMED,
               "model": None, "inputs": [],
               "validation_basis": ps.VALIDATION_NA,
               "confidence_note": source_note,
           }
       return reader_fn
   ```

4. At the **start** of each continuous-runtime tick (§1 step 2), the driver
   script reads every row in `plant_operator_setpoints` with
   `applied_at is null`, calls
   `engine.promote_to_measurement(key, make_operator_setpoint_reader(row.value, ...))`
   for each **before** calling `run_cycle()`, and marks the row
   `applied_at = now()`. This is a straight, unmodified reuse of an
   existing, already-tested method — no new engine capability.

This means an operator's setpoint change takes effect on the **next**
scheduled tick (up to ~1 hour later, plus GitHub's own scheduling jitter,
§1) — not instantly. That is stated here as a real, honest consequence of
decoupling the trigger from the dashboard, not hidden: the trade-off for
"runs independent of any Streamlit session" is that a change made in a
browser is no longer instantaneous. If sub-hour responsiveness to operator
input is ever a real requirement, that is a materially different, larger
design question (a genuinely real-time control loop) explicitly out of
scope here.

---

## 6. The sensor/PLC promotion path (Phase 6) is unaffected — confirmed, not assumed

Read `measurement_promotion.py` directly (not recalled) to check this
rather than assert it:

- `record_measurement(engine, key, reader_fn, ...)` takes an `engine`
  object and calls `engine.promote_to_measurement(key, reader_fn)` — it
  has never depended on *how* that `engine` was constructed, what process
  it lives in, or whether a Streamlit session exists. **It plugs into the
  continuous-runtime driver script exactly as it plugs into `app.py`
  today: call it once, on whatever live `SimulationEngine` instance is
  currently in scope, right after that instance is built and before its
  next `run_cycle()`.**
- One real, pre-existing gap this review surfaced (not introduced by this
  design): `record_measurement()`'s own module docstring says the audit
  trail (Supabase's `measurement_promotions` table) "does NOT
  auto-reconnect a real reader on a fresh process... a fresh process still
  needs `record_measurement()` called again" — and **today, nothing in
  `app.py` or `tab1_integration.py` ever calls it**, because
  `build_live_snapshot()` builds a brand-new engine every single render
  and nothing replays promotions into it. So sensor promotion is
  *already*, today, not durable across the dashboard's own repeated engine
  rebuilds — this is a pre-existing property of the current architecture,
  not a regression this design introduces.
- **This design actually fixes that gap as a side effect**, without
  touching `measurement_promotion.py` itself: because the continuous
  runtime rehydrates one real `SharedPlantState`/`SimulationEngine` per
  tick (§3) rather than rebuilding from nothing, the driver script's own
  startup sequence (§5 step 4) is the natural place to also call
  `measurement_promotion.list_promoted_measurements()` and re-apply each
  row's promotion via `engine.promote_to_measurement(...)` with a real
  reader — the exact same "replay durable decisions into live state at
  process start" idiom `app.py` already uses for `confirmation_loop.py`'s
  assumptions (`app.py`'s own existing startup replay, lines ~40 onward).
  **This is additive** (a few lines in the new driver script), calls
  `measurement_promotion.py`'s own existing, unmodified public function,
  and requires no change to that module.

**Conclusion: nothing about `measurement_promotion.py` needs to change.**
It was designed, per its own docstring, around exactly this
"apply once per live engine instance" contract — the continuous runtime is
simply a better-suited caller of that same contract than the dashboard's
own rebuild-every-render pattern ever was.

---

## 7. Resource and cost reality check

| Concern | Assessment |
|---|---|
| **GitHub Actions minutes** | A single `run_cycle()` call (7 phases, no Monte Carlo sampling) is a fundamentally lighter workload than the Monte Carlo runs this project already knows are slow on shared compute (`pinn_kinetics.py`'s own documented caution is about *Streamlit Cloud's* shared CPU specifically, and about 200–2000-sample optimizer runs — not a single steady-state solve). GitHub's own hosted runners are 2-core/~7GB, generally more generous than Streamlit Cloud's own free-tier compute. Estimate, stated as an estimate pending real measurement: well under a minute per run. At 24 runs/day that's comfortably inside even the 2,000 free minutes/month private-repo allowance (public repos get unlimited Actions minutes) — **recommend the first implementation task measure real wall-clock time for one cycle before relying on this for anything tighter than the proposed hourly cadence.** |
| **Supabase storage** | `plant_state_current` is upserted (bounded at ~130 rows, never grows). `digital_twin_cycle_log` is ~4 numeric columns × 8,760 rows/year — trivial even over several years. `plant_operator_setpoints`/`measurement_promotions` are small, upsert-on-key tables. **None of this threatens Supabase's free-tier 500MB cap.** The deferred full-history table (§3) is the one piece that *could*, which is exactly why it's deferred rather than built speculatively. |
| **Supabase free-project auto-pause** | A genuine, existing risk this project already carries: Supabase free-tier projects pause automatically after 7 days with no activity. **This design turns that into a solved problem as a side effect, not something needing separate defense** — an hourly write from the continuous runtime means the project is never idle for more than an hour, so it can never hit the 7-day pause threshold as long as the scheduled workflow is running. Worth stating explicitly since it's a real, positive consequence, not a coincidence to bury. |
| **Streamlit Cloud compute** | *Reduced*, not increased, by this design: today, every viewer whose 60-second cache has expired triggers a full 5-cycle engine run inside the shared Streamlit process; under this design, the dashboard does a single Supabase `select` instead. The compute-heavy work moves entirely off Streamlit Cloud's own shared free tier and onto GitHub Actions' own separate, dedicated-per-run compute. |
| **Compromises worth flagging now** | (1) The hourly cadence is not a free choice (§2) — a shorter interval would need the accumulation models themselves changed, explicitly out of scope. (2) The full per-key history table is deliberately not built yet (§3) — start without it, add it with a retention cap only if a real need appears. (3) A 5-minute dashboard cache TTL (§4) means a viewer can see data up to 5 minutes stale relative to the store, on top of up to ~1 hour of staleness relative to real time (§2/§5) — both are surfaced to the viewer via the freshness indicator, not hidden. |

---

## 8. Migration risk — confirmed, not assumed

Directly checked, rather than inferred from "the models aren't touched
therefore nothing changes":

- **No existing file's source is modified by this design.** Every piece
  proposed above is a **new** file (`scripts/run_continuous_cycle.py`,
  `.github/workflows/continuous_cycle.yml`, two new/extended `.sql` schema
  files) or a **local change inside `app.py`'s own
  `_tab1_integration_snapshot()` function body** (what it does, not its
  cached-call signature or what calls it). `simulation_engine.py`,
  `shared_plant_state.py`, `measurement_promotion.py`, and every equipment
  model file are untouched.
- Every one of this project's existing self-tests runs via each module's
  own `if __name__ == "__main__":` block, calling only functions that
  already exist inside that same module or modules it already imports.
  None of those blocks import `scripts/run_continuous_cycle.py` (it
  doesn't exist yet, and nothing proposed here would need it to), and none
  of them read from or write to `plant_state_current` /
  `plant_operator_setpoints` (new tables no existing code touches).
  **Therefore none of the standing self-tests — `plant_status`,
  `shared_plant_state`, `simulation_engine`, `ga001_gasifier_model`,
  `gc_gas_cleaning_chain`, `hb_wgs_psa_storage_chain`, `hb_remaining_chain`,
  `eu_utilities_chp`, `fe_feed_handling`, `sa_virtual_sensors`,
  `ai_automation_layer`, `tab1_integration`, `measurement_promotion`,
  `design_basis`, `equipment_data_requests`, `equipment_request_routing`
  — can be affected by anything in this design, because none of them
  exercise code this design adds or changes.**
- The one place this design touches something that already runs in
  production is `app.py`'s Tab 1 caching function — and even there, only
  its **body**, not `render_tab1_section()` (unchanged) or the shape of
  what it returns (a snapshot dict, unchanged). This has no existing
  automated self-test today (`app.py` is not one of the modules with an
  `if __name__ == "__main__":` self-test block — it is the Streamlit
  entry point, exercised manually/visually), so there is no existing test
  to break here either; the honest statement is "untested today, and this
  design does not change that," not "covered and confirmed passing."
- New code this design implies (the driver script, the two reader
  factories, the schema) would need its **own** new self-test once
  implemented — not written here, since this is a design-only deliverable
  with no code yet, per the task's own instruction.

---

## Summary of what this design proposes to build (none of it built yet)

1. `data/plant_state_current_schema.sql` — new table (§3).
2. `data/plant_operator_setpoints_schema.sql` — new table (§5).
3. (Optional, minor) an `ALTER TABLE digital_twin_cycle_log` if any
   additional headline columns are wanted later — not required to start.
4. `scripts/run_continuous_cycle.py` — new headless driver script (§1, §3,
   §5, §6), following the existing `scripts/migrate_vendor_quotes_to_
   supabase.py` pattern.
5. `.github/workflows/continuous_cycle.yml` — new scheduled workflow,
   `cron: "0 * * * *"` (§1, §2), with repo secrets `SUPABASE_URL`/
   `SUPABASE_KEY` written to a temporary `.streamlit/secrets.toml` at
   workflow-run time so `vendor_log._get_secret()` needs no code change to
   work headlessly in CI (it already has a non-Streamlit fallback path,
   confirmed by reading it directly — just not one that reads GitHub
   Actions' own env-var-injected secrets, so the workflow supplies them
   via the file path it already checks).
6. A small new reader-factory function,
   `make_operator_setpoint_reader()` (§5), living alongside
   `measurement_promotion.make_synthetic_measurement_reader()`'s own
   pattern (exact module TBD at implementation time — plausibly a new,
   small module rather than crowding `measurement_promotion.py`, since it
   serves a conceptually different purpose despite the mechanical
   similarity).
7. A local change to `app.py`'s `_tab1_integration_snapshot()` function
   body (§4) — read the store instead of running the engine, with a
   graceful fallback to today's own in-process bootstrap if the store is
   empty — plus a new "🔄 Refresh now" button and a freshness-timestamp
   display.

**Open decisions for review, not yet settled by this document:**

- Whether `plant_operator_setpoints` should support more than the one
  illustrative example (equivalence ratio) from day one, or start
  minimal and grow per real need.
- Whether the reader-factory in item 6 belongs in a brand-new module (e.g.
  `python/continuous_runtime.py`) or is small enough to live in the new
  driver script directly.
- The exact dashboard TTL value (300s proposed in §4) — a judgment call,
  not derived from a hard constraint.

Stopping here, per the task's own instruction — no implementation until
this design is reviewed.
