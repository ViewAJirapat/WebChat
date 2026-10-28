"""The Db wrapper (core/store.py) and the frozen schema (core/schema.sql)."""

import gc
import sqlite3
import warnings
from pathlib import Path

import pytest

from chatbook.core.store import Db, connect

# the frozen schema (DESIGN 3.3): table -> columns in order
SCHEMA = {
    "users": [
        "id",
        "username",
        "display_name",
        "bio",
        "password_hash",
        "created_at",
        "last_seen_at",
    ],
    "sessions": ["token_hash", "user_id", "created_at"],
    "friend_requests": ["id", "from_id", "to_id", "created_at"],
    "friendships": ["user_id", "friend_id", "created_at"],
    "conversations": [
        "id",
        "kind",
        "title",
        "direct_key",
        "created_by",
        "created_at",
        "last_message_id",
    ],
    "members": ["conversation_id", "user_id", "joined_at", "last_read_id"],
    "messages": ["id", "conversation_id", "sender_id", "body", "created_at"],
    "posts": ["id", "author_id", "body", "created_at"],
    "likes": ["post_id", "user_id", "created_at"],
    "comments": ["id", "post_id", "author_id", "body", "created_at"],
}
TABLES = set(SCHEMA)


def _db_with_posts(n: int = 5) -> Db:
    db = connect(":memory:", hash_iterations=1)
    for i in range(1, n + 1):
        db.run(
            "INSERT INTO posts (author_id, body, created_at) VALUES (?, ?, ?)", i % 2, f"p{i}", i
        )
    return db


def test_connect_creates_the_whole_schema() -> None:
    db = connect(":memory:")
    names = {r["name"] for r in db.all("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert names - {"sqlite_sequence"} == TABLES
    assert db.hash_iterations == 200_000
    assert connect(":memory:", hash_iterations=7).hash_iterations == 7


def test_schema_columns_indexes_and_no_foreign_keys() -> None:
    db = connect(":memory:")
    for table, columns in SCHEMA.items():
        assert [r["name"] for r in db.all(f"PRAGMA table_info({table})")] == columns, table
        assert db.all(f"PRAGMA foreign_key_list({table})") == [], table
    indexes = {
        r["name"]
        for r in db.all("SELECT name FROM sqlite_master WHERE type = 'index' AND sql IS NOT NULL")
    }
    assert indexes == {"members_user", "messages_conv", "posts_author"}


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO users (username, display_name, password_hash, created_at)"
        " VALUES ('ann', 'Ann', 'x', 0)",
        "INSERT INTO friend_requests (from_id, to_id, created_at) VALUES (1, 2, 0)",
        "INSERT INTO friendships (user_id, friend_id, created_at) VALUES (1, 2, 0)",
        "INSERT INTO conversations (kind, direct_key, created_by, created_at)"
        " VALUES ('direct', '1:2', 1, 0)",
        "INSERT INTO members (conversation_id, user_id, joined_at) VALUES (1, 1, 0)",
        "INSERT INTO likes (post_id, user_id, created_at) VALUES (1, 1, 0)",
        "INSERT INTO sessions (token_hash, user_id, created_at) VALUES ('h', 1, 0)",
    ],
)
def test_unique_keys_reject_a_second_row(sql: str) -> None:
    db = connect(":memory:")
    db.run(sql)
    with pytest.raises(sqlite3.IntegrityError):
        db.run(sql)


def test_defaults_and_the_kind_check() -> None:
    db = connect(":memory:")
    uid = db.run(
        "INSERT INTO users (username, display_name, password_hash, created_at)"
        " VALUES ('ann', 'Ann', 'x', 5)"
    )
    assert db.one("SELECT bio, last_seen_at FROM users WHERE id = ?", uid) == {
        "bio": "",
        "last_seen_at": 0,
    }
    cid = db.run("INSERT INTO conversations (kind, created_by, created_at) VALUES ('group', 1, 0)")
    row = db.one("SELECT title, direct_key, last_message_id FROM conversations WHERE id = ?", cid)
    assert row == {"title": "", "direct_key": None, "last_message_id": 0}
    db.run("INSERT INTO members (conversation_id, user_id, joined_at) VALUES (?, 1, 0)", cid)
    assert db.value("SELECT last_read_id FROM members WHERE conversation_id = ?", cid) == 0
    with pytest.raises(sqlite3.IntegrityError):
        db.run("INSERT INTO conversations (kind, created_by, created_at) VALUES ('chat', 1, 0)")


def test_a_collected_db_closes_without_a_resource_warning() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        db = connect(":memory:")
        db.one("SELECT 1")
        del db
        gc.collect()
    assert [w for w in caught if issubclass(w.category, ResourceWarning)] == []


def test_rows_are_plain_dicts() -> None:
    db = _db_with_posts(1)
    row = db.one("SELECT id, body FROM posts")
    assert type(row) is dict
    assert row == {"id": 1, "body": "p1"}
    assert all(type(r) is dict for r in db.all("SELECT * FROM posts"))


def test_params_as_varargs_tuple_or_list_are_equivalent() -> None:
    db = _db_with_posts()
    sql = "SELECT id FROM posts WHERE author_id = ? AND created_at > ? ORDER BY id"
    expected = [{"id": 3}, {"id": 5}]
    assert db.all(sql, 1, 1) == expected
    assert db.all(sql, (1, 1)) == expected
    assert db.all(sql, [1, 1]) == expected
    assert db.one("SELECT body FROM posts WHERE id = ?", (2,)) == {"body": "p2"}
    assert db.one("SELECT body FROM posts WHERE id = ?", [2]) == {"body": "p2"}
    assert db.value("SELECT body FROM posts WHERE id = ?", (4,)) == "p4"
    assert db.run("UPDATE posts SET body = ? WHERE id = ?", ("new", 1)) == 1
    rows, more = db.page("SELECT id FROM posts WHERE author_id = ? ORDER BY id", (1,), limit=2)
    assert (rows, more) == ([{"id": 1}, {"id": 3}], True)


def test_one_and_value_on_no_rows() -> None:
    db = _db_with_posts(0)
    assert db.one("SELECT * FROM posts") is None
    assert db.value("SELECT body FROM posts") is None
    assert db.all("SELECT * FROM posts") == []
    assert db.value("SELECT COUNT(*) FROM posts") == 0


def test_run_returns_lastrowid_for_insert_else_rowcount() -> None:
    db = _db_with_posts(3)
    assert (
        db.run("INSERT INTO posts (author_id, body, created_at) VALUES (?, ?, ?)", 9, "a", 0) == 4
    )
    assert db.run("\n   insert into posts (author_id, body, created_at) values (9, 'b', 0)") == 5
    assert db.run("UPDATE posts SET body = 'x' WHERE author_id = ?", 9) == 2
    assert db.run("UPDATE posts SET body = 'x' WHERE id = ?", 999) == 0
    assert db.run("DELETE FROM posts WHERE id <= ?", 3) == 3


def test_page_reports_has_more() -> None:
    db = _db_with_posts(5)
    sql = "SELECT id FROM posts ORDER BY id DESC"
    assert db.page(sql, limit=2) == ([{"id": 5}, {"id": 4}], True)
    assert db.page(sql, limit=4) == ([{"id": 5}, {"id": 4}, {"id": 3}, {"id": 2}], True)
    assert db.page(sql, limit=5) == ([{"id": i} for i in [5, 4, 3, 2, 1]], False)
    assert db.page(sql, limit=50) == ([{"id": i} for i in [5, 4, 3, 2, 1]], False)
    assert db.page("SELECT id FROM posts WHERE id < ? ORDER BY id", 3, limit=1) == (
        [{"id": 1}],
        True,
    )


def test_autoincrement_ids_start_at_one() -> None:
    db = connect(":memory:")
    sql = "INSERT INTO messages (conversation_id, sender_id, body, created_at) VALUES (1, 1, ?, 0)"
    first = db.run(sql, "a")
    db.run("DELETE FROM messages")
    second = db.run(sql, "b")
    assert (first, second) == (1, 2)  # AUTOINCREMENT never reuses an id


def test_file_database_autocommits_and_transactions_roll_back(tmp_path: Path) -> None:
    path = str(tmp_path / "t.db")
    writer = connect(path, hash_iterations=1)
    reader = connect(path, hash_iterations=1)  # the schema script is safe to run twice
    try:
        assert str(writer.value("PRAGMA journal_mode")).lower() == "wal"
        writer.run("INSERT INTO posts (author_id, body, created_at) VALUES (1, 'kept', 0)")
        assert reader.value("SELECT body FROM posts") == "kept"  # autocommit
        writer._begin()
        writer.run("INSERT INTO posts (author_id, body, created_at) VALUES (1, 'gone', 0)")
        writer._rollback()
        writer._begin()
        writer.run("INSERT INTO posts (author_id, body, created_at) VALUES (1, 'saved', 0)")
        writer._commit()
        bodies = [r["body"] for r in reader.all("SELECT body FROM posts ORDER BY id")]
        assert bodies == ["kept", "saved"]
    finally:
        writer.close()
        reader.close()
