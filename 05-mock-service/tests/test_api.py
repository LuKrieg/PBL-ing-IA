import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def token(monkeypatch):
    monkeypatch.setenv("INFO_TOKEN", "s3cret-token")


def test_health_open():
    r = client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_info_without_credentials_is_401():
    r = client.get("/info")
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("h", ["Bearer wrong", "bearer s3cret-token", "Bearer ", "Basic s3cret-token", "s3cret-token"])
def test_info_bad_credentials_is_401(h):
    assert client.get("/info", headers={"Authorization": h}).status_code == 401


def test_info_ok():
    r = client.get("/info", headers={"Authorization": "Bearer s3cret-token"})
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"team", "station", "version", "timestamp"}
    assert body["station"] == "PC10" and body["team"] == "Planta"


def test_unset_token_rejects_everything(monkeypatch):
    monkeypatch.delenv("INFO_TOKEN")
    assert client.get("/info", headers={"Authorization": "Bearer "}).status_code == 401
    assert client.get("/info", headers={"Authorization": "Bearer x"}).status_code == 401


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_no_extra_routes(path):
    assert client.get(path).status_code == 404
