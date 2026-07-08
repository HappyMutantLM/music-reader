"""
renaming.py — the core "messy filename -> normalized filename" transform,
shared between:

  - rename_tool.py       (repo root; manual batch cleanup of legacy raw
                           scans, with its own SKIP_FILES allow-list)
  - dropbox_processor.py (app/; automatic processing of new drops into
                           music_dropbox, no allow-list needed since every
                           file it sees is new)

Pulled out of rename_tool.py so both callers share one implementation
instead of drifting apart — same reasoning as naming.py's own docstring
(single source of truth for composer/instrument/category vocabulary).
propose_filename() is the pure transform; anything caller-specific (like
rename_tool.py's SKIP_FILES short-circuit for already-correct legacy
files) stays in the caller.
"""

import re

from naming import (
    OPUS_RE, VOLUME_RE, MOVEMENT_RE, BWV_RE, KV_RE,
    clean, to_camel, detect_category, find_category_keyword,
    detect_composer, detect_instrument, extract_pattern,
)


def propose_filename(filename: str) -> str | None:
    """Given a raw (un-normalized) PDF filename, return the normalized
    Composer-Title-Instrument-Opus-Volume.pdf form, or None if nothing
    usable could be extracted."""
    if not filename.lower().endswith(".pdf"):
        return None

    name = filename[:-4]

    # Normalize separators
    name = re.sub(r"[-_]+", " ", name)
    name = clean(name)
    name_lower = name.lower()

    # Detect category
    category = detect_category(name_lower)

    # Strip only the specific keyword that triggered category detection —
    # see naming.find_category_keyword()'s docstring for why not the whole
    # synonym list.
    matched_kw = find_category_keyword(name_lower, category)
    if matched_kw:
        name = re.sub(rf"\b{re.escape(matched_kw)}\b", "", name, count=1, flags=re.IGNORECASE)
    name = clean(name)

    # Extract structured tokens
    opus,     name = extract_pattern(name, OPUS_RE,     "Op{0}")
    volume,   name = extract_pattern(name, VOLUME_RE,   "{0}{1}")
    movement, name = extract_pattern(name, MOVEMENT_RE, "Mvt{1}")
    bwv,      name = extract_pattern(name, BWV_RE,      "BWV{0}")
    kv,       name = extract_pattern(name, KV_RE,       "KV{0}")

    # Split remaining into parts
    parts = [p for p in name.split() if p]

    # Detect composer and instrument
    composer,   parts = detect_composer(parts)
    instrument, parts = detect_instrument(parts)

    # Remaining parts form the title
    title = to_camel(" ".join(parts)) if parts else None

    # ── Build new filename ────────────────────────────────────
    if category == "repertoire":
        segments = [composer, title, instrument,
                    bwv or kv or opus, volume, movement]
    elif category in ("method", "etude", "technique"):
        # Include title so leftover descriptive words (e.g. "Scales",
        # "Fundamentals" after the category marker is stripped) aren't
        # silently dropped.
        segments = [category.capitalize(), composer, instrument, title,
                    opus or bwv or kv, volume]
    elif category in ("orch", "excerpt"):
        segments = [category.capitalize(), composer, title,
                    instrument, bwv or kv, movement]
    else:
        segments = [composer, title, instrument]

    segments = [s for s in segments if s]

    if not segments:
        return None

    return "-".join(segments) + ".pdf"