# 🏥 Medical DSS — Agentic Diagnostic Decision Support

> ⚠️ **Research & Education Only — Not a Medical Device — Not for Clinical Use**
> This system has not been validated for diagnostic accuracy. Never use output to make real clinical decisions. Always consult a qualified clinician.

**🔴 Live Demo:** https://medical-dss.streamlit.app &nbsp;|&nbsp; **📖 API Docs:** /api/docs &nbsp;|&nbsp; **🐙 Repo:** https://github.com/Ayushlion8/medical-dss

---

## 🎯 What It Does

Upload a chest X-ray + fill a clinical form → a team of 6 AI agents collaborates to produce a **grounded diagnostic report** in ~10 seconds:

- **4 ranked differentials** with ICD-10 codes and PubMed-cited rationale
- **Imaging findings** from TorchXRayVision DenseNet121 with bounding box overlays
- **Red flags** for urgent/emergent considerations
- **Next steps** — specific tests, imaging, and referrals
- **8 verified citations** with PMID, DOI, study type, and exact quotes
- **PDF export** — full report with overlays + citations + disclaimers

---

## 📸 System in Action

### Step 1 — Upload Chest X-Ray
> DICOM (.dcm), PNG, or JPEG · De-identification enforced · 50 MB max

![Upload Step](docs/upload.png)
<p align="center">
  <img src="chestXray_image.png" width="500"/>
</p>

### Step 2 — Clinical Case Form
> Demographics · Vitals · Labs (JSON) · Medications · Evidence preferences

![Case Form](docs/form.png)
![Case Form](docs/form1.png)
![Case Form](docs/form3.png)
![Case Form](docs/form2.png)

### Step 3a — Red Flags (Urgent Findings)
> Prominently displayed at the top of every report

![Red Flags](docs/redflags.png)

### Step 3b — Imaging Findings with Bounding Box Overlays
> TorchXRayVision DenseNet121 detects 14 pathologies with probability scores and visual overlays

![Imaging Findings](docs/imaging.png)

### Step 3c — Differential Diagnoses + Next Steps
> Ranked differentials with ICD-10 codes · Expandable citation panels · 8 verified PubMed citations

![Differentials](docs/differentials.png)

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│              React UI / Streamlit (3-step wizard)                │
│      Upload CXR → Case Form → Analysis (Overlays + Cites)        │
└──────────────────────────┬───────────────────────────────────────┘
                           │ HTTPS (nginx reverse proxy)
┌──────────────────────────▼───────────────────────────────────────┐
│                   FastAPI  /api/analyze-case                     │
│                                                                  │
│   ┌──────────────────────────────────────────────────────────┐   │
│   │                   OrchestratorAgent                      │   │
│   │  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌────────┐   │   │
│   │  │  Vision  │  │ Retrieval │  │Diagnosis │  │Citation│   │   │
│   │  │  Agent   │  │   Agent   │  │  Agent   │  │Verify. │   │   │
│   │  │ TorchXRV │  │BM25+Chroma│  │  Gemini  │  │        │   │   │
│   │  └──────────┘  └───────────┘  └──────────┘  └────────┘   │   │
│   │       │               │             │     ┌────────────┐ │   │
│   │       └───────────────┴─────────────┘     │Safety Agent│ │   │
│   │                                           │+ PDF Report│ │   │
│   └───────────────────────────────────────────┴────────────┘ │   │
└──────────────┬──────────────────────────┬────────────────────────┘
               │                          │
     ┌─────────▼──────────┐    ┌──────────▼──────────┐
     │  Gemini 2.0/2.5    │    │  ChromaDB + PubMed  │
     │  Flash (LLM)       │    │  355 abstracts RAG  │
     └────────────────────┘    └─────────────────────┘
```

---

## 🤖 Agent Team

| Agent | Responsibility | Model / Tool |
|---|---|---|
| **OrchestratorAgent** | Plans workflow, routes tasks, retries, saves JSONL traces | Python async |
| **VisionAgent** | CXR pathology detection (14 labels) + bounding box overlays | TorchXRayVision DenseNet121 + OpenCV |
| **RetrievalAgent** | Hybrid BM25 + dense vector search + live PubMed E-utilities | ChromaDB + sentence-transformers + Biopython |
| **DiagnosisAgent** | Clinical reasoning, ICD-10, red flags, next steps, inline citations | Gemini 2.0/2.5 Flash |
| **CitationVerifierAgent** | Validates every differential has exact-quote evidence, flags gaps | Python logic |
| **SafetyAgent** | PHI regex scan, dosing guardrail, disclaimer injection, PDF export | ReportLab |

---

## 📊 Sample Output

```
Case: 28yo Male — Sudden right-sided chest pain and dyspnea
Vitals: BP=122/78  HR=104  RR=22  SpO2=94%
Labs: D-dimer=1200, troponin=0.03

🚨 RED FLAGS
  • Sudden onset chest pain + tachycardia + tachypnea → acute cardiopulmonary distress
  • SpO2 94% → hypoxemia
  • Elevated D-dimer → suspicion for pulmonary embolism

🫁 IMAGING FINDINGS (TorchXRayVision DenseNet121)
  Infiltration   52%  [bbox overlay]
  Atelectasis    51%  [bbox overlay]
  Emphysema      50%  [bbox overlay]
  Consolidation  32%  [bbox overlay]

🩻 DIFFERENTIAL DIAGNOSES
  #1  Pneumothorax                  J93.9   [pm_41298238]
  #2  Pulmonary Embolism            I26.99  [pm_41704972]
  #3  Acute Pleurisy with Effusion  J90     [pm_41436219]
  #4  Acute Aortic Dissection       I71.00  [pm_40783555]

➡️  NEXT STEPS
  → Immediate CXR (pneumothorax, pleural effusion)
  → CT pulmonary angiography (CTPA) — elevated D-dimer
  → ECG — cardiac ischemia / right heart strain
  → Point-of-care ultrasound (POCUS)

📚 CITATIONS (8) — ✅ Verified
  [pm_41298238] BMJ Case Reports 2025 · PMID:41298238 · DOI:10.1136/bcr-...
  [pm_41704972] Cureus 2026 · PMID:41704972 · DOI:10.7759/cureus.101643
  ... (all with exact quotes from retrieved abstracts)

⏱️  AGENT TRACES
  VisionAgent              1842 ms
  RetrievalAgent            108 ms  (6 docs retrieved)
  DiagnosisAgent           5695 ms
  CitationVerifierAgent       0 ms
  SafetyAgent               151 ms
  ──────────────────────────────
  Total                    7796 ms

📄 PDF report generated: /reports/97d5ca174418.pdf
```

---

## 🚀 Quick Start

### Option A — Streamlit Cloud (No setup)
Visit **https://medical-dss.streamlit.app** → add your Gemini API key in the sidebar → upload a CXR and go.

### Option B — Local (Full Stack)

```bash
# 1. Clone
git clone https://github.com/Ayushlion8/medical-dss.git
cd medical-dss

# 2. Python environment
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r api/requirements.txt

# 3. Configure
cp .env.template .env
# Set: GEMINI_API_KEY, PUBMED_EMAIL in .env

# 4. Start ChromaDB
docker compose up -d chromadb

# 5. Seed RAG index (~355 PubMed abstracts, ~3 min)
python -m rag.ingestion --max-per-query 30

# 6. Start API
uvicorn api.main:app --port 8000

# 7. Start UI (new terminal)
cd ui && npm install && npm run dev
# → http://localhost:3000
```

### Option C — Full Docker Stack

```bash
cp .env.template .env        # configure first
docker compose up -d --build
bash scripts/seed_rag.sh
# → http://localhost
```

### Run Test Cases (CLI)

```bash
python scripts/test_case.py --case 1   # pneumothorax
python scripts/test_case.py --case 2   # pulmonary embolism
```

---

## 📁 Repository Structure

```
medical-dss/
├── agents/
│   ├── orchestrator.py          # Workflow coordinator + JSONL trace logger
│   ├── vision_agent.py          # TorchXRayVision DenseNet121 + LLaVA fallback
│   ├── retrieval_agent.py       # BM25 + ChromaDB + PubMed E-utilities
│   ├── diagnosis_agent.py       # Gemini clinical reasoning → differentials
│   ├── citation_verifier.py     # Groundedness validation
│   └── safety_agent.py          # PHI scan + dosing guardrail + PDF export
├── rag/
│   ├── store.py                 # ChromaDB singleton + sentence-transformers
│   └── ingestion.py             # ESearch → EFetch → upsert pipeline
├── api/
│   ├── main.py                  # FastAPI app + middleware
│   ├── config.py                # Pydantic settings (.env)
│   ├── models.py                # Full request / response schemas
│   └── routes/                  # analyze · health · reports
├── ui/src/components/
│   ├── UploadStep.jsx           # Dropzone + DICOM + de-id warning
│   ├── CaseFormStep.jsx         # Clinical form + animated agent pipeline
│   └── AnalysisPanel.jsx        # Differentials + overlays + citations
├── streamlit_app.py             # Self-contained Streamlit deployment
├── infra/
│   ├── openapi.yaml             # Full OpenAPI 3.1 specification
│   ├── Dockerfile.api / .ui     # Container builds
│   └── nginx.conf               # Rate limiting + TLS + reverse proxy
├── scripts/
│   ├── test_case.py             # CLI smoke test (no image needed)
│   ├── seed_rag.sh              # Ingest PubMed abstracts
│   └── pull_models.sh           # Pull Ollama models
├── sample_data/
│   ├── synthetic_vignettes.json # 5 test cases (no PHI)
│   └── agent_traces.jsonl       # 3 sample session traces (JSONL)
├── docker-compose.yml
└── .env.template
```

---

## 🔌 API Reference

Full spec: [`infra/openapi.yaml`](infra/openapi.yaml) · Interactive: `http://localhost:8000/api/docs`

### POST `/api/analyze-case`
```json
{
  "case_id": "case-001",
  "patient_context": {
    "age": 28, "sex": "M",
    "chief_complaint": "sudden right-sided chest pain and dyspnea",
    "vitals": {"BP": "122/78", "HR": 104, "RR": 22, "SpO2": 94},
    "labs": {"D_dimer": 1200, "troponin": 0.03},
    "meds": ["metformin"]
  },
  "images": [{"id": "img1", "format": "PNG", "uri": "/uploads/img1.png"}],
  "preferences": {"recency_years": 5, "max_citations": 8}
}
```

**Response includes:** `imaging_findings` · `differentials` (ICD-10 + rationale + citations) · `red_flags` · `next_steps` · `citations` (PMID + DOI + quote) · `groundedness` · `traces` · `report_url`

---

## ⚙️ Configuration

### LLM Options

| Model | Size | Speed | Use Case |
|---|---|---|---|
| `gemini-2.0-flash` | Cloud | ~3s | **Default — best quality/speed** |
| `gemini-2.5-flash` | Cloud | ~5s | Higher reasoning quality |
| `gemma3:4b` via Ollama | ~3 GB | ~30s CPU | Fully local / offline |
| `gemma3:12b` via Ollama | ~10 GB | Fast w/ GPU | Local production |

### Vision Options

| Route | Details |
|---|---|
| **TorchXRayVision** (default) | DenseNet121 — NIH/CheXpert/MIMIC trained, 14 pathology labels, deterministic |
| **LLaVA 13B** (fallback) | Free-form VQA via Ollama when TorchXRV unavailable |
| **PaliGemma 2** (optional) | Set `HF_TOKEN` + `PALIGEMMA_MODEL_ID` for HuggingFace route |

---

## 📚 Data Sources

| Dataset | Size | Use |
|---|---|---|
| NIH ChestX-ray14 | 112k images | 14 pathology labels for TorchXRV training |
| CheXpert | 224k images | Reports + uncertainty labels |
| VinDr-CXR | 18k images | Radiologist bounding boxes (overlay demo) |
| PubMed E-utilities | 355 abstracts | RAG index (ESearch → EFetch → ChromaDB) |

---

## 🛡️ Safety & Compliance

- **Not a medical device** under FDA 21 CFR Part 820 or EU MDR 2017/745
- **PHI guardrail** — SafetyAgent applies HIPAA Safe Harbor regex on all text before PDF export
- **Dosing guardrail** — flags any dosage not backed by a guideline citation
- **Mandatory disclaimer** on all outputs, reports, and the UI banner
- **Preprints labeled** — medRxiv/bioRxiv sources flagged as unreviewed
- **No secrets in repo** — `.env.template` with safe placeholders only
- **Rate limiting** — nginx limits `/api/` to 30 req/min per IP

---

## 📋 Deliverables Checklist

- [x] Working prototype — local + **Streamlit Cloud** (https://medical-dss.streamlit.app)
- [x] 6-agent team — Orchestrator · Vision · Retrieval · Diagnosis · Verifier · Safety
- [x] TorchXRayVision imaging findings + bounding box overlays (14 pathologies)
- [x] Hybrid RAG — BM25 + ChromaDB vector search over 355 PubMed abstracts
- [x] Live PubMed E-utilities — ESearch → EFetch → ESummary pipeline
- [x] Gemini-powered differentials with ICD-10 + inline `[snippet_id]` citations
- [x] Citation verification + groundedness score per case
- [x] PHI scan + dosing guardrail + safety disclaimers
- [x] PDF report generation (ReportLab — overlays + citations + disclaimer)
- [x] Agent traces (JSONL) — 3 sample sessions in `sample_data/`
- [x] 5 synthetic vignettes — pneumothorax · PE · pneumonia · CHF · malignancy
- [x] OpenAPI 3.1 specification (`infra/openapi.yaml`)
- [x] `docker-compose.yml` + `.env.template`
- [x] React UI — 3-step wizard with dark medical theme
- [x] Streamlit app — single-file cloud deployment

---

## 🔭 Observability

```bash
# View agent traces per case
docker compose exec api ls /app/traces/
docker compose exec api cat /app/traces/<case_id>.jsonl | python3 -m json.tool

# Check RAG index size
docker compose exec api python3 -c "from rag.store import VectorStore; print(VectorStore().count())"

# API logs
docker compose logs api -f
```

---

## 🧩 Extending the System

**Add a new agent** — create `agents/my_agent.py`, register in `orchestrator.py`, add output fields to `api/models.py`.

**Add a new RAG source** — edit `rag/ingestion.py` to add Cochrane, ClinicalTrials.gov, or WHO guidelines.

**Switch to PaliGemma** — set `HF_TOKEN` + `PALIGEMMA_MODEL_ID=google/paligemma2-3b-pt-448` in `.env`, update `vision_agent.py`.

---

## 🏗️ Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + Vite + Tailwind CSS |
| Streamlit | Streamlit 1.35+ (cloud deployment) |
| Backend | FastAPI + Uvicorn + Pydantic |
| LLM | Google Gemini 2.0/2.5 Flash |
| Vision | TorchXRayVision DenseNet121 + OpenCV |
| Vector DB | ChromaDB 0.6+ |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 |
| BM25 | rank-bm25 |
| Literature | PubMed E-utilities (ESearch + EFetch + ESummary) |
| PDF | ReportLab |
| Infra | Docker + docker-compose + nginx |

---

*Built for the Agentic Diagnostic Decision Support assignment.
All patient data is synthetic — no PHI. Research/education only.*
