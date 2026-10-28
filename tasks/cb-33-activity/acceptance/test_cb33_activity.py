import importlib

import pytest

from chatbook.testing import Account, Client

URL = "/api/activity/hidden"
EMPTY: dict[str, list[object]] = {"comments": [], "likes": []}
COMMENT_KEYS = {"id", "post_id", "post_author", "body", "created_at"}
LIKE_KEYS = {"post_id", "post_author", "created_at"}


class Cast:
    """kai (1) is me. lena (2) is my friend; mo (3) and nia (4) are my friends until a test
    unfriends them; omar (5) never was; pia (6) is a friend of mo only."""

    def __init__(self, c: Client) -> None:
        self.kai = c.user("kai", "Kai Kerr")
        self.lena = c.user("lena", "Lena Lowe")
        self.mo = c.user("mo", "Mo Moss")
        self.nia = c.user("nia", "Nia Nolan")
        self.omar = c.user("omar", "Omar Okafor")
        self.pia = c.user("pia", "Pia Pratt")
        c.befriend(self.kai, self.lena)
        c.befriend(self.kai, self.mo)
        c.befriend(self.nia, self.kai)
        c.befriend(self.mo, self.pia)


POST_TEXTS = [
    "kai plants tomatoes",
    "lena paints a fence",
    "mo bakes rye bread",
    "nia climbs a hill",
    "mo fixes a bike",
    "omar walks a dog",
]


def mixed(c: Client) -> tuple[Cast, dict[str, int]]:
    """Posts by kai, lena, mo, nia, mo and omar; rows by everyone; then mo and nia are no
    longer kai's friends (kai unfriends mo, nia unfriends kai). t0..t3 are the row times."""
    s = Cast(c)
    ids = {"t0": c.now}
    for key, author, text in zip(
        ["own", "lena", "mo", "nia", "mo2", "omar"],
        [s.kai, s.lena, s.mo, s.nia, s.mo, s.omar],
        POST_TEXTS,
        strict=True,
    ):
        ids[key] = c.make_post(author, text)
    c.tick(2000)
    ids["t1"] = c.now
    ids["c_pia"] = c.comment(s.pia, ids["mo"], "pia wants a slice")
    ids["c_lena"] = c.comment(s.lena, ids["nia"], "lena cheers")
    ids["c_mo"] = c.comment(s.kai, ids["mo"], "smells great")
    c.comment(s.kai, ids["own"], "my own note")
    c.comment(s.kai, ids["lena"], "nice colour")
    c.like(s.kai, ids["nia"])
    c.like(s.mo, ids["own"])
    c.tick(2000)
    ids["t2"] = c.now
    ids["c_nia"] = c.comment(s.kai, ids["nia"], "lovely hilltop")
    ids["c_omar"] = c.comment(s.omar, ids["nia"], "omar was here")
    c.like(s.kai, ids["own"])
    c.like(s.kai, ids["lena"])
    c.like(s.pia, ids["mo"])
    c.like(s.omar, ids["mo2"])
    c.tick(2000)
    ids["t3"] = c.now
    ids["c_mo2"] = c.comment(s.kai, ids["mo2"], "fixed yet?")
    c.like(s.kai, ids["mo"])
    c.tick(2000)
    c.unfriend(s.kai, s.mo)
    c.unfriend(s.nia, s.kai)
    return s, ids


def activity(c: Client, who: Account) -> dict[str, list[dict[str, object]]]:
    r = c.get(URL, user=who)
    assert r.status == 200
    assert set(r.json) == {"comments", "likes"}
    found: dict[str, list[dict[str, object]]] = r.json
    return found


def comment_item(c: Client, cid: int, post_author: Account) -> dict[str, object]:
    """The expected item for comment `cid`, from its comments row."""
    row = c.row("SELECT * FROM comments WHERE id = ?", cid)
    assert row is not None
    return {
        "id": cid,
        "post_id": row["post_id"],
        "post_author": post_author.json,
        "body": row["body"],
        "created_at": row["created_at"],
    }


def like_item(c: Client, pid: int, post_author: Account, liker: Account) -> dict[str, object]:
    """The expected item for liker's like of post `pid`, from its likes row."""
    row = c.row("SELECT * FROM likes WHERE post_id = ? AND user_id = ?", pid, liker.id)
    assert row is not None
    return {"post_id": pid, "post_author": post_author.json, "created_at": row["created_at"]}


# -- what is listed ------------------------------------------------------------------------


def test_lists_only_my_rows_on_posts_i_can_no_longer_see() -> None:
    c = Client()
    s, ids = mixed(c)
    r = c.get(URL, user=s.kai)
    assert r.status == 200
    assert r.json == {
        "comments": [
            {
                "id": ids["c_mo2"],
                "post_id": ids["mo2"],
                "post_author": s.mo.json,
                "body": "fixed yet?",
                "created_at": ids["t3"],
            },
            {
                "id": ids["c_nia"],
                "post_id": ids["nia"],
                "post_author": s.nia.json,
                "body": "lovely hilltop",
                "created_at": ids["t2"],
            },
            {
                "id": ids["c_mo"],
                "post_id": ids["mo"],
                "post_author": s.mo.json,
                "body": "smells great",
                "created_at": ids["t1"],
            },
        ],
        "likes": [
            {"post_id": ids["mo"], "post_author": s.mo.json, "created_at": ids["t3"]},
            {"post_id": ids["nia"], "post_author": s.nia.json, "created_at": ids["t1"]},
        ],
    }


def test_never_sends_post_fields_counts_or_other_rows() -> None:
    c = Client()
    s, ids = mixed(c)
    r = c.get(URL, user=s.kai)
    assert r.status == 200
    for text in POST_TEXTS:
        assert text not in r.text
    for text in ["pia wants a slice", "lena cheers", "omar was here", "my own note"]:
        assert text not in r.text
    assert [set(k) for k in r.json["comments"]] == [COMMENT_KEYS] * 3
    assert [set(x) for x in r.json["likes"]] == [LIKE_KEYS] * 2
    for item in r.json["comments"] + r.json["likes"]:
        assert set(item["post_author"]) == {"id", "username", "display_name"}
    assert ids["t0"] not in [item["created_at"] for item in r.json["comments"] + r.json["likes"]]


def test_each_viewer_sees_only_their_own_rows() -> None:
    c = Client()
    s, ids = mixed(c)
    assert activity(c, s.mo) == {
        "comments": [],
        "likes": [{"post_id": ids["own"], "post_author": s.kai.json, "created_at": ids["t1"]}],
    }
    assert activity(c, s.lena) == {
        "comments": [comment_item(c, ids["c_lena"], s.nia)],
        "likes": [],
    }
    assert activity(c, s.omar) == {
        "comments": [comment_item(c, ids["c_omar"], s.nia)],
        "likes": [like_item(c, ids["mo2"], s.mo, s.omar)],
    }
    assert activity(c, s.pia) == EMPTY  # mo is pia's friend
    assert activity(c, s.nia) == EMPTY


@pytest.mark.parametrize(
    "link", ["stranger", "fof", "asked", "asker"], ids=["stranger", "fof", "asked", "asker"]
)
def test_any_author_who_is_not_my_friend_counts(link: str) -> None:
    c = Client()
    s = Cast(c)
    author = s.pia if link == "fof" else s.omar
    if link == "asked":
        c.friend_request(s.kai, s.omar)
    elif link == "asker":
        c.friend_request(s.omar, s.kai)
    seen = c.make_post(s.lena, "lena reads a book")
    pid = c.make_post(author, "a post kai never saw")
    c.tick(1500)
    cid = c.comment(s.kai, pid, "seeded remark")
    c.comment(s.kai, seen, "good choice")
    c.like(s.kai, seen)
    c.like(s.kai, pid)
    assert activity(c, s.kai) == {
        "comments": [comment_item(c, cid, author)],
        "likes": [like_item(c, pid, author, s.kai)],
    }


@pytest.mark.parametrize("mine", [True, False], ids=["i_unfriend", "they_unfriend"])
def test_either_side_may_unfriend(mine: bool) -> None:
    c = Client()
    s = Cast(c)
    pid = c.make_post(s.mo, "mo sings a song")
    c.tick(700)
    cid = c.comment(s.kai, pid, "encore please")
    c.like(s.kai, pid)
    assert activity(c, s.kai) == EMPTY
    if mine:
        c.unfriend(s.kai, s.mo)
    else:
        c.unfriend(s.mo, s.kai)
    assert activity(c, s.kai) == {
        "comments": [comment_item(c, cid, s.mo)],
        "likes": [like_item(c, pid, s.mo, s.kai)],
    }


def test_rows_follow_the_friendship() -> None:
    c = Client()
    s = Cast(c)
    pid = c.make_post(s.nia, "nia hosts a picnic")
    c.tick(1000)
    cid = c.comment(s.kai, pid, "save me a seat")
    c.tick(1000)
    c.like(s.kai, pid)
    listed = {
        "comments": [comment_item(c, cid, s.nia)],
        "likes": [like_item(c, pid, s.nia, s.kai)],
    }
    assert activity(c, s.kai) == EMPTY
    c.unfriend(s.kai, s.nia)
    assert activity(c, s.kai) == listed
    c.befriend(s.nia, s.kai)
    assert activity(c, s.kai) == EMPTY
    c.unfriend(s.nia, s.kai)
    assert activity(c, s.kai) == listed


def test_post_author_shows_the_current_name() -> None:
    c = Client()
    s = Cast(c)
    pid = c.make_post(s.nia, "nia writes a poem")
    c.comment(s.kai, pid, "lovely lines")
    c.like(s.kai, pid)
    c.unfriend(s.nia, s.kai)
    c.db.run("UPDATE users SET display_name = ? WHERE id = ?", "Nia Northwood", s.nia.id)
    c.db.run("UPDATE users SET display_name = ? WHERE id = ?", "Kai Renamed", s.kai.id)
    renamed = {"id": s.nia.id, "username": "nia", "display_name": "Nia Northwood"}
    found = activity(c, s.kai)
    assert [k["post_author"] for k in found["comments"]] == [renamed]
    assert [x["post_author"] for x in found["likes"]] == [renamed]


# -- order and limit -----------------------------------------------------------------------


def test_comments_come_by_id_descending_not_by_time() -> None:
    c = Client()
    s = Cast(c)
    posts = [c.make_post(s.mo, "mo note " + str(i)) for i in range(3)]
    cids = []
    for pid in [posts[2], posts[0], posts[1], posts[0]]:
        c.tick(1000)
        cids.append(c.comment(s.kai, pid, "reply to " + str(pid)))
    # created_at order now differs from id order (and from post_id order)
    for cid, shift in zip(cids, [9000, -9000, 5000, -5000], strict=True):
        c.db.run("UPDATE comments SET created_at = ? WHERE id = ?", c.now + shift, cid)
    c.unfriend(s.mo, s.kai)
    found = activity(c, s.kai)["comments"]
    assert [k["id"] for k in found] == [cids[3], cids[2], cids[1], cids[0]]
    assert found == [comment_item(c, cid, s.mo) for cid in reversed(cids)]


def test_likes_come_newest_first_ties_by_post_id_descending() -> None:
    c = Client()
    s = Cast(c)
    p = [c.make_post(s.nia, "nia note " + str(i)) for i in range(6)]
    c.tick(1000)
    c.like(s.kai, p[1])
    c.tick(1000)
    c.like(s.kai, p[0])  # a tie, liked low id first
    c.like(s.kai, p[4])
    c.tick(1000)
    c.like(s.kai, p[5])  # a tie, liked high id first
    c.like(s.kai, p[2])
    c.tick(1000)
    c.like(s.kai, p[3])
    c.unfriend(s.kai, s.nia)
    found = activity(c, s.kai)["likes"]
    order = [p[3], p[5], p[2], p[4], p[0], p[1]]
    assert [x["post_id"] for x in found] == order
    assert found == [like_item(c, pid, s.nia, s.kai) for pid in order]


def test_each_list_holds_at_most_the_newest_100() -> None:
    c = Client()
    s = Cast(c)
    thread = c.make_post(s.omar, "omar's long thread")
    cids = [c.comment(s.kai, thread, "reply " + str(i)) for i in range(101)]
    pids = []
    for i in range(102):
        c.tick(10)
        pids.append(c.make_post(s.omar, "omar daily " + str(i)))
        c.like(s.kai, pids[-1])
    # newer rows on posts I can see take no place in the 100
    c.tick(10)
    for i in range(5):
        seen = c.make_post(s.lena, "lena daily " + str(i))
        c.comment(s.kai, seen, "seen " + str(i))
        c.like(s.kai, seen)
    found = activity(c, s.kai)
    comments, likes = found["comments"], found["likes"]
    assert len(comments) == 100
    assert (comments[0]["id"], comments[-1]["id"]) == (cids[100], cids[1])
    assert [k["id"] for k in comments] == cids[:0:-1]
    assert len(likes) == 100
    assert (likes[0]["post_id"], likes[-1]["post_id"]) == (pids[101], pids[2])
    assert [x["post_id"] for x in likes] == pids[:1:-1]


# -- edges ---------------------------------------------------------------------------------


def test_nothing_hidden_gives_two_empty_lists() -> None:
    c = Client()
    s = Cast(c)
    own = c.make_post(s.kai, "kai alone")
    friend = c.make_post(s.mo, "mo at work")
    stranger = c.make_post(s.omar, "omar at sea")
    for pid in (own, friend):
        c.comment(s.kai, pid, "kai was here")
        c.like(s.kai, pid)
    c.comment(s.pia, stranger, "pia was here")
    c.like(s.lena, stranger)
    r = c.get(URL, user=s.kai)
    assert (r.status, r.json) == (200, EMPTY)
    newbie = c.user("quin", "Quin Quade")
    assert activity(c, newbie) == EMPTY


def test_rows_of_a_deleted_post_are_not_listed() -> None:
    c = Client()
    s = Cast(c)
    gone = c.make_post(s.mo, "mo's deleted post")
    kept = c.make_post(s.mo, "mo's kept post")
    c.comment(s.kai, gone, "on the gone post")
    c.like(s.kai, gone)
    c.comment(s.pia, gone, "pia on the gone post")
    c.like(s.pia, gone)
    cid = c.comment(s.kai, kept, "on the kept post")
    c.like(s.kai, kept)
    c.unfriend(s.kai, s.mo)
    c.db.run("DELETE FROM posts WHERE id = ?", gone)
    # the rows left on the deleted post stay as they are: listing writes nothing
    tables = [
        "SELECT * FROM comments ORDER BY id",
        "SELECT * FROM likes ORDER BY post_id, user_id",
    ]
    before = [c.rows(sql) for sql in tables]
    assert activity(c, s.kai) == {
        "comments": [comment_item(c, cid, s.mo)],
        "likes": [like_item(c, kept, s.mo, s.kai)],
    }
    assert [c.rows(sql) for sql in tables] == before
    assert (len(before[0]), len(before[1])) == (3, 3)


def test_listing_writes_nothing() -> None:
    c = Client()
    s, _ = mixed(c)
    c.friend_request(s.omar, s.kai)
    c.tick(4000)
    tables = [
        # every user column except last_seen_at (the app itself updates the viewer's)
        "SELECT id, username, display_name, bio, password_hash, created_at FROM users ORDER BY id",
        "SELECT * FROM friendships ORDER BY user_id, friend_id",
        "SELECT * FROM friend_requests ORDER BY id",
        "SELECT * FROM sessions ORDER BY token_hash",
        "SELECT * FROM posts ORDER BY id",
        "SELECT * FROM likes ORDER BY post_id, user_id",
        "SELECT * FROM comments ORDER BY id",
    ]
    others = "SELECT * FROM users WHERE id != ? ORDER BY id"
    before = [c.rows(sql) for sql in tables] + [c.rows(others, s.kai.id)]
    found = activity(c, s.kai)
    assert (len(found["comments"]), len(found["likes"])) == (3, 2)
    after = [c.rows(sql) for sql in tables] + [c.rows(others, s.kai.id)]
    assert after == before


def test_login_required() -> None:
    c = Client()
    s = Cast(c)
    pid = c.make_post(s.omar, "omar alone")
    c.comment(s.kai, pid, "hello omar")
    assert c.get(URL).status == 401
    assert c.get(URL, token="not-a-token").status == 401


def test_lives_in_its_own_feature_folder() -> None:
    importlib.import_module("chatbook.features.activity.handler")
