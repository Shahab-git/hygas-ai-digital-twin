-- 002_digital_twin_cycle_log.sql  (audit fix D1, docs/audit_2026-10-27.md finding 4)
-- NOT RUN BY CLAUDE. Run once in the Supabase SQL Editor.
--
-- Creates ONLY the digital_twin_cycle_log table (copied from
-- data/supabase_schema.sql, the AI-011 time-series log). Idempotent.
--
-- Security (audit finding 20): RLS is enabled and the anon role gets SELECT only
-- (the app's reachability probe and any history chart read it). There is NO anon
-- INSERT/UPDATE policy and no anon write grant. Rows are written by the
-- continuous runtime; a key with the service_role (which bypasses RLS) is
-- required for that -- see data/migrations/004_tighten_rls.sql for the order in
-- which to switch the CI key. Until CI uses a service-role key, AI-011's
-- insert will be rejected by RLS and shown as "logged: False, error ..."; that
-- is honest, not silent.
-- (Temporary shortcut, NOT recommended: to log before the key is switched, run
--   create policy "digital_twin_cycle_log_insert_anon_TEMP" on digital_twin_cycle_log
--     for insert to anon with check (true);
--   grant insert on digital_twin_cycle_log to anon;
--   grant usage, select on sequence digital_twin_cycle_log_id_seq to anon;
--  and drop it again afterwards.)
--
-- UNDO: drop table if exists digital_twin_cycle_log;

create table if not exists digital_twin_cycle_log (
    id               bigint generated always as identity primary key,
    logged_at        timestamptz not null,
    ga_dry_flow_nm3_h numeric,
    gc_h2_pct        numeric,
    hb_storage_kg    numeric,
    eu_net_kw        numeric,
    created_at       timestamptz not null default now()
);

create index if not exists digital_twin_cycle_log_logged_at_idx
    on digital_twin_cycle_log (logged_at);

alter table digital_twin_cycle_log enable row level security;

drop policy if exists "digital_twin_cycle_log_select_all" on digital_twin_cycle_log;
create policy "digital_twin_cycle_log_select_all"
    on digital_twin_cycle_log for select
    using (true);

grant select on digital_twin_cycle_log to anon;
