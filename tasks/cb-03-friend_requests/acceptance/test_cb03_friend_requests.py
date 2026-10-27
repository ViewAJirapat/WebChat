import importlib

import pytest

from chatbook.testing import Account, Client

URL = "/api/friends/requests"


def crew(c: Client) -> list[Account]:
    return [
        c.user("gina", "Gina Gold"),
        c.user("hugo", "Hugo Hart"),
        c.user("ivan", "Ivan Ito"),
        c.user("jade", "Jade Jones"),
        c.user("kofi", "Kofi Kent"),
        c.user("lena", "Lena Lund"),
    ]


def req(rid: int, frm: Account, to: Account, created_at: int) -> dict[str, object]:
    return {"id": rid, "from": frm.json, "to": to.json, "created_at": created_at}


def row(rid: int, frm: Account, to: Account, created_at: int) -> dict[str, object]:
    return {"id": rid, "from_id": frm.id, "to_id": to.id, "created_at": created_at}


# -- POST /api/friends/requests -----------------------------------------------------------


def test_send_creates_a_pending_request() -> None:
    c = Client()
    gina, hugo, *_ = crew(c)
    c.tick(4321)
    r = c.post(URL, {"user_id": hugo.id}, user=gina)
    assert r.status == 201
    assert r.json == {"status": "pending", "request": req(1, gina, hugo, c.now)}
    assert c.rows("SELECT * FROM friend_requests") == [row(1, gina, hugo, c.now)]
    assert not c.are_friends(gina, hugo)


def test_new_request_gets_the_next_id() -> None:
    c = Client()
    gina, hugo, ivan, jade, *_ = crew(c)
    c.friend_request(ivan, hugo)
    c.tick(90)
    c.friend_request(hugo, gina)
    c.tick(250)
    r = c.post(URL, {"user_id": ivan.id}, user=jade)
    assert r.status == 201
    assert r.json == {"status": "pending", "request": req(3, jade, ivan, c.now)}
    assert c.row("SELECT * FROM friend_requests WHERE id = ?", 3) == row(3, jade, ivan, c.now)
    assert len(c.rows("SELECT * FROM friend_requests")) == 3


def test_repeated_request_is_409_and_keeps_the_first() -> None:
    c = Client()
    gina, hugo, *_ = crew(c)
    assert c.post(URL, {"user_id": hugo.id}, user=gina).status == 201
    first = c.now
    c.tick(5000)
    assert c.post(URL, {"user_id": hugo.id}, user=gina).status == 409
    assert c.rows("SELECT * FROM friend_requests") == [row(1, gina, hugo, first)]


def test_request_to_a_friend_is_409() -> None:
    c = Client()
    gina, _, ivan, *_ = crew(c)
    c.befriend(ivan, gina)
    assert c.post(URL, {"user_id": ivan.id}, user=gina).status == 409
    assert c.rows("SELECT * FROM friend_requests") == []
    assert c.are_friends(gina, ivan)


def test_request_after_unfriend_is_pending_again() -> None:
    c = Client()
    gina, _, ivan, *_ = crew(c)
    c.befriend(gina, ivan)
    c.unfriend(gina, ivan)
    c.tick(60)
    r = c.post(URL, {"user_id": ivan.id}, user=gina)
    assert (r.status, r.json) == (201, {"status": "pending", "request": req(1, gina, ivan, c.now)})


def test_request_to_self_is_400() -> None:
    c = Client()
    _, hugo, *_ = crew(c)
    assert c.post(URL, {"user_id": hugo.id}, user=hugo).status == 400
    assert c.rows("SELECT * FROM friend_requests") == []


@pytest.mark.parametrize("uid", [7, 999, 2**63 - 1])
def test_unknown_user_is_404(uid: int) -> None:
    c = Client()
    gina, *_ = crew(c)
    assert c.post(URL, {"user_id": uid}, user=gina).status == 404
    assert c.rows("SELECT * FROM friend_requests") == []


@pytest.mark.parametrize(
    "body",
    [
        {"user_id": "2"},
        {"user_id": True},
        {"user_id": 0},
        {"user_id": -2},
        {"user_id": 2.5},
        {"user_id": None},
        {"user_id": [2]},
        {"friend_id": 2},
        {},
        [2],
        "2",
        None,
    ],
)
def test_bad_user_id_is_400(body: object) -> None:
    c = Client()
    gina, *_ = crew(c)
    assert c.post(URL, body, user=gina).status == 400
    assert c.rows("SELECT * FROM friend_requests") == []


def test_request_back_makes_friends() -> None:
    c = Client()
    gina, hugo, _, jade, *_ = crew(c)
    c.friend_request(jade, gina)
    c.tick(30)
    c.friend_request(jade, hugo)
    other = c.now
    c.tick(777)
    r = c.post(URL, {"user_id": jade.id}, user=gina)
    assert r.status == 200
    assert r.json == {"status": "friends", "friend": jade.json}
    assert c.are_friends(gina, jade) and c.are_friends(jade, gina)
    assert c.rows("SELECT * FROM friendships WHERE user_id = ?", gina.id) == [
        {"user_id": gina.id, "friend_id": jade.id, "created_at": c.now}
    ]
    assert c.rows("SELECT * FROM friend_requests") == [row(2, jade, hugo, other)]


def test_request_back_through_the_api() -> None:
    c = Client()
    gina, hugo, *_ = crew(c)
    assert c.post(URL, {"user_id": gina.id}, user=hugo).status == 201
    c.tick(1500)
    r = c.post(URL, {"user_id": hugo.id}, user=gina)
    assert (r.status, r.json) == (200, {"status": "friends", "friend": hugo.json})
    assert c.are_friends(hugo, gina)
    assert c.rows("SELECT * FROM friend_requests") == []
    for who in (gina, hugo):
        listed = c.get(URL, user=who)
        assert (listed.status, listed.json) == (200, {"incoming": [], "outgoing": []})


def test_friends_check_comes_before_request_back() -> None:
    c = Client()
    gina, _, ivan, *_ = crew(c)
    c.befriend(gina, ivan)
    c.friend_request(ivan, gina)
    assert c.post(URL, {"user_id": ivan.id}, user=gina).status == 409
    assert len(c.rows("SELECT * FROM friend_requests")) == 1


def test_own_request_check_comes_before_request_back() -> None:
    c = Client()
    gina, hugo, *_ = crew(c)
    c.friend_request(gina, hugo)
    c.friend_request(hugo, gina)
    assert c.post(URL, {"user_id": hugo.id}, user=gina).status == 409
    assert not c.are_friends(gina, hugo)
    assert len(c.rows("SELECT * FROM friend_requests")) == 2


# -- GET /api/friends/requests ------------------------------------------------------------


def test_list_splits_incoming_and_outgoing_newest_first() -> None:
    c = Client()
    gina, hugo, ivan, jade, kofi, lena = crew(c)
    times = []
    for frm, to in [(hugo, gina), (ivan, jade), (jade, gina), (gina, kofi), (ivan, gina),
                    (gina, lena), (lena, kofi)]:
        c.friend_request(frm, to)
        times.append(c.now)
        c.tick(1000 + 100 * len(times))
    r = c.get(URL, user=gina)
    assert r.status == 200
    assert r.json == {
        "incoming": [req(5, ivan, gina, times[4]), req(3, jade, gina, times[2]),
                     req(1, hugo, gina, times[0])],
        "outgoing": [req(6, gina, lena, times[5]), req(4, gina, kofi, times[3])],
    }
    r = c.get(URL, user=jade)
    assert r.json == {"incoming": [req(2, ivan, jade, times[1])],
                      "outgoing": [req(3, jade, gina, times[2])]}


def test_list_orders_by_id_when_times_are_equal() -> None:
    c = Client()
    gina, hugo, ivan, jade, kofi, _ = crew(c)
    c.friend_request(jade, kofi)
    c.friend_request(hugo, kofi)
    c.friend_request(kofi, gina)
    c.friend_request(ivan, kofi)
    c.friend_request(kofi, hugo)
    now = c.now
    r = c.get(URL, user=kofi)
    assert r.status == 200
    assert r.json == {
        "incoming": [req(4, ivan, kofi, now), req(2, hugo, kofi, now), req(1, jade, kofi, now)],
        "outgoing": [req(5, kofi, hugo, now), req(3, kofi, gina, now)],
    }


def test_new_request_is_listed_for_both_sides() -> None:
    c = Client()
    _, hugo, _, jade, *_ = crew(c)
    c.tick(42)
    assert c.post(URL, {"user_id": hugo.id}, user=jade).status == 201
    expected = req(1, jade, hugo, c.now)
    c.tick(10)
    assert c.get(URL, user=hugo).json == {"incoming": [expected], "outgoing": []}
    assert c.get(URL, user=jade).json == {"incoming": [], "outgoing": [expected]}


def test_list_is_empty_without_requests() -> None:
    c = Client()
    gina, hugo, ivan, *_ = crew(c)
    c.friend_request(hugo, ivan)
    c.befriend(gina, hugo)
    r = c.get(URL, user=gina)
    assert (r.status, r.json) == (200, {"incoming": [], "outgoing": []})


def test_lives_in_its_own_feature_folder() -> None:
    importlib.import_module("chatbook.features.friend_requests.handler")
