"""
RetrievalAgent — hybrid BM25 + dense-vector search over local Chroma index
                 + live PubMed E-utilities fallback.

Returns: List[CitationSnippet]  (ranked, deduplicated)
"""
from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime
from typing import List, Optional

import httpx
import structlog
from rank_bm25 import BM25Okapi

from api.config import settings
from api.models import CitationSnippet
from rag.store import VectorStore

log = structlog.get_logger()

PUBMED_SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH_URL  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
PUBMED_SUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

STUDY_TYPE_KEYWORDS = {
    "Guideline":      ["guideline", "recommendation", "consensus"],
    "Meta-analysis":  ["meta-analysis", "systematic review"],
    "RCT":            ["randomized", "randomised", "rct", "clinical trial"],
    "Cohort":         ["cohort", "prospective", "retrospective"],
    "Review":         ["review"],
}


class RetrievalAgent:
    def __init__(self):
        self._store = VectorStore()

    async def retrieve(
        self,
        query: str,
        max_results: int = 8,
        recency_years: int = 5,
    ) -> List[CitationSnippet]:
        """
        1. Dense vector search in local Chroma index.
        2. BM25 re-ranking over retrieved candidates.
        3. If < 3 results, fall back to live PubMed E-utilities.
        4. Deduplicate by PMID/DOI. Return top-N.
        """
        # ── Vector search ────────────────────────────────────────────────────
        vector_results = await asyncio.get_event_loop().run_in_executor(
            None, self._store.query, query, max_results * 2
        )

        # ── BM25 re-rank ─────────────────────────────────────────────────────
        if vector_results:
            reranked = self._bm25_rerank(query, vector_results)
        else:
            reranked = []

        # ── PubMed fallback ───────────────────────────────────────────────────
        if len(reranked) < 3:
            log.info("pubmed_fallback", query=query)
            pubmed_results = await self._pubmed_search(
                query, max_results, recency_years
            )
            reranked = self._merge_dedupe(reranked, pubmed_results)

        return reranked[:max_results]

    # ── BM25 ──────────────────────────────────────────────────────────────────
    def _bm25_rerank(
        self, query: str, docs: List[CitationSnippet]
    ) -> List[CitationSnippet]:
        tokenized_corpus = [d.quote.lower().split() for d in docs]
        bm25 = BM25Okapi(tokenized_corpus)
        scores = bm25.get_scores(query.lower().split())
        ranked = sorted(zip(scores, docs), key=lambda x: x[0], reverse=True)
        return [doc for _, doc in ranked]

    # ── PubMed E-utilities ────────────────────────────────────────────────────
    async def _pubmed_search(
        self, query: str, max_results: int, recency_years: int
    ) -> List[CitationSnippet]:
        year_from = datetime.now().year - recency_years
        params = {
            "db":      "pubmed",
            "term":    f"{query} AND {year_from}:{datetime.now().year}[pdat]",
            "retmax":  max_results,
            "retmode": "json",
            "usehistory": "y",
        }
        if settings.PUBMED_API_KEY:
            params["api_key"] = settings.PUBMED_API_KEY

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                # ESearch
                search_resp = await client.get(PUBMED_SEARCH_URL, params=params)
                search_data = search_resp.json()
                pmids = search_data.get("esearchresult", {}).get("idlist", [])
                if not pmids:
                    return []

                # ESummary (metadata)
                summary_resp = await client.get(PUBMED_SUMMARY_URL, params={
                    "db": "pubmed",
                    "id": ",".join(pmids),
                    "retmode": "json",
                    **({"api_key": settings.PUBMED_API_KEY}
                       if settings.PUBMED_API_KEY else {}),
                })
                summary_data = summary_resp.json().get("result", {})

                # EFetch (abstracts)
                fetch_resp = await client.get(PUBMED_FETCH_URL, params={
                    "db":      "pubmed",
                    "id":      ",".join(pmids),
                    "rettype": "abstract",
                    "retmode": "text",
                    **({"api_key": settings.PUBMED_API_KEY}
                       if settings.PUBMED_API_KEY else {}),
                })
                abstracts = self._parse_abstracts(fetch_resp.text, pmids)
                snippets = []
                for pmid in pmids:
                    meta = summary_data.get(pmid, {})
                    abstract = abstracts.get(pmid, "")
                    if not abstract:
                        continue
                    # Take first meaningful sentence as the "quote"
                    quote = self._extract_key_sentence(abstract)
                    doi = next(
                        (aid.get("value", "")
                         for aid in meta.get("articleids", [])
                         if aid.get("idtype") == "doi"),
                        None,
                    )
                    year = None
                    pub_date = meta.get("pubdate", "")
                    if pub_date:
                        try:
                            year = int(pub_date.split()[0])
                        except (ValueError, IndexError):
                            pass

                    snippets.append(CitationSnippet(
                        id=f"pm_{pmid}",
                        pmid=pmid,
                        doi=doi,
                        title=meta.get("title", ""),
                        authors=", ".join(
                            a.get("name", "") for a in meta.get("authors", [])[:3]
                        ),
                        year=year,
                        source=meta.get("fulljournalname", meta.get("source", "")),
                        study_type=self._classify_study_type(
                            meta.get("title", "") + " " + abstract
                        ),
                        quote=quote,
                        url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    ))
                return snippets

            except Exception as e:
                log.warning("pubmed_fetch_error", error=str(e))
                return []

    def _parse_abstracts(
        self, text: str, pmids: List[str]
    ) -> dict[str, str]:
        """Parse multi-abstract EFetch response keyed by PMID."""
        abstracts: dict[str, str] = {}
        blocks = text.split("\n\n")
        for pmid in pmids:
            for i, block in enumerate(blocks):
                if f"PMID- {pmid}" in block:
                    # Look for AB - Abstract in surrounding blocks
                    for j in range(max(0, i - 3), min(len(blocks), i + 5)):
                        if blocks[j].startswith("AB  -"):
                            abstracts[pmid] = blocks[j][6:].strip()
                            break
        return abstracts

    def _extract_key_sentence(self, text: str) -> str:
        """Return first substantive sentence (≥ 40 chars)."""
        for sent in text.replace("\n", " ").split("."):
            s = sent.strip()
            if len(s) >= 40:
                return s + "."
        return text[:300]

    def _classify_study_type(self, text: str) -> str:
        text_lc = text.lower()
        for study_type, keywords in STUDY_TYPE_KEYWORDS.items():
            if any(kw in text_lc for kw in keywords):
                return study_type
        return "Study"

    def _merge_dedupe(
        self,
        primary: List[CitationSnippet],
        secondary: List[CitationSnippet],
    ) -> List[CitationSnippet]:
        seen: set[str] = set()
        result: List[CitationSnippet] = []
        for s in primary + secondary:
            key = s.pmid or s.doi or s.id
            if key not in seen:
                seen.add(key)
                result.append(s)
        return result
