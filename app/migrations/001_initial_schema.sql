-- music reader · initial schema migration
-- sqlite 3.x · WAL mode assumed (set in app startup)
-- run once against a fresh db file

PRAGMA foreign_keys = ON;

-- ─── composers ────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS composer (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    birth_year  INTEGER,
    death_year  INTEGER,
    nationality TEXT,
    notes       TEXT
);

CREATE INDEX IF NOT EXISTS idx_composer_name ON composer (name);

-- ─── repertoire ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS repertoire (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    title            TEXT    NOT NULL,
    nickname         TEXT,                   -- "Moonlight", "Trout", etc.
    key_signature    TEXT,                   -- "D minor", "G major"
    catalogue_number TEXT,                   -- "BWV 1004", "Op. 77", "RV 93"
    notes            TEXT
);

CREATE INDEX IF NOT EXISTS idx_repertoire_title ON repertoire (title);

-- ─── repertoire ↔ composer (many-to-many with role) ──────────────────────────

CREATE TABLE IF NOT EXISTS repertoire_composer (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    repertoire_id  INTEGER NOT NULL REFERENCES repertoire (id) ON DELETE CASCADE,
    composer_id    INTEGER NOT NULL REFERENCES composer   (id) ON DELETE CASCADE,
    -- composer | arranger | editor | transcriber | orchestrator
    role           TEXT    NOT NULL DEFAULT 'composer',
    UNIQUE (repertoire_id, composer_id, role)
);

CREATE INDEX IF NOT EXISTS idx_rc_repertoire ON repertoire_composer (repertoire_id);
CREATE INDEX IF NOT EXISTS idx_rc_composer   ON repertoire_composer (composer_id);

-- ─── scores (physical PDF files) ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS score (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    -- null for stand-alone method/etude books with no parent work
    repertoire_id  INTEGER REFERENCES repertoire (id) ON DELETE SET NULL,
    filename       TEXT    NOT NULL UNIQUE,
    -- repertoire | Method | Etude | Technique | Orch | Excerpt
    category       TEXT    NOT NULL,
    -- derived from filename; null if not instrument-specific (e.g. a full score)
    instrument     TEXT,
    page_count     INTEGER,
    file_hash      TEXT    UNIQUE,          -- SHA-256, for dedup on re-ingest
    ingested_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at     TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_score_repertoire ON score (repertoire_id);
CREATE INDEX IF NOT EXISTS idx_score_category   ON score (category);
CREATE INDEX IF NOT EXISTS idx_score_instrument ON score (instrument);

-- keep updated_at current automatically
CREATE TRIGGER IF NOT EXISTS trg_score_updated_at
    AFTER UPDATE ON score
    FOR EACH ROW
BEGIN
    UPDATE score SET updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
    WHERE id = OLD.id;
END;

-- ─── setlists ─────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS setlist (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    description TEXT,
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- ─── setlist ↔ score (ordered) ───────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS setlist_score (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    setlist_id  INTEGER NOT NULL REFERENCES setlist (id) ON DELETE CASCADE,
    score_id    INTEGER NOT NULL REFERENCES score   (id) ON DELETE CASCADE,
    position    INTEGER NOT NULL,           -- 1-indexed display order
    notes       TEXT,                       -- "start at letter B", "skip repeat"
    UNIQUE (setlist_id, score_id),
    UNIQUE (setlist_id, position)           -- no duplicate positions per setlist
);

CREATE INDEX IF NOT EXISTS idx_ss_setlist ON setlist_score (setlist_id);
CREATE INDEX IF NOT EXISTS idx_ss_score   ON setlist_score (score_id);

-- ─── schema version ───────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    description TEXT
);

INSERT INTO schema_version (version, description)
VALUES (1, 'initial schema — composer, repertoire, score, setlist');
