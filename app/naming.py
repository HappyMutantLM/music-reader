"""
naming.py — shared composer/category/instrument vocabulary and detection
logic used by both:

  - rename_tool.py   (fuzzy detection: raw scanned filename -> normalized name)
  - ingest.py        (positional parsing: normalized filename -> DB metadata,
                       via CATEGORY_MAP derived from CATEGORY_PREFIXES below)

Single source of truth so the two never drift apart. If you add a composer,
instrument, or category synonym, add it here once — both scripts pick it up.
"""

import re

# ── Known composers — expand as needed ─────────────────────────────────────
COMPOSERS = {
    "bach", "bachjs", "bachcpe",
    "beethoven", "brahms", "chopin", "debussy",
    "dvorak", "handel", "haydn", "mahler", "mozart", "prokofiev",
    "ravel", "schubert", "schumann", "shostakovich", "strauss",
    "tchaikovsky", "vivaldi", "wagner",
    "scriabin", "skrjabin", "satie", "rossini", "janacek",
    "gounod", "gershwin", "saint-saens", "saintsaens",
    # Bass repertoire
    "bottesini", "dragonetti", "koussevitzky", "rabbath", "vanhal",
    # Method/etude authors
    "simandl", "czerny", "hanon", "kreutzer", "popper", "kummer",
    "vance", "beringer", "manookian", "bastien",
    # Popular
    "billjoel", "billyjoel", "loureed", "queen", "joplin", "bowie",
    "comeau",
}

# ── Known instruments ───────────────────────────────────────────────────────
INSTRUMENTS = {
    "bass", "piano", "violin", "viola", "cello",
    "flute", "oboe", "clarinet", "trumpet", "horn", "organ",
    "satb", "lute",
}

# ── Category vocabulary (canonical) ─────────────────────────────────────────
# Keys are lowercase; keyword lists are synonyms used for fuzzy detection
# in raw filenames. capitalize() on the key gives the filename prefix
# (e.g. "method" -> "Method-...") and also the DB category label.
CATEGORY_PREFIXES = {
    "method":    ["method", "meth"],
    "etude":     ["etude", "étude", "study", "studies"],
    "technique": ["technique", "tech", "exercise", "exercises",
                  "scale", "scales", "arpeggios", "cadences", "fundamentals"],
    "orch":      ["orch", "orchestra", "orchestral", "symphony", "symphonie"],
    "excerpt":   ["excerpt", "excerpts", "audition"],
}

# Derived: used by ingest.py's parse_filename() to recognize an already-
# normalized filename's leading category token (e.g. "Method-Simandl-...").
# Adding a category to CATEGORY_PREFIXES above automatically adds it here —
# no need to touch ingest.py separately.
CATEGORY_MAP = {cat.capitalize(): cat.capitalize() for cat in CATEGORY_PREFIXES}

# ── Tokens to preserve exact casing ──────────────────────────────────────────
PRESERVE_CASE = {
    "js": "JS", "cpe": "CPE", "wa": "WA",
    "bwv": "BWV", "kv": "KV", "op": "Op",
    "vol": "Vol", "book": "Book",
    "i": "I", "ii": "II", "iii": "III", "iv": "IV",
    "v": "V", "vi": "VI", "vii": "VII", "viii": "VIII",
}

# ── Structured-token regex patterns ─────────────────────────────────────────
OPUS_RE     = re.compile(r"op\.?\s*(\d+)", re.IGNORECASE)
VOLUME_RE   = re.compile(r"(book|vol|volume|part|grade)\s*\.?(\d+)", re.IGNORECASE)
MOVEMENT_RE = re.compile(r"(mvt|mov|movement)\s*\.?(\d+)", re.IGNORECASE)
BWV_RE      = re.compile(r"bwv\s*(\d+)", re.IGNORECASE)
KV_RE       = re.compile(r"k\.?v?\.?\s*(\d+)", re.IGNORECASE)


def clean(s: str) -> str:
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def to_camel(s: str) -> str:
    """Convert string to CamelCase, preserving known tokens."""
    words = s.split()
    result = []
    for w in words:
        lower = w.lower()
        if lower in PRESERVE_CASE:
            result.append(PRESERVE_CASE[lower])
        else:
            result.append(w.capitalize())
    return "".join(result)


def detect_category(name_lower: str) -> str:
    for category, keywords in CATEGORY_PREFIXES.items():
        for kw in keywords:
            if kw in name_lower:
                return category
    return "repertoire"


def detect_composer(parts: list) -> tuple:
    """Find composer in parts, return (composer, remaining_parts)."""
    for i, part in enumerate(parts):
        if part.lower() in COMPOSERS:
            return to_camel(part), parts[:i] + parts[i + 1:]
    return None, parts


def detect_instrument(parts: list) -> tuple:
    """Find instrument in parts, return (instrument, remaining_parts)."""
    for i, part in enumerate(parts):
        if part.lower() in INSTRUMENTS:
            return to_camel(part), parts[:i] + parts[i + 1:]
    return None, parts


def extract_pattern(text: str, pattern: re.Pattern, fmt: str) -> tuple:
    m = pattern.search(text)
    if m:
        value = fmt.format(*m.groups())
        text = text[:m.start()] + text[m.end():]
        return value, text.strip()
    return None, text


def is_known_composer(name: str) -> bool:
    """Sanity-check helper for ingest.py: flag composer tokens that don't
    match the known list, since parse_filename() trusts filename structure
    positionally and doesn't otherwise validate against COMPOSERS."""
    if not name:
        return False
    return name.lower() in COMPOSERS


def is_known_instrument(name: str) -> bool:
    """Same idea as is_known_composer(), for instrument tokens."""
    if not name:
        return False
    return name.lower() in INSTRUMENTS