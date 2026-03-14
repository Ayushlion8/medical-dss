"""
DiagnosisAgent — clinical reasoning via Google Gemini API.
"""
from __future__ import annotations

import json
import re
from typing import Dict, List, Tuple

import httpx
import structlog

from api.config import settings
from api.models import CitationSnippet, Differential, ImagingFinding, PatientContext

log = structlog.get_logger()

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class DiagnosisAgent:
    async def reason(
        self,
        patient: PatientContext,
        findings: Dict[str, ImagingFinding],
        snippets: List[CitationSnippet],
    ) -> Tuple[List[Differential], List[str], List[str]]:
        prompt = self._build_prompt(patient, findings, snippets)
        raw = await self._call_gemini(prompt)
        return self._parse(raw, snippets)

    def _build_prompt(self, patient, findings, snippets) -> str:
        vitals_parts = []
        if patient.vitals:
            v = patient.vitals
            if v.BP:   vitals_parts.append(f"BP={v.BP}")
            if v.HR:   vitals_parts.append(f"HR={v.HR}")
            if v.RR:   vitals_parts.append(f"RR={v.RR}")
            if v.SpO2: vitals_parts.append(f"SpO2={v.SpO2}%")
        vitals = " ".join(vitals_parts) or "N/A"

        findings_str = ", ".join(
            f"{k}({v.prob:.0%})" for k, v in findings.items()
        ) if findings else "none"

        snips = "\n".join(
            f"[{s.id}] {s.source or ''} ({s.year or 'n/d'}): {s.quote[:250]}"
            for s in snippets[:8]
        ) if snippets else "none"

        return f"""You are an expert clinical reasoning AI producing a Diagnostic Decision Support report.
Output ONLY valid JSON with no markdown, no code fences, no extra text.

PATIENT:
Age: {patient.age}yo | Sex: {patient.sex}
Chief Complaint: {patient.chief_complaint}
HPI: {patient.hpi or 'Not provided'}
Vitals: {vitals}
Labs: {json.dumps(patient.labs or {})}
Medications: {', '.join(patient.meds or []) or 'None'}
PMH: {', '.join(patient.pmh or []) or 'None'}
Imaging findings: {findings_str}

EVIDENCE SNIPPETS (cite these IDs):
{snips}

OUTPUT JSON:
{{
  "differentials": [
    {{
      "dx": "Full diagnosis name",
      "icd10": "ICD-10 code",
      "rationale": "Clinical reasoning citing [snippet_id] inline",
      "probability_rank": 1,
      "support": [{{"snippet_id": "pm_xxxxx"}}]
    }}
  ],
  "red_flags": ["Urgent/emergent finding requiring immediate action"],
  "next_steps": ["Recommended test, imaging, or referral"]
}}

Rules:
- 3-5 differentials ranked by probability
- Every differential MUST cite at least one snippet_id
- Include correct ICD-10 codes
- red_flags only for genuinely urgent findings
- next_steps should be specific and actionable
- Research/education only disclaimer applies"""

    async def _call_gemini(self, prompt: str) -> str:
        api_key = settings.GEMINI_API_KEY
        model   = settings.GEMINI_MODEL

        if not api_key:
            return self._fallback("GEMINI_API_KEY not set in .env")

        url = GEMINI_URL.format(model=model)
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 8192,
                "thinkingConfig": {"thinkingBudget": 0},
            },
        }

        log.info("gemini_request", model=model)
        async with httpx.AsyncClient(timeout=60) as client:
            try:
                resp = await client.post(
                    url,
                    json=payload,
                    params={"key": api_key},
                )
                resp.raise_for_status()
                data = resp.json()
                # Log full structure for debugging
                log.info("gemini_raw", keys=list(data.keys()))
                candidates = data.get("candidates", [])
                if not candidates:
                    log.warning("gemini_no_candidates", data=str(data)[:300])
                    return self._fallback("No candidates in Gemini response")
                content_data = candidates[0].get("content", {})
                parts = content_data.get("parts", [])
                if not parts:
                    log.warning("gemini_no_parts", candidate=str(candidates[0])[:300])
                    return self._fallback("No parts in Gemini response")
                text = parts[0].get("text", "")
                log.info("gemini_ok", chars=len(text), preview=text[:200])
                return text
            except httpx.HTTPStatusError as e:
                body = e.response.text[:400]
                log.warning("gemini_http_error", status=e.response.status_code, body=body)
                return self._fallback(f"Gemini HTTP {e.response.status_code}: {body}")
            except Exception as e:
                log.warning("gemini_error", error=str(e))
                return self._fallback(str(e))

    def _parse(
        self, raw: str, snippets: List[CitationSnippet]
    ) -> Tuple[List[Differential], List[str], List[str]]:
        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()

        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start == -1 or end == 0:
            log.warning("no_json_found", raw_preview=raw[:300])
            return (
                [Differential(dx="No JSON in response", icd10="R69",
                              rationale=raw[:300], probability_rank=1)],
                ["LLM did not return structured output"],
                ["Check Gemini API key and quota"],
            )

        try:
            data = json.loads(raw[start:end])
        except json.JSONDecodeError:
            fixed = re.sub(r',\s*([}\]])', r'\1', raw[start:end])
            try:
                data = json.loads(fixed)
            except Exception:
                return (
                    [Differential(dx="JSON parse error", icd10="R69",
                                  rationale=raw[:300], probability_rank=1)],
                    [], [],
                )

        differentials = [
            Differential(
                dx=d.get("dx", "Unknown"),
                icd10=d.get("icd10", "R69"),
                rationale=d.get("rationale", ""),
                probability_rank=d.get("probability_rank", i),
                support=d.get("support", []),
            )
            for i, d in enumerate(data.get("differentials", []), 1)
        ]

        return (
            differentials or [Differential(dx="No differentials generated",
                                           icd10="R69", rationale=raw[:200],
                                           probability_rank=1)],
            data.get("red_flags", []),
            data.get("next_steps", []),
        )

    def _fallback(self, reason: str) -> str:
        return json.dumps({
            "differentials": [{
                "dx": "LLM unavailable",
                "icd10": "R69",
                "rationale": reason[:200],
                "probability_rank": 1,
                "support": [],
            }],
            "red_flags": [],
            "next_steps": [f"Error: {reason[:100]}"],
        })
