import pytest
from fastapi.testclient import TestClient

import doublage.app
from doublage.app import app, get_jobs, get_projects, get_store, get_transcriber
from doublage.auth import UserStore
from doublage.jobs import JobManager
from doublage.projects import ProjectStore
from doublage.segments import Segment, Transcript
from doublage.transcription import FakeTranscriber


@pytest.fixture
def store(tmp_path) -> UserStore:
    store = UserStore(tmp_path / "doublage.db")
    store.set_user("alice", "secret")
    projects = ProjectStore(tmp_path / "doublage.db", tmp_path)
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_projects] = lambda: projects
    jobs = JobManager()
    app.dependency_overrides[get_jobs] = lambda: jobs
    app.dependency_overrides[get_transcriber] = FakeTranscriber
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


def test_depot_d_une_video(client, tmp_path):
    login(client)
    contenu = b"fausse video " * 1000
    r = client.post("/projets", data={"nom": "Tuto Zimbra"},
                    files={"video": ("zimbra.mp4", contenu, "video/mp4")}, follow_redirects=False)
    assert r.status_code == 303
    url = r.headers["location"]
    assert url.startswith("/projets/")

    accueil = client.get("/").text
    assert "Tuto Zimbra" in accueil and "zimbra.mp4" in accueil and "alice" in accueil
    assert "Tuto Zimbra" in client.get(url).text

    video = client.get(url + "/video")
    assert video.status_code == 200 and video.content == contenu
    partiel = client.get(url + "/video", headers={"Range": "bytes=0-9"})
    assert partiel.status_code == 206 and partiel.content == contenu[:10]


def test_depot_format_refuse(client):
    login(client)
    r = client.post("/projets", files={"video": ("notes.txt", b"texte", "text/plain")})
    assert r.status_code == 400 and "Format non pris en charge" in r.text
    assert "Aucun projet" in r.text


def test_projet_inconnu(client):
    login(client)
    assert client.get("/projets/999").status_code == 404


def test_projets_reserves_aux_utilisateurs_connectes(client):
    assert client.get("/projets/1/video", follow_redirects=False).status_code == 303
    r = client.post("/projets", files={"video": ("a.mp4", b"x", "video/mp4")}, follow_redirects=False)
    assert r.status_code == 303


def creer_projet(client, contenu=b"video", nom="zimbra.mp4") -> str:
    r = client.post("/projets", files={"video": (nom, contenu, "video/mp4")}, follow_redirects=False)
    return r.headers["location"]


def test_transcription_en_tache_de_fond(client, monkeypatch):
    def faux_transcribe(video, workdir, transcriber, progress):
        progress("Transcription…")
        Transcript(5.0, [Segment(0, 0.0, 2.5, "Ouvrez Zimbra.", "Ouvrez Zimbra.")]).save(workdir / "segments.json")

    monkeypatch.setattr(doublage.app, "transcribe_video", faux_transcribe)
    login(client)
    url = creer_projet(client)
    assert "Lancer la transcription" in client.get(url).text
    assert client.get(url + "/etat").json() == {"etat": None}

    r = client.post(url + "/transcription", follow_redirects=False)
    assert r.status_code == 303
    app.dependency_overrides[get_jobs]().wait(int(url.rsplit("/", 1)[1]), timeout=5)

    assert client.get(url + "/etat").json()["etat"] == "termine"
    page = client.get(url).text
    assert "1 phrase." in page and "Ouvrez Zimbra." in page and "00:00.0" in page
    assert "Lancer la transcription" not in page


def test_transcription_en_erreur(client, monkeypatch):
    def en_panne(video, workdir, transcriber, progress):
        raise RuntimeError("Le serveur Whisper n'a pas répondu correctement")

    monkeypatch.setattr(doublage.app, "transcribe_video", en_panne)
    login(client)
    url = creer_projet(client)
    client.post(url + "/transcription")
    app.dependency_overrides[get_jobs]().wait(int(url.rsplit("/", 1)[1]), timeout=5)
    page = client.get(url).text
    assert "La transcription a échoué" in page and "Whisper" in page
    assert "Lancer la transcription" in page  # on peut relancer


def test_transcription_reelle_simulee(client, sample_video):
    """De bout en bout avec ffmpeg et la transcription simulée."""
    login(client)
    url = creer_projet(client, sample_video.read_bytes())
    client.post(url + "/transcription")
    app.dependency_overrides[get_jobs]().wait(int(url.rsplit("/", 1)[1]), timeout=30)
    assert "3 phrases" in client.get(url).text


def test_suivi_de_l_envoi(client):
    login(client)
    page = client.get("/").text
    assert 'id="envoi-barre"' in page and "xhr.upload.onprogress" in page
