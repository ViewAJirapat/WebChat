import importlib

import pytest

from chatbook.testing import Client

REG = "/api/auth/register"
LOGIN = "/api/auth/login"
GOOD = {"username": "quinn_42", "password": "hunter-22x", "display_name": "Quinn Q"}


def user_ids(c: Client) -> list[int]:
    return [int(r["id"]) for r in c.rows("SELECT id FROM users ORDER BY id")]


def session_count(c: Client) -> int:
    return len(c.rows("SELECT token_hash FROM sessions"))


# -- register ---------------------------------------------------------------------------


def test_register_returns_201_with_token_and_user() -> None:
    c = Client()
    c.tick(4321)
    r = c.post(REG, {"username": "  Quinn_42 ", "password": "hunter-22x",
                     "display_name": "  Quinn Q  "})
    assert r.status == 201
    assert set(r.json) == {"token", "user"}
    assert r.json["user"] == {"id": 1, "username": "quinn_42", "display_name": "Quinn Q"}
    assert isinstance(r.json["token"], str) and r.json["token"]
    me = c.get("/api/session", token=r.json["token"])
    assert (me.status, me.json) == (200, {"user": r.json["user"]})


def test_register_stores_the_user_and_one_session() -> None:
    c = Client()
    c.tick(98_765)
    r = c.post(REG, {"username": "Sol_77", "password": "sun-and-moon",
                     "display_name": " Sol  Varga "})
    assert r.status == 201
    row = c.row("SELECT id, username, display_name, bio, created_at, password_hash FROM users")
    assert row is not None
    assert {k: row[k] for k in ("id", "username", "display_name", "bio", "created_at")} == {
        "id": 1, "username": "sol_77", "display_name": "Sol  Varga", "bio": "",
        "created_at": c.now,
    }
    assert "sun-and-moon" not in row["password_hash"]
    assert c.rows("SELECT user_id, created_at FROM sessions") == [
        {"user_id": 1, "created_at": c.now}
    ]


def test_register_ids_follow_existing_users_and_tokens_are_per_user() -> None:
    c = Client()
    c.user("ann")
    c.user("ben")
    first = c.post(REG, {"username": "Cleo_3", "password": "cleo-pass-3", "display_name": "Cleo"})
    c.tick()
    second = c.post(REG, {"username": "dex", "password": "dex-pass-44", "display_name": "Dex D"})
    assert (first.status, second.status) == (201, 201)
    assert first.json["user"] == {"id": 3, "username": "cleo_3", "display_name": "Cleo"}
    assert second.json["user"] == {"id": 4, "username": "dex", "display_name": "Dex D"}
    assert first.json["token"] != second.json["token"]
    assert c.get("/api/session", token=first.json["token"]).json == {"user": first.json["user"]}
    assert c.get("/api/session", token=second.json["token"]).json == {"user": second.json["user"]}


@pytest.mark.parametrize(("raw", "stored"), [
    ("abc", "abc"), ("ABC", "abc"), ("x" * 20, "x" * 20), ("  " + "Y" * 20 + "  ", "y" * 20),
    ("007", "007"), ("___", "___"), ("Mr_Big_9", "mr_big_9"), ("\tzz9\n", "zz9"),
])
def test_register_accepts_and_lowercases_valid_usernames(raw: str, stored: str) -> None:
    c = Client()
    r = c.post(REG, GOOD | {"username": raw})
    assert r.status == 201
    assert r.json["user"] == {"id": 1, "username": stored, "display_name": "Quinn Q"}
    assert c.rows("SELECT username FROM users") == [{"username": stored}]


@pytest.mark.parametrize("username", [
    "ab", "  ab  ", "a b c", "x" * 21, "bad-name", "dot.name", "abc!", "jos\u00e9", "", "   ",
    123, None, True, ["abc"],
])
def test_register_rejects_bad_username(username: object) -> None:
    c = Client()
    assert c.post(REG, GOOD | {"username": username}).status == 400
    assert user_ids(c) == [] and session_count(c) == 0


@pytest.mark.parametrize("password", ["x" * 8, "y" * 128, "   ab   ", "        ", "UPPER-low 8"])
def test_register_accepts_password_lengths_without_stripping(password: str) -> None:
    c = Client()
    assert c.post(REG, GOOD | {"password": password}).status == 201
    assert c.post(LOGIN, {"username": "quinn_42", "password": password}).status == 200


@pytest.mark.parametrize("password", ["x" * 7, "  abc  ", "z" * 129, "", 12345678, None])
def test_register_rejects_bad_password(password: object) -> None:
    c = Client()
    assert c.post(REG, GOOD | {"password": password}).status == 400
    assert user_ids(c) == [] and session_count(c) == 0


@pytest.mark.parametrize(("raw", "stored"), [
    ("d" * 50, "d" * 50), ("  " + "E" * 50 + " ", "E" * 50), ("Zed  Hale", "Zed  Hale"),
    ("x", "x"), ("O'Neil-Ruiz 3", "O'Neil-Ruiz 3"),
])
def test_register_display_name_is_stripped_not_changed(raw: str, stored: str) -> None:
    c = Client()
    r = c.post(REG, GOOD | {"display_name": raw})
    assert r.status == 201
    assert r.json["user"]["display_name"] == stored
    assert c.rows("SELECT display_name FROM users") == [{"display_name": stored}]


@pytest.mark.parametrize("display_name", ["   ", "", "e" * 51, 42, None, ["Quinn"]])
def test_register_rejects_bad_display_name(display_name: object) -> None:
    c = Client()
    assert c.post(REG, GOOD | {"display_name": display_name}).status == 400
    assert user_ids(c) == [] and session_count(c) == 0


@pytest.mark.parametrize("missing", ["username", "password", "display_name"])
def test_register_rejects_missing_field(missing: str) -> None:
    c = Client()
    body = {k: v for k, v in GOOD.items() if k != missing}
    assert c.post(REG, body).status == 400
    assert user_ids(c) == []


@pytest.mark.parametrize("body", [None, ["quinn_42", "hunter-22x", "Quinn Q"], "quinn_42", 7])
def test_register_rejects_non_object_body(body: object) -> None:
    c = Client()
    assert c.post(REG, body).status == 400
    assert user_ids(c) == []


def test_register_taken_username_is_409_ignoring_case() -> None:
    c = Client()
    c.user("rhea_5", "Rhea")
    r = c.post(REG, GOOD | {"username": "  RHEA_5 "})
    assert r.status == 409
    assert user_ids(c) == [1] and session_count(c) == 1


def test_register_twice_is_409_then_another_name_works() -> None:
    c = Client()
    assert c.post(REG, GOOD | {"username": "Theo_1"}).status == 201
    assert c.post(REG, GOOD | {"username": "theo_1", "display_name": "Other"}).status == 409
    r = c.post(REG, GOOD | {"username": "theo_2"})
    assert r.status == 201
    assert r.json["user"] == {"id": 2, "username": "theo_2", "display_name": "Quinn Q"}
    assert c.rows("SELECT display_name FROM users WHERE username = ?", "theo_1") == [
        {"display_name": "Quinn Q"}
    ]


# -- login ------------------------------------------------------------------------------


def test_login_returns_200_with_new_token_and_user() -> None:
    c = Client()
    c.user("ivy", "Ivy Ito", password="ivy-pass-9")
    jon = c.user("jon", "Jon Jansen", password="jon-pass-9")
    c.user("kim", "Kim Kerr", password="kim-pass-9")
    c.tick(777)
    r = c.post(LOGIN, {"username": " JON ", "password": "jon-pass-9"})
    assert r.status == 200
    assert set(r.json) == {"token", "user"}
    assert r.json["user"] == jon.json
    assert r.json["token"] != jon.token
    assert c.get("/api/session", token=r.json["token"]).json == {"user": jon.json}
    assert c.get("/api/session", token=jon.token).json == {"user": jon.json}
    rows = c.rows("SELECT created_at FROM sessions WHERE user_id = ? ORDER BY created_at", jon.id)
    assert rows == [{"created_at": c.now - 777}, {"created_at": c.now}]


def test_login_twice_gives_two_working_tokens() -> None:
    c = Client()
    lea = c.user("lea", "Lea L", password="lea-secret")
    one = c.post(LOGIN, {"username": "lea", "password": "lea-secret"})
    two = c.post(LOGIN, {"username": "lea", "password": "lea-secret"})
    assert (one.status, two.status) == (200, 200)
    assert len({one.json["token"], two.json["token"], lea.token}) == 3
    for token in (one.json["token"], two.json["token"]):
        assert c.get("/api/session", token=token).json == {"user": lea.json}


@pytest.mark.parametrize("typed", ["ivy", "IVY", "  Ivy\t", "iVy "])
def test_login_username_is_stripped_and_lowercased(typed: str) -> None:
    c = Client()
    c.user("hal", password="hal-pass-1")
    ivy = c.user("ivy", "Ivy Ito", password="ivy-pass-9")
    r = c.post(LOGIN, {"username": typed, "password": "ivy-pass-9"})
    assert (r.status, r.json["user"]) == (200, ivy.json)


def test_login_has_no_register_length_or_pattern_rules() -> None:
    c = Client()
    long_name = c.user("m" * 30, "Long Name", password="long-pass-1")
    short_pw = c.user("nia", "Nia N", password="abc")
    r1 = c.post(LOGIN, {"username": "M" * 30, "password": "long-pass-1"})
    r2 = c.post(LOGIN, {"username": "nia", "password": "abc"})
    assert (r1.status, r1.json["user"]) == (200, long_name.json)
    assert (r2.status, r2.json["user"]) == (200, short_pw.json)


@pytest.mark.parametrize("creds", [
    {"username": "ivy", "password": "ivy-pass-8"},
    {"username": "ivy", "password": "IVY-PASS-9"},
    {"username": "ivy", "password": "jon-pass-9"},
    {"username": "jon", "password": "ivy-pass-9"},
    {"username": "ghost", "password": "ivy-pass-9"},
    {"username": "g" * 50, "password": "ivy-pass-9"},
    {"username": "ivy", "password": "w" * 128},
    {"username": "ivy", "password": " "},
])
def test_login_wrong_credentials_are_401(creds: dict[str, object]) -> None:
    c = Client()
    c.user("ivy", "Ivy Ito", password="ivy-pass-9")
    c.user("jon", "Jon Jansen", password="jon-pass-9")
    assert c.post(LOGIN, creds).status == 401
    assert session_count(c) == 2


def test_login_password_is_not_stripped() -> None:
    c = Client()
    c.user("ora", "Ora O", password="  open sesame  ")
    assert c.post(LOGIN, {"username": "ora", "password": "open sesame"}).status == 401
    assert c.post(LOGIN, {"username": "ora", "password": "  open sesame "}).status == 401
    assert c.post(LOGIN, {"username": "ora", "password": "  open sesame  "}).status == 200


def test_registered_user_can_log_in() -> None:
    c = Client()
    reg = c.post(REG, {"username": "Wes_8", "password": " Tab\tPass 1", "display_name": "Wes W"})
    assert reg.status == 201
    assert c.post(LOGIN, {"username": "wes_8", "password": " tab\tpass 1"}).status == 401
    r = c.post(LOGIN, {"username": "WES_8", "password": " Tab\tPass 1"})
    assert (r.status, r.json["user"]) == (200, reg.json["user"])
    assert r.json["token"] != reg.json["token"]


@pytest.mark.parametrize("creds", [
    {"username": "", "password": "ivy-pass-9"},
    {"username": "   ", "password": "ivy-pass-9"},
    {"username": "u" * 51, "password": "ivy-pass-9"},
    {"username": 7, "password": "ivy-pass-9"},
    {"username": None, "password": "ivy-pass-9"},
    {"password": "ivy-pass-9"},
    {"username": "ivy", "password": ""},
    {"username": "ivy", "password": "p" * 129},
    {"username": "ivy", "password": 12345678},
    {"username": "ivy", "password": None},
    {"username": "ivy"},
])
def test_login_rejects_bad_fields(creds: dict[str, object]) -> None:
    c = Client()
    c.user("ivy", "Ivy Ito", password="ivy-pass-9")
    assert c.post(LOGIN, creds).status == 400
    assert session_count(c) == 1


@pytest.mark.parametrize("body", [None, ["ivy", "ivy-pass-9"], "ivy", 3])
def test_login_rejects_non_object_body(body: object) -> None:
    c = Client()
    c.user("ivy", "Ivy Ito", password="ivy-pass-9")
    assert c.post(LOGIN, body).status == 400


def test_lives_in_its_own_feature_folder() -> None:
    importlib.import_module("chatbook.features.accounts.handler")
