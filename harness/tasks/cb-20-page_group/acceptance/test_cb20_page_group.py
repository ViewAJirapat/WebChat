from chatbook.testing import (
    ALICE,
    BOB,
    CAROL,
    ERIN,
    FRANK,
    UiResult,
    fake_conversation,
    run_page,
)


def group_conv(
    title: str = "Ski trip",
    members: list[dict[str, object]] | None = None,
    cid: int = 3,
) -> dict[str, object]:
    m = [ALICE, ERIN] if members is None else members
    return {"conversation": fake_conversation(cid, "group", title, m), "reads": []}


def open_group(
    params: dict[str, str] | None = None,
    api: dict[str, object] | None = None,
    steps: list[dict[str, object]] | None = None,
) -> UiResult:
    p = {"id": "3"} if params is None else params
    return run_page("page_group", "group", params=p, api=api, steps=steps)


def test_page_is_registered_without_nav_at_order_100() -> None:
    res = run_page("page_group", None)
    assert res.errors == [] and res.unmatched == []
    assert res.pages == [
        {
            "name": "group",
            "title": "Group settings",
            "nav": None,
            "order": 100,
            "public": False,
            "file": "page_group",
        }
    ]


def test_renders_group_settings_members_and_candidate_friends() -> None:
    res = open_group(
        api={
            "GET /api/conversations/3": group_conv("Ski trip", [ALICE, ERIN]),
            "GET /api/friends": {"friends": [ERIN, FRANK, CAROL]},
        }
    )
    assert res.errors == [] and res.unmatched == []
    assert (res.page, res.title) == ("group", "Group settings")
    assert res.calls == [
        ["GET", "/api/conversations/3", None],
        ["GET", "/api/friends", None],
    ]
    assert "Ski trip" in res.text
    assert "Members (2)" in res.text
    assert "Alice Adams" in res.text
    assert "Erin Evans" in res.text
    assert res.classes[0][0] == "stack"
    assert ["row", "Ski trip Back to chat"] in res.classes
    items = [c for c in res.classes if c[0] == "item"]
    assert items == [["item", "Alice Adams"], ["item", "Erin Evans"]]
    assert [c for c in res.classes if c[0] == "avatar"] == [["avatar", ""]] * 2
    assert ["danger", "Leave group"] in res.classes
    ordered = [
        "Ski trip Back to chat",
        "Group name",
        "Rename",
        "Members (2)",
        "Alice Adams",
        "Erin Evans",
        "Add a friend",
        "Add",
        "Leave group",
    ]
    positions = [res.text.index(part) for part in ordered]
    assert positions == sorted(positions)
    assert res.forms == [
        {
            "submit": "Rename",
            "fields": ["title"],
            "types": {"title": "text"},
            "options": {},
            "values": {"title": "Ski trip"},
        },
        {
            "submit": "Add",
            "fields": ["user_id"],
            "types": {"user_id": "select"},
            "options": {"user_id": ["6", "3"]},
            "values": {"user_id": "6"},
        },
    ]


def test_rename_puts_new_title_toasts_and_refreshes() -> None:
    res = open_group(
        api={
            "GET /api/conversations/3": [
                group_conv("Ski trip", [ALICE, ERIN]),
                group_conv("Alps", [ALICE, ERIN]),
            ],
            "GET /api/friends": {"friends": [ERIN, FRANK, CAROL]},
            "PUT /api/groups/3": group_conv("Alps", [ALICE, ERIN]),
        },
        steps=[{"submit": "Rename", "values": {"title": "Alps"}}],
    )
    assert res.errors == [] and res.unmatched == []
    assert ["PUT", "/api/groups/3", {"title": "Alps"}] in res.calls
    assert res.toasts == ["Renamed"]
    assert res.count("GET", "/api/conversations/3") == 2
    assert res.count("GET", "/api/friends") == 2
    assert "Alps" in res.text


def test_add_friend_posts_numeric_user_id_and_refreshes() -> None:
    res = open_group(
        params={"id": "14"},
        api={
            "GET /api/conversations/14": [
                group_conv("Ski trip", [ALICE, ERIN], cid=14),
                group_conv("Ski trip", [ALICE, ERIN, CAROL], cid=14),
            ],
            "GET /api/friends": {"friends": [ERIN, FRANK, CAROL]},
            "POST /api/groups/14/members": group_conv("Ski trip", [ALICE, ERIN, CAROL], cid=14),
        },
        steps=[{"submit": "Add", "values": {"user_id": "3"}}],
    )
    assert res.errors == [] and res.unmatched == []
    assert ["POST", "/api/groups/14/members", {"user_id": 3}] in res.calls
    assert res.count("GET", "/api/conversations/14") == 2
    assert res.count("GET", "/api/friends") == 2
    assert "Members (3)" in res.text


def test_leave_group_deletes_membership_and_goes_to_inbox() -> None:
    res = open_group(
        params={"id": "14"},
        api={
            "GET /api/conversations/14": group_conv("Ski trip", [ALICE, ERIN], cid=14),
            "GET /api/friends": {"friends": [ERIN, FRANK]},
            "DELETE /api/groups/14/members/me": {"ok": True},
        },
        steps=[{"click": "Leave group"}],
    )
    assert res.errors == [] and res.unmatched == []
    assert ["DELETE", "/api/groups/14/members/me", None] in res.calls
    assert res.nav == [["inbox", {}]]


def test_back_to_chat_and_member_links_navigate() -> None:
    res = open_group(
        params={"id": "14"},
        api={
            "GET /api/conversations/14": group_conv("Ski trip", [ALICE, ERIN], cid=14),
            "GET /api/friends": {"friends": [ERIN, FRANK]},
        },
        steps=[{"click": "Back to chat"}],
    )
    assert res.errors == [] and res.unmatched == []
    assert res.nav == [["chat", {"id": "14"}]]

    res_member = open_group(
        api={
            "GET /api/conversations/3": group_conv("Ski trip", [ALICE, ERIN]),
            "GET /api/friends": {"friends": [ERIN, FRANK]},
        },
        steps=[{"click": "Erin Evans"}],
    )
    assert res_member.errors == [] and res_member.unmatched == []
    assert res_member.nav == [["profile", {"id": "5"}]]


def test_omits_add_form_when_all_friends_are_already_members() -> None:
    res = open_group(
        api={
            "GET /api/conversations/3": group_conv("Ski trip", [ALICE, ERIN]),
            "GET /api/friends": {"friends": [ERIN]},
        }
    )
    assert res.errors == [] and res.unmatched == []
    assert [f["submit"] for f in res.forms] == ["Rename"]


def test_direct_conversation_shows_not_a_group_without_fetching_friends() -> None:
    dm = {
        "conversation": fake_conversation(3, "direct", "Bob Brown", [ALICE, BOB]),
        "reads": [],
    }
    res = open_group(api={"GET /api/conversations/3": dm})
    assert res.errors == [] and res.unmatched == []
    assert res.calls == [["GET", "/api/conversations/3", None]]
    assert res.forms == []
    assert res.text == "Not a group"
    assert ["muted", "Not a group"] in res.classes


def test_lives_in_its_own_feature_folder() -> None:
    res = run_page("page_group", None)
    assert res.errors == [] and res.unmatched == []
    assert "group" in [p["name"] for p in res.pages]
