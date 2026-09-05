"""Thin HTTP client for the FastAPI backend's companion endpoints
(routers/companion.py). Mirrors pi_client/api_client.py's retry/backoff
approach for consistency.
"""
import json
import logging
import os
import time

import requests

import config

log = logging.getLogger("companion.api_client")

RETRY_ATTEMPTS = 3
RETRY_BACKOFF_BASE = 0.5


class ApiError(Exception):
    """Raised for a non-200 response, or a connection failure that
    persisted through all retries."""


def _get(path: str):
    last_err = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            return requests.get(f"{config.SERVER_URL}{path}", timeout=config.REQUEST_TIMEOUT)
        except requests.RequestException as e:
            last_err = e
            if attempt < RETRY_ATTEMPTS - 1:
                time.sleep(RETRY_BACKOFF_BASE * (2 ** attempt))
    raise ApiError(
        f"Couldn't reach {config.SERVER_URL}{path} after {RETRY_ATTEMPTS} attempts: {last_err}"
    ) from last_err


def fetch_program():
    try:
        resp = _get(f"/setlists/{config.SETLIST_ID}/program")
        if resp.status_code != 200:
            raise ApiError(f"GET /setlists/{config.SETLIST_ID}/program -> {resp.status_code}: {resp.text}")
        program = resp.json()
        _save_cache(program)
        log.info("Fetched program from server (%d items)", len(program.get("items", [])))
        return program
    except ApiError as exc:
        log.warning("Could not fetch program from server (%s), trying local cache", exc)
        cached = _load_cache()
        if cached is not None:
            log.info("Loaded program from local cache (%d items)", len(cached.get("items", [])))
            return cached
        raise RuntimeError(
            "No network and no local cache available — can't load a program. "
            "Connect to Wi-Fi at least once before an event."
        ) from exc


def get_now_playing() -> tuple[bool, int | None]:
    """Returns (success, setlist_score_id).
    On network failure, returns (False, None) so caller leaves badge as-is.
    On successful 200, returns (True, id_or_none) so clear commands succeed."""
    try:
        resp = _get("/now-playing")
        if resp.status_code != 200:
            log.debug("now-playing poll got %s — leaving badge as-is", resp.status_code)
            return False, None
        return True, resp.json().get("setlist_score_id")
    except ApiError as exc:
        log.debug("now-playing poll failed (%s) — leaving badge as-is", exc)
        return False, None


def _save_cache(program):
    try:
        os.makedirs(os.path.dirname(config.CACHE_PATH) or ".", exist_ok=True)
        tmp_path = config.CACHE_PATH + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(program, f)
        os.replace(tmp_path, config.CACHE_PATH)
    except OSError as exc:
        log.warning("Could not write program cache: %s", exc)


def _load_cache():
    if not os.path.exists(config.CACHE_PATH):
        return None
    try:
        with open(config.CACHE_PATH) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("Could not read program cache: %s", exc)
        return None
