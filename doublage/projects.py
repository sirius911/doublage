"""Projets de doublage : liste dans SQLite, fichiers dans un dossier par projet."""

import shutil
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".m4v", ".webm", ".avi"}


class ProjectError(ValueError):
    pass


@dataclass
class Project:
    id: int
    name: str
    video_name: str  # nom du fichier déposé par l'utilisateur
    owner: str
    created: float
    folder: Path
    voice: str | None = None  # identifiant dans le catalogue ; None = voix par défaut

    @property
    def video(self) -> Path:
        return self.folder / f"video{Path(self.video_name).suffix.lower()}"

    @property
    def transcript_path(self) -> Path:
        return self.folder / "segments.json"

    @property
    def dubbed_video(self) -> Path:
        return self.folder / "video_doublee.mp4"


class ProjectStore:
    def __init__(self, db_path: Path, data_dir: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self.root = data_dir / "projets"
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    video_name TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    created REAL NOT NULL
                )
            """)
            columns = {row[1] for row in db.execute("PRAGMA table_info(projects)")}
            if "voice" not in columns:  # base créée avant le choix de la voix
                db.execute("ALTER TABLE projects ADD COLUMN voice TEXT")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _project(self, row: tuple) -> Project:
        id_, name, video_name, owner, created, voice = row
        return Project(id_, name, video_name, owner, created, self.root / str(id_), voice)

    def set_voice(self, project_id: int, voice: str) -> None:
        with self._connect() as db:
            db.execute("UPDATE projects SET voice = ? WHERE id = ?", (voice, project_id))

    def create(self, name: str, video_name: str, video: BinaryIO, owner: str) -> Project:
        """Crée le projet et y copie la vidéo (lue par morceaux : les fichiers sont gros)."""
        name = name.strip() or Path(video_name).stem
        if Path(video_name).suffix.lower() not in VIDEO_EXTENSIONS:
            raise ProjectError("Format non pris en charge (formats acceptés : "
                               + ", ".join(sorted(VIDEO_EXTENSIONS)) + ").")
        with self._connect() as db:
            cur = db.execute(
                "INSERT INTO projects (name, video_name, owner, created) VALUES (?, ?, ?, ?)",
                (name, Path(video_name).name, owner, time.time()),
            )
            project = self.get(cur.lastrowid, db)
        project.folder.mkdir(parents=True, exist_ok=True)
        try:
            with project.video.open("wb") as out:
                shutil.copyfileobj(video, out, length=1024 * 1024)
        except BaseException:
            self.delete(project.id)
            raise
        return project

    def get(self, project_id: int, db: sqlite3.Connection | None = None) -> Project | None:
        query = "SELECT id, name, video_name, owner, created, voice FROM projects WHERE id = ?"
        if db is None:
            with self._connect() as db:
                row = db.execute(query, (project_id,)).fetchone()
        else:
            row = db.execute(query, (project_id,)).fetchone()
        return self._project(row) if row else None

    def list(self) -> list[Project]:
        with self._connect() as db:
            rows = db.execute("SELECT id, name, video_name, owner, created, voice FROM projects "
                              "ORDER BY created DESC, id DESC").fetchall()
        return [self._project(r) for r in rows]

    def delete(self, project_id: int) -> None:
        with self._connect() as db:
            db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        shutil.rmtree(self.root / str(project_id), ignore_errors=True)
