# Carried from cb-25-comments (harness 2ecb8e5). Changed per owner decision 2026-10-28
# (backlog 10a, 11): a former friend may now delete an own comment; see test_cb32_comments.py.
# The only change: in test_delete_when_the_post_is_hidden_is_404 the case unfriended_author
# became unfriended_other (rosa, after the unfriend, tries to delete tia's comment on sam's
# post), and that parametrize got ids=. Everything else is verbatim.
import importlib
from typing import Any

import pytest

from chatbook.testing import Account, Client


def cast(c: Client) -> tuple[Account, Account, Account, Account, Account]:
    """rosa, sam and tia are all friends; vik is a friend of sam only; ugo knows nobody."""
    rosa = c.user("rosa", "Rosa Reyes")
    sam = c.user("sam", "Sam Stone")
    tia = c.user("tia", "Tia Tran")
    ugo = c.user("ugo", "Ugo Ueda")
    vik = c.user("vik", "Vik Vance")
    c.befriend(rosa, sam)
    c.befriend(sam, tia)
    c.befriend(rosa, tia)
    c.befriend(sam, vik)
    return rosa, sam, tia, ugo, vik


def k(cid: int, pid: int, author: Account, body: str, created_at: int) -> dict[str, Any]:
    return {
        "id": cid,
        "post_id": pid,
        "author": author.json,
        "body": body,
        "created_at": created_at,
    }


def stored(c: Client) -> list[dict[str, Any]]:
    return c.rows("SELECT id, post_id, author_id, body, created_at FROM comments ORDER BY id")


def listing(c: Client, who: Account, pid: object) -> tuple[int, object]:
    r = c.get(f"/api/posts/{pid}/comments", user=who)
    return r.status, r.json


def add(c: Client, who: Account, pid: object, body: object) -> tuple[int, object]:
    r = c.post(f"/api/posts/{pid}/comments", body, user=who)
    return r.status, r.json


def remove(c: Client, who: Account, cid: object) -> tuple[int, object]:
    r = c.delete(f"/api/comments/{cid}", user=who)
    return r.status, r.json


# -- GET /api/posts/{id}/comments ---------------------------------------------------------


def test_list_gives_only_that_posts_comments_in_id_order() -> None:
    c = Client()
    rosa, sam, tia, _, vik = cast(c)
    pid = c.make_post(sam, "trail run at dawn")
    other = c.make_post(rosa, "new bike")
    t0 = c.now
    k1 = c.comment(vik, pid, "first one here")
    c.tick(1500)
    c.comment(tia, other, "shiny")
    k3 = c.comment(tia, pid, "looks cold")
    c.tick(2500)
    k4 = c.comment(sam, pid, "it was freezing")
    c.comment(sam, other, "ride safe")
    expected = {
        "comments": [
            k(k1, pid, vik, "first one here", t0),
            k(k3, pid, tia, "looks cold", t0 + 1500),
            k(k4, pid, sam, "it was freezing", t0 + 4000),
        ]
    }
    # rosa is not a friend of vik but still sees his comment on her friend's post
    for viewer in (rosa, sam, tia, vik):
        assert listing(c, viewer, pid) == (200, expected)


def test_list_orders_by_id_and_returns_stored_values() -> None:
    c = Client()
    rosa, sam, tia, *_ = cast(c)
    pid = c.make_post(rosa, "garden update")
    t0 = c.now
    first = c.comment(sam, pid, "tomatoes?")
    c.tick(3000)
    second = c.comment(rosa, pid, "and basil")
    c.tick(3000)
    third = c.comment(tia, pid, "save me some")
    c.db.run("UPDATE comments SET created_at = ? WHERE id = ?", 1_650_000_000_000, second)
    c.db.run("UPDATE users SET display_name = ? WHERE id = ?", "Samuel S", sam.id)
    renamed = sam.json | {"display_name": "Samuel S"}
    status, body = listing(c, tia, pid)
    assert status == 200
    assert body == {
        "comments": [
            k(first, pid, sam, "tomatoes?", t0) | {"author": renamed},
            k(second, pid, rosa, "and basil", 1_650_000_000_000),
            k(third, pid, tia, "save me some", t0 + 6000),
        ]
    }


def test_list_of_a_post_without_comments_is_empty() -> None:
    c = Client()
    rosa, sam, tia, *_ = cast(c)
    other = c.make_post(sam, "busy thread")
    c.comment(rosa, other, "hey")
    c.comment(tia, other, "hi")
    pid = c.make_post(tia, "quiet day")
    assert listing(c, tia, pid) == (200, {"comments": []})
    assert listing(c, rosa, pid) == (200, {"comments": []})


def test_own_post_is_visible_without_friends() -> None:
    c = Client()
    _, _, _, ugo, _ = cast(c)
    pid = c.make_post(ugo, "talking to myself")
    c.tick(900)
    cid = c.comment(ugo, pid, "echo")
    assert listing(c, ugo, pid) == (200, {"comments": [k(cid, pid, ugo, "echo", c.now)]})


@pytest.mark.parametrize("case", ["stranger", "friend_of_friend", "unfriended", "unknown"])
def test_list_hidden_or_missing_post_is_404(case: str) -> None:
    c = Client()
    rosa, sam, _, ugo, vik = cast(c)
    sams = c.make_post(sam, "sunset")
    rosas = c.make_post(rosa, "sunrise")
    c.comment(rosa, sams, "lovely")
    c.comment(sam, rosas, "early bird")
    if case == "unfriended":
        c.unfriend(rosa, sam)
    who, pid = {
        "stranger": (ugo, sams),
        "friend_of_friend": (vik, rosas),
        "unfriended": (rosa, sams),
        "unknown": (rosa, 4321),
    }[case]
    assert listing(c, who, pid)[0] == 404


@pytest.mark.parametrize("bad", ["abc", "0", "-2", "1.0", "12345678901234567890"])
def test_list_bad_post_id_is_404(bad: str) -> None:
    c = Client()
    rosa, *_ = cast(c)
    pid = c.make_post(rosa, "anything")
    c.comment(rosa, pid, "self reply")
    assert listing(c, rosa, bad)[0] == 404


# -- POST /api/posts/{id}/comments --------------------------------------------------------


def test_add_returns_201_with_the_comment_and_stores_it() -> None:
    c = Client()
    rosa, sam, tia, _, vik = cast(c)
    pid = c.make_post(sam, "trail run at dawn")
    other = c.make_post(tia, "lunch")
    t0 = c.now
    c.comment(vik, pid, "wow")
    c.comment(rosa, other, "yum")
    c.tick(7250)
    status, body = add(c, tia, pid, {"body": "  count me in  "})
    expected = k(3, pid, tia, "count me in", c.now)
    assert (status, body) == (201, {"comment": expected})
    assert stored(c) == [
        {"id": 1, "post_id": pid, "author_id": vik.id, "body": "wow", "created_at": t0},
        {"id": 2, "post_id": other, "author_id": rosa.id, "body": "yum", "created_at": t0},
        {"id": 3, "post_id": pid, "author_id": tia.id, "body": "count me in", "created_at": c.now},
    ]
    assert listing(c, sam, pid) == (200, {"comments": [k(1, pid, vik, "wow", t0), expected]})


def test_add_by_a_friend_who_is_not_a_friend_of_other_commenters() -> None:
    c = Client()
    rosa, sam, _, _, vik = cast(c)
    pid = c.make_post(sam, "bbq saturday")
    c.comment(rosa, pid, "bringing salad")
    c.tick(60_000)
    status, body = add(c, vik, pid, {"body": "I'll bring drinks"})
    assert (status, body) == (201, {"comment": k(2, pid, vik, "I'll bring drinks", c.now)})


def test_post_author_may_comment_on_own_post() -> None:
    c = Client()
    rosa, sam, _, ugo, _ = cast(c)
    sams = c.make_post(sam, "moving day")
    ugos = c.make_post(ugo, "nobody reads this")
    c.tick(40)
    assert add(c, ugo, ugos, {"body": "still here"}) == (
        201,
        {"comment": k(1, ugos, ugo, "still here", c.now)},
    )
    c.tick(40)
    assert add(c, sam, sams, {"body": "boxes everywhere"}) == (
        201,
        {"comment": k(2, sams, sam, "boxes everywhere", c.now)},
    )
    assert [r["author_id"] for r in stored(c)] == [ugo.id, sam.id]
    assert rosa.id not in [r["author_id"] for r in stored(c)]


@pytest.mark.parametrize(
    ("raw", "text"),
    [
        ("k", "k"),
        ("q" * 1000, "q" * 1000),
        ("\n  " + "q" * 1000 + " \t", "q" * 1000),
        ("two  spaces\nnew line", "two  spaces\nnew line"),
    ],
    ids=["one_char", "1000_chars", "1000_chars_padded", "inner_spaces_newline"],
)
def test_add_strips_and_accepts_1_to_1000_characters(raw: str, text: str) -> None:
    c = Client()
    rosa, sam, *_ = cast(c)
    pid = c.make_post(rosa, "caption contest")
    status, body = add(c, sam, pid, {"body": raw})
    assert (status, body) == (201, {"comment": k(1, pid, sam, text, c.now)})
    assert [r["body"] for r in stored(c)] == [text]


@pytest.mark.parametrize(
    "payload",
    [
        {"body": ""},
        {"body": "    "},
        {"body": "\n\t "},
        {"body": "w" * 1001},
        {"body": "  " + "w" * 1001 + "  "},
        {"body": 42},
        {"body": None},
        {"body": True},
        {"body": ["hey"]},
        {"body": {"text": "hey"}},
        {},
        {"text": "hey"},
        ["hey"],
        "hey",
        None,
        5,
    ],
)
def test_add_bad_body_is_400_and_stores_nothing(payload: object) -> None:
    c = Client()
    rosa, sam, *_ = cast(c)
    pid = c.make_post(sam, "poll: tea or coffee")
    c.comment(sam, pid, "tea")
    before = stored(c)
    assert add(c, rosa, pid, payload)[0] == 400
    assert stored(c) == before


@pytest.mark.parametrize(
    "case", ["stranger", "friend_of_friend", "unfriended", "unknown", "bad_id", "zero_id"]
)
def test_add_to_hidden_or_missing_post_is_404(case: str) -> None:
    c = Client()
    rosa, sam, _, ugo, vik = cast(c)
    sams = c.make_post(sam, "sunset")
    rosas = c.make_post(rosa, "sunrise")
    c.comment(sam, rosas, "early bird")
    if case == "unfriended":
        c.unfriend(rosa, sam)
    who, pid = {
        "stranger": (ugo, str(sams)),
        "friend_of_friend": (vik, str(rosas)),
        "unfriended": (rosa, str(sams)),
        "unknown": (rosa, "4321"),
        "bad_id": (rosa, "x1"),
        "zero_id": (rosa, "0"),
    }[case]
    before = stored(c)
    assert add(c, who, pid, {"body": "can I join?"})[0] == 404
    assert stored(c) == before


def test_add_checks_the_post_before_the_body() -> None:
    c = Client()
    rosa, sam, _, ugo, _ = cast(c)
    pid = c.make_post(sam, "sunset")
    assert add(c, ugo, pid, {"body": "   "})[0] == 404
    assert add(c, rosa, 909, {"body": 3})[0] == 404
    assert stored(c) == []


# -- DELETE /api/comments/{id} ------------------------------------------------------------


def test_comment_author_deletes_own_comment() -> None:
    c = Client()
    rosa, sam, tia, *_ = cast(c)
    other = c.make_post(tia, "recipe")
    pid = c.make_post(sam, "concert tonight")
    c.comment(tia, other, "secret sauce")
    typo = c.comment(rosa, pid, "see you thier")
    keep = c.comment(rosa, pid, "see you there")
    c.comment(tia, pid, "me too")
    assert remove(c, rosa, typo) == (200, {"deleted": typo})
    assert [r["id"] for r in stored(c)] == [1, keep, 4]
    assert typo == 2


def test_post_author_deletes_any_comment_on_their_post() -> None:
    c = Client()
    rosa, sam, tia, _, vik = cast(c)
    pid = c.make_post(sam, "garage sale")
    elsewhere = c.make_post(rosa, "unrelated")
    by_vik = c.comment(vik, pid, "how much for the lamp")
    by_rosa = c.comment(rosa, elsewhere, "not this one")
    by_tia = c.comment(tia, pid, "spam spam")
    by_sam = c.comment(sam, pid, "sold out")
    assert remove(c, sam, by_vik) == (200, {"deleted": by_vik})
    assert remove(c, sam, by_tia) == (200, {"deleted": by_tia})
    assert remove(c, sam, by_sam) == (200, {"deleted": by_sam})
    assert [r["id"] for r in stored(c)] == [by_rosa]


def test_post_author_deletes_a_comment_by_a_former_friend() -> None:
    c = Client()
    _, sam, _, _, vik = cast(c)
    pid = c.make_post(sam, "rant")
    cid = c.comment(vik, pid, "rude remark")
    c.unfriend(sam, vik)
    assert remove(c, sam, cid) == (200, {"deleted": cid})
    assert stored(c) == []


@pytest.mark.parametrize("case", ["tia_on_rosas", "vik_on_rosas", "rosa_on_tias"])
def test_other_viewers_cannot_delete_403(case: str) -> None:
    c = Client()
    rosa, sam, tia, _, vik = cast(c)
    pid = c.make_post(sam, "photo dump")
    by_rosa = c.comment(rosa, pid, "great pics")
    by_tia = c.comment(tia, pid, "where was this")
    # rosa and tia also wrote posts of their own; that does not make them authors of sam's post
    c.comment(rosa, c.make_post(tia, "tia's own post"), "nice one")
    c.comment(tia, c.make_post(rosa, "rosa's own post"), "cool")
    actor, cid = {
        "tia_on_rosas": (tia, by_rosa),
        "vik_on_rosas": (vik, by_rosa),
        "rosa_on_tias": (rosa, by_tia),
    }[case]
    before = stored(c)
    assert remove(c, actor, cid)[0] == 403
    assert stored(c) == before


@pytest.mark.parametrize(
    "case",
    ["stranger", "unfriended_other", "friend_of_friend"],
    ids=["stranger", "unfriended_other", "friend_of_friend"],
)
def test_delete_when_the_post_is_hidden_is_404(case: str) -> None:
    c = Client()
    rosa, sam, tia, ugo, vik = cast(c)
    sams = c.make_post(sam, "hiking")
    rosas = c.make_post(rosa, "baking")
    on_sams = c.comment(rosa, sams, "which trail?")
    on_rosas = c.comment(tia, rosas, "smells good")
    by_tia = c.comment(tia, sams, "nice view")
    if case == "unfriended_other":
        c.unfriend(rosa, sam)
    actor, cid = {
        "stranger": (ugo, on_sams),
        "unfriended_other": (rosa, by_tia),
        "friend_of_friend": (vik, on_rosas),
    }[case]
    before = stored(c)
    assert remove(c, actor, cid)[0] == 404
    assert stored(c) == before


@pytest.mark.parametrize("bad", ["999", "abc", "0", "-1", "2.5", "12345678901234567890"])
def test_delete_unknown_or_bad_comment_id_is_404(bad: str) -> None:
    c = Client()
    rosa, sam, *_ = cast(c)
    pid = c.make_post(sam, "one comment")
    c.comment(sam, pid, "first")
    c.comment(rosa, pid, "second")
    before = stored(c)
    assert remove(c, sam, bad)[0] == 404
    assert stored(c) == before


def test_delete_twice_is_404_the_second_time() -> None:
    c = Client()
    rosa, sam, *_ = cast(c)
    pid = c.make_post(sam, "flash sale")
    c.comment(sam, pid, "opening")
    cid = c.comment(rosa, pid, "oops")
    assert remove(c, rosa, cid) == (200, {"deleted": cid})
    assert remove(c, rosa, cid)[0] == 404
    assert remove(c, sam, cid)[0] == 404
    assert [r["id"] for r in stored(c)] == [1]


def test_lives_in_its_own_feature_folder() -> None:
    importlib.import_module("chatbook.features.comments.handler")
