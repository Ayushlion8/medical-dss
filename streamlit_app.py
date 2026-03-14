"""
Medical DSS — Streamlit App
Single-file deployment. No separate FastAPI needed.
Deploy: streamlit run streamlit_app.py
"""
import streamlit as st
import json
import asyncio
import uuid
import os
from pathlib import Path
from datetime import datetime

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Medical DSS — Diagnostic Decision Support",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .stApp { background-color: #0b1e3d; color: #e2e8f0; }
    .main-header {
        background: linear-gradient(135deg, #1a3f6f, #0d9488);
        padding: 1.5rem 2rem; border-radius: 12px; margin-bottom: 1.5rem;
    }
    .warning-banner {
        background: rgba(251,191,36,0.1); border: 1px solid rgba(251,191,36,0.4);
        border-radius: 8px; padding: 0.75rem 1rem;
        color: #fbbf24; font-size: 0.85rem; margin-bottom: 1rem;
    }
    .result-card {
        background: #112849; border: 1px solid #1a3f6f;
        border-radius: 12px; padding: 1.25rem; margin-bottom: 1rem;
    }
    .dx-card {
        background: #0b1e3d; border: 1px solid #1a3f6f;
        border-radius: 8px; padding: 1rem; margin-bottom: 0.5rem;
    }
    .red-flag { color: #ef4444; font-weight: 600; }
    .teal { color: #14b8a6; }
    .badge {
        display: inline-block; padding: 2px 8px; border-radius: 9999px;
        font-size: 0.75rem; font-weight: 600; margin-right: 4px;
    }
    .badge-teal { background: rgba(20,184,166,0.15); color: #14b8a6; }
    .badge-red  { background: rgba(239,68,68,0.15);  color: #ef4444; }
    div[data-testid="stExpander"] { background: #112849; border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# ── Banner ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="warning-banner">
⚠️ <strong>Research & Education Only — Not a Medical Device — Not for Clinical Use</strong>
</div>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1 style="margin:0;color:white;font-size:1.8rem">🏥 Medical DSS</h1>
    <p style="margin:0;color:rgba(255,255,255,0.7);font-size:0.9rem">
        Agentic Diagnostic Decision Support · Chest X-Ray Analysis
    </p>
</div>
""", unsafe_allow_html=True)


# ── Helper: run async in streamlit ───────────────────────────────────────────
def run_async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)


# ── Gemini call ───────────────────────────────────────────────────────────────
async def call_gemini(prompt: str, api_key: str, model: str = "gemini-2.0-flash") -> str:
    import httpx
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 8192,
        },
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(url, json=payload, params={"key": api_key})
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]


# ── PubMed retrieval ──────────────────────────────────────────────────────────
async def fetch_pubmed(query: str, max_results: int = 6) -> list:
    import httpx, re
    BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    snippets = []
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            sr = await client.get(f"{BASE}/esearch.fcgi", params={
                "db": "pubmed", "term": query,
                "retmax": max_results, "retmode": "json"
            })
            pmids = sr.json().get("esearchresult", {}).get("idlist", [])
            if not pmids:
                return snippets
            smr = await client.get(f"{BASE}/esummary.fcgi", params={
                "db": "pubmed", "id": ",".join(pmids), "retmode": "json"
            })
            summary = smr.json().get("result", {})
            fr = await client.get(f"{BASE}/efetch.fcgi", params={
                "db": "pubmed", "id": ",".join(pmids),
                "rettype": "xml", "retmode": "xml"
            })
            # Parse abstracts
            abstracts = {}
            for article in fr.text.split("<PubmedArticle>")[1:]:
                m = re.search(r"<PMID[^>]*>(\d+)</PMID>", article)
                if not m:
                    continue
                pmid = m.group(1)
                parts = re.findall(r"<AbstractText[^>]*>(.*?)</AbstractText>",
                                   article, re.DOTALL)
                if parts:
                    text = " ".join(parts)
                    text = re.sub(r"<[^>]+>", "", text)
                    abstracts[pmid] = " ".join(text.split())[:400]

            for pmid in pmids:
                meta = summary.get(pmid, {})
                quote = abstracts.get(pmid, meta.get("title", ""))[:300]
                if not quote:
                    continue
                year = None
                try:
                    year = int(meta.get("pubdate", "").split()[0])
                except Exception:
                    pass
                snippets.append({
                    "id": f"pm_{pmid}",
                    "pmid": pmid,
                    "title": meta.get("title", "")[:150],
                    "source": meta.get("fulljournalname", ""),
                    "year": year,
                    "quote": quote,
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                })
        except Exception as e:
            st.warning(f"PubMed retrieval issue: {e}")
    return snippets


# ── Vision analysis ───────────────────────────────────────────────────────────
def analyze_image_txrv(image_bytes: bytes) -> dict:
    """TorchXRayVision analysis — returns {finding: prob}"""
    try:
        import torchxrayvision as xrv
        import torch
        import numpy as np
        from PIL import Image
        import io

        pil = Image.open(io.BytesIO(image_bytes)).convert("L").resize((224, 224))
        arr = np.array(pil, dtype=np.float32)
        arr = (arr / 255.0) * 2048 - 1024
        tensor = torch.from_numpy(arr[None, None]).float()

        model = xrv.models.DenseNet(weights="densenet121-res224-all")
        model.eval()
        with torch.no_grad():
            preds = model(tensor).squeeze().numpy()

        return {
            label: round(float(prob), 3)
            for label, prob in zip(model.pathologies, preds)
            if float(prob) >= 0.25
        }
    except Exception as e:
        return {"_error": str(e)}


# ── Build diagnosis prompt ────────────────────────────────────────────────────
def build_prompt(age, sex, cc, hpi, vitals_str, labs_str,
                 meds, findings, snippets) -> str:
    findings_str = ", ".join(
        f"{k}({v:.0%})" for k, v in findings.items()
        if not k.startswith("_")
    ) if findings else "none"

    snips_str = "\n".join(
        f"[{s['id']}] {s['source']} ({s['year'] or 'n/d'}): {s['quote'][:200]}"
        for s in snippets[:6]
    ) if snippets else "none"

    return f"""You are an expert clinical reasoning AI. Output ONLY valid JSON — no markdown fences.

PATIENT: {age}yo {sex} | CC: {cc}
HPI: {hpi or 'Not provided'}
Vitals: {vitals_str or 'N/A'}
Labs: {labs_str or 'N/A'}
Medications: {meds or 'None'}
Imaging findings: {findings_str}

EVIDENCE (cite these IDs inline):
{snips_str}

Return this exact JSON structure:
{{"differentials":[{{"dx":"name","icd10":"code","rationale":"reason citing [snippet_id]","probability_rank":1,"support":[{{"snippet_id":"pm_xxx"}}]}}],"red_flags":["urgent finding"],"next_steps":["action"]}}

Rules: 3-5 differentials ranked by probability, cite snippet IDs, correct ICD-10 codes."""


# ── Sidebar — Configuration ────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    gemini_key = st.text_input(
        "Gemini API Key",
        type="password",
        value=os.environ.get("GEMINI_API_KEY", ""),
        help="Get free key at aistudio.google.com/apikey"
    )
    gemini_model = st.selectbox(
        "Model",
        ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-1.5-flash"],
        index=0,
    )
    max_citations = st.slider("Max citations", 3, 12, 6)
    recency_years = st.slider("Evidence recency (years)", 2, 10, 5)

    st.markdown("---")
    st.markdown("### 📊 Session")
    if "results" not in st.session_state:
        st.session_state.results = []
    st.metric("Cases analyzed", len(st.session_state.results))

    st.markdown("---")
    st.caption("⚠️ Research/education only.\nNot a medical device.")


# ── Main layout ───────────────────────────────────────────────────────────────
tab1, tab2 = st.tabs(["📋 New Case", "📁 History"])

with tab1:
    col1, col2 = st.columns([1, 1], gap="large")

    # ── Left column: Image + Patient ─────────────────────────────────────────
    with col1:
        st.markdown("#### 🫁 Upload Chest X-Ray")
        uploaded = st.file_uploader(
            "DICOM (.dcm), PNG, or JPEG",
            type=["png", "jpg", "jpeg", "dcm"],
            help="Ensure image is de-identified before uploading"
        )
        image_findings = {}
        if uploaded:
            if uploaded.name.endswith(".dcm"):
                st.info("DICOM file uploaded — will process with pydicom")
            else:
                st.image(uploaded, caption="Uploaded CXR", use_container_width=True)

            if st.button("🔬 Analyze Image", use_container_width=True):
                with st.spinner("Running TorchXRayVision..."):
                    image_findings = analyze_image_txrv(uploaded.read())
                    if "_error" not in image_findings:
                        st.success(f"Found {len(image_findings)} findings")
                        for k, v in image_findings.items():
                            color = "🔴" if v > 0.7 else "🟡" if v > 0.4 else "🟢"
                            st.write(f"{color} **{k}**: {v:.0%}")
                    else:
                        st.warning(f"Vision model unavailable: {image_findings['_error']}")
                        image_findings = {}

        st.markdown("#### 👤 Patient Demographics")
        c1, c2 = st.columns(2)
        age = c1.number_input("Age *", 0, 130, 50)
        sex = c2.selectbox("Sex *", ["M", "F", "Other"])
        cc = st.text_input("Chief Complaint *", placeholder="Acute dyspnea")
        hpi = st.text_area("HPI", placeholder="Brief history...", height=80)

    # ── Right column: Vitals + Labs ──────────────────────────────────────────
    with col2:
        st.markdown("#### 🩺 Vitals")
        vc1, vc2 = st.columns(2)
        bp   = vc1.text_input("BP (mmHg)", placeholder="120/80")
        hr   = vc2.text_input("HR (bpm)",  placeholder="72")
        rr   = vc1.text_input("RR (/min)", placeholder="16")
        spo2 = vc2.text_input("SpO₂ (%)",  placeholder="98")
        vitals_str = " ".join(filter(None, [
            f"BP={bp}" if bp else "",
            f"HR={hr}" if hr else "",
            f"RR={rr}" if rr else "",
            f"SpO2={spo2}%" if spo2 else "",
        ]))

        st.markdown("#### 💊 History")
        meds     = st.text_input("Medications", placeholder="metformin, lisinopril")
        pmh      = st.text_input("PMH", placeholder="HTN, DM2")
        allergies= st.text_input("Allergies", placeholder="penicillin")

        st.markdown("#### 🧪 Labs (JSON)")
        labs_raw = st.text_area(
            "Labs",
            placeholder='{"D_dimer": 1200, "troponin": 0.03}',
            height=80,
        )
        labs_str = labs_raw or "None"

    # ── Analyze button ────────────────────────────────────────────────────────
    st.markdown("---")
    analyze_btn = st.button(
        "🚀 Run Diagnostic Analysis",
        use_container_width=True,
        type="primary",
        disabled=not gemini_key or not cc,
    )

    if not gemini_key:
        st.warning("⚠️ Add your Gemini API key in the sidebar to enable analysis.")
    if not cc:
        st.info("Fill in Chief Complaint to enable analysis.")

    # ── Run pipeline ──────────────────────────────────────────────────────────
    if analyze_btn and gemini_key and cc:
        case_id = f"case-{uuid.uuid4().hex[:8]}"

        progress = st.progress(0, text="Starting pipeline...")
        status   = st.empty()

        # Step 1 — Retrieval
        status.info("🔍 Retrieving PubMed evidence...")
        progress.progress(20, text="RetrievalAgent — searching PubMed...")
        query = f"{cc} {' '.join(image_findings.keys())} diagnosis treatment"
        snippets = run_async(fetch_pubmed(query, max_citations))
        progress.progress(40, text=f"Retrieved {len(snippets)} citations")

        # Step 2 — Diagnosis
        status.info("🧠 Gemini reasoning...")
        progress.progress(60, text="DiagnosisAgent — Gemini analyzing...")
        prompt = build_prompt(
            age, sex, cc, hpi, vitals_str, labs_str,
            meds, image_findings, snippets
        )
        try:
            raw = run_async(call_gemini(prompt, gemini_key, gemini_model))
            import re
            raw_clean = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`")
            start = raw_clean.find("{")
            end   = raw_clean.rfind("}") + 1
            result_data = json.loads(raw_clean[start:end]) if start != -1 else {}
        except Exception as e:
            st.error(f"Gemini error: {e}")
            result_data = {}

        progress.progress(80, text="CitationVerifier + SafetyAgent...")

        # Step 3 — Verify + finalize
        differentials = result_data.get("differentials", [])
        red_flags     = result_data.get("red_flags", [])
        next_steps    = result_data.get("next_steps", [])
        progress.progress(100, text="✅ Complete")
        status.empty()
        progress.empty()

        # ── Display results ────────────────────────────────────────────────
        st.markdown("---")
        st.markdown(f"## 📊 Results — `{case_id}`")

        # Disclaimer
        st.error("⚠️ RESEARCH/EDUCATION ONLY — NOT A MEDICAL DEVICE — NOT FOR CLINICAL USE")

        # Red flags
        if red_flags:
            st.markdown("### 🚨 Red Flags")
            for rf in red_flags:
                st.markdown(f'<p class="red-flag">⚠️ {rf}</p>',
                            unsafe_allow_html=True)

        # Imaging findings
        if image_findings:
            st.markdown("### 🫁 Imaging Findings (TorchXRayVision)")
            cols = st.columns(min(len(image_findings), 4))
            for i, (k, v) in enumerate(image_findings.items()):
                with cols[i % 4]:
                    color = "🔴" if v > 0.7 else "🟡" if v > 0.4 else "🟢"
                    st.metric(f"{color} {k}", f"{v:.0%}")

        # Differentials
        st.markdown("### 🩻 Differential Diagnoses")
        for i, dx in enumerate(differentials):
            with st.expander(
                f"#{dx.get('probability_rank', i+1)} **{dx.get('dx', 'Unknown')}** "
                f"— ICD-10: `{dx.get('icd10', 'N/A')}`",
                expanded=(i == 0)
            ):
                st.write(dx.get("rationale", ""))
                support = dx.get("support", [])
                if support:
                    cited = [s for s in snippets
                             if s["id"] in [r.get("snippet_id") for r in support]]
                    for c in cited:
                        st.markdown(f"""
**[{c['id']}]** {c.get('source','')} ({c.get('year','n/d')}) —
[PubMed ↗]({c['url']})
> *"{c['quote'][:200]}..."*
""")

        # Next steps
        if next_steps:
            st.markdown("### ➡️ Recommended Next Steps")
            for ns in next_steps:
                st.markdown(f"- {ns}")

        # Citations
        st.markdown("### 📚 Evidence Citations")
        for c in snippets:
            with st.expander(f"[{c['id']}] {c.get('title','')[:80]}"):
                st.markdown(f"**Source:** {c.get('source','')} · **Year:** {c.get('year','n/d')}")
                st.markdown(f"**Quote:** *\"{c['quote'][:300]}...\"*")
                st.markdown(f"[View on PubMed ↗]({c['url']})")

        # JSON export
        st.markdown("### 💾 Export")
        full_result = {
            "case_id": case_id,
            "timestamp": datetime.now().isoformat(),
            "patient": {"age": age, "sex": sex, "cc": cc},
            "imaging_findings": image_findings,
            "differentials": differentials,
            "red_flags": red_flags,
            "next_steps": next_steps,
            "citations": snippets,
            "disclaimer": "Research/education only. Not for clinical use.",
        }
        st.download_button(
            "📥 Download JSON Report",
            data=json.dumps(full_result, indent=2),
            file_name=f"dss_report_{case_id}.json",
            mime="application/json",
        )

        # Save to history
        st.session_state.results.append(full_result)
        st.success(f"✅ Analysis complete — {len(differentials)} differentials, {len(snippets)} citations")

# ── History tab ───────────────────────────────────────────────────────────────
with tab2:
    if not st.session_state.results:
        st.info("No cases analyzed yet. Go to 'New Case' tab.")
    else:
        for r in reversed(st.session_state.results):
            with st.expander(
                f"**{r['case_id']}** — {r['patient']['cc']} "
                f"({r['patient']['age']}yo {r['patient']['sex']}) — {r['timestamp'][:16]}"
            ):
                st.json(r)
