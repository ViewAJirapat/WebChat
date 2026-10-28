from typing import Any

import pytest

from chatbook.testing import BOB, CAROL, DAN, ERIN, FRANK, UiResult, run_page

ONLINE_GET = "GET /api/friends/online"
SUGGEST_GET = "GET /api/friends/suggestions"
LOADS = [
    ["GET", "/api/friends/online", None],
    ["GET", "/api/friends/suggestions", None],
]

ONLINE = [ERIN, DAN]
SUGGESTIONS = [FRANK | {"mutual": 2}, CAROL | {"mutual": 1}, BOB | {"mutual": 11}]


def base_api(
    online: Any = None,
    suggestions: Any = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    api: dict[str, Any] = {
        ONLINE_GET: {"online": ONLINE if online is None else online},
        SUGGEST_GET: {"suggestions": SUGGESTIONS if suggestions is None else suggestions},
    }
    if extra:
        api.update(extra)
    return api


def open_discover(
    api: dict[str, Any] | None = None,
    steps: list[dict[str, Any]] | None = None,
) -> UiResult:
    return run_page(
        "page_discover",
        "discover",
        api=base_api() if api is None else api,
        steps=steps,
    )


def test_page_is_registered_in_nav_at_order_35() -> None:
    res = run_page("page_discover", None)
    assert res.errors == [] and res.unmatched == []
    assert res.pages == [
        {
            "name": "discover",
            "title": "Discover",
            "nav": "Discover",
            "order": 35,
            "public": False,
            "file": "page_discover",
        }
    ]


def test_loads_online_friends_then_suggestions() -> None:
    res = open_discover()
    assert res.errors == [] and res.unmatched == []
    assert (res.page, res.title) == ("discover", "Discover")
    assert res.calls == LOADS
    assert res.nav == [] and res.toasts == []


def test_renders_online_section_then_suggestions_in_order() -> None:
    res = open_discover()
    assert res.errors == [] and res.unmatched == []
    assert res.text == (
        "Online now Erin Evans Message Dan Diaz Message "
        "People you may know Frank Fox 2 mutual friends Add friend "
        "Carol Chen 1 mutual friend Add friend Bob Brown 11 mutual friends Add friend"
    )
    assert res.classes == [
        ["stack", res.text],
        ["item", "Erin Evans Message"],
        ["avatar", ""],
        ["user-link", "Erin Evans"],
        ["item", "Dan Diaz Message"],
        ["avatar", ""],
        ["user-link", "Dan Diaz"],
        ["item", "Frank Fox 2 mutual friends Add friend"],
        ["avatar", ""],
        ["user-link", "Frank Fox"],
        ["muted", "2 mutual friends"],
        ["item", "Carol Chen 1 mutual friend Add friend"],
        ["avatar", ""],
        ["user-link", "Carol Chen"],
        ["muted", "1 mutual friend"],
        ["item", "Bob Brown 11 mutual friends Add friend"],
        ["avatar", ""],
        ["user-link", "Bob Brown"],
        ["muted", "11 mutual friends"],
    ]
    assert res.buttons == [
        {"label": "Message", "disabled": False, "testid": "message-5"},
        {"label": "Message", "disabled": False, "testid": "message-4"},
        {"label": "Add friend", "disabled": False, "testid": "add-6"},
        {"label": "Add friend", "disabled": False, "testid": "add-3"},
        {"label": "Add friend", "disabled": False, "testid": "add-2"},
    ]


def test_other_people_render_with_their_own_ids_and_counts() -> None:
    res = open_discover(api=base_api(online=[BOB], suggestions=[DAN | {"mutual": 1}]))
    assert res.errors == [] and res.unmatched == []
    assert res.text == (
        "Online now Bob Brown Message People you may know Dan Diaz 1 mutual friend Add friend"
    )
    assert [b["testid"] for b in res.buttons] == ["message-2", "add-4"]


def test_both_lists_empty_show_placeholders() -> None:
    res = open_discover(api=base_api(online=[], suggestions=[]))
    assert res.errors == [] and res.unmatched == []
    assert res.calls == LOADS
    assert res.text == "Online now Nobody is online People you may know No suggestions"
    assert res.classes == [
        ["stack", res.text],
        ["muted", "Nobody is online"],
        ["muted", "No suggestions"],
    ]
    assert res.buttons == []


def test_nobody_online_but_suggestions_present() -> None:
    res = open_discover(api=base_api(online=[], suggestions=[FRANK | {"mutual": 4}]))
    assert res.errors == [] and res.unmatched == []
    assert res.text == (
        "Online now Nobody is online People you may know Frank Fox 4 mutual friends Add friend"
    )
    assert ["muted", "Nobody is online"] in res.classes
    assert "No suggestions" not in res.text
    assert res.labels == ["Add friend"]


def test_friends_online_but_no_suggestions() -> None:
    res = open_discover(api=base_api(online=[CAROL], suggestions=[]))
    assert res.errors == [] and res.unmatched == []
    assert res.text == "Online now Carol Chen Message People you may know No suggestions"
    assert ["muted", "No suggestions"] in res.classes
    assert "Nobody is online" not in res.text
    assert [b["testid"] for b in res.buttons] == ["message-3"]


@pytest.mark.parametrize(("testid", "user_id"), [("add-3", 3), ("add-2", 2)])
def test_add_friend_posts_request_toasts_and_reloads(testid: str, user_id: int) -> None:
    api = base_api(
        extra={
            SUGGEST_GET: [
                {"suggestions": SUGGESTIONS},
                {"suggestions": [s for s in SUGGESTIONS if s["id"] != user_id]},
            ],
            "POST /api/friends/requests": {"status": "pending", "request": {"id": 40 + user_id}},
        }
    )
    res = open_discover(api=api, steps=[{"click_id": testid}])
    assert res.errors == [] and res.unmatched == []
    assert res.calls == [
        *LOADS,
        ["POST", "/api/friends/requests", {"user_id": user_id}],
        *LOADS,
    ]
    assert res.toasts == ["Request sent"]
    assert res.nav == []
    assert testid not in [b["testid"] for b in res.buttons]
    assert len([b for b in res.buttons if b["label"] == "Add friend"]) == 2


@pytest.mark.parametrize(
    ("testid", "user_id", "conversation_id"), [("message-4", 4, 31), ("message-5", 5, 17)]
)
def test_message_opens_direct_chat_without_reloading(
    testid: str, user_id: int, conversation_id: int
) -> None:
    dm = {"conversation": {"id": conversation_id, "kind": "direct", "title": "x"}}
    res = open_discover(api=base_api(extra={"POST /api/dm": dm}), steps=[{"click_id": testid}])
    assert res.errors == [] and res.unmatched == []
    assert res.calls == [*LOADS, ["POST", "/api/dm", {"user_id": user_id}]]
    assert res.nav == [["chat", {"id": str(conversation_id)}]]
    assert res.toasts == []


def test_names_link_to_profiles() -> None:
    for name, uid in (("Dan Diaz", "4"), ("Carol Chen", "3")):
        res = open_discover(steps=[{"click": name}])
        assert res.errors == [] and res.unmatched == []
        assert res.nav == [["profile", {"id": uid}]]


def test_polls_both_lists_every_15000_ms() -> None:
    api = base_api(
        extra={
            ONLINE_GET: [{"online": [ERIN]}, {"online": [ERIN, BOB]}],
            SUGGEST_GET: [{"suggestions": []}, {"suggestions": [DAN | {"mutual": 3}]}],
        }
    )
    res = open_discover(api=api, steps=[{"tick": 14999}])
    assert res.errors == [] and res.unmatched == []
    assert res.calls == LOADS

    res = open_discover(api=api, steps=[{"tick": 14999}, {"tick": 1}])
    assert res.errors == [] and res.unmatched == []
    assert res.calls == [*LOADS, *LOADS]
    assert res.text == (
        "Online now Erin Evans Message Bob Brown Message "
        "People you may know Dan Diaz 3 mutual friends Add friend"
    )

    res = open_discover(api=api, steps=[{"tick": 15000}, {"tick": 15000}])
    assert res.errors == [] and res.unmatched == []
    assert res.calls == [*LOADS, *LOADS, *LOADS]


def test_failed_friend_request_shows_no_success_toast_and_no_reload() -> None:
    api = base_api(
        extra={"POST /api/friends/requests": {"$status": 409, "error": "already requested"}}
    )
    res = open_discover(api=api, steps=[{"click_id": "add-6"}])
    assert res.errors == [] and res.unmatched == []
    assert res.calls == [*LOADS, ["POST", "/api/friends/requests", {"user_id": 6}]]
    assert "Request sent" not in res.toasts
    assert res.nav == []


def test_failed_dm_does_not_navigate() -> None:
    api = base_api(extra={"POST /api/dm": {"$status": 403, "error": "not friends"}})
    res = open_discover(api=api, steps=[{"click_id": "message-5"}])
    assert res.errors == [] and res.unmatched == []
    assert res.calls == [*LOADS, ["POST", "/api/dm", {"user_id": 5}]]
    assert res.nav == []


def test_lives_in_its_own_feature_folder() -> None:
    res = run_page("page_discover", None)
    assert res.errors == [] and res.unmatched == []
    assert "discover" in [p["name"] for p in res.pages]
