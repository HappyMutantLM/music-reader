import os
import threading
 
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
 
from routers import health, ingest
from database import migrate
from watcher import start_watcher
 
app = FastAPI(title="Music Library Server", version="0.2.0")
 
# Comma-separated list of allowed browser origins, e.g.:
#   ALLOWED_ORIGINS=http://localhost:5173,http://192.168.1.50:8000
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
 
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
 
 
@app.on_event("startup")
async def startup():
    migrate()
    watcher_thread = threading.Thread(target=start_watcher, daemon=True)
    watcher_thread.start()
 
 
from routers import scores, pages  # noqa: E402

app.include_router(health.router, tags=["health"])
app.include_router(ingest.router, prefix="/ingest", tags=["ingest"])
app.include_router(scores.router, prefix="/scores", tags=["scores"])
app.include_router(pages.router, prefix="/page", tags=["pages"])
