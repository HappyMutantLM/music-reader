import os

import fitz  # PyMuPDF
from fastapi import APIRouter, HTTPException, Response

from database import get_db
from ingest_core import PDF_DIR

CACHE_DIR = os.getenv("CACHE_DIR", "/cache")

# Waveshare 9.7" IT8951 panel resolution. Pages are scaled to fit this
# box (preserving aspect ratio) rather than stretched to fill it exactly.
PANEL_WIDTH = int(os.getenv("PANEL_WIDTH", "1200"))
PANEL_HEIGHT = int(os.getenv("PANEL_HEIGHT", "825"))

router = APIRouter()


def _find_pdf_path(filename: str) -> str | None:
    """Locate a score's PDF on disk.

    score.filename is stored as a bare basename with no path column, but
    PDF_DIR is scanned recursively at ingest time (watcher.py,
    ingest_core.ingest_all) — a file can live in a subfolder like
    Repertoire/Bach/. Try the flat PDF_DIR/filename path first (the
    common case), then fall back to walking PDF_DIR for a match.
    """
    flat_path = os.path.join(PDF_DIR, filename)
    if os.path.exists(flat_path):
        return flat_path

    for root, _dirs, filenames in os.walk(PDF_DIR):
        if filename in filenames:
            return os.path.join(root, filename)

    return None


def _render_page_png(pdf_path: str, page_number: int) -> bytes:
    """Render one page (1-indexed) of pdf_path to a grayscale PNG scaled
    to fit the panel. Raises HTTPException(404) if page_number is out of
    range for the actual PDF (belt-and-suspenders alongside the
    score.page_count check in get_page — that column can be null/stale
    for a score ingested before page_count existed or ingested
    incorrectly)."""
    doc = fitz.open(pdf_path)
    try:
        if page_number < 1 or page_number > doc.page_count:
            raise HTTPException(
                status_code=404,
                detail=f"Page {page_number} out of range (1-{doc.page_count})",
            )

        page = doc.load_page(page_number - 1)  # fitz pages are 0-indexed

        # Scale by whichever dimension is the binding constraint so the
        # page fits inside the panel box without distortion, then render
        # straight to grayscale — no separate PIL conversion pass needed.
        rect = page.rect
        scale = min(PANEL_WIDTH / rect.width, PANEL_HEIGHT / rect.height)
        matrix = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=matrix, colorspace=fitz.csGRAY)
        return pix.tobytes("png")
    finally:
        doc.close()


@router.get("/{score_id}/{page_number}")
def get_page(score_id: int, page_number: int):
    """Return a single page of a score as a grayscale PNG sized for the
    e-ink panel. Rendered once per (score_id, page_number) and cached to
    disk under CACHE_DIR — PyMuPDF rendering is too slow to redo on
    every pedal tap during a performance."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT filename, page_count FROM score WHERE id = ?", (score_id,)
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Score not found")

    filename, page_count = row["filename"], row["page_count"]
    if page_count and (page_number < 1 or page_number > page_count):
        raise HTTPException(
            status_code=404,
            detail=f"Page {page_number} out of range (1-{page_count})",
        )

    cache_path = os.path.join(CACHE_DIR, str(score_id), f"{page_number}.png")
    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            return Response(content=f.read(), media_type="image/png")

    pdf_path = _find_pdf_path(filename)
    if not pdf_path:
        raise HTTPException(
            status_code=404, detail=f"PDF file missing on disk: {filename}"
        )

    png_bytes = _render_page_png(pdf_path, page_number)

    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, "wb") as f:
        f.write(png_bytes)

    return Response(content=png_bytes, media_type="image/png")
