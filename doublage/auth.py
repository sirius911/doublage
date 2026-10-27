"""Comptes utilisateurs et sessions de connexion, enregistrés dans SQLite."""

import hashlib
import hmac
import secrets
import sqlite3
import time
from pathlib import Path

SESSION_DURATION = 30 * 24 * 3600  # secondes

# Paramètres scrypt (bibliothèque standard, pas de dépendance supplémentaire).
_N, _R, _P = 2**14, 8, 1


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${digest.hex()}"


def check_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt, digest = stored.split("$")
    except ValueError:
        return False
    if algo != "scrypt":
        return False
    candidate = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt),
                               n=int(n), r=int(r), p=int(p))
    return hmac.compare_digest(candidate.hex(), digest)


class UserStore:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    name TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    user TEXT NOT NULL REFERENCES users(name) ON DELETE CASCADE,
                    expires REAL NOT NULL
                );
            """)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.db_path)
        db.execute("PRAGMA foreign_keys = ON")
        return db

    # Comptes

    def set_user(self, name: str, password: str) -> None:
        """Crée le compte, ou change son mot de passe s'il existe déjà."""
        if not name or not password:
            raise ValueError("L'identifiant et le mot de passe sont obligatoires.")
        with self._connect() as db:
            db.execute(
                "INSERT INTO users (name, password_hash) VALUES (?, ?) "
                "ON CONFLICT(name) DO UPDATE SET password_hash = excluded.password_hash",
                (name, hash_password(password)),
            )

    def delete_user(self, name: str) -> bool:
        with self._connect() as db:
            return db.execute("DELETE FROM users WHERE name = ?", (name,)).rowcount > 0

    def list_users(self) -> list[str]:
        with self._connect() as db:
            return [row[0] for row in db.execute("SELECT name FROM users ORDER BY name")]

    def authenticate(self, name: str, password: str) -> bool:
        with self._connect() as db:
            row = db.execute("SELECT password_hash FROM users WHERE name = ?", (name,)).fetchone()
        return row is not None and check_password(password, row[0])

    # Sessions

    def open_session(self, name: str) -> str:
        token = secrets.token_urlsafe(32)
        with self._connect() as db:
            db.execute("DELETE FROM sessions WHERE expires < ?", (time.time(),))
            db.execute("INSERT INTO sessions (token, user, expires) VALUES (?, ?, ?)",
                       (token, name, time.time() + SESSION_DURATION))
        return token

    def session_user(self, token: str) -> str | None:
        with self._connect() as db:
            row = db.execute("SELECT user FROM sessions WHERE token = ? AND expires >= ?",
                             (token, time.time())).fetchone()
        return row[0] if row else None

    def close_session(self, token: str) -> None:
        with self._connect() as db:
            db.execute("DELETE FROM sessions WHERE token = ?", (token,))
