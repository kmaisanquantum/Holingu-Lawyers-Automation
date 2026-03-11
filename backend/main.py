"""
Holingu Lawyers Analytical Repository
FastAPI Backend — Port Moresby, Papua New Guinea
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from contextlib import asynccontextmanager
import os

from database import init_db
from routers import matters, documents, clients, users, risks, deadlines, analytics, vault

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    upload_dir = os.environ.get("UPLOAD_DIR", "./uploads")
    os.makedirs(upload_dir, exist_ok=True)
    yield

app = FastAPI(
    title="Holingu Lawyers — Analytical Repository API",
    description="Legal document management system — Port Moresby, Papua New Guinea",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API Routers ──────────────────────────────────────────────────────────────
app.include_router(matters.router,   prefix="/api/matters",   tags=["Matters"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(clients.router,   prefix="/api/clients",   tags=["Clients"])
app.include_router(users.router,     prefix="/api/users",     tags=["Users"])
app.include_router(risks.router,     prefix="/api/risks",     tags=["Risk Flags"])
app.include_router(deadlines.router, prefix="/api/deadlines", tags=["Deadlines"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(vault.router,     prefix="/api/vault",     tags=["Vault"])

# ── Frontend static files ─────────────────────────────────────────────────────
# backend/ is cwd; frontend/ is at ../frontend
_here = os.path.dirname(os.path.abspath(__file__))
frontend_dir = os.path.normpath(os.path.join(_here, "..", "frontend"))

if os.path.isdir(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

# ── Root ──────────────────────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
async def serve_frontend():
    index = os.path.join(frontend_dir, "index.html")
    if os.path.isfile(index):
        return FileResponse(index)
    return JSONResponse({"message": "Holingu Lawyers API", "docs": "/docs"})

@app.get("/health")
async def health():
    return {"status": "ok", "firm": "Holingu Lawyers", "location": "Port Moresby, PNG", "currency": "PGK"}

@app.get("/api")
async def api_root():
    return {
        "name": "Holingu Lawyers Analytical Repository",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": [
            "GET  /api/matters", "POST /api/matters",
            "GET  /api/documents", "POST /api/documents/upload/{matter_ref}",
            "GET  /api/clients", "GET  /api/users",
            "GET  /api/risks?status=open",
            "GET  /api/deadlines?days_ahead=30",
            "GET  /api/analytics/dashboard",
            "GET  /api/vault/search?q=..."
        ]
    }
