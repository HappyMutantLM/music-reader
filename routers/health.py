from fastapi import APIRouter
from ingest import ingest_all, ingest_file

router = APIRouter()

@router.get("/health")
def health():
    return {"status": "ok"}

@router.post("/ingest/all")
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

@router.post("/ingest/file/{filename}")
def run_ingest_file(filename: str):
    return ingest_file(filename)