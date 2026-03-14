#!/usr/bin/env bash
# scripts/seed_rag.sh — ingest PubMed abstracts into ChromaDB
# Usage: bash scripts/seed_rag.sh [--max-per-query N]

set -e
MAX="${1:-30}"

echo "==> Seeding RAG index from PubMed (max $MAX abstracts per query)..."
docker compose exec api python -m rag.ingestion \
  --max-per-query "$MAX" \
  --queries \
    "chest xray pneumothorax diagnosis" \
    "pulmonary embolism CT diagnosis treatment" \
    "pneumonia chest radiograph management" \
    "pleural effusion radiology etiology" \
    "congestive heart failure chest xray signs" \
    "atelectasis radiology etiology" \
    "lung malignancy CT screening diagnosis" \
    "ARDS acute respiratory distress syndrome management" \
    "cardiomegaly chest radiograph causes" \
    "tuberculosis chest xray diagnosis" \
    "aortic dissection imaging diagnosis" \
    "mediastinal widening differential diagnosis"

echo "==> RAG seed complete."
docker compose exec api python -c "
from rag.store import VectorStore
vs = VectorStore()
print(f'Index size: {vs.count()} documents')
"
