"""
library_health.py — cross-checks every ingested score against what's
actually sitting on disk. Lives at the repo root next to setlist_tool.py
and companion_tool.py, same role: a pure HTTP client against the FastAPI
backend (GET /ingest/health -> ingest_core.check_library_health()), run
from wherever's convenient.

Run this before a performance — it's exactly the check that would have
caught the Bach Arioso 404 (a score row whose filename never matched the
actual file on disk) before it showed up on the reader mid-setlist.

Usage:

    python library_health.py            # human-readable report
    python library_health.py --json     # raw JSON, for scripting

Exit code is 1 if anything is missing, 0 if the library's clean — so this
can double as a pre-gig check: `python library_health.py || echo "fix your library first"`.

Env vars (matches pi_client/config.py, setlist_tool.py, companion_tool.py):
    MUSIC_SERVER_URL   default http://memoryalpha:8000
"""
import argparse
import json
import os
import sys

import requests

SERVER_URL = os.getenv("MUSIC_SERVER_URL", "http://memoryalpha:8000")
REQUEST_TIMEOUT = 30  # a full-library disk walk can take a moment on a NAS


class ApiError(Exception):
    """Raised for any non-200 response or connection failure — caught at
    the command level so a bad request prints a clean message instead of
    a traceback."""


def _request(method: str, path: str, **kwargs):
    try:
        r = requests.request(method, f"{SERVER_URL}{path}", timeout=REQUEST_TIMEOUT, **kwargs)
    except requests.RequestException as e:
        raise ApiError(f"Couldn't reach {SERVER_URL}{path}: {e}") from e
    if r.status_code >= 400:
        raise ApiError(f"{method} {path} -> {r.status_code}: {r.text}")
    return r.json() if r.text else None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", action="store_true", help="Print raw JSON instead of a report")
    args = parser.parse_args()

    try:
        result = _request("GET", "/ingest/health")
    except ApiError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(result, indent=2))
        sys.exit(1 if result["missing_count"] else 0)

    print(f"Checked {result['total_scores']} scores.")
    if not result["missing_count"]:
        print("Library OK — every score's file is where the database expects it.")
        sys.exit(0)

    print(f"\n{result['missing_count']} score(s) with no matching file on disk:\n")
    for item in result["missing"]:
        title = item["repertoire_title"] or item["filename"]
        print(f"  score {item['score_id']:>4}  {title}")
        print(f"           expected filename: {item['filename']}")
        print(f"           category={item['category']}  instrument={item['instrument'] or '—'}")
    print("\nFix each by either renaming the real file to match, or correcting "
          "the score row's filename — there's no PATCH endpoint for this yet, "
          "so it's a direct sqlite3 UPDATE on the NAS today.")
    sys.exit(1)


if __name__ == "__main__":
    main()
