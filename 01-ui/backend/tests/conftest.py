import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["SIM_AUTOSTART"] = "0"

import pytest
from fastapi.testclient import TestClient

from app.config import DEMO_USERS
from app.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def auth(client):
    u = DEMO_USERS[0]
    r = client.post("/api/auth/login", json={"username": u["username"], "password": u["password"]})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def operator(client):
    u = DEMO_USERS[1]
    r = client.post("/api/auth/login", json={"username": u["username"], "password": u["password"]})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
