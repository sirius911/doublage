import io

import pytest

from doublage.projects import ProjectError, ProjectStore


def test_creation_et_liste(tmp_path):
    store = ProjectStore(tmp_path / "doublage.db", tmp_path)
    p1 = store.create("", "Mon tuto.MP4", io.BytesIO(b"abc"), "alice")
    p2 = store.create("Second", "b.mkv", io.BytesIO(b"def"), "bob")
    assert p1.name == "Mon tuto"  # nom par défaut : celui du fichier
    assert p1.video == tmp_path / "projets" / str(p1.id) / "video.mp4"
    assert p1.video.read_bytes() == b"abc"
    assert [p.id for p in store.list()] == [p2.id, p1.id]  # le plus récent d'abord
    assert store.get(p1.id).owner == "alice"
    assert store.get(12345) is None


def test_voix_du_projet_et_base_ancienne(tmp_path):
    import sqlite3

    db_path = tmp_path / "doublage.db"
    with sqlite3.connect(db_path) as db:  # base créée avant le choix de la voix
        db.execute("CREATE TABLE projects (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, "
                   "video_name TEXT NOT NULL, owner TEXT NOT NULL, created REAL NOT NULL)")
        db.execute("INSERT INTO projects (name, video_name, owner, created) VALUES ('a', 'a.mp4', 'alice', 0)")
    store = ProjectStore(db_path, tmp_path)
    assert store.get(1).voice is None
    store.set_voice(1, "alba")
    assert store.get(1).voice == "alba"


def test_format_refuse(tmp_path):
    store = ProjectStore(tmp_path / "doublage.db", tmp_path)
    with pytest.raises(ProjectError):
        store.create("x", "notes.txt", io.BytesIO(b""), "alice")
    assert store.list() == []


def test_echec_de_copie_annule_le_projet(tmp_path):
    class Casse(io.RawIOBase):
        def read(self, n=-1):
            raise OSError("disque plein")

    store = ProjectStore(tmp_path / "doublage.db", tmp_path)
    with pytest.raises(OSError):
        store.create("x", "a.mp4", Casse(), "alice")
    assert store.list() == [] and not any((tmp_path / "projets").iterdir())


def test_style_des_sous_titres(tmp_path):
    import io
    store = ProjectStore(tmp_path / "base.db", tmp_path)
    projet = store.create("Démo", "demo.mp4", io.BytesIO(b"x"), "alice")
    assert projet.subtitle_style == ("DejaVu Sans", 16)
    store.set_subtitle_style(projet.id, "Liberation Sans", 20)
    assert store.get(projet.id).subtitle_style == ("Liberation Sans", 20)
