import os
import re
import sys

# ── Make app/naming.py importable (repo root -> app/) ───────────────────────
# rename_tool.py lives at the repo root; naming.py lives in app/, imported
# flat (matching the convention app/ingest.py already uses for its own
# sibling imports, e.g. `from database import get_db`).
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "app"))

from renaming import propose_filename  # noqa: E402

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

    # Core transform lives in app/renaming.py now, shared with
    # dropbox_processor.py — see that module's docstring.
    return propose_filename(filename)


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