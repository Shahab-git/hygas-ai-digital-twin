-- measurement_promotions table for the HYGAS-AI Digital Twin's Phase 6
-- ("Real Sensor/PLC Migration Groundwork") promotion mechanism.
-- Run this once in the Supabase SQL Editor (same project as vendor_quotes
-- and assumption_confirmations), for whichever Supabase project you point
-- this app at.
--
-- Durably records the promotion DECISION only (which engine key is now
-- measurement-backed, by what reader description, since when) -- NOT the
-- constantly-changing live VALUE itself, which is inherently cyclical
-- (recomputed/re-read every cycle by the Central Simulation Engine) and
-- has no business living in a slowly-changing Supabase row. See
-- python/measurement_promotion.py's own module docstring for the full
-- reasoning (the same split confirmation_loop.py already uses for the
-- static registry, applied here to the live cyclical plant state instead).
--
-- Upserted on engine_key (like assumption_confirmations, not insert-only
-- like vendor_quotes) -- a key's own promotion metadata can be updated
-- (e.g. a new reader description) without creating duplicate rows.

create table if not exists measurement_promotions (
    id                  bigint generated always as identity primary key,
    engine_key          text not null unique,  -- e.g. 'SA-001|Reading' -- see
                                                 -- measurement_promotion.py's own _key_str()
    source_description  text default '',
    promoted_at          timestamptz not null default now()
);

create index if not exists measurement_promotions_key_idx on measurement_promotions (engine_key);

-- Row Level Security: the app reads all rows, and inserts/updates (via
-- upsert on engine_key) -- never deletes.
alter table measurement_promotions enable row level security;

create policy "measurement_promotions_select_all"
    on measurement_promotions for select
    using (true);

create policy "measurement_promotions_insert_all"
    on measurement_promotions for insert
    with check (true);

create policy "measurement_promotions_update_all"
    on measurement_promotions for update
    using (true)
    with check (true);

-- Table-level grants -- RLS policies above do NOT substitute for these
-- (the exact gotcha vendor_quotes's own schema file already documents).
grant select, insert, update on measurement_promotions to anon;
grant usage, select on sequence measurement_promotions_id_seq to anon;
