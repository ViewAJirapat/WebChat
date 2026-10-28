import importlib

import pytest

from chatbook.testing import Client


class Cast:
    """gale (1) and hugo (2) are friends until a test unfriends them; hugo wrote the tested
    post (pid) and a second post (p_more); ines (3) and jon (4) are friends of hugo and like
    pid; kit (5) is a friend of ines only; lou (6) knows nobody. ines wrote p_ines."""

    def __init__(self, c: Client) -> None:
        self.gale = c.user("gale", "Gale Grant")
        self.hugo = c.user("hugo", "Hugo Hale")
        self.ines = c.user("ines", "Ines Ito")
        self.jon = c.user("jon", "Jon Jung")
        self.kit = c.user("kit", "Kit Kemp")
        self.lou = c.user("lou", "Lou Lund")
        c.befriend(self.gale, self.hugo)
        c.befriend(self.hugo, self.ines)
        c.befriend(self.hugo, self.jon)
        c.befriend(self.ines, self.kit)
        self.p_ines = c.make_post(self.ines, "ines at the lake")
        self.p_more = c.make_post(self.hugo, "hugo's second post")
        self.pid = c.make_post(self.hugo, "hugo's bike ride")
        c.tick(3000)
        c.like(self.ines, self.pid)
        c.like(self.jon, self.pid)
        c.like(self.jon, self.p_ines)
        c.tick(3000)


def like_url(pid: int) -> str:
    return f"/api/posts/{pid}/like"


def all_likes(c: Client) -> list[dict[str, object]]:
    return c.rows("SELECT post_id, user_id, created_at FROM likes ORDER BY post_id, user_id")


def without(rows: list[dict[str, object]], pid: int, uid: int) -> list[dict[str, object]]:
    return [r for r in rows if (r["post_id"], r["user_id"]) != (pid, uid)]


def hidden(pid: int) -> dict[str, object]:
    return {"post_id": pid, "liked": False}


# -- my own like on a post I can no longer see -------------------------------------------


def test_former_friend_removes_own_like_without_a_count() -> None:
    c = Client()
    s = Cast(c)
    c.like(s.gale, s.pid)
    c.like(s.gale, s.p_more)
    c.unfriend(s.gale, s.hugo)
    before = all_likes(c)
    r = c.delete(like_url(s.pid), user=s.gale)
    assert (r.status, r.json) == (200, hidden(s.pid))
    assert all_likes(c) == without(before, s.pid, s.gale.id)
    assert {"post_id": s.p_more, "user_id": s.gale.id, "created_at": c.now} in all_likes(c)


@pytest.mark.parametrize("mine", [True, False], ids=["i_unfriend", "they_unfriend"])
def test_either_side_may_unfriend(mine: bool) -> None:
    c = Client()
    s = Cast(c)
    c.like(s.gale, s.p_more)
    if mine:
        c.unfriend(s.gale, s.hugo)
    else:
        c.unfriend(s.hugo, s.gale)
    before = all_likes(c)
    r = c.delete(like_url(s.p_more), user=s.gale)
    assert (r.status, r.json) == (200, hidden(s.p_more))
    assert all_likes(c) == without(before, s.p_more, s.gale.id)


@pytest.mark.parametrize("who", ["lou", "kit"], ids=["never_friend", "friend_of_friend"])
def test_seeded_like_of_a_never_friend_is_removed(who: str) -> None:
    c = Client()
    s = Cast(c)
    actor = s.lou if who == "lou" else s.kit
    c.like(actor, s.pid)
    c.like(actor, s.p_more)
    before = all_likes(c)
    r = c.delete(like_url(s.pid), user=actor)
    assert (r.status, r.json) == (200, hidden(s.pid))
    assert all_likes(c) == without(before, s.pid, actor.id)


# -- 404: nothing of mine to remove, the same answer as a missing post --------------------


def test_second_removal_is_the_404_of_a_missing_post() -> None:
    c = Client()
    s = Cast(c)
    c.like(s.gale, s.pid)
    c.like(s.gale, s.p_more)
    c.unfriend(s.gale, s.hugo)
    first = c.delete(like_url(s.pid), user=s.gale)
    assert (first.status, first.json) == (200, hidden(s.pid))
    before = all_likes(c)
    again = c.delete(like_url(s.pid), user=s.gale)
    gone_delete = c.delete(like_url(9999), user=s.gale)
    gone_post = c.post(like_url(9999), user=s.gale)
    assert (again.status, again.json) == (404, gone_post.json)
    assert (again.status, again.json) == (gone_delete.status, gone_delete.json)
    assert all_likes(c) == before


@pytest.mark.parametrize("who", ["lou", "kit", "gale"], ids=["stranger", "fof", "ex_friend"])
def test_hidden_post_without_my_like_is_404(who: str) -> None:
    c = Client()
    s = Cast(c)
    actor = {"lou": s.lou, "kit": s.kit, "gale": s.gale}[who]
    c.like(actor, s.p_more)
    c.unfriend(s.gale, s.hugo)
    before = all_likes(c)
    r = c.delete(like_url(s.pid), user=actor)
    listed = c.get(f"/api/posts/{s.pid}/likes", user=actor)
    gone = c.delete(like_url(9999), user=actor)
    assert (r.status, r.json) == (404, listed.json)
    assert (r.status, r.json) == (gone.status, gone.json)
    assert all_likes(c) == before


@pytest.mark.parametrize(
    ("method", "tail"), [("POST", "like"), ("GET", "likes")], ids=["post", "get"]
)
def test_after_removal_like_and_list_stay_404(method: str, tail: str) -> None:
    c = Client()
    s = Cast(c)
    c.like(s.gale, s.pid)
    c.unfriend(s.hugo, s.gale)
    first = c.delete(like_url(s.pid), user=s.gale)
    assert (first.status, first.json) == (200, hidden(s.pid))
    before = all_likes(c)
    r = c.request(method, f"/api/posts/{s.pid}/{tail}", user=s.gale)
    missing = c.request(method, f"/api/posts/9999/{tail}", user=s.gale)
    assert (r.status, r.json) == (404, missing.json)
    assert all_likes(c) == before


def test_deleted_post_is_404() -> None:
    c = Client()
    s = Cast(c)
    c.like(s.gale, s.pid)
    c.like(s.gale, s.p_ines)
    c.db.run("DELETE FROM likes WHERE post_id = ?", s.pid)
    c.db.run("DELETE FROM posts WHERE id = ?", s.pid)
    before = all_likes(c)
    r = c.delete(like_url(s.pid), user=s.gale)
    gone = c.post(like_url(9999), user=s.gale)
    assert (r.status, r.json) == (404, gone.json)
    assert all_likes(c) == before


# -- a post I can see: unchanged, with the count -------------------------------------------


def test_friends_again_get_the_count() -> None:
    c = Client()
    s = Cast(c)
    c.like(s.gale, s.pid)
    c.unfriend(s.gale, s.hugo)
    c.befriend(s.hugo, s.gale)
    before = all_likes(c)
    r = c.delete(like_url(s.pid), user=s.gale)
    assert (r.status, r.json) == (200, {"post_id": s.pid, "like_count": 2, "liked": False})
    assert all_likes(c) == without(before, s.pid, s.gale.id)
    again = c.delete(like_url(s.pid), user=s.gale)
    assert (again.status, again.json) == (200, {"post_id": s.pid, "like_count": 2, "liked": False})


def test_author_without_friends_unlikes_own_post_with_count() -> None:
    c = Client()
    s = Cast(c)
    own = c.make_post(s.lou, "lou alone")
    c.like(s.lou, own)
    c.like(s.kit, own)
    c.like(s.ines, own)
    before = all_likes(c)
    r = c.delete(like_url(own), user=s.lou)
    assert (r.status, r.json) == (200, {"post_id": own, "like_count": 2, "liked": False})
    assert all_likes(c) == without(before, own, s.lou.id)


def test_lives_in_its_own_feature_folder() -> None:
    importlib.import_module("chatbook.features.likes.handler")
