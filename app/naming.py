"""
naming.py — shared composer/category/instrument vocabulary and detection logic.
"""

import re

# ── Known composers ────────────────────────────────────────────────────────
COMPOSERS = {
    "bach", "bachjs", "jsbach", "bachcpe", "cpebach",
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
    "lpierce", "piercel",
}

# ── Known instruments ───────────────────────────────────────────────────────
INSTRUMENTS = {
    "bass", "piano", "violin", "viola", "cello",
    "flute", "oboe", "clarinet", "trumpet", "horn", "organ",
    "satb", "lute",
}

# ── Category vocabulary (canonical) ─────────────────────────────────────────
CATEGORY_PREFIXES = {
    "method":    ["method", "meth"],
    "etude":     ["etude", "étude", "study", "studies"],
    "technique": ["technique", "tech", "exercise", "exercises",
                  "scale", "scales", "arpeggios", "cadences", "fundamentals"],
    "orch":      ["orch", "orchestra", "orchestral", "symphony", "symphonie"],
    "excerpt":   ["excerpt", "excerpts", "audition"],
}

CATEGORY_MAP = {cat.capitalize(): cat.capitalize() for cat in CATEGORY_PREFIXES}

# ── Tokens to preserve exact casing ──────────────────────────────────────────
PRESERVE_CASE = {
    "js": "JS", "cpe": "CPE", "wa": "WA",
    "bwv": "BWV", "kv": "KV", "op": "Op",
    "vol": "Vol", "book": "Book",
    "i": "I", "ii": "II", "iii": "III", "iv": "IV",
    "v": "V", "vi": "VI", "vii": "VII", "viii": "VIII",
}

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
    words = s.split()
    result = []
    for w in words:
        lower = w.lower()
        if lower in PRESERVE_CASE:
            result.append(PRESERVE_CASE[lower])
        elif not w.isupper() and not w.islower() and w[:1].isupper():
            result.append(w)
        else:
            result.append(w.capitalize())
    return "".join(result)


def detect_category(name_lower: str) -> str:
    words = set(name_lower.split())
    for category, keywords in CATEGORY_PREFIXES.items():
        if words & set(keywords):
            return category
    return "repertoire"


def find_category_keyword(name_lower: str, category: str) -> str | None:
    words = name_lower.split()
    for kw in CATEGORY_PREFIXES.get(category, []):
        if kw in words:
            return kw
    return None


def detect_composer(parts: list) -> tuple:
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
    if not name:
        return False
    return name.lower() in COMPOSERS


def is_known_instrument(name: str) -> bool:
    if not name:
        return False
    return name.lower() in INSTRUMENTS
