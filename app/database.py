import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.getenv("DB_PATH", "/app/db/music.db")
MIGRATIONS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "migrations"
    )


def migrate():
    """Apply any .sql migration files in order that haven't been applied yet."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    os.makedirs(MIGRATIONS_DIR, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")

        # Ensure schema_version table exists before we query it
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version     INTEGER PRIMARY KEY,
                applied_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                description TEXT
            )
        """)
        conn.commit()

        applied = {
            row[0]
            for row in conn.execute("SELECT version FROM schema_version").fetchall()
        }

        migration_files = sorted(
            f for f in os.listdir(MIGRATIONS_DIR) if f.endswith(".sql")
        )

        for fname in migration_files:
            # Extract leading integer version number from filename, e.g. 001_initial_schema.sql → 1
            try:
                version = int(fname.split("_")[0])
            except ValueError:
                print(f"[db] skipping non-versioned file: {fname}")
                continue

            if version in applied:
                print(f"[db] already applied: {fname}")
                continue

            fpath = os.path.join(MIGRATIONS_DIR, fname)
            with open(fpath) as f:
                sql = f.read()

            print(f"[db] applying migration: {fname}")
            conn.executescript(sql)
            conn.commit()
            print(f"[db] applied: {fname}")


@contextmanager
def get_db():
    """Context manager yielding a WAL-mode, dict-row SQLite connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
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
    return dict(row) if row else None


def rows_to_list(rows) -> list:
    return [dict(r) for r in rows]