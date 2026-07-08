-- music reader · score_composer migration
-- goes in app/migrations/ alongside 001_initial_schema.sql
--
-- Adds a direct score -> composer link for scores with no parent
-- repertoire row (Method / Etude / Technique), mirroring the existing
-- repertoire_composer join table. Only ever populated when
-- score.repertoire_id IS NULL — repertoire-linked scores keep using
-- repertoire_composer as before, so there's no duplicate source of truth.

CREATE TABLE IF NOT EXISTS score_composer (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    score_id    INTEGER NOT NULL REFERENCES score    (id) ON DELETE CASCADE,
    composer_id INTEGER NOT NULL REFERENCES composer (id) ON DELETE CASCADE,
    -- composer | arranger | editor | transcriber | orchestrator
    role        TEXT    NOT NULL DEFAULT 'composer',
    UNIQUE (score_id, composer_id, role)
);

CREATE INDEX IF NOT EXISTS idx_sc_score    ON score_composer (score_id);
CREATE INDEX IF NOT EXISTS idx_sc_composer ON score_composer (composer_id);

INSERT INTO schema_version (version, description)
VALUES (2, 'score_composer — direct composer link for repertoire-less scores');