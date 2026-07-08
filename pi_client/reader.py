"""
Main entry point for the Pi e-ink display client. Ties together:
  - api_client:     fetch page images + score/setlist metadata from the FastAPI backend
  - display_driver: push images to the Waveshare/IT8951 panel
  - pedal_input:    AirTurn pedal taps drive page turns
  - state:          persist current position so a restart resumes where it left off

Two modes:

    python reader.py --score-id 12       # single score
    python reader.py --setlist-id 3      # whole setlist, in order

In setlist mode, next_page() advances past the current item's last page
(its page_end, or the end of the whole score if the item has no
page_start/page_end) straight into the next item — no separate "next
piece" pedal action needed. prev_page() does the same in reverse. Single-
score mode behaves exactly as before.

There's no on-panel picker yet (browsing/searching the library from the
panel itself) — pick the starting score/setlist with --score-id or
--setlist-id the first time. Subsequent runs resume the last position
automatically; omit both flags once state exists. Use `python -m ...` or
`python reader.py` from within this directory so the local config/
api_client/etc. imports resolve.
"""
import argparse
import threading

from api_client import ApiError, get_page_image, get_score, get_setlist
from display_driver import EinkDisplay
from pedal_input import listen
from state import load_state, save_state


class Reader:
    """Drives the e-ink display through a sequence of items. In
    single-score mode `items` is a synthetic one-item list built from
    the score's own metadata, so next_page/prev_page share identical
    boundary logic in both modes."""

    def __init__(self, items: list[dict], item_index: int, page_number: int,
                 setlist_id: int | None = None):
        self.items = items
        self.item_index = item_index
        self.page_number = page_number
        self.setlist_id = setlist_id
        self.display = EinkDisplay()
        # Guards state against a next/prev race if pedal taps arrive
        # faster than a page can render — pedal_input.listen calls these
        # from its own read loop.
        self._lock = threading.Lock()

    @property
    def current_item(self) -> dict:
        return self.items[self.item_index]

    @staticmethod
    def bounds(item: dict) -> tuple[int, int]:
        """(first, last) page for an item — page_start/page_end if set
        (an excerpt), otherwise the whole score (1..page_count). Falls
        back to (1, 1) if page_count is unknown so a stale/missing
        count never raises instead of just under-advancing."""
        start = item.get("page_start") or 1
        end = item.get("page_end") or item.get("page_count") or start
        return start, end

    def show_current_page(self):
        item = self.current_item
        try:
            png = get_page_image(item["score_id"], self.page_number)
        except ApiError as e:
            print(f"[reader] page fetch failed: {e}")
            self.display.show_message(f"Couldn't load page {self.page_number}:\n{e}")
            return
        self.display.show_page(png)
        save_state(
            score_id=item["score_id"],
            page_number=self.page_number,
            setlist_id=self.setlist_id,
            item_index=self.item_index if self.setlist_id is not None else None,
        )

    def next_page(self):
        with self._lock:
            _, last = self.bounds(self.current_item)
            if self.page_number < last:
                self.page_number += 1
            elif self.item_index < len(self.items) - 1:
                self.item_index += 1
                self.page_number, _ = self.bounds(self.current_item)
            else:
                return  # end of setlist / score — pedal tap is a no-op
            self.show_current_page()

    def prev_page(self):
        with self._lock:
            first, _ = self.bounds(self.current_item)
            if self.page_number > first:
                self.page_number -= 1
            elif self.item_index > 0:
                self.item_index -= 1
                _, self.page_number = self.bounds(self.current_item)
            else:
                return  # start of setlist / score — pedal tap is a no-op
            self.show_current_page()

    def run(self):
        self.show_current_page()
        listen(on_next=self.next_page, on_prev=self.prev_page)


def _single_score_items(score_id: int) -> list[dict]:
    score = get_score(score_id)
    return [{
        "score_id": score_id,
        "page_start": None,
        "page_end": None,
        "page_count": score.get("page_count"),
    }]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--score-id", type=int, default=None,
                         help="Open a single score (overrides saved state)")
    parser.add_argument("--setlist-id", type=int, default=None,
                         help="Open a whole setlist, in order (overrides saved state)")
    parser.add_argument("--page", type=int, default=None,
                         help="Page number to open (overrides saved state)")
    args = parser.parse_args()

    if args.score_id is not None and args.setlist_id is not None:
        raise SystemExit("Pass --score-id or --setlist-id, not both.")

    saved = load_state()

    setlist_id = args.setlist_id if args.setlist_id is not None else saved.get("setlist_id")
    score_id = args.score_id if args.score_id is not None else saved.get("score_id")

    # Explicit --score-id drops any previously saved setlist position —
    # otherwise a stale setlist_id in state would win below.
    if args.score_id is not None:
        setlist_id = None

    if setlist_id is not None:
        try:
            setlist = get_setlist(setlist_id)
        except ApiError as e:
            raise SystemExit(f"Couldn't load setlist {setlist_id}: {e}")

        items = setlist["items"]
        if not items:
            raise SystemExit(f"Setlist {setlist_id} ('{setlist['title']}') has no items yet.")

        item_index = saved.get("item_index") or 0
        if not (0 <= item_index < len(items)):
            item_index = 0

        page_number = args.page if args.page is not None else saved.get("page_number")
        if page_number is None:
            page_number, _ = Reader.bounds(items[item_index])

        Reader(items, item_index, page_number, setlist_id=setlist_id).run()
        return

    if score_id is None:
        raise SystemExit(
            "No score or setlist selected and no saved state found. Pass "
            "--score-id or --setlist-id the first time (GET /scores/ or "
            "GET /setlists/ on the backend lists ids)."
        )

    page_number = args.page if args.page is not None else (saved.get("page_number") or 1)
    Reader(_single_score_items(score_id), 0, page_number).run()


if __name__ == "__main__":
    main()
