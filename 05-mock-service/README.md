# Mock service (req. 5) - Docker + public tunnel

Exactly two endpoints, as the checkpoint asks. `/docs`, `/redoc` and `/openapi.json` are disabled on purpose.

| Endpoint | Auth | Response |
|---|---|---|
| `GET /health` | none | `200 {"status":"ok"}` |
| `GET /info` | `Authorization: Bearer <token>` | `200 {"team","station","version","timestamp"}`; without or with a wrong token: `401` + `WWW-Authenticate: Bearer` |

**Auth choice (for the PDF):** Bearer token read from env `INFO_TOKEN`. It works with a plain `curl -H`, needs no session or user store for a two-endpoint mock, and is the same scheme the team already used in `udb/nlp-qa-api`. If `INFO_TOKEN` is unset every `/info` call is 401 (fails closed). Comparison uses `secrets.compare_digest`. The scheme name is case-sensitive (`Bearer`).

## Run

Windows (one-click): double-click `iniciar-mock-docker.bat` (or `..\iniciar-todo.bat` from the repo root to start Docker + UI + tunnel together).

```bash
cd 05-mock-service
cp .env.example .env            # set INFO_TOKEN to a long random value:  python3 -c "import secrets;print(secrets.token_urlsafe(24))"
docker compose up --build -d    # or: docker build -t pc10-mock-service:1.0.0 . && docker run -d -p 8000:8000 -e INFO_TOKEN=... pc10-mock-service:1.0.0
python3 smoke_test.py http://localhost:8000 "$INFO_TOKEN"
```

Local tests (no Docker): `uv run pytest -q` (12 tests).

## Tunnel

Windows (one-click): double-click `iniciar-tunel.bat` (ngrok) or `iniciar-tunel-backup.bat` (cloudflared).

Primary (fixed URL, from `udb/nlp-qa-api`): `diffusion-briskly-craftily.ngrok-free.dev`.
**A fixed free ngrok domain only allows one tunnel at a time, so stop the `nlp-qa-api` tunnel first.** ngrok 3.39 is installed in WSL; the authtoken is NOT configured yet:

```bash
ngrok config add-authtoken <authtoken from dashboard.ngrok.com>   # once
./run-tunnel.sh            # ngrok http --url=diffusion-briskly-craftily.ngrok-free.dev 127.0.0.1:8000
./run-tunnel.sh backup     # cloudflared quick tunnel (random URL, no account)
python3 smoke_test.py https://<url> "$INFO_TOKEN"
```

The tunnel and the container must be running during class. Put the URL and test credentials on the PDF cover.

## Evidence (already captured, real run through a Cloudflare tunnel)

- `evidence/curl-public-tunnel.txt`: raw output of the three professor commands.
- `evidence/curl-health-200.png`, `curl-info-401.png`, `curl-info-200.png`: screenshots for the PDF.
- The Dockerfile (`Dockerfile`): `python:3.13-slim`, `uv sync --frozen --no-dev`, non-root user, `HEALTHCHECK` on `/health`.
- That run used a throwaway token and a random `trycloudflare.com` URL: **repeat it with the final URL/token before the PDF is exported** (the URL in the txt is already dead).
