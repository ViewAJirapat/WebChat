"""Friendship rules and post visibility (core/social.py)."""

import pytest

from chatbook.core.http import HTTPError
from chatbook.core.social import (
    are_friends,
    befriend,
    can_see_post,
    friend_ids,
    relationship,
    unfriend,
    visible_post,
)
from chatbook.core.store import Db, connect
from chatbook.core.users import create_user

NOW = 1_700_000_000_000


def make_db() -> tuple[Db, list[int]]:
    db = connect(":memory:", hash_iterations=1)
    ids = [
        create_user(db, name, "pw", name.title(), NOW).id for name in ["ann", "ben", "cat", "dan"]
    ]
    return db, ids


def request_row(db: Db, a: int, b: int) -> int:
    return db.run(
        "INSERT INTO friend_requests (from_id, to_id, created_at) VALUES (?, ?, ?)", a, b, NOW
    )


def test_befriend_both_directions_and_clears_requests() -> None:
    db, (a, b, c, d) = make_db()
    request_row(db, a, b)
    request_row(db, b, a)
    request_row(db, c, a)
    befriend(db, a, b, NOW + 1)
    assert are_friends(db, a, b) and are_friends(db, b, a)
    rows = db.all("SELECT user_id, friend_id, created_at FROM friendships ORDER BY user_id")
    assert rows == [
        {"user_id": a, "friend_id": b, "created_at": NOW + 1},
        {"user_id": b, "friend_id": a, "created_at": NOW + 1},
    ]
    left = db.all("SELECT from_id, to_id FROM friend_requests")
    assert left == [{"from_id": c, "to_id": a}]  # only requests between a and b are deleted
    befriend(db, b, a, NOW + 2)  # idempotent
    assert db.value("SELECT COUNT(*) FROM friendships") == 2
    assert not are_friends(db, a, c)
    assert not are_friends(db, a, d)


def test_unfriend_removes_both_directions_only_for_the_pair() -> None:
    db, (a, b, c, _) = make_db()
    befriend(db, a, b, NOW)
    befriend(db, a, c, NOW)
    unfriend(db, b, a)
    assert not are_friends(db, a, b) and not are_friends(db, b, a)
    assert are_friends(db, a, c) and are_friends(db, c, a)
    unfriend(db, b, a)  # no error when not friends


def test_relationship_values() -> None:
    db, (a, b, c, d) = make_db()
    befriend(db, a, b, NOW)
    request_row(db, a, c)
    request_row(db, d, a)
    assert relationship(db, a, a) == "self"
    assert relationship(db, a, b) == "friends"
    assert relationship(db, a, c) == "request_sent"
    assert relationship(db, c, a) == "request_received"
    assert relationship(db, a, d) == "request_received"
    assert relationship(db, d, a) == "request_sent"
    assert relationship(db, b, c) == "none"


def test_friend_ids_ascending() -> None:
    db, (a, b, c, d) = make_db()
    befriend(db, a, d, NOW)
    befriend(db, b, a, NOW)
    assert friend_ids(db, a) == [b, d]
    assert friend_ids(db, d) == [a]
    assert friend_ids(db, c) == []


def test_visible_post() -> None:
    db, (a, b, c, _) = make_db()
    befriend(db, a, b, NOW)
    pid = db.run("INSERT INTO posts (author_id, body, created_at) VALUES (?, ?, ?)", a, "hi", NOW)
    expected = {"id": pid, "author_id": a, "body": "hi", "created_at": NOW}
    assert visible_post(db, pid, a) == expected
    assert visible_post(db, pid, b) == expected
    for post_id, viewer in [(pid, c), (999, a)]:
        with pytest.raises(HTTPError) as info:
            visible_post(db, post_id, viewer)
        assert info.value.status == 404


def test_can_see_post() -> None:
    db, (a, b, c, d) = make_db()
    befriend(db, a, b, NOW)
    befriend(db, b, c, NOW)
    befriend(db, a, d, NOW)
    pid = db.run("INSERT INTO posts (author_id, body, created_at) VALUES (?, ?, ?)", a, "hi", NOW)
    unfriend(db, a, d)
    cases = [(pid, a, True), (pid, b, True), (pid, c, False), (pid, d, False), (999, a, False)]
    for post_id, viewer, seen in cases:
        assert can_see_post(db, post_id, viewer) is seen
        if seen:
            assert visible_post(db, post_id, viewer)["id"] == post_id
        else:
            with pytest.raises(HTTPError) as info:
                visible_post(db, post_id, viewer)
            assert (info.value.status, info.value.message) == (404, "post not found")
    befriend(db, a, d, NOW)
    assert can_see_post(db, pid, d) is True
