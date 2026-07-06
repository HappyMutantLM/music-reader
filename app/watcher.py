import os
import time
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from ingest import ingest_file

PDF_DIR = os.getenv("PDF_DIR", "/pdf")
LOG_DIR = os.getenv("LOG_DIR", "/logs")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [watcher] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "watcher.log")),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger(__name__)


class PDFHandler(FileSystemEventHandler):
    """Watch for new or moved-in PDF files and ingest them."""

    def on_created(self, event):
        if not event.is_directory and event.src_path.lower().endswith(".pdf"):
            self._handle(event.src_path)

    def on_moved(self, event):
        # Catches files moved/copied into the watch folder
        if not event.is_directory and event.dest_path.lower().endswith(".pdf"):
            self._handle(event.dest_path)

    def _handle(self, full_path: str):
        filename = os.path.basename(full_path)
        log.info(f"Detected: {filename}")

        # Wait for file to finish writing before ingesting
        self._wait_for_stable(full_path)

        result = ingest_file(filename)
        log.info(f"{result['status'].upper()}: {filename}")
        if result.get("meta"):
            log.info(f"  category={result['meta']['category']} "
                     f"composer={result['meta']['composer_name']} "
                     f"instrument={result['meta']['instrument']}")


    def _wait_for_stable(self, path: str, interval: float = 1.0, retries: int = 10):
        """
        Poll file size until stable — handles slow network copies
        from BeeStation dropping large PDFs.
        """
        prev_size = -1
        for _ in range(retries):
            try:
                curr_size = os.path.getsize(path)
            except FileNotFoundError:
                time.sleep(interval)
                continue
            if curr_size == prev_size:
                return  # stable
            prev_size = curr_size
            time.sleep(interval)
        log.warning(f"File may not be fully written: {path}")


def start_watcher():
    log.info(f"Watching {PDF_DIR} for new PDFs...")
    handler = PDFHandler()
    observer = Observer()
    observer.schedule(handler, PDF_DIR, recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    start_watcher()