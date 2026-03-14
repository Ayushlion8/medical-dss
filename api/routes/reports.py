"""GET /api/reports/{report_id} – serve generated PDF reports"""
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from api.config import settings

router = APIRouter(tags=["Reports"])

@router.get("/reports/{report_id}", summary="Download a generated PDF report")
async def get_report(report_id: str):
    path = Path(settings.REPORT_DIR) / f"{report_id}.pdf"
    if not path.exists():
        raise HTTPException(404, "Report not found")
    return FileResponse(path, media_type="application/pdf",
                        filename=f"dss_report_{report_id}.pdf")
