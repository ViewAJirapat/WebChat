import importlib

import pytest

from chatbook.testing import Account, Client

URL = "/api/groups"


def cast(c: Client) -> list[Account]:
    """Seven users. The usual creator, olga, is not the lowest id."""
    return [
        c.user("pia", "Pia Park"),
        c.user("olga", "Olga Ortiz"),
        c.user("rui", "Rui Rocha"),
        c.user("sia", "Sia Sung"),
        c.user("tom", "Tom Tran"),
        c.user("uma", "Uma Udall"),
        c.user("xavi", "Xavi Xu"),
    ]


def circle(c: Client) -> tuple[Account, list[Account], Account]:
    """olga, her five friends (pia, rui, sia, tom, uma: not friends with each other) and the
    stranger xavi."""
    pia, olga, rui, sia, tom, uma, xavi = cast(c)
    for pal in (tom, pia, uma, rui, sia):
        c.befriend(pal, olga)
    return olga, [pia, rui, sia, tom, uma], xavi


def group_json(
    cid: int,
    title: str,
    members: list[Account],
    updated_at: int,
    *,
    last: object = None,
    unread: int = 0,
) -> dict[str, object]:
    return {
        "id": cid,
        "kind": "group",
        "title": title,
        "members": [m.json for m in sorted(members, key=lambda m: m.id)],
        "last_message": last,
        "unread": unread,
        "updated_at": updated_at,
    }


def assert_nothing_created(c: Client) -> None:
    assert c.rows("SELECT id FROM conversations") == []
    assert c.rows("SELECT user_id FROM members") == []


# -- POST /api/groups ---------------------------------------------------------------------


def test_create_returns_the_new_group() -> None:
    c = Client()
    pia, olga, rui, *_ = cast(c)
    c.befriend(olga, rui)
    c.befriend(pia, olga)
    c.tick(3456)
    body = {"title": "  Ski  ", "member_ids": [rui.id, pia.id, olga.id, rui.id]}
    r = c.post(URL, body, user=olga)
    assert r.status == 201
    assert r.json == {"conversation": group_json(1, "Ski", [pia, olga, rui], c.now)}
    assert r.json["conversation"] == c.conversation(1, olga)
    assert not c.are_friends(pia, rui)


def test_create_stores_the_conversation_and_members() -> None:
    c = Client()
    olga, (pia, rui, sia, tom, uma), _ = circle(c)
    c.tick(9001)
    r = c.post(URL, {"title": "Hike crew", "member_ids": [uma.id, sia.id]}, user=olga)
    assert r.status == 201
    assert c.rows("SELECT * FROM conversations") == [
        {
            "id": 1,
            "kind": "group",
            "title": "Hike crew",
            "direct_key": None,
            "created_by": olga.id,
            "created_at": c.now,
            "last_message_id": 0,
        }
    ]
    members = c.rows(
        "SELECT conversation_id, user_id, joined_at, last_read_id FROM members ORDER BY user_id"
    )
    assert members == [
        {"conversation_id": 1, "user_id": u.id, "joined_at": c.now, "last_read_id": 0}
        for u in (olga, sia, uma)
    ]


@pytest.mark.parametrize(
    ("title", "picks", "stored"),
    [
        ("Band", [4, 0], "Band"),
        ("  Road   trip ", [1, 2, 3], "Road   trip"),
        ("Q", [3], "Q"),
        ("z" * 50, [0, 1, 2, 3, 4], "z" * 50),
        (" " + "w" * 50 + "\t", [2, 2, 0], "w" * 50),
        ("Movie night", [3, 1, 3, 1], "Movie night"),
    ],
)
def test_create_members_and_title(title: str, picks: list[int], stored: str) -> None:
    c = Client()
    olga, pals, _ = circle(c)
    c.tick(250)
    r = c.post(URL, {"title": title, "member_ids": [pals[i].id for i in picks]}, user=olga)
    chosen = [olga] + [pals[i] for i in sorted(set(picks))]
    assert r.status == 201
    assert r.json == {"conversation": group_json(1, stored, chosen, c.now)}


def test_any_user_can_create_a_group_with_a_friend() -> None:
    c = Client()
    olga, (pia, rui, sia, tom, uma), _ = circle(c)
    c.tick(42)
    r = c.post(URL, {"title": "Two of us", "member_ids": [olga.id]}, user=tom)
    assert r.status == 201
    assert r.json == {"conversation": group_json(1, "Two of us", [olga, tom], c.now)}
    assert r.json["conversation"] == c.conversation(1, tom)


def test_each_create_makes_a_new_conversation() -> None:
    c = Client()
    olga, (pia, rui, *_), _ = circle(c)
    c.dm(olga, pia)
    c.group(olga, [pia, rui], "Same")
    body = {"title": "Same", "member_ids": [pia.id, rui.id]}
    first = c.post(URL, body, user=olga)
    c.tick(5)
    second = c.post(URL, body, user=olga)
    assert (first.status, first.json["conversation"]["id"]) == (201, 3)
    assert second.status == 201
    assert second.json == {"conversation": group_json(4, "Same", [olga, pia, rui], c.now)}
    kinds = c.rows("SELECT id, kind FROM conversations ORDER BY id")
    assert [(k["id"], k["kind"]) for k in kinds] == [
        (1, "direct"),
        (2, "group"),
        (3, "group"),
        (4, "group"),
    ]


def big_circle(c: Client, n: int) -> tuple[Account, list[Account]]:
    host = c.user("host", "Host Hall")
    pals = [c.user(f"pal{i:02d}", f"Pal {i:02d}") for i in range(n)]
    for pal in pals:
        c.befriend(host, pal)
    return host, pals


def test_49_others_is_the_limit_and_i_do_not_count() -> None:
    c = Client()
    host, pals = big_circle(c, 49)
    ids = [host.id] + [p.id for p in pals]
    r = c.post(URL, {"title": "Big one", "member_ids": ids}, user=host)
    assert r.status == 201
    assert r.json == {"conversation": group_json(1, "Big one", [host, *pals], c.now)}
    assert len(c.rows("SELECT user_id FROM members WHERE conversation_id = ?", 1)) == 50


@pytest.mark.parametrize("with_me", [False, True])
def test_50_others_is_400(with_me: bool) -> None:
    c = Client()
    host, pals = big_circle(c, 50)
    ids = [p.id for p in pals] + ([host.id] if with_me else [])
    assert c.post(URL, {"title": "Too big", "member_ids": ids}, user=host).status == 400
    assert_nothing_created(c)


def test_duplicates_do_not_count_toward_the_limit() -> None:
    c = Client()
    olga, (pia, rui, *_), _ = circle(c)
    ids = [rui.id] * 30 + [pia.id] * 30
    r = c.post(URL, {"title": "Echo", "member_ids": ids}, user=olga)
    assert r.status == 201
    assert r.json == {"conversation": group_json(1, "Echo", [olga, pia, rui], c.now)}


@pytest.mark.parametrize("times", [0, 1, 3])
def test_no_other_member_is_400(times: int) -> None:
    c = Client()
    olga, _, _ = circle(c)
    r = c.post(URL, {"title": "Alone", "member_ids": [olga.id] * times}, user=olga)
    assert r.status == 400
    assert_nothing_created(c)


def test_me_and_one_friend_make_a_group() -> None:
    c = Client()
    olga, (pia, rui, sia, *_), _ = circle(c)
    r = c.post(URL, {"title": "Duo", "member_ids": [olga.id, sia.id, olga.id]}, user=olga)
    assert r.status == 201
    assert r.json == {"conversation": group_json(1, "Duo", [olga, sia], c.now)}


@pytest.mark.parametrize(
    "bad",
    [
        "x",
        "2",
        3,
        None,
        {"3": 3},
        [True],
        [False],
        [0],
        [-2],
        [1.5],
        [2.0],
        ["3"],
        [None],
        [[3]],
    ],
)
def test_bad_member_ids_is_400(bad: object) -> None:
    c = Client()
    olga, _, _ = circle(c)
    assert c.post(URL, {"title": "Bad", "member_ids": bad}, user=olga).status == 400
    assert_nothing_created(c)


def test_bad_item_after_a_friend_is_400() -> None:
    c = Client()
    olga, (pia, *_), _ = circle(c)
    for item in [True, 0, "4", 2.5]:
        body = {"title": "Mixed", "member_ids": [pia.id, item]}
        assert c.post(URL, body, user=olga).status == 400
    assert_nothing_created(c)


def test_missing_member_ids_is_400() -> None:
    c = Client()
    olga, _, _ = circle(c)
    assert c.post(URL, {"title": "Nobody"}, user=olga).status == 400
    assert_nothing_created(c)


@pytest.mark.parametrize("title", ["", "    ", "t" * 51, "  " + "t" * 51 + " ", 77, None, ["Ski"]])
def test_bad_title_is_400(title: object) -> None:
    c = Client()
    olga, (pia, *_), _ = circle(c)
    assert c.post(URL, {"title": title, "member_ids": [pia.id]}, user=olga).status == 400
    assert_nothing_created(c)


def test_missing_title_is_400() -> None:
    c = Client()
    olga, (pia, *_), _ = circle(c)
    assert c.post(URL, {"member_ids": [pia.id]}, user=olga).status == 400
    assert_nothing_created(c)


@pytest.mark.parametrize("body", [["Ski", [2]], "Ski", None, 5])
def test_body_must_be_an_object(body: object) -> None:
    c = Client()
    olga, _, _ = circle(c)
    assert c.post(URL, body, user=olga).status == 400
    assert_nothing_created(c)


@pytest.mark.parametrize(
    "relation", ["stranger", "request_sent", "request_received", "unfriended", "friend_of_friend"]
)
@pytest.mark.parametrize("after_a_friend", [False, True])
def test_member_who_is_not_my_friend_is_403(relation: str, after_a_friend: bool) -> None:
    c = Client()
    olga, (pia, rui, *_), xavi = circle(c)
    if relation == "request_sent":
        c.friend_request(olga, xavi)
    elif relation == "request_received":
        c.friend_request(xavi, olga)
    elif relation == "unfriended":
        c.befriend(olga, xavi)
        c.unfriend(xavi, olga)
    elif relation == "friend_of_friend":
        c.befriend(xavi, pia)
        c.befriend(xavi, rui)
    ids = [pia.id, xavi.id] if after_a_friend else [xavi.id]
    assert c.post(URL, {"title": "Nope", "member_ids": ids}, user=olga).status == 403
    assert_nothing_created(c)


@pytest.mark.parametrize("unknown", [999, 8, 12345678, 2**62])
@pytest.mark.parametrize("after_a_friend", [False, True])
def test_unknown_member_is_404(unknown: int, after_a_friend: bool) -> None:
    c = Client()
    olga, (pia, *_), _ = circle(c)
    ids = [pia.id, unknown] if after_a_friend else [unknown]
    assert c.post(URL, {"title": "Ghosts", "member_ids": ids}, user=olga).status == 404
    assert_nothing_created(c)


@pytest.mark.parametrize(
    ("order", "status"),
    [
        (["stranger", "unknown"], 403),
        (["unknown", "stranger"], 404),
        (["friend", "stranger", "unknown"], 403),
        (["friend", "unknown", "stranger"], 404),
        (["stranger", "friend", "unknown", "stranger"], 403),
    ],
)
def test_members_are_checked_one_by_one_in_list_order(order: list[str], status: int) -> None:
    c = Client()
    olga, (pia, *_), xavi = circle(c)
    by_name = {"stranger": xavi.id, "unknown": 777, "friend": pia.id}
    body = {"title": "Order", "member_ids": [by_name[n] for n in order]}
    assert c.post(URL, body, user=olga).status == status
    assert_nothing_created(c)


def test_member_count_is_checked_before_the_users() -> None:
    c = Client()
    olga, _, _ = circle(c)
    ids = list(range(1000, 1050))
    assert c.post(URL, {"title": "Crowd", "member_ids": ids}, user=olga).status == 400
    assert_nothing_created(c)


@pytest.mark.parametrize("who", ["stranger", "unknown"])
def test_title_is_checked_before_the_members(who: str) -> None:
    c = Client()
    olga, _, xavi = circle(c)
    uid = xavi.id if who == "stranger" else 555
    assert c.post(URL, {"title": "  ", "member_ids": [uid]}, user=olga).status == 400
    assert_nothing_created(c)


# -- PUT /api/groups/{id} -----------------------------------------------------------------


def test_member_renames_the_group() -> None:
    c = Client()
    pia, olga, rui, *_ = cast(c)
    c.befriend(olga, pia)
    c.befriend(olga, rui)
    c.dm(olga, pia)
    born = c.now
    g = c.group(olga, [rui, pia], "Old name")
    c.tick(60_000)
    r = c.put(f"{URL}/{g}", {"title": "  Lunch   club "}, user=rui)
    assert r.status == 200
    assert r.json == {"conversation": group_json(g, "Lunch   club", [pia, olga, rui], born)}
    assert c.row("SELECT title FROM conversations WHERE id = ?", g) == {"title": "Lunch   club"}


@pytest.mark.parametrize("title", ["n" * 50, "Old name", "A"])
def test_creator_can_rename_too(title: str) -> None:
    c = Client()
    olga, (pia, rui, *_), _ = circle(c)
    born = c.now
    g = c.group(olga, [pia, rui], "Old name")
    c.tick(7)
    r = c.put(f"{URL}/{g}", {"title": title}, user=olga)
    assert r.status == 200
    assert r.json == {"conversation": group_json(g, title, [olga, pia, rui], born)}
    assert c.row("SELECT title FROM conversations WHERE id = ?", g) == {"title": title}


def test_rename_answer_is_the_group_as_the_renamer_sees_it() -> None:
    c = Client()
    olga, (pia, rui, *_), _ = circle(c)
    g = c.group(olga, [pia, rui], "Plans")
    c.tick(10)
    c.send(olga, g, "first")
    c.tick(10)
    last = c.send(rui, g, "second")
    sent_at = c.now
    c.tick(10)
    r = c.put(f"{URL}/{g}", {"title": "Plans B"}, user=pia)
    assert r.status == 200
    expected = group_json(g, "Plans B", [olga, pia, rui], sent_at, last=c.message(last), unread=2)
    assert r.json == {"conversation": expected}
    assert r.json["conversation"] == c.conversation(g, pia)
    r = c.put(f"{URL}/{g}", {"title": "Plans C"}, user=olga)
    assert r.status == 200
    assert r.json["conversation"]["unread"] == 1
    assert r.json["conversation"] == c.conversation(g, olga)
    assert r.json["conversation"]["title"] == "Plans C"


def test_rename_changes_only_that_title() -> None:
    c = Client()
    olga, (pia, rui, sia, *_), _ = circle(c)
    dm = c.dm(olga, sia)
    g1 = c.group(olga, [pia, rui], "First")
    g2 = c.group(olga, [pia, sia], "Second")
    c.send(pia, g1, "hey")
    c.send(sia, dm, "yo")
    before_conv = c.rows("SELECT * FROM conversations ORDER BY id")
    before_members = c.rows("SELECT * FROM members ORDER BY conversation_id, user_id")
    before_messages = c.rows("SELECT * FROM messages ORDER BY id")
    c.tick(99)
    assert c.put(f"{URL}/{g1}", {"title": "Renamed"}, user=pia).status == 200
    after_conv = c.rows("SELECT * FROM conversations ORDER BY id")
    assert after_conv == [
        row | {"title": "Renamed"} if row["id"] == g1 else row for row in before_conv
    ]
    assert c.row("SELECT title FROM conversations WHERE id = ?", g2) == {"title": "Second"}
    assert c.rows("SELECT * FROM members ORDER BY conversation_id, user_id") == before_members
    assert c.rows("SELECT * FROM messages ORDER BY id") == before_messages


@pytest.mark.parametrize("raw", ["999", "abc", "0", "-1", "1.5", "3x"])
def test_rename_bad_or_unknown_id_is_404(raw: str) -> None:
    c = Client()
    olga, (pia, *_), _ = circle(c)
    g = c.group(olga, [pia], "Keep")
    assert c.put(f"{URL}/{raw}", {"title": "Changed"}, user=olga).status == 404
    assert c.row("SELECT title FROM conversations WHERE id = ?", g) == {"title": "Keep"}


@pytest.mark.parametrize("who", ["stranger", "creators_friend", "left"])
def test_rename_by_a_non_member_is_404(who: str) -> None:
    c = Client()
    olga, (pia, rui, sia, *_), xavi = circle(c)
    g = c.group(olga, [pia, rui], "Keep")
    if who == "left":
        c.leave(rui, g)
    user = {"stranger": xavi, "creators_friend": sia, "left": rui}[who]
    assert c.put(f"{URL}/{g}", {"title": "Mine now"}, user=user).status == 404
    assert c.row("SELECT title FROM conversations WHERE id = ?", g) == {"title": "Keep"}


def test_renaming_a_direct_conversation_is_400() -> None:
    c = Client()
    olga, (pia, *_), _ = circle(c)
    c.group(olga, [pia], "Group first")
    dm = c.dm(pia, olga)
    for user in (olga, pia):
        assert c.put(f"{URL}/{dm}", {"title": "Besties"}, user=user).status == 400
    assert c.row("SELECT kind, title FROM conversations WHERE id = ?", dm) == {
        "kind": "direct",
        "title": "",
    }


@pytest.mark.parametrize(
    "body",
    [
        {"title": ""},
        {"title": "   "},
        {"title": "n" * 51},
        {"title": 12},
        {"title": None},
        {"name": "New"},
        ["New"],
    ],
)
def test_rename_bad_title_is_400(body: object) -> None:
    c = Client()
    olga, (pia, *_), _ = circle(c)
    g = c.group(olga, [pia], "Keep")
    assert c.put(f"{URL}/{g}", body, user=pia).status == 400
    assert c.row("SELECT title FROM conversations WHERE id = ?", g) == {"title": "Keep"}


@pytest.mark.parametrize(
    ("target", "title"), [("group", ""), ("group", "x" * 60), ("direct", "Fine title")]
)
def test_rename_checks_membership_first(target: str, title: str) -> None:
    c = Client()
    olga, (pia, rui, *_), xavi = circle(c)
    g = c.group(olga, [pia], "Keep")
    dm = c.dm(olga, rui)
    cid = g if target == "group" else dm
    assert c.put(f"{URL}/{cid}", {"title": title}, user=xavi).status == 404
    assert c.row("SELECT title FROM conversations WHERE id = ?", g) == {"title": "Keep"}


def test_lives_in_its_own_feature_folder() -> None:
    importlib.import_module("chatbook.features.groups.handler")
