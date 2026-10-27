import os
import threading
import time

import pytest
from fastapi.testclient import TestClient

import doublage.app
from doublage.app import app, get_catalog, get_engine, get_jobs, get_projects, get_store, get_transcriber
from doublage.auth import UserStore
from doublage.jobs import JobManager
from doublage.projects import ProjectStore
from doublage.segments import Segment, Status, Transcript
from doublage.transcription import FakeTranscriber
from doublage.tts import FakeEngine
from doublage.voices import VoiceCatalog


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
    engine = FakeEngine()
    app.dependency_overrides[get_engine] = lambda: engine
    app.dependency_overrides[get_catalog] = lambda: VoiceCatalog(["estelle", "alba"], "estelle", tmp_path / "voix")
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


def test_suppression_d_un_projet(client, tmp_path):
    login(client)
    url = creer_projet(client)
    dossier = tmp_path / "projets" / url.rsplit("/", 1)[1]
    assert dossier.exists()
    accueil = client.get("/").text
    assert f'action="{url}/suppression"' in accueil and 'class="supprimer"' in accueil and "confirm(" in accueil

    r = client.post(url + "/suppression", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/"
    assert not dossier.exists()
    assert client.get(url).status_code == 404
    assert "Aucun projet" in client.get("/").text
    assert client.post(url + "/suppression").status_code == 404


def test_suppression_refusee_pendant_un_traitement(client, tmp_path):
    login(client)
    url = creer_projet(client)
    project_id = int(url.rsplit("/", 1)[1])
    fin = threading.Event()
    jobs = app.dependency_overrides[get_jobs]()
    jobs.submit(project_id, "doublage", lambda progress: fin.wait(5))
    try:
        r = client.post(url + "/suppression")
        assert r.status_code == 409 and "pendant le doublage en cours" in r.text
        assert (tmp_path / "projets" / str(project_id)).exists()
    finally:
        fin.set()
        jobs.wait(project_id, timeout=5)
    assert client.post(url + "/suppression", follow_redirects=False).status_code == 303


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
    assert "Phrases <small>(1)</small>" in page and "Ouvrez Zimbra." in page and "00:00.0" in page
    assert "Lancer la transcription" not in page
    # Éditeur : phrase affichable sur l'image au bon timecode
    assert 'id="sur-image"' in page and 'data-debut="0.0" data-fin="2.5"' in page
    assert 'class="aller"' in page and ">00:00.0</button>" in page  # clic → timecode
    assert client.get("/static/editeur.js").status_code == 200


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
    assert "Phrases <small>(3)</small>" in client.get(url).text


def test_suivi_de_l_envoi(client):
    login(client)
    page = client.get("/").text
    assert 'id="envoi-barre"' in page and "xhr.upload.onprogress" in page


def test_correction_d_une_phrase(client, store, tmp_path):
    login(client)
    url = creer_projet(client)
    projet = app.dependency_overrides[get_projects]().get(int(url.rsplit("/", 1)[1]))
    Transcript(5.0, [Segment(0, 0.0, 2.5, "Ouvrez Zim bra.", "Ouvrez Zim bra.")]).save(projet.transcript_path)

    r = client.put(url + "/phrases/0", json={"texte": "Ouvrez Zimbra."})
    assert r.status_code == 200 and r.json()["texte"] == "Ouvrez Zimbra."
    enregistre = Transcript.load(projet.transcript_path).segments[0]
    assert enregistre.text == "Ouvrez Zimbra." and enregistre.original_text == "Ouvrez Zim bra."
    page = client.get(url).text
    assert "Ouvrez Zimbra." in page and 'title="Original : Ouvrez Zim bra."' in page

    assert client.put(url + "/phrases/42", json={"texte": "x"}).status_code == 404


def test_voix_d_une_phrase(client, tmp_path):
    login(client)
    url = creer_projet(client)
    projet = app.dependency_overrides[get_projects]().get(int(url.rsplit("/", 1)[1]))
    Transcript(5.0, [Segment(0, 0.0, 2.5, "Bonjour.", "Bonjour."),
                     Segment(1, 2.5, 5.0, "Au revoir.", "Au revoir.")]).save(projet.transcript_path)
    assert "data-voix" not in client.get(url).text
    assert client.get(url + "/phrases/0/voix").status_code == 404

    r = client.post(url + "/phrases/0/voix")
    assert r.status_code == 200 and r.json()["etat"] == "synthetisee"
    wav = client.get(url + "/phrases/0/voix")
    assert wav.status_code == 200 and wav.headers["content-type"] == "audio/wav"
    assert wav.content[:4] == b"RIFF"
    segments = Transcript.load(projet.transcript_path).segments
    assert segments[0].status == Status.SYNTHESIZED and segments[1].status == Status.TRANSCRIBED
    assert 'data-etat="synthetisee" data-voix' in client.get(url).text

    # Texte corrigé : la voix devient périmée, puis la régénération la remet à jour.
    assert client.put(url + "/phrases/0", json={"texte": "Bonjour à tous."}).json()["etat"] == "modifiee"
    assert client.post(url + "/phrases/0/voix").json()["etat"] == "synthetisee"
    assert len(client.get(url + "/phrases/0/voix").content) > len(wav.content)  # texte plus long

    assert client.post(url + "/phrases/42/voix").status_code == 404


def test_choix_de_la_voix(client):
    login(client)
    url = creer_projet(client)
    projet_id = int(url.rsplit("/", 1)[1])
    projets = app.dependency_overrides[get_projects]()
    Transcript(5.0, [Segment(0, 0.0, 2.5, "Bonjour.", "Bonjour.")]).save(projets.get(projet_id).transcript_path)
    engine = app.dependency_overrides[get_engine]()
    page = client.get(url).text
    assert '<option value="estelle" selected>Estelle</option>' in page and '<option value="alba">Alba</option>' in page

    client.post(url + "/phrases/0/voix")
    assert engine.voices[-1] == "estelle"  # voix par défaut

    r = client.post(url + "/voix", data={"voix": "alba"}, follow_redirects=False)
    assert r.status_code == 303
    projet = projets.get(projet_id)
    assert projet.voice == "alba"
    # Les voix de l'ancienne voix sont effacées, le texte est conservé.
    assert not (projet.folder / "phrases").exists()
    assert Transcript.load(projet.transcript_path).segments[0].status == Status.TRANSCRIBED
    assert '<option value="alba" selected>Alba</option>' in client.get(url).text

    client.post(url + "/phrases/0/voix")
    assert engine.voices[-1] == "alba"
    # Même voix : rien n'est effacé ; voix inconnue : refusée.
    client.post(url + "/voix", data={"voix": "alba"})
    assert (projet.folder / "phrases" / "0000.wav").exists()
    assert client.post(url + "/voix", data={"voix": "inconnue"}).status_code == 400


def test_video_doublee(client, monkeypatch):
    from doublage import media
    monkeypatch.setattr(media, "probe_duration", lambda video: 5.0)
    monkeypatch.setattr(media, "replace_audio", lambda video, audio, output: output.write_bytes(b"video"))
    login(client)
    url = creer_projet(client)
    projet_id = int(url.rsplit("/", 1)[1])
    projet = app.dependency_overrides[get_projects]().get(projet_id)
    Transcript(5.0, [Segment(0, 0.0, 2.5, "Bonjour.", "Bonjour.")]).save(projet.transcript_path)
    assert "Générer la vidéo doublée" in client.get(url).text and "Générer la voix" not in client.get(url).text
    assert client.get(url + "/export").status_code == 404

    r = client.post(url + "/doublage", follow_redirects=False)
    assert r.status_code == 303
    app.dependency_overrides[get_jobs]().wait(projet_id, timeout=30)
    page = client.get(url).text
    assert "Télécharger la vidéo doublée" in page and "Mettre à jour la vidéo doublée" in page
    assert 'data-etat="synthetisee" data-voix' in page
    export = client.get(url + "/export")
    assert export.status_code == 200 and export.content == b"video"
    assert "doubl" in export.headers["content-disposition"]

    # Exports complémentaires : voix seule et sous-titres du texte corrigé.
    audio = client.get(url + "/audio")
    assert audio.status_code == 200 and audio.content[:4] == b"RIFF"
    srt = client.get(url + "/sous-titres.srt")
    assert srt.status_code == 200 and "00:00:00,000 --> 00:00:02,500\nBonjour." in srt.text
    assert "attachment" in srt.headers["content-disposition"]
    assert client.get(url + "/sous-titres.vtt").text.startswith("WEBVTT")
    assert client.get(url + "/sous-titres.txt").status_code == 404

    # Aperçu dans l'éditeur : choix du son, vidéo servie sans téléchargement forcé.
    assert 'name="son" value="doublee"' in page and "Des corrections ont été faites" not in page
    apercu = client.get(url + "/export?apercu=1")
    assert apercu.status_code == 200 and "content-disposition" not in apercu.headers
    # Une correction après la génération : l'aperçu est signalé comme périmé.
    os.utime(projet.dubbed_video, (time.time() - 60, time.time() - 60))
    client.put(url + "/phrases/0", json={"texte": "Bonjour à tous."})
    assert "Des corrections ont été faites" in client.get(url).text


def test_calage_affiche_dans_l_editeur(client):
    login(client)
    url = creer_projet(client)
    projet = app.dependency_overrides[get_projects]().get(int(url.rsplit("/", 1)[1]))
    # Voix simulée : 0,06 s par caractère → 10 caractères = 0,6 s ; 60 caractères = 3,6 s.
    Transcript(10.0, [Segment(0, 0.0, 1.0, "Bonjour !!", "Bonjour !!"),
                      Segment(1, 2.0, 3.0, "x" * 60, "x" * 60),
                      Segment(2, 4.0, 5.0, "Fin.", "Fin.")]).save(projet.transcript_path)
    assert client.post(url + "/phrases/0/voix").json()["calage"] == "vert"
    r = client.post(url + "/phrases/1/voix").json()
    # 3,6 s pour 2 s de créneau : même accélérée de 15 %, elle déborde de 2 + 3,6 / 1,15 - 4 ≈ 1,1 s.
    assert r["calage"] == "rouge" and "Même accélérée de 15 %" in r["calage_texte"]
    assert "1,1 s" in r["calage_texte"]
    page = client.get(url).text
    assert 'data-calage="vert"' in page and 'data-calage="rouge"' in page
    assert page.count("data-calage=") == 2  # pas d'indicateur sans voix


def test_page_des_voix(client, monkeypatch):
    from doublage import media
    from test_voices import faux_echantillon

    monkeypatch.setattr(media, "prepare_voice_sample", faux_echantillon(10))
    login(client)
    page = client.get("/voix").text
    assert "Estelle" in page and "Alba" in page and 'name="accord"' in page and 'href="/voix"' in page

    fichier = {"echantillon": ("moi.m4a", b"son", "audio/mp4")}
    r = client.post("/voix", data={"nom": "Cyrille"}, files=fichier)
    assert r.status_code == 400 and "accord" in r.text
    r = client.post("/voix", data={"nom": "Cyrille", "accord": "1"}, files=fichier, follow_redirects=False)
    assert r.status_code == 303
    voix = app.dependency_overrides[get_catalog]().custom()[0]
    page = client.get("/voix").text
    assert "Cyrille" in page and "ajoutée par alice" in page
    wav = client.get(f"/voix/{voix.id}/echantillon")
    assert wav.status_code == 200 and wav.content[:4] == b"RIFF"
    assert client.get("/voix/estelle/echantillon").status_code == 404

    # Choisie dans un projet : proposée dans l'éditeur, transmise au moteur, non supprimable.
    url = creer_projet(client)
    projets = app.dependency_overrides[get_projects]()
    projet_id = int(url.rsplit("/", 1)[1])
    Transcript(5.0, [Segment(0, 0.0, 2.5, "Bonjour.", "Bonjour.")]).save(projets.get(projet_id).transcript_path)
    assert f'<option value="{voix.id}">Cyrille</option>' in client.get(url).text
    client.post(url + "/voix", data={"voix": voix.id})
    client.post(url + "/phrases/0/voix")
    assert app.dependency_overrides[get_engine]().voices[-1] == voix.ref
    r = client.post(f"/voix/{voix.id}/suppression")
    assert r.status_code == 409 and "utilisée par" in r.text

    client.post(url + "/voix", data={"voix": "estelle"})
    r = client.post(f"/voix/{voix.id}/suppression", follow_redirects=False)
    assert r.status_code == 303 and app.dependency_overrides[get_catalog]().custom() == []
    assert client.post("/voix/estelle/suppression").status_code == 404
