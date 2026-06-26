from fastapi import APIRouter, HTTPException
from database import get_db, row_to_dict, rows_to_list

router = APIRouter()


@router.get("/")
def list_scores(category: str = None, instrument: str = None):
    """List all scores, optionally filtered by category and/or instrument."""
    with get_db() as conn:
        query = """
            SELECT
                s.id,
                s.filename,
                s.category,
                s.instrument,
                s.page_count,
                s.ingested_at,
                s.updated_at,
                r.title       AS repertoire_title,
                r.catalogue_number,
                GROUP_CONCAT(c.name, ', ') AS composers
            FROM score s
            LEFT JOIN repertoire r ON s.repertoire_id = r.id
            LEFT JOIN repertoire_composer rc ON r.id = rc.repertoire_id
            LEFT JOIN composer c ON rc.composer_id = c.id
        """
        filters, params = [], []
        if category:
            filters.append("s.category = ?")
            params.append(category)
        if instrument:
            filters.append("s.instrument = ?")
            params.append(instrument)
        if filters:
            query += " WHERE " + " AND ".join(filters)
        query += " GROUP BY s.id ORDER BY s.ingested_at DESC"

        rows = conn.execute(query, params).fetchall()
    return rows_to_list(rows)


@router.get("/{score_id}")
def get_score(score_id: int):
    """Get a single score by id, including full repertoire and composer detail."""
    with get_db() as conn:
        row = conn.execute("""
            SELECT
                s.id,
                s.filename,
                s.category,
                s.instrument,
                s.page_count,
                s.file_hash,
                s.ingested_at,
                s.updated_at,
                r.id          AS repertoire_id,
                r.title       AS repertoire_title,
                r.nickname    AS repertoire_nickname,
                r.key_signature,
                r.catalogue_number,
                r.notes       AS repertoire_notes
            FROM score s
            LEFT JOIN repertoire r ON s.repertoire_id = r.id
            WHERE s.id = ?
        """, (score_id,)).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Score not found")

        result = row_to_dict(row)

        # Attach composers separately so we get role info too
        composers = conn.execute("""
            SELECT c.id, c.name, c.birth_year, c.death_year, c.nationality, rc.role
            FROM composer c
            JOIN repertoire_composer rc ON c.id = rc.composer_id
            WHERE rc.repertoire_id = ?
            ORDER BY rc.role, c.name
        """, (result["repertoire_id"],)).fetchall() if result.get("repertoire_id") else []

        result["composers"] = rows_to_list(composers)

    return result


@router.get("/by-composer/{composer_id}")
def scores_by_composer(composer_id: int):
    """All scores linked to a given composer (via repertoire)."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT
                s.id,
                s.filename,
                s.category,
                s.instrument,
                s.page_count,
                r.title AS repertoire_title,
                r.catalogue_number,
                rc.role
            FROM score s
            JOIN repertoire r ON s.repertoire_id = r.id
            JOIN repertoire_composer rc ON r.id = rc.repertoire_id
            WHERE rc.composer_id = ?
            ORDER BY r.title, s.instrument
        """, (composer_id,)).fetchall()
    return rows_to_list(rows)


@router.get("/by-repertoire/{repertoire_id}")
def scores_by_repertoire(repertoire_id: int):
    """All scores (parts/editions) for a given work."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT
                s.id,
                s.filename,
                s.category,
                s.instrument,
                s.page_count,
                s.ingested_at
            FROM score s
            WHERE s.repertoire_id = ?
            ORDER BY s.instrument, s.filename
        """, (repertoire_id,)).fetchall()
    return rows_to_list(rows)