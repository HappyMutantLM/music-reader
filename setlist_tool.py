"""
setlist_tool.py — command-line setlist curation against the FastAPI
backend. Lives at the repo root next to rename_tool.py: both are
operator-run scripts, but where rename_tool.py works directly on files on
disk, this one is a pure HTTP client (same role as pi_client/api_client.py)
— run it from wherever's convenient (your Mac, an SSH session on the NAS,
etc.), it doesn't need to run inside a container.

There's no on-panel or web setlist editor yet (see pi_client/README's
"Known gaps"), so this is the only way to build one today short of
crafting raw requests to POST /setlists/ and POST /setlists/{id}/items by
hand.

Setup:
    pip install requests

Usage — interactive (the easy way):

    python setlist_tool.py build "Fall Recital 2026"

Walks you through searching the library and adding pieces one at a time,
with optional excerpt page ranges and notes, without needing to know any
score ids up front. Re-run against an existing setlist to keep adding to
it:

    python setlist_tool.py build --setlist-id 3

Usage — scripted / one-shot (the precise way):

    python setlist_tool.py search bach cello          # find a score id
    python setlist_tool.py create "Fall Recital 2026" --description "..."
    python setlist_tool.py add 3 --score 41 --start 3 --end 7 --notes "start at letter B"
    python setlist_tool.py list                       # all setlists
    python setlist_tool.py show 3                      # one setlist, in order
    python setlist_tool.py reorder 3                    # interactive re-sequence
    python setlist_tool.py remove 3 12                   # setlist_id, item_id
    python setlist_tool.py delete 3

Env vars (matches pi_client/config.py):
    MUSIC_SERVER_URL   default http://memoryalpha:8000
"""
import argparse
import os
import sys

import requests

SERVER_URL = os.getenv("MUSIC_SERVER_URL", "http://memoryalpha:8000")
REQUEST_TIMEOUT = 10  # seconds


class ApiError(Exception):
    """Raised for any non-200 response or connection failure — caught at
    the command level so a bad request prints a clean message instead of
    a traceback."""


def _request(method: str, path: str, **kwargs) -> dict | list | None:
    try:
        r = requests.request(method, f"{SERVER_URL}{path}", timeout=REQUEST_TIMEOUT, **kwargs)
    except requests.RequestException as e:
        raise ApiError(f"Couldn't reach {SERVER_URL}{path}: {e}") from e
    if r.status_code >= 300:
        raise ApiError(f"{method} {path} -> {r.status_code}: {r.text}")
    if not r.content:
        return None
    return r.json()


def list_scores(category: str | None = None, instrument: str | None = None) -> list:
    params = {}
    if category:
        params["category"] = category
    if instrument:
        params["instrument"] = instrument
    return _request("GET", "/scores/", params=params)


def search_scores(terms: list[str], category: str | None = None,
                   instrument: str | None = None) -> list:
    """Client-side substring search — the backend only filters by exact
    category/instrument (routers/scores.py), no free-text search. Fine
    for a personal-library-sized collection: fetch everything (optionally
    narrowed by category/instrument) and require every search term to
    appear somewhere in filename/title/composers, case-insensitive."""
    scores = list_scores(category=category, instrument=instrument)
    terms = [t.lower() for t in terms]

    def _haystack(s: dict) -> str:
        return " ".join(str(s.get(k) or "") for k in
                         ("filename", "repertoire_title", "composers", "instrument")).lower()

    return [s for s in scores if all(t in _haystack(s) for t in terms)]


def list_setlists() -> list:
    return _request("GET", "/setlists/")


def get_setlist(setlist_id: int) -> dict:
    return _request("GET", f"/setlists/{setlist_id}")


def create_setlist(title: str, description: str | None = None) -> dict:
    return _request("POST", "/setlists/", json={"title": title, "description": description})


def delete_setlist(setlist_id: int):
    return _request("DELETE", f"/setlists/{setlist_id}")


def add_item(setlist_id: int, score_id: int, position: int | None = None,
             page_start: int | None = None, page_end: int | None = None,
             notes: str | None = None) -> dict:
    body = {"score_id": score_id, "position": position,
            "page_start": page_start, "page_end": page_end, "notes": notes}
    return _request("POST", f"/setlists/{setlist_id}/items", json=body)


def remove_item(setlist_id: int, item_id: int):
    return _request("DELETE", f"/setlists/{setlist_id}/items/{item_id}")


def reorder_setlist(setlist_id: int, item_ids: list[int]) -> list:
    return _request("PUT", f"/setlists/{setlist_id}/reorder", json={"item_ids": item_ids})


# ─── display helpers ────────────────────────────────────────────────────────

def _score_line(s: dict) -> str:
    title = s.get("repertoire_title") or s["filename"]
    composers = s.get("composers") or "—"
    pages = s.get("page_count")
    pages = f"{pages}p" if pages else "?p"
    return f"[{s['id']:>4}] {title}  —  {composers}  ({s['category']}/{s.get('instrument') or '—'}, {pages})"


def _item_line(n: int, item: dict) -> str:
    title = item.get("repertoire_title") or item["filename"]
    composers = item.get("composers") or "—"
    rng = ""
    if item.get("page_start") or item.get("page_end"):
        rng = f"  [pp. {item.get('page_start')}–{item.get('page_end')}]"
    notes = f"  ({item['notes']})" if item.get("notes") else ""
    return f"  {n:>2}. item#{item['id']:<4} {title} — {composers}{rng}{notes}"


def _print_setlist(setlist: dict):
    print(f"\n{setlist['title']}  (id {setlist['id']})")
    if setlist.get("description"):
        print(f"  {setlist['description']}")
    items = setlist.get("items", [])
    if not items:
        print("  (no items yet)")
        return
    for i, item in enumerate(items, start=1):
        print(_item_line(i, item))


# ─── commands ─────────────────────────────────────────────────────────────

def cmd_search(args):
    results = search_scores(args.terms, category=args.category, instrument=args.instrument)
    if not results:
        print("No matches.")
        return
    for s in results:
        print(_score_line(s))


def cmd_list(args):
    setlists = list_setlists()
    if not setlists:
        print("No setlists yet.")
        return
    for sl in setlists:
        desc = f" — {sl['description']}" if sl.get("description") else ""
        print(f"[{sl['id']:>4}] {sl['title']}{desc}  ({sl['item_count']} item(s))")


def cmd_show(args):
    _print_setlist(get_setlist(args.setlist_id))


def cmd_create(args):
    sl = create_setlist(args.title, args.description)
    print(f"Created setlist [{sl['id']}] {sl['title']}")


def cmd_add(args):
    item = add_item(args.setlist_id, args.score, position=args.position,
                     page_start=args.start, page_end=args.end, notes=args.notes)
    print(f"Added item#{item['id']} to setlist {args.setlist_id} at position {item['position']}")


def cmd_remove(args):
    remove_item(args.setlist_id, args.item_id)
    print(f"Removed item#{args.item_id} from setlist {args.setlist_id}")


def cmd_delete(args):
    if not args.yes:
        confirm = input(f"Delete setlist {args.setlist_id} and all its items? (yes/no): ")
        if confirm.strip().lower() != "yes":
            print("Aborted.")
            return
    delete_setlist(args.setlist_id)
    print(f"Deleted setlist {args.setlist_id}")


def cmd_reorder(args):
    setlist = get_setlist(args.setlist_id)
    items = setlist.get("items", [])
    if not items:
        print("Nothing to reorder — setlist has no items.")
        return
    _print_setlist(setlist)
    raw = input(f"\nNew order as position numbers 1-{len(items)}, comma-separated "
                f"(e.g. 3,1,2{',...' if len(items) > 3 else ''}): ")
    try:
        picks = [int(p.strip()) for p in raw.split(",") if p.strip()]
    except ValueError:
        print("Couldn't parse that — expected comma-separated numbers.")
        return
    if sorted(picks) != list(range(1, len(items) + 1)):
        print(f"Must list every position 1-{len(items)} exactly once.")
        return
    item_ids = [items[p - 1]["id"] for p in picks]
    updated = reorder_setlist(args.setlist_id, item_ids)
    print("New order:")
    for i, item in enumerate(updated, start=1):
        print(_item_line(i, item))


def cmd_build(args):
    """Interactive: create (or reuse) a setlist, then loop search -> pick
    -> optional page range/notes -> add, until the user's done."""
    if args.setlist_id:
        setlist = get_setlist(args.setlist_id)
        print(f"Adding to existing setlist [{setlist['id']}] {setlist['title']}")
    else:
        if not args.title:
            args.title = input("Setlist title: ").strip()
        description = args.description
        if description is None:
            description = input("Description (blank to skip): ").strip() or None
        setlist = create_setlist(args.title, description)
        print(f"Created setlist [{setlist['id']}] {setlist['title']}")

    setlist_id = setlist["id"]

    while True:
        query = input("\nSearch for a piece (blank to finish): ").strip()
        if not query:
            break

        results = search_scores(query.split())
        if not results:
            print("No matches — try fewer/different words.")
            continue

        for i, s in enumerate(results[:20], start=1):
            print(f"  {i:>2}. {_score_line(s)}")
        if len(results) > 20:
            print(f"  ...and {len(results) - 20} more — narrow your search to see them.")

        pick = input("Pick # to add (blank to search again): ").strip()
        if not pick:
            continue
        try:
            chosen = results[int(pick) - 1]
        except (ValueError, IndexError):
            print("Not a valid number.")
            continue

        page_start = page_end = None
        rng = input("Page range, e.g. 3-7 (blank = whole score): ").strip()
        if rng:
            try:
                lo, hi = rng.split("-")
                page_start, page_end = int(lo), int(hi)
            except ValueError:
                print("Couldn't parse that range — adding the whole score instead.")

        notes = input("Notes (blank = none): ").strip() or None

        item = add_item(setlist_id, chosen["id"], page_start=page_start,
                         page_end=page_end, notes=notes)
        print(f"  -> added at position {item['position']}")

    _print_setlist(get_setlist(setlist_id))


# ─── argument parsing ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("search", help="Search the library for scores")
    p.add_argument("terms", nargs="+", help="Search words (matched against title/composer/filename)")
    p.add_argument("--category", default=None)
    p.add_argument("--instrument", default=None)
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("list", help="List all setlists")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("show", help="Show one setlist's items in order")
    p.add_argument("setlist_id", type=int)
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("create", help="Create an empty setlist")
    p.add_argument("title")
    p.add_argument("--description", default=None)
    p.set_defaults(func=cmd_create)

    p = sub.add_parser("add", help="Add one score to a setlist")
    p.add_argument("setlist_id", type=int)
    p.add_argument("--score", type=int, required=True, help="score id (see `search`)")
    p.add_argument("--position", type=int, default=None, help="1-indexed; default: append to end")
    p.add_argument("--start", type=int, default=None, help="excerpt start page")
    p.add_argument("--end", type=int, default=None, help="excerpt end page")
    p.add_argument("--notes", default=None)
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("remove", help="Remove one item from a setlist")
    p.add_argument("setlist_id", type=int)
    p.add_argument("item_id", type=int)
    p.set_defaults(func=cmd_remove)

    p = sub.add_parser("reorder", help="Interactively re-sequence a setlist's items")
    p.add_argument("setlist_id", type=int)
    p.set_defaults(func=cmd_reorder)

    p = sub.add_parser("delete", help="Delete a setlist and all its items")
    p.add_argument("setlist_id", type=int)
    p.add_argument("--yes", action="store_true", help="skip confirmation prompt")
    p.set_defaults(func=cmd_delete)

    p = sub.add_parser("build", help="Interactively build a setlist by searching and picking pieces")
    p.add_argument("title", nargs="?", default=None, help="omit to be prompted, or if using --setlist-id")
    p.add_argument("--description", default=None)
    p.add_argument("--setlist-id", type=int, default=None, dest="setlist_id",
                    help="append to an existing setlist instead of creating a new one")
    p.set_defaults(func=cmd_build)

    args = parser.parse_args()
    try:
        args.func(args)
    except ApiError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(130)


if __name__ == "__main__":
    main()