#!/usr/bin/env bash
# scripts/pull_models.sh  — pull required Ollama models
# Run once after docker-compose up:  bash scripts/pull_models.sh

set -e
OLLAMA_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"

echo "==> Waiting for Ollama to be ready..."
until curl -s "$OLLAMA_URL/api/tags" > /dev/null 2>&1; do
  sleep 2
done

echo "==> Pulling Gemma 3 12B (text + reasoning)..."
curl -s "$OLLAMA_URL/api/pull" -d '{"name":"gemma3:12b"}' | grep -E '"status"'

echo "==> Pulling LLaVA 13B (vision fallback)..."
curl -s "$OLLAMA_URL/api/pull" -d '{"name":"llava:13b"}' | grep -E '"status"'

echo "==> Done. Models available:"
curl -s "$OLLAMA_URL/api/tags" | python3 -c "
import sys, json
tags = json.load(sys.stdin)
for m in tags.get('models', []):
    print(f\"  • {m['name']}  ({round(m.get('size',0)/1e9, 1)} GB)\")
"
