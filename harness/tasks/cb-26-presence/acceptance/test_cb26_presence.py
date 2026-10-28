import importlib

import pytest

from chatbook.testing import Account, Client

URL = "/api/friends/online"


def expect_online(c: Client, viewer: Account, expected: list[Account]) -> None:
    """GET /api/friends/online as `viewer` must answer 200 with exactly these users, in order."""
    r = c.get(URL, user=viewer)
    assert r.status == 200
    assert r.json == {"online": [u.json for u in expected]}


def people(c: Client, names: list[str]) -> list[Account]:
    """Users with these display names, created in this order. Usernames run backwards
    (userz, usery, ...), so username order is the reverse of id order."""
    return [c.user("user" + chr(ord("z") - i), name) for i, name in enumerate(names)]


# -- who counts as online ------------------------------------------------------------------


def test_friends_seen_in_the_last_minute_slide_out_of_the_list() -> None:
    c = Client()
    host = c.user("hana", "Hana Holm")
    zoe = c.user("zoe", "Zoe")
    bea = c.user("bea", "Bea")
    xan = c.user("xan", "Xan")  # online, but not a friend
    c.befriend(host, zoe)
    c.befriend(host, bea)
    c.touch(zoe)
    c.touch(xan)
    c.tick(30_000)
    c.touch(bea)
    expect_online(c, host, [bea, zoe])
    c.tick(31_000)  # zoe last seen 61000 ms ago, bea 31000 ms ago
    expect_online(c, host, [bea])
    c.tick(60_000)  # bea last seen 91000 ms ago
    expect_online(c, host, [])


@pytest.mark.parametrize(
    ("age_ms", "shown"),
    [
        (0, True),
        (1, True),
        (45_000, True),
        (59_999, True),
        (60_000, True),
        (60_001, False),
        (60_002, False),
        (90_000, False),
        (3_600_000, False),
    ],
)
def test_window_is_sixty_seconds_inclusive(age_ms: int, shown: bool) -> None:
    c = Client()
    me = c.user("ines", "Ines Ito")
    pal = c.user("jack", "Jack Jones")
    c.befriend(me, pal)
    c.touch(pal)
    c.tick(age_ms)
    expect_online(c, me, [pal] if shown else [])


def test_exactly_sixty_seconds_counts_one_more_millisecond_does_not() -> None:
    c = Client()
    me = c.user("olga", "Olga Ortiz")
    late = c.user("abby", "Abby Ames")
    edge = c.user("yves", "Yves Young")
    c.befriend(me, late)
    c.befriend(me, edge)
    c.touch(late)
    c.tick(1)
    c.touch(edge)
    c.tick(60_000)  # edge seen exactly 60000 ms ago, late 60001 ms ago
    expect_online(c, me, [edge])


def test_friends_never_seen_are_offline() -> None:
    c = Client()
    me = c.user("pia", "Pia Pratt")
    quiet = c.user("quiet", "Quinn Quiet")
    shy = c.user("shy", "Shay Shore")
    seen = c.user("seen", "Seth Seen")
    for pal in (quiet, shy, seen):
        c.befriend(me, pal)
    c.tick(5_000)
    c.touch(seen)
    expect_online(c, me, [seen])


def test_any_logged_in_request_marks_a_friend_online() -> None:
    c = Client()
    me = c.user("kara", "Kara Kent")
    pal = c.user("liam", "Liam Lund")
    c.befriend(me, pal)
    expect_online(c, me, [])  # my own request marks only me
    c.tick(5_000)
    assert c.get("/api/session", user=pal).status == 200
    c.tick(5_000)
    expect_online(c, me, [pal])
    expect_online(c, pal, [me])  # my request 0 ms ago
    c.tick(60_001)  # pal's last request was 60001 ms ago
    expect_online(c, me, [])
    expect_online(c, pal, [me])


def test_friendship_age_does_not_matter_only_last_seen() -> None:
    c = Client()
    me = c.user("nell", "Nell Nash")
    pal = c.user("otis", "Otis Oak")
    c.touch(pal)
    c.tick(50_000)
    c.befriend(me, pal)  # a brand-new friendship, pal seen 50000 ms ago
    expect_online(c, me, [pal])
    c.tick(10_001)
    expect_online(c, me, [])


def test_only_current_friends_are_listed() -> None:
    c = Client()
    me = c.user("mona", "Mona Mills")
    pal = c.user("pal", "Pal Price")
    asked = c.user("asked", "Asked Ames")
    asker = c.user("asker", "Asker Ash")
    fof = c.user("fof", "Fof Ford")
    gone = c.user("gone", "Gone Gale")
    stranger = c.user("stranger", "Stranger Stone")
    other = c.user("other", "Other Owens")
    c.befriend(me, pal)
    c.friend_request(me, asked)
    c.friend_request(asker, me)
    c.befriend(pal, fof)
    c.befriend(gone, me)
    c.unfriend(me, gone)
    c.befriend(stranger, other)
    for u in (me, pal, asked, asker, fof, gone, stranger, other):
        c.touch(u)
    expect_online(c, me, [pal])


def test_each_viewer_sees_only_their_own_friends() -> None:
    c = Client()
    ruth = c.user("ruth", "Ruth Rao")
    saul = c.user("saul", "Saul Sims")
    tina = c.user("tina", "Tina Tam")
    umar = c.user("umar", "Umar Uddin")
    c.befriend(ruth, saul)
    c.befriend(ruth, tina)
    c.befriend(umar, saul)
    for u in (ruth, saul, tina, umar):
        c.touch(u)
    expect_online(c, ruth, [saul, tina])
    expect_online(c, umar, [saul])
    expect_online(c, saul, [ruth, umar])
    expect_online(c, tina, [ruth])


def test_lonely_user_gets_empty_list() -> None:
    c = Client()
    a = c.user("vera", "Vera Vale")
    b = c.user("walt", "Walt Webb")
    lonely = c.user("lonely", "Lonny Lone")
    c.befriend(a, b)
    c.friend_request(lonely, a)
    c.touch(a)
    c.touch(b)
    expect_online(c, lonely, [])


def test_all_friends_offline_gives_empty_list() -> None:
    c = Client()
    me = c.user("gina", "Gina Gold")
    pals = people(c, ["Hank", "Ivy", "Jules"])
    for pal in pals:
        c.befriend(me, pal)
        c.touch(pal)
    c.tick(60_001)
    expect_online(c, me, [])


# -- shape and order -----------------------------------------------------------------------


def test_items_are_only_user_fields() -> None:
    c = Client()
    me = c.user("ivy", "Ivy Ito")
    pal = c.user("jon", "Jon Jung")
    c.db.run("UPDATE users SET bio = ? WHERE id = ?", "Loves hiking", pal.id)
    c.befriend(me, pal)
    c.touch(pal)
    r = c.get(URL, user=me)
    assert r.status == 200
    assert r.json == {"online": [{"id": pal.id, "username": "jon", "display_name": "Jon Jung"}]}


@pytest.mark.parametrize(
    ("names", "order"),
    [
        (["Yara", "abe", "Moe"], [1, 2, 0]),
        (["dee", "Dee", "DEE"], [0, 1, 2]),
        (["Rui Sol", "rui", "RUI", "Pam"], [3, 1, 2, 0]),
        (["Lou", "Ivo", "Gus", "Hal", "Eli"], [4, 2, 3, 1, 0]),
        (["bo-ray", "Bo Ray", "Boray"], [1, 0, 2]),
        (["Zed2", "zed10", "Zed1"], [2, 1, 0]),
        (["Uma", "tia"], [1, 0]),
    ],
)
def test_order_is_display_name_ignoring_case_then_id(names: list[str], order: list[int]) -> None:
    c = Client()
    me = c.user("host", "Host Person")
    pals = people(c, names)
    for pal in reversed(pals):  # friendship order differs from id order
        c.befriend(me, pal)
    c.tick(2_000)
    for pal in pals:
        c.touch(pal)
    expect_online(c, me, [pals[i] for i in order])


def test_many_friends_all_online_ones_listed_in_order() -> None:
    c = Client()
    me = c.user("boss", "Boss Bell")
    names = [
        "Opal",
        "nico",
        "Lars",
        "kai",
        "Jude",
        "iris",
        "Hugo",
        "gwen",
        "Faye",
        "eddy",
        "Dora",
        "cole",
        "Bram",
        "ayla",
        "Pia",
    ]
    pals = people(c, names)
    for pal in pals:
        c.befriend(me, pal)
    away = {2, 7, 11}  # Lars, gwen, cole
    for i in sorted(away):
        c.touch(pals[i])
    c.tick(60_001)
    for i, pal in enumerate(pals):
        if i not in away:
            c.touch(pal)
    expected = [13, 12, 10, 9, 8, 6, 5, 4, 3, 1, 0, 14]
    assert [pals[i].display_name for i in expected] == [
        "ayla",
        "Bram",
        "Dora",
        "eddy",
        "Faye",
        "Hugo",
        "iris",
        "Jude",
        "kai",
        "nico",
        "Opal",
        "Pia",
    ]
    expect_online(c, me, [pals[i] for i in expected])


def test_listing_writes_nothing() -> None:
    c = Client()
    me = c.user("dina", "Dina Doyle")
    pal = c.user("eli", "Eli Earl")
    asker = c.user("finn", "Finn Fry")
    c.befriend(me, pal)
    c.friend_request(asker, me)
    c.touch(pal)
    c.tick(4_000)
    tables = [
        # every user column except last_seen_at (the app itself updates the viewer's)
        "SELECT id, username, display_name, bio, password_hash, created_at FROM users ORDER BY id",
        "SELECT * FROM friendships ORDER BY user_id, friend_id",
        "SELECT * FROM friend_requests ORDER BY id",
        "SELECT * FROM sessions ORDER BY token_hash",
    ]
    others = "SELECT * FROM users WHERE id != ? ORDER BY id"
    before = [c.rows(sql) for sql in tables] + [c.rows(others, me.id)]
    expect_online(c, me, [pal])
    after = [c.rows(sql) for sql in tables] + [c.rows(others, me.id)]
    assert after == before


def test_lives_in_its_own_feature_folder() -> None:
    importlib.import_module("chatbook.features.presence.handler")
