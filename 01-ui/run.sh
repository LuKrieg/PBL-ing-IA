#!/usr/bin/env bash
# One-process demo: builds the SPA and serves it together with the API on http://127.0.0.1:8100
set -euo pipefail
cd "$(dirname "$0")"
(cd frontend && pnpm install --frozen-lockfile && pnpm build)
cd backend && uv sync && exec uv run uvicorn app.main:app --host 127.0.0.1 --port "${PORT:-8100}"
