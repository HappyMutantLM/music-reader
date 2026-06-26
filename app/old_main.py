from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
# from app.database import init_db
from database import init_db
import threading
# from watcher import start_watcher
from watcher import start_watcher
from app.database import init_db

app = FastAPI(title="Music Library Server", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    init_db()
    watcher_thread = threading.Thread(
        target=start_watcher,
        daemon=True  # dies cleanly when container stops
    )
    watcher_thread.start()

# from routers import composers, instruments, repertoire, methods, excerpts, render, health

# app.include_router(health.router)
# app.include_router(composers.router,    prefix="/composers")
# app.include_router(instruments.router,  prefix="/instruments")
# app.include_router(repertoire.router,   prefix="/repertoire")
# app.include_router(methods.router,      prefix="/methods")
# app.include_router(excerpts.router,     prefix="/excerpts")
# app.include_router(render.router,       prefix="/render")





# scp /Users/leilamureebe/Documents/VS\ Code\ Projects/sheet_music/app/main.py leilamureebe@memoryalpha:/volume1/docker/music-server/app/
#