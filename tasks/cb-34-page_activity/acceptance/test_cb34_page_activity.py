import re
from typing import Any

import pytest

from chatbook.testing import CAROL, DAN, ERIN, FRANK, START_MS, UiResult, run_page

GET = "GET /api/activity/hidden"
LOAD = ["GET", "/api/activity/hidden", None]
INTRO = "Your comments and likes on posts you can no longer see"

K31 = {
    "id": 31,
    "post_id": 14,
    "post_author": ERIN,
    "body": "count me in",
    "created_at": START_MS + 300_000,
}
K27 = {
    "id": 27,
    "post_id": 6,
    "post_author": FRANK,
    "body": "<b>loud</b> and clear",
    "created_at": START_MS,
}
K19 = {
    "id": 19,
    "post_id": 20,
    "post_author": DAN,
    "body": "same here",
    "created_at": START_MS + 120_000,
}
LONG = (
    "Thanks for the invite, I will bring the tent, the stove and two folding chairs, "
    "and I can drive three people to the lake on Saturday morning"
)
K42 = {"id": 42, "post_id": 17, "post_author": CAROL, "body": LONG, "created_at": START_MS}
L9 = {"post_id": 9, "post_author": CAROL, "created_at": START_MS + 180_000}
L6 = {"post_id": 6, "post_author": FRANK, "created_at": START_MS + 60_000}
L4 = {"post_id": 4, "post_author": ERIN, "created_at": START_MS + 240_000}
# [K31, K27, K19] (posts 14, 6, 20) and [L4, L9] (posts 4, 9) are server orders (comments by
# id DESC, likes newest first) that are not post_id DESC: the page must not re-sort them.


def answer(comments: list[dict[str, Any]], likes: list[dict[str, Any]]) -> dict[str, Any]:
    return {"comments": comments, "likes": likes}


DATA = answer([K31, K27], [L9, L6])


def open_page(
    *answers: dict[str, Any],
    extra: dict[str, Any] | None = None,
    steps: list[dict[str, Any]] | None = None,
) -> UiResult:
    """Each GET of the page gets the next answer (the last one repeats)."""
    api: dict[str, Any] = {GET: list(answers)}
    return run_page("page_activity", "activity", api=api | (extra or {}), steps=steps)


def page_text(comments: list[dict[str, Any]], likes: list[dict[str, Any]]) -> str:
    """A regex for the whole page text. Each CB.time text is matched by \\S+ (not tested)."""
    parts = [re.escape(INTRO), re.escape(f"Comments ({len(comments)})")]
    rows = [
        re.escape(f"You commented on a post by {k['post_author']['display_name']} {k['body']}")
        + r" \S+ Delete"
        for k in comments
    ]
    parts += rows or ["No comments to remove"]
    parts.append(re.escape(f"Likes ({len(likes)})"))
    rows = [
        re.escape(f"You liked a post by {lk['post_author']['display_name']}") + r" \S+ Unlike"
        for lk in likes
    ]
    parts += rows or ["No likes to remove"]
    return " ".join(parts)


def button_ids(res: UiResult) -> list[str | None]:
    return [b["testid"] for b in res.buttons]


def test_page_is_registered_in_nav_at_order_45() -> None:
    res = run_page("page_activity", None)
    assert res.errors == [] and res.unmatched == []
    assert res.pages == [
        {
            "name": "activity",
            "title": "My activity",
            "nav": "Activity",
            "order": 45,
            "public": False,
            "file": "page_activity",
        }
    ]


def test_loads_once_without_navigating_or_toasting() -> None:
    res = open_page(DATA)
    assert res.errors == [] and res.unmatched == []
    assert (res.page, res.title) == ("activity", "My activity")
    assert res.calls == [LOAD]
    assert res.nav == [] and res.toasts == []


def test_intro_then_comments_then_likes_in_server_order() -> None:
    res = open_page(DATA)
    assert res.errors == [] and res.unmatched == []
    ordered = [
        INTRO,
        "Comments (2)",
        "You commented on a post by Erin Evans count me in",
        "You commented on a post by Frank Fox <b>loud</b> and clear",
        "Likes (2)",
        "You liked a post by Carol Chen",
        "You liked a post by Frank Fox",
    ]
    positions = [res.text.index(part) for part in ordered]
    assert positions == sorted(positions)
    assert re.fullmatch(page_text([K31, K27], [L9, L6]), res.text), res.text
    assert "No comments to remove" not in res.text
    assert "No likes to remove" not in res.text


def test_rows_are_items_with_author_link_and_time() -> None:
    res = open_page(DATA)
    assert res.errors == [] and res.unmatched == []
    assert [c[0] for c in res.classes] == ["stack", "muted"] + ["item", "user-link", "muted"] * 4
    assert res.classes[1] == ["muted", INTRO]
    items = [c[1] for c in res.classes if c[0] == "item"]
    assert items[0].startswith("You commented on a post by Erin Evans count me in ")
    assert items[1].startswith("You commented on a post by Frank Fox <b>loud</b> and clear ")
    assert items[2].startswith("You liked a post by Carol Chen ")
    assert items[3].startswith("You liked a post by Frank Fox ")
    assert [i.rsplit(" ", 1)[1] for i in items] == ["Delete", "Delete", "Unlike", "Unlike"]
    links = [c[1] for c in res.classes if c[0] == "user-link"]
    assert links == ["Erin Evans", "Frank Fox", "Carol Chen", "Frank Fox"]
    times = [c[1] for c in res.classes[2:] if c[0] == "muted"]
    assert len(set(times)) == 4  # each row shows CB.time of its own created_at
    for row in (K31, K27, L9, L6):
        assert str(row["created_at"]) not in res.text  # CB.time, not the raw milliseconds


def test_buttons_use_the_comment_id_and_the_post_id_of_the_like() -> None:
    res = open_page(DATA)
    assert res.errors == [] and res.unmatched == []
    assert res.labels == ["Delete", "Delete", "Unlike", "Unlike"]
    assert res.buttons == [
        {"label": "Delete", "disabled": False, "testid": "delete-31"},
        {"label": "Delete", "disabled": False, "testid": "delete-27"},
        {"label": "Unlike", "disabled": False, "testid": "unlike-9"},
        {"label": "Unlike", "disabled": False, "testid": "unlike-6"},
    ]


@pytest.mark.parametrize(
    ("testid", "path", "reply", "after"),
    [
        ("delete-31", "/api/comments/31", {"deleted": 31}, answer([K27], [L9, L6])),
        ("delete-27", "/api/comments/27", {"deleted": 27}, answer([K31], [L9, L6])),
        ("unlike-9", "/api/posts/9/like", {"post_id": 9, "liked": False}, answer([K31, K27], [L6])),
        ("unlike-6", "/api/posts/6/like", {"post_id": 6, "liked": False}, answer([K31, K27], [L9])),
    ],
    ids=["delete-31", "delete-27", "unlike-9", "unlike-6"],
)
def test_click_sends_delete_then_reloads(
    testid: str, path: str, reply: dict[str, Any], after: dict[str, Any]
) -> None:
    res = open_page(DATA, after, extra={f"DELETE {path}": reply}, steps=[{"click_id": testid}])
    assert res.errors == [] and res.unmatched == []
    assert res.calls == [LOAD, ["DELETE", path, None], LOAD]
    assert res.nav == [] and res.toasts == []
    assert testid not in button_ids(res)
    assert re.fullmatch(page_text(after["comments"], after["likes"]), res.text), res.text


@pytest.mark.parametrize(
    ("testid", "path"),
    [("delete-27", "/api/comments/27"), ("unlike-9", "/api/posts/9/like")],
    ids=["delete", "unlike"],
)
def test_error_answer_toasts_once_and_does_not_reload(testid: str, path: str) -> None:
    gone = {"$status": 404, "error": "post not found"}
    res = open_page(DATA, extra={f"DELETE {path}": gone}, steps=[{"click_id": testid}])
    assert res.errors == [] and res.unmatched == []
    assert res.calls == [LOAD, ["DELETE", path, None]]
    assert res.count("GET", "/api/activity/hidden") == 1
    assert len(res.toasts) == 1
    assert res.nav == []
    assert testid in button_ids(res)


def test_both_lists_empty_show_placeholders() -> None:
    res = open_page(answer([], []))
    assert res.errors == [] and res.unmatched == []
    assert res.calls == [LOAD]
    assert res.text == f"{INTRO} Comments (0) No comments to remove Likes (0) No likes to remove"
    assert res.classes == [
        ["stack", res.text],
        ["muted", INTRO],
        ["muted", "No comments to remove"],
        ["muted", "No likes to remove"],
    ]
    assert res.buttons == []


@pytest.mark.parametrize(
    ("comments", "likes"),
    [([K27], []), ([], [L9]), ([K31, K27, K19], [L4, L9])],
    ids=["only_comments", "only_likes", "three_and_two"],
)
def test_headings_count_the_listed_rows(
    comments: list[dict[str, Any]], likes: list[dict[str, Any]]
) -> None:
    res = open_page(answer(comments, likes))
    assert res.errors == [] and res.unmatched == []
    assert res.calls == [LOAD]
    assert re.fullmatch(page_text(comments, likes), res.text), res.text
    assert button_ids(res) == [f"delete-{k['id']}" for k in comments] + [
        f"unlike-{lk['post_id']}" for lk in likes
    ]


@pytest.mark.parametrize(
    ("name", "uid"), [("Erin Evans", "5"), ("Carol Chen", "3")], ids=["comment", "like"]
)
def test_author_name_opens_the_profile(name: str, uid: str) -> None:
    res = open_page(DATA, steps=[{"click": name}])
    assert res.errors == [] and res.unmatched == []
    assert res.nav == [["profile", {"id": uid}]]
    assert res.calls == [LOAD]
    assert res.toasts == []


@pytest.mark.parametrize(
    "text",
    ["You commented on a post by", "count me in", "You liked a post by"],
    ids=["commented", "body", "liked"],
)
def test_row_text_is_not_a_link_to_the_post(text: str) -> None:
    res = open_page(DATA, steps=[{"click": text}])
    assert res.errors == [f'scenario: no clickable element with text "{text}"']
    assert res.unmatched == []
    assert res.calls == [LOAD]
    assert res.nav == [] and res.toasts == []


@pytest.mark.parametrize("row", [0, 2], ids=["comment", "like"])
def test_row_time_is_not_a_link_to_the_post(row: int) -> None:
    times = [c[1] for c in open_page(DATA).classes[2:] if c[0] == "muted"]
    res = open_page(DATA, steps=[{"click": times[row]}])
    assert res.errors == [f'scenario: no clickable element with text "{times[row]}"']
    assert res.unmatched == []
    assert res.calls == [LOAD]
    assert res.nav == [] and res.toasts == []


def test_page_does_not_poll() -> None:
    res = open_page(DATA, steps=[{"tick": 15000}, {"tick": 60000}, {"tick": 3_600_000}])
    assert res.errors == [] and res.unmatched == []
    assert res.calls == [LOAD]


def test_comment_html_is_shown_as_text() -> None:
    res = open_page(answer([K27], []))
    assert res.errors == [] and res.unmatched == []
    assert "You commented on a post by Frank Fox <b>loud</b> and clear " in res.text
    items = [c[1] for c in res.classes if c[0] == "item"]
    assert len(items) == 1 and "<b>loud</b> and clear" in items[0]


def test_long_comment_body_is_shown_in_full() -> None:
    res = open_page(answer([K42], []))
    assert res.errors == [] and res.unmatched == []
    assert len(LONG) > 100
    assert re.fullmatch(page_text([K42], []), res.text), res.text
    assert f"{LONG} " in res.text and "..." not in res.text


def test_lives_in_its_own_feature_folder() -> None:
    res = run_page("page_activity", None)
    assert res.errors == [] and res.unmatched == []
    assert "activity" in [p["name"] for p in res.pages]
