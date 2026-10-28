import importlib

import pytest

from chatbook.testing import Account, Client


def setup_five_messages(c: Client) -> tuple[Account, Account, Account, int, int, list[int]]:
    """Create a DM between `ada` and `ben` with 5 messages interleaved with another chat."""
    ada = c.user("ada", "Ada Ahn")
    ben = c.user("ben", "Ben Bae")
    cal = c.user("cal", "Cal Cho")
    other_cid = c.dm(ben, cal)
    cid = c.dm(ada, ben)
    c.send(ben, other_cid, "noise 1")
    ids: list[int] = []
    texts = ["alpha", "bravo", "charlie", "delta", "echo"]
    for idx, text in enumerate(texts):
        c.tick(1000)
        sender = ada if idx % 2 == 0 else ben
        ids.append(c.send(sender, cid, text))
        if idx in (0, 2, 4):
            c.tick(500)
            c.send(cal, other_cid, f"side {idx}")
    return ada, ben, cal, cid, other_cid, ids


# -- GET /api/conversations/{id}/messages: pagination & ordering --------------------------


def test_default_returns_all_messages_oldest_first_and_has_more_false() -> None:
    c = Client()
    ada, ben, _, cid, _, ids = setup_five_messages(c)
    assert len(ids) == 5
    assert ids != [1, 2, 3, 4, 5]  # interleaved with another conversation
    r = c.get(f"/api/conversations/{cid}/messages", user=ada)
    assert r.status == 200
    assert r.json == {
        "messages": [c.message(mid) for mid in ids],
        "has_more": False,
    }
    r_ben = c.get(f"/api/conversations/{cid}/messages", user=ben)
    assert (r_ben.status, r_ben.json) == (200, r.json)


def test_limit_returns_newest_slice_in_ascending_order() -> None:
    c = Client()
    ada, _, _, cid, _, ids = setup_five_messages(c)
    r = c.get(f"/api/conversations/{cid}/messages?limit=2", user=ada)
    assert r.status == 200
    assert r.json == {
        "messages": [c.message(ids[3]), c.message(ids[4])],
        "has_more": True,
    }
    r_exact = c.get(f"/api/conversations/{cid}/messages?limit=5", user=ada)
    assert r_exact.status == 200
    assert r_exact.json == {
        "messages": [c.message(mid) for mid in ids],
        "has_more": False,
    }


def test_default_limit_is_50_and_max_limit_200_is_accepted() -> None:
    c = Client()
    ada = c.user("ada", "Ada Ahn")
    ben = c.user("ben", "Ben Bae")
    cid = c.dm(ada, ben)
    ids = [c.send(ada if i % 2 == 0 else ben, cid, f"m-{i}") for i in range(55)]

    r_default = c.get(f"/api/conversations/{cid}/messages", user=ada)
    assert r_default.status == 200
    assert r_default.json == {
        "messages": [c.message(mid) for mid in ids[5:]],
        "has_more": True,
    }

    r_max = c.get(f"/api/conversations/{cid}/messages?limit=200", user=ada)
    assert r_max.status == 200
    assert r_max.json == {
        "messages": [c.message(mid) for mid in ids],
        "has_more": False,
    }


def test_before_cursor_and_combined_before_and_limit() -> None:
    c = Client()
    ada, _, _, cid, _, ids = setup_five_messages(c)
    r1 = c.get(f"/api/conversations/{cid}/messages?before={ids[2]}", user=ada)
    assert r1.status == 200
    assert r1.json == {
        "messages": [c.message(ids[0]), c.message(ids[1])],
        "has_more": False,
    }
    r2 = c.get(f"/api/conversations/{cid}/messages?before={ids[3]}&limit=1", user=ada)
    assert r2.status == 200
    assert r2.json == {
        "messages": [c.message(ids[2])],
        "has_more": True,
    }
    r3 = c.get(f"/api/conversations/{cid}/messages?before={ids[3]}&limit=2", user=ada)
    assert r3.status == 200
    assert r3.json == {
        "messages": [c.message(ids[1]), c.message(ids[2])],
        "has_more": True,
    }
    r4 = c.get(f"/api/conversations/{cid}/messages?before={ids[3]}&limit=3", user=ada)
    assert r4.status == 200
    assert r4.json == {
        "messages": [c.message(ids[0]), c.message(ids[1]), c.message(ids[2])],
        "has_more": False,
    }


@pytest.mark.parametrize("cursor_kind", ["zero", "first_id"])
def test_before_at_or_below_oldest_message_returns_empty(cursor_kind: str) -> None:
    c = Client()
    ada, _, _, cid, _, ids = setup_five_messages(c)
    cursor = 0 if cursor_kind == "zero" else ids[0]
    r = c.get(f"/api/conversations/{cid}/messages?before={cursor}", user=ada)
    assert (r.status, r.json) == (200, {"messages": [], "has_more": False})


def test_empty_conversation_returns_empty_list() -> None:
    c = Client()
    ada = c.user("ada", "Ada Ahn")
    ben = c.user("ben", "Ben Bae")
    cal = c.user("cal", "Cal Cho")
    other = c.dm(ben, cal)
    c.send(ben, other, "elsewhere")
    cid = c.dm(ada, ben)
    r = c.get(f"/api/conversations/{cid}/messages", user=ada)
    assert (r.status, r.json) == (200, {"messages": [], "has_more": False})


def test_empty_query_params_use_defaults() -> None:
    c = Client()
    ada, _, _, cid, _, ids = setup_five_messages(c)
    r = c.get(f"/api/conversations/{cid}/messages?limit=&before=", user=ada)
    assert r.status == 200
    assert r.json == {
        "messages": [c.message(mid) for mid in ids],
        "has_more": False,
    }


def test_group_conversation_and_unfriended_direct_conversation_work() -> None:
    c = Client()
    ada = c.user("ada", "Ada Ahn")
    ben = c.user("ben", "Ben Bae")
    cal = c.user("cal", "Cal Cho")
    # Group members who are not friends can read message history
    g = c.group(ada, [ben, cal], "Study")
    m1 = c.send(ada, g, "notes 1")
    c.tick(1000)
    m2 = c.send(cal, g, "notes 2")
    rg = c.get(f"/api/conversations/{g}/messages", user=ben)
    assert (rg.status, rg.json) == (
        200,
        {"messages": [c.message(m1), c.message(m2)], "has_more": False},
    )
    # Direct conversation members who unfriended can still read history
    c.befriend(ada, ben)
    d = c.dm(ada, ben)
    dm_msg = c.send(ada, d, "old friend")
    c.unfriend(ada, ben)
    rd = c.get(f"/api/conversations/{d}/messages", user=ben)
    assert (rd.status, rd.json) == (
        200,
        {"messages": [c.message(dm_msg)], "has_more": False},
    )


def test_history_is_read_only_and_does_not_mark_read() -> None:
    c = Client()
    ada = c.user("ada", "Ada Ahn")
    ben = c.user("ben", "Ben Bae")
    cid = c.dm(ada, ben)
    c.send(ada, cid, "first unread")
    m2 = c.send(ada, cid, "second unread")
    assert c.unread(ben, cid) == 2
    r = c.get(f"/api/conversations/{cid}/messages", user=ben)
    assert r.status == 200
    assert c.unread(ben, cid) == 2
    assert c.rows(
        "SELECT user_id, last_read_id FROM members WHERE conversation_id = ? ORDER BY user_id",
        cid,
    ) == [
        {"user_id": ada.id, "last_read_id": m2},
        {"user_id": ben.id, "last_read_id": 0},
    ]


# -- GET /api/conversations/{id}/messages: validation & authorization ---------------------


@pytest.mark.parametrize(
    "query",
    [
        "limit=0",
        "limit=-1",
        "limit=201",
        "limit=x",
        "limit=1.5",
        "before=x",
        "before=-1",
        "before=2.5",
        "before=12345678901234567890",
    ],
)
def test_bad_query_parameter_is_400(query: str) -> None:
    c = Client()
    ada = c.user("ada", "Ada Ahn")
    ben = c.user("ben", "Ben Bae")
    cid = c.dm(ada, ben)
    c.send(ada, cid, "hi")
    r = c.get(f"/api/conversations/{cid}/messages?{query}", user=ada)
    assert r.status == 400


@pytest.mark.parametrize(
    "case",
    ["dm_outsider", "group_outsider", "left_group", "unknown_id", "abc", "0", "-4", "1.5"],
)
def test_non_member_or_bad_conversation_id_is_404(case: str) -> None:
    c = Client()
    ada = c.user("ada", "Ada Ahn")
    ben = c.user("ben", "Ben Bae")
    cal = c.user("cal", "Cal Cho")
    dan = c.user("dan", "Dan Doe")
    d = c.dm(ada, ben)
    g = c.group(ada, [ben, cal], "Team")
    c.send(ada, d, "secret")
    c.send(ada, g, "team msg")
    if case == "left_group":
        c.leave(cal, g)
    who, target = {
        "dm_outsider": (cal, d),
        "group_outsider": (dan, g),
        "left_group": (cal, g),
        "unknown_id": (ada, 999),
    }.get(case, (ada, case))
    r = c.get(f"/api/conversations/{target}/messages", user=who)
    assert r.status == 404


def test_membership_is_checked_before_query_parameters() -> None:
    c = Client()
    ada = c.user("ada", "Ada Ahn")
    ben = c.user("ben", "Ben Bae")
    cal = c.user("cal", "Cal Cho")
    d = c.dm(ada, ben)
    assert c.get(f"/api/conversations/{d}/messages?limit=0", user=cal).status == 404
    assert c.get(f"/api/conversations/{d}/messages?before=-1", user=cal).status == 404
    assert c.get("/api/conversations/999/messages?limit=999", user=ada).status == 404
    assert c.get("/api/conversations/abc/messages?before=xyz", user=ada).status == 404


def test_lives_in_its_own_feature_folder() -> None:
    importlib.import_module("chatbook.features.chat_history.handler")
