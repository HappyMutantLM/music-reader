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
                COALESCE(
                    GROUP_CONCAT(c.name, ', '),
                    GROUP_CONCAT(c2.name, ', ')
                ) AS composers
            FROM score s
            LEFT JOIN repertoire r ON s.repertoire_id = r.id
            LEFT JOIN repertoire_composer rc ON r.id = rc.repertoire_id
            LEFT JOIN composer c ON rc.composer_id = c.id
            LEFT JOIN score_composer sc ON s.id = sc.score_id
            LEFT JOIN composer c2 ON sc.composer_id = c2.id
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

        # Attach composers separately so we get role info too.
        # Repertoire-linked scores get their composer(s) via repertoire_composer;
        # repertoire-less scores (Method/Etude/Technique) get them via the
        # direct score_composer link instead.
        if result.get("repertoire_id"):
            composers = conn.execute("""
                SELECT c.id, c.name, c.birth_year, c.death_year, c.nationality, rc.role
                FROM composer c
                JOIN repertoire_composer rc ON c.id = rc.composer_id
                WHERE rc.repertoire_id = ?
                ORDER BY rc.role, c.name
            """, (result["repertoire_id"],)).fetchall()
        else:
            composers = conn.execute("""
                SELECT c.id, c.name, c.birth_year, c.death_year, c.nationality, sc.role
                FROM composer c
                JOIN score_composer sc ON c.id = sc.composer_id
                WHERE sc.score_id = ?
                ORDER BY sc.role, c.name
            """, (result["id"],)).fetchall()

        result["composers"] = rows_to_list(composers)

    return result


@router.get("/by-composer/{composer_id}")
def scores_by_composer(composer_id: int):
    """All scores linked to a given composer — either via a parent repertoire
    (piece/work), or directly for repertoire-less Method/Etude/Technique
    scores that link straight to score_composer."""
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

            UNION ALL

            SELECT
                s.id,
                s.filename,
                s.category,
                s.instrument,
                s.page_count,
                NULL AS repertoire_title,
                NULL AS catalogue_number,
                sc.role
            FROM score s
            JOIN score_composer sc ON s.id = sc.score_id
            WHERE sc.composer_id = ?

            ORDER BY repertoire_title, instrument, filename
        """, (composer_id, composer_id)).fetchall()
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