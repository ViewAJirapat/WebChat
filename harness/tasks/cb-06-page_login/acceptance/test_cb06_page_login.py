import pytest

from chatbook.testing import DAN, ERIN, FRANK, UiResult, run_page

QUINN = {"id": 42, "username": "quinn_q", "display_name": "Quinn Quill"}

TEXT = (
    "Log in Username Password Log in Create account Username Display name Password Create account"
)
LOGIN_FORM = {
    "submit": "Log in",
    "fields": ["username", "password"],
    "types": {"username": "text", "password": "password"},
    "options": {},
    "values": {"username": "", "password": ""},
}
REGISTER_FORM = {
    "submit": "Create account",
    "fields": ["username", "display_name", "password"],
    "types": {"username": "text", "display_name": "text", "password": "password"},
    "options": {},
    "values": {"username": "", "display_name": "", "password": ""},
}


def open_login(
    api: dict[str, object] | None = None, steps: list[dict[str, object]] | None = None
) -> UiResult:
    """The login page, logged out."""
    return run_page("page_login", "login", me=None, api=api, steps=steps)


def test_page_is_public_titled_welcome_without_nav() -> None:
    res = run_page("page_login", None, me=None)
    assert res.errors == []
    assert res.pages == [
        {
            "name": "login",
            "title": "Welcome",
            "nav": None,
            "order": 100,
            "public": True,
            "file": "page_login",
        }
    ]


def test_shows_two_headings_and_two_forms_in_order_without_api_calls() -> None:
    res = open_login(steps=[{"tick": 10000}])
    assert res.errors == [] and res.unmatched == []
    assert (res.page, res.title) == ("login", "Welcome")
    assert res.calls == []
    assert res.forms == [LOGIN_FORM, REGISTER_FORM]
    assert res.text == TEXT
    assert res.classes[0] == ["stack narrow", TEXT]
    assert res.labels == ["Log in", "Create account"]
    assert not any(b["disabled"] for b in res.buttons)
    assert res.session == [] and res.nav == [] and res.toasts == []


@pytest.mark.parametrize(
    ("username", "password", "token", "user"),
    [
        ("dan", "dan-pass-77", "tok-d4", DAN),
        ("  Frank ", " two words ", "zz9", FRANK),
        ("QUINN_Q", "p@ss word!", "a.b.c", QUINN),
    ],
)
def test_log_in_posts_typed_values_then_logs_in_with_the_answer(
    username: str, password: str, token: str, user: dict[str, object]
) -> None:
    res = open_login(
        api={"POST /api/auth/login": {"token": token, "user": user}},
        steps=[{"submit": "Log in", "values": {"username": username, "password": password}}],
    )
    assert res.errors == [] and res.unmatched == []
    assert res.calls == [["POST", "/api/auth/login", {"username": username, "password": password}]]
    assert res.session == [["login", token, user]]
    assert res.nav == [["inbox", {}]]
    assert res.toasts == []


@pytest.mark.parametrize(
    ("values", "token", "user"),
    [
        (
            {"username": "erin", "display_name": "Erin Evans", "password": "erin-secret"},
            "reg-1",
            ERIN,
        ),
        (
            {"username": " Quinn_Q", "display_name": "  Quinn Quill ", "password": " spaced pw "},
            "t-777",
            QUINN,
        ),
    ],
)
def test_create_account_posts_typed_values_then_logs_in_with_the_answer(
    values: dict[str, str], token: str, user: dict[str, object]
) -> None:
    res = open_login(
        api={"POST /api/auth/register": {"$status": 201, "token": token, "user": user}},
        steps=[{"submit": "Create account", "values": values}],
    )
    assert res.errors == [] and res.unmatched == []
    body = {
        "username": values["username"],
        "password": values["password"],
        "display_name": values["display_name"],
    }
    assert res.calls == [["POST", "/api/auth/register", body]]
    assert res.session == [["login", token, user]]
    assert res.nav == [["inbox", {}]]
    assert res.toasts == []


@pytest.mark.parametrize("status", [401, 400])
def test_failed_log_in_shows_the_server_message_and_stays(status: int) -> None:
    res = open_login(
        api={"POST /api/auth/login": {"$status": status, "error": "no luck this time"}},
        steps=[{"submit": "Log in", "values": {"username": "dan", "password": "wrong-one"}}],
    )
    assert res.errors == [] and res.unmatched == []
    assert res.calls == [["POST", "/api/auth/login", {"username": "dan", "password": "wrong-one"}]]
    assert res.session == [] and res.nav == []
    assert res.toasts == ["no luck this time"]
    assert res.page == "login"
    assert [f["submit"] for f in res.forms] == ["Log in", "Create account"]
    assert res.forms[0]["values"] == {"username": "dan", "password": "wrong-one"}


@pytest.mark.parametrize("status", [409, 400])
def test_failed_create_account_shows_the_server_message_and_stays(status: int) -> None:
    values = {"username": "frank", "display_name": "Frank F", "password": "frank-pass"}
    res = open_login(
        api={"POST /api/auth/register": {"$status": status, "error": "pick another one"}},
        steps=[{"submit": "Create account", "values": values}],
    )
    assert res.errors == [] and res.unmatched == []
    body = {"username": "frank", "password": "frank-pass", "display_name": "Frank F"}
    assert res.calls == [["POST", "/api/auth/register", body]]
    assert res.session == [] and res.nav == []
    assert res.toasts == ["pick another one"]
    assert res.page == "login"
    assert [f["submit"] for f in res.forms] == ["Log in", "Create account"]
    assert res.forms[1]["values"] == values


def test_log_in_can_be_retried_after_a_failure() -> None:
    res = open_login(
        api={
            "POST /api/auth/login": [
                {"$status": 401, "error": "try again"},
                {"token": "tok-r2", "user": FRANK},
            ]
        },
        steps=[
            {"submit": "Log in", "values": {"username": "frank", "password": "bad-guess"}},
            {"submit": "Log in", "values": {"password": "good-guess"}},
        ],
    )
    assert res.errors == [] and res.unmatched == []
    assert res.calls == [
        ["POST", "/api/auth/login", {"username": "frank", "password": "bad-guess"}],
        ["POST", "/api/auth/login", {"username": "frank", "password": "good-guess"}],
    ]
    assert res.toasts == ["try again"]
    assert res.session == [["login", "tok-r2", FRANK]]
    assert res.nav == [["inbox", {}]]


@pytest.mark.parametrize(
    ("label", "path", "body"),
    [
        ("Log in", "/api/auth/login", {"username": "", "password": ""}),
        (
            "Create account",
            "/api/auth/register",
            {"username": "", "password": "", "display_name": ""},
        ),
    ],
)
def test_empty_fields_are_sent_without_checks(label: str, path: str, body: dict[str, str]) -> None:
    res = open_login(
        api={"POST " + path: {"$status": 400, "error": "fill in the fields"}},
        steps=[{"submit": label}],
    )
    assert res.errors == [] and res.unmatched == []
    assert res.calls == [["POST", path, body]]
    assert res.session == [] and res.nav == []
    assert res.toasts == ["fill in the fields"]


def test_each_form_sends_only_its_own_fields() -> None:
    res = open_login(
        api={"POST /api/auth/register": {"$status": 201, "token": "tok-e", "user": ERIN}},
        steps=[
            {"fill": "Log in", "values": {"username": "dan", "password": "login-side"}},
            {
                "submit": "Create account",
                "values": {"username": "erin", "display_name": "E E", "password": "reg-side"},
            },
        ],
    )
    assert res.errors == [] and res.unmatched == []
    body = {"username": "erin", "password": "reg-side", "display_name": "E E"}
    assert res.calls == [["POST", "/api/auth/register", body]]
    assert res.session == [["login", "tok-e", ERIN]]

    res = open_login(
        api={"POST /api/auth/login": {"token": "tok-d", "user": DAN}},
        steps=[
            {
                "fill": "Create account",
                "values": {"username": "erin", "display_name": "E E", "password": "reg-side"},
            },
            {"submit": "Log in", "values": {"username": "dan", "password": "login-side"}},
        ],
    )
    assert res.errors == [] and res.unmatched == []
    assert res.calls == [["POST", "/api/auth/login", {"username": "dan", "password": "login-side"}]]
    assert res.session == [["login", "tok-d", DAN]]


def test_lives_in_its_own_feature_folder() -> None:
    assert "login" in [p["name"] for p in run_page("page_login", None, me=None).pages]
