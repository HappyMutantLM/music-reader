-- Core score table
CREATE TABLE scores (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    filename    TEXT NOT NULL UNIQUE,
    title       TEXT NOT NULL,
    category    TEXT NOT NULL,  -- repertoire, method, etude, technique, orch, excerpt
    instrument  TEXT,           -- Bass, Piano, Violin, etc.
    composer_id INTEGER REFERENCES composers(id),
    opus        TEXT,           -- op299, op740, etc.
    volume      TEXT,           -- Book1, Vol2, etc.
    movement    TEXT,           -- Mvt1, Mvt4, etc.
    level       TEXT,           -- Grade3, Advanced, etc.
    page_count  INTEGER,
    file_path   TEXT NOT NULL,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Composers
CREATE TABLE composers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    last_name   TEXT NOT NULL,
    first_name  TEXT,
    birth_year  INTEGER,
    death_year  INTEGER
);

-- Repertoire container -- holds multiple parts of same work
CREATE TABLE works (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    composer_id INTEGER REFERENCES composers(id),
    title       TEXT NOT NULL,
    genre       TEXT,   -- symphony, trio, sonata, concerto, etc.
    key         TEXT,   -- D minor, E flat major, etc.
    opus        TEXT
);

-- Links scores to works (one work, many parts)
CREATE TABLE work_scores (
    work_id     INTEGER REFERENCES works(id),
    score_id    INTEGER REFERENCES scores(id),
    PRIMARY KEY (work_id, score_id)
);

-- Setlists -- audition prep, gig sets, practice sessions
CREATE TABLE setlists (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,   -- "Fall Audition", "Trio Gig Oct"
    description TEXT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Links scores to setlists
CREATE TABLE setlist_scores (
    setlist_id  INTEGER REFERENCES setlists(id),
    score_id    INTEGER REFERENCES scores(id),
    position    INTEGER,         -- order within setlist
    PRIMARY KEY (setlist_id, score_id)
);

-- Page render cache tracking
CREATE TABLE render_cache (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    score_id    INTEGER REFERENCES scores(id),
    page_num    INTEGER NOT NULL,
    width       INTEGER,
    height      INTEGER,
    dither      TEXT,            -- floyd-steinberg, etc.
    cache_path  TEXT NOT NULL,
    rendered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(score_id, page_num, width, height)
);

-- Indexes for your three discovery axes
CREATE INDEX idx_scores_instrument ON scores(instrument);
CREATE INDEX idx_scores_category   ON scores(category);
CREATE INDEX idx_scores_composer   ON scores(composer_id);
CREATE INDEX idx_render_cache      ON render_cache(score_id, page_num);