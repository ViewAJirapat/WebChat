import pytest

from chatbook.testing import ALICE, DAN, ERIN, START_MS, UiResult, run_page


def user_profile(
    base: dict[str, object] = ERIN,
    *,
    bio: str = "",
    relationship: str = "none",
    friend_count: int = 0,
    request_id: int | None = None,
) -> dict[str, object]:
    return {
        "id": base["id"],
        "username": base["username"],
        "display_name": base["display_name"],
        "bio": bio,
        "joined_at": START_MS,
        "relationship": relationship,
        "friend_count": friend_count,
        "request_id": request_id,
    }


def open_profile(
    *,
    params: dict[str, str] | None = None,
    me: dict[str, object] | None = ALICE,
    api: dict[str, object] | None = None,
    steps: list[dict[str, object]] | None = None,
) -> UiResult:
    return run_page("page_profile", "profile", params=params, me=me, api=api, steps=steps)


def test_page_is_registered_with_title_nav_and_order() -> None:
    res = run_page("page_profile", None)
    assert res.errors == [] and res.unmatched == []
    assert res.pages == [
        {
            "name": "profile",
            "title": "Profile",
            "nav": "Profile",
            "order": 50,
            "public": False,
            "file": "page_profile",
        }
    ]


@pytest.mark.parametrize(
    ("bio", "expected_bio", "friend_count", "expected_friends"),
    [
        ("", "No bio yet", 0, "0 friends"),
        ("", "No bio yet", 1, "1 friend"),
        ("Coffee and trails", "Coffee and trails", 3, "3 friends"),
    ],
)
def test_profile_by_id_shows_name_handle_bio_and_friend_count(
    bio: str, expected_bio: str, friend_count: int, expected_friends: str
) -> None:
    u = user_profile(ERIN, bio=bio, relationship="none", friend_count=friend_count)
    res = open_profile(
        params={"id": "5"},
        api={"GET /api/users/5": {"user": u}},
    )
    assert res.errors == [] and res.unmatched == []
    assert (res.page, res.title) == ("profile", "Profile")
    assert res.calls == [["GET", "/api/users/5", None]]
    expected_text = f"Erin Evans @erin {expected_bio} {expected_friends} Add friend"
    assert res.text == expected_text
    assert res.classes[0] == ["stack", expected_text]
    assert ["row", "Erin Evans"] in res.classes
    assert any(c[0] == "avatar" for c in res.classes)
    assert ["muted", "@erin"] in res.classes
    assert ["muted", expected_friends] in res.classes
    assert res.labels == ["Add friend"]
    assert res.forms == []


def test_relationship_none_add_friend_posts_request_and_refreshes() -> None:
    u_before = user_profile(ERIN, bio="Hello there", relationship="none", friend_count=2)
    u_after = user_profile(
        ERIN, bio="Hello there", relationship="request_sent", friend_count=2, request_id=9
    )
    res = open_profile(
        params={"id": "5"},
        api={
            "GET /api/users/5": [{"user": u_before}, {"user": u_after}],
            "POST /api/friends/requests": {"$status": 201, "request": {"id": 9}},
        },
        steps=[{"click": "Add friend"}],
    )
    assert res.errors == [] and res.unmatched == []
    assert res.calls == [
        ["GET", "/api/users/5", None],
        ["POST", "/api/friends/requests", {"user_id": 5}],
        ["GET", "/api/users/5", None],
    ]
    assert res.count("GET", "/api/users/5") == 2
    assert res.labels == ["Cancel request"]


def test_relationship_request_sent_cancel_deletes_request_and_refreshes() -> None:
    u_sent = user_profile(ERIN, relationship="request_sent", friend_count=1, request_id=9)
    u_none = user_profile(ERIN, relationship="none", friend_count=1)
    res = open_profile(
        params={"id": "5"},
        api={
            "GET /api/users/5": [{"user": u_sent}, {"user": u_none}],
            "DELETE /api/friends/requests/9": {"ok": True},
        },
        steps=[{"click": "Cancel request"}],
    )
    assert res.errors == [] and res.unmatched == []
    assert res.calls == [
        ["GET", "/api/users/5", None],
        ["DELETE", "/api/friends/requests/9", None],
        ["GET", "/api/users/5", None],
    ]
    assert res.count("GET", "/api/users/5") == 2
    assert res.labels == ["Add friend"]


def test_relationship_request_received_accept_posts_accept_and_refreshes() -> None:
    u_rec = user_profile(ERIN, relationship="request_received", friend_count=1, request_id=17)
    u_friends = user_profile(ERIN, relationship="friends", friend_count=2)
    res = open_profile(
        params={"id": "5"},
        api={
            "GET /api/users/5": [{"user": u_rec}, {"user": u_friends}],
            "POST /api/friends/requests/17/accept": {"ok": True},
        },
        steps=[{"click": "Accept"}],
    )
    assert res.errors == [] and res.unmatched == []
    assert res.calls == [
        ["GET", "/api/users/5", None],
        ["POST", "/api/friends/requests/17/accept", None],
        ["GET", "/api/users/5", None],
    ]
    assert res.count("GET", "/api/users/5") == 2
    assert res.labels == ["Message", "Unfriend"]
    assert "2 friends" in res.text


def test_relationship_friends_message_opens_dm_chat() -> None:
    u_friends = user_profile(ERIN, bio="Sketching", relationship="friends", friend_count=3)
    res_shown = open_profile(
        params={"id": "5"},
        api={"GET /api/users/5": {"user": u_friends}},
    )
    assert res_shown.errors == [] and res_shown.unmatched == []
    assert ["row", "Message Unfriend"] in res_shown.classes
    assert res_shown.labels == ["Message", "Unfriend"]

    res = open_profile(
        params={"id": "5"},
        api={
            "GET /api/users/5": {"user": u_friends},
            "POST /api/dm": {"conversation": {"id": 14}},
        },
        steps=[{"click": "Message"}],
    )
    assert res.errors == [] and res.unmatched == []
    assert res.calls == [
        ["GET", "/api/users/5", None],
        ["POST", "/api/dm", {"user_id": 5}],
    ]
    assert res.count("GET", "/api/users/5") == 1
    assert res.nav == [["chat", {"id": "14"}]]


def test_relationship_friends_unfriend_deletes_friendship_and_refreshes() -> None:
    u_friends = user_profile(ERIN, relationship="friends", friend_count=3)
    u_none = user_profile(ERIN, relationship="none", friend_count=2)
    res = open_profile(
        params={"id": "5"},
        api={
            "GET /api/users/5": [{"user": u_friends}, {"user": u_none}],
            "DELETE /api/friends/5": {"ok": True},
        },
        steps=[{"click": "Unfriend"}],
    )
    assert res.errors == [] and res.unmatched == []
    assert res.calls == [
        ["GET", "/api/users/5", None],
        ["DELETE", "/api/friends/5", None],
        ["GET", "/api/users/5", None],
    ]
    assert res.count("GET", "/api/users/5") == 2
    assert res.nav == []
    assert res.labels == ["Add friend"]
    assert "2 friends" in res.text


def test_own_profile_without_params_loads_me_and_prefills_form() -> None:
    u_self = user_profile(ALICE, bio="Reading sci-fi", relationship="self", friend_count=4)
    res = open_profile(
        params={},
        me=ALICE,
        api={"GET /api/users/1": {"user": u_self}},
    )
    assert res.errors == [] and res.unmatched == []
    assert res.calls == [["GET", "/api/users/1", None]]
    assert res.text == "Alice Adams @alice Reading sci-fi 4 friends Display name Bio Save profile"
    assert res.forms == [
        {
            "submit": "Save profile",
            "fields": ["display_name", "bio"],
            "types": {"display_name": "text", "bio": "textarea"},
            "options": {},
            "values": {"display_name": "Alice Adams", "bio": "Reading sci-fi"},
        }
    ]

    u_dan = user_profile(DAN, bio="Biking", relationship="self", friend_count=2)
    res_dan = open_profile(
        params={},
        me=DAN,
        api={"GET /api/users/4": {"user": u_dan}},
    )
    assert res_dan.errors == [] and res_dan.unmatched == []
    assert res_dan.calls == [["GET", "/api/users/4", None]]
    assert "Dan Diaz @dan Biking 2 friends" in res_dan.text


def test_save_profile_puts_values_toasts_reloads_session_and_refreshes() -> None:
    u_before = user_profile(ALICE, bio="Old bio", relationship="self", friend_count=1)
    updated_alice = {"id": 1, "username": "alice", "display_name": "Alice A. Updated"}
    u_after = user_profile(updated_alice, bio="New bio line", relationship="self", friend_count=1)
    res = open_profile(
        params={},
        me=ALICE,
        api={
            "GET /api/users/1": [{"user": u_before}, {"user": u_after}],
            "PUT /api/profile": {"user": u_after},
            "GET /api/session": {"user": updated_alice},
        },
        steps=[
            {
                "submit": "Save profile",
                "values": {"display_name": "Alice A. Updated", "bio": "New bio line"},
            }
        ],
    )
    assert res.errors == [] and res.unmatched == []
    assert res.calls == [
        ["GET", "/api/users/1", None],
        ["PUT", "/api/profile", {"display_name": "Alice A. Updated", "bio": "New bio line"}],
        ["GET", "/api/session", None],
        ["GET", "/api/users/1", None],
    ]
    assert res.count("GET", "/api/users/1") == 2
    assert res.count("GET", "/api/session") == 1
    assert res.toasts == ["Profile saved"]
    assert "Alice A. Updated @alice New bio line 1 friend" in res.text


def test_lives_in_its_own_feature_folder() -> None:
    res = run_page("page_profile", None)
    assert res.errors == [] and res.unmatched == []
    assert "profile" in [p["name"] for p in res.pages]
