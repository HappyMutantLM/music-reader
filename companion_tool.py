"""
companion_tool.py — command-line helper for the companion display's
program notes. Lives at the repo root next to setlist_tool.py, same role:
a pure HTTP client against routers/companion.py, run from wherever's
convenient.

There's no editor UI for program notes yet, so this is the only way to
attach a blurb to a piece today short of writing raw SQL.

Usage:

    python companion_tool.py show 1                 # a program, with item ids
    python companion_tool.py set-note 12 --blurb "One of six suites for unaccompanied cello..."
    python companion_tool.py set-note 12 --blurb "..." --source "written by Leila"
    python companion_tool.py now-playing 12          # set the live badge
    python companion_tool.py now-playing --clear     # clear it

Env vars (matches pi_client/config.py and setlist_tool.py):
    MUSIC_SERVER_URL   default http://memoryalpha:8000
"""
import argparse
import os
import sys

import requests

SERVER_URL = os.getenv("MUSIC_SERVER_URL", "http://memoryalpha:8000")
REQUEST_TIMEOUT = 10


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


def cmd_show(args):
    program = _request("GET", f"/setlists/{args.setlist_id}/program")
    print(program["name"])
    for item in program["items"]:
        blurb_flag = "  [has note]" if item.get("blurb") else "  [no note yet]"
        print(f"  {item['id']:>4}  {item['order']}. {item['composer']} — {item['title']}{blurb_flag}")


def cmd_set_note(args):
    body = {"blurb": args.blurb, "program_note": args.program_note, "note_source": args.source}
    updated = _request(
        "PUT", f"/setlist-items/{args.item_id}/program-note", json=body
    )
    print(f"Updated repertoire {updated['id']} ({updated['title']}):")
    print(f"  blurb: {updated['blurb']}")
    if updated.get("program_note"):
        print(f"  program_note: {updated['program_note']}")
    if updated.get("note_source"):
        print(f"  source: {updated['note_source']}")


def cmd_now_playing(args):
    if args.clear:
        result = _request("POST", "/now-playing", json={"setlist_score_id": None})
        print("Cleared now-playing.")
    elif args.item_id is not None:
        result = _request("POST", "/now-playing", json={"setlist_score_id": args.item_id})
        print(f"now-playing set to item {result['setlist_score_id']}")
    else:
        result = _request("GET", "/now-playing")
        print(f"now-playing: {result['setlist_score_id']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_show = sub.add_parser("show", help="Show a program with item ids and note status")
    p_show.add_argument("setlist_id", type=int)
    p_show.set_defaults(func=cmd_show)

    p_note = sub.add_parser("set-note", help="Attach a program note to a setlist item")
    p_note.add_argument("item_id", type=int, help="setlist item id, from `show`")
    p_note.add_argument("--blurb", default=None, help="1-3 sentences, shown on the companion detail screen")
    p_note.add_argument("--program-note", default=None, help="Longer note, for future archival use")
    p_note.add_argument("--source", default=None, help="Attribution, e.g. 'IMSLP' or 'written by Leila'")
    p_note.set_defaults(func=cmd_set_note)

    p_now = sub.add_parser("now-playing", help="Get or set the live now-playing badge")
    p_now.add_argument("item_id", type=int, nargs="?", default=None, help="setlist item id to mark as playing")
    p_now.add_argument("--clear", action="store_true", help="Clear the badge instead")
    p_now.set_defaults(func=cmd_now_playing)

    args = parser.parse_args()
    try:
        args.func(args)
    except ApiError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
