-- 004_tighten_rls.sql  (audit fix E4, docs/audit_2026-10-27.md finding 20)
-- NOT RUN BY CLAUDE. DO NOT RUN BEFORE THE PREREQUISITES BELOW.
--
-- What the code uses (checked without printing any key):
--   * The local .streamlit/secrets.toml SUPABASE_KEY is a legacy JWT whose role
--     claim is 'anon'. The workflow writes the SAME repo secret into the same
--     file, so the continuous runtime most likely writes as ANON too (the
--     workflow header says the CI secret equals the local value; the secret itself
--     is not readable, so that equality is NOT VERIFIED).
--   * The Streamlit app writes from the UI in exactly two places:
--     vendor_log.log_quote() (INSERT into vendor_quotes) and
--     confirmation_loop.mark_asked()/record_confirmation() (upsert = INSERT/UPDATE
--     on assumption_confirmations). It never writes plant_state_current,
--     measurement_promotions, plant_operator_setpoints or digital_twin_cycle_log.
--   * The continuous runtime writes plant_state_current and digital_twin_cycle_log
--     (and marks operator setpoints applied).
--
-- PREREQUISITES (in this order):
--   1. Supabase dashboard -> Project Settings -> API: copy the service_role key.
--   2. GitHub repo -> Settings -> Secrets and variables -> Actions: add a secret
--      named SUPABASE_SERVICE_KEY. (.github/workflows/continuous_cycle.yml already
--      prefers it and falls back to SUPABASE_KEY while it is empty.)
--   3. Run the workflow once (workflow_dispatch); confirm it succeeds and its log
--      shows "N row(s) upserted". The service role bypasses RLS, so it needs no
--      policy of its own.
--   4. Only then run this file. If you run it earlier, the next scheduled run fails
--      with a permission error (the store stops updating) until step 2 is done.
--
-- RESULT: anon = SELECT only everywhere, plus the two UI writes kept below.
-- UNDO: the commented block at the bottom re-creates the removed policies/grants.

-- plant_state_current: anon read only
drop policy if exists "plant_state_current_upsert_all" on plant_state_current;
drop policy if exists "plant_state_current_update_all" on plant_state_current;
revoke insert, update on plant_state_current from anon;
revoke usage, select on sequence plant_state_current_id_seq from anon;

-- plant_operator_setpoints: anon read only (no UI writer exists today; a future
-- operator UI should write through an authenticated role)
drop policy if exists "plant_operator_setpoints_upsert_all" on plant_operator_setpoints;
drop policy if exists "plant_operator_setpoints_update_all" on plant_operator_setpoints;
revoke insert, update on plant_operator_setpoints from anon;
revoke usage, select on sequence plant_operator_setpoints_id_seq from anon;

-- measurement_promotions: anon read only (written only by record_measurement, never the UI)
drop policy if exists "measurement_promotions_insert_all" on measurement_promotions;
drop policy if exists "measurement_promotions_update_all" on measurement_promotions;
revoke insert, update on measurement_promotions from anon;
revoke usage, select on sequence measurement_promotions_id_seq from anon;

-- digital_twin_cycle_log: 002 already creates it SELECT-only for anon (no-op if 002 was run)
drop policy if exists "digital_twin_cycle_log_insert_all" on digital_twin_cycle_log;
revoke insert on digital_twin_cycle_log from anon;
revoke usage, select on sequence digital_twin_cycle_log_id_seq from anon;

-- KEPT ON PURPOSE (the UI needs anon writes here):
--   vendor_quotes            : select + insert            (log_quote button)
--   assumption_confirmations : select + insert + update   (mark-asked / confirm buttons)
-- These remain writable by anyone holding the anon key; closing that needs real
-- user authentication in the app (out of scope for this round).

-- UNDO (re-grants what was removed):
-- create policy "plant_state_current_upsert_all" on plant_state_current for insert with check (true);
-- create policy "plant_state_current_update_all" on plant_state_current for update using (true) with check (true);
-- grant select, insert, update on plant_state_current to anon;
-- grant usage, select on sequence plant_state_current_id_seq to anon;
-- (same pattern for plant_operator_setpoints, measurement_promotions and digital_twin_cycle_log;
--  the original policy definitions are in data/*_schema.sql and data/supabase_schema.sql.)
