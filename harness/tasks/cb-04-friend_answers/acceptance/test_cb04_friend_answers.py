import importlib

import pytest

from chatbook.testing import Account, Client

ROUTES = {
    "accept": ("POST", "/api/friends/requests/{}/accept"),
    "decline": ("POST", "/api/friends/requests/{}/decline"),
    "cancel": ("DELETE", "/api/friends/requests/{}"),
}


def people(c: Client) -> tuple[Account, Account, Account, Account]:
    return (
        c.user("quinn", "Quinn Park"),
        c.user("rosa", "Rosa Lind"),
        c.user("tariq", "Tariq Noor"),
        c.user("uma", "Uma Vale"),
    )


def answer(c: Client, action: str, rid: object, who: Account) -> tuple[int, object]:
    method, path = ROUTES[action]
    res = c.request(method, path.format(rid), user=who)
    return res.status, res.json


def request_ids(c: Client) -> list[int]:
    return [r["id"] for r in c.rows("SELECT id FROM friend_requests ORDER BY id")]


def friendships(c: Client) -> list[dict[str, object]]:
    return c.rows(
        "SELECT user_id, friend_id, created_at FROM friendships ORDER BY user_id, friend_id"
    )


# -- accept -------------------------------------------------------------------------------


def test_accept_makes_friends_and_returns_the_sender() -> None:
    c = Client()
    quinn, rosa, tariq, uma = people(c)
    other1 = c.friend_request(tariq, uma)
    other2 = c.friend_request(uma, quinn)
    rid = c.friend_request(quinn, rosa)
    from_sender = c.friend_request(quinn, tariq)
    from_recipient = c.friend_request(rosa, uma)
    c.tick(7000)
    assert answer(c, "accept", rid, rosa) == (200, {"friend": quinn.json})
    assert c.are_friends(quinn, rosa) and c.are_friends(rosa, quinn)
    assert friendships(c) == [
        {"user_id": quinn.id, "friend_id": rosa.id, "created_at": c.now},
        {"user_id": rosa.id, "friend_id": quinn.id, "created_at": c.now},
    ]
    assert c.row("SELECT * FROM friend_requests WHERE id = ?", rid) is None
    assert request_ids(c) == [other1, other2, from_sender, from_recipient]


def test_accept_answers_the_request_named_by_the_id() -> None:
    c = Client()
    quinn, rosa, tariq, uma = people(c)
    from_quinn = c.friend_request(quinn, rosa)
    from_tariq = c.friend_request(tariq, rosa)
    from_uma = c.friend_request(uma, rosa)
    assert answer(c, "accept", from_tariq, rosa) == (200, {"friend": tariq.json})
    assert c.are_friends(rosa, tariq)
    assert not c.are_friends(rosa, quinn) and not c.are_friends(rosa, uma)
    assert request_ids(c) == [from_quinn, from_uma]
    assert answer(c, "accept", from_uma, rosa) == (200, {"friend": uma.json})
    assert c.are_friends(uma, rosa)
    assert request_ids(c) == [from_quinn]


def test_accept_also_removes_the_request_in_the_other_direction() -> None:
    c = Client()
    quinn, rosa, tariq, _ = people(c)
    keep = c.friend_request(tariq, rosa)
    rid = c.friend_request(quinn, rosa)
    c.friend_request(rosa, quinn)
    assert answer(c, "accept", rid, rosa) == (200, {"friend": quinn.json})
    assert request_ids(c) == [keep]


@pytest.mark.parametrize("who", ["sender", "stranger"])
def test_accept_by_anyone_but_the_recipient_is_404(who: str) -> None:
    c = Client()
    quinn, rosa, tariq, _ = people(c)
    rid = c.friend_request(quinn, rosa)
    status, _ = answer(c, "accept", rid, quinn if who == "sender" else tariq)
    assert status == 404
    assert request_ids(c) == [rid]
    assert friendships(c) == []


# -- decline ------------------------------------------------------------------------------


def test_decline_deletes_only_that_request() -> None:
    c = Client()
    quinn, rosa, tariq, uma = people(c)
    other1 = c.friend_request(uma, tariq)
    rid = c.friend_request(quinn, rosa)
    other2 = c.friend_request(tariq, rosa)
    reverse = c.friend_request(rosa, quinn)
    from_sender = c.friend_request(quinn, uma)
    assert answer(c, "decline", rid, rosa) == (200, {"declined": rid})
    assert request_ids(c) == [other1, other2, reverse, from_sender]
    assert not c.are_friends(quinn, rosa)
    assert friendships(c) == []


@pytest.mark.parametrize("who", ["sender", "stranger"])
def test_decline_by_anyone_but_the_recipient_is_404(who: str) -> None:
    c = Client()
    quinn, rosa, _, uma = people(c)
    rid = c.friend_request(quinn, rosa)
    status, _ = answer(c, "decline", rid, quinn if who == "sender" else uma)
    assert status == 404
    assert request_ids(c) == [rid]


# -- cancel -------------------------------------------------------------------------------


def test_cancel_deletes_only_that_request() -> None:
    c = Client()
    quinn, rosa, tariq, uma = people(c)
    other1 = c.friend_request(quinn, tariq)
    reverse = c.friend_request(rosa, quinn)
    other2 = c.friend_request(uma, quinn)
    rid = c.friend_request(quinn, rosa)
    to_recipient = c.friend_request(tariq, rosa)
    assert answer(c, "cancel", rid, quinn) == (200, {"cancelled": rid})
    assert request_ids(c) == [other1, reverse, other2, to_recipient]
    assert not c.are_friends(quinn, rosa)
    assert friendships(c) == []


@pytest.mark.parametrize("who", ["recipient", "stranger"])
def test_cancel_by_anyone_but_the_sender_is_404(who: str) -> None:
    c = Client()
    quinn, rosa, tariq, _ = people(c)
    rid = c.friend_request(quinn, rosa)
    status, _ = answer(c, "cancel", rid, rosa if who == "recipient" else tariq)
    assert status == 404
    assert request_ids(c) == [rid]


# -- every route --------------------------------------------------------------------------


@pytest.mark.parametrize("action", ["accept", "decline", "cancel"])
@pytest.mark.parametrize("bad", ["4242", "abc", "0", "-2", "12345678901234567890"])
def test_unknown_or_malformed_id_is_404(action: str, bad: str) -> None:
    c = Client()
    quinn, rosa, _, _ = people(c)
    rid = c.friend_request(quinn, rosa)
    who = quinn if action == "cancel" else rosa
    status, _ = answer(c, action, bad, who)
    assert status == 404
    assert request_ids(c) == [rid]


@pytest.mark.parametrize("first", ["accept", "decline", "cancel"])
@pytest.mark.parametrize("second", ["accept", "decline", "cancel"])
def test_an_answered_request_is_404(first: str, second: str) -> None:
    c = Client()
    quinn, rosa, tariq, _ = people(c)
    c.friend_request(tariq, quinn)
    rid = c.friend_request(quinn, rosa)
    assert answer(c, first, rid, quinn if first == "cancel" else rosa)[0] == 200
    status, _ = answer(c, second, rid, quinn if second == "cancel" else rosa)
    assert status == 404
    assert c.are_friends(quinn, rosa) == (first == "accept")


def test_lives_in_its_own_feature_folder() -> None:
    importlib.import_module("chatbook.features.friend_answers.handler")
