import os
import re
import sys

# ── Make app/naming.py importable (repo root -> app/) ───────────────────────
# rename_tool.py lives at the repo root; naming.py lives in app/, imported
# flat (matching the convention app/ingest.py already uses for its own
# sibling imports, e.g. `from database import get_db`).
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "app"))

from naming import (  # noqa: E402
    CATEGORY_PREFIXES,
    OPUS_RE, VOLUME_RE, MOVEMENT_RE, BWV_RE, KV_RE,
    clean, to_camel, detect_category, find_category_keyword,
    detect_composer, detect_instrument, extract_pattern,
)

# ── Configuration ────────────────────────────────────────────
MUSIC_DIR = '/Users/leilamureebe/Library/CloudStorage/BeeStation-KelvinArchive/Music/Scanned Music/Raw Scans'
DRY_RUN   = True                          # set False to actually rename
# ─────────────────────────────────────────────────────────────

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
}


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

    # Strip only the specific keyword that triggered category detection —
    # not the whole category's synonym list, and not other categories'
    # lists either. Some synonyms (e.g. "scales", "fundamentals" under
    # "technique") double as legitimate title content in specific files;
    # stripping every synonym unconditionally would delete real title
    # words, not just the category marker.
    matched_kw = find_category_keyword(name_lower, category)
    if matched_kw:
        name = re.sub(re.escape(matched_kw), "", name, count=1, flags=re.IGNORECASE)
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
        # silently dropped — previously this branch had no title slot at
        # all, so any such words computed by detect_composer/detect_instrument
        # leftover logic just vanished from the final filename.
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