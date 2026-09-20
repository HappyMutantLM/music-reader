-- music reader · companion program-notes migration
--
-- Adds program-note fields to repertoire — the musical work itself, not
-- any one instrument's PDF, since the note text is the same regardless
-- of which score row (part) it's attached to — plus a singleton
-- now_playing pointer the companion e-ink device polls for its "now
-- playing" badge.
--
-- now_playing deliberately points at setlist_score.id rather than
-- duplicating a new "setlist item" concept — setlist_score already is
-- the ordered setlist-item table (see 001_initial_schema.sql /
-- 004_setlist_excerpts.sql), so this just needed a place to record
-- which row is currently live.

PRAGMA foreign_keys = ON;

ALTER TABLE repertoire ADD COLUMN blurb TEXT;         -- 1-3 sentences, companion detail screen
ALTER TABLE repertoire ADD COLUMN program_note TEXT;  -- longer note, future archival/expanded view
ALTER TABLE repertoire ADD COLUMN note_source TEXT;   -- attribution, e.g. "IMSLP", "written by Leila"

CREATE TABLE IF NOT EXISTS now_playing (
    id               INTEGER PRIMARY KEY CHECK (id = 1),
    setlist_score_id INTEGER REFERENCES setlist_score (id) ON DELETE SET NULL,
    updated_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
INSERT OR IGNORE INTO now_playing (id, setlist_score_id) VALUES (1, NULL);

INSERT INTO schema_version (version, description)
VALUES (5, 'companion device — repertoire program notes + now_playing pointer');
