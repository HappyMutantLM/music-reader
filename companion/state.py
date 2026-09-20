"""Companion display state. Deliberately keeps two things separate:

  - Local browsing state (view, cursor_index): only this device cares,
    changes instantly on a button press, never touches the network.
  - now_playing_score_id: shared/global (setlist_score.id), updated by the
    background poll thread. Only used to decide whether to show the "now
    playing" badge — never drives what the guest is currently looking at.

A guest flipping ahead to read about piece 4 should never get yanked back
to whatever the performer is playing, and shouldn't need a round trip to
do it — see routers/companion.py's module docstring for the backend half
of this design.
"""

import threading

VIEW_LIST = "list"
VIEW_DETAIL = "detail"


class AppState:
    def __init__(self, program):
        self._lock = threading.Lock()
        self.program = program              # {"name": ..., "items": [...]}
        self.view = VIEW_LIST
        self.cursor_index = 0
        self.now_playing_score_id = None
        self.dirty = True                   # set whenever something needs a redraw

    @property
    def items(self):
        return self.program.get("items", [])

    @property
    def current_item(self):
        if not self.items:
            return None
        return self.items[self.cursor_index]

    def move_cursor(self, delta):
        if not self.items:
            return
        with self._lock:
            self.cursor_index = (self.cursor_index + delta) % len(self.items)
            self.dirty = True

    def select(self):
        with self._lock:
            self.view = VIEW_DETAIL if self.view == VIEW_LIST else VIEW_LIST
            self.dirty = True

    def set_now_playing(self, setlist_score_id):
        with self._lock:
            if setlist_score_id != self.now_playing_score_id:
                self.now_playing_score_id = setlist_score_id
                self.dirty = True

    def take_dirty(self):
        """Returns True and clears the flag if a redraw is owed."""
        with self._lock:
            was_dirty = self.dirty
            self.dirty = False
            return was_dirty
