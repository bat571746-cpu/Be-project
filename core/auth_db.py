"""
auth_db.py
==========
Minimal local user store for the Web Console.

Design intent: store as little as possible about each user. The table
holds ONLY:

    id            -- internal row id
    username      -- the login id the person chose (their only "identity")
    password_hash -- a salted hash (werkzeug's PBKDF2-based generator),
                     never the password itself
    created_at    -- account creation timestamp
    last_login    -- timestamp of the most recent successful login

No email, no real name, no profile data of any kind is collected or
stored. This is a single-file SQLite database (web/data/users.db),
created automatically on first run.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime, timezone

from werkzeug.security import generate_password_hash, check_password_hash

DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
DB_PATH = os.path.join(DB_DIR, "users.db")

_lock = threading.Lock()  # SQLite + simple Flask dev server: keep writes serialized


class UsernameTakenError(Exception):
    """Raised when registration is attempted with an existing username."""


class InvalidCredentialsError(Exception):
    """Raised when login fails (unknown username or wrong password)."""


def _connect() -> sqlite3.Connection:
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Creates the users table if it doesn't already exist. Safe to call every startup."""
    with _lock, _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at    TEXT NOT NULL,
                last_login    TEXT
            )
            """
        )
        conn.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------
# Registration / login
# ---------------------------------------------------------------------
def create_user(username: str, password: str) -> int:
    """
    Registers a new user. Only the login id + a salted password hash are
    written to disk. Returns the new user's row id.
    """
    username = username.strip()
    if not username or not password:
        raise ValueError("Login id and password are required.")

    password_hash = generate_password_hash(password)

    with _lock, _connect() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if existing:
            raise UsernameTakenError(f"Login id '{username}' is already taken.")

        cur = conn.execute(
            "INSERT INTO users (username, password_hash, created_at, last_login) "
            "VALUES (?, ?, ?, NULL)",
            (username, password_hash, _now()),
        )
        conn.commit()
        return cur.lastrowid


def verify_user(username: str, password: str) -> dict:
    """
    Checks a login id + password against the stored hash. On success,
    updates last_login and returns a small dict describing the account
    (never the hash). Raises InvalidCredentialsError on any failure.
    """
    username = (username or "").strip()

    with _lock, _connect() as conn:
        row = conn.execute(
            "SELECT id, username, password_hash, created_at, last_login "
            "FROM users WHERE username = ?",
            (username,),
        ).fetchone()

        if not row or not check_password_hash(row["password_hash"], password or ""):
            # Deliberately identical error for "no such user" and "wrong
            # password" -- don't leak which one it was.
            raise InvalidCredentialsError("Incorrect login id or password.")

        conn.execute(
            "UPDATE users SET last_login = ? WHERE id = ?", (_now(), row["id"])
        )
        conn.commit()

        return {
            "id": row["id"],
            "username": row["username"],
            "created_at": row["created_at"],
            "last_login": row["last_login"],
        }


def get_user(username: str) -> dict | None:
    with _lock, _connect() as conn:
        row = conn.execute(
            "SELECT id, username, created_at, last_login FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        return dict(row) if row else None


def change_password(username: str, old_password: str, new_password: str) -> None:
    """Verifies the old password, then overwrites the stored hash with the new one."""
    if not new_password:
        raise ValueError("New password cannot be empty.")

    # reuse verify_user's check (also refreshes last_login, which is fine)
    verify_user(username, old_password)

    new_hash = generate_password_hash(new_password)
    with _lock, _connect() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE username = ?",
            (new_hash, username),
        )
        conn.commit()


def delete_user(username: str) -> None:
    with _lock, _connect() as conn:
        conn.execute("DELETE FROM users WHERE username = ?", (username,))
        conn.commit()
