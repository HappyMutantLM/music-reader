import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.getenv("DB_PATH", "/db/music.db")

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS composers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    last_name   TEXT NOT NULL,
    first_name  TEXT,
    birth_year  INTEGER,
    death_year  INTEGER
);

CREATE TABLE IF NOT EXISTS scores (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    filename    TEXT NOT NULL UNIQUE,
    title       TEXT NOT NULL,
    category    TEXT NOT NULL,
    instrument  TEXT,
    composer_id INTEGER REFERENCES composers(id),
    opus        TEXT,
    volume      TEXT,
    movement    TEXT,
    level       TEXT,
    page_count  INTEGER,
    file_path   TEXT NOT NULL,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS works (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    composer_id INTEGER REFERENCES composers(id),
    title       TEXT NOT NULL,
    genre       TEXT,
    key         TEXT,
    opus        TEXT
);

CREATE TABLE IF NOT EXISTS work_scores (
    work_id     INTEGER REFERENCES works(id),
    score_id    INTEGER REFERENCES scores(id),
    PRIMARY KEY (work_id, score_id)
);

CREATE TABLE IF NOT EXISTS setlists (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    description TEXT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS setlist_scores (
    setlist_id  INTEGER REFERENCES setlists(id),
    score_id    INTEGER REFERENCES scores(id),
    position    INTEGER,
    PRIMARY KEY (setlist_id, score_id)
);

CREATE TABLE IF NOT EXISTS render_cache (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    score_id    INTEGER REFERENCES scores(id),
    page_num    INTEGER NOT NULL,
    width       INTEGER,
    height      INTEGER,
    dither      TEXT,
    cache_path  TEXT NOT NULL,
    rendered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(score_id, page_num, width, height)
);

CREATE INDEX IF NOT EXISTS idx_scores_instrument ON scores(instrument);
CREATE INDEX IF NOT EXISTS idx_scores_category   ON scores(category);
CREATE INDEX IF NOT EXISTS idx_scores_composer   ON scores(composer_id);
CREATE INDEX IF NOT EXISTS idx_render_cache      ON render_cache(score_id, page_num);
"""

def init_db():
    """Initialize database and schema on first run."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA)
    print(f"Database initialized at {DB_PATH}")


@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row   # rows behave like dicts
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to a plain dict."""
    return dict(row) if row else None


def rows_to_list(rows) -> list:
    """Convert a list of sqlite3.Rows to plain dicts."""
    return [dict(r) for r in rows]