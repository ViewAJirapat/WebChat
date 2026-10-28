"""Friendship rules shared by every feature (core-owned table friendships)."""

from chatbook.core.http import HTTPError
from chatbook.core.store import Db, Row


def are_friends(db: Db, a: int, b: int) -> bool:
    """True if a and b are friends."""
    row = db.one("SELECT 1 FROM friendships WHERE user_id = ? AND friend_id = ?", a, b)
    return row is not None


def befriend(db: Db, a: int, b: int, now: int) -> None:
    """Make a and b friends (both directions) and delete pending requests between them."""
    sql = "INSERT OR IGNORE INTO friendships (user_id, friend_id, created_at) VALUES (?, ?, ?)"
    db.run(sql, a, b, now)
    db.run(sql, b, a, now)
    db.run(
        "DELETE FROM friend_requests"
        " WHERE (from_id = ? AND to_id = ?) OR (from_id = ? AND to_id = ?)",
        a,
        b,
        b,
        a,
    )


def unfriend(db: Db, a: int, b: int) -> None:
    """End the friendship of a and b (both directions)."""
    db.run(
        "DELETE FROM friendships"
        " WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)",
        a,
        b,
        b,
        a,
    )


def relationship(db: Db, me: int, other: int) -> str:
    """'self', 'friends', 'request_sent', 'request_received' or 'none'."""
    if me == other:
        return "self"
    if are_friends(db, me, other):
        return "friends"
    pending = "SELECT 1 FROM friend_requests WHERE from_id = ? AND to_id = ?"
    if db.one(pending, me, other) is not None:
        return "request_sent"
    if db.one(pending, other, me) is not None:
        return "request_received"
    return "none"


def friend_ids(db: Db, user_id: int) -> list[int]:
    """Ids of the user's friends, ascending."""
    rows = db.all("SELECT friend_id FROM friendships WHERE user_id = ? ORDER BY friend_id", user_id)
    return [int(r["friend_id"]) for r in rows]


def visible_post(db: Db, post_id: int, viewer_id: int) -> Row:
    """The posts row; HTTPError(404) unless its author is the viewer or a friend of the viewer."""
    row = db.one("SELECT * FROM posts WHERE id = ?", post_id)
    if row is None:
        raise HTTPError(404, "post not found")
    author = int(row["author_id"])
    if author != viewer_id and not are_friends(db, viewer_id, author):
        raise HTTPError(404, "post not found")
    return row


def can_see_post(db: Db, post_id: int, viewer_id: int) -> bool:
    """True if the post exists and its author is the viewer or a friend of the viewer."""
    row = db.one("SELECT author_id FROM posts WHERE id = ?", post_id)
    if row is None:
        return False
    author = int(row["author_id"])
    return author == viewer_id or are_friends(db, viewer_id, author)
