-- music reader · setlist excerpts migration
-- Adds page_start/page_end to setlist_score for excerpt-level entries
-- (both null = whole score, matching the current behavior), and drops
-- the UNIQUE(setlist_id, score_id) constraint so the same score can
-- appear more than once in a setlist — e.g. an excerpt from the first
-- movement and a separate excerpt from the third movement of the same
-- score, or a repeated encore.
--
-- SQLite can't drop an inline table constraint with ALTER TABLE, so
-- this rebuilds setlist_score from scratch and copies existing rows
-- across. UNIQUE(setlist_id, position) is kept — the Pi client and the
-- reorder endpoint both rely on positions being gap-free and unique
-- within a setlist.

PRAGMA foreign_keys = OFF;

CREATE TABLE setlist_score_new (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    setlist_id  INTEGER NOT NULL REFERENCES setlist (id) ON DELETE CASCADE,
    score_id    INTEGER NOT NULL REFERENCES score   (id) ON DELETE CASCADE,
    position    INTEGER NOT NULL,           -- 1-indexed display order
    page_start  INTEGER,                    -- null = start of score
    page_end    INTEGER,                    -- null = end of score
    notes       TEXT,                       -- "start at letter B", "skip repeat"
    UNIQUE (setlist_id, position),          -- no duplicate positions per setlist
    CHECK ((page_start IS NULL) = (page_end IS NULL)),
    CHECK (page_start IS NULL OR page_end >= page_start)
);

INSERT INTO setlist_score_new (id, setlist_id, score_id, position, notes)
SELECT id, setlist_id, score_id, position, notes FROM setlist_score;

DROP TABLE setlist_score;
ALTER TABLE setlist_score_new RENAME TO setlist_score;

CREATE INDEX IF NOT EXISTS idx_ss_setlist ON setlist_score (setlist_id);
CREATE INDEX IF NOT EXISTS idx_ss_score   ON setlist_score (score_id);

PRAGMA foreign_keys = ON;

INSERT INTO schema_version (version, description)
VALUES (4, 'setlist_score — add page_start/page_end for excerpts, drop UNIQUE(setlist_id, score_id)');
