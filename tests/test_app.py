import pytest
from fastapi.testclient import TestClient

from doublage.app import app, get_store
from doublage.auth import UserStore


@pytest.fixture
def store(tmp_path) -> UserStore:
    store = UserStore(tmp_path / "doublage.db")
    store.set_user("alice", "secret")
    app.dependency_overrides[get_store] = lambda: store
    yield store
    app.dependency_overrides.clear()


@pytest.fixture
def client(store) -> TestClient:
    return TestClient(app)


def login(client: TestClient, password: str = "secret"):
    return client.post("/connexion", data={"nom": "alice", "mot_de_passe": password},
                       follow_redirects=False)


def test_sante(client):
    r = client.get("/sante")
    assert r.status_code == 200 and r.json()["statut"] == "ok"


def test_accueil_sans_connexion_redirige(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/connexion"


def test_page_de_connexion(client):
    r = client.get("/connexion")
    assert r.status_code == 200 and "mot_de_passe" in r.text


def test_mauvais_mot_de_passe(client):
    r = login(client, "faux")
    assert r.status_code == 303 and "error" in r.headers["location"]
    assert "doublage_session" not in client.cookies


def test_connexion_puis_deconnexion(client):
    r = login(client)
    assert r.status_code == 303 and r.headers["location"] == "/"
    r = client.get("/")
    assert r.status_code == 200 and "alice" in r.text

    client.post("/deconnexion", follow_redirects=False)
    assert client.get("/", follow_redirects=False).status_code == 303


def test_session_invalide_apres_suppression_du_compte(client, store):
    login(client)
    store.delete_user("alice")
    assert client.get("/", follow_redirects=False).status_code == 303
