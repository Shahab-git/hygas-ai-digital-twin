-- plant_state_current table for the HYGAS-AI continuous simulation runtime
-- (docs/continuous_runtime_design.md, approved design, section 3).
-- Run this once in the Supabase SQL Editor (same project as vendor_quotes,
-- assumption_confirmations, digital_twin_cycle_log, and
-- measurement_promotions), for whichever Supabase project you point this
-- app at.
--
-- The latest published Shared Plant State, one row per (equipment_id,
-- category) engine key, upserted every cycle -- a literal, structural
-- mirror of shared_plant_state.py's own SharedPlantState._published dict
-- ({(equipment_id, category): entry}), not a new shape invented for this
-- table. `entry` is stored verbatim as shared_plant_state.py already
-- produces it (value/unit/status/source/validation_basis/confidence_note/
-- cycle/timestamp/missing_reason) -- supabase-py accepts a plain Python
-- dict for a jsonb column directly, no new serialization code needed
-- beyond the existing _native() numpy-safety helper tab1_integration.py
-- already has for exactly this reason.
--
-- {(row.equipment_id, row.category): row.entry for row in <all rows>} is
-- then, by construction, exactly what SharedPlantState.get_snapshot()
-- already returns.

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

-- Row Level Security: the app reads all rows, and inserts/updates (via
-- upsert on equipment_id+category) as each cycle publishes -- never
-- deletes. Same pattern as every existing table in this project.
alter table plant_state_current enable row level security;

create policy "plant_state_current_select_all"
    on plant_state_current for select
    using (true);

create policy "plant_state_current_upsert_all"
    on plant_state_current for insert
    with check (true);

create policy "plant_state_current_update_all"
    on plant_state_current for update
    using (true) with check (true);

-- Table-level grants -- RLS policies above do NOT substitute for these
-- (the exact gotcha vendor_quotes's own schema file already documents).
grant select, insert, update on plant_state_current to anon;
grant usage, select on sequence plant_state_current_id_seq to anon;
