-- assumption_confirmations table for the HYGAS-AI confirmation-loop agent.
-- Run this once in the Supabase SQL Editor (same project as vendor_quotes),
-- for whichever Supabase project you point this app at.
--
-- Includes the anon-role GRANT statements up front this time -- RLS
-- policies alone do NOT grant table-level privileges in Postgres; that
-- was the exact gotcha from the vendor_quotes setup (PGRST205 /
-- "permission denied for table" until the GRANTs were added separately).
--
-- Unlike vendor_quotes (insert-only), this table needs UPDATE too: a
-- row's status moves not_yet_asked -> awaiting_response -> confirmed
-- over time, upserted on assumption_key rather than always inserting a
-- new row.

create table if not exists assumption_confirmations (
    id                    bigint generated always as identity primary key,
    assumption_key        text not null unique,  -- matches uncertainty.ASSUMPTIONS' own dict keys
    status                text not null default 'not_yet_asked'
                          check (status in ('not_yet_asked', 'awaiting_response', 'confirmed')),
    confirmed_value       numeric,
    confirmed_range_low   numeric,
    confirmed_range_high  numeric,
    notes                 text default '',
    updated_at            timestamptz not null default now()
);

create index if not exists assumption_confirmations_key_idx on assumption_confirmations (assumption_key);

-- Row Level Security: the app reads all rows, and inserts/updates (via
-- upsert on assumption_key) as status changes -- never deletes.
alter table assumption_confirmations enable row level security;

create policy "assumption_confirmations_select_all"
    on assumption_confirmations for select
    using (true);

create policy "assumption_confirmations_insert_all"
    on assumption_confirmations for insert
    with check (true);

create policy "assumption_confirmations_update_all"
    on assumption_confirmations for update
    using (true)
    with check (true);

-- Table-level grants -- RLS policies above do NOT substitute for these.
grant select, insert, update on assumption_confirmations to anon;
grant usage, select on sequence assumption_confirmations_id_seq to anon;
