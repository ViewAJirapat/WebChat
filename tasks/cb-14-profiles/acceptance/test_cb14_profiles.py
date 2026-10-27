import importlib

import pytest

from chatbook.testing import Account, Client

USERS_URL = "/api/users"
PROFILE_URL = "/api/profile"


def cast(c: Client) -> tuple[Account, Account, Account, Account, Account]:
    """Five users created at distinct timestamps. None has id 1 as the only tested subject."""
    lara = c.user("lara", "Lara Lin")
    c.tick(1000)
    milo = c.user("milo", "Milo Moss")
    c.tick(2000)
    nora = c.user("nora", "Nora Nash")
    c.tick(3000)
    omar = c.user("omar", "Omar Odom")
    c.tick(4000)
    petra = c.user("petra", "Petra Park")
    return lara, milo, nora, omar, petra


def set_bio(c: Client, user: Account, bio: str) -> None:
    with c._tx():
        c.db.run("UPDATE users SET bio = ? WHERE id = ?", bio, user.id)


def profile_json(
    c: Client,
    user: Account,
    *,
    display_name: str | None = None,
    bio: str = "",
    relationship: str,
    friend_count: int = 0,
    request_id: int | None = None,
) -> dict[str, object]:
    row = c.row("SELECT created_at FROM users WHERE id = ?", user.id)
    assert row is not None
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name if display_name is None else display_name,
        "bio": bio,
        "joined_at": row["created_at"],
        "relationship": relationship,
        "friend_count": friend_count,
        "request_id": request_id,
    }


# -- GET /api/users/{id} ------------------------------------------------------------------


def test_get_stranger_profile() -> None:
    c = Client()
    lara, milo, nora, *_ = cast(c)
    set_bio(c, milo, "mountain biker")
    c.befriend(milo, nora)
    r = c.get(f"{USERS_URL}/{milo.id}", user=lara)
    assert r.status == 200
    assert r.json == {
        "user": profile_json(
            c,
            milo,
            bio="mountain biker",
            relationship="none",
            friend_count=1,
            request_id=None,
        )
    }


def test_get_profile_when_request_sent_picks_exact_request_id() -> None:
    c = Client()
    lara, milo, nora, omar, petra = cast(c)
    # Unrelated friend requests before and after the one between milo and nora
    c.friend_request(lara, omar)
    c.friend_request(petra, milo)
    rid = c.friend_request(milo, nora)
    c.friend_request(nora, omar)
    c.friend_request(milo, petra)
    set_bio(c, nora, "cellist")
    r = c.get(f"{USERS_URL}/{nora.id}", user=milo)
    assert r.status == 200
    assert r.json == {
        "user": profile_json(
            c,
            nora,
            bio="cellist",
            relationship="request_sent",
            friend_count=0,
            request_id=rid,
        )
    }


def test_get_profile_when_request_received_picks_exact_request_id() -> None:
    c = Client()
    lara, milo, nora, omar, petra = cast(c)
    c.friend_request(lara, milo)
    c.friend_request(nora, petra)
    rid = c.friend_request(omar, milo)
    c.friend_request(omar, lara)
    c.befriend(omar, petra)
    r = c.get(f"{USERS_URL}/{omar.id}", user=milo)
    assert r.status == 200
    assert r.json == {
        "user": profile_json(
            c,
            omar,
            bio="",
            relationship="request_received",
            friend_count=1,
            request_id=rid,
        )
    }


@pytest.mark.parametrize("target_friends", [0, 1, 3])
def test_get_friend_count_counts_targets_friends(target_friends: int) -> None:
    c = Client()
    lara, milo, nora, omar, petra = cast(c)
    # Give viewer (lara) 2 friends so viewer's friend_count != target's friend_count when 0, 1, 3
    c.befriend(lara, omar)
    c.befriend(lara, petra)
    others = [nora, omar, petra]
    for pal in others[:target_friends]:
        c.befriend(milo, pal)
    r = c.get(f"{USERS_URL}/{milo.id}", user=lara)
    assert r.status == 200
    assert r.json == {
        "user": profile_json(
            c,
            milo,
            relationship="none",
            friend_count=target_friends,
            request_id=None,
        )
    }


def test_get_profile_when_friends() -> None:
    c = Client()
    lara, milo, nora, omar, _ = cast(c)
    c.befriend(lara, milo)
    c.befriend(milo, nora)
    c.befriend(milo, omar)
    c.friend_request(lara, nora)
    set_bio(c, milo, "baker")
    r = c.get(f"{USERS_URL}/{milo.id}", user=lara)
    assert r.status == 200
    assert r.json == {
        "user": profile_json(
            c,
            milo,
            bio="baker",
            relationship="friends",
            friend_count=3,
            request_id=None,
        )
    }


def test_get_own_profile() -> None:
    c = Client()
    lara, milo, nora, omar, _ = cast(c)
    c.befriend(milo, lara)
    c.befriend(milo, nora)
    c.friend_request(omar, milo)
    set_bio(c, milo, "my own bio")
    r = c.get(f"{USERS_URL}/{milo.id}", user=milo)
    assert r.status == 200
    assert r.json == {
        "user": profile_json(
            c,
            milo,
            bio="my own bio",
            relationship="self",
            friend_count=2,
            request_id=None,
        )
    }


@pytest.mark.parametrize("raw", ["999", "abc", "0", "-1", "1.5", "2x"])
def test_get_unknown_or_bad_id_is_404(raw: str) -> None:
    c = Client()
    lara, *_ = cast(c)
    assert c.get(f"{USERS_URL}/{raw}", user=lara).status == 404


# -- PUT /api/profile ---------------------------------------------------------------------


def test_update_profile_persists_and_returns_updated_self_profile() -> None:
    c = Client()
    lara, milo, nora, omar, _ = cast(c)
    c.befriend(milo, lara)
    c.befriend(milo, nora)
    c.friend_request(omar, milo)
    before_others = c.rows(
        "SELECT id, username, display_name, bio, password_hash, created_at"
        " FROM users WHERE id != ? ORDER BY id",
        milo.id,
    )
    before_milo = c.row(
        "SELECT username, password_hash, created_at FROM users WHERE id = ?", milo.id
    )
    c.tick(5000)
    r = c.put(
        PROFILE_URL,
        {"display_name": "  Milo M.  ", "bio": "  plays chess and reads  "},
        user=milo,
    )
    assert r.status == 200
    expected = profile_json(
        c,
        milo,
        display_name="Milo M.",
        bio="plays chess and reads",
        relationship="self",
        friend_count=2,
        request_id=None,
    )
    assert r.json == {"user": expected}
    assert c.row("SELECT display_name, bio FROM users WHERE id = ?", milo.id) == {
        "display_name": "Milo M.",
        "bio": "plays chess and reads",
    }
    assert (
        c.row("SELECT username, password_hash, created_at FROM users WHERE id = ?", milo.id)
        == before_milo
    )
    after_others = c.rows(
        "SELECT id, username, display_name, bio, password_hash, created_at"
        " FROM users WHERE id != ? ORDER BY id",
        milo.id,
    )
    assert after_others == before_others
    # Subsequent GET reflects the persisted changes
    get_self = c.get(f"{USERS_URL}/{milo.id}", user=milo)
    assert get_self.status == 200
    assert get_self.json == {"user": expected}
    get_as_friend = c.get(f"{USERS_URL}/{milo.id}", user=lara)
    assert get_as_friend.status == 200
    assert get_as_friend.json == {"user": expected | {"relationship": "friends"}}


@pytest.mark.parametrize(
    ("raw_name", "raw_bio", "stored_name", "stored_bio"),
    [
        ("K", "", "K", ""),
        ("Lara", "   \t\n  ", "Lara", ""),
        ("d" * 50, "b" * 300, "d" * 50, "b" * 300),
        ("  " + "n" * 50 + "\n", "  " + "x" * 300 + "\t", "n" * 50, "x" * 300),
        ("Milo   Moss", "line one\nline two", "Milo   Moss", "line one\nline two"),
    ],
)
def test_update_profile_boundary_lengths_and_stripping(
    raw_name: str, raw_bio: str, stored_name: str, stored_bio: str
) -> None:
    c = Client()
    lara, milo, *_ = cast(c)
    set_bio(c, milo, "initial bio")
    r = c.put(PROFILE_URL, {"display_name": raw_name, "bio": raw_bio}, user=milo)
    assert r.status == 200
    assert r.json == {
        "user": profile_json(
            c,
            milo,
            display_name=stored_name,
            bio=stored_bio,
            relationship="self",
            friend_count=0,
            request_id=None,
        )
    }
    assert c.row("SELECT display_name, bio FROM users WHERE id = ?", milo.id) == {
        "display_name": stored_name,
        "bio": stored_bio,
    }
    assert c.row("SELECT display_name, bio FROM users WHERE id = ?", lara.id) == {
        "display_name": "Lara Lin",
        "bio": "",
    }


@pytest.mark.parametrize(
    "bad_name",
    ["", "   ", "\t\n", "d" * 51, "  " + "d" * 51 + "  ", 123, None, True, ["Milo"], {"a": "b"}],
)
def test_update_profile_bad_display_name_is_400(bad_name: object) -> None:
    c = Client()
    _, milo, *_ = cast(c)
    set_bio(c, milo, "keep me")
    r = c.put(PROFILE_URL, {"display_name": bad_name, "bio": "new bio"}, user=milo)
    assert r.status == 400
    assert c.row("SELECT display_name, bio FROM users WHERE id = ?", milo.id) == {
        "display_name": "Milo Moss",
        "bio": "keep me",
    }


def test_update_profile_missing_display_name_is_400() -> None:
    c = Client()
    _, milo, *_ = cast(c)
    set_bio(c, milo, "keep me")
    r = c.put(PROFILE_URL, {"bio": "new bio"}, user=milo)
    assert r.status == 400
    assert c.row("SELECT display_name, bio FROM users WHERE id = ?", milo.id) == {
        "display_name": "Milo Moss",
        "bio": "keep me",
    }


@pytest.mark.parametrize(
    "bad_bio",
    ["b" * 301, "  " + "b" * 301 + "  ", 5, None, True, ["bio"], {"bio": "x"}],
)
def test_update_profile_bad_bio_is_400(bad_bio: object) -> None:
    c = Client()
    _, milo, *_ = cast(c)
    set_bio(c, milo, "keep me")
    r = c.put(PROFILE_URL, {"display_name": "New Name", "bio": bad_bio}, user=milo)
    assert r.status == 400
    assert c.row("SELECT display_name, bio FROM users WHERE id = ?", milo.id) == {
        "display_name": "Milo Moss",
        "bio": "keep me",
    }


def test_update_profile_missing_bio_is_400() -> None:
    c = Client()
    _, milo, *_ = cast(c)
    set_bio(c, milo, "keep me")
    r = c.put(PROFILE_URL, {"display_name": "New Name"}, user=milo)
    assert r.status == 400
    assert c.row("SELECT display_name, bio FROM users WHERE id = ?", milo.id) == {
        "display_name": "Milo Moss",
        "bio": "keep me",
    }


@pytest.mark.parametrize("body", [["Milo", "bio"], "str", None, 42, True])
def test_update_profile_non_object_body_is_400(body: object) -> None:
    c = Client()
    _, milo, *_ = cast(c)
    set_bio(c, milo, "keep me")
    r = c.put(PROFILE_URL, body, user=milo)
    assert r.status == 400
    assert c.row("SELECT display_name, bio FROM users WHERE id = ?", milo.id) == {
        "display_name": "Milo Moss",
        "bio": "keep me",
    }


def test_lives_in_its_own_feature_folder() -> None:
    importlib.import_module("chatbook.features.profiles.handler")
