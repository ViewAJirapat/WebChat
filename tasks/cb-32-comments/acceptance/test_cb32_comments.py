import importlib

import pytest

from chatbook.testing import Account, Client


def cast(c: Client) -> tuple[Account, Account, Account, Account, Account]:
    """dora, finn and gwen are all friends; iris is a friend of gwen only; hugo knows nobody."""
    dora = c.user("dora", "Dora Diaz")
    finn = c.user("finn", "Finn Ford")
    gwen = c.user("gwen", "Gwen Gray")
    hugo = c.user("hugo", "Hugo Hart")
    iris = c.user("iris", "Iris Ito")
    c.befriend(dora, finn)
    c.befriend(finn, gwen)
    c.befriend(dora, gwen)
    c.befriend(gwen, iris)
    return dora, finn, gwen, hugo, iris


def stored(c: Client) -> list[dict[str, object]]:
    return c.rows("SELECT id, post_id, author_id, body, created_at FROM comments ORDER BY id")


def remove(c: Client, who: Account, cid: object) -> tuple[int, object]:
    r = c.delete(f"/api/comments/{cid}", user=who)
    return r.status, r.json


def listing(c: Client, who: Account, pid: int) -> tuple[int, object]:
    r = c.get(f"/api/posts/{pid}/comments", user=who)
    return r.status, r.json


# -- my own comment on a post I can no longer see ----------------------------------------


@pytest.mark.parametrize(
    "side", ["i_unfriend", "they_unfriend"], ids=["i_unfriend", "they_unfriend"]
)
def test_former_friend_deletes_own_comment(side: str) -> None:
    c = Client()
    dora, finn, gwen, *_ = cast(c)
    elsewhere = c.make_post(gwen, "new kayak")
    pid = c.make_post(finn, "lake swim at six")
    c.comment(dora, elsewhere, "take me along")
    c.comment(gwen, pid, "brr")
    typo = c.comment(dora, pid, "so cold?!")
    c.comment(dora, pid, "count me in tomorrow")
    c.comment(finn, pid, "bring a towel")
    if side == "i_unfriend":
        c.unfriend(dora, finn)
    else:
        c.unfriend(finn, dora)
    before = stored(c)
    assert remove(c, dora, typo) == (200, {"deleted": typo})
    assert stored(c) == [r for r in before if r["id"] != typo]
    assert typo == 3
    # the post itself stays hidden: listing its comments is still 404
    assert listing(c, dora, pid)[0] == 404


@pytest.mark.parametrize("who", ["stranger", "friend_of_friend"], ids=["stranger", "fof"])
def test_never_friend_deletes_own_seeded_comment(who: str) -> None:
    c = Client()
    _, finn, gwen, hugo, iris = cast(c)
    pid = c.make_post(finn, "garden tour")
    c.comment(gwen, pid, "roses!")
    actor = {"stranger": hugo, "friend_of_friend": iris}[who]
    cid = c.comment(actor, pid, "how did I get here")
    c.comment(finn, pid, "welcome anyway")
    assert remove(c, actor, cid) == (200, {"deleted": cid})
    assert [r["author_id"] for r in stored(c)] == [gwen.id, finn.id]


def test_own_hidden_comment_deleted_twice() -> None:
    c = Client()
    dora, finn, gwen, *_ = cast(c)
    pid = c.make_post(finn, "harbour lights")
    c.comment(gwen, pid, "stunning")
    mine = c.comment(dora, pid, "next time!")
    c.unfriend(dora, finn)
    assert remove(c, dora, mine) == (200, {"deleted": mine})
    again = remove(c, dora, mine)
    assert again[0] == 404
    assert again == remove(c, dora, 8080)
    assert again == listing(c, dora, pid)
    assert [r["author_id"] for r in stored(c)] == [gwen.id]


# -- someone else's comment on a post I can no longer see ---------------------------------


@pytest.mark.parametrize("target", ["by_friend", "by_post_author"], ids=["friend", "author"])
def test_former_friend_cannot_delete_others_comments(target: str) -> None:
    c = Client()
    dora, finn, gwen, *_ = cast(c)
    pid = c.make_post(finn, "lake swim at six")
    by_gwen = c.comment(gwen, pid, "brr")
    by_finn = c.comment(finn, pid, "bring a towel")
    c.comment(dora, pid, "so cold?!")
    c.unfriend(finn, dora)
    cid = {"by_friend": by_gwen, "by_post_author": by_finn}[target]
    before = stored(c)
    assert remove(c, dora, cid)[0] == 404
    assert stored(c) == before


@pytest.mark.parametrize(
    "who",
    ["stranger", "friend_of_friend", "former_friend"],
    ids=["stranger", "fof", "former_friend"],
)
def test_hidden_and_missing_comments_give_the_same_404(who: str) -> None:
    c = Client()
    dora, finn, gwen, hugo, iris = cast(c)
    pid = c.make_post(finn, "harbour lights")
    hidden = c.comment(gwen, pid, "stunning")
    gone = c.comment(finn, pid, "thanks all")
    c.comment(dora, pid, "wish I was there")
    c.db.run("DELETE FROM comments WHERE id = ?", gone)
    c.unfriend(dora, finn)
    actor = {"stranger": hugo, "friend_of_friend": iris, "former_friend": dora}[who]
    before = stored(c)
    missing = remove(c, actor, 999)
    assert missing[0] == 404
    assert remove(c, actor, hidden) == missing
    assert remove(c, actor, gone) == missing
    # the same body as the 404 that visible_post gives for this hidden post
    assert listing(c, actor, pid) == missing
    assert stored(c) == before


def test_friends_again_gives_403_again() -> None:
    c = Client()
    dora, finn, gwen, *_ = cast(c)
    pid = c.make_post(finn, "harbour lights")
    by_gwen = c.comment(gwen, pid, "stunning")
    mine = c.comment(dora, pid, "next time!")
    c.unfriend(dora, finn)
    before = stored(c)
    assert remove(c, dora, by_gwen)[0] == 404
    c.befriend(finn, dora)
    assert remove(c, dora, by_gwen)[0] == 403
    assert stored(c) == before
    assert remove(c, dora, mine) == (200, {"deleted": mine})
    assert [r["id"] for r in stored(c)] == [by_gwen]


# -- the post's author --------------------------------------------------------------------


def test_post_author_deletes_a_former_friends_comment() -> None:
    c = Client()
    dora, finn, gwen, hugo, _ = cast(c)
    pid = c.make_post(finn, "harbour lights")
    elsewhere = c.make_post(gwen, "night market")
    theirs = c.comment(dora, pid, "meh")
    c.comment(dora, elsewhere, "yum")
    by_hugo = c.comment(hugo, pid, "who are you")
    c.comment(gwen, pid, "stunning")
    c.unfriend(dora, finn)
    assert remove(c, finn, theirs) == (200, {"deleted": theirs})
    assert remove(c, finn, by_hugo) == (200, {"deleted": by_hugo})
    assert [(r["post_id"], r["author_id"]) for r in stored(c)] == [
        (elsewhere, dora.id),
        (pid, gwen.id),
    ]


def test_lives_in_its_own_feature_folder() -> None:
    importlib.import_module("chatbook.features.comments.handler")
