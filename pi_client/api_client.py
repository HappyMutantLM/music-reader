"""Thin HTTP client for the FastAPI backend running on the NAS."""
import time

import requests

from config import SERVER_URL, REQUEST_TIMEOUT

# Retry/backoff for transient connection failures (NAS asleep, WiFi drop
# mid-request) — common on a home network, and previously meant a page
# turn just failed outright with no automatic recovery. 3 attempts with
# 0.5s/1s backoff adds at most ~1.5s before giving up, which is well
# under REQUEST_TIMEOUT and still fast enough not to stall a page turn
# for long if the NAS is genuinely down.
RETRY_ATTEMPTS = 3
RETRY_BACKOFF_BASE = 0.5  # seconds; doubles each retry: 0.5, 1.0


class ApiError(Exception):
    """Raised for any non-200 response, or a connection failure that
    persisted through all retries — lets reader.py show an on-panel
    error message instead of crashing the whole client."""


def _get(path: str, **params) -> requests.Response:
    """GET path (relative to SERVER_URL), retrying only on connection-
    level failures (timeouts, DNS, refused connections) — NOT on non-200
    HTTP responses. A 404/500 is an application-level answer (bad score
    id, backend bug) that a retry won't fix; a dropped connection is
    exactly the kind of transient hiccup a retry is for."""
    last_err = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            return requests.get(f"{SERVER_URL}{path}", params=params or None,
                                 timeout=REQUEST_TIMEOUT)
        except requests.RequestException as e:
            last_err = e
            if attempt < RETRY_ATTEMPTS - 1:
                time.sleep(RETRY_BACKOFF_BASE * (2 ** attempt))
    raise ApiError(
        f"Couldn't reach {SERVER_URL}{path} after {RETRY_ATTEMPTS} attempts: {last_err}"
    ) from last_err


def get_score(score_id: int) -> dict:
    """Metadata for a score, including page_count — used for bounds
    checking so next_page() doesn't walk past the end of the piece."""
    r = _get(f"/scores/{score_id}")
    if r.status_code != 200:
        raise ApiError(f"GET /scores/{score_id} -> {r.status_code}: {r.text}")
    return r.json()


def list_scores(**filters) -> list:
    """List scores, optionally filtered by category/instrument — for a
    future on-panel score picker (not built yet, see pi_client/README)."""
    r = _get("/scores/", **filters)
    if r.status_code != 200:
        raise ApiError(f"GET /scores/ -> {r.status_code}: {r.text}")
    return r.json()


def get_setlist(setlist_id: int) -> dict:
    """A setlist with its ordered items (score_id, page_start/page_end,
    notes) joined to score metadata — everything reader.py needs to walk
    through a performance without a follow-up request per item."""
    r = _get(f"/setlists/{setlist_id}")
    if r.status_code != 200:
        raise ApiError(f"GET /setlists/{setlist_id} -> {r.status_code}: {r.text}")
    return r.json()


def get_page_image(score_id: int, page_number: int) -> bytes:
    """Fetch a rendered page as PNG bytes. Raises ApiError on any
    non-200 (out-of-range page, missing PDF, backend down, etc.)."""
    r = _get(f"/page/{score_id}/{page_number}")
    if r.status_code != 200:
        raise ApiError(
            f"GET /page/{score_id}/{page_number} -> {r.status_code}: {r.text}"
        )
    return r.content
