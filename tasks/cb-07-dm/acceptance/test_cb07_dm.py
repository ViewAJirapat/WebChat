import importlib

import pytest

from chatbook.testing import Account, Client

URL = "/api/dm"


def cast(c: Client) -> tuple[Account, Account, Account, Account]:
    return (
        c.user("gina"),  # id 1, display name "Gina"
        c.user("hank", "Hank Hill"),  # id 2
        c.user("iris", "Iris Ivy"),  # id 3
        c.user("xena", "Xena Xu"),  # id 4, nobody's friend unless a test says so
    )


def conv(
    cid: int,
    title: str,
    members: list[Account],
    updated_at: int,
    last_message: object = None,
    unread: int = 0,
) -> dict[str, object]:
    return {
        "id": cid,
        "kind": "direct",
        "title": title,
        "members": [m.json for m in members],
        "last_message": last_message,
        "unread": unread,
        "updated_at": updated_at,
    }


def open_dm(c: Client, me: Account, other: Account) -> tuple[int, object]:
    res = c.post(URL, {"user_id": other.id}, user=me)
    return res.status, res.json


def conversation_rows(c: Client) -> list[dict[str, object]]:
    return c.rows("SELECT * FROM conversations ORDER BY id")


def member_rows(c: Client) -> list[dict[str, object]]:
    return c.rows("SELECT * FROM members ORDER BY conversation_id, user_id")


# -- creating ------------------------------------------------------------------------------


def test_first_open_creates_the_direct_conversation() -> None:
    c = Client()
    gina, hank, _, _ = cast(c)
    c.befriend(gina, hank)
    c.tick(2500)
    assert open_dm(c, gina, hank) == (
        201,
        {"conversation": conv(1, "Hank Hill", [gina, hank], c.now)},
    )
    assert conversation_rows(c) == [
        {
            "id": 1,
            "kind": "direct",
            "title": "",
            "direct_key": "1:2",
            "created_by": gina.id,
            "created_at": c.now,
            "last_message_id": 0,
        },
    ]
    assert member_rows(c) == [
        {"conversation_id": 1, "user_id": gina.id, "joined_at": c.now, "last_read_id": 0},
        {"conversation_id": 1, "user_id": hank.id, "joined_at": c.now, "last_read_id": 0},
    ]
    assert c.dm(hank, gina) == 1


def test_higher_id_user_opens_first() -> None:
    c = Client()
    _, hank, iris, _ = cast(c)
    c.befriend(hank, iris)
    c.tick(640)
    assert open_dm(c, iris, hank) == (
        201,
        {"conversation": conv(1, "Hank Hill", [hank, iris], c.now)},
    )
    row = c.row("SELECT * FROM conversations WHERE id = ?", 1)
    assert row is not None
    assert (row["direct_key"], row["created_by"], row["title"]) == ("2:3", iris.id, "")


def test_group_of_the_same_two_people_is_not_a_direct_conversation() -> None:
    c = Client()
    gina, hank, _, _ = cast(c)
    c.befriend(gina, hank)
    g = c.group(gina, [hank], "Pair")
    c.send(hank, g, "in the group")
    c.tick(900)
    assert open_dm(c, gina, hank) == (
        201,
        {"conversation": conv(2, "Hank Hill", [gina, hank], c.now)},
    )
    assert [r["kind"] for r in conversation_rows(c)] == ["group", "direct"]


# -- finding -------------------------------------------------------------------------------


def test_second_open_returns_the_same_conversation() -> None:
    c = Client()
    gina, hank, _, _ = cast(c)
    c.befriend(gina, hank)
    c.tick(1200)
    created = c.now
    assert open_dm(c, gina, hank)[0] == 201
    c.tick(3000)
    assert open_dm(c, gina, hank) == (
        200,
        {"conversation": conv(1, "Hank Hill", [gina, hank], created)},
    )
    assert len(conversation_rows(c)) == 1
    assert len(member_rows(c)) == 2


def test_other_side_gets_the_same_conversation_with_its_own_title() -> None:
    c = Client()
    gina, hank, _, _ = cast(c)
    c.befriend(gina, hank)
    created = c.now
    assert open_dm(c, gina, hank)[0] == 201
    c.tick(4100)
    assert open_dm(c, hank, gina) == (200, {"conversation": conv(1, "Gina", [gina, hank], created)})
    rows = conversation_rows(c)
    assert len(rows) == 1 and rows[0]["created_by"] == gina.id


def test_existing_conversation_is_shown_as_the_caller_sees_it() -> None:
    c = Client()
    gina, hank, _, _ = cast(c)
    c.befriend(gina, hank)
    cid = c.dm(hank, gina)
    c.tick(100)
    c.send(gina, cid, "are you there?")
    c.tick(200)
    c.send(hank, cid, "yes")
    c.tick(300)
    last = c.send(hank, cid, "what's up")
    sent = c.now
    c.tick(5000)
    assert open_dm(c, gina, hank) == (
        200,
        {
            "conversation": conv(
                cid, "Hank Hill", [gina, hank], sent, last_message=c.message(last), unread=2
            )
        },
    )
    assert open_dm(c, hank, gina) == (
        200,
        {
            "conversation": conv(
                cid, "Gina", [gina, hank], sent, last_message=c.message(last), unread=0
            )
        },
    )
    assert c.unread(gina, cid) == 2
    assert len(conversation_rows(c)) == 1


def test_finds_the_right_conversation_among_several() -> None:
    c = Client()
    gina, hank, iris, xena = cast(c)
    c.befriend(gina, hank)
    c.befriend(gina, iris)
    c.befriend(hank, iris)
    c.befriend(xena, iris)
    d_hank_iris = c.dm(hank, iris)
    c.group(gina, [hank, iris], "Trio")
    d_iris_gina = c.dm(iris, gina)
    d_xena_iris = c.dm(xena, iris)
    c.tick(750)
    assert open_dm(c, gina, hank) == (
        201,
        {"conversation": conv(5, "Hank Hill", [gina, hank], c.now)},
    )
    status, body = open_dm(c, gina, iris)
    assert status == 200 and isinstance(body, dict)
    assert body["conversation"]["id"] == d_iris_gina
    assert body["conversation"]["title"] == "Iris Ivy"
    status, body = open_dm(c, iris, hank)
    assert status == 200 and isinstance(body, dict)
    assert body["conversation"]["id"] == d_hank_iris
    assert body["conversation"]["title"] == "Hank Hill"
    status, body = open_dm(c, iris, xena)
    assert status == 200 and isinstance(body, dict)
    assert body["conversation"]["id"] == d_xena_iris
    assert body["conversation"]["members"] == [iris.json, xena.json]
    assert len(conversation_rows(c)) == 5


def test_friends_again_reuse_the_old_conversation() -> None:
    c = Client()
    gina, hank, _, _ = cast(c)
    c.befriend(gina, hank)
    cid = c.dm(gina, hank)
    mid = c.send(gina, cid, "see you")
    sent = c.now
    c.unfriend(gina, hank)
    c.tick(8000)
    c.befriend(hank, gina)
    assert open_dm(c, hank, gina) == (
        200,
        {
            "conversation": conv(
                cid, "Gina", [gina, hank], sent, last_message=c.message(mid), unread=1
            )
        },
    )
    assert len(conversation_rows(c)) == 1


# -- errors (each changes nothing) ---------------------------------------------------------


def test_stranger_is_403() -> None:
    c = Client()
    gina, hank, _, xena = cast(c)
    c.befriend(gina, hank)
    assert open_dm(c, gina, xena)[0] == 403
    assert open_dm(c, xena, hank)[0] == 403
    assert conversation_rows(c) == [] and member_rows(c) == []


@pytest.mark.parametrize("asker_first", [True, False])
def test_pending_friend_request_is_403(asker_first: bool) -> None:
    c = Client()
    _, hank, iris, _ = cast(c)
    if asker_first:
        c.friend_request(iris, hank)
    else:
        c.friend_request(hank, iris)
    assert open_dm(c, iris, hank)[0] == 403
    assert conversation_rows(c) == []


def test_former_friend_with_an_old_conversation_is_403() -> None:
    c = Client()
    gina, hank, _, _ = cast(c)
    c.befriend(gina, hank)
    cid = c.dm(gina, hank)
    c.send(hank, cid, "bye")
    c.unfriend(hank, gina)
    before = (conversation_rows(c), member_rows(c))
    assert open_dm(c, gina, hank)[0] == 403
    assert open_dm(c, hank, gina)[0] == 403
    assert (conversation_rows(c), member_rows(c)) == before


def test_self_is_400() -> None:
    c = Client()
    gina, hank, _, _ = cast(c)
    c.befriend(gina, hank)
    assert open_dm(c, hank, hank)[0] == 400
    assert conversation_rows(c) == []


@pytest.mark.parametrize("uid", [5, 999, 2**63 - 1])
def test_unknown_user_is_404(uid: int) -> None:
    c = Client()
    gina, *_ = cast(c)
    assert c.post(URL, {"user_id": uid}, user=gina).status == 404
    assert conversation_rows(c) == []


@pytest.mark.parametrize(
    "body",
    [
        {"user_id": "2"},
        {"user_id": 0},
        {"user_id": -2},
        {"user_id": 2.5},
        {"user_id": None},
        {"user_id": [2]},
        {"friend_id": 2},
        {},
        [2],
        "2",
        2,
        None,
    ],
)
def test_bad_user_id_is_400(body: object) -> None:
    c = Client()
    gina, hank, _, _ = cast(c)
    c.befriend(gina, hank)
    assert c.post(URL, body, user=gina).status == 400
    assert conversation_rows(c) == []


@pytest.mark.parametrize("flag", [True, False])
def test_true_or_false_is_400(flag: bool) -> None:
    # Sent by hank (id 2): True == 1 is gina, his friend, so only a real bool check gives 400
    # here (gina sending True would hit the self check instead).
    c = Client()
    gina, hank, _, _ = cast(c)
    c.befriend(gina, hank)
    assert c.post(URL, {"user_id": flag}, user=hank).status == 400
    assert conversation_rows(c) == [] and member_rows(c) == []


def test_lives_in_its_own_feature_folder() -> None:
    importlib.import_module("chatbook.features.dm.handler")
