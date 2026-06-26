import os
import re

# ── Configuration ────────────────────────────────────────────
MUSIC_DIR = '/Users/leilamureebe/Library/CloudStorage/BeeStation-KelvinArchive/Music/Scanned Music/Raw Scans'
DRY_RUN   = False                         # set False to actually rename
# ─────────────────────────────────────────────────────────────

# Known composers — expand as needed
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

# Known instruments
INSTRUMENTS = {
    "bass", "piano", "violin", "viola", "cello",
    "flute", "oboe", "clarinet", "trumpet", "horn", "organ",
    "satb", "lute",
}

# Prefix detection
CATEGORY_PREFIXES = {
    "method":    ["method", "meth"],
    "etude":     ["etude", "étude", "study", "studies"],
    "technique": ["technique", "tech", "exercise", "exercises",
                  "scale", "scales", "arpeggios", "cadences", "fundamentals"],
    "orch":      ["orch", "orchestra", "orchestral", "symphony", "symphonie"],
    "excerpt":   ["excerpt", "excerpts", "audition"],
}

# Tokens to preserve exact casing
PRESERVE_CASE = {
    "js": "JS", "cpe": "CPE", "wa": "WA",
    "bwv": "BWV", "kv": "KV", "op": "Op",
    "vol": "Vol", "book": "Book",
    "i": "I", "ii": "II", "iii": "III", "iv": "IV",
    "v": "V", "vi": "VI", "vii": "VII", "viii": "VIII",
}

# Files to skip — already correctly named

SKIP_FILES = {
    "Beethoven-Pathetique-Piano-Op13.pdf",
    "Technique-Brahms-Piano-Op51.pdf",
    "Method-Vance-Bass-Vol1.pdf",
    "Method-Vance-Bass-Vol2.pdf",
    "Method-Vance-Bass-Vol3.pdf",
    "Technique-Bass-Fundamentals.pdf",
    "Technique-Bass-Scales.pdf",
    "Technique-Bass-Scale.pdf",
    "Debussy-ClairDeLune-Piano.pdf",
    "Debussy-ClairDeLune-Cello-Part.pdf",
    "Janacek-MadonnaOfFrydek-Piano.pdf",
    "Janacek-OnAnOvergrownPath-Piano.pdf",
    "BachJS-EnglishSuite2-Piano.pdf",
    "BachJS-EnglishSuites1to3-Piano.pdf",
    "BachJS-Arioso-Full-Score.pdf",
    "BachJS-Bouree-Piano-BWV996.pdf",
    "BachJS-Sonata-Flute-BWV1034-Part.pdf",
    "BachJS-Sonata-Flute-BWV1034-Score.pdf",
    "BachJS-ToccataFugue-Organ-DMinor.pdf",
    "BachJS-WTC1-Piano-Urtext.pdf",
    "BachJS-Partitas1to3-Piano.pdf",
    "BachJS-Partitas4to6-Piano.pdf",
    "BachCPE-Sonata-Flute-W65.pdf",
    "Orch-BachJS-Suite2-BWV1067.pdf",
    "Chopin-Raindrop-Piano-Op28No15.pdf",
    "Gounod-AveMaria-Piano-F.pdf",
    "Technique-Piano-ArtOfFingerDexterity.pdf",
    "Method-Simandl-Bass-Book1.pdf",
    "BachJS-Inventions15-Piano.pdf",
    "BillyJoel-PianoMan-Piano.pdf",
    "SaintSaens-LeCygne-Cello.pdf",
    "BachJS-Inventions15-Piano.pdf"
}

# Opus pattern
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
            return to_camel(part), parts[:i] + parts[i+1:]
    return None, parts


def detect_instrument(parts: list) -> tuple:
    """Find instrument in parts, return (instrument, remaining_parts)."""
    for i, part in enumerate(parts):
        if part.lower() in INSTRUMENTS:
            return to_camel(part), parts[:i] + parts[i+1:]
    return None, parts


def extract_pattern(text: str, pattern: re.Pattern, fmt: str) -> tuple:
    m = pattern.search(text)
    if m:
        value = fmt.format(*m.groups())
        text = text[:m.start()] + text[m.end():]
        return value, text.strip()
    return None, text


def propose_rename(filename: str) -> str | None:
    if not filename.lower().endswith(".pdf"):
        return None

    # Skip already-correct files
    if filename in SKIP_FILES:
        return filename  # signals "already correct"

    name = filename[:-4]

    # Normalize separators
    name = re.sub(r"[-_]+", " ", name)
    name = clean(name)
    name_lower = name.lower()

    # Detect category
    category = detect_category(name_lower)

    # Strip category keywords
    for keywords in CATEGORY_PREFIXES.values():
        for kw in keywords:
            name = re.sub(re.escape(kw), "", name, flags=re.IGNORECASE)
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
        segments = [category.capitalize(), composer, instrument,
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


def run(music_dir: str = MUSIC_DIR, dry_run: bool = DRY_RUN):
    if not os.path.exists(music_dir):
        print(f"Directory not found: {music_dir}")
        return

    # Recursive file collection
    files = []
    for root, dirs, filenames in os.walk(music_dir):
        for f in sorted(filenames):
            if f.lower().endswith(".pdf"):
                files.append((root, f))

    if not files:
        print("No PDF files found.")
        return

    renames   = []
    unchanged = []
    skipped   = []

    for root, filename in files:
        proposed = propose_rename(filename)

        if proposed is None:
            skipped.append((root, filename))
        elif proposed == filename:
            unchanged.append(filename)
        else:
            renames.append((root, filename, proposed))

    # ── Report ────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"DRY RUN: {dry_run}")
    print(f"Directory: {music_dir}")
    print(f"{'='*60}\n")

    if renames:
        print(f"── PROPOSED RENAMES ({len(renames)}) ──")
        for root, old, new in renames:
            print(f"  {old}")
            print(f"  → {new}\n")

    if unchanged:
        print(f"── ALREADY CORRECT ({len(unchanged)}) ──")
        for f in unchanged:
            print(f"  ✓ {f}")
        print()

    if skipped:
        print(f"── COULD NOT PARSE ({len(skipped)}) ──")
        for root, f in skipped:
            print(f"  ? {f}")
        print()

    print(f"{'='*60}")
    print(f"Total: {len(files)} | Rename: {len(renames)} | "
          f"OK: {len(unchanged)} | Skipped: {len(skipped)}")
    print(f"{'='*60}\n")

    # ── Execute renames ───────────────────────────────────────
    if not dry_run and renames:
        confirm = input("Proceed with renames? (yes/no): ")
        if confirm.strip().lower() == "yes":
            for root, old, new in renames:
                src = os.path.join(root, old)
                dst = os.path.join(root, new)
                if os.path.exists(dst):
                    print(f"SKIP (destination exists): {new}")
                else:
                    os.rename(src, dst)
                    print(f"RENAMED: {old} → {new}")
        else:
            print("Aborted.")


if __name__ == "__main__":
    run()