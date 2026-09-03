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
# Multi-word names (an initial + surname, a hyphenated surname whose hyphen
# renaming.py has already turned into a space by the time this is checked,
# etc.) are stored glued with no separator — e.g. "lpierce", not "l pierce"
# or "l-pierce" — because detect_composer() below matches by gluing
# candidate word-groups together the same way before comparing. Where the
# word order in a raw filename might go either way, both orders are listed
# (see "lpierce"/"piercel") rather than betting on one.
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
    # Contemporary/local
    "pierce",
    # Multi-word (initial + surname), for when a scan happens to credit
    # the initial too — e.g. "L Pierce" or "Pierce L". Bare "pierce" above
    # already covers the common case of the surname alone.
    "lpierce", "piercel",
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
        elif not w.isupper() and not w.islower() and w[:1].isupper():
            # Already internally mixed-case (e.g. "ArtOfFingerDexterity" —
            # a glued compound title with no separators between words).
            # w.capitalize() would lowercase everything after the first
            # letter and destroy that structure, so leave it as-is instead.
            result.append(w)
        else:
            result.append(w.capitalize())
    return "".join(result)


def detect_category(name_lower: str) -> str:
    # Whole-word match, not substring — a bare `kw in name_lower` check
    # would false-positive on short keywords like "orch"/"tech"/"study"
    # appearing inside unrelated words (e.g. "Orchid" contains "orch").
    words = set(name_lower.split())
    for category, keywords in CATEGORY_PREFIXES.items():
        if words & set(keywords):
            return category
    return "repertoire"


def find_category_keyword(name_lower: str, category: str) -> str | None:
    """Return the specific keyword from CATEGORY_PREFIXES[category] that
    appears in name_lower, or None. Used to strip only the marker word that
    actually triggered category detection — not every synonym in that
    category's list. Some synonyms (e.g. "scales", "fundamentals" under
    "technique") double as legitimate title content in specific files, so
    blanket-stripping the whole keyword list would delete real title words
    rather than just the category marker.

    Whole-word match, same reasoning as detect_category() above."""
    words = name_lower.split()
    for kw in CATEGORY_PREFIXES.get(category, []):
        if kw in words:
            return kw
    return None


def detect_composer(parts: list) -> tuple:
    """Find composer in parts, return (composer, remaining_parts).

    Checks windows of 1 to 3 consecutive words (longest first) against
    COMPOSERS, comparing each window glued together with no separator —
    e.g. ["L", "Pierce"] is tested as "lpierce". Single-word entries still
    match exactly as before (a window of 1 glues to just that word), but
    this also catches a multi-word name as a unit — an initial + surname,
    or a hyphenated surname whose hyphen has already become a space by the
    time this runs (propose_filename() converts "-"/"_" to spaces before
    any detection happens) — instead of only ever being able to check one
    word at a time. Longest-window-first so a multi-word entry isn't
    pre-empted by a shorter single-word match sharing its first word.

    Composer names longer than 3 words are rare enough in practice not to
    bother widening this further; if one comes up, raise max_window.
    """
    max_window = min(3, len(parts))
    for window in range(max_window, 0, -1):
        for i in range(len(parts) - window + 1):
            candidate = parts[i:i + window]
            glued = "".join(candidate).lower()
            if glued in COMPOSERS:
                composer = to_camel(" ".join(candidate))
                remaining = parts[:i] + parts[i + window:]
                return composer, remaining
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
    positionally and doesn't otherwise validate against COMPOSERS.

    A multi-word composer ends up as a single glued token by the time it
    reaches here (detect_composer()/to_camel() glue candidate words with
    no separator, e.g. "LPierce"), so a plain lowercase lookup against the
    same glued COMPOSERS entries is still correct — no windowing needed on
    this side."""
    if not name:
        return False
    return name.lower() in COMPOSERS


def is_known_instrument(name: str) -> bool:
    """Same idea as is_known_composer(), for instrument tokens."""
    if not name:
        return False
    return name.lower() in INSTRUMENTS
