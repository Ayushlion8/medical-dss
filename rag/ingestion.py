"""
rag/ingestion.py — seeds the ChromaDB index with PubMed abstracts.
Uses XML-based EFetch for reliable abstract parsing.
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path
from typing import List

import httpx
import structlog

sys.path.insert(0, str(Path(__file__).parent.parent))

from api.config import settings
from api.models import CitationSnippet
from rag.store import VectorStore

log = structlog.get_logger()

PUBMED_QUERIES = [
    "chest xray pneumothorax diagnosis",
    "pulmonary embolism CT diagnosis treatment",
    "pneumonia chest radiograph management",
    "pleural effusion radiology etiology",
    "congestive heart failure chest xray signs",
    "atelectasis radiology etiology",
    "lung malignancy CT screening diagnosis",
    "ARDS acute respiratory distress syndrome management",
    "cardiomegaly chest radiograph causes",
    "tuberculosis chest xray diagnosis",
    "aortic dissection imaging diagnosis",
    "mediastinal widening differential diagnosis",
]

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


async def fetch_pubmed_abstracts(query: str, max_results: int = 30) -> List[CitationSnippet]:
    snippets: List[CitationSnippet] = []

    esearch_params = {
        "db": "pubmed", "term": query,
        "retmax": max_results, "retmode": "json",
    }
    if settings.PUBMED_EMAIL:
        esearch_params["email"] = settings.PUBMED_EMAIL
    if settings.PUBMED_API_KEY:
        esearch_params["api_key"] = settings.PUBMED_API_KEY

    async with httpx.AsyncClient(timeout=30) as client:
        # ESearch
        try:
            sr = await client.get(f"{BASE}/esearch.fcgi", params=esearch_params)
            sr.raise_for_status()
            pmids: List[str] = sr.json().get("esearchresult", {}).get("idlist", [])
        except Exception as e:
            log.warning("esearch_failed", query=query, error=str(e))
            return snippets

        if not pmids:
            log.warning("no_pmids", query=query)
            return snippets

        log.info("pmids_found", count=len(pmids), query=query)

        # ESummary
        try:
            smr = await client.get(f"{BASE}/esummary.fcgi", params={
                "db": "pubmed", "id": ",".join(pmids), "retmode": "json",
                **({"api_key": settings.PUBMED_API_KEY} if settings.PUBMED_API_KEY else {}),
            })
            summary = smr.json().get("result", {})
        except Exception:
            summary = {}

        # EFetch XML
        try:
            fr = await client.get(f"{BASE}/efetch.fcgi", params={
                "db": "pubmed", "id": ",".join(pmids),
                "rettype": "xml", "retmode": "xml",
                **({"api_key": settings.PUBMED_API_KEY} if settings.PUBMED_API_KEY else {}),
            })
            abstracts = _parse_xml(fr.text, pmids)
        except Exception as e:
            log.warning("efetch_failed", error=str(e))
            abstracts = {}

        for pmid in pmids:
            abstract = abstracts.get(pmid, "").strip()
            meta = summary.get(pmid, {})
            title = meta.get("title", "")

            quote = abstract[:500] if len(abstract) >= 50 else title
            if not quote:
                continue

            doi = next((a.get("value") for a in meta.get("articleids", [])
                        if a.get("idtype") == "doi"), None)
            year = None
            try:
                year = int(meta.get("pubdate", "").split()[0])
            except Exception:
                pass

            snippets.append(CitationSnippet(
                id=f"pm_{pmid}", pmid=pmid, doi=doi,
                title=title[:200],
                authors=", ".join(a.get("name","") for a in meta.get("authors",[])[:3]),
                year=year,
                source=meta.get("fulljournalname", meta.get("source","")),
                study_type=_classify(title + " " + abstract),
                quote=quote,
                url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            ))

    log.info("fetched_abstracts", query=query, count=len(snippets))
    return snippets


def _parse_xml(xml_text: str, pmids: List[str]) -> dict:
    result = {}
    if not xml_text:
        return result
    for article in xml_text.split("<PubmedArticle>")[1:]:
        m = re.search(r"<PMID[^>]*>(\d+)</PMID>", article)
        if not m or m.group(1) not in pmids:
            continue
        parts = re.findall(r"<AbstractText[^>]*>(.*?)</AbstractText>", article, re.DOTALL)
        if parts:
            text = " ".join(parts)
            text = re.sub(r"<[^>]+>", "", text)
            text = text.replace("&lt;","<").replace("&gt;",">").replace("&amp;","&")
            result[m.group(1)] = " ".join(text.split())
    return result


def _classify(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ["guideline","recommendation","consensus"]): return "Guideline"
    if any(k in t for k in ["meta-analysis","systematic review"]): return "Meta-analysis"
    if any(k in t for k in ["randomized","randomised","rct"]): return "RCT"
    if any(k in t for k in ["cohort","prospective","retrospective"]): return "Cohort"
    return "Review"


async def main(queries: List[str], max_per_query: int):
    store = VectorStore()
    total = 0
    for i, query in enumerate(queries):
        log.info("ingesting_query", query=query, progress=f"{i+1}/{len(queries)}")
        snippets = await fetch_pubmed_abstracts(query, max_per_query)
        if snippets:
            store.add_snippets(snippets)
            total += len(snippets)
        await asyncio.sleep(0.4)
    log.info("ingestion_complete", total_ingested=total, index_size=store.count())
    print(f"\n✅ Done — {total} abstracts ingested. Index size: {store.count()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", nargs="*", default=PUBMED_QUERIES)
    parser.add_argument("--max-per-query", type=int, default=30)
    args = parser.parse_args()
    asyncio.run(main(args.queries, args.max_per_query))
