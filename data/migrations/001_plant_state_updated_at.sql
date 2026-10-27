-- 001_plant_state_updated_at.sql  (audit fix C2, docs/audit_2026-10-27.md finding 2)
-- NOT RUN BY CLAUDE. Run once in the Supabase SQL Editor.
--
-- Problem: plant_state_current.updated_at has "default now()", which only
-- applies at INSERT. Every hourly upsert after the first one leaves it at its
-- original value (audit: all 116 rows = 2026-09-04T14:09:38Z).
--
-- Fix: a BEFORE UPDATE trigger that stamps updated_at = now() on every update.
--
-- NOTE: published_at (a column AND inside each entry) remains the AUTHORITATIVE
-- freshness field -- it is the time the simulated cycle was computed. updated_at
-- is only "when the row was last written". The driver also sets updated_at
-- explicitly (scripts/run_continuous_cycle.py), so this trigger is belt and braces.
--
-- UNDO:
--   drop trigger if exists plant_state_current_set_updated_at on plant_state_current;
--   drop function if exists set_updated_at_now();

create or replace function set_updated_at_now()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists plant_state_current_set_updated_at on plant_state_current;
create trigger plant_state_current_set_updated_at
    before update on plant_state_current
    for each row
    execute function set_updated_at_now();
