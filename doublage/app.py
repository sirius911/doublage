"""Application web (FastAPI)."""

import json
import logging
import tempfile
import threading
import time
from datetime import datetime
from functools import cached_property, lru_cache
from html import escape
from pathlib import Path
from typing import Annotated
from urllib.parse import quote

from fastapi import Depends, FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__, media
from .aide import help_content
from .assembly import MANUAL_SPEED_MAX, MANUAL_SPEED_MIN, Fit, fit, speed_factor
from .auth import SESSION_DURATION, UserStore
from .config import get_settings
from .jobs import Job, JobManager, JobState
from .pipeline import (burned_subtitles_marker, clip_path, dub_project, dubbed_voice_path, mark_synthesized, reset_voices,
                       synthesize_segment, transcribe_video)
from .projects import VIDEO_EXTENSIONS, Project, ProjectError, ProjectStore
from .segments import Segment, Transcript, display_text, notation_error
from .subtitles import DEFAULT_FONT, DEFAULT_SIZE, FONTS, SIZES, burn_style, to_srt, to_vtt
from .transcription import FakeTranscriber, Transcriber, WhisperApiTranscriber
from .tts import Engine, FakeEngine, Synthesizer
from .voices import SAMPLE_MAX_SECONDS, SAMPLE_MIN_SECONDS, Voice, VoiceCatalog, VoiceError

SESSION_COOKIE = "doublage_session"
logger = logging.getLogger("doublage")

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
                                 settings.whisper_model, settings.whisper_timeout, settings.whisper_prompt)


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
<span class="espace"></span><a href="/voix">Voix</a><a href="/aide">Aide</a><span>{escape(user)}</span>
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
{upload_progress("Envoi terminé, enregistrement de la vidéo…")}
</form>
<h2>Projets</h2>
{f'<ul class="projets">{rows}</ul>' if rows else "<p>Aucun projet pour l'instant.</p>"}""", bar=header(user))


# Durée lisible en JavaScript : « 45 s », « 2 min 5 s », « 1 h 12 min », « 1 h ».
DURATION_JS = """const duree = (s) => {
  s = Math.max(0, Math.round(s));
  if (s < 60) return `${s} s`;
  const reste = (n, unite) => n ? ` ${n} ${unite}` : "";
  if (s < 3600) return `${Math.floor(s / 60)} min` + reste(s % 60, "s");
  return `${Math.floor(s / 3600)} h` + reste(Math.floor(s % 3600 / 60), "min");
};"""


def upload_progress(saving: str) -> str:
    """Suivi de l'avancement de l'envoi d'un fichier, à placer dans le formulaire (un seul par page).

    `saving` s'affiche une fois le fichier reçu, pendant son traitement par le serveur. Sans JavaScript,
    le formulaire classique fonctionne.
    """
    return """<div id="envoi" hidden>
<p><progress id="envoi-barre" max="100" value="0" style="width: 100%"></progress></p>
<p id="envoi-texte"></p>
</div>
<script>
document.currentScript.closest("form").addEventListener("submit", (event) => {
  event.preventDefault();
  const form = event.target;
  const barre = document.getElementById("envoi-barre");
  const texte = document.getElementById("envoi-texte");
  const mo = (octets) => (octets / 1048576).toFixed(1).replace(".", ",") + " Mo";
  DURATION_JS
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
    const reste = (e.total - e.loaded) / Math.max(debit, 1);
    texte.textContent = `${barre.value} % — ${mo(e.loaded)} sur ${mo(e.total)}`
      + (e.loaded < e.total ? ` — encore environ ${duree(reste)}` : "");
  };
  xhr.upload.onload = () => {
    barre.removeAttribute("value");  // barre animée pendant l'enregistrement sur le serveur
    texte.textContent = SAVING;
  };
  xhr.onload = () => {
    if (xhr.status < 400) {
      location.href = xhr.responseURL;  // page vers laquelle le serveur redirige
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
</script>""".replace("SAVING", json.dumps(saving)).replace("DURATION_JS", DURATION_JS)


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
{upload_progress("Envoi terminé, préparation de l'échantillon…")}
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


@app.get("/aide", response_class=HTMLResponse)
def help_page(user: User) -> str:
    return page("Aide — Doublage", help_content(get_settings().acceleration_max, get_settings().vitesse_min), width=52,
                bar=header(user, '<span>›</span><span class="titre">Aide</span>'))


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


class ProjectVoice:
    """Voix du projet, préparée par le moteur à la première synthèse seulement : la préparation d'un
    échantillon est longue et peut échouer, elle doit se faire sous le verrou de synthèse (ou dans le
    traitement de fond), pas pendant la résolution de la requête."""

    def __init__(self, engine: Engine, ref: str):
        self.engine, self.ref = engine, ref

    @cached_property
    def _synthesizer(self) -> Synthesizer:
        return self.engine.voice(self.ref)

    @property
    def sample_rate(self) -> int:
        return self._synthesizer.sample_rate

    def synthesize(self, text: str):
        return self._synthesizer.synthesize(text)


def get_synthesizer(project: CurrentProject, catalog: Catalog,
                    engine: Annotated[Engine, Depends(get_engine)]) -> Synthesizer:
    """Synthétiseur de la voix choisie pour le projet."""
    return ProjectVoice(engine, catalog.for_project(project.voice).ref)


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


def voice_fit(project: Project, transcript: Transcript, segment: Segment) -> tuple[Fit, str, float] | None:
    """Calage de la voix existante d'une phrase dans son créneau, et vitesse automatique (None : pas de voix)."""
    path = clip_path(project.folder, segment.id)
    if not path.exists():
        return None
    settings, duration, slot_end = get_settings(), media.wav_duration(path), transcript.slot_end(segment)
    level, explanation = fit(segment, slot_end, duration, settings.acceleration_max, settings.vitesse_min)
    auto = speed_factor(segment, slot_end, duration, settings.acceleration_max, settings.vitesse_min)
    return level, explanation, round(auto, 3)


def speed_label(speed: float) -> str:
    return "×" + f"{speed:.2f}".replace(".", ",")


def segment_row(project: Project, transcript: Transcript, s: Segment) -> str:
    calage = voice_fit(project, transcript, s)
    voice = f' data-voix data-calage="{calage[0]}" data-vitesse-auto="{calage[2]}"' if calage else ""
    voice += f' data-vitesse="{s.speed}"' if s.speed is not None else ""
    speed = s.speed if s.speed is not None else calage[2] if calage else 1.0
    voice += " data-origine" if s.keep_original else ""
    voice += " data-vide" if not s.text else ""  # phrase effacée : ni voix ni sous-titre
    voice += " data-notation-invalide" if notation_error(s.text) else ""
    original = " ".join(s.original_text.split())  # comme le texte corrigé (Transcript.set_text)
    return (
        f'<li data-id="{s.id}" data-debut="{s.start}" data-fin="{s.end}" data-etat="{s.status}"{voice}>'
        f'<button type="button" class="aller" title="Aller à ce moment de la vidéo">'
        f'{timecode(s.start)}</button> <span class="texte" contenteditable="plaintext-only" '
        f'spellcheck="true" title="Original : {escape(s.original_text)}" data-original="{escape(original)}">'
        f'{escape(s.text)}</span>'
        f'<button type="button" class="retablir" title="Revenir au texte de la transcription d’origine"'
        f'{"" if s.text != original else " hidden"}>↺</button>'
        f'<span class="actions"><button type="button" class="original">▶ Original</button>'
        f'<button type="button" class="voix">▶ Voix</button>'
        f'<span class="calage" title="{escape(calage[1]) if calage else ""}">●</span>'
        f'<span class="vitesse-reglee">{speed_label(speed)}</span>'
        f'<span class="etat"></span>'
        f'<span class="notation" title="Crochet ou barre en trop : ils apparaîtraient dans les sous-titres. '
        f'Notation attendue : [écrit|prononcé], par ex. [Zimbra|Zimm-bra]">⚠ notation</span>'
        f'<label class="garder" title="La vidéo doublée garde le son d’origine de cette phrase">'
        f'<input type="checkbox"{" checked" if s.keep_original else ""}> voix d’origine</label></span>'
        # Réglage de la vitesse, ouvert par un clic sur la pastille (editeur.js).
        f'<span class="reglage" hidden>Vitesse <input type="range" min="{MANUAL_SPEED_MIN}" '
        f'max="{MANUAL_SPEED_MAX}" step="0.01" value="{speed}"> <output>{speed_label(speed)}</output> '
        f'<button type="button" class="auto" title="Revenir à la vitesse automatique">auto</button></span></li>'
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
<img id="apercu-sous-titres" hidden alt="Aperçu du sous-titre incrusté" title="Cliquez pour fermer l'aperçu">
</div>
<div class="sous-video">
<div class="sous-ecran">{voice_choice(project, catalog)}{sound_choice(project)}</div>
{dubbing_section(project, job)}
</div>
</div>
<div class="colonne-phrases">
<h2>Phrases <small>({n})</small></h2>
<ol id="phrases">{rows}</ol>
</div>
</div>
<div id="enregistrement" role="status" hidden></div>
<script>const PROJET = {project.id};</script>
<script src="/static/editeur.js"></script>"""


def job_progress(project: Project, job: Job, when_done: str = "location.reload()") -> str:
    """Barre indéterminée, étape et temps écoulé, mis à jour toutes les 2 s ; `when_done` (JS) à la fin."""
    return f"""<p><progress style="width: 100%"></progress></p>
<p id="etape">{escape(job.step)}</p>
<script>
(() => {{
  {DURATION_JS}
  const debut = Date.now() / 1000 - {time.time() - job.started:.0f};
  const suivi = setInterval(async () => {{
    const etat = await (await fetch("/projets/{project.id}/etat")).json();
    if (etat.etat === "termine" || etat.etat === "erreur") {{ clearInterval(suivi); {when_done}; return; }}
    document.getElementById("etape").textContent = `${{etat.etape}} (${{duree(Date.now() / 1000 - debut)}})`;
  }}, 2000);
}})();
</script>"""


def subtitle_style_choice(project: Project) -> str:
    """Police et taille des sous-titres incrustés, avec un aperçu sur l'image (affichés si la case est cochée)."""
    font, size = project.subtitle_style
    fonts = "".join(f'<option{" selected" if f == font else ""}>{f}</option>' for f in FONTS)
    sizes = "".join(f'<option value="{s}"{" selected" if s == size else ""}>{label}</option>'
                    for s, label in SIZES.items())
    return f"""<p id="style-sous-titres" class="generer" hidden>
<label>Police <select name="police">{fonts}</select></label>
<label>Taille <select name="taille">{sizes}</select></label>
<button type="button" id="voir-sous-titres">Aperçu sur l'image</button></p>"""


def sound_choice(project: Project) -> str:
    """Aperçu : le lecteur bascule sur la vidéo doublée, avec le texte et la liste synchronisés.

    Masqué tant qu'il n'y a pas de vidéo doublée ; remplacé à la fin de chaque génération (editeur.js).
    """
    exists = project.dubbed_video.exists()
    version = f"{project.dubbed_video.stat().st_mtime:.0f}" if exists else ""
    return f"""<p id="choix-son" data-version="{version}"{"" if exists else " hidden"}>Son de la vidéo :
<label><input type="radio" name="son" value="original" checked> original</label>
<label><input type="radio" name="son" value="doublee"> nouvelle voix (aperçu)</label></p>"""


def dubbing_section(project: Project, job: Job | None) -> str:
    if job and job.kind == "doublage" and job.active:
        # À la fin, seule cette section est rafraîchie : la vidéo et les corrections en cours restent.
        return f"""<section id="doublage"><h2>Vidéo doublée</h2>
{job_progress(project, job, "rafraichirDoublage()")}</section>"""
    parts = ['<section id="doublage"><h2>Vidéo doublée</h2>']
    if job and job.kind == "doublage" and job.state == JobState.FAILED:
        parts.append(f'<p style="color: #b00">La génération a échoué : {escape(job.error)}</p>')
    exists = project.dubbed_video.exists()
    if exists:
        generated = project.dubbed_video.stat().st_mtime
    # Le texte du bouton et l'avertissement suivent la case (editeur.js).
    label = "Mettre à jour la vidéo doublée" if exists else "Générer la vidéo doublée"
    parts.append(f"""<form method="post" action="/projets/{project.id}/doublage">
<p class="generer"><button type="submit" data-libelle="{label}">{label}</button>
<label><input type="checkbox" name="sous_titres" value="1"> Sous-titres incrustés</label></p>
{subtitle_style_choice(project)}
<p id="avertissement-sous-titres" hidden><small>L'image entière est alors ré-encodée : comptez en plus environ
un quart de la durée de la vidéo (un peu plus d'une minute pour 5 minutes).</small></p>
</form>""")
    if exists:
        date = datetime.fromtimestamp(generated).strftime("%d/%m/%Y à %H:%M")
        voice_path = dubbed_voice_path(project.dubbed_video)
        voice = voice_path.read_text(encoding="utf-8") if voice_path.exists() else ""
        voice = f" avec la voix {escape(voice)}" if voice else ""  # vidéos générées avant ce suivi : rien
        burned = ", sous-titres incrustés" if burned_subtitles_marker(project.dubbed_video).exists() else ""
        parts.append(f'<p><a href="/projets/{project.id}/export" download>Télécharger la vidéo doublée</a> '
                     f'<small>(générée le {date}{voice}{burned})</small><br><small>Aussi : '
                     f'<a href="/projets/{project.id}/audio" download>voix seule (WAV)</a>, sous-titres '
                     f'<a href="/projets/{project.id}/sous-titres.srt" download>SRT</a> / '
                     f'<a href="/projets/{project.id}/sous-titres.vtt" download>VTT</a></small></p>')
        if project.transcript_path.stat().st_mtime > generated:
            parts.append('<p style="color: #b65c00"><small>Des corrections ont été faites depuis : '
                         "mettez à jour la vidéo doublée pour les entendre.</small></p>")
    parts.append("</section>")
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
def start_dubbing(user: User, project: CurrentProject, jobs: Jobs, catalog: Catalog, projects: Projects,
                  synthesizer: Annotated[Synthesizer, Depends(get_synthesizer)],
                  sous_titres: Annotated[bool, Form()] = False,
                  police: Annotated[str, Form()] = DEFAULT_FONT,
                  taille: Annotated[int, Form()] = DEFAULT_SIZE) -> RedirectResponse:
    if not project.transcript_path.exists():
        raise HTTPException(404, "Pas encore de transcription")
    check_subtitle_style(police, taille)
    projects.set_subtitle_style(project.id, police, taille)
    jobs.submit(project.id, "doublage",
                lambda progress: dub_project(project.video, project.folder, project.dubbed_video, synthesizer,
                                             progress, get_settings().acceleration_max,
                                             _synthesis_lock, _transcript_lock,
                                             sous_titres, get_settings().tts_threads,
                                             catalog.for_project(project.voice).label,
                                             get_settings().vitesse_min, burn_style(police, taille)))
    return RedirectResponse(f"/projets/{project.id}#doublage", status_code=303)


def check_subtitle_style(font: str, size: int) -> None:
    if font not in FONTS or size not in SIZES:
        raise HTTPException(400, "Police ou taille de sous-titres inconnue")


@app.get("/projets/{project_id}/sous-titres/apercu")
def subtitle_preview(user: User, project: CurrentProject, t: float = 0.0, police: str = DEFAULT_FONT,
                     taille: int = DEFAULT_SIZE) -> Response:
    """Image de la vidéo à l'instant `t`, la phrase affichée gravée dans la police et la taille choisies,
    exactement comme dans la vidéo doublée (même filtre ffmpeg), sans générer la vidéo."""
    check_subtitle_style(police, taille)
    if not project.transcript_path.exists():
        raise HTTPException(404, "Pas encore de transcription")
    with _transcript_lock:
        transcript = Transcript.load(project.transcript_path)
    shown = [s for s in transcript.segments if display_text(s.text)]
    # Phrase en cours, sinon la suivante (on est entre deux phrases), sinon la première.
    segment = (next((s for s in shown if s.start <= t < s.end), None)
               or next((s for s in shown if s.start >= t), None) or next(iter(shown), None))
    text = display_text(segment.text) if segment else "Exemple de sous-titre"
    at = max(0.0, min(t, transcript.duration - 0.5))  # au-delà de la fin : aucune image
    with tempfile.TemporaryDirectory() as tmp:
        srt = Path(tmp) / "apercu.srt"
        srt.write_text(f"1\n00:00:00,000 --> 99:00:00,000\n{text}\n", encoding="utf-8")
        try:
            image = media.subtitle_frame(project.video, at, srt, Path(tmp) / "apercu.jpg",
                                         burn_style(police, taille)).read_bytes()
        except media.MediaError as e:
            raise HTTPException(500, f"Aperçu impossible : {e}") from e
    return Response(image, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@app.post("/projets/{project_id}/voix")
def change_voice(user: User, project: CurrentProject, projects: Projects, jobs: Jobs, catalog: Catalog,
                 voix: Annotated[str, Form()]) -> RedirectResponse:
    voice = catalog.get(voix)
    if voice is None:
        raise HTTPException(400, "Voix inconnue")
    job = jobs.get(project.id)
    if job is not None and job.active:  # le doublage en cours mélangerait les deux voix
        raise HTTPException(409, "Impossible de changer de voix pendant un traitement en cours")
    # Voix enregistrée retirée du catalogue : les voix générées ne sont pas celles de la voix affichée
    # (voix par défaut), il faut les refaire même si c'est celle-ci qu'on choisit.
    current = catalog.get(project.voice) if project.voice else catalog.for_project(None)
    if voice != current:
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


class SegmentUpdate(BaseModel):
    texte: str | None = None
    voix_origine: bool | None = None
    vitesse: float | None = Field(None, ge=MANUAL_SPEED_MIN, le=MANUAL_SPEED_MAX)  # null : automatique


@app.put("/projets/{project_id}/phrases/{segment_id}")
def update_segment(user: User, project: CurrentProject, segment_id: int, update: SegmentUpdate) -> dict:
    if not project.transcript_path.exists():
        raise HTTPException(404, "Pas encore de transcription")
    with _transcript_lock:
        transcript = Transcript.load(project.transcript_path)
        segment = next((s for s in transcript.segments if s.id == segment_id), None)
        if segment is None:
            raise HTTPException(404, "Phrase introuvable")
        if update.texte is not None:
            transcript.set_text(segment_id, update.texte)
        if update.voix_origine is not None:
            segment.keep_original = update.voix_origine
        if "vitesse" in update.model_fields_set:
            segment.speed = update.vitesse
        transcript.save(project.transcript_path)
    return {"id": segment.id, "texte": segment.text, "etat": segment.status,
            "voix_origine": segment.keep_original, "vitesse": segment.speed,
            "notation_invalide": notation_error(segment.text),
            **voice_fit_fields(project, transcript, segment)}


def voice_fit_fields(project: Project, transcript: Transcript, segment: Segment) -> dict:
    calage = voice_fit(project, transcript, segment)
    if calage is None:
        return {}
    return {"calage": calage[0], "calage_texte": calage[1], "vitesse_auto": calage[2]}


@app.post("/projets/{project_id}/phrases/{segment_id}/voix")
def synthesize_one(user: User, project: CurrentProject, segment_id: int,
                   synthesizer: Annotated[Synthesizer, Depends(get_synthesizer)]) -> dict:
    """(Ré)génère la voix d'une seule phrase, avec son texte actuel. Attend la fin de la synthèse."""
    if not project.transcript_path.exists():
        raise HTTPException(404, "Pas encore de transcription")
    segment = next((s for s in Transcript.load(project.transcript_path).segments if s.id == segment_id), None)
    if segment is None:
        raise HTTPException(404, "Phrase introuvable")
    if not segment.text:
        raise HTTPException(400, "Phrase effacée : pas de voix à générer")
    with _synthesis_lock:
        try:
            synthesize_segment(segment, project.folder, synthesizer)
        except Exception as e:
            logger.exception("Synthèse de la phrase %s du projet %s", segment_id, project.id)
            raise HTTPException(500, f"Échec de la génération : {e or type(e).__name__}")
    with _transcript_lock:
        current = mark_synthesized(project.transcript_path, segment)
        transcript = Transcript.load(project.transcript_path)
    return {"id": segment_id, "etat": current.status if current else None,
            **voice_fit_fields(project, transcript, current or segment)}


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
