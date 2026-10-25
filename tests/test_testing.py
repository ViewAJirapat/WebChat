"""The hidden-test kit (testing.py): every Client helper, the UI fixtures and run_page."""

import json
from pathlib import Path
from typing import Any

import pytest

from chatbook.core.chat import conversation_json
from chatbook.core.clock import FakeClock
from chatbook.core.http import Request, Response
from chatbook.core.registry import Route, specificity
from chatbook.core.users import check_password
from chatbook.testing import (
    ALICE,
    BOB,
    CAROL,
    DAN,
    ERIN,
    FRANK,
    Account,
    Client,
    UiResult,
    fake_conversation,
    fake_message,
    fake_post,
    fake_request,
    run_page,
)

SAMPLE = str(Path(__file__).resolve().parent / "fixtures" / "sample_page.js")
START = 1_700_000_000_000
DATA = {
    "owner": ERIN,
    "note": "short",
    "items": [{"id": 4, "name": "Pear", "likes": 2}],
}


def install(c: Client, handler: Any, pattern: str = "/api/t/echo/{name}") -> None:
    routes = [
        Route(method=m, pattern=pattern, handler=handler, feature="t", public=True)
        for m in ["GET", "POST", "PUT", "DELETE"]
    ]
    c.app.routes = sorted([*c.app.routes, *routes], key=lambda r: specificity(r.pattern))


def echo(request: Request) -> Response:
    return Response(
        200,
        {
            "method": request.method,
            "params": request.params,
            "query": request.query,
            "body": request.body,
            "headers": request.headers,
            "user": None if request.user is None else request.user.id,
        },
    )


# --- constants and fixtures -------------------------------------------------------------


def test_people_constants() -> None:
    assert [ALICE, BOB, CAROL, DAN, ERIN, FRANK] == [
        {"id": 1, "username": "alice", "display_name": "Alice Adams"},
        {"id": 2, "username": "bob", "display_name": "Bob Brown"},
        {"id": 3, "username": "carol", "display_name": "Carol Chen"},
        {"id": 4, "username": "dan", "display_name": "Dan Diaz"},
        {"id": 5, "username": "erin", "display_name": "Erin Evans"},
        {"id": 6, "username": "frank", "display_name": "Frank Fox"},
    ]


def test_ui_fixtures_have_the_api_shapes() -> None:
    m = fake_message(10, ERIN, "hi")
    assert m == {
        "id": 10,
        "conversation_id": 3,
        "sender": ERIN,
        "body": "hi",
        "created_at": START,
    }
    assert fake_message(11, ALICE, "yo", conversation_id=4, created_at=5)["conversation_id"] == 4
    assert fake_conversation(3, "group", "Ski", [ALICE, ERIN]) == {
        "id": 3,
        "kind": "group",
        "title": "Ski",
        "members": [ALICE, ERIN],
        "last_message": None,
        "unread": 0,
        "updated_at": START,
    }
    conv = fake_conversation(
        4, "direct", "Erin", [ALICE, ERIN], last_message=m, unread=2, updated_at=7
    )
    assert (conv["last_message"], conv["unread"], conv["updated_at"]) == (m, 2, 7)
    assert fake_request(7, ERIN, ALICE) == {
        "id": 7,
        "from": ERIN,
        "to": ALICE,
        "created_at": START,
    }
    post = fake_post(8, FRANK, "news", like_count=2, comment_count=1, liked=True)
    assert set(post) == {
        "id",
        "author",
        "body",
        "created_at",
        "like_count",
        "comment_count",
        "liked",
    }
    assert (post["id"], post["author"], post["body"]) == (8, FRANK, "news")
    assert (post["like_count"], post["comment_count"], post["liked"]) == (2, 1, True)
    assert isinstance(post["created_at"], int)
    assert fake_post(9, FRANK, "x")["liked"] is False


# --- Client: app, clock, users, requests ------------------------------------------------


def test_client_app_db_and_clock() -> None:
    c = Client()
    assert c.db is c.app.db
    assert c.clock is c.app.clock
    assert isinstance(c.clock, FakeClock)
    assert c.app.raise_errors is True
    assert c.db.hash_iterations == 1
    assert c.now == START
    c.tick()
    assert c.now == START + 1000
    c.tick(5)
    assert c.now == START + 1005
    assert Client.__test__ is False


def test_client_user_creates_account_with_session() -> None:
    c = Client()
    zoe = c.user("zoe")
    assert isinstance(zoe, Account)
    assert (zoe.id, zoe.username, zoe.display_name) == (1, "zoe", "Zoe")
    assert zoe.json == {"id": 1, "username": "zoe", "display_name": "Zoe"}
    yan = c.user("yan", "Yan Yu", password="other-pass")
    assert yan.json == {"id": 2, "username": "yan", "display_name": "Yan Yu"}
    assert check_password(c.db, "zoe", "password1") is not None
    assert check_password(c.db, "yan", "other-pass") is not None
    assert c.get("/api/session", user=zoe).json == {"user": zoe.json}
    assert c.get("/api/session", token=yan.token).json == {"user": yan.json}
    assert c.get("/api/session", token="bogus").status == 401
    assert c.get("/api/session").status == 401


def test_client_request_parses_path_query_and_round_trips_json() -> None:
    c = Client()
    zoe = c.user("zoe")
    install(c, echo)
    r = c.get("/api/t/echo/caf%C3%A9?q=a%20b&n=1&n=2&blank=", user=zoe)
    assert r.status == 200
    assert r.json["method"] == "GET"
    assert r.json["params"] == {"name": "caf\u00e9"}
    assert r.json["query"] == {"q": "a b", "n": "2"}
    assert r.json["user"] == zoe.id
    assert r.json["headers"]["authorization"] == "Bearer " + zoe.token
    assert json.loads(r.text) == r.json
    assert c.post("/api/t/echo/x", {1: "one", "k": [1, 2]}).json["body"] == {
        "1": "one",
        "k": [1, 2],
    }
    assert c.put("/api/t/echo/x", {"a": None}).json["method"] == "PUT"
    assert c.delete("/api/t/echo/x").json["method"] == "DELETE"
    assert c.post("/api/t/echo/x").json["body"] is None
    r = c.request("PUT", "/api/t/echo/x", [1], headers={"x-extra": "yes"})
    assert (r.json["method"], r.json["body"], r.json["headers"]["x-extra"]) == ("PUT", [1], "yes")
    assert r.json["user"] is None


def test_client_response_must_be_json_and_errors_propagate() -> None:
    c = Client()

    def not_json(request: Request) -> Response:
        return Response(200, {"bad": {1, 2}})

    def crash(request: Request) -> Response:
        raise RuntimeError("kaboom")

    install(c, not_json, "/api/t/notjson")
    install(c, crash, "/api/t/crash")
    with pytest.raises((TypeError, ValueError, AssertionError)):
        c.get("/api/t/notjson")
    with pytest.raises(RuntimeError, match="kaboom"):
        c.get("/api/t/crash")


def test_client_non_json_response() -> None:
    r = Client().get("/")
    assert r.status == 200
    assert r.json is None
    assert "<title>ChatBook</title>" in r.text
    assert isinstance(r.headers, dict)


# --- Client: seeding and inspection -----------------------------------------------------


def test_friend_helpers() -> None:
    c = Client()
    a, b = c.user("ann"), c.user("ben")
    assert not c.are_friends(a, b)
    c.befriend(a, b)
    assert c.are_friends(a, b) and c.are_friends(b, a)
    c.unfriend(b, a)
    assert not c.are_friends(a, b)
    c.tick()
    rid = c.friend_request(a, b)
    assert c.row("SELECT * FROM friend_requests WHERE id = ?", rid) == {
        "id": rid,
        "from_id": a.id,
        "to_id": b.id,
        "created_at": c.now,
    }


def test_conversation_helpers() -> None:
    c = Client()
    a, b, d = c.user("ann"), c.user("ben"), c.user("dee")
    cid = c.dm(a, b)
    assert c.dm(b, a) == cid
    assert c.row("SELECT kind, title FROM conversations WHERE id = ?", cid) == {
        "kind": "direct",
        "title": "",
    }
    g = c.group(a, [b, d], "Trip")
    member_rows = c.rows(
        "SELECT user_id FROM members WHERE conversation_id = ? ORDER BY user_id", g
    )
    assert [r["user_id"] for r in member_rows] == [a.id, b.id, d.id]
    assert c.row("SELECT kind, title FROM conversations WHERE id = ?", g) == {
        "kind": "group",
        "title": "Trip",
    }
    default = c.group(b, [a])
    assert c.row("SELECT title FROM conversations WHERE id = ?", default) == {"title": "Group"}
    c.leave(d, g)
    assert (
        c.rows("SELECT user_id FROM members WHERE conversation_id = ? AND user_id = ?", g, d.id)
        == []
    )


def test_message_helpers() -> None:
    c = Client()
    a, b = c.user("ann"), c.user("ben")
    g = c.group(a, [b], "G")
    c.tick()
    mid = c.send(a, g, "hi")
    assert c.message(mid) == {
        "id": mid,
        "conversation_id": g,
        "sender": a.json,
        "body": "hi",
        "created_at": c.now,
    }
    assert c.message(c.send(a, g))["body"] == "hello"
    assert c.unread(b, g) == 2
    assert c.unread(a, g) == 0
    c.read(b, g)
    assert c.unread(b, g) == 0
    assert c.conversation(g, b) == conversation_json(c.db, g, b.id)
    assert c.conversation(g, b)["last_message"] == c.message(mid + 1)


def test_post_helpers() -> None:
    c = Client()
    a, b = c.user("ann"), c.user("ben")
    pid = c.make_post(a, "first")
    assert c.row("SELECT author_id, body, created_at FROM posts WHERE id = ?", pid) == {
        "author_id": a.id,
        "body": "first",
        "created_at": c.now,
    }
    assert c.row("SELECT body FROM posts WHERE id = ?", c.make_post(b)) == {"body": "post"}
    c.like(b, pid)
    assert c.rows("SELECT post_id, user_id FROM likes") == [{"post_id": pid, "user_id": b.id}]
    kid = c.comment(b, pid, "great")
    assert c.row("SELECT post_id, author_id, body FROM comments WHERE id = ?", kid) == {
        "post_id": pid,
        "author_id": b.id,
        "body": "great",
    }
    assert c.row("SELECT body FROM comments WHERE id = ?", c.comment(a, pid)) == {"body": "nice"}


def test_touch_row_and_rows() -> None:
    c = Client()
    a = c.user("ann")
    c.tick(3000)
    c.touch(a)
    assert c.row("SELECT last_seen_at FROM users WHERE id = ?", a.id) == {"last_seen_at": c.now}
    assert c.row("SELECT * FROM users WHERE id = ?", 99) is None
    assert c.rows("SELECT id FROM users WHERE id > ?", 5) == []


# --- run_page and UiResult --------------------------------------------------------------


def sample(**kw: Any) -> UiResult:
    api = {"GET /api/sample": DATA, "GET /api/sample/count": {"n": 0}} | kw.pop("api", {})
    return run_page("sample", kw.pop("page", "sample"), api=api, files=[SAMPLE], **kw)


def test_run_page_reports_the_page() -> None:
    res = sample()
    assert res.errors == [] and res.unmatched == []
    assert (res.page, res.title) == ("sample", "Sample")
    assert ["GET", "/api/sample", None] in res.calls
    assert res.count("GET", "/api/sample") == 1
    assert res.count("GET", "/api/sample?id=1") == 0
    assert res.labels == [b["label"] for b in res.buttons]
    assert {"Like", "Reload", "Locked", "Add", "Find"} <= set(res.labels)
    assert "Pear: 2 likes" in res.text
    assert res.nav == [] and res.toasts == [] and res.session == []
    by_name = {p["name"]: p for p in res.pages}
    assert {k: by_name["sample"][k] for k in ["title", "nav", "order", "public"]} == {
        "title": "Sample",
        "nav": "Sample",
        "order": 60,
        "public": False,
    }
    assert {k: by_name["sample_open"][k] for k in ["title", "nav", "order", "public"]} == {
        "title": "Open",
        "nav": None,
        "order": 100,
        "public": True,
    }


def test_run_page_params_reach_load() -> None:
    res = sample(params={"id": "12"})
    assert res.errors == []
    assert res.count("GET", "/api/sample?id=12") == 1
    assert "Sample 12" in res.text


def test_api_answers_are_consumed_in_order_and_the_last_repeats() -> None:
    plum = DATA | {"items": [{"id": 5, "name": "Plum", "likes": 0}]}
    res = sample(api={"GET /api/sample": [DATA, plum]}, steps=[{"click": "Reload"}] * 2)
    assert res.errors == []
    assert res.count("GET", "/api/sample") == 3
    assert "Plum: 0 likes" in res.text and "Pear" not in res.text


def test_api_key_with_query_wins_over_the_plain_path() -> None:
    quince = DATA | {"items": [{"id": 9, "name": "Quince", "likes": 1}]}
    res = sample(params={"id": "9"}, api={"GET /api/sample?id=9": quince})
    assert res.errors == [] and res.unmatched == []
    assert "Quince: 1 like" in res.text


def test_error_answers_use_their_status() -> None:
    res = sample(
        api={"POST /api/sample/fail": {"$status": 409, "error": "already there"}},
        steps=[{"click": "Fail"}],
    )
    assert res.errors == []
    assert res.toasts == ["already there"]
    assert ["POST", "/api/sample/fail", None] in res.calls


def test_run_page_without_page_loads_files_only() -> None:
    res = run_page("sample", None, me=None, files=[SAMPLE])
    assert res.errors == [] and res.calls == []
    assert {p["name"] for p in res.pages} == {"sample", "sample_open"}


def test_run_page_defaults_to_the_feature_ui_file() -> None:
    res = run_page("page_login", None, me=None)
    assert res.errors == []
    assert [p["name"] for p in res.pages] == ["login"]


def test_a_runner_crash_is_an_assertion_error_with_stderr(tmp_path: Path) -> None:
    missing = str(tmp_path / "missing" / "ui.js")
    with pytest.raises(AssertionError, match="ENOENT"):
        run_page("sample", None, files=[missing])


def test_node_missing_is_an_assertion_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("chatbook.testing.shutil.which", lambda name: None)
    with pytest.raises(AssertionError, match="Node"):
        run_page("sample", None, files=[SAMPLE])
