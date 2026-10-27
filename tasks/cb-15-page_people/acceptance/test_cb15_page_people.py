from chatbook.testing import UiResult, run_page

JO_NONE = {
    "id": 5,
    "username": "jo_none",
    "display_name": "Joanna Nash",
    "relationship": "none",
}
JO_SENT = {
    "id": 6,
    "username": "jo_sent",
    "display_name": "Jonas Reed",
    "relationship": "request_sent",
}
JO_RECV = {
    "id": 7,
    "username": "jo_recv",
    "display_name": "Jodie Vance",
    "relationship": "request_received",
}
JO_PAL = {
    "id": 8,
    "username": "jo_pal",
    "display_name": "Jordan Bell",
    "relationship": "friends",
}
FOUR_USERS = [JO_NONE, JO_SENT, JO_RECV, JO_PAL]


def search_form(value: str = "") -> dict[str, object]:
    return {
        "submit": "Search",
        "fields": ["q"],
        "types": {"q": "text"},
        "options": {},
        "values": {"q": value},
    }


def open_people(
    params: dict[str, str] | None = None,
    api: dict[str, object] | None = None,
    steps: list[dict[str, object]] | None = None,
) -> UiResult:
    return run_page("page_people", "people", params=params, api=api, steps=steps)


def test_page_is_registered_in_nav_at_order_30() -> None:
    res = run_page("page_people", None)
    assert res.errors == [] and res.unmatched == []
    assert res.pages == [
        {
            "name": "people",
            "title": "People",
            "nav": "People",
            "order": 30,
            "public": False,
            "file": "page_people",
        }
    ]


def test_without_query_shows_prompt_without_api_calls() -> None:
    for params in ({}, {"q": ""}, {"q": "   "}):
        res = open_people(params=params)
        assert res.errors == [] and res.unmatched == []
        assert (res.page, res.title) == ("people", "People")
        assert res.calls == []
        assert res.forms == [search_form("")]
        assert "Search by name or username" in res.text
        assert "No people found" not in res.text
        assert ["muted", "Search by name or username"] in res.classes


def test_submitting_search_trims_query_navigates_and_fetches() -> None:
    res = open_people(
        api={"GET /api/users?q=jo": {"users": FOUR_USERS}},
        steps=[{"submit": "Search", "values": {"q": "  jo "}}],
    )
    assert res.errors == [] and res.unmatched == []
    assert res.nav == [["people", {"q": "jo"}]]
    assert res.calls == [["GET", "/api/users?q=jo", None]]
    assert res.forms == [search_form("jo")]
    assert "Joanna Nash" in res.text


def test_renders_four_relationship_states_in_order() -> None:
    res = open_people(
        params={"q": "jo"},
        api={"GET /api/users?q=jo": {"users": FOUR_USERS}},
    )
    assert res.errors == [] and res.unmatched == []
    assert res.calls == [["GET", "/api/users?q=jo", None]]
    assert res.forms == [search_form("jo")]
    assert "Search by name or username" not in res.text
    assert "No people found" not in res.text

    expected_items = [
        ["item", "Joanna Nash @jo_none Add friend"],
        ["item", "Jonas Reed @jo_sent Requested"],
        ["item", "Jodie Vance @jo_recv Respond"],
        ["item", "Jordan Bell @jo_pal Message"],
    ]
    assert res.classes[0][0] == "stack"
    items = [c for c in res.classes if c[0] == "item"]
    assert items == expected_items
    assert [c for c in res.classes if c[0] == "avatar"] == [["avatar", ""]] * 4
    for u in FOUR_USERS:
        assert ["muted", f"@{u['username']}"] in res.classes

    assert res.buttons == [
        {"label": "Search", "disabled": False, "testid": None},
        {"label": "Add friend", "disabled": False, "testid": "add-5"},
        {"label": "Requested", "disabled": True, "testid": None},
        {"label": "Respond", "disabled": False, "testid": None},
        {"label": "Message", "disabled": False, "testid": "message-8"},
    ]

    # load(params) trims params.q directly when opened with whitespace around q
    trimmed = open_people(
        params={"q": "  jo  "},
        api={"GET /api/users?q=jo": {"users": FOUR_USERS}},
    )
    assert trimmed.errors == [] and trimmed.unmatched == []
    assert trimmed.calls == [["GET", "/api/users?q=jo", None]]
    assert trimmed.forms == [search_form("jo")]


def test_clicking_user_link_opens_profile() -> None:
    res = open_people(
        params={"q": "jo"},
        api={"GET /api/users?q=jo": {"users": FOUR_USERS}},
        steps=[{"click": "Joanna Nash"}],
    )
    assert res.errors == [] and res.unmatched == []
    assert res.nav == [["profile", {"id": "5"}]]


def test_add_friend_posts_request_toasts_and_refreshes() -> None:
    res = open_people(
        params={"q": "jo"},
        api={
            "GET /api/users?q=jo": {"users": FOUR_USERS},
            "POST /api/friends/requests": {"request": {"id": 99}},
        },
        steps=[{"click_id": "add-5"}],
    )
    assert res.errors == [] and res.unmatched == []
    assert ["POST", "/api/friends/requests", {"user_id": 5}] in res.calls
    assert res.toasts == ["Request sent"]
    assert res.count("GET", "/api/users?q=jo") == 2


def test_respond_navigates_to_friends_page() -> None:
    res = open_people(
        params={"q": "jo"},
        api={"GET /api/users?q=jo": {"users": FOUR_USERS}},
        steps=[{"click": "Respond"}],
    )
    assert res.errors == [] and res.unmatched == []
    assert res.nav == [["friends", {}]]


def test_message_creates_dm_and_opens_chat() -> None:
    res = open_people(
        params={"q": "jo"},
        api={
            "GET /api/users?q=jo": {"users": FOUR_USERS},
            "POST /api/dm": {"conversation": {"id": 12, "kind": "direct"}},
        },
        steps=[{"click_id": "message-8"}],
    )
    assert res.errors == [] and res.unmatched == []
    assert res.calls == [
        ["GET", "/api/users?q=jo", None],
        ["POST", "/api/dm", {"user_id": 8}],
    ]
    assert res.nav == [["chat", {"id": "12"}]]


def test_empty_result_shows_no_people_found() -> None:
    res = open_people(
        params={"q": "nobody"},
        api={"GET /api/users?q=nobody": {"users": []}},
    )
    assert res.errors == [] and res.unmatched == []
    assert res.calls == [["GET", "/api/users?q=nobody", None]]
    assert res.forms == [search_form("nobody")]
    assert "No people found" in res.text
    assert "Search by name or username" not in res.text
    assert ["muted", "No people found"] in res.classes


def test_lives_in_its_own_feature_folder() -> None:
    assert "people" in [p["name"] for p in run_page("page_people", None).pages]
