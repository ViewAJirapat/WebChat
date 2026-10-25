"""Demo data for `python -m chatbook --demo`, written through core helpers only, so it works
whichever features are merged."""

from chatbook.core.chat import create_conversation, post_message
from chatbook.core.social import befriend
from chatbook.core.store import Db
from chatbook.core.users import create_user

DEMO_PASSWORD = "password1"  # local demo only; printed at startup
DEMO_USERS = [
    ("alice", "Alice Adams"),
    ("bob", "Bob Brown"),
    ("carol", "Carol Chen"),
    ("dave", "Dave Diaz"),
]
_MINUTE = 60_000


def seed(db: Db, now: int) -> None:
    """Four users, three friendships, one pending request, a direct chat, a group chat,
    two posts, one like and one comment. The caller owns the transaction."""
    start = now - 120 * _MINUTE
    ids = {
        username: create_user(db, username, DEMO_PASSWORD, name, start).id
        for username, name in DEMO_USERS
    }
    alice, bob, carol, dave = ids["alice"], ids["bob"], ids["carol"], ids["dave"]
    befriend(db, alice, bob, start + _MINUTE)
    befriend(db, alice, carol, start + _MINUTE)
    befriend(db, bob, carol, start + _MINUTE)
    db.run(
        "INSERT INTO friend_requests (from_id, to_id, created_at) VALUES (?, ?, ?)",
        dave,
        alice,
        start + 2 * _MINUTE,
    )

    direct = create_conversation(db, "direct", "", alice, [bob], start + 10 * _MINUTE)
    post_message(db, direct, alice, "Hi Bob! How are you?", start + 11 * _MINUTE)
    post_message(db, direct, bob, "Great, thanks! Lunch tomorrow?", start + 12 * _MINUTE)
    post_message(db, direct, alice, "Sure, see you at noon.", start + 13 * _MINUTE)

    group = create_conversation(
        db, "group", "Weekend trip", alice, [bob, carol], start + 20 * _MINUTE
    )
    post_message(db, group, carol, "Who is in for the lake on Saturday?", start + 21 * _MINUTE)
    post_message(db, group, bob, "Me! I can drive.", start + 22 * _MINUTE)

    post_a = db.run(
        "INSERT INTO posts (author_id, body, created_at) VALUES (?, ?, ?)",
        alice,
        "Hello ChatBook! This is my first post.",
        start + 30 * _MINUTE,
    )
    db.run(
        "INSERT INTO posts (author_id, body, created_at) VALUES (?, ?, ?)",
        bob,
        "Anyone up for a board game night?",
        start + 40 * _MINUTE,
    )
    db.run(
        "INSERT INTO likes (post_id, user_id, created_at) VALUES (?, ?, ?)",
        post_a,
        bob,
        start + 41 * _MINUTE,
    )
    db.run(
        "INSERT INTO comments (post_id, author_id, body, created_at) VALUES (?, ?, ?, ?)",
        post_a,
        carol,
        "Welcome, Alice!",
        start + 42 * _MINUTE,
    )
