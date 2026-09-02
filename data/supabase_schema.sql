-- vendor_quotes table for the HYGAS-AI vendor-sourcing agent.
-- Run this once in the Supabase SQL Editor (Project -> SQL Editor -> New query)
-- for whichever Supabase project you point this app at.
--
-- price is NUMERIC, not TEXT: the JSON schema it replaces (data/vendor_quotes.json)
-- stored price as a float (e.g. 42500.0), and python/vendor_log.py always
-- coerces it with float(price) before writing, so numeric matches actual usage.

create table if not exists vendor_quotes (
    id            bigint generated always as identity primary key,
    equipment_tag text not null,        -- e.g. 'FE-001' — the registry item id
    vendor_name   text not null,
    price         numeric not null,
    date          date not null,
    notes         text default '',
    created_at    timestamptz not null default now()
);

create index if not exists vendor_quotes_equipment_tag_idx on vendor_quotes (equipment_tag);

-- Row Level Security: the app only ever needs to read all rows and insert new
-- ones (it never updates or deletes a logged quote), so that's all we grant.
alter table vendor_quotes enable row level security;

create policy "vendor_quotes_select_all"
    on vendor_quotes for select
    using (true);

create policy "vendor_quotes_insert_all"
    on vendor_quotes for insert
    with check (true);

-- RLS policies alone aren't enough — Postgres also requires table-level
-- grants for the role the anon/publishable key authenticates as.
grant select, insert on vendor_quotes to anon;
grant usage, select on sequence vendor_quotes_id_seq to anon;

-- digital_twin_cycle_log table for AI-011 (Time-Series Database), Phase 4 --
-- python/ai_automation_layer.py's own get_ai011_logging_status(). Same
-- pattern as vendor_quotes above, reusing python/vendor_log.py's own
-- Supabase client. Run this once in the same Supabase project's SQL Editor.

create table if not exists digital_twin_cycle_log (
    id               bigint generated always as identity primary key,
    logged_at        timestamptz not null,
    ga_dry_flow_nm3_h numeric,
    gc_h2_pct        numeric,
    hb_storage_kg    numeric,
    eu_net_kw        numeric,
    created_at       timestamptz not null default now()
);

create index if not exists digital_twin_cycle_log_logged_at_idx on digital_twin_cycle_log (logged_at);

alter table digital_twin_cycle_log enable row level security;

create policy "digital_twin_cycle_log_select_all"
    on digital_twin_cycle_log for select
    using (true);

create policy "digital_twin_cycle_log_insert_all"
    on digital_twin_cycle_log for insert
    with check (true);

grant select, insert on digital_twin_cycle_log to anon;
grant usage, select on sequence digital_twin_cycle_log_id_seq to anon;
