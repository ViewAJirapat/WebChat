from chatbook.testing import (
    ALICE,
    CAROL,
    ERIN,
    FRANK,
    UiResult,
    fake_conversation,
    run_page,
)


def open_group_new(
    api: dict[str, object] | None = None,
    steps: list[dict[str, object]] | None = None,
) -> UiResult:
    return run_page("page_group_new", "group_new", api=api, steps=steps)


def test_page_is_registered_without_nav_at_order_100() -> None:
    res = run_page("page_group_new", None)
    assert res.errors == [] and res.unmatched == []
    assert res.pages == [
        {
            "name": "group_new",
            "title": "New group",
            "nav": None,
            "order": 100,
            "public": False,
            "file": "page_group_new",
        }
    ]


def test_renders_create_group_form_with_friend_checkboxes() -> None:
    res = open_group_new(api={"GET /api/friends": {"friends": [ERIN, FRANK]}})
    assert res.errors == [] and res.unmatched == []
    assert (res.page, res.title) == ("group_new", "New group")
    assert res.calls == [["GET", "/api/friends", None]]
    assert res.forms == [
        {
            "submit": "Create group",
            "fields": ["title", "members"],
            "types": {"title": "text", "members": "checkboxes"},
            "options": {"members": ["5", "6"]},
            "values": {"title": "", "members": []},
        }
    ]
    assert "Group name" in res.text
    assert "Members" in res.text
    assert "Erin Evans" in res.text
    assert "Frank Fox" in res.text
    assert "Add friends first" not in res.text


def test_submit_creates_group_with_numeric_member_ids_and_opens_chat() -> None:
    created = fake_conversation(9, "group", "Ski", [ALICE, ERIN, FRANK])
    res = open_group_new(
        api={
            "GET /api/friends": {"friends": [ERIN, FRANK]},
            "POST /api/groups": {"$status": 201, "conversation": created},
        },
        steps=[
            {
                "submit": "Create group",
                "values": {"title": "Ski", "members": ["5", "6"]},
            }
        ],
    )
    assert res.errors == [] and res.unmatched == []
    assert res.calls == [
        ["GET", "/api/friends", None],
        ["POST", "/api/groups", {"title": "Ski", "member_ids": [5, 6]}],
    ]
    assert res.nav == [["chat", {"id": "9"}]]
    assert res.toasts == []


def test_submit_with_single_or_no_checked_members() -> None:
    unordered = open_group_new(api={"GET /api/friends": {"friends": [FRANK, CAROL, ERIN]}})
    assert unordered.errors == [] and unordered.unmatched == []
    assert unordered.forms[0]["options"] == {"members": ["6", "3", "5"]}

    created_one = fake_conversation(11, "group", "Duo", [ALICE, CAROL])
    res = open_group_new(
        api={
            "GET /api/friends": {"friends": [FRANK, CAROL, ERIN]},
            "POST /api/groups": {"$status": 201, "conversation": created_one},
        },
        steps=[
            {
                "submit": "Create group",
                "values": {"title": "Duo", "members": ["3"]},
            }
        ],
    )
    assert res.errors == [] and res.unmatched == []
    assert res.calls == [
        ["GET", "/api/friends", None],
        ["POST", "/api/groups", {"title": "Duo", "member_ids": [3]}],
    ]
    assert res.nav == [["chat", {"id": "11"}]]

    created_empty = fake_conversation(12, "group", "Solo", [ALICE])
    res_empty = open_group_new(
        api={
            "GET /api/friends": {"friends": [ERIN, FRANK]},
            "POST /api/groups": {"$status": 201, "conversation": created_empty},
        },
        steps=[
            {
                "submit": "Create group",
                "values": {"title": "Solo", "members": []},
            }
        ],
    )
    assert res_empty.errors == [] and res_empty.unmatched == []
    assert res_empty.calls == [
        ["GET", "/api/friends", None],
        ["POST", "/api/groups", {"title": "Solo", "member_ids": []}],
    ]
    assert res_empty.nav == [["chat", {"id": "12"}]]


def test_no_friends_shows_placeholder_without_form() -> None:
    res = open_group_new(api={"GET /api/friends": {"friends": []}})
    assert res.errors == [] and res.unmatched == []
    assert res.calls == [["GET", "/api/friends", None]]
    assert res.forms == []
    assert res.text == "Add friends first"
    assert ["muted", "Add friends first"] in res.classes


def test_lives_in_its_own_feature_folder() -> None:
    res = run_page("page_group_new", None)
    assert res.errors == [] and res.unmatched == []
    assert "group_new" in [p["name"] for p in res.pages]
