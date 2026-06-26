from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import migrate
import threading
from watcher import start_watcher

app = FastAPI(title="Music Library Server", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    migrate()
    watcher_thread = threading.Thread(target=start_watcher, daemon=True)
    watcher_thread.start()

@app.get("/health")
def health():
    return {"status": "ok"}

from routers import ingest, scores
app.include_router(ingest.router, prefix="/ingest", tags=["ingest"])
app.include_router(scores.router, prefix="/scores", tags=["scores"])