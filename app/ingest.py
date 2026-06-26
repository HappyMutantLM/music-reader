import os
import re
import fitz  # PyMuPDF
from app.database import get_db, rows_to_list

PDF_DIR = os.getenv("PDF_DIR", "/pdf")

# Mapping of prefix to category
CATEGORY_MAP = {
    "Method":    "method",
    "Etude":     "etude",
    "Technique": "technique",
    "Orch":      "orch",
    "Excerpt":   "excerpt",
}

def parse_filename(filename: str) -> dict:
    """
    Parse filename into metadata dict.
    
    Patterns:
      Method-Simandl-Bass-Book1.pdf
      Etude-Czerny-Piano-Op299-Book1.pdf
      Orch-Brahms-Symphony1-Bass-Part.pdf
      Excerpt-Beethoven-Symphony5-Bass-Mvt1.pdf
      Bach-CelloSuite1-Bass-BassClef.pdf          ← repertoire (no prefix)
    """
    name = filename.replace(".pdf", "")
    parts = name.split("-")
    
    meta = {
        "filename":   filename,
        "category":   "repertoire",
        "composer":   None,
        "title":      None,
        "instrument": None,
        "opus":       None,
        "volume":     None,
        "movement":   None,
        "level":      None,
    }

    # Check for known prefix
    if parts[0] in CATEGORY_MAP:
        meta["category"] = CATEGORY_MAP[parts[0]]
        parts = parts[1:]  # strip prefix, work with remainder

    # Parse by category
    if meta["category"] == "repertoire":
        # Bach-CelloSuite1-Bass-BassClef
        meta["composer"]   = parts[0] if len(parts) > 0 else None
        meta["title"]      = parts[1] if len(parts) > 1 else None
        meta["instrument"] = parts[2] if len(parts) > 2 else None
        meta["level"]      = parts[3] if len(parts) > 3 else None

    elif meta["category"] in ("method", "etude", "technique"):
        # Simandl-Bass-Book1 or Czerny-Piano-Op299-Book1
        meta["composer"]   = parts[0] if len(parts) > 0 else None
        meta["instrument"] = parts[1] if len(parts) > 1 else None
        # Scan remaining parts for opus/volume patterns
        for part in parts[2:]:
            if re.match(r"^Op\d+", part, re.IGNORECASE):
                meta["opus"] = part
            elif re.match(r"^(Book|Vol|Grade)\d+", part, re.IGNORECASE):
                meta["volume"] = part

    elif meta["category"] in ("orch", "excerpt"):
        # Brahms-Symphony1-Bass-Part or Beethoven-Symphony5-Bass-Mvt1
        meta["composer"]   = parts[0] if len(parts) > 0 else None
        meta["title"]      = parts[1] if len(parts) > 1 else None
        meta["instrument"] = parts[2] if len(parts) > 2 else None
        meta["movement"]   = parts[3] if len(parts) > 3 else None

    return meta


def get_or_create_composer(conn, last_name: str) -> int:
    """Get existing composer id or create new one."""
    row = conn.execute(
        "SELECT id FROM composers WHERE last_name = ?", (last_name,)
    ).fetchone()
    if row:
        return row["id"]
    cursor = conn.execute(
        "INSERT INTO composers (last_name) VALUES (?)", (last_name,)
    )
    return cursor.lastrowid


def get_page_count(file_path: str) -> int:
    """Get PDF page count via PyMuPDF."""
    try:
        doc = fitz.open(file_path)
        count = doc.page_count
        doc.close()
        return count
    except Exception:
        return 0


def ingest_file(filename: str) -> dict:
    """Ingest a single PDF file into the database."""
    file_path = os.path.join(PDF_DIR, filename)

    if not os.path.exists(file_path):
        return {"status": "error", "message": f"File not found: {filename}"}

    meta = parse_filename(filename)
    page_count = get_page_count(file_path)

    with get_db() as conn:
        # Check if already ingested
        existing = conn.execute(
            "SELECT id FROM scores WHERE filename = ?", (filename,)
        ).fetchone()
        if existing:
            return {"status": "skipped", "message": f"Already ingested: {filename}"}

        # Get or create composer
        composer_id = None
        if meta["composer"]:
            composer_id = get_or_create_composer(conn, meta["composer"])

        # Insert score
        conn.execute("""
            INSERT INTO scores 
                (filename, title, category, instrument, composer_id,
                 opus, volume, movement, level, page_count, file_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            meta["filename"],
            meta["title"] or meta["filename"],
            meta["category"],
            meta["instrument"],
            composer_id,
            meta["opus"],
            meta["volume"],
            meta["movement"],
            meta["level"],
            page_count,
            file_path,
        ))

    return {"status": "ok", "filename": filename, "meta": meta}


def ingest_all() -> list:
    """Scan PDF_DIR and ingest all PDFs not yet in the database."""
    if not os.path.exists(PDF_DIR):
        return [{"status": "error", "message": f"PDF_DIR not found: {PDF_DIR}"}]

    results = []
    for filename in sorted(os.listdir(PDF_DIR)):
        if filename.lower().endswith(".pdf"):
            result = ingest_file(filename)
            results.append(result)
            print(f"[ingest] {result['status']}: {filename}")

    return results