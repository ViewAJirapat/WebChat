"""Users, passwords and sessions (core-owned tables users and sessions)."""

import functools
import hashlib
import hmac
import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from chatbook.core.http import HTTPError
from chatbook.core.store import Db, Row

_SCHEME = "pbkdf2_sha256"


@dataclass(frozen=True)
class User:
    id: int
    username: str
    display_name: str


def user_json(u: User | Mapping[str, Any]) -> dict[str, Any]:
    """U = {"id", "username", "display_name"} from a User or a users row."""
    if isinstance(u, User):
        return {"id": u.id, "username": u.username, "display_name": u.display_name}
    return {"id": u["id"], "username": u["username"], "display_name": u["display_name"]}


def get_user(db: Db, user_id: int) -> Row | None:
    """The full users row, or None."""
    return db.one("SELECT * FROM users WHERE id = ?", user_id)


def require_user(db: Db, user_id: int) -> Row:
    """The full users row; HTTPError(404) if there is none."""
    row = get_user(db, user_id)
    if row is None:
        raise HTTPError(404, "user not found")
    return row


def hash_password(password: str, iterations: int) -> str:
    """'pbkdf2_sha256$<iterations>$<salt hex>$<hash hex>' with a random 16-byte salt."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{_SCHEME}${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """True if `password` matches `stored` (iterations are read from `stored`)."""
    parts = stored.split("$")
    if len(parts) != 4 or parts[0] != _SCHEME:
        return False
    _, raw_iterations, salt_hex, digest_hex = parts
    if not (raw_iterations.isascii() and raw_iterations.isdigit()) or int(raw_iterations) < 1:
        return False
    try:
        salt, expected = bytes.fromhex(salt_hex), bytes.fromhex(digest_hex)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(raw_iterations))
    return hmac.compare_digest(digest, expected)


@functools.cache
def _dummy_hash(iterations: int) -> str:
    return hash_password("not-a-real-password", iterations)


def create_user(db: Db, username: str, password: str, display_name: str, now: int) -> User:
    """Insert a user (username stored exactly as given); HTTPError(409) if it is taken."""
    if db.one("SELECT id FROM users WHERE username = ?", username) is not None:
        raise HTTPError(409, "username taken")
    user_id = db.run(
        "INSERT INTO users (username, display_name, password_hash, created_at) VALUES (?, ?, ?, ?)",
        username,
        display_name,
        hash_password(password, db.hash_iterations),
        now,
    )
    return User(user_id, username, display_name)


def check_password(db: Db, username: str, password: str) -> User | None:
    """The user if the username (exact match) and password are right, else None."""
    row = db.one("SELECT * FROM users WHERE username = ?", username)
    if row is None:
        verify_password(password, _dummy_hash(db.hash_iterations))  # same cost as a real check
        return None
    if not verify_password(password, str(row["password_hash"])):
        return None
    return User(int(row["id"]), str(row["username"]), str(row["display_name"]))


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_session(db: Db, user_id: int, now: int) -> str:
    """Create a session and return its bearer token (only its hash is stored)."""
    token = secrets.token_urlsafe(32)
    db.run(
        "INSERT INTO sessions (token_hash, user_id, created_at) VALUES (?, ?, ?)",
        _token_hash(token),
        user_id,
        now,
    )
    return token


def end_session(db: Db, token: str | None) -> None:
    """Delete the session of `token` (nothing happens for None or an unknown token)."""
    if token:
        db.run("DELETE FROM sessions WHERE token_hash = ?", _token_hash(token))


def user_for_token(db: Db, token: str | None) -> User | None:
    """The user of a session token, or None."""
    if not token:
        return None
    row = db.one(
        "SELECT u.id, u.username, u.display_name FROM sessions s JOIN users u ON u.id = s.user_id"
        " WHERE s.token_hash = ?",
        _token_hash(token),
    )
    if row is None:
        return None
    return User(int(row["id"]), str(row["username"]), str(row["display_name"]))


def touch(db: Db, user_id: int, now: int) -> None:
    """last_seen_at = now (the App calls it on every logged-in request)."""
    db.run("UPDATE users SET last_seen_at = ? WHERE id = ?", now, user_id)
