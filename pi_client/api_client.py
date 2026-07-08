"""Thin HTTP client for the FastAPI backend running on the NAS."""
import requests

from config import SERVER_URL, REQUEST_TIMEOUT


class ApiError(Exception):
    """Raised for any non-200 response or connection failure — lets
    reader.py show an on-panel error message instead of crashing the
    whole client over a flaky NAS connection or an out-of-range page."""


def get_score(score_id: int) -> dict:
    """Metadata for a score, including page_count — used for bounds
    checking so next_page() doesn't walk past the end of the piece."""
    try:
        r = requests.get(f"{SERVER_URL}/scores/{score_id}", timeout=REQUEST_TIMEOUT)
    except requests.RequestException as e:
        raise ApiError(f"Couldn't reach {SERVER_URL}: {e}") from e
    if r.status_code != 200:
        raise ApiError(f"GET /scores/{score_id} -> {r.status_code}: {r.text}")
    return r.json()


def list_scores(**filters) -> list:
    """List scores, optionally filtered by category/instrument — for a
    future on-panel score picker (not built yet, see pi_client/README)."""
    try:
        r = requests.get(f"{SERVER_URL}/scores/", params=filters, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as e:
        raise ApiError(f"Couldn't reach {SERVER_URL}: {e}") from e
    if r.status_code != 200:
        raise ApiError(f"GET /scores/ -> {r.status_code}: {r.text}")
    return r.json()


def get_page_image(score_id: int, page_number: int) -> bytes:
    """Fetch a rendered page as PNG bytes. Raises ApiError on any
    non-200 (out-of-range page, missing PDF, backend down, etc.)."""
    try:
        r = requests.get(
            f"{SERVER_URL}/page/{score_id}/{page_number}", timeout=REQUEST_TIMEOUT
        )
    except requests.RequestException as e:
        raise ApiError(f"Couldn't reach {SERVER_URL}: {e}") from e
    if r.status_code != 200:
        raise ApiError(
            f"GET /page/{score_id}/{page_number} -> {r.status_code}: {r.text}"
        )
    return r.content
