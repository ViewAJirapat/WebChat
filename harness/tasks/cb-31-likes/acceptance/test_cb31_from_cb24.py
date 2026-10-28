# Carried from cb-24-likes (harness 2ecb8e5). Changed per owner decision 2026-10-28
# (backlog 10a, 11): a former friend may now remove an own like; see test_cb31_likes.py.
import importlib

import pytest

from chatbook.testing import Client


class Cast:
    """quinn (1) and tara (4) are friends of rosa (2); sami (3) is a friend of quinn only;
    uma (5) knows nobody. Posts: quinn's (1), tara's (2), rosa's (3) = the tested post."""

    def __init__(self, c: Client) -> None:
        self.quinn = c.user("quinn", "Quinn Quill")
        self.rosa = c.user("rosa", "Rosa Reyes")
        self.sami = c.user("sami", "Sami Shah")
        self.tara = c.user("tara", "Tara Tran")
        self.uma = c.user("uma", "Uma Ueda")
        c.befriend(self.quinn, self.rosa)
        c.befriend(self.rosa, self.tara)
        c.befriend(self.quinn, self.sami)
        self.p_quinn = c.make_post(self.quinn, "quinn's thoughts")
        self.p_tara = c.make_post(self.tara, "tara's garden")
        self.pid = c.make_post(self.rosa, "rosa's trip photos")
        c.tick(4000)


def like_url(pid: int | str) -> str:
    return f"/api/posts/{pid}/like"


def likes_url(pid: int | str) -> str:
    return f"/api/posts/{pid}/likes"


def like_rows(c: Client, pid: int) -> list[dict[str, object]]:
    return c.rows(
        "SELECT post_id, user_id, created_at FROM likes WHERE post_id = ? ORDER BY user_id", pid
    )


def all_likes(c: Client) -> list[dict[str, object]]:
    return c.rows("SELECT post_id, user_id, created_at FROM likes ORDER BY post_id, user_id")


def answer(pid: int, count: int, liked: bool) -> dict[str, object]:
    return {"post_id": pid, "like_count": count, "liked": liked}


# -- POST /api/posts/{id}/like ------------------------------------------------------------


def test_like_returns_count_and_stores_row() -> None:
    c = Client()
    s = Cast(c)
    c.like(s.rosa, s.p_tara)
    c.like(s.tara, s.p_tara)
    t = c.now
    r = c.post(like_url(s.pid), user=s.quinn)
    assert (r.status, r.json) == (200, answer(s.pid, 1, True))
    assert like_rows(c, s.pid) == [{"post_id": s.pid, "user_id": s.quinn.id, "created_at": t}]
    assert len(like_rows(c, s.p_tara)) == 2


def test_like_count_includes_every_users_like() -> None:
    c = Client()
    s = Cast(c)
    c.like(s.tara, s.pid)
    c.tick(500)
    r = c.post(like_url(s.pid), user=s.quinn)
    assert (r.status, r.json) == (200, answer(s.pid, 2, True))
    c.tick(500)
    r = c.post(like_url(s.pid), user=s.rosa)
    assert (r.status, r.json) == (200, answer(s.pid, 3, True))
    assert [row["user_id"] for row in like_rows(c, s.pid)] == [s.quinn.id, s.rosa.id, s.tara.id]


def test_like_twice_keeps_one_row_and_first_time() -> None:
    c = Client()
    s = Cast(c)
    first = c.post(like_url(s.pid), user=s.tara)
    t = c.now
    assert (first.status, first.json) == (200, answer(s.pid, 1, True))
    c.tick(7000)
    again = c.post(like_url(s.pid), user=s.tara)
    assert (again.status, again.json) == (200, answer(s.pid, 1, True))
    assert like_rows(c, s.pid) == [{"post_id": s.pid, "user_id": s.tara.id, "created_at": t}]


def test_author_can_like_own_post_without_friends() -> None:
    c = Client()
    s = Cast(c)
    own = c.make_post(s.uma, "uma alone")
    r = c.post(like_url(own), user=s.uma)
    assert (r.status, r.json) == (200, answer(own, 1, True))
    assert like_rows(c, own) == [{"post_id": own, "user_id": s.uma.id, "created_at": c.now}]


def test_like_ignores_a_request_body() -> None:
    c = Client()
    s = Cast(c)
    r = c.post(like_url(s.p_quinn), {"liked": False}, user=s.sami)
    assert (r.status, r.json) == (200, answer(s.p_quinn, 1, True))


# -- DELETE /api/posts/{id}/like ----------------------------------------------------------


def test_unlike_removes_only_my_like_of_this_post() -> None:
    c = Client()
    s = Cast(c)
    c.like(s.tara, s.pid)
    c.like(s.quinn, s.pid)
    c.like(s.quinn, s.p_quinn)
    c.like(s.rosa, s.p_quinn)
    t = c.now
    c.tick(2000)
    r = c.delete(like_url(s.pid), user=s.quinn)
    assert (r.status, r.json) == (200, answer(s.pid, 1, False))
    assert like_rows(c, s.pid) == [{"post_id": s.pid, "user_id": s.tara.id, "created_at": t}]
    assert [row["user_id"] for row in like_rows(c, s.p_quinn)] == [s.quinn.id, s.rosa.id]


def test_unlike_twice_gives_the_same_answer() -> None:
    c = Client()
    s = Cast(c)
    c.like(s.tara, s.pid)
    c.like(s.rosa, s.pid)
    c.like(s.quinn, s.pid)
    first = c.delete(like_url(s.pid), user=s.quinn)
    assert (first.status, first.json) == (200, answer(s.pid, 2, False))
    again = c.delete(like_url(s.pid), user=s.quinn)
    assert (again.status, again.json) == (200, answer(s.pid, 2, False))
    assert [row["user_id"] for row in like_rows(c, s.pid)] == [s.rosa.id, s.tara.id]


def test_unlike_without_a_like_is_ok() -> None:
    c = Client()
    s = Cast(c)
    c.like(s.sami, s.p_quinn)
    c.like(s.rosa, s.p_quinn)
    before = all_likes(c)
    r = c.delete(like_url(s.p_quinn), user=s.quinn)
    assert (r.status, r.json) == (200, answer(s.p_quinn, 2, False))
    assert all_likes(c) == before


def test_unlike_last_like_gives_zero() -> None:
    c = Client()
    s = Cast(c)
    c.like(s.rosa, s.p_tara)
    r = c.delete(like_url(s.p_tara), user=s.rosa)
    assert (r.status, r.json) == (200, answer(s.p_tara, 0, False))
    assert like_rows(c, s.p_tara) == []


def test_like_unlike_like_stores_a_new_time() -> None:
    c = Client()
    s = Cast(c)
    assert c.post(like_url(s.pid), user=s.quinn).json == answer(s.pid, 1, True)
    c.tick(3000)
    assert c.delete(like_url(s.pid), user=s.quinn).json == answer(s.pid, 0, False)
    c.tick(3000)
    r = c.post(like_url(s.pid), user=s.quinn)
    assert (r.status, r.json) == (200, answer(s.pid, 1, True))
    assert like_rows(c, s.pid) == [{"post_id": s.pid, "user_id": s.quinn.id, "created_at": c.now}]


# -- GET /api/posts/{id}/likes ------------------------------------------------------------


def test_likers_in_like_time_order() -> None:
    c = Client()
    s = Cast(c)
    c.like(s.tara, s.pid)
    c.tick(1000)
    c.like(s.uma, s.pid)
    c.tick(1000)
    c.like(s.quinn, s.pid)
    c.tick(1000)
    c.like(s.rosa, s.pid)
    c.like(s.sami, s.p_quinn)
    r = c.get(likes_url(s.pid), user=s.quinn)
    assert r.status == 200
    assert r.json == {"users": [s.tara.json, s.uma.json, s.quinn.json, s.rosa.json]}


def test_likers_at_the_same_time_by_user_id() -> None:
    c = Client()
    s = Cast(c)
    c.like(s.uma, s.p_tara)
    c.tick(1000)
    c.like(s.tara, s.p_tara)
    c.like(s.rosa, s.p_tara)
    c.like(s.sami, s.p_tara)
    r = c.get(likes_url(s.p_tara), user=s.rosa)
    assert r.status == 200
    assert r.json == {"users": [s.uma.json, s.rosa.json, s.sami.json, s.tara.json]}


def test_likers_follow_likes_made_through_the_api() -> None:
    c = Client()
    s = Cast(c)
    c.post(like_url(s.pid), user=s.tara)
    c.tick(1000)
    c.post(like_url(s.pid), user=s.quinn)
    c.tick(1000)
    c.post(like_url(s.pid), user=s.tara)  # already liked: keeps its first time
    r = c.get(likes_url(s.pid), user=s.rosa)
    assert (r.status, r.json) == (200, {"users": [s.tara.json, s.quinn.json]})
    c.tick(1000)
    c.delete(like_url(s.pid), user=s.tara)
    c.tick(1000)
    c.post(like_url(s.pid), user=s.tara)  # liked again later: now last
    r = c.get(likes_url(s.pid), user=s.tara)
    assert (r.status, r.json) == (200, {"users": [s.quinn.json, s.tara.json]})


def test_likers_of_a_post_without_likes() -> None:
    c = Client()
    s = Cast(c)
    c.like(s.quinn, s.p_quinn)
    r = c.get(likes_url(s.pid), user=s.rosa)
    assert (r.status, r.json) == (200, {"users": []})


def test_listing_writes_nothing() -> None:
    c = Client()
    s = Cast(c)
    c.like(s.rosa, s.pid)
    before = all_likes(c)
    r = c.get(likes_url(s.pid), user=s.tara)
    assert (r.status, r.json) == (200, {"users": [s.rosa.json]})
    assert all_likes(c) == before


# -- 404: post not visible, unknown or bad id ---------------------------------------------


ROUTES = [("POST", "like"), ("DELETE", "like"), ("GET", "likes")]


@pytest.mark.parametrize(("method", "tail"), ROUTES)
def test_stranger_gets_404(method: str, tail: str) -> None:
    c = Client()
    s = Cast(c)
    c.like(s.tara, s.pid)
    before = all_likes(c)
    assert c.request(method, f"/api/posts/{s.pid}/{tail}", user=s.uma).status == 404
    assert all_likes(c) == before


@pytest.mark.parametrize(("method", "tail"), ROUTES)
def test_friend_of_a_friend_gets_404(method: str, tail: str) -> None:
    c = Client()
    s = Cast(c)
    c.like(s.quinn, s.pid)
    before = all_likes(c)
    assert c.request(method, f"/api/posts/{s.pid}/{tail}", user=s.sami).status == 404
    assert all_likes(c) == before


@pytest.mark.parametrize(
    ("method", "tail"), [("POST", "like"), ("GET", "likes")], ids=["post", "get"]
)
def test_former_friend_cannot_like_or_list(method: str, tail: str) -> None:
    c = Client()
    s = Cast(c)
    c.like(s.tara, s.pid)
    c.unfriend(s.tara, s.rosa)
    before = all_likes(c)
    assert c.request(method, f"/api/posts/{s.pid}/{tail}", user=s.tara).status == 404
    assert all_likes(c) == before


def test_former_friends_like_still_counts() -> None:
    c = Client()
    s = Cast(c)
    c.like(s.tara, s.pid)
    c.unfriend(s.tara, s.rosa)
    c.tick(1000)
    r = c.post(like_url(s.pid), user=s.quinn)
    assert (r.status, r.json) == (200, answer(s.pid, 2, True))
    listed = c.get(likes_url(s.pid), user=s.quinn)
    assert (listed.status, listed.json) == (200, {"users": [s.tara.json, s.quinn.json]})


@pytest.mark.parametrize(("method", "tail"), ROUTES)
@pytest.mark.parametrize("raw", ["999", "x", "0", "-3", "2.5", "3x"])
def test_unknown_or_bad_post_id_is_404(method: str, tail: str, raw: str) -> None:
    c = Client()
    s = Cast(c)
    c.like(s.rosa, s.pid)
    before = all_likes(c)
    assert c.request(method, f"/api/posts/{raw}/{tail}", user=s.rosa).status == 404
    assert all_likes(c) == before


def test_lives_in_its_own_feature_folder() -> None:
    importlib.import_module("chatbook.features.likes.handler")
