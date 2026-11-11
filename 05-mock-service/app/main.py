"""Mock service for the IMACASA PC10 checkpoint: exactly two endpoints."""

import os
import secrets
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

TEAM = os.getenv("TEAM_NAME", "Planta")
STATION = os.getenv("STATION", "PC10")
VERSION = os.getenv("APP_VERSION", "1.0.0")

# Docs and schema routes are disabled on purpose: the contract is only /health and /info.
app = FastAPI(title="pc10-mock-service", docs_url=None, redoc_url=None, openapi_url=None)


def _unauthorized() -> JSONResponse:
    return JSONResponse(
        {"detail": "Unauthorized"},
        status_code=401,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _token_ok(header: str | None) -> bool:
    expected = os.getenv("INFO_TOKEN", "")
    if not expected or not header:
        return False
    scheme, _, supplied = header.partition(" ")
    if scheme != "Bearer" or not supplied:
        return False
    return secrets.compare_digest(supplied.encode(), expected.encode())


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/info")
def info(request: Request):
    if not _token_ok(request.headers.get("authorization")):
        return _unauthorized()
    return {
        "team": TEAM,
        "station": STATION,
        "version": VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
