import hashlib
import os
import re

import fitz  # PyMuPDF

from database import get_db

PDF_DIR = os.getenv("PDF_DIR", "/app/pdf")

CATEGORY_MAP = {
    "Method":    "Method",
    "Etude":     "Etude",
    "Technique": "Technique",
    "Orch":      "Orch",
    "Excerpt":   "Excerpt",
}


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
    """
    name = filename.removesuffix(".pdf")
    parts = name.split("-")

    meta = {
        "filename":        filename,
        "category":        "repertoire",
        "composer_name":   None,
        "title":           None,
        "instrument":      None,
        "catalogue_number": None,
        "volume":          None,
        "movement":        None,
    }

    if parts[0] in CATEGORY_MAP:
        meta["category"] = CATEGORY_MAP[parts[0]]
        parts = parts[1:]

    if meta["category"] == "repertoire":
        # Bach-CelloSuite1-Bass-BassClef
        meta["composer_name"] = parts[0] if len(parts) > 0 else None
        meta["title"]         = parts[1] if len(parts) > 1 else None
        meta["instrument"]    = parts[2] if len(parts) > 2 else None

    elif meta["category"] in ("Method", "Etude", "Technique"):
        # Simandl-Bass-Book1  /  Czerny-Piano-Op299-Book1
        meta["composer_name"] = parts[0] if len(parts) > 0 else None
        meta["instrument"]    = parts[1] if len(parts) > 1 else None
        for part in parts[2:]:
            if re.match(r"^Op\d+", part, re.IGNORECASE):
                meta["catalogue_number"] = part
            elif re.match(r"^(Book|Vol|Grade)\d+", part, re.IGNORECASE):
                meta["volume"] = part

    elif meta["category"] in ("Orch", "Excerpt"):
        # Brahms-Symphony1-Bass-Part  /  Beethoven-Symphony5-Bass-Mvt1
        meta["composer_name"] = parts[0] if len(parts) > 0 else None
        meta["title"]         = parts[1] if len(parts) > 1 else None
        meta["instrument"]    = parts[2] if len(parts) > 2 else None
        meta["movement"]      = parts[3] if len(parts) > 3 else None

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
    row = conn.execute(
        "SELECT id FROM composer WHERE name = ?", (name,)
    ).fetchone()
    if row:
        return row["id"]
    cursor = conn.execute(
        "INSERT INTO composer (name) VALUES (?)", (name,)
    )
    return cursor.lastrowid


def get_or_create_repertoire(conn, meta: dict) -> int | None:
    """
    For repertoire/orch/excerpt categories, look up or create a REPERTOIRE row.
    Method/Etude/Technique scores have no parent work — return None.
    """
    if meta["category"] in ("Method", "Etude", "Technique"):
        return None

    title = meta.get("title") or meta["filename"].removesuffix(".pdf")

    row = conn.execute(
        "SELECT id FROM repertoire WHERE title = ?", (title,)
    ).fetchone()
    if row:
        return row["id"]

    cursor = conn.execute(
        "INSERT INTO repertoire (title) VALUES (?)", (title,)
    )
    rep_id = cursor.lastrowid

    # Link composer → repertoire via join table
    if meta.get("composer_name"):
        composer_id = get_or_create_composer(conn, meta["composer_name"])
        conn.execute("""
            INSERT OR IGNORE INTO repertoire_composer (repertoire_id, composer_id, role)
            VALUES (?, ?, 'composer')
        """, (rep_id, composer_id))

    return rep_id


# ─── ingest ───────────────────────────────────────────────────────────────────

def ingest_file(filename: str) -> dict:
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

        conn.execute("""
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

    return {"status": "ok", "filename": filename, "meta": meta}


def ingest_all() -> list:
    if not os.path.exists(PDF_DIR):
        return [{"status": "error", "message": f"PDF_DIR not found: {PDF_DIR}"}]

    results = []
    for filename in sorted(os.listdir(PDF_DIR)):
        if filename.lower().endswith(".pdf"):
            result = ingest_file(filename)
            results.append(result)
            print(f"[ingest] {result['status']}: {filename}")
    return results