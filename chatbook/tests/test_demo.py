"""The --demo seed (core/demo.py) works on an empty DB through core helpers only."""

from chatbook import create_app
from chatbook.__main__ import seed_demo
from chatbook.core.chat import find_direct, member_ids
from chatbook.core.clock import FakeClock
from chatbook.core.demo import seed
from chatbook.core.social import are_friends
from chatbook.core.store import connect
from chatbook.core.users import check_password

NOW = 1_700_000_000_000


def test_seed_on_an_empty_database() -> None:
    db = connect(":memory:", hash_iterations=1)
    seed(db, NOW)
    users = {r["username"]: r for r in db.all("SELECT * FROM users")}
    names = {u: r["display_name"] for u, r in users.items()}
    assert names == {
        "alice": "Alice Adams",
        "bob": "Bob Brown",
        "carol": "Carol Chen",
        "dave": "Dave Diaz",
    }
    for username in names:
        assert check_password(db, username, "password1") is not None
    alice, bob, carol, dave = (users[u]["id"] for u in ["alice", "bob", "carol", "dave"])

    pairs = [(alice, bob), (alice, carol), (bob, carol)]
    for x, y in pairs:
        assert are_friends(db, x, y) and are_friends(db, y, x)
    assert db.value("SELECT COUNT(*) FROM friendships") == 2 * len(pairs)
    requests = db.all("SELECT from_id, to_id FROM friend_requests")
    assert requests == [{"from_id": dave, "to_id": alice}]

    direct = find_direct(db, alice, bob)
    assert direct is not None
    assert db.value("SELECT COUNT(*) FROM messages WHERE conversation_id = ?", direct) == 3
    group = db.one("SELECT * FROM conversations WHERE kind = 'group'")
    assert group is not None and group["title"] == "Weekend trip"
    assert member_ids(db, group["id"]) == sorted([alice, bob, carol])
    assert db.value("SELECT COUNT(*) FROM messages WHERE conversation_id = ?", group["id"]) == 2
    assert db.value("SELECT COUNT(*) FROM conversations") == 2
    last = db.value("SELECT MAX(id) FROM messages WHERE conversation_id = ?", direct)
    assert db.value("SELECT last_message_id FROM conversations WHERE id = ?", direct) == last

    authors = sorted(r["author_id"] for r in db.all("SELECT author_id FROM posts"))
    assert authors == sorted([alice, bob])
    assert db.value("SELECT COUNT(*) FROM likes") == 1
    assert db.value("SELECT COUNT(*) FROM comments") == 1


def test_demo_flag_seeds_only_an_empty_database() -> None:
    app = create_app(":memory:", clock=FakeClock(), hash_iterations=1)
    assert seed_demo(app) is True
    assert app.db.value("SELECT COUNT(*) FROM users") == 4
    assert seed_demo(app) is False  # users exist: nothing is added
    assert app.db.value("SELECT COUNT(*) FROM users") == 4
    assert app.db.value("SELECT COUNT(*) FROM messages") == 5
