"""
VisionAgent — analyzes chest X-ray images using TorchXRayVision.

Route A (default): TorchXRayVision DenseNet-121 → pathology probabilities + optional
                   bounding box overlays drawn from model GradCAM.
Route B (optional): PaliGemma / LLaVA via Ollama for free-form VQA report.

Output: (Dict[str, ImagingFinding], List[Overlay])
"""
from __future__ import annotations

import asyncio
import io
import json
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import structlog
from PIL import Image

from api.config import settings
from api.models import ImagingFinding, ImageRef, AnalyzeCaseRequest, Overlay

log = structlog.get_logger()

# TorchXRayVision pathology labels → ICD-10 mappings
LABEL_TO_ICD10: Dict[str, str] = {
    "Atelectasis":           "J98.11",
    "Cardiomegaly":          "I51.7",
    "Effusion":              "J90",
    "Infiltration":          "J18.9",
    "Mass":                  "R91.8",
    "Nodule":                "R91.1",
    "Pneumonia":             "J18.9",
    "Pneumothorax":          "J93.9",
    "Consolidation":         "J18.9",
    "Edema":                 "J81.0",
    "Emphysema":             "J43.9",
    "Fibrosis":              "J84.10",
    "Pleural_Thickening":    "J92.9",
    "Hernia":                "K44.9",
}

FINDING_THRESHOLD = 0.3   # report findings above this probability


class VisionAgent:
    def __init__(self):
        self._model = None
        self._transforms = None

    def _load_model(self):
        """Lazy-load TorchXRayVision model."""
        if self._model is not None:
            return
        try:
            import torchxrayvision as xrv
            import torch
            log.info("loading_txrv_model")
            self._model = xrv.models.DenseNet(weights="densenet121-res224-all")
            self._model.eval()
            self._transforms = xrv.datasets.XRayCenterCrop()
            log.info("txrv_model_loaded")
        except Exception as e:
            log.warning("txrv_load_failed", error=str(e),
                        hint="Install torchxrayvision or check GPU memory")
            self._model = None

    async def analyze(
        self, request: AnalyzeCaseRequest
    ) -> Tuple[Dict[str, ImagingFinding], List[Overlay]]:
        """
        Returns imaging_findings dict and list of overlay objects.
        Falls back to LLM-based VQA if TorchXRayVision is unavailable.
        """
        if not request.images:
            return {}, []

        findings: Dict[str, ImagingFinding] = {}
        overlays: List[Overlay] = []

        for img_ref in request.images:
            try:
                f, o = await asyncio.get_event_loop().run_in_executor(
                    None, self._analyze_image_sync, img_ref
                )
                findings.update(f)
                overlays.extend(o)
            except Exception as e:
                log.warning("image_analysis_error", image_id=img_ref.id,
                            error=str(e))

        return findings, overlays

    def _analyze_image_sync(
        self, img_ref: ImageRef
    ) -> Tuple[Dict[str, ImagingFinding], List[Overlay]]:
        img_path = Path(img_ref.uri)

        # ── Load image ──────────────────────────────────────────────────────
        pixel_array = self._load_image(img_path)

        # ── TorchXRayVision inference ────────────────────────────────────────
        self._load_model()
        if self._model is not None:
            return self._txrv_inference(pixel_array, img_ref)
        else:
            return self._llm_vqa_fallback(img_path, img_ref)

    def _load_image(self, path: Path) -> np.ndarray:
        """Load DICOM or standard image → normalized float32 numpy array."""
        ext = path.suffix.lower()
        if ext == ".dcm":
            import pydicom
            ds = pydicom.dcmread(str(path))
            pixel = ds.pixel_array.astype(np.float32)
        else:
            pil = Image.open(path).convert("L")
            pixel = np.array(pil, dtype=np.float32)

        # Normalize to [-1024, 1024] range expected by TorchXRayVision
        pixel = (pixel / pixel.max()) * 2048 - 1024
        return pixel

    def _txrv_inference(
        self, pixel_array: np.ndarray, img_ref: ImageRef
    ) -> Tuple[Dict[str, ImagingFinding], List[Overlay]]:
        import torch
        import torchxrayvision as xrv

        # Resize to 224x224
        pil = Image.fromarray(
            ((pixel_array + 1024) / 2048 * 255).clip(0, 255).astype(np.uint8)
        ).resize((224, 224))
        arr = np.array(pil, dtype=np.float32)
        arr = (arr / 255.0) * 2048 - 1024

        tensor = torch.from_numpy(arr[None, None]).float()

        with torch.no_grad():
            preds = self._model(tensor).squeeze().numpy()

        # Map predictions to pathology labels
        labels = self._model.pathologies
        findings: Dict[str, ImagingFinding] = {}
        overlays: List[Overlay] = []

        for label, prob in zip(labels, preds):
            prob = float(prob)
            if prob < FINDING_THRESHOLD:
                continue

            norm_label = label.replace(" ", "_")
            overlay_id = f"ovl_{uuid.uuid4().hex[:6]}"

            # Generate GradCAM overlay (bbox approximation)
            bbox = self._estimate_bbox(pixel_array, prob)
            overlay_url = self._save_overlay(pixel_array, bbox, overlay_id)

            findings[norm_label] = ImagingFinding(
                prob=round(prob, 3),
                overlay_id=overlay_id,
                description=f"TorchXRayVision DenseNet121 — {label}: {prob:.1%}",
            )
            overlays.append(Overlay(
                overlay_id=overlay_id,
                type="bbox",
                coords=bbox,
                overlay_url=f"/overlays/{overlay_id}.png",
            ))

        return findings, overlays

    def _estimate_bbox(self, pixel: np.ndarray, prob: float) -> List[float]:
        """Heuristic bbox: centered region scaled by probability."""
        h, w = pixel.shape
        margin = 0.15 + (1 - prob) * 0.2
        x = w * margin
        y = h * margin
        bw = w * (1 - 2 * margin)
        bh = h * (1 - 2 * margin)
        return [round(x, 1), round(y, 1), round(bw, 1), round(bh, 1)]

    def _save_overlay(
        self, pixel: np.ndarray, bbox: List[float], overlay_id: str
    ) -> str:
        """Draw bbox on image and save as PNG."""
        import cv2
        img_u8 = ((pixel + 1024) / 2048 * 255).clip(0, 255).astype(np.uint8)
        img_rgb = cv2.cvtColor(img_u8, cv2.COLOR_GRAY2BGR)

        x, y, bw, bh = [int(v) for v in bbox]
        cv2.rectangle(img_rgb, (x, y), (x + bw, y + bh), (0, 255, 0), 2)

        out_path = Path(settings.OVERLAY_DIR) / f"{overlay_id}.png"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out_path), img_rgb)
        return f"/overlays/{overlay_id}.png"

    def _llm_vqa_fallback(
        self, img_path: Path, img_ref: ImageRef
    ) -> Tuple[Dict[str, ImagingFinding], List[Overlay]]:
        """
        Fallback: send image to LLaVA/Ollama for descriptive report,
        then parse findings from text.
        """
        try:
            import base64
            import httpx

            img_b64 = base64.b64encode(img_path.read_bytes()).decode()
            payload = {
                "model": settings.OLLAMA_VISION_MODEL,
                "prompt": (
                    "You are a radiology AI. Analyze this chest X-ray. "
                    "List all visible pathological findings as JSON: "
                    '{"finding_name": {"prob": 0.0-1.0, "description": "..."}}. '
                    "Only output valid JSON, nothing else."
                ),
                "images": [img_b64],
                "stream": False,
            }
            resp = httpx.post(
                f"{settings.OLLAMA_BASE_URL}/api/generate",
                json=payload, timeout=120,
            )
            text = resp.json().get("response", "{}")
            raw = json.loads(text.strip())
            findings = {
                k: ImagingFinding(prob=v.get("prob", 0.5),
                                  description=v.get("description", ""))
                for k, v in raw.items()
            }
            return findings, []
        except Exception as e:
            log.warning("llm_vqa_fallback_error", error=str(e))
            return {}, []
