"""
API request / response models (matches assignment spec exactly).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ─── Request ─────────────────────────────────────────────────────────────────

class Vitals(BaseModel):
    BP: Optional[str] = None
    HR: Optional[int] = None
    RR: Optional[int] = None
    SpO2: Optional[float] = None
    Temp: Optional[float] = None
    Weight_kg: Optional[float] = None


class PatientContext(BaseModel):
    age: int
    sex: str  # M / F / Other
    chief_complaint: str
    hpi: Optional[str] = None
    pmh: Optional[List[str]] = []
    allergies: Optional[List[str]] = []
    vitals: Optional[Vitals] = None
    labs: Optional[Dict[str, Any]] = {}
    meds: Optional[List[str]] = []
    ros: Optional[Dict[str, Any]] = {}


class ImageRef(BaseModel):
    id: str
    modality: str = "CR"          # CR, DX, CT …
    format: str = "PNG"           # DICOM | PNG | JPEG
    uri: Optional[str] = None     # s3:// or local path (set server-side)


class AnalysisPreferences(BaseModel):
    recency_years: int = 5
    max_citations: int = 8
    show_overlays: bool = True


class AnalyzeCaseRequest(BaseModel):
    case_id: str
    patient_context: PatientContext
    images: List[ImageRef] = []
    preferences: AnalysisPreferences = Field(default_factory=AnalysisPreferences)


# ─── Response ─────────────────────────────────────────────────────────────────

class ImagingFinding(BaseModel):
    prob: float
    laterality: Optional[str] = None
    size: Optional[str] = None
    overlay_id: Optional[str] = None
    description: Optional[str] = None


class CitationSnippet(BaseModel):
    id: str
    pmid: Optional[str] = None
    doi: Optional[str] = None
    title: Optional[str] = None
    authors: Optional[str] = None
    year: Optional[int] = None
    source: Optional[str] = None
    study_type: Optional[str] = None   # Guideline | Meta | RCT | Cohort | Review
    quote: str
    url: Optional[str] = None


class Differential(BaseModel):
    dx: str
    icd10: str
    rationale: str
    probability_rank: int
    support: List[Dict[str, str]] = []   # [{"snippet_id": "s1"}, ...]


class Overlay(BaseModel):
    overlay_id: str
    type: str = "bbox"                   # bbox | mask
    coords: Optional[List[float]] = None  # [x, y, w, h]
    overlay_url: Optional[str] = None    # URL to PNG mask


class GroundednessNote(BaseModel):
    verified: bool
    gaps: List[str] = []
    note: str = ""


class AgentTrace(BaseModel):
    agent: str
    duration_ms: float
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    retrieved_doc_ids: Optional[List[str]] = None


class AnalyzeCaseResponse(BaseModel):
    case_id: str
    imaging_findings: Dict[str, ImagingFinding] = {}
    differentials: List[Differential] = []
    red_flags: List[str] = []
    next_steps: List[str] = []
    citations: List[CitationSnippet] = []
    overlays: List[Overlay] = []
    groundedness: Optional[GroundednessNote] = None
    traces: List[AgentTrace] = []
    report_url: Optional[str] = None
    disclaimer: str = (
        "⚠️  Research / education only. "
        "Not a medical device. Not for clinical use. "
        "Always consult a qualified clinician."
    )
