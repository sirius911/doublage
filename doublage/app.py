"""Application web (FastAPI)."""

import threading
import time
from datetime import datetime
from functools import lru_cache
from html import escape
from pathlib import Path
from typing import Annotated
from urllib.parse import quote

from fastapi import Depends, FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import __version__, media
from .assembly import Fit, fit
from .auth import SESSION_DURATION, UserStore
from .config import get_settings
from .jobs import Job, JobManager, JobState
from .pipeline import (clip_path, dub_project, mark_synthesized, reset_voices, synthesize_segment,
                       transcribe_video)
from .projects import VIDEO_EXTENSIONS, Project, ProjectError, ProjectStore
from .segments import Segment, Transcript
from .subtitles import to_srt, to_vtt
from .transcription import FakeTranscriber, Transcriber, WhisperApiTranscriber
from .tts import Engine, FakeEngine, Synthesizer
from .voices import SAMPLE_MAX_SECONDS, SAMPLE_MIN_SECONDS, Voice, VoiceCatalog, VoiceError

SESSION_COOKIE = "doublage_session"

app = FastAPI(title="Doublage", version=__version__)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


def get_store() -> UserStore:
    return UserStore(get_settings().data_dir / "doublage.db")


Store = Annotated[UserStore, Depends(get_store)]


def get_projects() -> ProjectStore:
    settings = get_settings()
    return ProjectStore(settings.data_dir / "doublage.db", settings.data_dir)


Projects = Annotated[ProjectStore, Depends(get_projects)]

_jobs = JobManager()


def get_jobs() -> JobManager:
    return _jobs


Jobs = Annotated[JobManager, Depends(get_jobs)]


def get_transcriber() -> Transcriber:
    settings = get_settings()
    if settings.simuler:
        return FakeTranscriber()
    return WhisperApiTranscriber(settings.whisper_url, settings.whisper_language,
                                 settings.whisper_model, settings.whisper_timeout)


@lru_cache
def get_engine() -> Engine:
    """Chargé au premier usage puis gardé en mémoire (le modèle met plusieurs secondes à charger)."""
    settings = get_settings()
    if settings.simuler:
        return FakeEngine()
    from .tts import PocketEngine  # import tardif : PyTorch est lourd

    return PocketEngine(settings.tts_language, settings.tts_threads)


def get_catalog() -> VoiceCatalog:
    settings = get_settings()
    return VoiceCatalog(settings.tts_voices.replace(" ", "").split(","), settings.tts_voice,
                        settings.data_dir / "voix")


Catalog = Annotated[VoiceCatalog, Depends(get_catalog)]


# Une synthèse à la fois : elle occupe le processeur de la VM partagée.
_synthesis_lock = threading.Lock()
# Les corrections arrivent en rafale (enregistrement automatique) : une écriture à la fois.
_transcript_lock = threading.Lock()


class LoginRequired(Exception):
    pass


@app.exception_handler(LoginRequired)
def redirect_to_login(request: Request, exc: LoginRequired) -> RedirectResponse:
    return RedirectResponse("/connexion", status_code=303)


def current_user(request: Request, store: Store) -> str:
    token = request.cookies.get(SESSION_COOKIE)
    user = store.session_user(token) if token else None
    if user is None:
        raise LoginRequired
    return user


User = Annotated[str, Depends(current_user)]


def page(title: str, body: str, width: int = 40, bar: str = "", full: bool = False) -> str:
    """`bar` : barre de titre (pleine largeur) ; `full` : contenu à la hauteur de l'écran (éditeur)."""
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><title>{title}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="/static/commun.css"></head>
<body{' class="plein"' if full else ""}>
{bar}
<main style="max-width: {width}rem">
{body}
</main>
</body></html>"""


@app.get("/sante")
def health() -> dict:
    return {"statut": "ok", "version": __version__}


@app.get("/connexion", response_class=HTMLResponse)
def login_form(error: bool = False) -> str:
    message = '<p style="color: #b00">Identifiant ou mot de passe incorrect.</p>' if error else ""
    return page("Connexion — Doublage", f"""<h1>Doublage</h1>
{message}
<form method="post" action="/connexion">
<p><label>Identifiant<br><input name="nom" autocomplete="username" required autofocus></label></p>
<p><label>Mot de passe<br><input name="mot_de_passe" type="password" autocomplete="current-password" required></label></p>
<p><button type="submit">Se connecter</button></p>
</form>""")


@app.post("/connexion")
def login(store: Store, nom: Annotated[str, Form()],
          mot_de_passe: Annotated[str, Form()]) -> RedirectResponse:
    if not store.authenticate(nom, mot_de_passe):
        return RedirectResponse("/connexion?error=1", status_code=303)
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(SESSION_COOKIE, store.open_session(nom), max_age=SESSION_DURATION,
                        httponly=True, samesite="lax")
    return response


@app.post("/deconnexion")
def logout(request: Request, store: Store) -> RedirectResponse:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        store.close_session(token)
    response = RedirectResponse("/connexion", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response


def header(user: str, title: str = "") -> str:
    """Barre de titre : retour aux projets, titre de la page (HTML), utilisateur et déconnexion."""
    return f"""<header class="barre"><a class="marque" href="/">Doublage</a>{title}
<span class="espace"></span><a href="/voix">Voix</a><span>{escape(user)}</span>
<form method="post" action="/deconnexion"><button type="submit">Se déconnecter</button></form></header>"""


def home_page(user: str, projects: ProjectStore, error: str = "") -> str:
    rows = "".join(
        f'<li><span><a href="/projets/{p.id}">{escape(p.name)}</a> '
        f'<small>— {escape(p.video_name)}, déposé par {escape(p.owner)} le '
        f'{datetime.fromtimestamp(p.created):%d/%m/%Y à %H:%M}</small></span>'
        f'<form method="post" action="/projets/{p.id}/suppression" data-nom="{escape(p.name)}" '
        f'onsubmit="return confirm(\'Supprimer définitivement le projet « \' + this.dataset.nom + '
        f'\' » ?\\nLa vidéo, la transcription corrigée, les voix et la vidéo doublée seront effacées.\')">'
        f'<button type="submit" class="supprimer" title="Supprimer le projet">×</button></form></li>'
        for p in projects.list()
    )
    message = f'<p style="color: #b00">{escape(error)}</p>' if error else ""
    return page("Doublage", f"""<h2>Nouveau projet</h2>
{message}
<form id="depot" method="post" action="/projets" enctype="multipart/form-data">
<p><label>Vidéo du tutoriel<br><input type="file" name="video" accept="video/*,{",".join(sorted(VIDEO_EXTENSIONS))}" required></label></p>
<p><label>Nom du projet (facultatif)<br><input name="nom" size="40"></label></p>
<p><button type="submit">Déposer la vidéo</button></p>
<div id="envoi" hidden>
<p><progress id="envoi-barre" max="100" value="0" style="width: 100%"></progress></p>
<p id="envoi-texte"></p>
</div>
</form>
{UPLOAD_SCRIPT}
<h2>Projets</h2>
{f'<ul class="projets">{rows}</ul>' if rows else "<p>Aucun projet pour l'instant.</p>"}""", bar=header(user))


# Envoi de la vidéo avec suivi de l'avancement (sans JavaScript, le formulaire classique fonctionne).
UPLOAD_SCRIPT = """<script>
document.getElementById("depot").addEventListener("submit", (event) => {
  event.preventDefault();
  const form = event.target;
  const barre = document.getElementById("envoi-barre");
  const texte = document.getElementById("envoi-texte");
  const mo = (octets) => (octets / 1048576).toFixed(1).replace(".", ",") + " Mo";
  form.querySelector("button").disabled = true;
  document.getElementById("envoi").hidden = false;
  texte.textContent = "Envoi en cours…";

  const xhr = new XMLHttpRequest();
  const debut = Date.now();
  xhr.upload.onprogress = (e) => {
    if (!e.lengthComputable) return;
    barre.value = Math.round(100 * e.loaded / e.total);
    const secondes = (Date.now() - debut) / 1000;
    const debit = e.loaded / Math.max(secondes, 0.1);
    const reste = Math.round((e.total - e.loaded) / Math.max(debit, 1));
    texte.textContent = `${barre.value} % — ${mo(e.loaded)} sur ${mo(e.total)}`
      + (e.loaded < e.total ? ` — encore environ ${reste} s` : "");
  };
  xhr.upload.onload = () => {
    barre.removeAttribute("value");  // barre animée pendant l'enregistrement sur le serveur
    texte.textContent = "Envoi terminé, enregistrement de la vidéo…";
  };
  xhr.onload = () => {
    if (xhr.status < 400) {
      location.href = xhr.responseURL;  // page du nouveau projet
    } else {
      document.open(); document.write(xhr.responseText); document.close();
    }
  };
  xhr.onerror = () => {
    texte.textContent = "L'envoi a échoué (connexion interrompue ?). Réessayez.";
    form.querySelector("button").disabled = false;
  };
  xhr.open("POST", form.action);
  xhr.send(new FormData(form));
});
</script>"""


@app.get("/", response_class=HTMLResponse)
def home(user: User, projects: Projects) -> str:
    return home_page(user, projects)


@app.post("/projets", response_model=None)
def create_project(user: User, projects: Projects, video: UploadFile,
                   nom: Annotated[str, Form()] = "") -> RedirectResponse | HTMLResponse:
    try:
        project = projects.create(nom, video.filename or "", video.file, user)
    except ProjectError as e:
        return HTMLResponse(home_page(user, projects, str(e)), status_code=400)
    return RedirectResponse(f"/projets/{project.id}", status_code=303)


def voices_page(user: str, catalog: VoiceCatalog, error: str = "") -> str:
    rows = []
    for v in catalog.list():
        if v.added_by is None:
            rows.append(f"<li><span>{escape(v.label)} <small>— voix prédéfinie de Pocket TTS</small></span></li>")
            continue
        rows.append(
            f'<li><span>{escape(v.label)} <small>— ajoutée par {escape(v.added_by)} le '
            f'{datetime.fromtimestamp(v.added):%d/%m/%Y}</small> '
            f'<audio controls preload="none" src="/voix/{escape(v.id)}/echantillon"></audio></span>'
            f'<form method="post" action="/voix/{escape(v.id)}/suppression" data-nom="{escape(v.label)}" '
            f'onsubmit="return confirm(\'Supprimer la voix « \' + this.dataset.nom + \' » ?\')">'
            f'<button type="submit" class="supprimer" title="Supprimer la voix">×</button></form></li>')
    message = f'<p style="color: #b00">{escape(error)}</p>' if error else ""
    return page("Voix — Doublage", f"""<h2>Voix disponibles</h2>
<ul class="projets">{"".join(rows)}</ul>
<h2>Ajouter une voix à partir d'un échantillon</h2>
{message}
<p><small>Un enregistrement de {SAMPLE_MIN_SECONDS} à {SAMPLE_MAX_SECONDS} secondes d'une seule personne
qui parle naturellement, sans musique ni bruit de fond : la qualité de l'échantillon (écho, souffle)
se retrouve dans la voix produite. Fichier audio ou vidéo ; seules les {SAMPLE_MAX_SECONDS} premières
secondes sont gardées. L'échantillon reste sur le serveur de l'établissement.</small></p>
<form method="post" action="/voix" enctype="multipart/form-data">
<p><label>Nom de la voix<br><input name="nom" size="30" required></label></p>
<p><label>Échantillon<br><input type="file" name="echantillon" accept="audio/*,video/*" required></label></p>
<p><label><input type="checkbox" name="accord" value="1" required> La personne enregistrée a donné son
accord pour que sa voix soit utilisée dans les tutoriels.</label></p>
<p><button type="submit">Ajouter la voix</button></p>
</form>""", bar=header(user, '<span>›</span><span class="titre">Voix</span>'))


@app.get("/voix", response_class=HTMLResponse)
def voices(user: User, catalog: Catalog) -> str:
    return voices_page(user, catalog)


@app.post("/voix", response_model=None)
def add_voice(user: User, catalog: Catalog, nom: Annotated[str, Form()], echantillon: UploadFile,
              accord: Annotated[bool, Form()] = False) -> RedirectResponse | HTMLResponse:
    try:
        if not accord:
            raise VoiceError("L'accord de la personne enregistrée est obligatoire.")
        catalog.add(nom, echantillon.file, user)
    except VoiceError as e:
        return HTMLResponse(voices_page(user, catalog, str(e)), status_code=400)
    return RedirectResponse("/voix", status_code=303)


def custom_voice(voice_id: str, catalog: Catalog) -> Voice:
    voice = catalog.get(voice_id)
    if voice is None or voice.added_by is None:
        raise HTTPException(404, "Voix introuvable")
    return voice


@app.get("/voix/{voice_id}/echantillon")
def voice_sample(user: User, voice: Annotated[Voice, Depends(custom_voice)]) -> FileResponse:
    return FileResponse(voice.ref, media_type="audio/wav")


@app.post("/voix/{voice_id}/suppression", response_model=None)
def delete_voice(user: User, voice: Annotated[Voice, Depends(custom_voice)], catalog: Catalog,
                 projects: Projects) -> RedirectResponse | HTMLResponse:
    used = [p.name for p in projects.list() if p.voice == voice.id]
    if used:  # ces projets repasseraient sans prévenir sur la voix par défaut
        return HTMLResponse(voices_page(user, catalog, f"« {voice.label} » est utilisée par : "
                                        f"{', '.join(used)}. Choisissez une autre voix dans ces projets "
                                        f"avant de la supprimer."), status_code=409)
    with _synthesis_lock:
        catalog.delete(voice.id)
    return RedirectResponse("/voix", status_code=303)


def get_project(project_id: int, projects: Projects) -> Project:
    project = projects.get(project_id)
    if project is None:
        raise HTTPException(404, "Projet introuvable")
    return project


CurrentProject = Annotated[Project, Depends(get_project)]


def get_synthesizer(project: CurrentProject, catalog: Catalog,
                    engine: Annotated[Engine, Depends(get_engine)]) -> Synthesizer:
    """Synthétiseur de la voix choisie pour le projet."""
    return engine.voice(catalog.for_project(project.voice).ref)


@app.post("/projets/{project_id}/suppression", response_model=None)
def delete_project(user: User, project: CurrentProject, projects: Projects,
                   jobs: Jobs) -> RedirectResponse | HTMLResponse:
    """Supprime le projet et tous ses fichiers (la confirmation est demandée par la page)."""
    job = jobs.get(project.id)
    if job is not None and job.active:  # le traitement écrirait dans un dossier effacé
        work = "la transcription" if job.kind == "transcription" else "le doublage"
        return HTMLResponse(home_page(user, projects, f"« {project.name} » ne peut pas être supprimé "
                                      f"pendant {work} en cours : réessayez une fois le traitement terminé."),
                            status_code=409)
    with _synthesis_lock, _transcript_lock:  # attend la fin d'une voix ou d'une correction en cours
        projects.delete(project.id)
    return RedirectResponse("/", status_code=303)


def timecode(seconds: float) -> str:
    return f"{int(seconds // 60):02d}:{seconds % 60:04.1f}"


def voice_fit(project: Project, transcript: Transcript, segment: Segment) -> tuple[Fit, str] | None:
    """Calage de la voix existante d'une phrase dans son créneau (None : pas encore de voix)."""
    path = clip_path(project.folder, segment.id)
    if not path.exists():
        return None
    return fit(segment, transcript.slot_end(segment), media.wav_duration(path),
               get_settings().acceleration_max)


def segment_row(project: Project, transcript: Transcript, s: Segment) -> str:
    calage = voice_fit(project, transcript, s)
    voice = f' data-voix data-calage="{calage[0]}"' if calage else ""
    return (
        f'<li data-id="{s.id}" data-debut="{s.start}" data-fin="{s.end}" data-etat="{s.status}"{voice}>'
        f'<button type="button" class="aller" title="Aller à ce moment de la vidéo">'
        f'{timecode(s.start)}</button> <span class="texte" contenteditable="plaintext-only" '
        f'spellcheck="true" title="Original : {escape(s.original_text)}">{escape(s.text)}</span>'
        f'<span class="actions"><button type="button" class="original">▶ Original</button>'
        f'<button type="button" class="voix">▶ Voix</button>'
        f'<span class="calage" title="{escape(calage[1]) if calage else ""}">●</span>'
        f'<span class="etat"></span></span></li>'
    )


def voice_choice(project: Project, catalog: VoiceCatalog) -> str:
    """Choix de la voix du projet ; en changer efface les voix déjà générées (confirmation)."""
    current = catalog.for_project(project.voice)
    voices = catalog.list()
    if current not in voices:
        voices.insert(0, current)
    options = "".join(f'<option value="{escape(v.id)}"{" selected" if v == current else ""}>'
                      f'{escape(v.label)}</option>' for v in voices)
    return f"""<form id="choix-voix" method="post" action="/projets/{project.id}/voix"
 onchange="if (confirm('Changer de voix efface les voix déjà générées pour ce projet (le texte corrigé est conservé). Continuer ?')) this.submit(); else this.reset()">
<label>Voix : <select name="voix">{options}</select></label> <small><a href="/voix">ajouter une voix</a></small>
<noscript><button type="submit">Changer</button></noscript></form>"""


def editor(project: Project, job: Job | None, catalog: VoiceCatalog) -> str:
    """Vidéo avec le texte de la phrase en cours affiché sur l'image, et liste des phrases."""
    transcript = Transcript.load(project.transcript_path)
    rows = "".join(segment_row(project, transcript, s) for s in transcript.segments)
    n = len(transcript.segments)
    return f"""<link rel="stylesheet" href="/static/editeur.css">
<div class="editeur">
<div class="colonne-video">
<div class="ecran">
<video id="video" src="/projets/{project.id}/video" controls preload="metadata"></video>
<div id="sur-image" hidden spellcheck="true"></div>
</div>
<div class="sous-video">
{voice_choice(project, catalog)}
<p><small>Mettez la vidéo en pause pour corriger le texte sur l'image, ou corrigez-le dans la liste :
les modifications sont enregistrées automatiquement. Cliquez sur une phrase pour y placer la vidéo ;
« ▶ Original » rejoue la phrase d'origine, « ▶ Voix » fait entendre la voix de synthèse (créée si besoin).
La pastille indique si la voix tient dans le temps de la phrase d'origine : <span style="color: #2e7d32">●</span> oui,
<span style="color: #ef8a00">●</span> corrigé automatiquement (débord sur le silence qui suit ou légère accélération),
<span style="color: #c62828">●</span> trop longue, à raccourcir (détail au survol).
<span id="enregistrement"></span></small></p>
{dubbing_section(project, job)}
</div>
</div>
<div class="colonne-phrases">
<h2>Phrases <small>({n})</small></h2>
<ol id="phrases">{rows}</ol>
</div>
</div>
<script>const PROJET = {project.id};</script>
<script src="/static/editeur.js"></script>"""


def job_progress(project: Project, job: Job, when_done: str = "location.reload()") -> str:
    """Barre indéterminée, étape et temps écoulé, mis à jour toutes les 2 s ; `when_done` (JS) à la fin."""
    return f"""<p><progress style="width: 100%"></progress></p>
<p id="etape">{escape(job.step)}</p>
<script>
(() => {{
  const debut = Date.now() / 1000 - {time.time() - job.started:.0f};
  const suivi = setInterval(async () => {{
    const etat = await (await fetch("/projets/{project.id}/etat")).json();
    if (etat.etat === "termine" || etat.etat === "erreur") {{ clearInterval(suivi); {when_done}; return; }}
    const s = Math.round(Date.now() / 1000 - debut);
    document.getElementById("etape").textContent = `${{etat.etape}} (${{Math.floor(s / 60)}} min ${{s % 60}} s)`;
  }}, 2000);
}})();
</script>"""


def dubbing_section(project: Project, job: Job | None) -> str:
    if job and job.kind == "doublage" and job.active:
        # À la fin, seule cette section est rafraîchie : la vidéo et les corrections en cours restent.
        return f"""<section id="doublage"><h2>Vidéo doublée</h2>
{job_progress(project, job, "rafraichirDoublage()")}</section>"""
    parts = ['<section id="doublage"><h2>Vidéo doublée</h2>']
    if job and job.kind == "doublage" and job.state == JobState.FAILED:
        parts.append(f'<p style="color: #b00">La génération a échoué : {escape(job.error)}</p>')
    if project.dubbed_video.exists():
        generated = project.dubbed_video.stat().st_mtime
        date = datetime.fromtimestamp(generated).strftime("%d/%m/%Y à %H:%M")
        # Aperçu : le lecteur ci-dessus bascule sur la vidéo doublée, avec le texte et la liste synchronisés.
        parts.append(f"""<p id="choix-son" data-version="{generated:.0f}">Son de la vidéo :
<label><input type="radio" name="son" value="original" checked> original</label>
<label><input type="radio" name="son" value="doublee"> nouvelle voix (aperçu)</label></p>""")
        if project.transcript_path.stat().st_mtime > generated:
            parts.append('<p style="color: #b65c00"><small>Des corrections ont été faites depuis : '
                         "mettez à jour la vidéo doublée pour les entendre.</small></p>")
        parts.append(f'<p><a href="/projets/{project.id}/export" download>Télécharger la vidéo doublée</a> '
                     f'<small>(générée le {date})</small><br><small>Aussi : '
                     f'<a href="/projets/{project.id}/audio" download>voix seule (WAV)</a>, sous-titres '
                     f'<a href="/projets/{project.id}/sous-titres.srt" download>SRT</a> / '
                     f'<a href="/projets/{project.id}/sous-titres.vtt" download>VTT</a></small></p>')
    label = "Mettre à jour la vidéo doublée" if project.dubbed_video.exists() else "Générer la vidéo doublée"
    parts.append(f"""<form method="post" action="/projets/{project.id}/doublage">
<button type="submit">{label}</button>
</form>
</section>""")
    return "\n".join(parts)


def transcription_section(project: Project, job: Job | None) -> str:
    if job and job.kind == "transcription" and job.active:
        # Le serveur Whisper ne donne pas d'avancement : barre indéterminée, étape et temps écoulé.
        return f"""<h2>Transcription</h2>
{job_progress(project, job)}"""
    error = ""
    if job and job.kind == "transcription" and job.state == JobState.FAILED:
        error = f'<p style="color: #b00">La transcription a échoué : {escape(job.error)}</p>'
    return f"""<h2>Transcription</h2>
{error}
<form method="post" action="/projets/{project.id}/transcription">
<button type="submit">Lancer la transcription</button>
</form>"""


@app.get("/projets/{project_id}", response_class=HTMLResponse)
def project_page(user: User, project: CurrentProject, jobs: Jobs, catalog: Catalog) -> str:
    if project.transcript_path.exists():
        content = editor(project, jobs.get(project.id), catalog)
    else:
        content = (f'<video src="/projets/{project.id}/video" controls preload="metadata" '
                   f'style="width: 100%"></video>\n'
                   f'{transcription_section(project, jobs.get(project.id))}')
    title = (f'<span>›</span><span class="titre">{escape(project.name)}</span>'
             f'<span class="detail">{escape(project.video_name)}, déposé par {escape(project.owner)}</span>')
    full = project.transcript_path.exists()
    return page(f"{escape(project.name)} — Doublage", content, width=120 if full else 64,
                bar=header(user, title), full=full)


@app.post("/projets/{project_id}/transcription")
def start_transcription(user: User, project: CurrentProject, jobs: Jobs,
                        transcriber: Annotated[Transcriber, Depends(get_transcriber)]) -> RedirectResponse:
    # Une transcription existante n'est jamais écrasée : elle contient peut-être des corrections.
    if not project.transcript_path.exists():
        jobs.submit(project.id, "transcription",
                    lambda progress: transcribe_video(project.video, project.folder, transcriber, progress))
    return RedirectResponse(f"/projets/{project.id}", status_code=303)


@app.post("/projets/{project_id}/doublage")
def start_dubbing(user: User, project: CurrentProject, jobs: Jobs,
                  synthesizer: Annotated[Synthesizer, Depends(get_synthesizer)]) -> RedirectResponse:
    if not project.transcript_path.exists():
        raise HTTPException(404, "Pas encore de transcription")
    jobs.submit(project.id, "doublage",
                lambda progress: dub_project(project.video, project.folder, project.dubbed_video, synthesizer,
                                             progress, get_settings().acceleration_max,
                                             _synthesis_lock, _transcript_lock))
    return RedirectResponse(f"/projets/{project.id}#doublage", status_code=303)


@app.post("/projets/{project_id}/voix")
def change_voice(user: User, project: CurrentProject, projects: Projects, jobs: Jobs, catalog: Catalog,
                 voix: Annotated[str, Form()]) -> RedirectResponse:
    voice = catalog.get(voix)
    if voice is None:
        raise HTTPException(400, "Voix inconnue")
    job = jobs.get(project.id)
    if job is not None and job.active:  # le doublage en cours mélangerait les deux voix
        raise HTTPException(409, "Impossible de changer de voix pendant un traitement en cours")
    if voice != catalog.for_project(project.voice):
        with _synthesis_lock, _transcript_lock:
            projects.set_voice(project.id, voice.id)
            reset_voices(project.folder)
    return RedirectResponse(f"/projets/{project.id}", status_code=303)


@app.get("/projets/{project_id}/audio")
def dubbed_audio(user: User, project: CurrentProject) -> FileResponse:
    """Bande son de la dernière vidéo doublée (voix seule, sans l'image)."""
    path = project.folder / "doublage.wav"
    if not project.dubbed_video.exists() or not path.exists():
        raise HTTPException(404, "La vidéo doublée n'a pas encore été générée")
    return FileResponse(path, media_type="audio/wav", filename=f"{project.name} (voix).wav")


@app.get("/projets/{project_id}/sous-titres.{format}")
def subtitles(user: User, project: CurrentProject, format: str) -> Response:
    """Sous-titres du texte corrigé, aux timecodes des phrases d'origine."""
    if format not in ("srt", "vtt") or not project.transcript_path.exists():
        raise HTTPException(404, "Sous-titres indisponibles")
    transcript = Transcript.load(project.transcript_path)
    content, media_type = ((to_srt(transcript), "application/x-subrip") if format == "srt"
                           else (to_vtt(transcript), "text/vtt"))
    filename = quote(f"{project.name}.{format}")
    return Response(content, media_type=f"{media_type}; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename*=utf-8''{filename}"})


@app.get("/projets/{project_id}/export")
def dubbed_video(user: User, project: CurrentProject, apercu: bool = False) -> FileResponse:
    if not project.dubbed_video.exists():
        raise HTTPException(404, "La vidéo doublée n'a pas encore été générée")
    if apercu:  # lue dans l'éditeur (requêtes partielles), pas téléchargée
        return FileResponse(project.dubbed_video, media_type="video/mp4")
    return FileResponse(project.dubbed_video, filename=f"{project.name} (doublée).mp4")


@app.get("/projets/{project_id}/etat")
def project_state(user: User, project: CurrentProject, jobs: Jobs) -> dict:
    job = jobs.get(project.id)
    if job is None:
        return {"etat": None}
    return {"traitement": job.kind, "etat": job.state, "etape": job.step, "erreur": job.error}


class TextUpdate(BaseModel):
    texte: str


@app.put("/projets/{project_id}/phrases/{segment_id}")
def update_segment(user: User, project: CurrentProject, segment_id: int, update: TextUpdate) -> dict:
    if not project.transcript_path.exists():
        raise HTTPException(404, "Pas encore de transcription")
    with _transcript_lock:
        transcript = Transcript.load(project.transcript_path)
        try:
            segment = transcript.set_text(segment_id, update.texte)
        except KeyError:
            raise HTTPException(404, "Phrase introuvable") from None
        transcript.save(project.transcript_path)
    return {"id": segment.id, "texte": segment.text, "etat": segment.status}


@app.post("/projets/{project_id}/phrases/{segment_id}/voix")
def synthesize_one(user: User, project: CurrentProject, segment_id: int,
                   synthesizer: Annotated[Synthesizer, Depends(get_synthesizer)]) -> dict:
    """(Ré)génère la voix d'une seule phrase, avec son texte actuel. Attend la fin de la synthèse."""
    if not project.transcript_path.exists():
        raise HTTPException(404, "Pas encore de transcription")
    segment = next((s for s in Transcript.load(project.transcript_path).segments if s.id == segment_id), None)
    if segment is None:
        raise HTTPException(404, "Phrase introuvable")
    with _synthesis_lock:
        synthesize_segment(segment, project.folder, synthesizer)
    with _transcript_lock:
        current = mark_synthesized(project.transcript_path, segment)
        transcript = Transcript.load(project.transcript_path)
    level, explanation = voice_fit(project, transcript, segment)
    return {"id": segment_id, "etat": current.status if current else None,
            "calage": level, "calage_texte": explanation}


@app.get("/projets/{project_id}/phrases/{segment_id}/voix")
def segment_voice(user: User, project: CurrentProject, segment_id: int) -> FileResponse:
    path = clip_path(project.folder, segment_id)
    if not path.exists():
        raise HTTPException(404, "Pas encore de voix pour cette phrase")
    return FileResponse(path, media_type="audio/wav", headers={"Cache-Control": "no-store"})


@app.get("/projets/{project_id}/video")
def project_video(user: User, project: CurrentProject) -> FileResponse:
    # FileResponse gère les requêtes partielles (Range) : le lecteur peut se déplacer dans la vidéo.
    return FileResponse(project.video, filename=project.video_name)
