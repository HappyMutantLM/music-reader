"""Persists the reader's position to disk so a restart or power cycle
resumes on the same page instead of always booting to a blank screen.
Tracks either a single score (setlist_id null) or a position within a
setlist (setlist_id + item_index)."""
import json
import os

from config import STATE_FILE

_EMPTY_STATE = {
    "setlist_id": None,
    "item_index": None,
    "score_id": None,
    "page_number": None,
}


def load_state() -> dict:
    """Returns {'setlist_id': int|None, 'item_index': int|None,
    'score_id': int|None, 'page_number': int|None}. Falls back to an
    empty state on missing or corrupt state file — a bad state file
    should never prevent the reader from starting. Also safe against
    older state files written before setlist support existed (missing
    keys just come back None via .get()).
    """
    if not os.path.exists(STATE_FILE):
        return dict(_EMPTY_STATE)
    try:
        with open(STATE_FILE) as f:
            data = json.load(f)
        return {
            "setlist_id": data.get("setlist_id"),
            "item_index": data.get("item_index"),
            "score_id": data.get("score_id"),
            "page_number": data.get("page_number"),
        }
    except (json.JSONDecodeError, OSError):
        return dict(_EMPTY_STATE)


def save_state(score_id: int, page_number: int, setlist_id: int | None = None,
                item_index: int | None = None):
    # Write to a temp file + os.replace (atomic on the same filesystem)
    # rather than writing STATE_FILE directly — avoids leaving a
    # half-written, unparseable state file if power drops mid-write.
    tmp_path = STATE_FILE + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump({
            "setlist_id": setlist_id,
            "item_index": item_index,
            "score_id": score_id,
            "page_number": page_number,
        }, f)
    os.replace(tmp_path, STATE_FILE)
