"""Persists the reader's last (score_id, page_number) to disk so a
restart or power cycle resumes on the same page instead of always
booting to a blank screen."""
import json
import os

from config import STATE_FILE


def load_state() -> dict:
    """Returns {'score_id': int|None, 'page_number': int}. Falls back to
    an empty/blank state on missing or corrupt state file — a bad state
    file should never prevent the reader from starting."""
    if not os.path.exists(STATE_FILE):
        return {"score_id": None, "page_number": 1}
    try:
        with open(STATE_FILE) as f:
            data = json.load(f)
        return {
            "score_id": data.get("score_id"),
            "page_number": data.get("page_number", 1),
        }
    except (json.JSONDecodeError, OSError):
        return {"score_id": None, "page_number": 1}


def save_state(score_id: int, page_number: int):
    # Write to a temp file + os.replace (atomic on the same filesystem)
    # rather than writing STATE_FILE directly — avoids leaving a
    # half-written, unparseable state file if power drops mid-write.
    tmp_path = STATE_FILE + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump({"score_id": score_id, "page_number": page_number}, f)
    os.replace(tmp_path, STATE_FILE)
