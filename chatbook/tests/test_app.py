"""The App (app.py): dispatch, auth, transactions, frame routes, static files, WSGI, threading."""

import http.client
import io
import json
import re
import socket
import sqlite3
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from wsgiref.simple_server import WSGIRequestHandler, make_server

import pytest

import chatbook
from chatbook import App, create_app
from chatbook.__main__ import RequestHandler, ThreadingWSGIServer
from chatbook.core.clock import FakeClock, SystemClock
from chatbook.core.http import JSON_TYPE, HTTPError, Request, Response
from chatbook.core.registry import RegistryError, Route, discover_ui, specificity
from chatbook.core.users import new_session
from chatbook.core.validate import body_str
from chatbook.testing import Client

SRC = Path(__file__).resolve().parents[1] / "src" / "chatbook"
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
)
NOT_FOUND = {"error": "not found"}
Handler = Callable[[Request], Any]


def new_app(*, raise_errors: bool = False) -> App:
    return create_app(":memory:", clock=FakeClock(), hash_iterations=1, raise_errors=raise_errors)


def add_route(
    app: App, method: str, pattern: str, handler: Handler, *, public: bool = True
) -> None:
    extra = Route(method=method, pattern=pattern, handler=handler, feature="t", public=public)
    app.routes = sorted([*app.routes, extra], key=lambda r: specificity(r.pattern))


def insert_post(request: Request) -> None:
    request.db.run(
        "INSERT INTO posts (author_id, body, created_at) VALUES (?, ?, ?)", 1, "x", request.now
    )


def posts(app: App) -> int:
    return int(app.db.value("SELECT COUNT(*) FROM posts"))


def echo(request: Request) -> Response:
    return Response(
        200,
        {
            "method": request.method,
            "path": request.path,
            "params": request.params,
            "query": request.query,
            "body": request.body,
            "headers": request.headers,
            "user": None if request.user is None else request.user.id,
            "token": request.token,
            "now": request.now,
        },
    )


def wsgi(
    app: App,
    method: str,
    path: str,
    *,
    body: bytes = b"",
    length: str | None = None,
    query: str = "",
    extra: dict[str, str] | None = None,
) -> tuple[str, dict[str, str], bytes]:
    environ: dict[str, Any] = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "CONTENT_LENGTH": str(len(body)) if length is None else length,
        "SERVER_NAME": "127.0.0.1",
        "SERVER_PORT": "8000",
        "SERVER_PROTOCOL": "HTTP/1.1",
        "wsgi.url_scheme": "http",
        "wsgi.input": io.BytesIO(body),
        "wsgi.errors": io.StringIO(),
        **(extra or {}),
    }
    seen: list[tuple[str, list[tuple[str, str]]]] = []

    def start_response(
        status: str, headers: list[tuple[str, str]], exc_info: object = None
    ) -> Callable[[bytes], object]:
        seen.append((status, headers))
        return lambda data: None

    data = b"".join(app.wsgi(environ, start_response))
    status, headers = seen[0]
    return status, {name.lower(): value for name, value in headers}, data


# --- frame routes, dispatch and auth ----------------------------------------------------


def test_package_exports_and_create_app_defaults() -> None:
    assert chatbook.__all__ == ["App", "create_app"]
    app = create_app()
    assert isinstance(app, App)
    assert isinstance(app.clock, SystemClock)
    assert app.raise_errors is False
    assert app.db.hash_iterations == 200_000


def test_frame_routes_take_part_in_ensure_unique() -> None:
    clash = Route(method="GET", pattern="/api/health", handler=echo, feature="x", public=True)
    with pytest.raises(RegistryError):
        App(routes=[clash])
    frame = [(r.method, r.pattern, r.public, r.feature) for r in new_app().routes]
    assert ("GET", "/api/health", True, "core") in frame


def test_health_is_public() -> None:
    resp = new_app().handle("GET", "/api/health")
    assert (resp.status, resp.body) == (200, {"status": "ok"})


def test_session_get_and_delete() -> None:
    c = Client()
    alice = c.user("alice")
    second = new_session(c.db, alice.id, c.now)
    r = c.get("/api/session", user=alice)
    assert (r.status, r.json) == (200, {"user": alice.json})
    r = c.delete("/api/session", user=alice)
    assert (r.status, r.json) == (200, {"ok": True})
    assert c.get("/api/session", user=alice).status == 401
    assert c.get("/api/session", token=second).status == 200


def test_login_required_by_default() -> None:
    c = Client()
    alice = c.user("alice")
    calls: list[int | None] = []

    def private(request: Request) -> Response:
        calls.append(None if request.user is None else request.user.id)
        return Response(200, {"ok": True})

    add_route(c.app, "GET", "/api/t/private", private, public=False)
    for token in [None, "not-a-token"]:
        r = c.get("/api/t/private", token=token)
        assert (r.status, r.json) == (401, {"error": "login required"})
    assert calls == []
    assert c.get("/api/t/private", user=alice).json == {"ok": True}
    assert calls == [alice.id]
    assert c.get("/api/session").status == 401


def test_public_route_runs_anonymous_and_me_raises_401() -> None:
    app = new_app()

    def who(request: Request) -> Response:
        return Response(200, {"id": request.me.id})

    add_route(app, "GET", "/api/t/echo", echo)
    add_route(app, "GET", "/api/t/who", who)
    body = app.handle("GET", "/api/t/echo").body
    assert isinstance(body, dict) and (body["user"], body["token"]) == (None, None)
    resp = app.handle("GET", "/api/t/who")
    assert (resp.status, resp.body) == (401, {"error": "login required"})
    # an unknown token is anonymous; header names reach the handler lower-cased
    headers = {"Authorization": "Bearer not-a-token", "X-Mixed-Case": "v"}
    body = app.handle("GET", "/api/t/echo", headers=headers).body
    assert isinstance(body, dict) and body["user"] is None
    assert body["headers"]["x-mixed-case"] == "v"
    assert app.handle("GET", "/api/t/who", headers=headers).status == 401


def test_request_carries_user_token_and_clock_time() -> None:
    c = Client()
    alice = c.user("alice")
    add_route(c.app, "GET", "/api/t/echo/{name}", echo)
    c.tick(1234)
    r = c.get("/api/t/echo/abc", user=alice)
    assert r.json["user"] == alice.id
    assert r.json["token"] == alice.token
    assert r.json["now"] == c.now
    assert r.json["params"] == {"name": "abc"}
    assert r.json["method"] == "GET"
    assert r.json["path"] == "/api/t/echo/abc"


def test_logged_in_requests_touch_last_seen() -> None:
    c = Client()
    alice = c.user("alice")
    c.tick(5000)
    c.get("/api/session", user=alice)
    assert c.row("SELECT last_seen_at FROM users WHERE id = ?", alice.id) == {"last_seen_at": c.now}


def test_unknown_path_is_404_and_wrong_method_is_405() -> None:
    app = new_app()
    for path in ["/api/nowhere", "/api/health/extra", "/api/"]:
        resp = app.handle("GET", path)
        assert (resp.status, resp.body) == (404, NOT_FOUND)
    resp = app.handle("put", "/api/health")
    assert (resp.status, resp.body) == (405, {"error": "method not allowed", "allow": ["GET"]})
    resp = app.handle("POST", "/api/session")
    assert resp.status == 405
    assert resp.body == {"error": "method not allowed", "allow": ["DELETE", "GET"]}


def test_method_is_upper_cased() -> None:
    assert new_app().handle("get", "/api/health").status == 200


# --- transactions and outcomes ----------------------------------------------------------


def test_success_commits() -> None:
    app = new_app()

    def ok(request: Request) -> Response:
        insert_post(request)
        return Response(201, {"ok": True})

    add_route(app, "POST", "/api/t/ok", ok)
    resp = app.handle("POST", "/api/t/ok")
    assert (resp.status, resp.body) == (201, {"ok": True})
    assert posts(app) == 1


def test_error_response_rolls_back() -> None:
    app = new_app()

    def bad(request: Request) -> Response:
        insert_post(request)
        return Response(422, {"error": "unprocessable"})

    add_route(app, "POST", "/api/t/bad", bad)
    resp = app.handle("POST", "/api/t/bad")
    assert (resp.status, resp.body) == (422, {"error": "unprocessable"})
    assert posts(app) == 0


def test_http_error_rolls_back() -> None:
    app = new_app()

    def nope(request: Request) -> Response:
        insert_post(request)
        raise HTTPError(403, "nope")

    add_route(app, "POST", "/api/t/nope", nope)
    resp = app.handle("POST", "/api/t/nope")
    assert (resp.status, resp.body) == (403, {"error": "nope"})
    assert posts(app) == 0


def test_integrity_error_is_409_and_rolls_back() -> None:
    c = Client()  # raise_errors=True: IntegrityError is still an answer, not a crash

    def dup(request: Request) -> Response:
        insert_post(request)
        sql = (
            "INSERT INTO users (username, display_name, password_hash, created_at)"
            " VALUES (?, ?, ?, ?)"
        )
        request.db.run(sql, "dup", "Dup", "x", 0)
        request.db.run(sql, "dup", "Dup", "x", 0)
        return Response(201, {"ok": True})

    add_route(c.app, "POST", "/api/t/dup", dup)
    r = c.post("/api/t/dup")
    assert (r.status, r.json) == (409, {"error": "conflict"})
    assert c.rows("SELECT id FROM posts") == []
    assert c.rows("SELECT id FROM users") == []


def test_primary_key_clash_is_409_and_rolls_back() -> None:
    c = Client()

    def twice(request: Request) -> Response:
        insert_post(request)
        for _ in range(2):
            request.db.run(
                "INSERT INTO friendships (user_id, friend_id, created_at) VALUES (?, ?, ?)", 1, 2, 0
            )
        return Response(201, {"ok": True})

    add_route(c.app, "POST", "/api/t/twice", twice)
    r = c.post("/api/t/twice")
    assert (r.status, r.json) == (409, {"error": "conflict"})
    assert c.rows("SELECT id FROM posts") == []
    assert c.rows("SELECT user_id FROM friendships") == []


# A handler bug, not a conflict: these constraint failures must not look like a 409.
BROKEN_INSERTS = {
    "NOT NULL": ("INSERT INTO comments (post_id, author_id, body) VALUES (?, ?, ?)", 1, 1, "x"),
    "CHECK": (
        "INSERT INTO conversations (kind, created_by, created_at) VALUES (?, ?, ?)",
        "x",
        1,
        0,
    ),
}


@pytest.mark.parametrize("kind", sorted(BROKEN_INSERTS))
def test_other_constraint_failures_are_unexpected_errors(
    kind: str, capsys: pytest.CaptureFixture[str]
) -> None:
    sql, *args = BROKEN_INSERTS[kind]

    def broken(request: Request) -> Response:
        insert_post(request)
        request.db.run(sql, *args)
        return Response(201, {"ok": True})

    c = Client()  # raise_errors=True: the worker sees the real error and its traceback
    add_route(c.app, "POST", "/api/t/broken", broken)
    with pytest.raises(sqlite3.IntegrityError, match=f"{kind} constraint failed"):
        c.post("/api/t/broken")
    assert c.rows("SELECT id FROM posts") == []
    assert c.get("/api/health").status == 200  # no transaction left open

    app = new_app()  # production: a 500 with the traceback on stderr
    add_route(app, "POST", "/api/t/broken", broken)
    resp = app.handle("POST", "/api/t/broken")
    assert (resp.status, resp.body) == (500, {"error": "internal error"})
    err = capsys.readouterr().err
    assert "Traceback" in err and f"{kind} constraint failed" in err
    assert posts(app) == 0


def test_unexpected_error_is_500_with_traceback_unless_raise_errors(
    capsys: pytest.CaptureFixture[str],
) -> None:
    def crash(request: Request) -> Response:
        insert_post(request)
        raise RuntimeError("kaboom")

    app = new_app()
    add_route(app, "POST", "/api/t/crash", crash)
    resp = app.handle("POST", "/api/t/crash")
    assert (resp.status, resp.body) == (500, {"error": "internal error"})
    assert "kaboom" in capsys.readouterr().err
    assert posts(app) == 0

    strict = new_app(raise_errors=True)
    add_route(strict, "POST", "/api/t/crash", crash)
    with pytest.raises(RuntimeError, match="kaboom"):
        strict.handle("POST", "/api/t/crash")
    assert posts(strict) == 0
    assert strict.handle("GET", "/api/health").status == 200  # no transaction left open


def test_handler_must_return_a_response() -> None:
    def plain(request: Request) -> Any:
        insert_post(request)
        return {"ok": True}

    app = new_app()
    add_route(app, "GET", "/api/t/plain", plain)
    resp = app.handle("GET", "/api/t/plain")
    assert (resp.status, resp.body) == (500, {"error": "internal error"})
    assert posts(app) == 0
    strict = new_app(raise_errors=True)
    add_route(strict, "GET", "/api/t/plain", plain)
    with pytest.raises(TypeError):
        strict.handle("GET", "/api/t/plain")


# --- http types and clocks --------------------------------------------------------------


def test_response_defaults_and_http_error_fields() -> None:
    resp = Response(204)
    assert (resp.body, resp.content_type, resp.headers) == (None, JSON_TYPE, ())
    assert JSON_TYPE == "application/json; charset=utf-8"
    err = HTTPError(418, "teapot")
    assert (err.status, err.message) == (418, "teapot")


def test_clocks() -> None:
    clock = FakeClock()
    assert clock.now_ms() == 1_700_000_000_000
    clock.advance(250)
    assert clock.now_ms() == 1_700_000_000_250
    assert FakeClock(5).now_ms() == 5
    assert abs(SystemClock().now_ms() - int(time.time() * 1000)) < 5000


# --- WSGI -------------------------------------------------------------------------------


def test_wsgi_json_headers() -> None:
    status, headers, data = wsgi(new_app(), "GET", "/api/health")
    assert status == "200 OK"
    assert json.loads(data) == {"status": "ok"}
    assert headers["content-type"] == JSON_TYPE
    assert headers["cache-control"] == "no-store"
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["content-length"] == str(len(data))


def test_wsgi_head_is_get_without_body() -> None:
    status, _, data = wsgi(new_app(), "HEAD", "/api/health")
    assert (status, data) == ("200 OK", b"")


def test_wsgi_body_too_large_is_413() -> None:
    status, _, data = wsgi(new_app(), "POST", "/api/health", body=b"x" * 65537)
    assert status.startswith("413 ")
    assert json.loads(data) == {"error": "request body too large"}
    limit = b'"' + b"a" * 65534 + b'"'  # exactly 65536 bytes is allowed
    assert wsgi(new_app(), "POST", "/api/health", body=limit)[0].startswith("405 ")


@pytest.mark.parametrize("length", ["abc", "-1", "\u00b2", "1.5"])
def test_wsgi_bad_content_length_is_400(length: str) -> None:
    status, _, data = wsgi(new_app(), "POST", "/api/health", length=length)
    assert status.startswith("400 ")
    assert json.loads(data) == {"error": "bad Content-Length"}


def test_wsgi_content_length_whitespace_is_fine() -> None:
    assert wsgi(new_app(), "GET", "/api/health", length="0 ")[0] == "200 OK"


def test_wsgi_invalid_json_is_400() -> None:
    status, _, data = wsgi(new_app(), "POST", "/api/health", body=b"{")
    assert status.startswith("400 ")
    assert json.loads(data) == {"error": "request body is not valid JSON"}


@pytest.mark.parametrize(
    "body", [b"[" * 60000, b"[" * 30000 + b"]" * 30000], ids=["open", "balanced"]
)
def test_wsgi_deeply_nested_json_is_400(body: bytes) -> None:
    # json.loads raises RecursionError (not ValueError) for these; still a JSON 400 answer
    status, headers, data = wsgi(new_app(), "POST", "/api/health", body=body)
    assert status.startswith("400 ")
    assert headers["content-type"] == JSON_TYPE
    assert json.loads(data) == {"error": "request body is not valid JSON"}


def test_wsgi_short_body_is_400() -> None:
    # fewer bytes than Content-Length: the client went away before sending them all
    status, _, data = wsgi(new_app(), "POST", "/api/health", body=b"{}", length="10")
    assert status.startswith("400 ")
    assert json.loads(data) == {"error": "request body incomplete"}


def test_wsgi_lone_surrogate_in_a_string_is_400() -> None:
    app = new_app()

    def named(request: Request) -> Response:
        return Response(200, {"name": body_str(request, "name")})

    add_route(app, "POST", "/api/t/named", named)
    status, _, data = wsgi(app, "POST", "/api/t/named", body=b'{"name": "a\\ud800"}')
    assert (status, json.loads(data)) == ("400 Bad Request", {"error": "name must be a string"})
    status, _, data = wsgi(app, "POST", "/api/t/named", body=b'{"name": "a\\u00e9"}')
    assert (status, json.loads(data)) == ("200 OK", {"name": "aé"})


def test_wsgi_passes_body_query_path_and_headers() -> None:
    app = new_app()
    add_route(app, "POST", "/api/t/echo/{name}", echo)
    status, _, data = wsgi(
        app,
        "POST",
        "/api/t/echo/caf\u00c3\u00a9",  # PEP 3333: the UTF-8 bytes arrive decoded as latin-1
        body=b'{"a": [1, 2]}',
        query="q=caf%C3%A9&n=1&n=2&blank=&w=caf\u00c3\u00a9",
        extra={"HTTP_X_TRACE_ID": "t-1", "CONTENT_TYPE": "application/json"},
    )
    assert status == "200 OK"
    got = json.loads(data)
    assert got["params"] == {"name": "caf\u00e9"}
    assert got["body"] == {"a": [1, 2]}
    assert got["query"] == {"q": "caf\u00e9", "n": "2", "w": "caf\u00e9"}
    assert got["headers"]["x-trace-id"] == "t-1"
    assert got["headers"]["content-type"] == "application/json"


def test_wsgi_bearer_token_logs_in() -> None:
    c = Client()
    alice = c.user("alice")
    auth = {"HTTP_AUTHORIZATION": "Bearer " + alice.token}
    status, _, data = wsgi(c.app, "GET", "/api/session", extra=auth)
    assert (status, json.loads(data)) == ("200 OK", {"user": alice.json})
    assert wsgi(c.app, "GET", "/api/session")[0].startswith("401 ")


# --- static files and pages -------------------------------------------------------------


def _static_headers(headers: dict[str, str], content_type: str) -> None:
    assert headers["content-type"] == content_type
    assert headers["content-security-policy"] == CSP
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["referrer-policy"] == "no-referrer"
    assert headers["cache-control"] == "no-store"


def test_index_page_lists_every_ui_feature_in_order() -> None:
    app = new_app()
    assert app.ui_features == discover_ui()
    status, headers, data = wsgi(app, "GET", "/")
    assert status == "200 OK"
    _static_headers(headers, "text/html; charset=utf-8")
    html = data.decode("utf-8")
    assert "<!--FEATURE_SCRIPTS-->" not in html
    assert "<title>ChatBook</title>" in html
    for part in ['id="cb-header"', 'id="cb-main"', 'id="cb-toasts"', "/static/cb.css"]:
        assert part in html
    tags = ['<script defer src="/static/cb.js"></script>']
    tags += [f'<script defer src="/ui/{f}.js"></script>' for f in app.ui_features]
    tags += ['<script defer src="/static/start.js"></script>']
    positions = [html.find(tag) for tag in tags]
    assert -1 not in positions
    assert positions == sorted(positions)
    # no inline script or style (CSP)
    assert len(re.findall(r"<script\b", html)) == len(re.findall(r"<script\b[^>]*\bsrc=", html))
    assert "<style" not in html
    assert wsgi(app, "HEAD", "/")[2] == b""


@pytest.mark.parametrize(
    ("name", "content_type"),
    [
        ("cb.js", "text/javascript; charset=utf-8"),
        ("start.js", "text/javascript; charset=utf-8"),
        ("cb.css", "text/css; charset=utf-8"),
    ],
)
def test_static_files(name: str, content_type: str) -> None:
    status, headers, data = wsgi(new_app(), "GET", "/static/" + name)
    assert status == "200 OK"
    _static_headers(headers, content_type)
    expected = (SRC / "core" / "static" / name).read_bytes()
    assert data.replace(b"\r\n", b"\n") == expected.replace(b"\r\n", b"\n")


def test_ui_files_are_served_wrapped_in_their_own_strict_scope() -> None:
    app = new_app()
    assert len(app.ui_features) >= 1
    for feature in app.ui_features:
        status, headers, data = wsgi(app, "GET", f"/ui/{feature}.js")
        assert status == "200 OK"
        _static_headers(headers, "text/javascript; charset=utf-8")
        text = (SRC / "features" / feature / "ui.js").read_text(encoding="utf-8")
        wrapped = f"(() => {{\n'use strict';\n{text}\n}})();\n//# sourceURL=/ui/{feature}.js\n"
        assert data.decode("utf-8") == wrapped


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/nope"),
        ("GET", "/static/evil.js"),
        ("GET", "/static/../app.py"),
        ("GET", "/static/"),
        ("GET", "/ui/accounts.js"),
        ("GET", "/ui/nope.js"),
        ("GET", "/ui/../app.js"),
        ("GET", "/api"),
        ("POST", "/"),
        ("POST", "/static/cb.js"),
        ("DELETE", "/ui/page_login.js"),
    ],
)
def test_unknown_static_is_404(method: str, path: str) -> None:
    resp = new_app().handle(method, path)
    assert (resp.status, resp.body) == (404, NOT_FOUND)


# --- threads ----------------------------------------------------------------------------


def _slow_app() -> tuple[App, list[int]]:
    app = new_app()
    guard = threading.Lock()
    state = [0, 0]  # active, peak

    def slow(request: Request) -> Response:
        with guard:
            state[0] += 1
            state[1] = max(state[1], state[0])
        time.sleep(0.15)
        with guard:
            state[0] -= 1
        return Response(200, {"ok": True})

    add_route(app, "GET", "/api/t/slow", slow)
    return app, state


def test_wsgi_runs_one_request_at_a_time() -> None:
    app, state = _slow_app()
    statuses: list[str] = []
    threads = [
        threading.Thread(target=lambda: statuses.append(wsgi(app, "GET", "/api/t/slow")[0]))
        for _ in range(2)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    assert statuses == ["200 OK", "200 OK"]
    assert state[1] == 1


@contextmanager
def serve(app: App, handler: type[WSGIRequestHandler] = RequestHandler) -> Iterator[int]:
    """The app on the threaded server (as `python -m chatbook` runs it); yields the port."""
    server = make_server(
        "127.0.0.1", 0, app.wsgi, server_class=ThreadingWSGIServer, handler_class=handler
    )
    assert server.daemon_threads
    runner = threading.Thread(target=server.serve_forever, daemon=True)
    runner.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()


def http_get(port: int, path: str, results: list[int]) -> None:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request("GET", path)
        results.append(conn.getresponse().status)
    finally:
        conn.close()


def read_until_closed(sock: socket.socket) -> bytes:
    sock.settimeout(5)
    chunks: list[bytes] = []
    while chunk := sock.recv(4096):
        chunks.append(chunk)
    return b"".join(chunks)


STALLED_POST = b"POST /api/health HTTP/1.1\r\nHost: x\r\nContent-Length: 10\r\n\r\n{"


def test_threaded_server_is_not_stalled_by_an_idle_socket() -> None:
    app, state = _slow_app()
    results: list[int] = []
    with serve(app) as port:
        idle = socket.create_connection(("127.0.0.1", port))  # like a browser preconnect
        try:
            http_get(port, "/api/health", results)
            threads = [
                threading.Thread(target=http_get, args=(port, "/api/t/slow", results))
                for _ in range(2)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join(10)
        finally:
            idle.close()
    assert results == [200, 200, 200]
    assert state[1] == 1


def test_a_client_stalled_mid_body_does_not_block_others() -> None:
    # headers plus 1 of the 10 announced body bytes, then nothing: the body is read outside
    # the request lock, so only this client's thread waits
    results: list[int] = []
    with serve(new_app()) as port:
        stalled = socket.create_connection(("127.0.0.1", port))
        try:
            stalled.sendall(STALLED_POST)
            time.sleep(0.2)  # let the server thread start waiting for the rest of the body
            started = time.monotonic()
            http_get(port, "/api/health", results)
            assert time.monotonic() - started < 3
        finally:
            stalled.close()
    assert results == [200]


class QuickHandler(RequestHandler):
    timeout = 0.5


def test_silent_and_stalled_clients_are_dropped_after_the_timeout(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert RequestHandler.timeout == 30
    with serve(new_app(), QuickHandler) as port:
        silent = socket.create_connection(("127.0.0.1", port))
        stalled = socket.create_connection(("127.0.0.1", port))
        try:
            stalled.sendall(STALLED_POST)
            assert read_until_closed(silent) == b""  # closed by the server, no answer
            answer = read_until_closed(stalled)
        finally:
            silent.close()
            stalled.close()
    head, _, body = answer.partition(b"\r\n\r\n")
    assert head.split(b"\r\n")[0].split(b" ")[1] == b"400", answer
    assert json.loads(body) == {"error": "request body incomplete"}
    assert "Traceback" not in capsys.readouterr().err
