from typing import Any

import pytest

from chatbook.testing import (
    ALICE,
    CAROL,
    DAN,
    ERIN,
    FRANK,
    START_MS,
    UiResult,
    fake_post,
    run_page,
)

LAKE = fake_post(7, ERIN, "sunset at the lake", like_count=3)


def k(cid: int, author: dict[str, Any], body: str, pid: int = 7) -> dict[str, Any]:
    return {
        "id": cid,
        "post_id": pid,
        "author": dict(author),
        "body": body,
        "created_at": START_MS + cid * 60_000,
    }


K21 = k(21, ALICE, "gorgeous colours")
K22 = k(22, FRANK, "where is this")
K23 = k(23, ERIN, "thanks both")


def gets(pid: int) -> list[list[Any]]:
    return [
        ["GET", f"/api/posts/{pid}", None],
        ["GET", f"/api/posts/{pid}/comments", None],
    ]


def open_post(
    post: Any = LAKE,
    comments: Any = None,
    *,
    me: dict[str, Any] = ALICE,
    extra: dict[str, Any] | None = None,
    steps: list[dict[str, Any]] | None = None,
) -> UiResult:
    """`post` and `comments` are one answer each, or a list of answers consumed in order."""
    first = post[0] if isinstance(post, list) else post
    pid = first["id"]
    if comments is None:
        comments = [K21, K22]
    if comments and isinstance(comments[0], list):
        comment_answers: Any = [{"comments": c} for c in comments]
    else:
        comment_answers = {"comments": comments}
    post_answers = [{"post": p} for p in post] if isinstance(post, list) else {"post": post}
    api: dict[str, Any] = {
        f"GET /api/posts/{pid}": post_answers,
        f"GET /api/posts/{pid}/comments": comment_answers,
    }
    return run_page(
        "page_post",
        "post",
        params={"id": str(pid)},
        me=me,
        api=api | (extra or {}),
        steps=steps,
    )


def items(res: UiResult) -> list[str]:
    return [c[1] for c in res.classes if c[0] == "item"]


def delete_ids(res: UiResult) -> list[str | None]:
    return [b["testid"] for b in res.buttons if b["label"] == "Delete"]


def test_page_is_registered_without_nav() -> None:
    res = run_page("page_post", None)
    assert res.errors == [] and res.unmatched == []
    assert res.pages == [
        {
            "name": "post",
            "title": "Post",
            "nav": None,
            "order": 100,
            "public": False,
            "file": "page_post",
        }
    ]


def test_loads_post_then_comments_and_renders_in_order() -> None:
    res = open_post()
    assert res.errors == [] and res.unmatched == []
    assert (res.page, res.title) == ("post", "Post")
    assert res.calls == gets(7)
    assert res.classes[0][0] == "stack"
    assert res.labels == ["Back to feed", "Like (3)", "Delete", "Comment"]
    assert [b["testid"] for b in res.buttons[1:3]] == ["like-7", "delete-21"]

    cards = [c[1] for c in res.classes if c[0] == "card"]
    assert len(cards) == 1
    assert cards[0].startswith("Erin Evans ")
    assert cards[0].endswith(" sunset at the lake Like (3)")
    rows = [c[1] for c in res.classes if c[0] == "row"]
    assert len(rows) == 1 and rows[0].startswith("Erin Evans ")
    assert "sunset" not in rows[0]
    links = [c[1] for c in res.classes if c[0] == "user-link"]
    assert links == ["Erin Evans", "Alice Adams", "Frank Fox"]
    assert [c for c in res.classes if c[0] == "avatar"] == [["avatar", ""]] * 3
    assert len([c for c in res.classes if c[0] == "muted"]) == 3

    found = items(res)
    assert len(found) == 2
    assert found[0].startswith("Alice Adams gorgeous colours ")
    assert found[0].endswith(" Delete")
    assert found[1].startswith("Frank Fox where is this ")
    assert "Delete" not in found[1]

    assert "Comments (2)" in res.text
    assert "No comments yet" not in res.text
    assert res.forms == [
        {
            "submit": "Comment",
            "fields": ["body"],
            "types": {"body": "text"},
            "options": {},
            "values": {"body": ""},
        }
    ]
    ordered = [
        "Back to feed",
        "Erin Evans",
        "sunset at the lake",
        "Like (3)",
        "Comments (2)",
        "Alice Adams",
        "gorgeous colours",
        "Frank Fox",
        "where is this",
        "Write a comment",
    ]
    positions = [res.text.index(part) for part in ordered]
    assert positions == sorted(positions)
    assert res.text.endswith(" Write a comment Comment")


@pytest.mark.parametrize(
    ("me", "author", "expected"),
    [
        (ALICE, ERIN, ["delete-21"]),
        (FRANK, ERIN, ["delete-22"]),
        (ERIN, ERIN, ["delete-21", "delete-22", "delete-23"]),
        (CAROL, ERIN, []),
        (ALICE, ALICE, ["delete-21", "delete-22", "delete-23"]),
        (DAN, DAN, ["delete-21", "delete-22", "delete-23"]),
    ],
    ids=["own", "other-own", "post-author", "stranger", "author-commented", "author-silent"],
)
def test_delete_shown_for_comment_author_or_post_author(
    me: dict[str, Any], author: dict[str, Any], expected: list[str]
) -> None:
    post = fake_post(7, author, "sunset at the lake")
    res = open_post(post, [K21, K22, K23], me=me)
    assert res.errors == [] and res.unmatched == []
    assert "Comments (3)" in res.text
    assert len(items(res)) == 3
    assert delete_ids(res) == expected
    assert [i.endswith(" Delete") for i in items(res)] == [
        f"delete-{c['id']}" in expected for c in (K21, K22, K23)
    ]


def test_clicking_delete_removes_the_comment_and_reloads() -> None:
    res = open_post(
        comments=[[K21, K22], [K22]],
        extra={"DELETE /api/comments/21": {"deleted": 21}},
        steps=[{"click_id": "delete-21"}],
    )
    assert res.errors == [] and res.unmatched == []
    assert res.nav == [] and res.toasts == []
    assert res.calls == [*gets(7), ["DELETE", "/api/comments/21", None], *gets(7)]
    assert "Comments (1)" in res.text
    assert "gorgeous colours" not in res.text
    assert "where is this" in res.text
    assert "Delete" not in res.labels


def test_post_author_deletes_another_users_comment() -> None:
    post = fake_post(12, DAN, "first snow", comment_count=2)
    k31 = k(31, CAROL, "so early this year", pid=12)
    k34 = k(34, FRANK, "brr", pid=12)
    res = open_post(
        post,
        [[k31, k34], [k31]],
        me=DAN,
        extra={"DELETE /api/comments/34": {"deleted": 34}},
        steps=[{"click_id": "delete-34"}],
    )
    assert res.errors == [] and res.unmatched == []
    assert res.nav == [] and res.toasts == []
    assert res.calls == [*gets(12), ["DELETE", "/api/comments/34", None], *gets(12)]
    assert "Comments (1)" in res.text
    assert "brr" not in res.text
    assert delete_ids(res) == ["delete-31"]


def test_like_posts_then_refreshes() -> None:
    liked = LAKE | {"liked": True, "like_count": 4}
    res = open_post(
        [LAKE, liked],
        extra={"POST /api/posts/7/like": {"post_id": 7, "like_count": 4, "liked": True}},
        steps=[{"click_id": "like-7"}],
    )
    assert res.errors == [] and res.unmatched == []
    assert res.nav == [] and res.toasts == []
    assert res.calls == [*gets(7), ["POST", "/api/posts/7/like", None], *gets(7)]
    assert "Unlike (4)" in res.labels
    assert "Like (3)" not in res.labels


def test_unlike_deletes_then_refreshes() -> None:
    liked = fake_post(12, FRANK, "first snow", like_count=1, liked=True)
    before = open_post(liked, [])
    assert before.errors == [] and before.unmatched == []
    assert before.labels == ["Back to feed", "Unlike (1)", "Comment"]
    assert before.buttons[1]["testid"] == "like-12"

    res = open_post(
        [liked, liked | {"liked": False, "like_count": 0}],
        [],
        extra={"DELETE /api/posts/12/like": {"post_id": 12, "like_count": 0, "liked": False}},
        steps=[{"click_id": "like-12"}],
    )
    assert res.errors == [] and res.unmatched == []
    assert res.nav == [] and res.toasts == []
    assert res.calls == [*gets(12), ["DELETE", "/api/posts/12/like", None], *gets(12)]
    assert "Like (0)" in res.labels
    assert res.count("POST", "/api/posts/12/like") == 0


@pytest.mark.parametrize("pid", [7, 12])
def test_comment_form_trims_posts_and_refreshes(pid: int) -> None:
    post = LAKE | {"id": pid}
    first = [k(41, CAROL, "lovely", pid=pid)]
    added = k(42, ALICE, "lovely light", pid=pid)
    res = open_post(
        post,
        [first, [*first, added]],
        extra={f"POST /api/posts/{pid}/comments": {"comment": added}},
        steps=[{"submit": "Comment", "values": {"body": "  lovely light "}}],
    )
    assert res.errors == [] and res.unmatched == []
    assert res.nav == [] and res.toasts == []
    assert res.calls == [
        *gets(pid),
        ["POST", f"/api/posts/{pid}/comments", {"body": "lovely light"}],
        *gets(pid),
    ]
    assert "Comments (2)" in res.text
    assert "Alice Adams lovely light" in res.text
    assert res.forms[0]["values"] == {"body": ""}


def test_like_refreshes_in_place_and_keeps_the_comment_draft() -> None:
    liked = LAKE | {"liked": True, "like_count": 4}
    res = open_post(
        [LAKE, liked],
        extra={"POST /api/posts/7/like": {"post_id": 7, "like_count": 4, "liked": True}},
        steps=[
            {"fill": "Comment", "values": {"body": "half a thought"}},
            {"click_id": "like-7"},
        ],
    )
    assert res.errors == [] and res.unmatched == []
    assert res.nav == []
    assert res.calls == [*gets(7), ["POST", "/api/posts/7/like", None], *gets(7)]
    assert res.forms[0]["values"] == {"body": "half a thought"}


@pytest.mark.parametrize("body", ["   ", ""], ids=["spaces", "empty"])
def test_blank_comment_is_not_posted(body: str) -> None:
    res = open_post(steps=[{"submit": "Comment", "values": {"body": body}}])
    assert res.errors == [] and res.unmatched == []
    assert res.calls == gets(7)
    assert "Comments (2)" in res.text


def test_no_comments_shows_placeholder() -> None:
    res = open_post(comments=[])
    assert res.errors == [] and res.unmatched == []
    assert res.calls == gets(7)
    assert "Comments (0)" in res.text
    assert ["muted", "No comments yet"] in res.classes
    assert items(res) == []
    assert res.labels == ["Back to feed", "Like (3)", "Comment"]
    positions = [res.text.index(p) for p in ("Comments (0)", "No comments yet", "Write a comment")]
    assert positions == sorted(positions)


def test_back_to_feed_navigates_without_params() -> None:
    res = open_post(steps=[{"click": "Back to feed"}])
    assert res.errors == [] and res.unmatched == []
    assert res.nav == [["feed", {}]]
    assert res.calls == gets(7)


def test_page_does_not_poll() -> None:
    res = open_post(steps=[{"tick": 15000}, {"tick": 60000}])
    assert res.errors == [] and res.unmatched == []
    assert res.calls == gets(7)


def test_lives_in_its_own_feature_folder() -> None:
    res = run_page("page_post", None)
    assert res.errors == [] and res.unmatched == []
    assert "post" in [p["name"] for p in res.pages]
