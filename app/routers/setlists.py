from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database import get_db, row_to_dict, rows_to_list

router = APIRouter()


class SetlistCreate(BaseModel):
    title: str
    description: str | None = None


class SetlistItemCreate(BaseModel):
    score_id: int
    position: int | None = None    # appended at the end if omitted
    page_start: int | None = None  # null + page_end null = whole score
    page_end: int | None = None
    notes: str | None = None


class ReorderRequest(BaseModel):
    # every setlist_score.id currently in this setlist, in the new order
    item_ids: list[int]


def _validate_page_range(page_start: int | None, page_end: int | None):
    if (page_start is None) != (page_end is None):
        raise HTTPException(
            status_code=400,
            detail="page_start and page_end must both be set or both be null",
        )
    if page_start is not None and page_end < page_start:
        raise HTTPException(status_code=400, detail="page_end must be >= page_start")


# Items joined with score/repertoire/composer — everything a consumer
# (the Pi client, a setlist editor UI) needs in one request, mirroring
# the join style in routers/scores.py.
ITEM_JOIN_QUERY = """
    SELECT
        ss.id,
        ss.setlist_id,
        ss.score_id,
        ss.position,
        ss.page_start,
        ss.page_end,
        ss.notes,
        s.filename,
        s.category,
        s.instrument,
        s.page_count,
        r.title       AS repertoire_title,
        r.catalogue_number,
        COALESCE(
            GROUP_CONCAT(DISTINCT c.name),
            GROUP_CONCAT(DISTINCT c2.name)
        ) AS composers
    FROM setlist_score ss
    JOIN score s ON ss.score_id = s.id
    LEFT JOIN repertoire r ON s.repertoire_id = r.id
    LEFT JOIN repertoire_composer rc ON r.id = rc.repertoire_id
    LEFT JOIN composer c ON rc.composer_id = c.id
    LEFT JOIN score_composer sc ON s.id = sc.score_id
    LEFT JOIN composer c2 ON sc.composer_id = c2.id
    WHERE ss.setlist_id = ?
    GROUP BY ss.id
    ORDER BY ss.position
"""


@router.get("/")
def list_setlists():
    """All setlists with an item count, most recently created first."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT
                sl.id, sl.title, sl.description, sl.created_at,
                COUNT(ss.id) AS item_count
            FROM setlist sl
            LEFT JOIN setlist_score ss ON ss.setlist_id = sl.id
            GROUP BY sl.id
            ORDER BY sl.created_at DESC
        """).fetchall()
    return rows_to_list(rows)


@router.post("/")
def create_setlist(body: SetlistCreate):
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO setlist (title, description) VALUES (?, ?)",
            (body.title, body.description),
        )
        row = conn.execute(
            "SELECT id, title, description, created_at FROM setlist WHERE id = ?",
            (cur.lastrowid,),
        ).fetchone()
    return row_to_dict(row)


@router.get("/{setlist_id}")
def get_setlist(setlist_id: int):
    """A setlist with its items in performance order — everything the Pi
    client needs to walk through a performance without a follow-up
    request per item."""
    with get_db() as conn:
        setlist_row = conn.execute(
            "SELECT id, title, description, created_at FROM setlist WHERE id = ?",
            (setlist_id,),
        ).fetchone()
        if not setlist_row:
            raise HTTPException(status_code=404, detail="Setlist not found")

        items = conn.execute(ITEM_JOIN_QUERY, (setlist_id,)).fetchall()

    result = row_to_dict(setlist_row)
    result["items"] = rows_to_list(items)
    return result


@router.delete("/{setlist_id}")
def delete_setlist(setlist_id: int):
    """Deletes the setlist and its items (ON DELETE CASCADE on
    setlist_score.setlist_id) — the scores themselves are untouched."""
    with get_db() as conn:
        cur = conn.execute("DELETE FROM setlist WHERE id = ?", (setlist_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Setlist not found")
    return {"status": "deleted"}


@router.post("/{setlist_id}/items")
def add_item(setlist_id: int, body: SetlistItemCreate):
    """Add a score (or an excerpt of one) to a setlist. If position is
    omitted, the item is appended to the end; otherwise existing items
    at or after that position are shifted down to make room."""
    _validate_page_range(body.page_start, body.page_end)

    with get_db() as conn:
        setlist = conn.execute(
            "SELECT id FROM setlist WHERE id = ?", (setlist_id,)
        ).fetchone()
        if not setlist:
            raise HTTPException(status_code=404, detail="Setlist not found")

        score = conn.execute(
            "SELECT id FROM score WHERE id = ?", (body.score_id,)
        ).fetchone()
        if not score:
            raise HTTPException(status_code=404, detail="Score not found")

        max_position = conn.execute(
            "SELECT COALESCE(MAX(position), 0) FROM setlist_score WHERE setlist_id = ?",
            (setlist_id,),
        ).fetchone()[0]

        position = body.position if body.position is not None else max_position + 1
        if position < 1 or position > max_position + 1:
            raise HTTPException(
                status_code=400,
                detail=f"position must be between 1 and {max_position + 1}",
            )

        if position <= max_position:
            # Shift position >= target down one slot to make room.
            # Two-phase (temp negative, then final) so we never collide
            # with the UNIQUE(setlist_id, position) constraint mid-update.
            conn.execute("""
                UPDATE setlist_score SET position = -(position + 1)
                WHERE setlist_id = ? AND position >= ?
            """, (setlist_id, position))
            conn.execute("""
                UPDATE setlist_score SET position = -position
                WHERE setlist_id = ? AND position < 0
            """, (setlist_id,))

        cur = conn.execute("""
            INSERT INTO setlist_score
                (setlist_id, score_id, position, page_start, page_end, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (setlist_id, body.score_id, position, body.page_start, body.page_end, body.notes))

        item = conn.execute(
            "SELECT * FROM setlist_score WHERE id = ?", (cur.lastrowid,)
        ).fetchone()

    return row_to_dict(item)


@router.delete("/{setlist_id}/items/{item_id}")
def remove_item(setlist_id: int, item_id: int):
    """Remove an item and compact the remaining positions so there's no
    gap — the Pi client indexes through items by consecutive position."""
    with get_db() as conn:
        cur = conn.execute(
            "DELETE FROM setlist_score WHERE id = ? AND setlist_id = ?",
            (item_id, setlist_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Item not found in this setlist")

        remaining = conn.execute("""
            SELECT id FROM setlist_score WHERE setlist_id = ? ORDER BY position
        """, (setlist_id,)).fetchall()

        # Two-phase renumber, same collision-avoidance as add_item/reorder.
        for i, row in enumerate(remaining):
            conn.execute(
                "UPDATE setlist_score SET position = ? WHERE id = ?",
                (-(i + 1), row["id"]),
            )
        for i, row in enumerate(remaining):
            conn.execute(
                "UPDATE setlist_score SET position = ? WHERE id = ?",
                (i + 1, row["id"]),
            )

    return {"status": "deleted"}


@router.put("/{setlist_id}/reorder")
def reorder_setlist(setlist_id: int, body: ReorderRequest):
    """Reorder every item in a setlist in one shot. item_ids must be
    exactly the set of setlist_score ids currently in this setlist —
    partial reorders aren't supported (position numbering has to stay
    gap-free and unambiguous for the Pi client)."""
    with get_db() as conn:
        current_ids = {
            row["id"]
            for row in conn.execute(
                "SELECT id FROM setlist_score WHERE setlist_id = ?", (setlist_id,)
            ).fetchall()
        }
        if not current_ids:
            raise HTTPException(status_code=404, detail="Setlist not found or has no items")
        if set(body.item_ids) != current_ids:
            raise HTTPException(
                status_code=400,
                detail="item_ids must exactly match this setlist's current items",
            )

        # Two-phase: negative temp positions first so the
        # UNIQUE(setlist_id, position) constraint never sees a collision
        # mid-update.
        for i, item_id in enumerate(body.item_ids):
            conn.execute(
                "UPDATE setlist_score SET position = ? WHERE id = ?",
                (-(i + 1), item_id),
            )
        for i, item_id in enumerate(body.item_ids):
            conn.execute(
                "UPDATE setlist_score SET position = ? WHERE id = ?",
                (i + 1, item_id),
            )

        items = conn.execute(ITEM_JOIN_QUERY, (setlist_id,)).fetchall()

    return rows_to_list(items)
