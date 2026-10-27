from fastapi.testclient import TestClient

from doublage.app import app


def test_sante():
    r = TestClient(app).get("/sante")
    assert r.status_code == 200 and r.json()["statut"] == "ok"


def test_accueil():
    r = TestClient(app).get("/")
    assert r.status_code == 200 and "Doublage" in r.text
