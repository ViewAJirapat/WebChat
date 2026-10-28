"""Users, passwords and sessions (core/users.py)."""

import hashlib

import pytest

from chatbook.core.http import HTTPError
from chatbook.core.store import Db, connect
from chatbook.core.users import (
    User,
    check_password,
    create_user,
    end_session,
    get_user,
    hash_password,
    new_session,
    require_user,
    touch,
    user_for_token,
    user_json,
    verify_password,
)

NOW = 1_700_000_000_000


def fresh() -> Db:
    return connect(":memory:", hash_iterations=1)


def test_create_user_returns_user_and_stores_row() -> None:
    db = fresh()
    ann = create_user(db, "Ann_1", "secret-pw", "Ann Lee", NOW)
    assert ann == User(id=1, username="Ann_1", display_name="Ann Lee")  # stored as given
    row = get_user(db, ann.id)
    assert row is not None
    assert row["username"] == "Ann_1"
    assert row["display_name"] == "Ann Lee"
    assert row["bio"] == ""
    assert row["created_at"] == NOW
    assert row["last_seen_at"] == 0
    assert row["password_hash"].startswith("pbkdf2_sha256$1$")
    assert "secret-pw" not in row["password_hash"]
    assert create_user(db, "bob", "pw", "Bob", NOW).id == 2


def test_create_user_taken_is_409() -> None:
    db = fresh()
    create_user(db, "ann", "pw-one", "Ann", NOW)
    with pytest.raises(HTTPError) as info:
        create_user(db, "ann", "pw-two", "Other Ann", NOW)
    assert info.value.status == 409
    assert db.value("SELECT COUNT(*) FROM users") == 1


def test_user_json_from_user_or_row() -> None:
    db = fresh()
    ann = create_user(db, "ann", "pw", "Ann Lee", NOW)
    expected = {"id": 1, "username": "ann", "display_name": "Ann Lee"}
    assert user_json(ann) == expected
    row = get_user(db, ann.id)
    assert row is not None
    assert user_json(row) == expected  # extra columns are dropped


def test_get_and_require_user() -> None:
    db = fresh()
    ann = create_user(db, "ann", "pw", "Ann", NOW)
    assert get_user(db, 99) is None
    assert require_user(db, ann.id) == get_user(db, ann.id)
    with pytest.raises(HTTPError) as info:
        require_user(db, 99)
    assert info.value.status == 404


def test_check_password() -> None:
    db = fresh()
    ann = create_user(db, "ann", "right-pw", "Ann", NOW)
    assert check_password(db, "ann", "right-pw") == ann
    assert check_password(db, "ann", "wrong-pw") is None
    assert check_password(db, "ann", "right-pw ") is None
    assert check_password(db, "Ann", "right-pw") is None  # exact username match
    assert check_password(db, "ghost", "right-pw") is None


def test_sessions() -> None:
    db = fresh()
    ann = create_user(db, "ann", "pw", "Ann", NOW)
    token = new_session(db, ann.id, NOW)
    other = new_session(db, ann.id, NOW)
    assert token != other
    assert len(token) >= 40
    assert user_for_token(db, token) == ann
    assert user_for_token(db, "bogus") is None
    assert user_for_token(db, None) is None
    assert user_for_token(db, "") is None
    stored = {r["token_hash"] for r in db.all("SELECT token_hash FROM sessions")}
    assert hashlib.sha256(token.encode()).hexdigest() in stored  # only the hash is stored
    assert token not in stored
    row = db.one(
        "SELECT user_id, created_at FROM sessions WHERE token_hash = ?",
        hashlib.sha256(token.encode()).hexdigest(),
    )
    assert row == {"user_id": ann.id, "created_at": NOW}
    end_session(db, token)
    assert user_for_token(db, token) is None
    assert user_for_token(db, other) == ann
    end_session(db, None)
    end_session(db, "bogus")


def test_touch_sets_last_seen() -> None:
    db = fresh()
    ann = create_user(db, "ann", "pw", "Ann", NOW)
    touch(db, ann.id, NOW + 5)
    row = get_user(db, ann.id)
    assert row is not None and row["last_seen_at"] == NOW + 5


def test_hash_format_and_verify() -> None:
    stored = hash_password("p\u00e4ss word", 3)
    algo, iterations, salt, digest = stored.split("$")
    assert (algo, iterations) == ("pbkdf2_sha256", "3")
    assert len(salt) == 32 and bytes.fromhex(salt)
    expected = hashlib.pbkdf2_hmac("sha256", "p\u00e4ss word".encode(), bytes.fromhex(salt), 3)
    assert digest == expected.hex()
    assert verify_password("p\u00e4ss word", stored)
    assert not verify_password("pass word", stored)
    assert hash_password("same", 1) != hash_password("same", 1)  # random salt
    assert verify_password("x", hash_password("x", 2))


@pytest.mark.parametrize(
    "stored",
    ["", "x", "pbkdf2_sha256$1$zz$zz", "md5$1$00$00", "pbkdf2_sha256$x$00$00", "a$b$c"],
)
def test_verify_password_rejects_malformed_hashes(stored: str) -> None:
    assert verify_password("x", stored) is False
