"""Application web (FastAPI)."""

import time
from datetime import datetime
from html import escape
from typing import Annotated

from fastapi import Depends, FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from . import __version__
from .auth import SESSION_DURATION, UserStore
from .config import get_settings
from .jobs import Job, JobManager, JobState
from .pipeline import transcribe_video
from .projects import VIDEO_EXTENSIONS, Project, ProjectError, ProjectStore
from .segments import Transcript
from .transcription import FakeTranscriber, Transcriber, WhisperApiTranscriber

SESSION_COOKIE = "doublage_session"

app = FastAPI(title="Doublage", version=__version__)


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


def page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><title>{title}</title>
<meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="font-family: system-ui, sans-serif; max-width: 40rem; margin: 3rem auto; padding: 0 1rem">
{body}
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


def header(user: str) -> str:
    return f"""<p style="text-align: right">{escape(user)}
<form method="post" action="/deconnexion" style="display: inline"><button type="submit">Se déconnecter</button></form></p>"""


def home_page(user: str, projects: ProjectStore, error: str = "") -> str:
    rows = "".join(
        f'<li><a href="/projets/{p.id}">{escape(p.name)}</a> '
        f'<small>— {escape(p.video_name)}, déposé par {escape(p.owner)} le '
        f'{datetime.fromtimestamp(p.created):%d/%m/%Y à %H:%M}</small></li>'
        for p in projects.list()
    )
    message = f'<p style="color: #b00">{escape(error)}</p>' if error else ""
    return page("Doublage", f"""{header(user)}
<h1>Doublage</h1>
<h2>Nouveau projet</h2>
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
{f"<ul>{rows}</ul>" if rows else "<p>Aucun projet pour l'instant.</p>"}""")


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


def get_project(project_id: int, projects: Projects) -> Project:
    project = projects.get(project_id)
    if project is None:
        raise HTTPException(404, "Projet introuvable")
    return project


CurrentProject = Annotated[Project, Depends(get_project)]


def timecode(seconds: float) -> str:
    return f"{int(seconds // 60):02d}:{seconds % 60:04.1f}"


def transcription_section(project: Project, job: Job | None) -> str:
    if project.transcript_path.exists():
        transcript = Transcript.load(project.transcript_path)
        rows = "".join(f"<li><code>{timecode(s.start)}</code> {escape(s.text)}</li>"
                       for s in transcript.segments)
        return f"""<h2>Transcription</h2>
<p>{len(transcript.segments)} phrase{"s" if len(transcript.segments) > 1 else ""}. L'éditeur arrive dans une prochaine étape.</p>
<ol>{rows}</ol>"""
    if job and job.kind == "transcription" and job.active:
        # Le serveur Whisper ne donne pas d'avancement : barre indéterminée, étape et temps écoulé.
        return f"""<h2>Transcription</h2>
<p><progress style="width: 100%"></progress></p>
<p id="etape">{escape(job.step)}</p>
<script>
const debut = Date.now() / 1000 - {time.time() - job.started:.0f};
setInterval(async () => {{
  const etat = await (await fetch("/projets/{project.id}/etat")).json();
  if (etat.etat === "termine" || etat.etat === "erreur") location.reload();
  const s = Math.round(Date.now() / 1000 - debut);
  document.getElementById("etape").textContent = `${{etat.etape}} (${{Math.floor(s / 60)}} min ${{s % 60}} s)`;
}}, 2000);
</script>"""
    error = ""
    if job and job.kind == "transcription" and job.state == JobState.FAILED:
        error = f'<p style="color: #b00">La transcription a échoué : {escape(job.error)}</p>'
    return f"""<h2>Transcription</h2>
{error}
<form method="post" action="/projets/{project.id}/transcription">
<button type="submit">Lancer la transcription</button>
</form>"""


@app.get("/projets/{project_id}", response_class=HTMLResponse)
def project_page(user: User, project: CurrentProject, jobs: Jobs) -> str:
    return page(f"{escape(project.name)} — Doublage", f"""{header(user)}
<p><a href="/">← Projets</a></p>
<h1>{escape(project.name)}</h1>
<p><small>{escape(project.video_name)}, déposé par {escape(project.owner)}</small></p>
<video src="/projets/{project.id}/video" controls preload="metadata" style="width: 100%"></video>
{transcription_section(project, jobs.get(project.id))}""")


@app.post("/projets/{project_id}/transcription")
def start_transcription(user: User, project: CurrentProject, jobs: Jobs,
                        transcriber: Annotated[Transcriber, Depends(get_transcriber)]) -> RedirectResponse:
    # Une transcription existante n'est jamais écrasée : elle contient peut-être des corrections.
    if not project.transcript_path.exists():
        jobs.submit(project.id, "transcription",
                    lambda progress: transcribe_video(project.video, project.folder, transcriber, progress))
    return RedirectResponse(f"/projets/{project.id}", status_code=303)


@app.get("/projets/{project_id}/etat")
def project_state(user: User, project: CurrentProject, jobs: Jobs) -> dict:
    job = jobs.get(project.id)
    if job is None:
        return {"etat": None}
    return {"traitement": job.kind, "etat": job.state, "etape": job.step, "erreur": job.error}


@app.get("/projets/{project_id}/video")
def project_video(user: User, project: CurrentProject) -> FileResponse:
    # FileResponse gère les requêtes partielles (Range) : le lecteur peut se déplacer dans la vidéo.
    return FileResponse(project.video, filename=project.video_name)
