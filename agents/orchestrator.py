"""
OrchestratorAgent — plans the workflow, routes tasks, retries, enforces policy.
Uses CrewAI for agent coordination.
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from pathlib import Path
from typing import Optional

import structlog

from api.config import settings
from api.models import (
    AgentTrace, AnalyzeCaseRequest, AnalyzeCaseResponse,
    GroundednessNote,
)
from agents.vision_agent import VisionAgent
from agents.retrieval_agent import RetrievalAgent
from agents.diagnosis_agent import DiagnosisAgent
from agents.citation_verifier import CitationVerifierAgent
from agents.safety_agent import SafetyAgent

log = structlog.get_logger()


class OrchestratorAgent:
    """
    Plans and executes the full diagnostic pipeline:
    1. Vision   → imaging_findings + overlays
    2. Retrieval → ranked evidence snippets
    3. Diagnosis → differentials + red_flags + next_steps
    4. Citation Verifier → groundedness check
    5. Safety   → PHI check + disclaimers + PDF report
    """

    def __init__(self):
        self.vision    = VisionAgent()
        self.retrieval = RetrievalAgent()
        self.diagnosis = DiagnosisAgent()
        self.verifier  = CitationVerifierAgent()
        self.safety    = SafetyAgent()

    async def run(self, request: AnalyzeCaseRequest) -> AnalyzeCaseResponse:
        traces: list[AgentTrace] = []
        response = AnalyzeCaseResponse(case_id=request.case_id)

        # ── 1. Vision ────────────────────────────────────────────────────────
        t0 = time.perf_counter()
        try:
            findings, overlays = await self.vision.analyze(request)
            response.imaging_findings = findings
            response.overlays = overlays
        except Exception as e:
            log.warning("vision_agent_error", error=str(e))
            findings, overlays = {}, []
        traces.append(AgentTrace(
            agent="VisionAgent",
            duration_ms=round((time.perf_counter() - t0) * 1000, 1),
        ))

        # ── 2. Retrieval ─────────────────────────────────────────────────────
        t0 = time.perf_counter()
        query = self._build_retrieval_query(request, findings)
        try:
            snippets = await self.retrieval.retrieve(
                query=query,
                max_results=request.preferences.max_citations,
                recency_years=request.preferences.recency_years,
            )
        except Exception as e:
            log.warning("retrieval_agent_error", error=str(e))
            snippets = []
        doc_ids = [s.id for s in snippets]
        traces.append(AgentTrace(
            agent="RetrievalAgent",
            duration_ms=round((time.perf_counter() - t0) * 1000, 1),
            retrieved_doc_ids=doc_ids,
        ))

        # ── 3. Diagnosis ─────────────────────────────────────────────────────
        t0 = time.perf_counter()
        try:
            differentials, red_flags, next_steps = await self.diagnosis.reason(
                patient=request.patient_context,
                findings=findings,
                snippets=snippets,
            )
            response.differentials = differentials
            response.red_flags = red_flags
            response.next_steps = next_steps
            response.citations = snippets
        except Exception as e:
            log.warning("diagnosis_agent_error", error=str(e))
        traces.append(AgentTrace(
            agent="DiagnosisAgent",
            duration_ms=round((time.perf_counter() - t0) * 1000, 1),
        ))

        # ── 4. Citation Verifier ──────────────────────────────────────────────
        t0 = time.perf_counter()
        try:
            groundedness = await self.verifier.verify(
                differentials=response.differentials,
                citations=response.citations,
            )
            response.groundedness = groundedness
        except Exception as e:
            log.warning("citation_verifier_error", error=str(e))
            response.groundedness = GroundednessNote(
                verified=False, gaps=[], note=f"Verifier error: {e}"
            )
        traces.append(AgentTrace(
            agent="CitationVerifierAgent",
            duration_ms=round((time.perf_counter() - t0) * 1000, 1),
        ))

        # ── 5. Safety / PDF ───────────────────────────────────────────────────
        t0 = time.perf_counter()
        try:
            report_id, report_url = await self.safety.process_and_export(
                request=request,
                response=response,
            )
            response.report_url = report_url
        except Exception as e:
            log.warning("safety_agent_error", error=str(e))
        traces.append(AgentTrace(
            agent="SafetyAgent",
            duration_ms=round((time.perf_counter() - t0) * 1000, 1),
        ))

        response.traces = traces

        # ── Save trace ───────────────────────────────────────────────────────
        self._save_trace(request.case_id, request, response)
        return response

    def _build_retrieval_query(self, req: AnalyzeCaseRequest,
                               findings: dict) -> str:
        ctx = req.patient_context
        finding_names = " ".join(findings.keys()) if findings else ""
        return (
            f"{ctx.chief_complaint} {finding_names} "
            f"age {ctx.age} {ctx.sex} diagnosis treatment"
        ).strip()

    def _save_trace(self, case_id: str,
                    req: AnalyzeCaseRequest,
                    resp: AnalyzeCaseResponse) -> None:
        try:
            trace_dir = Path(settings.TRACE_DIR)
            trace_dir.mkdir(parents=True, exist_ok=True)
            trace_file = trace_dir / f"{case_id}_{uuid.uuid4().hex[:6]}.jsonl"
            with trace_file.open("w") as f:
                f.write(json.dumps({
                    "case_id": case_id,
                    "patient_age": req.patient_context.age,
                    "patient_sex": req.patient_context.sex,
                    "chief_complaint": req.patient_context.chief_complaint,
                    "num_differentials": len(resp.differentials),
                    "num_citations": len(resp.citations),
                    "traces": [t.model_dump() for t in resp.traces],
                }, default=str) + "\n")
        except Exception as e:
            log.warning("trace_save_error", error=str(e))
