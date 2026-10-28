from typing import Any

from chatbook.testing import (
    ALICE,
    CAROL,
    DAN,
    ERIN,
    FRANK,
    START_MS,
    UiResult,
    fake_conversation,
    fake_message,
    run_page,
)

LONG_BODY = "packing the skis and boots right now so we can leave before sunrise!!!"
assert len(LONG_BODY) == 70

CONV_DIRECT = fake_conversation(
    4,
    "direct",
    "Erin Evans",
    [ALICE, ERIN],
    last_message=fake_message(9, ERIN, LONG_BODY, conversation_id=4),
    unread=2,
    updated_at=START_MS,
)
CONV_GROUP = fake_conversation(
    7,
    "group",
    "Ski trip",
    [ALICE, ERIN, FRANK],
    updated_at=START_MS + 120_000,
)


def open_inbox(
    conversations: list[dict[str, Any]] | None = None,
    steps: list[dict[str, Any]] | None = None,
) -> UiResult:
    convs = [CONV_DIRECT, CONV_GROUP] if conversations is None else conversations
    return run_page(
        "page_inbox",
        "inbox",
        api={"GET /api/conversations": {"conversations": convs}},
        steps=steps,
    )


def test_page_is_registered_in_nav_at_order_10() -> None:
    res = run_page("page_inbox", None)
    assert res.errors == [] and res.unmatched == []
    assert res.pages == [
        {
            "name": "inbox",
            "title": "Chats",
            "nav": "Chats",
            "order": 10,
            "public": False,
            "file": "page_inbox",
        }
    ]


def test_renders_conversations_with_truncated_preview_unread_badge_and_no_messages() -> None:
    res = open_inbox()
    assert res.errors == [] and res.unmatched == []
    assert (res.page, res.title) == ("inbox", "Chats")
    assert res.calls == [["GET", "/api/conversations", None]]
    assert res.classes[0][0] == "stack"
    assert ["row", "Chats New group"] in res.classes
    assert "Chats" in res.text
    assert "New group" in res.labels
    preview_1 = "Erin Evans: " + LONG_BODY[:60] + "..."
    assert preview_1 in res.text
    assert LONG_BODY[:61] not in res.text
    assert "Ski trip" in res.text
    assert "No messages yet" in res.text
    assert "No conversations yet" not in res.text

    assert ["muted", preview_1] in res.classes
    assert ["muted", "No messages yet"] in res.classes
    muted_texts = [c[1] for c in res.classes if c[0] == "muted"]
    assert len(muted_texts) == 4
    assert all(t != "" for t in muted_texts)
    assert muted_texts[1] != muted_texts[3]

    assert ["badge", "2"] in res.classes
    badges = [c for c in res.classes if c[0] == "badge"]
    assert badges == [["badge", "2"]]

    items = [c for c in res.classes if c[0] in ("item", "item unread")]
    assert [c[0] for c in items] == ["item unread", "item"]
    assert items[0][1].startswith(f"Erin Evans {preview_1} ")
    assert items[0][1].endswith(" 2")
    assert items[1][1].startswith("Ski trip No messages yet ")


def test_short_message_body_is_not_truncated() -> None:
    exact_60 = "a" * 60
    short_conv = fake_conversation(
        11,
        "direct",
        "Dan Diaz",
        [ALICE, DAN],
        last_message=fake_message(15, DAN, exact_60, conversation_id=11),
        unread=0,
    )
    unread_5 = fake_conversation(
        12,
        "direct",
        "Carol Chen",
        [ALICE, CAROL],
        last_message=fake_message(16, CAROL, "quick note", conversation_id=12),
        unread=5,
    )
    res = open_inbox(conversations=[short_conv, unread_5])
    assert res.errors == [] and res.unmatched == []
    assert f"Dan Diaz: {exact_60}" in res.text
    assert f"{exact_60}..." not in res.text
    assert [c for c in res.classes if c[0] == "badge"] == [["badge", "5"]]
    assert [c[0] for c in res.classes if c[0] in ("item", "item unread")] == [
        "item",
        "item unread",
    ]


def test_clicking_new_group_navigates_to_group_new() -> None:
    res = open_inbox(steps=[{"click": "New group"}])
    assert res.errors == [] and res.unmatched == []
    assert res.nav == [["group_new", {}]]


def test_clicking_conversation_items_navigates_to_chat() -> None:
    res_7 = open_inbox(steps=[{"click_id": "conv-7"}])
    assert res_7.errors == [] and res_7.unmatched == []
    assert res_7.nav == [["chat", {"id": "7"}]]

    res_4 = open_inbox(steps=[{"click_id": "conv-4"}])
    assert res_4.errors == [] and res_4.unmatched == []
    assert res_4.nav == [["chat", {"id": "4"}]]


def test_polls_conversations_every_3000_ms() -> None:
    res = open_inbox(steps=[{"tick": 3000}])
    assert res.errors == [] and res.unmatched == []
    assert res.count("GET", "/api/conversations") == 2


def test_empty_inbox_shows_no_conversations_yet() -> None:
    res = open_inbox(conversations=[])
    assert res.errors == [] and res.unmatched == []
    assert res.calls == [["GET", "/api/conversations", None]]
    assert "No conversations yet" in res.text
    assert ["muted", "No conversations yet"] in res.classes
    assert [c for c in res.classes if c[0] in ("item", "item unread")] == []


def test_lives_in_its_own_feature_folder() -> None:
    res = run_page("page_inbox", None)
    assert res.errors == [] and res.unmatched == []
    assert "inbox" in [p["name"] for p in res.pages]
