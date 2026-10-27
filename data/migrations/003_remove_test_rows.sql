-- 003_remove_test_rows.sql  (audit fix E2, docs/audit_2026-10-27.md findings 15, I3)
-- NOT RUN BY CLAUDE. Review, then run in the Supabase SQL Editor.
--
-- Deletes ONLY rows classified as test data. Every DELETE is keyed on the id AND
-- its identifying text so it cannot hit a different row. Rows that could not be
-- classified are listed at the bottom, commented out, for the owner to decide.
--
-- Rows were read with SELECT on 2026-10-27 (nothing written by the audit).
-- Downstream effect of deleting the air-ratio row (shown in memory, no DB): the
-- ER sampling band goes from the "confirmed" [0.245, 0.255] back to the default
-- +/-15 % band [0.2125, 0.2875]; compliance / AI-015 "Confirmed" count 2 -> 1; the
-- Monte Carlo 90 % CI on HTS conversion widens from [70.4 %, 78.9 %] to
-- [68.5 %, 81.3 %]. GA-001's ER point value stays 0.25 (Assumed) either way.
--
-- UNDO: the INSERT statement under each DELETE restores the exact row.

-- measurement_promotions id=1  | LOOKS LIKE TEST
-- Evidence: source_description 'Phase 6 self-test -- synthetic SA-001 H2 sensor';
-- promoted_at 2026-09-08T17:57:41Z, the minute the module self-tests were run
-- (measurement_promotion.py __main__ calls record_measurement); the value it
-- describes (32.7 vol%) is the self-test's SYNTHETIC_H2_PCT; no real reader exists.
delete from measurement_promotions
 where id = 1 and engine_key = 'SA-001|Reading'
   and source_description = 'Phase 6 self-test -- synthetic SA-001 H2 sensor';
-- undo: insert into measurement_promotions (engine_key, source_description, promoted_at)
--       values ('SA-001|Reading', 'Phase 6 self-test -- synthetic SA-001 H2 sensor', '2026-09-08T17:57:41.964716+00:00');

-- measurement_promotions id=2  | LOOKS LIKE TEST
-- Evidence: 'Phase 6 self-test -- synthetic EU-009 revenue meter', promoted_at
-- 2026-09-08T17:57:42Z (0.7 s after id=1, same self-test run).
delete from measurement_promotions
 where id = 2 and engine_key = 'EU-009|GridBalance'
   and source_description = 'Phase 6 self-test -- synthetic EU-009 revenue meter';
-- undo: insert into measurement_promotions (engine_key, source_description, promoted_at)
--       values ('EU-009|GridBalance', 'Phase 6 self-test -- synthetic EU-009 revenue meter', '2026-09-08T17:57:42.654854+00:00');

-- assumption_confirmations id=3 (air_equivalence_ratio)  | LOOKS LIKE TEST
-- Evidence: notes = 'test: DOK-ING confirmed air ratio 0.25 +/- 0.005' (the row
-- itself says "test:"); updated_at 2026-08-26T09:23:38Z, the same session as the
-- other row (id=1). The range 0.245-0.255 is exactly 0.25 +/- 0.005, a round test
-- value rather than a DOK-ING-sourced range.
delete from assumption_confirmations
 where id = 3 and assumption_key = 'air_equivalence_ratio' and notes like 'test:%';
-- undo: insert into assumption_confirmations
--         (assumption_key, status, confirmed_value, confirmed_range_low, confirmed_range_high, notes, updated_at)
--       values ('air_equivalence_ratio', 'confirmed', 0.25, 0.245, 0.255,
--               'test: DOK-ING confirmed air ratio 0.25 +/- 0.005', '2026-08-26T09:23:38.284954+00:00');

-- plant_operator_setpoints: 0 rows, nothing to delete.

-- ---------------------------------------------------------------------------
-- NEEDS THE OWNER'S DECISION -- NOT deleted (cannot tell):
-- assumption_confirmations id=1 (steam_to_feed_ratio): status 'confirmed',
--   value 0.4, range [0.392, 0.408] (= 0.4 +/- 2 %), notes '' (empty),
--   updated_at 2026-08-26T09:29:25Z (6 minutes after the "test:" air row). Nothing
--   in the row proves it is test or real. Check it against the DOK-ING
--   correspondence. If it is NOT a real confirmation, remove it with:
-- delete from assumption_confirmations
--  where id = 1 and assumption_key = 'steam_to_feed_ratio' and notes = '';
