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

        # COALESCE preserves existing fields when only updating specific attributes
        conn.execute(
            """
            UPDATE repertoire SET 
                blurb = COALESCE(?, blurb),
                program_note = COALESCE(?, program_note),
                note_source = COALESCE(?, note_source)
            WHERE id = ?
            """,
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
