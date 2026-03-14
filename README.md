# 🏥 Medical DSS — Agentic Diagnostic Decision Support

> **⚠️ RESEARCH & EDUCATION ONLY. NOT A MEDICAL DEVICE. NOT FOR CLINICAL USE.**
> This system has not been validated for diagnostic accuracy. Never use output to make real clinical decisions. Always consult a qualified clinician.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                        BROWSER (React)                       │
│  Upload CXR → Case Form → Analysis Panel (Overlays/Cites)    │
└────────────────────────┬─────────────────────────────────────┘
                         │ HTTPS (nginx reverse proxy)
┌────────────────────────▼─────────────────────────────────────┐
│                    FastAPI  /api/analyze-case                │
│                                                              │
│   ┌────────────────────────────────────────────────────── ┐  │
│   │              OrchestratorAgent                        │  │
│   │  ┌─────────┐ ┌───────────┐ ┌──────────┐ ┌────────┐    │  │
│   │  │ Vision  │ │ Retrieval │ │Diagnosis │ │Citation│    │  │
│   │  │ Agent   │ │  Agent    │ │  Agent   │ │Verify. │    │  │
│   │  │TorchXRV │ │BM25+Chroma│ │  Gemma   │ │        │    │  │
│   │  └────┬────┘ └─────┬─────┘ └────┬─────┘ └────────┘    │  │
│   │       │            │            │    ┌──────────────┐ │  │
│   │       └────────────┴────────────┘    │Safety Agent  │ │  │
│   │                                      │+ PDF report  │ │  │
│   └──────────────────────────────────────┴──────────────┘─│  │
└───────────┬─────────────────────────┬────────────────────────┘
            │                         │
  ┌─────────▼───────┐      ┌──────────▼────────┐
  │  Ollama (Gemma) │      │  ChromaDB (Chroma)│
  │  gemma3:12b     │      │  RAG vector index │
  │  llava:13b      │      │  PubMed abstracts │
  └─────────────────┘      └───────────────────┘
```

### Agent Roles

| Agent | Responsibility | Model/Tool |
|---|---|---|
| **OrchestratorAgent** | Workflow planning, routing, retries, trace saving | Python logic |
| **VisionAgent** | CXR image analysis, pathology probabilities, bbox overlays | TorchXRayVision DenseNet121 + OpenCV |
| **RetrievalAgent** | Hybrid BM25 + dense vector search + live PubMed E-utilities | ChromaDB + sentence-transformers + Biopython |
| **DiagnosisAgent** | Clinical reasoning, differentials, ICD-10, red flags, citations | Gemma 3 12B via Ollama |
| **CitationVerifierAgent** | Validates every differential has exact-quote evidence | Python logic |
| **SafetyAgent** | PHI detection, dosing guardrail, disclaimer injection, PDF export | ReportLab |

---

## Quick Start

### Prerequisites
- Docker + Docker Compose v2
- 16 GB RAM minimum (32 GB recommended for Gemma 12B)
- NVIDIA GPU optional but strongly recommended

### 1. Clone & configure

```bash
git clone https://github.com/your-org/medical-dss.git
cd medical-dss

# Copy environment template
cp .env.template .env

# Edit .env — set your PubMed email (required by NCBI ToS)
# PUBMED_EMAIL=your@email.com
```

### 2. Start services

```bash
docker compose up -d --build

# Check all services are healthy
docker compose ps
docker compose logs api --tail 30
```

### 3. Pull LLM models (one-time, ~15 GB)

```bash
bash scripts/pull_models.sh
```

This pulls:
- `gemma3:12b` — primary diagnosis/reasoning model
- `llava:13b` — vision fallback for LLM-based CXR description

### 4. Seed RAG index from PubMed

```bash
bash scripts/seed_rag.sh
# Default: 30 abstracts × 12 clinical queries ≈ 300-360 documents
```

### 5. Open the UI

Navigate to **http://localhost** (or **http://localhost:3000** for dev).

### 6. Run a test case (no image needed)

```bash
python scripts/test_case.py --case 1   # pneumothorax
python scripts/test_case.py --case 2   # PE
```

---

## Development Setup (without Docker)

```bash
# API
cd medical-dss
python -m venv .venv && source .venv/bin/activate
pip install -r api/requirements.txt
uvicorn api.main:app --reload --port 8000

# UI
cd ui
npm install
npm run dev   # http://localhost:3000
```

Requires local ChromaDB and Ollama running.

---

## Repository Structure

```
medical-dss/
├── agents/
│   ├── orchestrator.py        # Workflow coordinator
│   ├── vision_agent.py        # TorchXRayVision + LLaVA fallback
│   ├── retrieval_agent.py     # BM25 + ChromaDB + PubMed E-utilities
│   ├── diagnosis_agent.py     # Gemma reasoning → differentials
│   ├── citation_verifier.py   # Groundedness check
│   └── safety_agent.py        # PHI scan + PDF export
├── rag/
│   ├── store.py               # ChromaDB vector store
│   └── ingestion.py           # PubMed abstract ingestion script
├── api/
│   ├── main.py                # FastAPI app entry point
│   ├── config.py              # Pydantic settings
│   ├── models.py              # Request / response schemas
│   └── routes/
│       ├── analyze.py         # POST /analyze-case, POST /upload-image
│       ├── health.py          # GET /health
│       └── reports.py         # GET /reports/{id}
├── ui/
│   ├── src/
│   │   ├── App.jsx            # Root component + step router
│   │   ├── components/
│   │   │   ├── Banner.jsx     # Medical device warning banner
│   │   │   ├── Navbar.jsx     # Step progress nav
│   │   │   ├── UploadStep.jsx # Dropzone + DICOM upload
│   │   │   ├── CaseFormStep.jsx # Clinical form + agent progress
│   │   │   └── AnalysisPanel.jsx # Full result display
│   │   └── api/client.js      # Axios API client
│   └── package.json
├── infra/
│   ├── Dockerfile.api         # API container
│   ├── Dockerfile.ui          # React build + nginx
│   ├── nginx.conf             # Reverse proxy + TLS note
│   ├── nginx-ui.conf          # SPA static serving
│   └── openapi.yaml           # Full OpenAPI 3.1 specification
├── scripts/
│   ├── pull_models.sh         # Pull Ollama models
│   ├── seed_rag.sh            # Ingest PubMed abstracts
│   └── test_case.py           # CLI test runner
├── sample_data/
│   ├── synthetic_vignettes.json  # 5 test cases (no PHI)
│   └── agent_traces.jsonl        # 3 sample session traces
├── docker-compose.yml
├── .env.template
└── README.md
```

---

## Model Configuration

### Text model (Gemma via Ollama)

| Model | VRAM | Speed | Recommended for |
|---|---|---|---|
| `gemma3:4b`  | ~4 GB  | Fast   | Development / CPU-only |
| `gemma3:12b` | ~10 GB | Good   | **Default** |
| `gemma3:27b` | ~20 GB | Best   | Production w/ GPU |
| `gemma2:9b`  | ~8 GB  | Good   | Alternative |

Change `OLLAMA_MODEL` in `.env`.

### Vision model

| Route | Details |
|---|---|
| **TorchXRayVision** (default) | DenseNet121 trained on NIH/CheXpert/MIMIC — fast, deterministic, 14 pathology labels |
| **LLaVA 13B** (fallback) | Free-form VQA via Ollama when TorchXRV unavailable |
| **PaliGemma 2** (optional) | Set `HF_TOKEN` and `PALIGEMMA_MODEL_ID` for HuggingFace route |

---

## Data Sources (Public / Synthetic Only)

| Dataset | Use | Link |
|---|---|---|
| NIH ChestX-ray14 | 112k CXR images, 14 labels | [NIH](https://nihcc.app.box.com/v/ChestXray-NIHCC) |
| CheXpert | 224k CXR + reports | [Stanford](https://stanfordmlgroup.github.io/competitions/chexpert/) |
| VinDr-CXR | 18k CXR + radiologist bboxes | [PhysioNet](https://physionet.org/content/vindr-cxr/1.0.0/) |
| PubMed/PMC | Clinical evidence via E-utilities | [NCBI](https://eutils.ncbi.nlm.nih.gov/) |

---

## API Reference

Full spec: [`infra/openapi.yaml`](infra/openapi.yaml)  
Interactive docs: http://localhost:8000/api/docs

### POST `/api/upload-image`
Upload a CXR image. Returns `image_id` for use in `/analyze-case`.

### POST `/api/analyze-case`
Full pipeline: Vision → Retrieval → Diagnosis → Verify → Safety → PDF.  
See [`api/models.py`](api/models.py) for complete request/response schemas.

### GET `/api/reports/{report_id}`
Download generated PDF report.

---

## Observability

Agent traces are saved as JSONL to `/app/traces/` (mapped to Docker volume).

```bash
# View latest traces
docker compose exec api ls /app/traces/
docker compose exec api cat /app/traces/<case_id>_*.jsonl | python3 -m json.tool

# Check RAG index size
docker compose exec api python3 -c "from rag.store import VectorStore; print(VectorStore().count())"
```

---

## Security Notes

- **No secrets in repo.** Use `.env` (git-ignored). `.env.template` has safe placeholders.
- **TLS:** Uncomment TLS blocks in `infra/nginx.conf` and mount certs for production.
- **PHI:** SafetyAgent applies regex-based PHI detection on all text before PDF export. Never upload identifiable data.
- **Rate limiting:** nginx limits `/api/` to 30 req/min per IP.

---

## Compliance & Disclaimers

- This system is **NOT** a medical device under FDA 21 CFR Part 820 or EU MDR 2017/745.
- All outputs are for **research and education** purposes only.
- No PHI should be processed. Use only de-identified or synthetic data.
- The SafetyAgent enforces: PHI scan, dosing guardrails, and mandatory disclaimer on all outputs.
- Preprint results (medRxiv/bioRxiv) are labeled as such in citations.

---

## Extending the System

### Add a new agent
1. Create `agents/my_agent.py` with an `async def run(...)` method.
2. Register it in `agents/orchestrator.py`.
3. Add its output fields to `api/models.py`.

### Add a new RAG source
Edit `rag/ingestion.py` to add queries or new data sources (Cochrane, ClinicalTrials.gov, etc.).

### Switch to PaliGemma
Set `HF_TOKEN` and `PALIGEMMA_MODEL_ID=google/paligemma2-3b-pt-448` in `.env`.  
Update `agents/vision_agent.py` → `_analyze_image_sync` to call the HuggingFace pipeline instead of TorchXRayVision.

---

*Built for the Agentic Diagnostic Decision Support assignment. All patient data used is synthetic (no PHI).*
