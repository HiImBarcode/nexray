"""
NEXRAY v3 — FastAPI Backend Server
Single-entity warehouse and order operations platform for Larry's Hitex Inc.
MySQL backend via pymysql. Deploy on Railway, Render, or any cloud platform.
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import os
import mimetypes

app = FastAPI(title="NEXRAY Operations Platform", version="3.0.0")

# ========== CORS ==========
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== IMPORT AND MOUNT ROUTERS ==========
from routes_core import router as core_router
from routes_commerce import router as commerce_router
from routes_messaging import router as messaging_router
from routes_agents import router as agents_router

app.include_router(core_router)
app.include_router(commerce_router)
app.include_router(messaging_router)
app.include_router(agents_router)

# ========== DB INIT ==========
from db import init_db
from routes_commerce import init_commerce_db
from routes_messaging import init_messaging_db
from routes_agents import init_agents_db


@app.on_event("startup")
async def startup():
    init_db()
    init_commerce_db()
    init_messaging_db()
    init_agents_db()


# ========== SERVE STATIC FILES + SPA FALLBACK ==========
static_dir = "static"
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def serve_index():
    return FileResponse("static/index.html", media_type="text/html")


@app.get("/{path:path}")
async def catch_all(path: str):
    if path.startswith("api/"):
        return JSONResponse({"detail": "Not Found", "path": f"/{path}"}, status_code=404)

    static_root = Path("static").resolve()
    requested = (static_root / path).resolve()
    if not str(requested).startswith(str(static_root)):
        return JSONResponse({"detail": "Forbidden"}, status_code=403)

    if requested.is_file():
        mime_type, _ = mimetypes.guess_type(str(requested))
        if mime_type is None:
            mime_type = "application/octet-stream"
        return FileResponse(str(requested), media_type=mime_type)

    index_path = static_root / "index.html"
    if index_path.is_file():
        return FileResponse(str(index_path), media_type="text/html")
    return JSONResponse({"detail": "Not Found"}, status_code=404)
