import hashlib
import os
import re

import fitz  # PyMuPDF

from database import get_db
from naming import CATEGORY_MAP, is_known_composer, is_known_instrument

PDF_DIR = os.getenv("PDF_DIR", "/pdf")

# Structured-token patterns for classifying filename parts by content
# rather than position (see parse_filename() docstring below).
CATALOGUE_RE      = re.compile(r"^(Op|BWV|KV)\d+", re.IGNORECASE)
VOLUME_TOKEN_RE   = re.compile(r"^(book|vol|volume|part|grade)\d+", re.IGNORECASE)
MOVEMENT_TOKEN_RE = re.compile(r"^(mvt|mov|movement)\d+", re.IGNORECASE)


# ─── filename parsing ─────────────────────────────────────────────────────────

def parse_filename(filename: str) -> dict:
    """
    Parse a renamed PDF filename into metadata.

    Patterns:
      Bach-CelloSuite1-Bass-BassClef.pdf          ← repertoire (no prefix)
      Method-Simandl-Bass-Book1.pdf
      Etude-Czerny-Piano-Op299-Book1.pdf
      Orch-Brahms-Symphony1-Bass-Part.pdf
      Excerpt-Beethoven-Symphony5-Bass-Mvt1.pdf

    Assumes the filename is already normalized (e.g. by rename_tool.py) —
    this is content-based parsing, not fuzzy detection. See naming.py for
    the shared composer/instrument/category vocabulary both scripts draw
    from.

    rename_tool.py builds these filenames by joining only the segments
    that are actually present for a given file — catalogue number, volume,
    movement, and instrument are all optional, so any given field's
    position shifts depending on what's missing. Composer is the one
    field rename_tool always places immediately after the category prefix
    (or first, for repertoire's no-prefix case), so that stays positional;
    everything else is classified by content instead of index:
      - catalogue number / volume / movement are recognized by regex
        (Op123, BWV1067, KV421, Vol1, Book2, Part1, Mvt3, ...)
      - instrument is recognized against naming.py's known INSTRUMENTS
        vocabulary — the same vocabulary rename_tool draws from, so an
        instrument token here is always a known one
      - whatever's left over becomes the title (non-numeric markers like
        a bare "Part"/"Score" with no digit fall in here too, since
        there's no dedicated schema column for that distinction)
    """
    name = filename.removesuffix(".pdf")
    parts = [p.strip() for p in name.split("-") if p.strip()]

    meta = {
        "filename":        filename,
        "category":        "Repertoire",
        "composer_name":   None,
        "title":           None,
        "instrument":      None,
        "catalogue_number": None,
        "volume":          None,
        "movement":        None,
        "warnings":        [],
    }

    if parts and parts[0] in CATEGORY_MAP:
        meta["category"] = CATEGORY_MAP[parts[0]]
        parts = parts[1:]

    # Composer, when present, is always the token right after the category
    # prefix (or first, for repertoire) — the one field rename_tool never
    # shifts. But composer is itself optional (e.g. a generic instrument
    # method/technique book with no attributed composer), so don't claim
    # this slot as composer if it's actually the instrument token instead.
    if parts and not is_known_instrument(parts[0]):
        meta["composer_name"] = parts[0]
        parts = parts[1:]

    # Peel off the regex-recognizable structured tokens, in any order.
    leftover = []
    for part in parts:
        if CATALOGUE_RE.match(part):
            meta["catalogue_number"] = part
        elif VOLUME_TOKEN_RE.match(part):
            meta["volume"] = part
        elif MOVEMENT_TOKEN_RE.match(part):
            meta["movement"] = part
        else:
            leftover.append(part)

    # Of what's left, the instrument is whichever token matches the known
    # vocabulary; anything else is title text.
    title_parts = []
    for part in leftover:
        if meta["instrument"] is None and is_known_instrument(part):
            meta["instrument"] = part
        else:
            title_parts.append(part)

    if title_parts:
        meta["title"] = "-".join(title_parts)

    # Sanity checks — composer is still positional and instrument tokens
    # are matched against a known vocabulary, but a bad rename (typo,
    # missing field) can still slip through. These are warnings, not hard
    # failures, since the vocabulary in naming.py won't cover every edge
    # case.
    if meta["composer_name"] and not is_known_composer(meta["composer_name"]):
        meta["warnings"].append(
            f"composer_name '{meta['composer_name']}' not in known COMPOSERS list"
        )
    if meta["instrument"] and not is_known_instrument(meta["instrument"]):
        meta["warnings"].append(
            f"instrument '{meta['instrument']}' not in known INSTRUMENTS list"
        )

    return meta


# ─── helpers ──────────────────────────────────────────────────────────────────

def sha256(file_path: str) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def get_page_count(file_path: str) -> int:
    try:
        doc = fitz.open(file_path)
        count = doc.page_count
        doc.close()
        return count
    except Exception:
        return 0


def get_or_create_composer(conn, name: str) -> int:
    # INSERT OR IGNORE + re-select instead of select-then-insert: the watcher
    # thread and API request handlers can both hit this for the same new
    # composer name concurrently, and a plain select-then-insert has a
    # TOCTOU gap that produces duplicate composer rows. The UNIQUE index on
    # composer.name (migration 003) is what actually makes this safe — the
    # INSERT is a no-op if another connection won the race, and the
    # following SELECT then sees whichever row is authoritative.
    conn.execute("INSERT OR IGNORE INTO composer (name) VALUES (?)", (name,))
    row = conn.execute(
        "SELECT id FROM composer WHERE name = ?", (name,)
    ).fetchone()
    return row["id"]


def get_or_create_repertoire(conn, meta: dict) -> int | None:
    """
    For repertoire/orch/excerpt categories, look up or create a REPERTOIRE row.
    Method/Etude/Technique scores have no parent work — return None.
    """
    if meta["category"] in ("Method", "Etude", "Technique"):
        return None

    title = meta.get("title") or meta["filename"].removesuffix(".pdf")
    catalogue_number = meta.get("catalogue_number")

    # Same INSERT OR IGNORE + re-select pattern as get_or_create_composer()
    # above, backed by the UNIQUE index on repertoire.title (migration 003).
    conn.execute(
        "INSERT OR IGNORE INTO repertoire (title, catalogue_number) VALUES (?, ?)",
        (title, catalogue_number),
    )
    row = conn.execute(
        "SELECT id, catalogue_number FROM repertoire WHERE title = ?", (title,)
    ).fetchone()
    rep_id = row["id"]

    # Backfill catalogue_number if an earlier score for this same title
    # was ingested before parse_filename() could recognize one (or from
    # an edition that simply omitted it) — don't overwrite one that's
    # already set.
    if catalogue_number and not row["catalogue_number"]:
        conn.execute(
            "UPDATE repertoire SET catalogue_number = ? WHERE id = ?",
            (catalogue_number, rep_id),
        )

    # Link composer → repertoire via join table. Runs unconditionally now
    # (not just on first-insert) so a second score for an existing
    # repertoire row still gets its composer linked — INSERT OR IGNORE
    # makes this a safe no-op if the link already exists.
    if meta.get("composer_name"):
        composer_id = get_or_create_composer(conn, meta["composer_name"])
        conn.execute("""
            INSERT OR IGNORE INTO repertoire_composer (repertoire_id, composer_id, role)
            VALUES (?, ?, 'composer')
        """, (rep_id, composer_id))

    return rep_id


# ─── ingest ───────────────────────────────────────────────────────────────────

def ingest_file(filename: str, file_path: str | None = None) -> dict:
    """
    `filename` is the identity used for parsing/dedup — the bare, canonical
    name rename_tool.py produces (score.filename is unique on this).
    `file_path` is where to actually find the file on disk; defaults to
    PDF_DIR/filename for flat-layout callers (e.g. the POST
    /ingest/file/{filename} endpoint, which only ever targets top-level
    files). ingest_all() and the watcher now scan PDF_DIR recursively, so
    they pass the real (possibly nested) path explicitly.
    """
    if file_path is None:
        file_path = os.path.join(PDF_DIR, filename)

    if not os.path.exists(file_path):
        return {"status": "error", "message": f"File not found: {filename}"}

    file_hash = sha256(file_path)

    with get_db() as conn:
        # Dedup by filename
        existing = conn.execute(
            "SELECT id FROM score WHERE filename = ?", (filename,)
        ).fetchone()
        if existing:
            return {"status": "skipped", "message": f"Already ingested: {filename}"}

        # Dedup by hash (renamed file with identical content)
        existing_hash = conn.execute(
            "SELECT filename FROM score WHERE file_hash = ?", (file_hash,)
        ).fetchone()
        if existing_hash:
            return {
                "status": "skipped",
                "message": f"Duplicate of {existing_hash['filename']}: {filename}",
            }

        meta = parse_filename(filename)
        page_count = get_page_count(file_path)

        if meta["warnings"]:
            for w in meta["warnings"]:
                print(f"[ingest] WARNING ({filename}): {w}")

        # For standalone composer name on Method/Etude (no repertoire row)
        composer_id = None
        if meta["category"] in ("Method", "Etude", "Technique") and meta.get("composer_name"):
            composer_id = get_or_create_composer(conn, meta["composer_name"])

        repertoire_id = get_or_create_repertoire(conn, meta)

        # Append volume/movement to title for display if present
        display_title = meta.get("title") or filename.removesuffix(".pdf")
        if meta.get("volume"):
            display_title = f"{display_title} {meta['volume']}"
        if meta.get("movement"):
            display_title = f"{display_title} {meta['movement']}"

        cursor = conn.execute("""
            INSERT INTO score
                (repertoire_id, filename, category, instrument, page_count, file_hash)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            repertoire_id,
            filename,
            meta["category"],
            meta.get("instrument"),
            page_count,
            file_hash,
        ))

        # Method/Etude/Technique scores have no repertoire row to hang a
        # repertoire_composer link off of — link the composer directly via
        # score_composer instead, so it's not silently dropped.
        if repertoire_id is None and composer_id is not None:
            conn.execute("""
                INSERT OR IGNORE INTO score_composer (score_id, composer_id, role)
                VALUES (?, ?, 'composer')
            """, (cursor.lastrowid, composer_id))

    return {"status": "ok", "filename": filename, "meta": meta}


def ingest_all() -> list:
    """
    Recursively scan PDF_DIR (matching rename_tool.py's os.walk over the
    source folder) rather than only the top level — otherwise PDFs placed
    in subfolders would be silently invisible to ingestion even though
    the watcher and rename tool both see them.
    """
    if not os.path.exists(PDF_DIR):
        return [{"status": "error", "message": f"PDF_DIR not found: {PDF_DIR}"}]

    results = []
    for root, _dirs, filenames in os.walk(PDF_DIR):
        for filename in sorted(filenames):
            if filename.lower().endswith(".pdf"):
                file_path = os.path.join(root, filename)
                result = ingest_file(filename, file_path=file_path)
                results.append(result)
                print(f"[ingest] {result['status']}: {filename}")
    return results