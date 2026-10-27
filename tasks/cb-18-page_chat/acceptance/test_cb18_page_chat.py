from typing import Any

from chatbook.testing import (
    ALICE,
    ERIN,
    FRANK,
    fake_conversation,
    fake_message,
    run_page,
)

GROUP = fake_conversation(3, "group", "Ski trip", [ALICE, ERIN, FRANK], unread=2)
M10 = fake_message(10, ERIN, "hi there")
M11 = fake_message(11, ALICE, "on my way")
M12 = fake_message(12, ALICE, "hello")
READS = [
    {"user_id": 1, "last_read_id": 11},
    {"user_id": 5, "last_read_id": 11},
    {"user_id": 6, "last_read_id": 0},
]


def api(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "GET /api/conversations/3": [
            {"conversation": GROUP, "reads": READS},
            {"conversation": GROUP | {"unread": 0}, "reads": READS},
        ],
        "GET /api/conversations/3/messages?limit=50": [
            {"messages": [M10, M11], "has_more": True},
            {"messages": [M10, M11, M12], "has_more": True},
        ],
        "POST /api/conversations/3/read": {
            "conversation_id": 3,
            "last_read_id": 11,
            "unread": 0,
        },
        "POST /api/conversations/3/messages": {"message": M12},
    }
    return base | over


def test_page_is_registered_without_nav() -> None:
    res = run_page("page_chat", None)
    assert res.errors == [] and res.unmatched == []
    assert res.pages == [
        {
            "name": "chat",
            "title": "Chat",
            "nav": None,
            "order": 100,
            "public": False,
            "file": "page_chat",
        }
    ]


def test_loads_thread_then_marks_read() -> None:
    res = run_page("page_chat", "chat", params={"id": "3"}, api=api())
    assert res.errors == [] and res.unmatched == []
    assert res.calls[:3] == [
        ["GET", "/api/conversations/3", None],
        ["GET", "/api/conversations/3/messages?limit=50", None],
        ["POST", "/api/conversations/3/read", None],
    ]
    assert "Ski trip" in res.text and "Erin Evans: hi there" in res.text
    assert "Alice Adams: on my way" in res.text
    assert "Alice Adams, Erin Evans, Frank Fox" in res.text
    assert {"Group settings", "Show older", "Send"} <= set(res.labels)
    assert "Seen" in res.text
    assert res.classes[0][0] == "stack"
    assert ["row", "Ski trip Group settings"] in res.classes
    assert ["muted", "Alice Adams, Erin Evans, Frank Fox"] in res.classes
    assert any(c[0] == "messages" for c in res.classes)
    assert [c for c in res.classes if c[0] == "avatar"] == [["avatar", ""]] * 2
    msg_classes = [c[0] for c in res.classes if c[0] in ("msg", "msg mine")]
    assert msg_classes == ["msg", "msg mine"]
    assert res.forms == [
        {
            "submit": "Send",
            "fields": ["body"],
            "types": {"body": "text"},
            "options": {},
            "values": {"body": ""},
        }
    ]
    ordered = [
        "Ski trip",
        "Group settings",
        "Alice Adams, Erin Evans, Frank Fox",
        "Show older",
        "Erin Evans: hi there",
        "Alice Adams: on my way",
        "Seen",
        "Write a message",
        "Send",
    ]
    positions = [res.text.index(part) for part in ordered]
    assert positions == sorted(positions)


def test_send_trims_and_refreshes() -> None:
    res = run_page(
        "page_chat",
        "chat",
        params={"id": "3"},
        api=api(),
        steps=[{"submit": "Send", "values": {"body": "  hello "}}],
    )
    assert res.errors == [] and res.unmatched == []
    assert ["POST", "/api/conversations/3/messages", {"body": "hello"}] in res.calls
    assert res.count("GET", "/api/conversations/3/messages?limit=50") == 2
    assert "Alice Adams: hello" in res.text
    assert res.forms[0]["values"] == {"body": ""}


def test_send_whitespace_only_does_not_post() -> None:
    res = run_page(
        "page_chat",
        "chat",
        params={"id": "3"},
        api=api(),
        steps=[{"submit": "Send", "values": {"body": "   "}}],
    )
    assert res.errors == [] and res.unmatched == []
    assert res.count("POST", "/api/conversations/3/messages") == 0
    assert res.count("GET", "/api/conversations/3/messages?limit=50") == 1


def test_poll_fetches_messages_again_without_second_read_when_unread_is_zero() -> None:
    res = run_page(
        "page_chat",
        "chat",
        params={"id": "3"},
        api=api(),
        steps=[{"tick": 2000}],
    )
    assert res.errors == [] and res.unmatched == []
    assert res.count("GET", "/api/conversations/3") == 2
    assert res.count("GET", "/api/conversations/3/messages?limit=50") == 2
    assert res.count("POST", "/api/conversations/3/read") == 1


def test_show_older_increments_limit_by_50() -> None:
    res = run_page(
        "page_chat",
        "chat",
        params={"id": "3"},
        api=api(
            **{
                "GET /api/conversations/3/messages?limit=100": {
                    "messages": [M10, M11],
                    "has_more": False,
                }
            }
        ),
        steps=[{"click": "Show older"}],
    )
    assert res.errors == [] and res.unmatched == []
    assert res.nav == [["chat", {"id": "3", "limit": "100"}]]
    assert res.count("GET", "/api/conversations/3/messages?limit=100") == 1
    assert "Show older" not in res.labels

    res_150 = run_page(
        "page_chat",
        "chat",
        params={"id": "3", "limit": "100"},
        api=api(
            **{
                "GET /api/conversations/3/messages?limit=100": {
                    "messages": [M10, M11],
                    "has_more": True,
                },
                "GET /api/conversations/3/messages?limit=150": {
                    "messages": [M10, M11],
                    "has_more": False,
                },
            }
        ),
        steps=[{"click": "Show older"}],
    )
    assert res_150.errors == [] and res_150.unmatched == []
    assert res_150.nav == [["chat", {"id": "3", "limit": "150"}]]
    assert res_150.count("GET", "/api/conversations/3/messages?limit=150") == 1


def test_clicking_group_settings_navigates_to_group_page() -> None:
    other_group = fake_conversation(9, "group", "Book club", [ALICE, ERIN], unread=0)
    res = run_page(
        "page_chat",
        "chat",
        params={"id": "9"},
        api={
            "GET /api/conversations/9": {"conversation": other_group, "reads": []},
            "GET /api/conversations/9/messages?limit=50": {
                "messages": [],
                "has_more": False,
            },
        },
        steps=[{"click": "Group settings"}],
    )
    assert res.errors == [] and res.unmatched == []
    assert res.nav == [["group", {"id": "9"}]]


def test_direct_empty_conversation_shows_say_hi_without_optional_controls() -> None:
    direct = fake_conversation(8, "direct", "Erin Evans", [ALICE, ERIN], unread=0)
    res = run_page(
        "page_chat",
        "chat",
        params={"id": "8"},
        api={
            "GET /api/conversations/8": {"conversation": direct, "reads": []},
            "GET /api/conversations/8/messages?limit=50": {
                "messages": [],
                "has_more": False,
            },
        },
    )
    assert res.errors == [] and res.unmatched == []
    assert res.calls == [
        ["GET", "/api/conversations/8", None],
        ["GET", "/api/conversations/8/messages?limit=50", None],
    ]
    assert "Say hi!" in res.text
    assert ["muted", "Say hi!"] in res.classes
    assert "Group settings" not in res.labels
    assert "Show older" not in res.labels
    assert "Seen" not in res.text


def test_seen_indicator_conditions() -> None:
    # 1. Others' last_read_id is below my last message id -> no "Seen"
    res_below = run_page(
        "page_chat",
        "chat",
        params={"id": "3"},
        api=api(
            **{
                "GET /api/conversations/3": {
                    "conversation": GROUP | {"unread": 0},
                    "reads": [
                        {"user_id": 1, "last_read_id": 11},
                        {"user_id": 5, "last_read_id": 10},
                        {"user_id": 6, "last_read_id": 0},
                    ],
                }
            }
        ),
    )
    assert res_below.errors == [] and res_below.unmatched == []
    assert "Seen" not in res_below.text

    # 2. Messages exist from others only (none from CB.me.id) -> no "Seen"
    res_no_mine = run_page(
        "page_chat",
        "chat",
        params={"id": "3"},
        api=api(
            **{
                "GET /api/conversations/3": {
                    "conversation": GROUP | {"unread": 0},
                    "reads": [{"user_id": 5, "last_read_id": 10}],
                },
                "GET /api/conversations/3/messages?limit=50": {
                    "messages": [M10],
                    "has_more": False,
                },
            }
        ),
    )
    assert res_no_mine.errors == [] and res_no_mine.unmatched == []
    assert "Seen" not in res_no_mine.text

    # 3. Only CB.me.id's own read entry has last_read_id >= last -> no "Seen"
    res_only_me = run_page(
        "page_chat",
        "chat",
        params={"id": "3"},
        api=api(
            **{
                "GET /api/conversations/3": {
                    "conversation": GROUP | {"unread": 0},
                    "reads": [{"user_id": 1, "last_read_id": 11}],
                }
            }
        ),
    )
    assert res_only_me.errors == [] and res_only_me.unmatched == []
    assert "Seen" not in res_only_me.text

    # 4. Another member has last_read_id > my last message id (later message from them) -> "Seen"
    m13_erin = fake_message(13, ERIN, "got it!")
    res_greater = run_page(
        "page_chat",
        "chat",
        params={"id": "3"},
        api=api(
            **{
                "GET /api/conversations/3": {
                    "conversation": GROUP | {"unread": 0},
                    "reads": [
                        {"user_id": 1, "last_read_id": 11},
                        {"user_id": 5, "last_read_id": 13},
                    ],
                },
                "GET /api/conversations/3/messages?limit=50": {
                    "messages": [M10, M11, m13_erin],
                    "has_more": False,
                },
            }
        ),
    )
    assert res_greater.errors == [] and res_greater.unmatched == []
    assert "Seen" in res_greater.text
    assert ["muted", "Seen"] in res_greater.classes


def test_lives_in_its_own_feature_folder() -> None:
    res = run_page("page_chat", None)
    assert res.errors == [] and res.unmatched == []
    assert "chat" in [p["name"] for p in res.pages]
