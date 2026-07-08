import os

from fastapi import APIRouter, HTTPException
from ingest_core import ingest_all, ingest_file

router = APIRouter()

@router.post("/all")
def run_ingest_all():
    results = ingest_all()
    ok      = [r for r in results if r["status"] == "ok"]
    skipped = [r for r in results if r["status"] == "skipped"]
    errors  = [r for r in results if r["status"] == "error"]
    return {
        "ingested": len(ok),
        "skipped":  len(skipped),
        "errors":   len(errors),
        "detail":   results,
    }

@router.post("/file/{filename}")
def run_ingest_file(filename: str):
    # Reject path traversal / absolute paths — filename must resolve to
    # itself as a bare basename, or os.path.join(PDF_DIR, filename) in
    # ingest_core could escape PDF_DIR entirely (e.g. "/etc/passwd" or
    # "../../something" as the path param).
    if os.path.basename(filename) != filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    return ingest_file(filename)