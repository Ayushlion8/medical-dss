"""
POST /api/analyze-case   – orchestrates the full agent pipeline
POST /api/upload-image   – pre-upload CXR files
"""
from __future__ import annotations

import shutil
import time
import uuid
from pathlib import Path
from typing import List

import structlog
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import JSONResponse

from api.config import settings
from api.models import AnalyzeCaseRequest, AnalyzeCaseResponse
from agents.orchestrator import OrchestratorAgent

router = APIRouter(tags=["Analysis"])
log = structlog.get_logger()


# ─── Upload image ──────────────────────────────────────────────────────────────
@router.post("/upload-image", summary="Upload CXR image (DICOM/PNG/JPEG)")
async def upload_image(file: UploadFile = File(...)):
    """
    Accepts DICOM (.dcm), PNG, or JPEG.
    Returns an image_id that references the saved file for /analyze-case.
    """
    allowed_types = {
        "image/png", "image/jpeg", "image/jpg",
        "application/dicom", "application/octet-stream"
    }
    # Relaxed MIME check (browsers may send octet-stream for .dcm)
    ext = Path(file.filename or "").suffix.lower()
    if ext not in (".dcm", ".png", ".jpg", ".jpeg"):
        raise HTTPException(400, f"Unsupported file type: {ext}")

    if file.size and file.size > settings.max_upload_bytes:
        raise HTTPException(413, "File too large")

    image_id = str(uuid.uuid4())
    dest = Path(settings.UPLOAD_DIR) / f"{image_id}{ext}"
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    log.info("image_uploaded", image_id=image_id, filename=file.filename, ext=ext)
    return {"image_id": image_id, "filename": file.filename, "path": str(dest)}


# ─── Analyze case ──────────────────────────────────────────────────────────────
@router.post(
    "/analyze-case",
    response_model=AnalyzeCaseResponse,
    summary="Run full agentic diagnostic analysis on a clinical case",
)
async def analyze_case(request: AnalyzeCaseRequest):
    t0 = time.perf_counter()
    log.info("analyze_case_start", case_id=request.case_id)

    # Resolve image URIs to local paths
    for img in request.images:
        if not img.uri:
            raise HTTPException(400, f"Image {img.id} has no URI. Upload first.")
        local_path = Path(settings.UPLOAD_DIR) / Path(img.uri).name
        if not local_path.exists():
            # Allow absolute paths directly (for testing)
            if Path(img.uri).exists():
                img.uri = str(img.uri)
            else:
                raise HTTPException(404, f"Image not found: {img.uri}")
        else:
            img.uri = str(local_path)

    try:
        orchestrator = OrchestratorAgent()
        result: AnalyzeCaseResponse = await orchestrator.run(request)
    except Exception as exc:
        log.exception("pipeline_error", case_id=request.case_id, error=str(exc))
        raise HTTPException(500, f"Pipeline error: {exc}") from exc

    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
    log.info("analyze_case_done", case_id=request.case_id, ms=elapsed_ms)
    return result
