def test_login_wrong_password(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "nope"})
    assert r.status_code == 401


def test_requires_token(client):
    for p in ("/api/stations", "/api/inspections", "/api/catalog", "/api/stats"):
        assert client.get(p).status_code == 401
    assert client.get("/api/stream?token=bad").status_code == 401


def test_stations_cover_three(client, auth):
    r = client.get("/api/stations", headers=auth).json()
    assert [s["code"] for s in r] == ["PC08", "PC10", "PC12"]
    assert len(next(s for s in r if s["code"] == "PC10")["defects"]) == 8


def test_handle_misalignment_shared(client, auth):
    cat = client.get("/api/catalog", headers=auth).json()["defects"]
    d = next(x for x in cat if x["code"] == "handle_misalignment")
    assert d["stations"] == ["PC10", "PC12"]


def test_filters(client, auth):
    allr = client.get("/api/inspections?page_size=100", headers=auth).json()
    assert allr["total"] > 500
    pc10 = client.get("/api/inspections?station=PC10&page_size=100", headers=auth).json()
    assert pc10["items"] and all(i["station"] == "PC10" for i in pc10["items"])
    dd = client.get("/api/inspections?defect=handle_misalignment&page_size=100", headers=auth).json()
    assert {i["station"] for i in dd["items"]} >= {"PC10", "PC12"}
    assert all(i["verdict"] == "DEFECT" for i in dd["items"])
    assert client.get("/api/inspections?station=XX", headers=auth).status_code == 422
    assert client.get("/api/inspections?date_from=garbage", headers=auth).status_code == 422


def test_sort_and_pagination(client, auth):
    a = client.get("/api/inspections?page_size=5&sort=asc", headers=auth).json()["items"]
    d = client.get("/api/inspections?page_size=5&sort=desc", headers=auth).json()["items"]
    assert a[0]["ts"] <= a[-1]["ts"] and d[0]["ts"] >= d[-1]["ts"]


def test_manual_thickness(client, auth):
    r = client.post("/api/inspections/manual", headers=auth, json={"station": "PC10", "thickness_mm": 2.8})
    assert r.status_code == 201 and r.json()["defect_code"] == "thickness_out_of_range" and r.json()["source"] == "manual"
    r = client.post("/api/inspections/manual", headers=auth, json={"station": "PC10", "thickness_mm": 3.5})
    assert r.json()["verdict"] == "OK"
    assert client.post("/api/inspections/manual", headers=auth, json={"station": "PC10", "thickness_mm": -1}).status_code == 422


def test_simulator_admin_only(client, operator):
    assert client.post("/api/simulator/start", headers=operator).status_code == 403


def test_stats(client, auth):
    s = client.get("/api/stats?days=14", headers=auth).json()
    assert s["total"] > 0 and s["by_defect"] and s["series"]
