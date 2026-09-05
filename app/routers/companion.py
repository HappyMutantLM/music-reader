"""
Endpoints for the companion display — a second, small e-ink device passed
around during a performance so guests can browse the evening's program and
read a short note on whatever's playing, in place of a printed program.

Deliberately separate from routers/setlists.py's GET /setlists/{id}, which
the main Pi reader uses and which returns filename/category/page_count —
fields the companion doesn't need and doesn't have (it needs composer as
plain text and a program-note blurb instead).

now_playing is a tiny, separate concern from the program itself: the
companion fetches /setlists/{id}/program once and caches it locally, then
only polls /now-playing periodically to decide whether to show a badge.
A guest browsing ahead on their own device should never get pulled back to
whatever the performer is currently on — see companion/state.py for the
client-side half of that design.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database import get_db

router = APIRouter()

# Mirrors the join shape in routers/setlists.py's ITEM_JOIN_QUERY, but
# pulls composer names and the repertoire blurb instead of file/category
# metadata the companion has no use for. Filtered to role='composer' (not
# arranger/editor/transcriber/orchestrator) — a printed-program-style
# credit line shouldn't get muddled with every contributor role that
# repertoire_composer/score_composer can carry.
PROGRAM_ITEM_QUERY = """
    SELECT
        ss.id,
        ss.position,
        s.instrument,
        COALESCE(r.title, s.filename) AS title,
        r.catalogue_number,
        r.blurb,
        COALESCE(
            GROUP_CONCAT(DISTINCT c.name),
            GROUP_CONCAT(DISTINCT c2.name)
        ) AS composer
    FROM setlist_score ss
    JOIN score s ON ss.score_id = s.id
    LEFT JOIN repertoire r ON s.repertoire_id = r.id
    LEFT JOIN repertoire_composer rc
        ON r.id = rc.repertoire_id AND rc.role = 'composer'
    LEFT JOIN composer c ON rc.composer_id = c.id
    LEFT JOIN score_composer sc
        ON s.id = sc.score_id AND sc.role = 'composer'
    LEFT JOIN composer c2 ON sc.composer_id = c2.id
    WHERE ss.setlist_id = ?
    GROUP BY ss.id
    ORDER BY ss.position
"""


class NowPlaying(BaseModel):
    setlist_score_id: int | None = None


class ProgramNoteUpdate(BaseModel):
    blurb: str | None = None
    program_note: str | None = None
    note_source: str | None = None


@router.get("/setlists/{setlist_id}/program")
def get_program(setlist_id: int):
    """The whole evening in one call — the companion fetches this once at
    startup and caches it to disk, so it keeps working if it wanders out
    of Wi-Fi range while being passed around the room."""
    with get_db() as conn:
        setlist = conn.execute(
            "SELECT title FROM setlist WHERE id = ?", (setlist_id,)
        ).fetchone()
        if not setlist:
            raise HTTPException(status_code=404, detail="Setlist not found")

        rows = conn.execute(PROGRAM_ITEM_QUERY, (setlist_id,)).fetchall()

    items = [
        {
            "id": row["id"],
            "order": row["position"],
            "composer": row["composer"],
            "title": row["title"],
            "opus": row["catalogue_number"],
            "instrument": row["instrument"],
            "blurb": row["blurb"],
        }
        for row in rows
    ]
    return {"name": setlist["title"], "items": items}


@router.put("/setlist-items/{setlist_score_id}/program-note")
def set_program_note(setlist_score_id: int, body: ProgramNoteUpdate):
    """Keyed on setlist_score_id (the same id GET /setlists/{id}/program
    shows for each item) rather than a raw repertoire_id, so the workflow
    is: look at a program, pick the item you want to annotate, use its id
    directly — no separate repertoire-id lookup needed. Resolves to
    repertoire under the hood since that's where the note actually lives
    (see 005_companion_program_notes.sql).

    No other endpoint writes to repertoire yet (routers/scores.py is
    read-only) — this is the only way to attach a companion blurb to a
    piece today, short of editing the db directly. See companion_tool.py
    at the repo root for a command-line wrapper around this."""
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT s.repertoire_id
            FROM setlist_score ss
            JOIN score s ON s.id = ss.score_id
            WHERE ss.id = ?
            """,
            (setlist_score_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Setlist item not found")
        if row["repertoire_id"] is None:
            raise HTTPException(
                status_code=400,
                detail="This item's score has no parent repertoire (a Method/Etude/"
                "Technique score) — there's nowhere to attach a program note.",
            )
        repertoire_id = row["repertoire_id"]

        conn.execute(
            "UPDATE repertoire SET blurb = ?, program_note = ?, note_source = ? WHERE id = ?",
            (body.blurb, body.program_note, body.note_source, repertoire_id),
        )
        updated = conn.execute(
            "SELECT id, title, blurb, program_note, note_source FROM repertoire WHERE id = ?",
            (repertoire_id,),
        ).fetchone()
    return dict(updated)


@router.get("/now-playing", response_model=NowPlaying)
def get_now_playing():
    with get_db() as conn:
        row = conn.execute(
            "SELECT setlist_score_id FROM now_playing WHERE id = 1"
        ).fetchone()
    return NowPlaying(setlist_score_id=row["setlist_score_id"] if row else None)


@router.post("/now-playing", response_model=NowPlaying)
def set_now_playing(body: NowPlaying):
    """Not called by the companion device itself — this is for whatever
    ends up triggering a setlist advance on the performer's side (a
    footswitch action, or the main reader's own next-piece event). Not
    wired up to anything yet; the companion only reads this endpoint."""
    with get_db() as conn:
        if body.setlist_score_id is not None:
            exists = conn.execute(
                "SELECT 1 FROM setlist_score WHERE id = ?",
                (body.setlist_score_id,),
            ).fetchone()
            if not exists:
                raise HTTPException(
                    status_code=404,
                    detail=f"No setlist_score with id {body.setlist_score_id}",
                )
        conn.execute(
            "UPDATE now_playing SET setlist_score_id = ?, "
            "updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = 1",
            (body.setlist_score_id,),
        )
    return body
