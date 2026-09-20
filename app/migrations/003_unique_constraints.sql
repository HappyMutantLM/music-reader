-- music reader · unique constraints migration
-- Adds real UNIQUE constraints on composer.name and repertoire.title.
--
-- Without these, get_or_create_composer()/get_or_create_repertoire() in
-- ingest_core.py had a select-then-insert race: the watcher thread and API
-- request handlers can both open connections against the same db
-- concurrently, and two simultaneous first-time ingests referencing the
-- same new composer/title could each insert a duplicate row. These indexes
-- make INSERT OR IGNORE the actual enforcement mechanism instead of relying
-- on application-level check-then-act.
--
-- NOTE: if the live db already has duplicate composer.name or
-- repertoire.title values, this migration will fail to apply. Check first:
--   SELECT name, COUNT(*) FROM composer GROUP BY name HAVING COUNT(*) > 1;
--   SELECT title, COUNT(*) FROM repertoire GROUP BY title HAVING COUNT(*) > 1;
-- and merge/dedupe any hits before re-running.

CREATE UNIQUE INDEX IF NOT EXISTS idx_composer_name_unique ON composer (name);
CREATE UNIQUE INDEX IF NOT EXISTS idx_repertoire_title_unique ON repertoire (title);

INSERT INTO schema_version (version, description)
VALUES (3, 'unique constraints on composer.name and repertoire.title to prevent duplicate-row races');
