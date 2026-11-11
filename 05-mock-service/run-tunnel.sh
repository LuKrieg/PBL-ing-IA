#!/usr/bin/env bash
# Starts the public tunnel for the mock service (port 8000).
# Primary: ngrok with the fixed domain. Backup: cloudflared quick tunnel (random URL).
set -euo pipefail
DOMAIN="${NGROK_DOMAIN:-diffusion-briskly-craftily.ngrok-free.dev}"
if [[ "${1:-}" == "backup" ]]; then
  exec cloudflared tunnel --url http://localhost:8000
fi
exec ngrok http --url="$DOMAIN" 127.0.0.1:8000
