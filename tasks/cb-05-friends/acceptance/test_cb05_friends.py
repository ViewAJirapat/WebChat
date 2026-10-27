import importlib

import pytest

from chatbook.testing import Account, Client


def make_friends(c: Client, me: Account, names: list[str]) -> list[Account]:
    """Users with these display names, created in this order. Usernames run backwards
    (userz, usery, ...), so username order is the reverse of id order."""
    people = [c.user("user" + chr(ord("z") - i), name) for i, name in enumerate(names)]
    for person in reversed(people):  # friendship order differs from id order
        c.befriend(me, person)
    return people


def test_list_sorts_by_display_name_ignoring_case_ties_by_id() -> None:
    c = Client()
    me = c.user("mira", "Mira Moss")
    bob = c.user("bob", "bob")
    ann1 = c.user("ann1", "Ann")
    ann2 = c.user("ann2", "ann")
    c.befriend(me, ann2)
    c.befriend(me, bob)
    c.befriend(me, ann1)
    r = c.get("/api/friends", user=me)
    assert r.status == 200
    assert r.json == {"friends": [ann1.json, ann2.json, bob.json]}


@pytest.mark.parametrize(
    ("names", "order"),
    [
        (["ann", "Ann", "bob"], [0, 1, 2]),
        (["Carl", "alma", "Bea"], [1, 2, 0]),
        (["Kim Lee", "kim lee", "KIM LEE", "Jo"], [3, 0, 1, 2]),
        (["Dana", "dan", "DAN", "Dan Ray"], [1, 2, 3, 0]),
        (["Omar", "Nell", "Lars", "Pia", "Hugo"], [4, 2, 1, 0, 3]),
        (["Vic", "Uma"], [1, 0]),
    ],
)
def test_list_order(names: list[str], order: list[int]) -> None:
    c = Client()
    me = c.user("host", "Host Person")
    people = make_friends(c, me, names)
    r = c.get("/api/friends", user=me)
    assert r.status == 200
    assert r.json == {"friends": [people[i].json for i in order]}


def test_list_holds_only_my_friends() -> None:
    c = Client()
    me = c.user("gwen", "Gwen Gray")
    pal = c.user("pal", "Pal Pine")
    asked = c.user("asked", "Asked Ash")
    asker = c.user("asker", "Asker Ames")
    other1 = c.user("other1", "Other One")
    other2 = c.user("other2", "Other Two")
    gone = c.user("gone", "Gone Gale")
    c.befriend(me, pal)
    c.friend_request(me, asked)
    c.friend_request(asker, me)
    c.befriend(other1, other2)
    c.befriend(pal, other1)
    c.befriend(gone, me)
    c.unfriend(me, gone)
    r = c.get("/api/friends", user=me)
    assert (r.status, r.json) == (200, {"friends": [pal.json]})


def test_friendship_shows_on_both_sides() -> None:
    c = Client()
    rex = c.user("rex", "Rex Reed")
    sue = c.user("sue", "Sue Sato")
    c.befriend(sue, rex)
    assert c.get("/api/friends", user=rex).json == {"friends": [sue.json]}
    assert c.get("/api/friends", user=sue).json == {"friends": [rex.json]}


def test_list_items_are_only_user_fields() -> None:
    c = Client()
    me = c.user("ivy", "Ivy Ito")
    pal = c.user("jon", "Jon Jung")
    c.db.run("UPDATE users SET bio = ? WHERE id = ?", "Loves hiking", pal.id)
    c.touch(pal)
    c.befriend(me, pal)
    r = c.get("/api/friends", user=me)
    assert r.status == 200
    assert r.json == {"friends": [{"id": pal.id, "username": "jon", "display_name": "Jon Jung"}]}


def test_user_without_friends_gets_empty_list() -> None:
    c = Client()
    x = c.user("xena", "Xena X")
    y = c.user("yuri", "Yuri Y")
    lonely = c.user("lonely", "Lonely L")
    c.befriend(x, y)
    c.friend_request(lonely, x)
    r = c.get("/api/friends", user=lonely)
    assert (r.status, r.json) == (200, {"friends": []})


def test_unfriend_removes_both_directions_only_for_the_pair() -> None:
    c = Client()
    filler = c.user("filler", "Filler F")
    me = c.user("tess", "Tess Tran")
    pal = c.user("pal", "Pal Park")
    carl = c.user("carl", "Carl Cho")
    dora = c.user("dora", "Dora Diaz")
    c.befriend(me, pal)
    c.befriend(me, carl)
    c.befriend(pal, dora)
    c.befriend(filler, carl)
    r = c.delete(f"/api/friends/{pal.id}", user=me)
    assert (r.status, r.json) == (200, {"removed": pal.id})
    assert not c.are_friends(me, pal)
    assert not c.are_friends(pal, me)
    pair = c.rows(
        "SELECT * FROM friendships WHERE user_id IN (?, ?) AND friend_id IN (?, ?)",
        me.id,
        pal.id,
        me.id,
        pal.id,
    )
    assert pair == []
    assert c.are_friends(me, carl) and c.are_friends(carl, me)
    assert c.are_friends(pal, dora) and c.are_friends(dora, pal)
    assert c.are_friends(filler, carl)
    assert c.get("/api/friends", user=me).json == {"friends": [carl.json]}
    assert c.get("/api/friends", user=pal).json == {"friends": [dora.json]}


def test_either_friend_can_unfriend() -> None:
    c = Client()
    for name in ["pad1", "pad2", "pad3"]:
        c.user(name)
    kai = c.user("kai", "Kai Kent")
    lea = c.user("lea", "Lea Lund")
    c.befriend(kai, lea)
    r = c.delete(f"/api/friends/{kai.id}", user=lea)
    assert (r.status, r.json) == (200, {"removed": kai.id})
    assert not c.are_friends(kai, lea) and not c.are_friends(lea, kai)
    assert c.get("/api/friends", user=kai).json == {"friends": []}


def test_second_unfriend_is_404() -> None:
    c = Client()
    me = c.user("nina", "Nina Novak")
    pal = c.user("otto", "Otto Olsen")
    c.befriend(me, pal)
    assert c.delete(f"/api/friends/{pal.id}", user=me).status == 200
    r = c.delete(f"/api/friends/{pal.id}", user=me)
    assert r.status == 404
    assert not c.are_friends(me, pal)


@pytest.mark.parametrize("raw", ["987", "x", "0", "-2", "1.5", "4abc"])
def test_unfriend_bad_or_unknown_id_is_404(raw: str) -> None:
    c = Client()
    me = c.user("quinn", "Quinn Q")
    pal = c.user("rosa", "Rosa R")
    c.befriend(me, pal)
    assert c.delete(f"/api/friends/{raw}", user=me).status == 404
    assert c.are_friends(me, pal) and c.are_friends(pal, me)


def test_unfriend_non_friend_is_404_and_changes_nothing() -> None:
    c = Client()
    me = c.user("sam", "Sam Stone")
    stranger = c.user("stranger", "Stranger S")
    pal = c.user("pal", "Pal P")
    c.befriend(stranger, pal)
    c.befriend(me, pal)
    assert c.delete(f"/api/friends/{stranger.id}", user=me).status == 404
    assert c.are_friends(stranger, pal) and c.are_friends(me, pal)


@pytest.mark.parametrize("outgoing", [True, False])
def test_pending_request_is_not_a_friendship(outgoing: bool) -> None:
    c = Client()
    me = c.user("uli", "Uli Umber")
    other = c.user("vera", "Vera Voss")
    rid = c.friend_request(me, other) if outgoing else c.friend_request(other, me)
    assert c.delete(f"/api/friends/{other.id}", user=me).status == 404
    assert c.row("SELECT id FROM friend_requests WHERE id = ?", rid) == {"id": rid}


def test_unfriend_myself_is_404() -> None:
    c = Client()
    c.user("first", "First F")
    me = c.user("wade", "Wade West")
    pal = c.user("pal", "Pal Pratt")
    c.befriend(me, pal)
    assert c.delete(f"/api/friends/{me.id}", user=me).status == 404
    assert c.are_friends(me, pal)


def test_lives_in_its_own_feature_folder() -> None:
    importlib.import_module("chatbook.features.friends.handler")
