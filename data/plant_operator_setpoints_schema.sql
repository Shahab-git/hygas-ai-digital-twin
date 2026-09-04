-- plant_operator_setpoints table for the HYGAS-AI continuous simulation
-- runtime (docs/continuous_runtime_design.md, approved design, section 5).
-- Run this once in the Supabase SQL Editor (same project as vendor_quotes,
-- assumption_confirmations, digital_twin_cycle_log, measurement_promotions,
-- and plant_state_current), for whichever Supabase project you point this
-- app at.
--
-- Durably records a pending (or already-applied) operator setpoint change
-- -- e.g. 'GA-001-INPUT|equivalence_ratio' -- picked up and applied by the
-- continuous runtime's own driver script (scripts/run_continuous_cycle.py)
-- at the START of each tick, via SimulationEngine.promote_to_measurement()
-- (the SAME existing, unmodified method Phase 6's measurement_promotion.py
-- already uses -- reused for a second purpose here, not a new engine
-- capability). Upserted on engine_key (like assumption_confirmations and
-- measurement_promotions, not insert-only like vendor_quotes): a fresh
-- setpoint request for the same key replaces the still-pending one, rather
-- than piling up duplicate rows.
--
-- No UI writer exists yet as of this task -- that's a separate, later
-- piece of work (a Tab 1 operator-input widget). This table and the
-- driver script's own consumption of it are real and functional the
-- moment any writer inserts a row with applied_at null.

create table if not exists plant_operator_setpoints (
    id            bigint generated always as identity primary key,
    engine_key    text not null unique,  -- e.g. 'GA-001-INPUT|equivalence_ratio'
    value         jsonb not null,
    requested_by  text default '',
    requested_at  timestamptz not null default now(),
    applied_at    timestamptz            -- null until the runtime has picked it up
);

create index if not exists plant_operator_setpoints_pending_idx
    on plant_operator_setpoints (applied_at);

-- Row Level Security: the app reads all rows, and inserts/updates (via
-- upsert on engine_key, and the driver script's own applied_at stamp) --
-- never deletes. Same pattern as every existing table in this project.
alter table plant_operator_setpoints enable row level security;

create policy "plant_operator_setpoints_select_all"
    on plant_operator_setpoints for select
    using (true);

create policy "plant_operator_setpoints_upsert_all"
    on plant_operator_setpoints for insert
    with check (true);

create policy "plant_operator_setpoints_update_all"
    on plant_operator_setpoints for update
    using (true) with check (true);

-- Table-level grants -- RLS policies above do NOT substitute for these
-- (the exact gotcha vendor_quotes's own schema file already documents).
grant select, insert, update on plant_operator_setpoints to anon;
grant usage, select on sequence plant_operator_setpoints_id_seq to anon;
