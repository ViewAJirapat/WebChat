import pytest

from chatbook.testing import run_page


def test_polls_updates_on_start_and_every_5000ms_without_registering_a_page() -> None:
    res = run_page(
        "badges",
        None,
        api={
            "GET /api/updates": {
                "unread_total": 4,
                "unread_conversations": 2,
                "friend_requests": 1,
            }
        },
        steps=[{"tick": 5000}],
    )
    assert res.errors == [] and res.unmatched == []
    assert res.pages == []
    assert res.count("GET", "/api/updates") == 2
    assert res.calls == [["GET", "/api/updates", None], ["GET", "/api/updates", None]]
    assert res.badges == {"inbox": 4, "friends": 1}


@pytest.mark.parametrize(
    ("unread_total", "unread_conversations", "friend_requests"),
    [
        (7, 2, 0),
        (0, 0, 3),
        (0, 0, 0),
    ],
)
def test_initial_run_sets_inbox_from_unread_total_and_handles_zero_counts(
    unread_total: int, unread_conversations: int, friend_requests: int
) -> None:
    res = run_page(
        "badges",
        None,
        api={
            "GET /api/updates": {
                "unread_total": unread_total,
                "unread_conversations": unread_conversations,
                "friend_requests": friend_requests,
            }
        },
    )
    assert res.errors == [] and res.unmatched == []
    assert res.pages == []
    assert res.calls == [["GET", "/api/updates", None]]
    assert res.badges == {"inbox": unread_total, "friends": friend_requests}


def test_multiple_ticks_update_badges_dynamically_down_to_zero() -> None:
    answers = [
        {"unread_total": 5, "unread_conversations": 3, "friend_requests": 2},
        {"unread_total": 1, "unread_conversations": 1, "friend_requests": 4},
        {"unread_total": 0, "unread_conversations": 0, "friend_requests": 0},
    ]
    res_partial = run_page(
        "badges",
        None,
        api={"GET /api/updates": answers},
        steps=[{"tick": 4999}],
    )
    assert res_partial.errors == [] and res_partial.unmatched == []
    assert res_partial.count("GET", "/api/updates") == 1
    assert res_partial.badges == {"inbox": 5, "friends": 2}

    res_one = run_page(
        "badges",
        None,
        api={"GET /api/updates": answers},
        steps=[{"tick": 5000}],
    )
    assert res_one.errors == [] and res_one.unmatched == []
    assert res_one.count("GET", "/api/updates") == 2
    assert res_one.badges == {"inbox": 1, "friends": 4}

    res_two = run_page(
        "badges",
        None,
        api={"GET /api/updates": answers},
        steps=[{"tick": 5000}, {"tick": 5000}],
    )
    assert res_two.errors == [] and res_two.unmatched == []
    assert res_two.count("GET", "/api/updates") == 3
    assert res_two.badges == {"inbox": 0, "friends": 0}


def test_logged_out_makes_no_calls_and_sets_no_badges() -> None:
    res = run_page("badges", None, me=None, steps=[{"tick": 5000}, {"tick": 5000}])
    assert res.errors == [] and res.unmatched == []
    assert res.pages == []
    assert res.calls == []
    assert res.badges == {}
