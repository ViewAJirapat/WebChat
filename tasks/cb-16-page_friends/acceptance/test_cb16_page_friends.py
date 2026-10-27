from chatbook.testing import (
    ALICE,
    BOB,
    CAROL,
    DAN,
    ERIN,
    FRANK,
    UiResult,
    fake_request,
    run_page,
)


def base_api(
    incoming: list[dict[str, object]] | None = None,
    outgoing: list[dict[str, object]] | None = None,
    friends: list[dict[str, object]] | None = None,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    inc = [fake_request(7, ERIN, ALICE)] if incoming is None else incoming
    out = [fake_request(8, ALICE, FRANK)] if outgoing is None else outgoing
    frs = [CAROL] if friends is None else friends
    api: dict[str, object] = {
        "GET /api/friends/requests": {"incoming": inc, "outgoing": out},
        "GET /api/friends": {"friends": frs},
    }
    if extra:
        api.update(extra)
    return api


def open_friends(
    api: dict[str, object] | None = None,
    steps: list[dict[str, object]] | None = None,
) -> UiResult:
    return run_page(
        "page_friends",
        "friends",
        api=base_api() if api is None else api,
        steps=steps,
    )


def test_page_is_registered_in_nav_at_order_20() -> None:
    res = run_page("page_friends", None)
    assert res.errors == [] and res.unmatched == []
    assert res.pages == [
        {
            "name": "friends",
            "title": "Friends",
            "nav": "Friends",
            "order": 20,
            "public": False,
            "file": "page_friends",
        }
    ]


def test_renders_incoming_outgoing_and_friends_in_order() -> None:
    res = open_friends()
    assert res.errors == [] and res.unmatched == []
    assert (res.page, res.title) == ("friends", "Friends")
    assert res.calls == [
        ["GET", "/api/friends/requests", None],
        ["GET", "/api/friends", None],
    ]
    for expected in (
        "Friend requests",
        "Erin Evans",
        "Sent requests",
        "Frank Fox",
        "Friends (1)",
        "Carol Chen",
    ):
        assert expected in res.text
    for placeholder in ("No requests", "No sent requests", "No friends yet"):
        assert placeholder not in res.text

    assert res.classes[0][0] == "stack"
    items = [c for c in res.classes if c[0] == "item"]
    assert items == [
        ["item", "Erin Evans Accept Decline"],
        ["item", "Frank Fox Cancel"],
        ["item", "Carol Chen Message Unfriend"],
    ]
    assert [c for c in res.classes if c[0] == "avatar"] == [["avatar", ""]] * 3
    assert res.buttons == [
        {"label": "Accept", "disabled": False, "testid": "accept-7"},
        {"label": "Decline", "disabled": False, "testid": "decline-7"},
        {"label": "Cancel", "disabled": False, "testid": "cancel-8"},
        {"label": "Message", "disabled": False, "testid": "message-3"},
        {"label": "Unfriend", "disabled": False, "testid": "unfriend-3"},
    ]


def test_renders_multiple_items_per_section_and_links_to_profiles() -> None:
    api = base_api(
        incoming=[fake_request(7, ERIN, ALICE), fake_request(9, DAN, ALICE)],
        outgoing=[fake_request(8, ALICE, FRANK), fake_request(10, ALICE, BOB)],
        friends=[CAROL, DAN],
    )
    res = open_friends(api=api)
    assert res.errors == [] and res.unmatched == []
    assert "Friends (2)" in res.text
    items = [c for c in res.classes if c[0] == "item"]
    assert items == [
        ["item", "Erin Evans Accept Decline"],
        ["item", "Dan Diaz Accept Decline"],
        ["item", "Frank Fox Cancel"],
        ["item", "Bob Brown Cancel"],
        ["item", "Carol Chen Message Unfriend"],
        ["item", "Dan Diaz Message Unfriend"],
    ]

    for name, uid in (("Erin Evans", "5"), ("Frank Fox", "6"), ("Carol Chen", "3")):
        click_res = open_friends(api=api, steps=[{"click": name}])
        assert click_res.errors == [] and click_res.unmatched == []
        assert click_res.nav == [["profile", {"id": uid}]]


def test_accept_posts_and_reloads_both_endpoints() -> None:
    res = open_friends(
        api=base_api(extra={"POST /api/friends/requests/7/accept": {"ok": True}}),
        steps=[{"click_id": "accept-7"}],
    )
    assert res.errors == [] and res.unmatched == []
    assert ["POST", "/api/friends/requests/7/accept", None] in res.calls
    assert res.count("GET", "/api/friends/requests") == 2
    assert res.count("GET", "/api/friends") == 2


def test_decline_posts_and_reloads_both_endpoints() -> None:
    res = open_friends(
        api=base_api(extra={"POST /api/friends/requests/7/decline": {"ok": True}}),
        steps=[{"click_id": "decline-7"}],
    )
    assert res.errors == [] and res.unmatched == []
    assert ["POST", "/api/friends/requests/7/decline", None] in res.calls
    assert res.count("GET", "/api/friends/requests") == 2
    assert res.count("GET", "/api/friends") == 2


def test_cancel_deletes_and_reloads_both_endpoints() -> None:
    res = open_friends(
        api=base_api(extra={"DELETE /api/friends/requests/8": {"ok": True}}),
        steps=[{"click_id": "cancel-8"}],
    )
    assert res.errors == [] and res.unmatched == []
    assert ["DELETE", "/api/friends/requests/8", None] in res.calls
    assert res.count("GET", "/api/friends/requests") == 2
    assert res.count("GET", "/api/friends") == 2


def test_unfriend_deletes_and_reloads_both_endpoints() -> None:
    res = open_friends(
        api=base_api(extra={"DELETE /api/friends/3": {"ok": True}}),
        steps=[{"click_id": "unfriend-3"}],
    )
    assert res.errors == [] and res.unmatched == []
    assert ["DELETE", "/api/friends/3", None] in res.calls
    assert res.count("GET", "/api/friends/requests") == 2
    assert res.count("GET", "/api/friends") == 2


def test_message_creates_dm_and_navigates_to_chat() -> None:
    dm_extra: dict[str, object] = {
        "POST /api/dm": {"conversation": {"id": 21, "kind": "direct"}},
    }
    res = open_friends(
        api=base_api(extra=dm_extra),
        steps=[{"click_id": "message-3"}],
    )
    assert res.errors == [] and res.unmatched == []
    assert ["POST", "/api/dm", {"user_id": 3}] in res.calls
    assert res.nav == [["chat", {"id": "21"}]]


def test_empty_sections_show_muted_placeholders_and_zero_count() -> None:
    res = open_friends(api=base_api(incoming=[], outgoing=[], friends=[]))
    assert res.errors == [] and res.unmatched == []
    assert res.text.startswith("Friend requests No requests Sent requests ")
    assert res.text.endswith("No sent requests Friends (0) No friends yet")
    assert ["muted", "No requests"] in res.classes
    assert ["muted", "No sent requests"] in res.classes
    assert ["muted", "No friends yet"] in res.classes
    assert res.buttons == []


def test_lives_in_its_own_feature_folder() -> None:
    assert "friends" in [p["name"] for p in run_page("page_friends", None).pages]
