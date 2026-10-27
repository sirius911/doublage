import time

from doublage.auth import UserStore, check_password, hash_password
from doublage.cli import main


def test_mot_de_passe_chiffre():
    stored = hash_password("secret")
    assert "secret" not in stored
    assert check_password("secret", stored)
    assert not check_password("autre", stored)
    assert stored != hash_password("secret")  # sel aléatoire


def test_comptes(tmp_path):
    store = UserStore(tmp_path / "doublage.db")
    store.set_user("bob", "un")
    store.set_user("alice", "deux")
    assert store.list_users() == ["alice", "bob"]
    assert store.authenticate("bob", "un")
    assert not store.authenticate("bob", "deux")
    assert not store.authenticate("inconnu", "un")

    store.set_user("bob", "trois")  # changement de mot de passe
    assert store.authenticate("bob", "trois") and not store.authenticate("bob", "un")

    assert store.delete_user("bob") and not store.delete_user("bob")
    assert store.list_users() == ["alice"]


def test_sessions(tmp_path, monkeypatch):
    store = UserStore(tmp_path / "doublage.db")
    store.set_user("alice", "secret")
    token = store.open_session("alice")
    assert store.session_user(token) == "alice"
    assert store.session_user("inconnu") is None

    store.close_session(token)
    assert store.session_user(token) is None

    token = store.open_session("alice")
    monkeypatch.setattr(time, "time", lambda: 1e12)  # bien après l'expiration
    assert store.session_user(token) is None


def test_commande_utilisateur(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DOUBLAGE_DATA_DIR", str(tmp_path))
    from doublage.config import get_settings
    get_settings.cache_clear()
    monkeypatch.setattr("getpass.getpass", lambda prompt="": "secret")
    try:
        main(["utilisateur", "ajouter", "alice"])
        main(["utilisateur", "liste"])
        assert "alice" in capsys.readouterr().out
        assert UserStore(tmp_path / "doublage.db").authenticate("alice", "secret")
        main(["utilisateur", "supprimer", "alice"])
        assert UserStore(tmp_path / "doublage.db").list_users() == []
    finally:
        get_settings.cache_clear()
