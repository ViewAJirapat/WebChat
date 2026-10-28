from typing import Any

import pytest

from chatbook.testing import (
    ALICE,
    CAROL,
    DAN,
    ERIN,
    FRANK,
    UiResult,
    fake_post,
    run_page,
)

FEED_20 = "GET /api/feed?limit=20"

P21 = fake_post(21, ALICE, "Fresh bread from the market", like_count=1, liked=True)
P17 = fake_post(17, ERIN, "Anyone up for a hike on Sunday", like_count=7, comment_count=3)
P9 = fake_post(9, CAROL, "Concert tickets are sold out", comment_count=1)
POSTS = [P21, P17, P9]


def feed(posts: list[dict[str, Any]], has_more: bool) -> dict[str, Any]:
    return {"posts": posts, "has_more": has_more}


def base_api(**over: Any) -> dict[str, Any]:
    api: dict[str, Any] = {
        FEED_20: feed(POSTS, True),
        "POST /api/posts/17/like": {"post_id": 17, "like_count": 8, "liked": True},
        "POST /api/posts/9/like": {"post_id": 9, "like_count": 1, "liked": True},
        "DELETE /api/posts/21/like": {"post_id": 21, "like_count": 0, "liked": False},
        "DELETE /api/posts/21": {"deleted": 21},
    }
    api.update(over)
    return api


def open_feed(
    api: dict[str, Any] | None = None,
    steps: list[dict[str, Any]] | None = None,
    params: dict[str, str] | None = None,
    me: dict[str, Any] = ALICE,
) -> UiResult:
    return run_page(
        "page_feed",
        "feed",
        params=params,
        me=me,
        api=base_api() if api is None else api,
        steps=steps,
    )


def delete_ids(res: UiResult) -> list[Any]:
    return [b["testid"] for b in res.buttons if b["label"] == "Delete"]


def test_page_is_registered_in_nav_at_order_40() -> None:
    res = run_page("page_feed", None)
    assert res.errors == [] and res.unmatched == []
    assert res.pages == [
        {
            "name": "feed",
            "title": "Feed",
            "nav": "Feed",
            "order": 40,
            "public": False,
            "file": "page_feed",
        }
    ]


def test_renders_form_cards_and_show_more_in_order() -> None:
    res = open_feed()
    assert res.errors == [] and res.unmatched == []
    assert (res.page, res.title) == ("feed", "Feed")
    assert res.calls == [["GET", "/api/feed?limit=20", None]]
    assert res.forms == [
        {
            "submit": "Post",
            "fields": ["body"],
            "types": {"body": "textarea"},
            "options": {},
            "values": {"body": ""},
        }
    ]
    assert res.text.startswith("What is on your mind? Post ")
    assert res.labels == [
        "Post",
        "Unlike (1)",
        "Comments (0)",
        "Delete",
        "Like (7)",
        "Comments (3)",
        "Like (0)",
        "Comments (1)",
        "Show more",
    ]
    assert [b["testid"] for b in res.buttons] == [
        None,
        "like-21",
        "comments-21",
        "delete-21",
        "like-17",
        "comments-17",
        "like-9",
        "comments-9",
        None,
    ]
    assert [c[0] for c in res.classes] == ["stack"] + [
        "card",
        "row",
        "avatar",
        "user-link",
        "muted",
        "row",
    ] * 3
    assert [c for c in res.classes if c[0] == "user-link"] == [
        ["user-link", "Alice Adams"],
        ["user-link", "Erin Evans"],
        ["user-link", "Carol Chen"],
    ]
    assert [c for c in res.classes if c[0] == "avatar"] == [["avatar", ""]] * 3
    cards = [c[1] for c in res.classes if c[0] == "card"]
    assert cards[0].startswith("Alice Adams ")
    assert cards[0].endswith(" Fresh bread from the market Unlike (1) Comments (0) Delete")
    assert cards[1].startswith("Erin Evans ")
    assert cards[1].endswith(" Anyone up for a hike on Sunday Like (7) Comments (3)")
    assert cards[2].startswith("Carol Chen ")
    assert cards[2].endswith(" Concert tickets are sold out Like (0) Comments (1)")
    rows = [c[1] for c in res.classes if c[0] == "row"]
    assert rows[1::2] == [
        "Unlike (1) Comments (0) Delete",
        "Like (7) Comments (3)",
        "Like (0) Comments (1)",
    ]
    assert [r.split(" ")[0] for r in rows[0::2]] == ["Alice", "Erin", "Carol"]
    assert all(c[1] for c in res.classes if c[0] == "muted")
    assert "No posts yet" not in res.text


def test_cards_follow_the_server_order() -> None:
    p5 = fake_post(5, DAN, "Lost my keys again", like_count=12)
    res = open_feed(api={FEED_20: feed([P9, p5, P17], False)})
    assert res.errors == [] and res.unmatched == []
    assert res.labels == [
        "Post",
        "Like (0)",
        "Comments (1)",
        "Like (12)",
        "Comments (0)",
        "Like (7)",
        "Comments (3)",
    ]
    assert [c[1] for c in res.classes if c[0] == "user-link"] == [
        "Carol Chen",
        "Dan Diaz",
        "Erin Evans",
    ]
    assert delete_ids(res) == []
    assert "Show more" not in res.labels


@pytest.mark.parametrize(
    ("testid", "method", "path"),
    [
        ("like-17", "POST", "/api/posts/17/like"),
        ("like-9", "POST", "/api/posts/9/like"),
        ("like-21", "DELETE", "/api/posts/21/like"),
    ],
    ids=["like-17", "like-9", "unlike-21"],
)
def test_like_button_toggles_and_refreshes(testid: str, method: str, path: str) -> None:
    res = open_feed(steps=[{"click_id": testid}])
    assert res.errors == [] and res.unmatched == []
    assert res.calls == [
        ["GET", "/api/feed?limit=20", None],
        [method, path, None],
        ["GET", "/api/feed?limit=20", None],
    ]
    assert res.nav == []


def test_like_refresh_shows_the_new_answer() -> None:
    liked_17 = P17 | {"liked": True, "like_count": 8}
    api = base_api(**{FEED_20: [feed(POSTS, True), feed([P21, liked_17, P9], True)]})
    res = open_feed(api=api, steps=[{"click_id": "like-17"}])
    assert res.errors == [] and res.unmatched == []
    assert res.count("GET", "/api/feed?limit=20") == 2
    assert "Unlike (8)" in res.labels
    assert "Like (7)" not in res.labels
    assert ["row", "Unlike (8) Comments (3)"] in res.classes


@pytest.mark.parametrize("pid", ["17", "21", "9"])
def test_comments_button_opens_the_post_page(pid: str) -> None:
    res = open_feed(steps=[{"click_id": "comments-" + pid}])
    assert res.errors == [] and res.unmatched == []
    assert res.nav == [["post", {"id": pid}]]
    assert res.calls == [["GET", "/api/feed?limit=20", None]]


def test_delete_shown_only_on_own_posts_and_deletes() -> None:
    api = base_api(**{FEED_20: [feed(POSTS, True), feed([P17, P9], True)]})
    first = open_feed(api=api)
    assert first.errors == [] and first.unmatched == []
    assert delete_ids(first) == ["delete-21"]

    res = open_feed(api=api, steps=[{"click_id": "delete-21"}])
    assert res.errors == [] and res.unmatched == []
    assert res.calls == [
        ["GET", "/api/feed?limit=20", None],
        ["DELETE", "/api/posts/21", None],
        ["GET", "/api/feed?limit=20", None],
    ]
    assert res.nav == []
    assert "Fresh bread from the market" not in res.text
    assert delete_ids(res) == []


@pytest.mark.parametrize(
    ("me", "expected"),
    [(ERIN, ["delete-17"]), (CAROL, ["delete-9"]), (FRANK, [])],
    ids=["erin", "carol", "frank"],
)
def test_delete_follows_the_logged_in_user(me: dict[str, Any], expected: list[str]) -> None:
    res = open_feed(me=me)
    assert res.errors == [] and res.unmatched == []
    assert delete_ids(res) == expected
    assert len([lb for lb in res.labels if lb.startswith("Comments (")]) == 3


def test_delete_of_another_users_own_post() -> None:
    api = base_api(
        **{
            FEED_20: [feed(POSTS, True), feed([P21, P9], True)],
            "DELETE /api/posts/17": {"deleted": 17},
        }
    )
    res = open_feed(api=api, me=ERIN, steps=[{"click_id": "delete-17"}])
    assert res.errors == [] and res.unmatched == []
    assert ["DELETE", "/api/posts/17", None] in res.calls
    assert res.count("DELETE", "/api/posts/21") == 0
    assert res.count("GET", "/api/feed?limit=20") == 2
    assert res.nav == []
    assert "Anyone up for a hike on Sunday" not in res.text


@pytest.mark.parametrize(
    ("typed", "sent"),
    [
        ("  sunny day \n", "sunny day"),
        ("\tline one\nline two  ", "line one\nline two"),
    ],
    ids=["spaces", "two-lines"],
)
def test_post_form_trims_posts_and_refreshes(typed: str, sent: str) -> None:
    mine = fake_post(30, ALICE, sent)
    api = base_api(
        **{
            FEED_20: [feed(POSTS, True), feed([mine, *POSTS], True)],
            "POST /api/posts": {"post": mine},
        }
    )
    res = open_feed(api=api, steps=[{"submit": "Post", "values": {"body": typed}}])
    assert res.errors == [] and res.unmatched == []
    assert res.calls == [
        ["GET", "/api/feed?limit=20", None],
        ["POST", "/api/posts", {"body": sent}],
        ["GET", "/api/feed?limit=20", None],
    ]
    assert res.nav == []
    assert res.forms[0]["values"] == {"body": ""}
    assert delete_ids(res) == ["delete-30", "delete-21"]


@pytest.mark.parametrize("typed", ["", "    ", " \n\t "], ids=["empty", "spaces", "whitespace"])
def test_blank_post_is_not_sent(typed: str) -> None:
    res = open_feed(steps=[{"submit": "Post", "values": {"body": typed}}])
    assert res.errors == [] and res.unmatched == []
    assert res.calls == [["GET", "/api/feed?limit=20", None]]


def test_show_more_adds_20_to_the_default_limit() -> None:
    api = base_api(**{"GET /api/feed?limit=40": feed([*POSTS, P9 | {"id": 3}], False)})
    res = open_feed(api=api, steps=[{"click": "Show more"}])
    assert res.errors == [] and res.unmatched == []
    assert res.nav == [["feed", {"limit": "40"}]]
    assert res.calls == [
        ["GET", "/api/feed?limit=20", None],
        ["GET", "/api/feed?limit=40", None],
    ]
    assert "Show more" not in res.labels
    assert len([c for c in res.classes if c[0] == "card"]) == 4


def test_limit_param_is_used_and_grows_by_20() -> None:
    api = {
        "GET /api/feed?limit=35": feed(POSTS, True),
        "GET /api/feed?limit=55": feed(POSTS, True),
    }
    res = open_feed(api=api, params={"limit": "35"}, steps=[{"click": "Show more"}])
    assert res.errors == [] and res.unmatched == []
    assert res.calls == [
        ["GET", "/api/feed?limit=35", None],
        ["GET", "/api/feed?limit=55", None],
    ]
    assert res.nav == [["feed", {"limit": "55"}]]


@pytest.mark.parametrize(
    ("testid", "method", "path"),
    [
        ("like-17", "POST", "/api/posts/17/like"),
        ("delete-21", "DELETE", "/api/posts/21"),
    ],
    ids=["like-17", "delete-21"],
)
def test_actions_refresh_in_place_and_keep_limit_and_draft(
    testid: str, method: str, path: str
) -> None:
    api = base_api(**{"GET /api/feed?limit=35": feed(POSTS, True)})
    steps: list[dict[str, Any]] = [
        {"fill": "Post", "values": {"body": "half-typed draft"}},
        {"click_id": testid},
    ]
    res = open_feed(api=api, params={"limit": "35"}, steps=steps)
    assert res.errors == [] and res.unmatched == []
    assert res.calls == [
        ["GET", "/api/feed?limit=35", None],
        [method, path, None],
        ["GET", "/api/feed?limit=35", None],
    ]
    assert res.nav == []
    assert res.forms[0]["values"] == {"body": "half-typed draft"}


def test_no_show_more_without_has_more() -> None:
    res = open_feed(api={FEED_20: feed(POSTS, False)})
    assert res.errors == [] and res.unmatched == []
    assert "Show more" not in res.labels
    assert res.labels[-1] == "Comments (1)"


def test_empty_feed_shows_no_posts_yet() -> None:
    res = open_feed(api={FEED_20: feed([], False)})
    assert res.errors == [] and res.unmatched == []
    assert res.calls == [["GET", "/api/feed?limit=20", None]]
    assert "No posts yet" in res.text
    assert [c[0] for c in res.classes] == ["stack", "muted"]
    assert ["muted", "No posts yet"] in res.classes
    assert res.labels == ["Post"]
    assert res.text.index("What is on your mind?") < res.text.index("No posts yet")


def test_polls_the_feed_every_15000_ms() -> None:
    api = base_api(**{FEED_20: [feed(POSTS, True), feed([P17], False)]})
    early = open_feed(api=api, steps=[{"tick": 14000}])
    assert early.errors == [] and early.unmatched == []
    assert early.count("GET", "/api/feed?limit=20") == 1

    res = open_feed(api=api, steps=[{"tick": 14000}, {"tick": 1000}])
    assert res.errors == [] and res.unmatched == []
    assert res.count("GET", "/api/feed?limit=20") == 2
    assert res.labels == ["Post", "Like (7)", "Comments (3)"]


def test_lives_in_its_own_feature_folder() -> None:
    res = run_page("page_feed", None)
    assert res.errors == [] and res.unmatched == []
    assert "feed" in [p["name"] for p in res.pages]
