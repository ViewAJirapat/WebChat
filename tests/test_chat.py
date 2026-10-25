"""Conversations, members, messages and their JSON shapes (core/chat.py)."""

from typing import Any

import pytest

from chatbook.core.chat import (
    add_member,
    conversation_json,
    create_conversation,
    find_direct,
    mark_read,
    member_ids,
    message_json,
    post_message,
    remove_member,
    require_member,
    unread_count,
)
from chatbook.core.http import HTTPError
from chatbook.core.store import Db, connect
from chatbook.core.users import create_user

NOW = 1_700_000_000_000
NAMES = [("ann", "Ann Lee"), ("ben", "Ben Bo"), ("cat", "Cat Cy"), ("dan", "Dan Du")]


def make_db() -> tuple[Db, list[int], list[dict[str, Any]]]:
    db = connect(":memory:", hash_iterations=1)
    ids = [create_user(db, u, "pw", name, NOW).id for u, name in NAMES]
    users = [
        {"id": i, "username": u, "display_name": n} for i, (u, n) in zip(ids, NAMES, strict=True)
    ]
    return db, ids, users


def members(db: Db, cid: int) -> list[dict[str, Any]]:
    return db.all(
        "SELECT user_id, joined_at, last_read_id FROM members WHERE conversation_id = ?"
        " ORDER BY user_id",
        cid,
    )


def test_create_direct() -> None:
    db, (a, b, _, _), _ = make_db()
    cid = create_conversation(db, "direct", "ignored", b, [a], NOW)
    row = db.one("SELECT * FROM conversations WHERE id = ?", cid)
    assert row == {
        "id": cid,
        "kind": "direct",
        "title": "",
        "direct_key": f"{a}:{b}",
        "created_by": b,
        "created_at": NOW,
        "last_message_id": 0,
    }
    assert members(db, cid) == [
        {"user_id": a, "joined_at": NOW, "last_read_id": 0},
        {"user_id": b, "joined_at": NOW, "last_read_id": 0},
    ]


def test_direct_key_orders_ids_numerically() -> None:
    db, (a, _, _, _), _ = make_db()
    db.run(
        "INSERT INTO users (id, username, display_name, password_hash, created_at)"
        " VALUES (10, 'ten', 'Ten', 'x', 0)"
    )
    cid = create_conversation(db, "direct", "", 10, [a], NOW)
    assert db.value("SELECT direct_key FROM conversations WHERE id = ?", cid) == f"{a}:10"


def test_create_group_dedupes_members() -> None:
    db, (a, b, _, d), _ = make_db()
    cid = create_conversation(db, "group", "Trip", a, [d, b, a, b], NOW)
    row = db.one("SELECT kind, title, direct_key, created_by FROM conversations WHERE id = ?", cid)
    assert row == {"kind": "group", "title": "Trip", "direct_key": None, "created_by": a}
    assert member_ids(db, cid) == [a, b, d]
    assert [m["last_read_id"] for m in members(db, cid)] == [0, 0, 0]


@pytest.mark.parametrize(
    ("kind", "others"), [("direct", [1, 2]), ("direct", [3]), ("direct", []), ("chat", [1])]
)
def test_create_rejects_bad_kind_or_member_count(kind: str, others: list[int]) -> None:
    db, _, _ = make_db()
    with pytest.raises(ValueError):
        create_conversation(db, kind, "", 3, others, NOW)  # creator 3 is not repeated


def test_find_direct() -> None:
    db, (a, b, c, _), _ = make_db()
    cid = create_conversation(db, "direct", "", a, [b], NOW)
    create_conversation(db, "group", "Pair", a, [c], NOW)
    assert find_direct(db, a, b) == cid
    assert find_direct(db, b, a) == cid
    assert find_direct(db, a, c) is None


def test_require_member() -> None:
    db, (a, b, c, _), _ = make_db()
    cid = create_conversation(db, "group", "G", a, [b], NOW)
    row = require_member(db, cid, b)
    assert row["id"] == cid and row["kind"] == "group" and row["title"] == "G"
    for conv, user in [(cid, c), (999, a)]:
        with pytest.raises(HTTPError) as info:
            require_member(db, conv, user)
        assert info.value.status == 404


def test_post_message_returns_m_and_updates_pointers() -> None:
    db, (a, b, _, _), users = make_db()
    cid = create_conversation(db, "direct", "", a, [b], NOW)
    m = post_message(db, cid, a, "hi there", NOW + 5)
    assert m == {
        "id": 1,
        "conversation_id": cid,
        "sender": users[0],
        "body": "hi there",
        "created_at": NOW + 5,
    }
    assert db.value("SELECT last_message_id FROM conversations WHERE id = ?", cid) == 1
    assert [r["last_read_id"] for r in members(db, cid)] == [1, 0]
    row = db.one("SELECT * FROM messages WHERE id = ?", m["id"])
    assert row is not None
    assert message_json(db, row) == m
    assert unread_count(db, cid, b) == 1
    assert unread_count(db, cid, a) == 0


def test_unread_count_skips_own_messages_and_non_members() -> None:
    db, (a, b, c, _), _ = make_db()
    cid = create_conversation(db, "group", "G", a, [b], NOW)
    post_message(db, cid, a, "1", NOW)
    post_message(db, cid, b, "2", NOW)
    post_message(db, cid, a, "3", NOW)
    db.run("UPDATE members SET last_read_id = 0 WHERE user_id = ?", a)
    assert unread_count(db, cid, a) == 1  # only b's message counts
    assert unread_count(db, cid, b) == 1  # a's third message
    assert unread_count(db, cid, c) == 0


def test_mark_read() -> None:
    db, (a, b, _, _), _ = make_db()
    cid = create_conversation(db, "direct", "", a, [b], NOW)
    assert mark_read(db, cid, b) == 0
    post_message(db, cid, a, "x", NOW)
    last = post_message(db, cid, a, "y", NOW)["id"]
    assert unread_count(db, cid, b) == 2
    assert mark_read(db, cid, b) == last
    assert unread_count(db, cid, b) == 0
    assert mark_read(db, cid, b) == last


def test_add_member_sees_no_old_messages_and_remove_member() -> None:
    db, (a, b, _, d), _ = make_db()
    cid = create_conversation(db, "group", "G", a, [b], NOW)
    post_message(db, cid, b, "old", NOW)
    last = post_message(db, cid, b, "older", NOW)["id"]
    add_member(db, cid, d, NOW + 9)
    add_member(db, cid, d, NOW + 10)  # INSERT OR IGNORE
    assert member_ids(db, cid) == [a, b, d]
    assert members(db, cid)[2] == {"user_id": d, "joined_at": NOW + 9, "last_read_id": last}
    assert unread_count(db, cid, d) == 0
    post_message(db, cid, b, "new", NOW)
    assert unread_count(db, cid, d) == 1
    remove_member(db, cid, d)
    assert member_ids(db, cid) == [a, b]
    assert unread_count(db, cid, d) == 0


def test_conversation_json_direct_per_viewer() -> None:
    db, (a, b, _, _), users = make_db()
    cid = create_conversation(db, "direct", "", b, [a], NOW)
    expected: dict[str, Any] = {
        "id": cid,
        "kind": "direct",
        "title": "Ben Bo",
        "members": [users[0], users[1]],
        "last_message": None,
        "unread": 0,
        "updated_at": NOW,
    }
    assert conversation_json(db, cid, a) == expected
    assert conversation_json(db, cid, b) == expected | {"title": "Ann Lee"}
    m = post_message(db, cid, b, "yo", NOW + 30)
    assert conversation_json(db, cid, a) == expected | {
        "last_message": m,
        "unread": 1,
        "updated_at": NOW + 30,
    }


def test_conversation_json_after_members_leave() -> None:
    db, (a, b, c, _), users = make_db()
    direct = create_conversation(db, "direct", "", a, [b], NOW)
    remove_member(db, direct, b)
    got = conversation_json(db, direct, a)
    assert (got["title"], got["members"]) == ("Unknown", [users[0]])
    group = create_conversation(db, "group", "G", a, [b, c], NOW)
    remove_member(db, group, b)
    assert conversation_json(db, group, a)["members"] == [users[0], users[2]]


def test_conversation_json_group() -> None:
    db, (a, b, c, _), users = make_db()
    cid = create_conversation(db, "group", "Ski trip", c, [b, a], NOW)
    post_message(db, cid, a, "first", NOW + 1)
    last = post_message(db, cid, b, "second", NOW + 2)
    got = conversation_json(db, cid, c)
    assert got == {
        "id": cid,
        "kind": "group",
        "title": "Ski trip",
        "members": users[:3],
        "last_message": last,
        "unread": 2,
        "updated_at": NOW + 2,
    }
