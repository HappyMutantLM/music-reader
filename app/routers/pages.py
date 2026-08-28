import os

import fitz  # PyMuPDF
from fastapi import APIRouter, HTTPException, Response
from PILimport io
import os

import fitz  # PyMuPDF
from fastapi import APIRouter, HTTPException, Response
from PIL import Image

from database import get_db
from ingest_core import PDF_DIR

CACHE_DIR = os.getenv("CACHE_DIR", "/cache")

# Bump this any time _render_page_png's output changes (crop logic,
# threshold defaults, panel size, etc.). Cached PNGs are keyed by
# (RENDER_VERSION, score_id, page_number), so a bump makes every page
# re-render fresh automatically instead of silently continuing to serve
# images rendered under the old logic — which is exactly what happened
# after the content-crop change below: score_id/page combos that had
# already been viewed (and cached) before this file was deployed kept
# showing the old, uncropped render until manually cleared, while
# never-before-viewed pages picked up the new logic immediately. Old
# version directories under CACHE_DIR just become dead weight — safe to
# delete by hand, or ignore.
RENDER_VERSION = "v2-content-crop"

# Waveshare 9.7" IT8951 panel, logical (post-rotation) portrait shape —
# the enclosure mounts the panel rotated 90° from its native 1200x825
# landscape resolution. Pages are scaled to fit this box (preserving
# aspect ratio) rather than stretched to fill it exactly. Keep these in
# sync with pi_client/config.py's PANEL_WIDTH/PANEL_HEIGHT.
PANEL_WIDTH = int(os.getenv("PANEL_WIDTH", "825"))
PANEL_HEIGHT = int(os.getenv("PANEL_HEIGHT", "1200"))

# Detection resolution used to find each page's actual content bounding
# box before cropping (see _render_page_png). Deliberately higher than
# the panel needs so a tightly-cropped page still downsamples cleanly
# instead of upscaling a low-res crop.
CONTENT_DETECT_SCALE = 4.0

# A pixel this light or lighter (0-255, grayscale) counts as background
# when finding each page's content bounding box. Scanned scores vary
# page to page in how much margin surrounds the actual engraving —
# without cropping to content first, a page with more margin (e.g. a
# piece that ends partway down the page) renders its notation
# noticeably smaller than a page whose content runs edge to edge, even
# though both pages are the same physical size. Lower this if faint
# scan artifacts near page edges are being picked up as "content" and
# preventing a tight crop; raise it if genuinely light-but-real marks
# (soft pencil, faint slurs) are being cropped away.
CONTENT_WHITE_THRESHOLD = int(os.getenv("CONTENT_WHITE_THRESHOLD", "250"))

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
    """Render one page (1-indexed) of pdf_path to a grayscale PNG, cropped
    to its actual printed content and scaled to fit the panel. Raises
    HTTPException(404) if page_number is out of range for the actual PDF
    (belt-and-suspenders alongside the score.page_count check in
    get_page — that column can be null/stale for a score ingested before
    page_count existed or ingested incorrectly)."""
    doc = fitz.open(pdf_path)
    try:
        if page_number < 1 or page_number > doc.page_count:
            raise HTTPException(
                status_code=404,
                detail=f"Page {page_number} out of range (1-{doc.page_count})",
            )

        page = doc.load_page(page_number - 1)  # fitz pages are 0-indexed

        # Render at a higher resolution than the panel needs so cropping
        # to content below still leaves enough pixels to downsample
        # cleanly, then find the bounding box of everything that isn't
        # near-white — i.e. the actual printed music, ignoring however
        # much blank margin this particular page happens to have.
        matrix = fitz.Matrix(CONTENT_DETECT_SCALE, CONTENT_DETECT_SCALE)
        pix = page.get_pixmap(matrix=matrix, colorspace=fitz.csGRAY)
        img = Image.frombytes("L", (pix.width, pix.height), pix.samples)

        bbox = Image.eval(img, lambda p: 0 if p >= CONTENT_WHITE_THRESHOLD else 255).getbbox()
        if bbox:
            # Small breathing room so notation doesn't touch the panel's
            # edge exactly — proportional to image size so it scales
            # sensibly across different page sizes/scan resolutions.
            pad = round(0.015 * min(img.width, img.height))
            left = max(bbox[0] - pad, 0)
            top = max(bbox[1] - pad, 0)
            right = min(bbox[2] + pad, img.width)
            bottom = min(bbox[3] + pad, img.height)
            img = img.crop((left, top, right, bottom))
        # bbox is None for a genuinely blank page — fall back to the
        # full (blank) render rather than crashing on an empty crop.

        # Scale by whichever dimension is the binding constraint so the
        # cropped content fits inside the panel box without distortion.
        scale = min(PANEL_WIDTH / img.width, PANEL_HEIGHT / img.height)
        target_size = (
            max(1, round(img.width * scale)),
            max(1, round(img.height * scale)),
        )
        img = img.resize(target_size, Image.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
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

    cache_path = os.path.join(
        CACHE_DIR, RENDER_VERSION, str(score_id), f"{page_number}.png"
    )
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
 import Image

from database import get_db
from ingest_core import PDF_DIR

CACHE_DIR = os.getenv("CACHE_DIR", "/cache")

# Waveshare 9.7" IT8951 panel, logical (post-rotation) portrait shape —
# the enclosure mounts the panel rotated 90° from its native 1200x825
# landscape resolution. Pages are scaled to fit this box (preserving
# aspect ratio) rather than stretched to fill it exactly. Keep these in
# sync with pi_client/config.py's PANEL_WIDTH/PANEL_HEIGHT.
PANEL_WIDTH = int(os.getenv("PANEL_WIDTH", "825"))
PANEL_HEIGHT = int(os.getenv("PANEL_HEIGHT", "1200"))

# Detection resolution used to find each page's actual content bounding
# box before cropping (see _render_page_png). Deliberately higher than
# the panel needs so a tightly-cropped page still downsamples cleanly
# instead of upscaling a low-res crop.
CONTENT_DETECT_SCALE = 4.0

# A pixel this light or lighter (0-255, grayscale) counts as background
# when finding each page's content bounding box. Scanned scores vary
# page to page in how much margin surrounds the actual engraving —
# without cropping to content first, a page with more margin (e.g. a
# piece that ends partway down the page) renders its notation
# noticeably smaller than a page whose content runs edge to edge, even
# though both pages are the same physical size. Lower this if faint
# scan artifacts near page edges are being picked up as "content" and
# preventing a tight crop; raise it if genuinely light-but-real marks
# (soft pencil, faint slurs) are being cropped away.
CONTENT_WHITE_THRESHOLD = int(os.getenv("CONTENT_WHITE_THRESHOLD", "250"))

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
    """Render one page (1-indexed) of pdf_path to a grayscale PNG, cropped
    to its actual printed content and scaled to fit the panel. Raises
    HTTPException(404) if page_number is out of range for the actual PDF
    (belt-and-suspenders alongside the score.page_count check in
    get_page — that column can be null/stale for a score ingested before
    page_count existed or ingested incorrectly)."""
    doc = fitz.open(pdf_path)
    try:
        if page_number < 1 or page_number > doc.page_count:
            raise HTTPException(
                status_code=404,
                detail=f"Page {page_number} out of range (1-{doc.page_count})",
            )

        page = doc.load_page(page_number - 1)  # fitz pages are 0-indexed

        # Render at a higher resolution than the panel needs so cropping
        # to content below still leaves enough pixels to downsample
        # cleanly, then find the bounding box of everything that isn't
        # near-white — i.e. the actual printed music, ignoring however
        # much blank margin this particular page happens to have.
        matrix = fitz.Matrix(CONTENT_DETECT_SCALE, CONTENT_DETECT_SCALE)
        pix = page.get_pixmap(matrix=matrix, colorspace=fitz.csGRAY)
        img = Image.frombytes("L", (pix.width, pix.height), pix.samples)

        bbox = Image.eval(img, lambda p: 0 if p >= CONTENT_WHITE_THRESHOLD else 255).getbbox()
        if bbox:
            # Small breathing room so notation doesn't touch the panel's
            # edge exactly — proportional to image size so it scales
            # sensibly across different page sizes/scan resolutions.
            pad = round(0.015 * min(img.width, img.height))
            left = max(bbox[0] - pad, 0)
            top = max(bbox[1] - pad, 0)
            right = min(bbox[2] + pad, img.width)
            bottom = min(bbox[3] + pad, img.height)
            img = img.crop((left, top, right, bottom))
        # bbox is None for a genuinely blank page — fall back to the
        # full (blank) render rather than crashing on an empty crop.

        # Scale by whichever dimension is the binding constraint so the
        # cropped content fits inside the panel box without distortion.
        scale = min(PANEL_WIDTH / img.width, PANEL_HEIGHT / img.height)
        target_size = (
            max(1, round(img.width * scale)),
            max(1, round(img.height * scale)),
        )
        img = img.resize(target_size, Image.LANCZOS)

        import io
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
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