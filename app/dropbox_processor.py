"""
dropbox_processor.py — watches music_dropbox for newly-added PDFs and files
them automatically:

  1. Wait for the file to finish copying (large scans over network shares
     write slowly — same stability-poll trick as watcher.py).
  2. Propose a normalized name via renaming.propose_filename(), then parse
     that proposal with ingest_core.parse_filename() to see what it
     understood (composer, instrument, warnings, ...).
  3. Confident match -> rename + move into PDF_DIR/<Category>/<Composer>/.
     PDF_DIR is already watched recursively by watcher.py (see app/watcher.py),
     so this move alone triggers ingestion — dropbox_processor.py does not
     touch the database directly.
  4. Anything else -> move into NEEDS_REVIEW_DIR with a sidecar .txt
     explaining why, so nothing is silently lost or mis-filed.

Deliberately a separate long-running process from the FastAPI app (and
from its embedded PDF_DIR watcher thread) — a crash or restart here has no
effect on API uptime, and vice versa. See docker-compose.yml for how it's
run as its own container.
"""

import hashlib
import logging
import os
import shutil
import time

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from renaming import propose_filename
from ingest_core import parse_filename

DROPBOX_DIR = os.getenv("DROPBOX_DIR", "/dropbox")
PDF_DIR = os.getenv("PDF_DIR", "/pdf")
LOG_DIR = os.getenv("LOG_DIR", "/logs")
NEEDS_REVIEW_DIR = os.getenv(
    "NEEDS_REVIEW_DIR", os.path.join(DROPBOX_DIR, "needs_review")
)

os.makedirs(NEEDS_REVIEW_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [dropbox] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "dropbox_processor.log")),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# Ledger of already-handled files (by content hash), so a mid-run restart
# doesn't reprocess a file whose move it already completed. Persisted as a
# flat file next to the log so it survives container restarts.
LEDGER_PATH = os.path.join(LOG_DIR, "dropbox_processed.txt")


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_ledger() -> set:
    if not os.path.exists(LEDGER_PATH):
        return set()
    with open(LEDGER_PATH) as f:
        return {line.strip() for line in f if line.strip()}


def _record_ledger(file_hash: str):
    with open(LEDGER_PATH, "a") as f:
        f.write(file_hash + "\n")


def _is_confident(proposed: str | None, meta: dict | None) -> bool:
    """True if we'd trust this to auto-file without a human glancing at it
    first. Deliberately conservative — false negatives just mean an extra
    file in needs_review/, false positives mean a mis-filed score."""
    if proposed is None or meta is None:
        return False
    if meta["warnings"]:
        return False
    if meta.get("title") is None and meta.get("composer_name") is None:
        # Nothing meaningful was extracted at all.
        return False
    return True


def _dest_subdir(meta: dict) -> str:
    """Category/Composer folder, matching the existing human-organization
    convention (Repertoire/Bach/, Method/Simandl/, ...). Falls back to a
    catch-all when composer is absent (e.g. a generic technique book) —
    this is purely for human browsing; SQLite is the real retrieval layer,
    so an imperfect folder guess here never breaks lookup."""
    category = meta.get("category") or "Repertoire"
    composer = meta.get("composer_name") or "_Uncategorized"
    return os.path.join(PDF_DIR, category, composer)


class DropboxHandler(FileSystemEventHandler):
    def __init__(self):
        self.ledger = _load_ledger()

    def on_created(self, event):
        if not event.is_directory and event.src_path.lower().endswith(".pdf"):
            self._handle(event.src_path)

    def on_moved(self, event):
        if not event.is_directory and event.dest_path.lower().endswith(".pdf"):
            self._handle(event.dest_path)

    def _in_needs_review(self, path: str) -> bool:
        review_root = os.path.abspath(NEEDS_REVIEW_DIR) + os.sep
        return os.path.abspath(path).startswith(review_root)

    def _wait_for_stable(self, path: str, interval: float = 1.0, retries: int = 10):
        """Poll file size until stable — handles slow network copies onto
        the dropbox share."""
        prev_size = -1
        for _ in range(retries):
            try:
                curr_size = os.path.getsize(path)
            except FileNotFoundError:
                time.sleep(interval)
                continue
            if curr_size == prev_size:
                return
            prev_size = curr_size
            time.sleep(interval)
        log.warning(f"File may not be fully written: {path}")

    def _handle(self, src_path: str):
        # needs_review/ lives inside DROPBOX_DIR (watched recursively), so
        # files we move there ourselves would otherwise re-trigger this
        # handler. Ignore anything already under it.
        if self._in_needs_review(src_path):
            return

        original_name = os.path.basename(src_path)
        log.info(f"Detected: {original_name}")
        self._wait_for_stable(src_path)

        if not os.path.exists(src_path):
            log.warning(f"Vanished before processing: {original_name}")
            return

        file_hash = _sha256(src_path)
        if file_hash in self.ledger:
            log.info(f"Already processed (hash match), skipping: {original_name}")
            return

        proposed = propose_filename(original_name)
        meta = parse_filename(proposed) if proposed else None

        if _is_confident(proposed, meta):
            self._file_it(src_path, original_name, proposed, meta, file_hash)
        else:
            if proposed is None:
                reason = "could not parse filename"
            elif meta["warnings"]:
                reason = "; ".join(meta["warnings"])
            else:
                reason = "no usable title/composer detected"
            self._send_to_review(src_path, original_name, proposed, meta, reason)
            self.ledger.add(file_hash)
            _record_ledger(file_hash)

    def _file_it(self, src_path, original_name, proposed, meta, file_hash):
        dest_dir = _dest_subdir(meta)
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, proposed)

        if os.path.exists(dest_path):
            log.warning(
                f"Destination already exists, sending to review instead: {proposed}"
            )
            self._send_to_review(
                src_path, original_name, proposed, meta,
                reason="destination filename collision",
            )
            self.ledger.add(file_hash)
            _record_ledger(file_hash)
            return

        shutil.move(src_path, dest_path)
        log.info(f"FILED: {original_name} -> {dest_path}")
        self.ledger.add(file_hash)
        _record_ledger(file_hash)

    def _send_to_review(self, src_path, original_name, proposed, meta, reason):
        dest_name = proposed or original_name
        dest_path = os.path.join(NEEDS_REVIEW_DIR, dest_name)
        base, ext = os.path.splitext(dest_path)
        n = 1
        while os.path.exists(dest_path):
            dest_path = f"{base}_{n}{ext}"
            n += 1

        shutil.move(src_path, dest_path)

        note_path = os.path.splitext(dest_path)[0] + ".txt"
        with open(note_path, "w") as f:
            f.write(f"Original filename: {original_name}\n")
            f.write(f"Proposed rename:   {proposed}\n")
            f.write(f"Reason for review: {reason}\n")
            if meta:
                f.write(f"Detected metadata: {meta}\n")

        log.warning(f"NEEDS REVIEW: {original_name} -> {dest_path} ({reason})")


def start_dropbox_processor():
    log.info(f"Watching {DROPBOX_DIR} for new sheet music...")
    handler = DropboxHandler()
    observer = Observer()
    observer.schedule(handler, DROPBOX_DIR, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    start_dropbox_processor()
