-- 005_service_role_grants.sql
-- ALREADY RUN by the owner in the Supabase SQL Editor on 2026-10-28. NOT RUN BY CLAUDE.
-- This file records what was run, so the database can be rebuilt from data/migrations/. Re-running it is harmless
-- (GRANT is idempotent).
--
-- Why: the service_role key bypasses row-level security (RLS) -- no policy is needed -- but it still needs ordinary
-- table privileges (GRANT). 004_tighten_rls.sql removed the anon write grants; the continuous runtime now writes with
-- SUPABASE_SERVICE_KEY, so it needs exactly the grants below and nothing more (no delete, no truncate, no DDL).
--
--   plant_state_current          select, insert, update   (the driver reads the stored state and upserts it)
--   plant_operator_setpoints     select, update           (reads pending setpoints, marks them applied)
--   measurement_promotions       select                   (read-only)
--   assumption_confirmations     select                   (read-only)
--   digital_twin_cycle_log       select, insert           (AI-011 appends one row per cycle)
--   digital_twin_cycle_log_id_seq  usage, select          (the identity column's sequence, needed by the insert)
--
-- UNDO (removes exactly what this file grants):
-- revoke usage, select on sequence public.digital_twin_cycle_log_id_seq from service_role;
-- revoke select, insert on public.digital_twin_cycle_log from service_role;
-- revoke select on public.assumption_confirmations from service_role;
-- revoke select on public.measurement_promotions from service_role;
-- revoke select, update on public.plant_operator_setpoints from service_role;
-- revoke select, insert, update on public.plant_state_current from service_role;
-- revoke usage on schema public from service_role;
-- (Revoking the schema usage as well would also break anything else that uses service_role; skip that line if unsure.)

grant usage on schema public to service_role;
grant select, insert, update on public.plant_state_current to service_role;
grant select, update on public.plant_operator_setpoints to service_role;
grant select on public.measurement_promotions to service_role;
grant select on public.assumption_confirmations to service_role;
grant select, insert on public.digital_twin_cycle_log to service_role;
grant usage, select on sequence public.digital_twin_cycle_log_id_seq to service_role;
