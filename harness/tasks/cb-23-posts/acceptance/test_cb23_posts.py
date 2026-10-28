import importlib

import pytest

from chatbook.testing import Account, Client

FEED = "/api/feed"
POSTS = "/api/posts"

Cast = tuple[Account, Account, Account, Account, Account]


def cast(c: Client) -> Cast:
    """hana is friends with ivan and kurt; jade is a friend of ivan only (a friend of a friend
    for hana); lena has a pending friend request to hana (a friend of no one)."""
    hana = c.user("hana", "Hana Hill")
    ivan = c.user("ivan", "Ivan Ito")
    jade = c.user("jade", "Jade Jones")
    kurt = c.user("kurt", "Kurt Kemp")
    lena = c.user("lena", "Lena Lowe")
    c.befriend(hana, ivan)
    c.befriend(hana, kurt)
    c.befriend(ivan, jade)
    c.friend_request(lena, hana)
    return hana, ivan, jade, kurt, lena


def post(
    pid: int,
    author: Account,
    body: str,
    created_at: int,
    *,
    likes: int = 0,
    comments: int = 0,
    liked: bool = False,
) -> dict[str, object]:
    return {
        "id": pid,
        "author": author.json,
        "body": body,
        "created_at": created_at,
        "like_count": likes,
        "comment_count": comments,
        "liked": liked,
    }


def assert_bools(posts: list[dict[str, object]]) -> None:
    assert all(type(p["liked"]) is bool for p in posts)


def feed(c: Client, user: Account, query: str = "") -> tuple[list[int], bool]:
    r = c.get(FEED + query, user=user)
    assert r.status == 200
    assert set(r.json) == {"posts", "has_more"}
    assert type(r.json["has_more"]) is bool
    return [p["id"] for p in r.json["posts"]], r.json["has_more"]


# -- GET /api/feed -----------------------------------------------------------------------


def world(c: Client) -> tuple[Cast, dict[str, tuple[int, int]]]:
    """One post per cast member at distinct times, plus likes and comments.
    Returns the cast and name -> (post id, created_at). Post ids: ivan 1, jade 2, hana 3,
    lena 4, kurt 5."""
    people = cast(c)
    hana, ivan, jade, kurt, lena = people
    made: dict[str, tuple[int, int]] = {}
    for name, author, body in [
        ("ivan", ivan, "morning run"),
        ("jade", jade, "quiet lake"),
        ("hana", hana, "garden notes"),
        ("lena", lena, "first day here"),
        ("kurt", kurt, "new bike"),
    ]:
        c.tick(1500)
        made[name] = (c.make_post(author, body), c.now)
    c.tick(1000)
    c.like(ivan, made["hana"][0])
    c.like(kurt, made["hana"][0])
    c.like(hana, made["ivan"][0])
    c.like(jade, made["ivan"][0])
    c.like(jade, made["jade"][0])
    c.comment(ivan, made["hana"][0], "lovely")
    c.comment(hana, made["ivan"][0], "keep going")
    c.comment(jade, made["ivan"][0], "nice pace")
    c.comment(ivan, made["ivan"][0], "thanks")
    return people, made


def test_feed_has_own_and_friends_posts_newest_first_with_exact_shapes() -> None:
    c = Client()
    (hana, ivan, _, kurt, _), m = world(c)
    r = c.get(FEED, user=hana)
    assert r.status == 200
    assert r.json == {
        "posts": [
            post(m["kurt"][0], kurt, "new bike", m["kurt"][1]),
            post(m["hana"][0], hana, "garden notes", m["hana"][1], likes=2, comments=1),
            post(m["ivan"][0], ivan, "morning run", m["ivan"][1], likes=2, comments=3, liked=True),
        ],
        "has_more": False,
    }
    assert type(r.json["has_more"]) is bool
    assert_bools(r.json["posts"])


def test_feed_depends_on_the_viewer() -> None:
    c = Client()
    (hana, ivan, jade, kurt, lena), m = world(c)
    r = c.get(FEED, user=ivan)
    assert r.status == 200
    assert r.json == {
        "posts": [
            post(m["hana"][0], hana, "garden notes", m["hana"][1], likes=2, comments=1, liked=True),
            post(m["jade"][0], jade, "quiet lake", m["jade"][1], likes=1),
            post(m["ivan"][0], ivan, "morning run", m["ivan"][1], likes=2, comments=3),
        ],
        "has_more": False,
    }
    assert_bools(r.json["posts"])
    r = c.get(FEED, user=jade)
    assert r.status == 200
    assert r.json == {
        "posts": [
            post(m["jade"][0], jade, "quiet lake", m["jade"][1], likes=1, liked=True),
            post(m["ivan"][0], ivan, "morning run", m["ivan"][1], likes=2, comments=3, liked=True),
        ],
        "has_more": False,
    }
    assert feed(c, kurt) == ([m["kurt"][0], m["hana"][0]], False)
    # a pending friend request does not share posts, in either direction
    assert feed(c, lena) == ([m["lena"][0]], False)


def test_feed_of_a_user_without_posts_or_friends_is_empty() -> None:
    c = Client()
    world(c)
    mona = c.user("mona", "Mona Moss")
    r = c.get(FEED, user=mona)
    assert (r.status, r.json) == (200, {"posts": [], "has_more": False})


def test_unfriended_users_posts_leave_the_feed() -> None:
    c = Client()
    (hana, ivan, _, _, _), m = world(c)
    c.unfriend(hana, ivan)
    assert feed(c, hana) == ([m["kurt"][0], m["hana"][0]], False)
    assert feed(c, ivan) == ([m["jade"][0], m["ivan"][0]], False)


@pytest.mark.parametrize(
    ("query", "names", "more"),
    [
        ("?limit=1", ["kurt"], True),
        ("?limit=2", ["kurt", "hana"], True),
        ("?limit=3", ["kurt", "hana", "ivan"], False),
        ("?limit=4", ["kurt", "hana", "ivan"], False),
        ("?before=5", ["hana", "ivan"], False),
        ("?before=4", ["hana", "ivan"], False),
        ("?before=3", ["ivan"], False),
        ("?before=2", ["ivan"], False),
        ("?before=1", [], False),
        ("?before=0", [], False),
        ("?before=987654", ["kurt", "hana", "ivan"], False),
        ("?before=5&limit=1", ["hana"], True),
        ("?limit=1&before=4", ["hana"], True),
        ("?before=3&limit=1", ["ivan"], False),
        ("?limit=&before=", ["kurt", "hana", "ivan"], False),
    ],
)
def test_feed_limit_and_before_cursor(query: str, names: list[str], more: bool) -> None:
    c = Client()
    (hana, *_), m = world(c)
    assert [m[n][0] for n in ["ivan", "jade", "hana", "lena", "kurt"]] == [1, 2, 3, 4, 5]
    assert feed(c, hana, query) == ([m[n][0] for n in names], more)


def test_has_more_ignores_older_posts_the_viewer_cannot_see() -> None:
    c = Client()
    hana, ivan, jade, _, lena = cast(c)
    for i in range(4):
        c.make_post(jade, f"hidden {i}")
        c.make_post(lena, f"other {i}")
    c.tick(2000)
    mine = c.make_post(hana, "mine")
    c.tick(2000)
    theirs = c.make_post(ivan, "theirs")
    assert feed(c, hana, "?limit=2") == ([theirs, mine], False)
    assert feed(c, hana, "?limit=1") == ([theirs], True)
    assert feed(c, hana, f"?before={mine}") == ([], False)


def test_posts_at_the_same_time_are_ordered_by_id_descending() -> None:
    c = Client()
    hana, ivan, _, kurt, _ = cast(c)
    ids = [c.make_post(a, f"same ms {i}") for i, a in enumerate([kurt, hana, ivan, hana, kurt])]
    r = c.get(FEED, user=hana)
    assert r.status == 200
    assert [p["id"] for p in r.json["posts"]] == ids[::-1]
    assert {p["created_at"] for p in r.json["posts"]} == {c.now}
    assert feed(c, hana, f"?before={ids[3]}&limit=2") == ([ids[2], ids[1]], True)


def test_default_limit_is_20_and_100_is_allowed() -> None:
    c = Client()
    hana, ivan, jade, kurt, _ = cast(c)
    visible: list[int] = []
    for i in range(23):
        c.tick(100)
        visible.append(c.make_post([hana, ivan, kurt][i % 3], f"note {i}"))
        if i % 4 == 0:
            c.make_post(jade, f"fof {i}")
    newest_first = visible[::-1]
    assert feed(c, hana) == (newest_first[:20], True)
    assert feed(c, hana, "?limit=100") == (newest_first, False)
    assert feed(c, hana, "?limit=23") == (newest_first, False)
    assert feed(c, hana, "?limit=22") == (newest_first[:22], True)


def test_walking_pages_with_before_returns_every_visible_post_once() -> None:
    c = Client()
    hana, ivan, jade, kurt, lena = cast(c)
    visible: list[int] = []
    for i in range(17):
        c.tick(250)
        author = [hana, jade, ivan, lena, kurt][i % 5]
        pid = c.make_post(author, f"walk {i}")
        if author in (hana, ivan, kurt):
            visible.append(pid)
    assert len(visible) == 10
    seen: list[int] = []
    flags: list[bool] = []
    query = "?limit=3"
    for _ in range(6):  # bounded: a feed that ignores `before` must fail, not hang
        ids, more = feed(c, hana, query)
        seen += ids
        flags.append(more)
        if not more or not ids:
            break
        query = f"?limit=3&before={ids[-1]}"
    assert seen == visible[::-1]
    assert flags == [True, True, True, False]


@pytest.mark.parametrize(
    "query",
    [
        "?limit=0",
        "?limit=101",
        "?limit=-2",
        "?limit=ten",
        "?limit=2.5",
        "?before=-1",
        "?before=abc",
        "?before=3.5",
    ],
)
def test_feed_rejects_bad_query(query: str) -> None:
    c = Client()
    (hana, *_), _ = world(c)
    assert c.get(FEED + query, user=hana).status == 400


# -- POST /api/posts ---------------------------------------------------------------------


def test_create_post_strips_body_and_returns_new_post() -> None:
    c = Client()
    hana, ivan, jade, _, _ = cast(c)
    c.make_post(ivan, "older one")
    c.make_post(jade, "older two")
    c.tick(4321)
    r = c.post(POSTS, {"body": "  sunny\n\nafternoon \t"}, user=hana)
    assert r.status == 201
    assert r.json == {"post": post(3, hana, "sunny\n\nafternoon", c.now)}
    assert_bools([r.json["post"]])
    assert c.rows("SELECT * FROM posts WHERE id = 3") == [
        {"id": 3, "author_id": hana.id, "body": "sunny\n\nafternoon", "created_at": c.now}
    ]
    assert len(c.rows("SELECT id FROM posts")) == 3


def test_new_post_shows_in_own_and_friends_feeds_only() -> None:
    c = Client()
    hana, ivan, jade, kurt, lena = cast(c)
    c.tick(800)
    r = c.post(POSTS, {"body": "quick hello"}, user=ivan)
    assert r.status == 201
    pid = r.json["post"]["id"]
    expected = post(pid, ivan, "quick hello", c.now)
    for viewer in (ivan, hana, jade):
        got = c.get(FEED, user=viewer)
        assert (got.status, got.json) == (200, {"posts": [expected], "has_more": False})
    for viewer in (kurt, lena):
        assert feed(c, viewer) == ([], False)
    got = c.get(f"{POSTS}/{pid}", user=jade)
    assert (got.status, got.json) == (200, {"post": expected})


@pytest.mark.parametrize(
    ("raw", "stored"),
    [
        ("z", "z"),
        ("x" * 2000, "x" * 2000),
        ("  " + "y" * 2000 + "\n", "y" * 2000),
        ("tab\tinside", "tab\tinside"),
    ],
    ids=["one_char", "2000_chars", "2000_chars_padded", "inner_tab"],
)
def test_create_post_length_bounds(raw: str, stored: str) -> None:
    c = Client()
    _, ivan, *_ = cast(c)
    r = c.post(POSTS, {"body": raw}, user=ivan)
    assert r.status == 201
    assert r.json == {"post": post(1, ivan, stored, c.now)}
    assert c.rows("SELECT body FROM posts") == [{"body": stored}]


@pytest.mark.parametrize(
    "body",
    [
        {"body": ""},
        {"body": "  \n\t "},
        {"body": "q" * 2001},
        {"body": " " + "q" * 2001 + " "},
        {"body": 99},
        {"body": None},
        {"body": True},
        {"body": ["hi"]},
        {"text": "hi"},
        {},
        ["body", "hi"],
        "hi",
        None,
    ],
)
def test_create_post_rejects_bad_body(body: object) -> None:
    c = Client()
    _, ivan, *_ = cast(c)
    assert c.post(POSTS, body, user=ivan).status == 400
    assert c.rows("SELECT id FROM posts") == []


# -- GET /api/posts/{id} -----------------------------------------------------------------


def test_get_post_counts_and_liked_depend_on_viewer() -> None:
    c = Client()
    hana, ivan, jade, kurt, _ = cast(c)
    c.make_post(kurt, "unrelated")
    c.tick(2500)
    pid = c.make_post(ivan, "trail map")
    created = c.now
    c.tick(600)
    c.like(hana, pid)
    c.like(jade, pid)
    c.comment(jade, pid, "where?")
    c.comment(ivan, pid, "north ridge")
    c.comment(hana, pid, "count me in")
    other = c.make_post(ivan, "other")
    c.like(ivan, other)
    c.comment(hana, other, "x")
    base = post(pid, ivan, "trail map", created, likes=2, comments=3)
    for viewer, liked in [(hana, True), (ivan, False), (jade, True)]:
        r = c.get(f"{POSTS}/{pid}", user=viewer)
        assert r.status == 200
        assert r.json == {"post": base | {"liked": liked}}
        assert_bools([r.json["post"]])


def test_get_own_post_and_likes_of_former_friends_still_count() -> None:
    c = Client()
    hana, ivan, _, kurt, _ = cast(c)
    c.tick(900)
    pid = c.make_post(hana, "garden")
    created = c.now
    c.like(kurt, pid)
    c.like(hana, pid)
    c.like(ivan, pid)
    c.comment(kurt, pid, "nice")
    c.unfriend(hana, kurt)
    r = c.get(f"{POSTS}/{pid}", user=hana)
    assert r.status == 200
    assert r.json == {"post": post(pid, hana, "garden", created, likes=3, comments=1, liked=True)}


@pytest.mark.parametrize("viewer_index", [2, 4])
def test_get_post_of_a_non_friend_is_404(viewer_index: int) -> None:
    c = Client()
    people = cast(c)
    hana = people[0]
    pid = c.make_post(hana, "friends only")
    c.friend_request(hana, people[2])  # a pending request from the author does not count
    for friend in (people[1], people[3]):
        assert c.get(f"{POSTS}/{pid}", user=friend).status == 200
    # jade (a friend of a friend) and lena (who sent hana a request) are not friends
    assert c.get(f"{POSTS}/{pid}", user=people[viewer_index]).status == 404


def test_get_post_after_unfriend_is_404() -> None:
    c = Client()
    hana, ivan, *_ = cast(c)
    pid = c.make_post(ivan, "for friends")
    c.unfriend(hana, ivan)
    assert c.get(f"{POSTS}/{pid}", user=hana).status == 404


@pytest.mark.parametrize("raw", ["999", "abc", "0", "-1", "1.5", "2x"])
def test_get_unknown_or_bad_post_id_is_404(raw: str) -> None:
    c = Client()
    hana, *_ = cast(c)
    c.make_post(hana, "one")
    c.make_post(hana, "two")
    assert c.get(f"{POSTS}/{raw}", user=hana).status == 404


# -- DELETE /api/posts/{id} --------------------------------------------------------------


def snapshot(c: Client) -> tuple[object, ...]:
    return (
        c.rows("SELECT * FROM posts ORDER BY id"),
        c.rows("SELECT * FROM likes ORDER BY post_id, user_id"),
        c.rows("SELECT * FROM comments ORDER BY id"),
    )


def test_author_deletes_post_with_its_likes_and_comments() -> None:
    c = Client()
    hana, ivan, _, kurt, _ = cast(c)
    keep = c.make_post(ivan, "keep me")
    c.tick(300)
    pid = c.make_post(hana, "to remove")
    c.tick(300)
    other = c.make_post(hana, "stays too")
    for user in (ivan, hana, kurt):
        c.like(user, pid)
    c.like(ivan, keep)
    c.like(hana, other)
    c.comment(ivan, pid, "first")
    c.comment(hana, pid, "second")
    c.comment(hana, keep, "third")
    c.comment(kurt, other, "fourth")
    likes_before = c.rows("SELECT * FROM likes WHERE post_id != ? ORDER BY post_id, user_id", pid)
    comments_before = c.rows("SELECT * FROM comments WHERE post_id != ? ORDER BY id", pid)
    r = c.delete(f"{POSTS}/{pid}", user=hana)
    assert (r.status, r.json) == (200, {"deleted": pid})
    assert c.rows("SELECT id FROM posts ORDER BY id") == [{"id": keep}, {"id": other}]
    assert c.rows("SELECT * FROM likes WHERE post_id = ?", pid) == []
    assert c.rows("SELECT * FROM comments WHERE post_id = ?", pid) == []
    assert c.rows("SELECT * FROM likes ORDER BY post_id, user_id") == likes_before
    assert c.rows("SELECT * FROM comments ORDER BY id") == comments_before
    assert c.get(f"{POSTS}/{pid}", user=hana).status == 404
    assert feed(c, hana) == ([other, keep], False)
    assert c.delete(f"{POSTS}/{pid}", user=hana).status == 404


def test_friend_cannot_delete_post_is_403() -> None:
    c = Client()
    hana, ivan, _, kurt, _ = cast(c)
    pid = c.make_post(hana, "mine only")
    c.like(ivan, pid)
    c.comment(kurt, pid, "hey")
    before = snapshot(c)
    assert c.delete(f"{POSTS}/{pid}", user=ivan).status == 403
    assert snapshot(c) == before
    r = c.delete(f"{POSTS}/{pid}", user=hana)
    assert (r.status, r.json) == (200, {"deleted": pid})


@pytest.mark.parametrize("viewer_index", [2, 4])
def test_non_friend_delete_is_404(viewer_index: int) -> None:
    c = Client()
    people = cast(c)
    hana, ivan = people[0], people[1]
    pid = c.make_post(hana, "not yours")
    c.like(ivan, pid)
    c.comment(ivan, pid, "ok")
    before = snapshot(c)
    assert c.delete(f"{POSTS}/{pid}", user=people[viewer_index]).status == 404
    assert snapshot(c) == before


def test_deleting_a_post_without_likes_or_comments() -> None:
    c = Client()
    _, ivan, jade, _, _ = cast(c)
    first = c.make_post(jade, "jade post")
    pid = c.make_post(jade, "short lived")
    c.like(ivan, first)
    r = c.delete(f"{POSTS}/{pid}", user=jade)
    assert (r.status, r.json) == (200, {"deleted": pid})
    assert c.rows("SELECT id FROM posts") == [{"id": first}]
    assert len(c.rows("SELECT * FROM likes WHERE post_id = ?", first)) == 1


@pytest.mark.parametrize("raw", ["999", "abc", "0", "-3"])
def test_delete_unknown_or_bad_post_id_is_404(raw: str) -> None:
    c = Client()
    hana, *_ = cast(c)
    c.make_post(hana, "one")
    before = snapshot(c)
    assert c.delete(f"{POSTS}/{raw}", user=hana).status == 404
    assert snapshot(c) == before


def test_lives_in_its_own_feature_folder() -> None:
    importlib.import_module("chatbook.features.posts.handler")
