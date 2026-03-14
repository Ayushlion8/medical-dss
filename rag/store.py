"""
VectorStore — ChromaDB-backed persistent vector store.
Embedding model: sentence-transformers/all-MiniLM-L6-v2 (local, fast).
"""
from __future__ import annotations

import hashlib
from typing import List, Optional

import chromadb
import structlog
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer

from api.config import settings as app_settings
from api.models import CitationSnippet

log = structlog.get_logger()

EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class VectorStore:
    _instance: Optional["VectorStore"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        log.info("initializing_vector_store")
        self._client = chromadb.HttpClient(
            host=app_settings.CHROMA_HOST,
            port=app_settings.CHROMA_PORT,
        )
        # Create default tenant/database if using v2
        try:
            self._client.heartbeat()
        except Exception:
            pass
        self._collection = self._client.get_or_create_collection(
            name=app_settings.CHROMA_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
        self._embedder = SentenceTransformer(EMBED_MODEL)
        log.info("vector_store_ready",
                collection=app_settings.CHROMA_COLLECTION)

    def add_snippets(self, snippets: List[CitationSnippet]) -> None:
        """Upsert a list of CitationSnippets into the collection."""
        if not snippets:
            return

        docs, ids, metas = [], [], []
        for s in snippets:
            # Stable ID based on content hash
            content = f"{s.pmid or ''}{s.doi or ''}{s.quote}"
            doc_id = hashlib.md5(content.encode()).hexdigest()[:16]
            docs.append(s.quote)
            ids.append(doc_id)
            metas.append({
                "snippet_id": s.id,
                "pmid":       s.pmid or "",
                "doi":        s.doi or "",
                "title":      (s.title or "")[:200],
                "source":     s.source or "",
                "year":       s.year or 0,
                "study_type": s.study_type or "",
                "url":        s.url or "",
            })

        embeddings = self._embedder.encode(docs).tolist()
        self._collection.upsert(
            ids=ids,
            documents=docs,
            embeddings=embeddings,
            metadatas=metas,
        )
        log.info("snippets_upserted", count=len(snippets))

    def query(
        self, query_text: str, n_results: int = 10
    ) -> List[CitationSnippet]:
        """Dense similarity search. Returns CitationSnippet list."""
        try:
            embedding = self._embedder.encode([query_text]).tolist()
            results = self._collection.query(
                query_embeddings=embedding,
                n_results=min(n_results, self._collection.count() or 1),
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            log.warning("chroma_query_error", error=str(e))
            return []

        snippets: List[CitationSnippet] = []
        docs      = results.get("documents", [[]])[0]
        metas     = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for doc, meta, dist in zip(docs, metas, distances):
            snippets.append(CitationSnippet(
                id=meta.get("snippet_id", ""),
                pmid=meta.get("pmid") or None,
                doi=meta.get("doi") or None,
                title=meta.get("title") or None,
                source=meta.get("source") or None,
                year=meta.get("year") or None,
                study_type=meta.get("study_type") or None,
                url=meta.get("url") or None,
                quote=doc,
            ))

        return snippets

    def count(self) -> int:
        try:
            return self._collection.count()
        except Exception:
            return 0
