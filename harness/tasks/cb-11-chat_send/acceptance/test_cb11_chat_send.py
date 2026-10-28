import importlib

import pytest

from chatbook.testing import Account, Client


def people(c: Client) -> tuple[Account, Account, Account, Account]:
    return (
        c.user("gwen", "Gwen Hale"),
        c.user("hugo", "Hugo Ito"),
        c.user("ivy", "Ivy Jones"),
        c.user("jules", "Jules Kim"),
    )


def send(c: Client, who: Account, cid: object, body: object) -> tuple[int, object]:
    res = c.post(f"/api/conversations/{cid}/messages", body, user=who)
    return res.status, res.json


def read(c: Client, who: Account, cid: object, body: object = None) -> tuple[int, object]:
    res = c.post(f"/api/conversations/{cid}/read", body, user=who)
    return res.status, res.json


def message_ids(c: Client) -> list[int]:
    return [r["id"] for r in c.rows("SELECT id FROM messages ORDER BY id")]


def last_message_id(c: Client, cid: int) -> int:
    row = c.row("SELECT last_message_id FROM conversations WHERE id = ?", cid)
    assert row is not None
    return int(row["last_message_id"])


def last_read_id(c: Client, who: Account, cid: int) -> int:
    row = c.row(
        "SELECT last_read_id FROM members WHERE conversation_id = ? AND user_id = ?", cid, who.id
    )
    assert row is not None
    return int(row["last_read_id"])


# -- send: success ------------------------------------------------------------------------


def test_send_in_a_direct_conversation_returns_and_stores_the_message() -> None:
    c = Client()
    gwen, hugo, ivy, jules = people(c)
    c.befriend(gwen, hugo)
    c.befriend(ivy, jules)
    elsewhere = c.dm(ivy, jules)
    c.send(ivy, elsewhere, "first")
    c.send(jules, elsewhere, "second")
    cid = c.dm(gwen, hugo)
    c.tick(4500)
    status, body = send(c, gwen, cid, {"body": "  lunch at noon?  "})
    expected = {
        "id": 3,
        "conversation_id": cid,
        "sender": gwen.json,
        "body": "lunch at noon?",
        "created_at": c.now,
    }
    assert (status, body) == (201, {"message": expected})
    assert c.message(3) == expected
    assert message_ids(c) == [1, 2, 3]
    assert last_message_id(c, cid) == 3
    assert last_message_id(c, elsewhere) == 2
    assert c.unread(hugo, cid) == 1
    assert c.unread(gwen, cid) == 0
    assert last_read_id(c, gwen, cid) == 3
    assert last_read_id(c, hugo, cid) == 0


def test_both_members_can_send_and_the_sender_has_no_unread() -> None:
    c = Client()
    gwen, hugo, _, _ = people(c)
    c.befriend(hugo, gwen)
    cid = c.dm(hugo, gwen)
    c.tick(700)
    s1, b1 = send(c, gwen, cid, {"body": "ping"})
    t1 = c.now
    c.tick(2500)
    s2, b2 = send(c, gwen, cid, {"body": "ping again"})
    t2 = c.now
    assert c.unread(hugo, cid) == 2
    c.tick(60000)
    s3, b3 = send(c, hugo, cid, {"body": " pong "})
    assert (s1, s2, s3) == (201, 201, 201)
    assert b1 == {
        "message": {
            "id": 1,
            "conversation_id": cid,
            "sender": gwen.json,
            "body": "ping",
            "created_at": t1,
        }
    }
    assert b2 == {
        "message": {
            "id": 2,
            "conversation_id": cid,
            "sender": gwen.json,
            "body": "ping again",
            "created_at": t2,
        }
    }
    assert b3 == {
        "message": {
            "id": 3,
            "conversation_id": cid,
            "sender": hugo.json,
            "body": "pong",
            "created_at": c.now,
        }
    }
    assert c.unread(hugo, cid) == 0
    assert c.unread(gwen, cid) == 1
    assert last_read_id(c, hugo, cid) == 3
    assert last_read_id(c, gwen, cid) == 2
    assert last_message_id(c, cid) == 3


def test_group_members_send_without_being_friends() -> None:
    c = Client()
    gwen, hugo, ivy, jules = people(c)
    c.befriend(gwen, jules)
    g = c.group(gwen, [hugo, ivy], "Book club")
    c.send(gwen, g, "welcome")
    c.tick(3000)
    status, body = send(c, hugo, g, {"body": "  chapter 3 done "})
    assert (status, body) == (
        201,
        {
            "message": {
                "id": 2,
                "conversation_id": g,
                "sender": hugo.json,
                "body": "chapter 3 done",
                "created_at": c.now,
            }
        },
    )
    assert c.unread(gwen, g) == 1
    assert c.unread(ivy, g) == 2
    assert c.unread(hugo, g) == 0
    assert last_message_id(c, g) == 2


@pytest.mark.parametrize(
    "text",
    ["k", "w" * 2000, "   " + "w" * 2000 + " \n", "\tA  b\nc d "],
    ids=["one_char", "2000_chars", "2000_chars_padded", "inner_whitespace"],
)
def test_body_is_stripped_and_kept_up_to_2000_characters(text: str) -> None:
    c = Client()
    gwen, hugo, _, _ = people(c)
    c.befriend(gwen, hugo)
    cid = c.dm(gwen, hugo)
    status, body = send(c, hugo, cid, {"body": text})
    assert status == 201
    assert isinstance(body, dict)
    assert body["message"]["body"] == text.strip()
    assert c.message(1)["body"] == text.strip()


# -- send: friendship ---------------------------------------------------------------------


@pytest.mark.parametrize("sender", ["gwen", "hugo"])
def test_unfriended_direct_is_403_but_a_group_of_the_same_two_accepts(sender: str) -> None:
    c = Client()
    gwen, hugo, _, _ = people(c)
    c.befriend(gwen, hugo)
    cid = c.dm(gwen, hugo)
    g = c.group(hugo, [gwen], "Pair")
    c.send(gwen, cid, "before")
    c.unfriend(gwen, hugo)
    who = gwen if sender == "gwen" else hugo
    status, _ = send(c, who, cid, {"body": "after"})
    assert status == 403
    assert message_ids(c) == [1]
    assert last_message_id(c, cid) == 1
    status, body = send(c, who, g, {"body": "still here"})
    assert status == 201
    assert body == {"message": c.message(2)}
    assert c.message(2)["conversation_id"] == g


@pytest.mark.parametrize("sender", ["gwen", "hugo"])
def test_direct_needs_friendship_with_the_other_member(sender: str) -> None:
    c = Client()
    gwen, hugo, ivy, jules = people(c)
    c.befriend(gwen, ivy)
    c.befriend(gwen, jules)
    c.befriend(hugo, ivy)
    cid = c.dm(gwen, hugo)
    status, _ = send(c, gwen if sender == "gwen" else hugo, cid, {"body": "hey there"})
    assert status == 403
    assert message_ids(c) == []


def test_friends_again_can_send_again() -> None:
    c = Client()
    gwen, hugo, _, _ = people(c)
    c.befriend(gwen, hugo)
    cid = c.dm(gwen, hugo)
    c.unfriend(hugo, gwen)
    assert send(c, hugo, cid, {"body": "sorry"})[0] == 403
    c.befriend(hugo, gwen)
    status, body = send(c, hugo, cid, {"body": "sorry"})
    assert status == 201
    assert body == {"message": c.message(1)}


# -- send: errors -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        {"body": ""},
        {"body": "    "},
        {"body": "\n\t "},
        {"body": "q" * 2001},
        {"body": " " + "q" * 2001 + " "},
        {"body": 7},
        {"body": None},
        {"body": True},
        {"body": ["hi"]},
        {},
        {"text": "hi"},
        ["hi"],
        "hi",
        None,
    ],
)
def test_bad_body_is_400(payload: object) -> None:
    c = Client()
    gwen, hugo, _, _ = people(c)
    c.befriend(gwen, hugo)
    cid = c.dm(gwen, hugo)
    status, _ = send(c, gwen, cid, payload)
    assert status == 400
    assert message_ids(c) == []
    assert last_message_id(c, cid) == 0


@pytest.mark.parametrize("case", ["outsider", "group_outsider", "left", "unknown"])
def test_send_where_not_a_member_is_404(case: str) -> None:
    c = Client()
    gwen, hugo, ivy, jules = people(c)
    c.befriend(gwen, hugo)
    c.befriend(ivy, gwen)
    c.befriend(ivy, hugo)
    cid = c.dm(gwen, hugo)
    g = c.group(gwen, [hugo, jules], "Trio")
    who, target = {
        "outsider": (ivy, cid),
        "group_outsider": (ivy, g),
        "left": (jules, g),
        "unknown": (gwen, 4040),
    }[case]
    if case == "left":
        c.leave(jules, g)
    status, _ = send(c, who, target, {"body": "knock knock"})
    assert status == 404
    assert message_ids(c) == []


@pytest.mark.parametrize("bad", ["abc", "0", "-1", "12345678901234567890"])
def test_send_malformed_id_is_404(bad: str) -> None:
    c = Client()
    gwen, hugo, _, _ = people(c)
    c.befriend(gwen, hugo)
    c.dm(gwen, hugo)
    status, _ = send(c, gwen, bad, {"body": "hello there"})
    assert status == 404
    assert message_ids(c) == []


def test_membership_is_checked_before_the_body() -> None:
    c = Client()
    gwen, hugo, ivy, _ = people(c)
    c.befriend(gwen, hugo)
    cid = c.dm(gwen, hugo)
    assert send(c, ivy, cid, {"body": "   "})[0] == 404
    assert send(c, gwen, 777, {"body": 12})[0] == 404


def test_body_is_checked_before_the_friendship() -> None:
    c = Client()
    gwen, hugo, _, _ = people(c)
    cid = c.dm(gwen, hugo)
    assert send(c, hugo, cid, {"body": "  "})[0] == 400
    assert send(c, hugo, cid, {"body": "fine text"})[0] == 403
    assert message_ids(c) == []


# -- read ---------------------------------------------------------------------------------


def test_read_marks_the_conversation_read() -> None:
    c = Client()
    gwen, hugo, ivy, jules = people(c)
    c.befriend(gwen, hugo)
    cid = c.dm(gwen, hugo)
    g = c.group(ivy, [jules], "Side")
    c.send(gwen, cid, "one")
    c.send(ivy, g, "x")
    c.send(gwen, cid, "two")
    c.send(jules, g, "y")
    last = c.send(gwen, cid, "three")
    c.send(ivy, g, "z")
    assert c.unread(hugo, cid) == 3
    status, body = read(c, hugo, cid)
    assert (status, body) == (200, {"conversation_id": cid, "last_read_id": last, "unread": 0})
    assert last == 5
    assert c.unread(hugo, cid) == 0
    assert last_read_id(c, hugo, cid) == 5
    assert last_read_id(c, gwen, cid) == 5
    assert c.unread(jules, g) == 1
    assert message_ids(c) == [1, 2, 3, 4, 5, 6]


def test_read_after_new_messages_moves_forward_and_repeats() -> None:
    c = Client()
    gwen, hugo, _, _ = people(c)
    c.befriend(gwen, hugo)
    cid = c.dm(gwen, hugo)
    first = c.send(hugo, cid, "a")
    c.read(gwen, cid)
    c.send(gwen, cid, "b")
    c.send(hugo, cid, "c")
    c.send(hugo, cid, "d")
    newest = c.send(hugo, cid, "e")
    assert first == 1 and c.unread(gwen, cid) == 3
    expected = {"conversation_id": cid, "last_read_id": newest, "unread": 0}
    assert read(c, gwen, cid) == (200, expected)
    assert read(c, gwen, cid) == (200, expected)
    assert last_read_id(c, gwen, cid) == newest == 5


def test_read_by_the_last_sender_returns_their_own_message() -> None:
    c = Client()
    gwen, hugo, _, _ = people(c)
    c.befriend(gwen, hugo)
    cid = c.dm(gwen, hugo)
    c.send(hugo, cid, "q")
    mine = c.send(gwen, cid, "r")
    assert read(c, gwen, cid) == (200, {"conversation_id": cid, "last_read_id": mine, "unread": 0})
    assert c.unread(hugo, cid) == 1


@pytest.mark.parametrize("kind", ["direct", "group"])
def test_read_without_messages_is_zero(kind: str) -> None:
    c = Client()
    gwen, hugo, ivy, jules = people(c)
    busy = c.group(ivy, [jules], "Busy")
    c.send(ivy, busy, "noise")
    c.send(jules, busy, "more noise")
    cid = c.dm(gwen, hugo) if kind == "direct" else c.group(hugo, [gwen], "Quiet")
    assert read(c, gwen, cid) == (200, {"conversation_id": cid, "last_read_id": 0, "unread": 0})
    assert last_read_id(c, gwen, cid) == 0


def test_read_changes_only_the_reader() -> None:
    c = Client()
    gwen, hugo, ivy, _ = people(c)
    g = c.group(gwen, [hugo, ivy], "Crew")
    c.send(gwen, g, "m1")
    last = c.send(gwen, g, "m2")
    assert read(c, hugo, g) == (200, {"conversation_id": g, "last_read_id": last, "unread": 0})
    assert c.unread(hugo, g) == 0
    assert c.unread(ivy, g) == 2
    assert last_read_id(c, ivy, g) == 0
    assert last_read_id(c, gwen, g) == last


def test_read_needs_no_friendship() -> None:
    c = Client()
    gwen, hugo, _, _ = people(c)
    c.befriend(gwen, hugo)
    cid = c.dm(gwen, hugo)
    c.send(gwen, cid, "bye")
    last = c.send(gwen, cid, "really bye")
    c.unfriend(gwen, hugo)
    assert read(c, hugo, cid) == (200, {"conversation_id": cid, "last_read_id": last, "unread": 0})


def test_read_ignores_a_body() -> None:
    c = Client()
    gwen, hugo, _, _ = people(c)
    c.befriend(gwen, hugo)
    cid = c.dm(gwen, hugo)
    c.send(gwen, cid, "s1")
    c.send(gwen, cid, "s2")
    last = c.send(gwen, cid, "s3")
    status, body = read(c, hugo, cid, {"body": "note", "last_read_id": 1})
    assert (status, body) == (200, {"conversation_id": cid, "last_read_id": last, "unread": 0})
    assert message_ids(c) == [1, 2, 3]


@pytest.mark.parametrize("case", ["outsider", "left", "unknown", "abc", "0", "-3"])
def test_read_where_not_a_member_is_404(case: str) -> None:
    c = Client()
    gwen, hugo, ivy, jules = people(c)
    c.befriend(gwen, hugo)
    cid = c.dm(gwen, hugo)
    g = c.group(gwen, [hugo, jules], "Trio")
    c.send(gwen, g, "hello all")
    if case == "left":
        c.leave(jules, g)
    who, target = {
        "outsider": (ivy, cid),
        "left": (jules, g),
        "unknown": (gwen, 909),
    }.get(case, (gwen, case))
    status, _ = read(c, who, target)
    assert status == 404
    assert c.rows("SELECT * FROM members WHERE user_id = ?", ivy.id) == []


def test_lives_in_its_own_feature_folder() -> None:
    importlib.import_module("chatbook.features.chat_send.handler")
