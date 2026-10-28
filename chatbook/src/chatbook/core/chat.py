"""Conversations, members and messages (core-owned tables), and the M and C JSON shapes."""

from collections.abc import Mapping
from typing import Any

from chatbook.core.http import HTTPError
from chatbook.core.store import Db, Row
from chatbook.core.users import get_user, user_json

KINDS = ("direct", "group")


def _direct_key(a: int, b: int) -> str:
    lo, hi = sorted((a, b))
    return f"{lo}:{hi}"


def create_conversation(
    db: Db, kind: str, title: str, creator_id: int, member_ids: list[int], now: int
) -> int:
    """Insert a conversation with the creator and member_ids (deduplicated) as members.

    'direct' needs exactly 2 members and stores direct_key 'min:max' and title ''; 'group'
    needs at least 2. A bad kind or member count raises ValueError (a programming error).
    """
    members = [creator_id]
    for uid in member_ids:
        if uid not in members:
            members.append(uid)
    direct_key: str | None = None
    if kind == "direct":
        if len(members) != 2:
            raise ValueError(f"a direct conversation needs exactly 2 members, got {members}")
        direct_key = _direct_key(members[0], members[1])
        title = ""
    elif kind == "group":
        if len(members) < 2:
            raise ValueError(f"a group needs the creator and at least 1 member, got {members}")
    else:
        raise ValueError(f"conversation kind must be one of {KINDS}, got {kind!r}")
    cid = db.run(
        "INSERT INTO conversations (kind, title, direct_key, created_by, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        kind,
        title,
        direct_key,
        creator_id,
        now,
    )
    for uid in members:
        db.run(
            "INSERT INTO members (conversation_id, user_id, joined_at, last_read_id)"
            " VALUES (?, ?, ?, 0)",
            cid,
            uid,
            now,
        )
    return cid


def find_direct(db: Db, a: int, b: int) -> int | None:
    """The id of the direct conversation of a and b, or None."""
    cid = db.value("SELECT id FROM conversations WHERE direct_key = ?", _direct_key(a, b))
    return None if cid is None else int(cid)


def require_member(db: Db, conversation_id: int, user_id: int) -> Row:
    """The conversations row; HTTPError(404) if it is missing or the user is not a member."""
    row = db.one(
        "SELECT c.* FROM conversations c JOIN members m ON m.conversation_id = c.id"
        " WHERE c.id = ? AND m.user_id = ?",
        conversation_id,
        user_id,
    )
    if row is None:
        raise HTTPError(404, "conversation not found")
    return row


def member_ids(db: Db, conversation_id: int) -> list[int]:
    """Ids of the members, ascending."""
    rows = db.all(
        "SELECT user_id FROM members WHERE conversation_id = ? ORDER BY user_id", conversation_id
    )
    return [int(r["user_id"]) for r in rows]


def add_member(db: Db, conversation_id: int, user_id: int, now: int) -> None:
    """Add a member (no-op if already one); older messages do not count as unread for them."""
    last = db.value("SELECT last_message_id FROM conversations WHERE id = ?", conversation_id)
    db.run(
        "INSERT OR IGNORE INTO members (conversation_id, user_id, joined_at, last_read_id)"
        " VALUES (?, ?, ?, ?)",
        conversation_id,
        user_id,
        now,
        int(last or 0),
    )


def remove_member(db: Db, conversation_id: int, user_id: int) -> None:
    """Remove a member (no-op if not one)."""
    db.run(
        "DELETE FROM members WHERE conversation_id = ? AND user_id = ?", conversation_id, user_id
    )


def message_json(db: Db, row: Mapping[str, Any]) -> dict[str, Any]:
    """M = {"id", "conversation_id", "sender": U, "body", "created_at"} from a messages row."""
    sender = get_user(db, int(row["sender_id"]))
    sender_json = (
        user_json(sender)
        if sender is not None
        else {"id": row["sender_id"], "username": "", "display_name": "Unknown"}
    )
    return {
        "id": row["id"],
        "conversation_id": row["conversation_id"],
        "sender": sender_json,
        "body": row["body"],
        "created_at": row["created_at"],
    }


def post_message(
    db: Db, conversation_id: int, sender_id: int, body: str, now: int
) -> dict[str, Any]:
    """Insert a message, move the conversation's last_message_id and the sender's
    last_read_id to it, and return M."""
    mid = db.run(
        "INSERT INTO messages (conversation_id, sender_id, body, created_at) VALUES (?, ?, ?, ?)",
        conversation_id,
        sender_id,
        body,
        now,
    )
    db.run("UPDATE conversations SET last_message_id = ? WHERE id = ?", mid, conversation_id)
    db.run(
        "UPDATE members SET last_read_id = ? WHERE conversation_id = ? AND user_id = ?",
        mid,
        conversation_id,
        sender_id,
    )
    row = {
        "id": mid,
        "conversation_id": conversation_id,
        "sender_id": sender_id,
        "body": body,
        "created_at": now,
    }
    return message_json(db, row)


def mark_read(db: Db, conversation_id: int, user_id: int) -> int:
    """last_read_id = max(last_read_id, last_message_id); returns the new value (0 if not
    a member)."""
    db.run(
        "UPDATE members SET last_read_id = MAX(last_read_id,"
        " (SELECT last_message_id FROM conversations WHERE id = ?))"
        " WHERE conversation_id = ? AND user_id = ?",
        conversation_id,
        conversation_id,
        user_id,
    )
    value = db.value(
        "SELECT last_read_id FROM members WHERE conversation_id = ? AND user_id = ?",
        conversation_id,
        user_id,
    )
    return int(value or 0)


def unread_count(db: Db, conversation_id: int, user_id: int) -> int:
    """Messages after the user's last_read_id sent by someone else; 0 if not a member."""
    last = db.value(
        "SELECT last_read_id FROM members WHERE conversation_id = ? AND user_id = ?",
        conversation_id,
        user_id,
    )
    if last is None:
        return 0
    count = db.value(
        "SELECT COUNT(*) FROM messages WHERE conversation_id = ? AND id > ? AND sender_id != ?",
        conversation_id,
        last,
        user_id,
    )
    return int(count or 0)


def conversation_json(db: Db, conversation_id: int, viewer_id: int) -> dict[str, Any]:
    """C = {"id", "kind", "title", "members": [U by id], "last_message": M | None,
    "unread", "updated_at"} as seen by viewer_id."""
    conv = db.one("SELECT * FROM conversations WHERE id = ?", conversation_id)
    if conv is None:
        raise HTTPError(404, "conversation not found")
    members = [
        user_json(r)
        for r in db.all(
            "SELECT u.id, u.username, u.display_name FROM members m"
            " JOIN users u ON u.id = m.user_id WHERE m.conversation_id = ? ORDER BY u.id",
            conversation_id,
        )
    ]
    if conv["kind"] == "direct":
        others = [m for m in members if m["id"] != viewer_id]
        title = str(others[0]["display_name"]) if others else "Unknown"
    else:
        title = str(conv["title"])
    last = db.one(
        "SELECT * FROM messages WHERE conversation_id = ? ORDER BY id DESC LIMIT 1",
        conversation_id,
    )
    return {
        "id": conv["id"],
        "kind": conv["kind"],
        "title": title,
        "members": members,
        "last_message": None if last is None else message_json(db, last),
        "unread": unread_count(db, conversation_id, viewer_id),
        "updated_at": conv["created_at"] if last is None else last["created_at"],
    }
