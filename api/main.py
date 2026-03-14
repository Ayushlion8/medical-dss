"""
medical-dss · FastAPI entry point
"""
from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path as _Path

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.config import settings
from api.routes import analyze, health, reports

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── startup ───────────────────────────────────────────────────────────────
    for d in (settings.UPLOAD_DIR, settings.OVERLAY_DIR,
              settings.REPORT_DIR, settings.TRACE_DIR):
        _Path(d).mkdir(parents=True, exist_ok=True)
    log.info("medical-dss API started", env=settings.APP_ENV)
    yield
    # ── shutdown ──────────────────────────────────────────────────────────────
    log.info("medical-dss API shutting down")


app = FastAPI(
    title="Medical DSS – Agentic Diagnostic Decision Support",
    version="1.0.0",
    description="Research / education only. Not a medical device.",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request ID + latency logging ─────────────────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    req_id = str(uuid.uuid4())[:8]
    t0 = time.perf_counter()
    response = await call_next(request)
    elapsed = round((time.perf_counter() - t0) * 1000, 1)
    log.info("http", method=request.method, path=request.url.path,
             status=response.status_code, ms=elapsed, req_id=req_id)
    response.headers["X-Request-ID"] = req_id
    return response


# ── Static overlays (PNG) ─────────────────────────────────────────────────────
if _Path(settings.OVERLAY_DIR).exists():
    app.mount("/overlays", StaticFiles(directory=settings.OVERLAY_DIR), name="overlays")
if _Path(settings.REPORT_DIR).exists():
    app.mount("/reports", StaticFiles(directory=settings.REPORT_DIR), name="reports")

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health.router,  prefix="/api")
app.include_router(analyze.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
