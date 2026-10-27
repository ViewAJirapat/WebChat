import importlib

import pytest

from chatbook.testing import Account, Client

URL = "/api/friends/suggestions"
PALS = ["pal_k", "pal_l", "pal_m", "pal_n", "pal_o"]


def sug(person: Account, mutual: int) -> dict[str, object]:
    return person.json | {"mutual": mutual}


def suggestions(c: Client, who: Account) -> list[dict[str, object]]:
    r = c.get(URL, user=who)
    assert r.status == 200
    assert set(r.json) == {"suggestions"}
    found: list[dict[str, object]] = r.json["suggestions"]
    return found


def befriend_all(c: Client, person: Account, others: list[Account]) -> None:
    for other in others:
        c.befriend(person, other)


def small_town(c: Client) -> dict[str, Account]:
    """hana's friends are ivo and jude. Ids, usernames and display names sort differently."""
    t = {
        "hana": c.user("hana", "Hana Hart"),
        "ivo": c.user("ivo", "Ivo Isle"),
        "jude": c.user("jude", "Jude Jett"),
        "tia": c.user("tia", "Ann Tia"),  # friend of ivo; hana asked tia
        "sol": c.user("sol", "Bo Sol"),  # friend of ivo only
        "rex": c.user("rex", "Cy Rex"),  # friend of ivo and jude
    }
    c.befriend(t["hana"], t["jude"])
    c.befriend(t["ivo"], t["hana"])
    c.befriend(t["jude"], t["rex"])
    c.befriend(t["ivo"], t["sol"])
    c.befriend(t["rex"], t["ivo"])
    c.befriend(t["tia"], t["ivo"])
    c.friend_request(t["hana"], t["tia"])
    return t


def test_friends_of_friends_ranked_by_mutual_friends() -> None:
    c = Client()
    t = small_town(c)
    r = c.get(URL, user=t["hana"])
    assert r.status == 200
    assert r.json == {"suggestions": [sug(t["rex"], 2), sug(t["sol"], 1)]}
    assert all(type(s["mutual"]) is int for s in r.json["suggestions"])


def test_suggestions_are_seen_from_the_viewer() -> None:
    c = Client()
    t = small_town(c)
    assert suggestions(c, t["rex"]) == [sug(t["hana"], 2), sug(t["sol"], 1), sug(t["tia"], 1)]
    # tia has a request from hana: left out from tia's side too
    assert suggestions(c, t["tia"]) == [sug(t["rex"], 1), sug(t["sol"], 1)]
    assert suggestions(c, t["sol"]) == [sug(t["hana"], 1), sug(t["rex"], 1), sug(t["tia"], 1)]
    assert suggestions(c, t["ivo"]) == [sug(t["jude"], 2)]
    assert suggestions(c, t["jude"]) == [sug(t["ivo"], 2)]


def ranked_world(c: Client, cands: list[tuple[str, int]]) -> tuple[Account, dict[str, Account]]:
    """wren has five friends (PALS); each candidate is a friend of the first `mutual` pals.
    Display names sort in reverse id order, usernames in neither id nor reverse id order."""
    wren = c.user("wren", "Wren Wolfe")
    pals = [c.user(p, "Pal " + p[-1].upper()) for p in PALS]
    for pal in reversed(pals):
        c.befriend(wren, pal)
    people: dict[str, Account] = {}
    for i, (name, mutual) in enumerate(cands):
        person = c.user(name, chr(ord("Z") - i) + " " + name.capitalize())
        befriend_all(c, person, pals[:mutual])
        people[name] = person
    return wren, people


@pytest.mark.parametrize(
    ("cands", "order"),
    [
        ([("zora", 3), ("abby", 1), ("kurt", 2)], ["zora", "kurt", "abby"]),
        (
            [("mona", 2), ("dirk", 1), ("bess", 2), ("yuri", 1), ("cole", 5)],
            ["cole", "bess", "mona", "dirk", "yuri"],
        ),
        ([("lena", 1), ("leo", 1), ("lea", 1), ("len", 1)], ["lea", "len", "lena", "leo"]),
        ([("tom", 4), ("ugo", 4), ("sam", 4)], ["sam", "tom", "ugo"]),
        ([("gil", 1), ("fern", 4), ("hal", 3), ("ezra", 3)], ["fern", "ezra", "hal", "gil"]),
    ],
)
def test_order_is_mutual_descending_then_username(
    cands: list[tuple[str, int]], order: list[str]
) -> None:
    c = Client()
    wren, people = ranked_world(c, cands)
    mutual = dict(cands)
    assert suggestions(c, wren) == [sug(people[n], mutual[n]) for n in order]


NAMES = ["gus", "ada", "lev", "bea", "nia", "cal", "oto", "dex", "pam", "eve", "quin", "fox"]


@pytest.mark.parametrize("n", [1, 9, 10, 11, 12])
def test_at_most_ten_by_username(n: int) -> None:
    c = Client()
    me = c.user("yves", "Yves Young")
    pal = c.user("pal_q", "Pal Q")
    c.befriend(me, pal)
    people = [c.user(name, "Zz " + name) for name in NAMES[:n]]
    befriend_all(c, pal, people)
    expected = sorted(people, key=lambda p: p.username)[:10]
    assert suggestions(c, me) == [sug(p, 1) for p in expected]


def test_filter_and_sort_come_before_the_cut() -> None:
    c = Client()
    me = c.user("yves", "Yves Young")
    pal1 = c.user("pal_r", "Pal R")
    pal2 = c.user("pal_s", "Pal S")
    befriend_all(c, me, [pal1, pal2])
    ones = [c.user(name, "Zz " + name) for name in NAMES]  # 12 people, 1 mutual each
    befriend_all(c, pal1, ones)
    zack = c.user("zack", "Zack Zed")  # 2 mutual, last username
    befriend_all(c, zack, [pal1, pal2])
    asked = c.user("aaron", "Aaron Ash")  # 2 mutual, I asked him
    befriend_all(c, asked, [pal1, pal2])
    c.friend_request(me, asked)
    asker = c.user("abe", "Abe Ames")  # 2 mutual, he asked me
    befriend_all(c, asker, [pal2, pal1])
    c.friend_request(asker, me)
    mate = c.user("aby", "Aby Ash")  # my friend and a friend of both pals
    befriend_all(c, mate, [pal1, pal2, me])
    expected = [sug(zack, 2)] + [sug(p, 1) for p in sorted(ones, key=lambda p: p.username)[:9]]
    assert suggestions(c, me) == expected


@pytest.mark.parametrize(
    ("link", "expected"),
    [
        ("none", ["abel", "zeke"]),
        ("friends", ["zeke"]),
        ("request_sent", ["zeke"]),
        ("request_received", ["zeke"]),
    ],
)
def test_people_i_already_know_are_left_out(link: str, expected: list[str]) -> None:
    c = Client()
    me = c.user("gina", "Gina Gold")
    pal1 = c.user("hugo", "Hugo Hale")
    pal2 = c.user("iris", "Iris Ito")
    zeke = c.user("zeke", "Zeke Zorn")  # 1 mutual
    abel = c.user("abel", "Abel Ames")  # 2 mutual
    befriend_all(c, me, [pal1, pal2])
    befriend_all(c, abel, [pal1, pal2])
    c.befriend(pal1, zeke)
    if link == "friends":
        c.befriend(me, abel)
    elif link == "request_sent":
        c.friend_request(me, abel)
    elif link == "request_received":
        c.friend_request(abel, me)
    found = suggestions(c, me)
    assert [s["username"] for s in found] == expected
    assert found[-1] == sug(zeke, 1)
    if link == "none":
        assert found[0] == sug(abel, 2)


def test_only_friendships_of_my_friends_count() -> None:
    c = Client()
    me = c.user("nadia", "Nadia North")
    pal = c.user("oscar", "Oscar Oak")
    fof = c.user("pia_b", "Pia Bell")
    asked = c.user("ari", "Ari Ames")  # my friend asked ari: a request, not a friendship
    asker = c.user("bo", "Bo Bay")  # bo asked my friend
    far = c.user("cid", "Cid Cole")  # friend of a friend of a friend
    c.user("dot", "Dot Dee")  # a stranger
    c.befriend(me, pal)
    c.befriend(pal, fof)
    c.befriend(fof, far)
    c.friend_request(pal, asked)
    c.friend_request(asker, pal)
    assert suggestions(c, me) == [sug(fof, 1)]


def test_counts_follow_current_friendships() -> None:
    c = Client()
    me = c.user("nell", "Nell Nash")
    pal1 = c.user("otis", "Otis Ord")
    pal2 = c.user("pearl", "Pearl Pratt")
    cand = c.user("quinn", "Quinn Quill")
    befriend_all(c, me, [pal1, pal2])
    befriend_all(c, cand, [pal1, pal2])
    assert suggestions(c, me) == [sug(cand, 2)]
    c.unfriend(pal2, cand)
    assert suggestions(c, me) == [sug(cand, 1)]
    c.befriend(me, cand)
    assert suggestions(c, me) == []
    c.unfriend(me, pal1)  # pal1 is now a friend of my friend cand only
    assert suggestions(c, me) == [sug(pal1, 1)]


def test_reading_suggestions_changes_nothing() -> None:
    c = Client()
    t = small_town(c)
    c.friend_request(t["sol"], t["jude"])
    friendships = "SELECT * FROM friendships ORDER BY user_id, friend_id"
    requests = "SELECT * FROM friend_requests ORDER BY id"
    before = (c.rows(friendships), c.rows(requests))
    for who in t.values():
        suggestions(c, who)
    assert (c.rows(friendships), c.rows(requests)) == before
    assert len(before[0]) == 12 and len(before[1]) == 2


def test_nobody_to_suggest() -> None:
    c = Client()
    lone = c.user("lone", "Lone Lark")
    r = c.get(URL, user=lone)
    assert (r.status, r.json) == (200, {"suggestions": []})
    pair_a = c.user("pair_a", "Pair A")
    pair_b = c.user("pair_b", "Pair B")
    c.befriend(pair_a, pair_b)
    assert suggestions(c, pair_a) == []
    assert suggestions(c, lone) == []


def test_login_required() -> None:
    c = Client()
    c.user("vera", "Vera Vale")
    assert c.get(URL).status == 401


def test_lives_in_its_own_feature_folder() -> None:
    importlib.import_module("chatbook.features.suggestions.handler")
