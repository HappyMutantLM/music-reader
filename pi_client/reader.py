"""
Main entry point for the Pi e-ink display client. Ties together:
  - api_client:     fetch page images + score metadata from the FastAPI backend
  - display_driver: push images to the Waveshare/IT8951 panel
  - pedal_input:    AirTurn pedal taps drive page turns
  - state:          persist current score/page so a restart resumes where it left off

There's no on-panel score picker yet (browsing/searching the library
from the panel itself) — pick the starting score with --score-id the
first time:

    python reader.py --score-id 12

Subsequent runs resume the last score/page automatically; omit
--score-id once state exists. Use `python -m ...` or `python reader.py`
from within this directory so the local config/api_client/etc. imports
resolve.
"""
import argparse
import threading

from api_client import ApiError, get_page_image, get_score
from display_driver import EinkDisplay
from pedal_input import listen
from state import load_state, save_state


class Reader:
    def __init__(self, score_id: int, page_number: int):
        self.score_id = score_id
        self.page_number = page_number
        self.page_count = None
        self.display = EinkDisplay()
        # Guards page_number/display against a next/prev race if pedal
        # taps arrive faster than a page can render — pedal_input.listen
        # calls these from its own read loop.
        self._lock = threading.Lock()

    def _refresh_page_count(self):
        try:
            score = get_score(self.score_id)
        except ApiError as e:
            print(f"[reader] couldn't fetch score metadata: {e}")
            return
        self.page_count = score.get("page_count")

    def show_current_page(self):
        try:
            png = get_page_image(self.score_id, self.page_number)
        except ApiError as e:
            print(f"[reader] page fetch failed: {e}")
            self.display.show_message(f"Couldn't load page {self.page_number}:\n{e}")
            return
        self.display.show_page(png)
        save_state(self.score_id, self.page_number)

    def next_page(self):
        with self._lock:
            if self.page_count and self.page_number >= self.page_count:
                return  # already on the last page — pedal tap is a no-op
            self.page_number += 1
            self.show_current_page()

    def prev_page(self):
        with self._lock:
            if self.page_number <= 1:
                return  # already on the first page — pedal tap is a no-op
            self.page_number -= 1
            self.show_current_page()

    def run(self):
        self._refresh_page_count()
        self.show_current_page()
        listen(on_next=self.next_page, on_prev=self.prev_page)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--score-id", type=int, default=None,
                         help="Score id to open (overrides saved state)")
    parser.add_argument("--page", type=int, default=None,
                         help="Page number to open (overrides saved state)")
    args = parser.parse_args()

    saved = load_state()
    score_id = args.score_id if args.score_id is not None else saved["score_id"]
    page_number = args.page if args.page is not None else saved["page_number"]

    if score_id is None:
        raise SystemExit(
            "No score selected and no saved state found. Pass --score-id "
            "the first time (GET /scores/ on the backend lists ids)."
        )

    Reader(score_id, page_number).run()


if __name__ == "__main__":
    main()
