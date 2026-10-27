"""Application web (FastAPI)."""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from . import __version__

app = FastAPI(title="Doublage", version=__version__)


@app.get("/sante")
def health() -> dict:
    return {"statut": "ok", "version": __version__}


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return """<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><title>Doublage</title></head>
<body style="font-family: system-ui, sans-serif; max-width: 40rem; margin: 3rem auto; padding: 0 1rem">
<h1>Doublage</h1>
<p>Doublage de tutoriels vidéo par voix de synthèse. L'interface d'édition arrive bientôt.</p>
</body></html>"""
