"""The app: dispatches requests to discovered routes inside one transaction each, serves the
browser shell and the feature pages, and is a WSGI app for a real server."""

import importlib
import json
import sqlite3
import threading
import traceback
from collections.abc import Iterable
from http import HTTPStatus
from pathlib import Path
from urllib.parse import parse_qsl
from wsgiref.types import StartResponse, WSGIEnvironment

from chatbook.core.clock import Clock, SystemClock
from chatbook.core.http import JSON_TYPE, HTTPError, Request, Response
from chatbook.core.registry import (
    Route,
    discover,
    discover_ui,
    ensure_unique,
    match,
    specificity,
)
from chatbook.core.store import Db, connect
from chatbook.core.users import end_session, touch, user_for_token, user_json

MAX_BODY = 65536
STATIC_DIR = Path(__file__).resolve().parent / "core" / "static"
STATIC_FILES = {
    "cb.js": "text/javascript; charset=utf-8",
    "cb.css": "text/css; charset=utf-8",
    "start.js": "text/javascript; charset=utf-8",
}
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
)
STATIC_HEADERS: tuple[tuple[str, str], ...] = (
    ("Content-Security-Policy", CSP),
    ("X-Content-Type-Options", "nosniff"),
    ("Referrer-Policy", "no-referrer"),
    ("Cache-Control", "no-store"),
)
FEATURE_SCRIPTS = "<!--FEATURE_SCRIPTS-->"


# ---------------------------------------------------------------------------------------
# Frame routes (feature "core")


def _health(request: Request) -> Response:
    return Response(200, {"status": "ok"})


def _get_session(request: Request) -> Response:
    return Response(200, {"user": user_json(request.me)})


def _delete_session(request: Request) -> Response:
    end_session(request.db, request.token)
    return Response(200, {"ok": True})


FRAME_ROUTES = (
    Route("GET", "/api/health", _health, "core", True),
    Route("GET", "/api/session", _get_session, "core", False),
    Route("DELETE", "/api/session", _delete_session, "core", False),
)


# ---------------------------------------------------------------------------------------
# The app


class App:
    def __init__(
        self,
        routes: list[Route] | None = None,
        db: Db | None = None,
        *,
        clock: Clock | None = None,
        ui_features: list[str] | None = None,
        raise_errors: bool = False,
        features_package: str = "chatbook.features",
    ) -> None:
        given = list(routes or [])
        merged = [r for r in FRAME_ROUTES if r not in given] + given
        ensure_unique(merged)
        # Most specific first: /items/new wins over /items/{id} from any feature.
        self.routes: list[Route] = sorted(merged, key=lambda r: specificity(r.pattern))
        self.ui_features: list[str] = sorted(ui_features or [])
        self.db: Db = db if db is not None else connect(":memory:")
        self.clock: Clock = clock if clock is not None else SystemClock()
        self.raise_errors = raise_errors
        self.features_package = features_package
        self._lock = threading.Lock()

    # -- dispatch ------------------------------------------------------------------------

    def handle(
        self,
        method: str,
        path: str,
        body: object = None,
        query: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Response:
        method = method.upper()
        if not path.startswith("/api/"):
            return self._static(method, path)
        allowed: list[str] = []
        for r in self.routes:
            params = match(r.pattern, path)
            if params is None:
                continue
            if r.method != method:
                allowed.append(r.method)
                continue
            lower = {k.lower(): v for k, v in (headers or {}).items()}
            return self._call(r, params, method, path, body, dict(query or {}), lower)
        if allowed:
            return Response(405, {"error": "method not allowed", "allow": sorted(set(allowed))})
        return Response(404, {"error": "not found"})

    def _call(
        self,
        r: Route,
        params: dict[str, str],
        method: str,
        path: str,
        body: object,
        query: dict[str, str],
        headers: dict[str, str],
    ) -> Response:
        token = _bearer(headers.get("authorization"))
        user = user_for_token(self.db, token)
        if user is None and not r.public:
            return Response(401, {"error": "login required"})
        now = self.clock.now_ms()
        self.db._begin()
        try:
            if user is not None:
                touch(self.db, user.id, now)
            request = Request(method, path, params, query, body, headers, user, token, self.db, now)
            result: object = r.handler(request)
            if not isinstance(result, Response):
                raise TypeError("handler must return Response")
        except HTTPError as exc:
            self.db._rollback()
            return Response(exc.status, {"error": exc.message})
        except Exception as exc:
            self.db._rollback()
            if _is_conflict(exc):
                return Response(409, {"error": "conflict"})
            if self.raise_errors:
                raise
            traceback.print_exc()
            return Response(500, {"error": "internal error"})
        except BaseException:
            self.db._rollback()
            raise
        if result.status < 400:
            self.db._commit()
        else:
            self.db._rollback()
        return result

    # -- static files and pages ----------------------------------------------------------

    def _static(self, method: str, path: str) -> Response:
        if method == "GET":
            if path == "/":
                return _static_response(self._index().encode("utf-8"), "text/html; charset=utf-8")
            if path.startswith("/static/") and path[len("/static/") :] in STATIC_FILES:
                name = path[len("/static/") :]
                return _static_response((STATIC_DIR / name).read_bytes(), STATIC_FILES[name])
            if path.startswith("/ui/") and path.endswith(".js"):
                feature = path[len("/ui/") : -len(".js")]
                if feature in self.ui_features:
                    text = self._ui_path(feature).read_text(encoding="utf-8")
                    data = wrap_ui(feature, text).encode("utf-8")
                    return _static_response(data, "text/javascript; charset=utf-8")
        return Response(404, {"error": "not found"})

    def _index(self) -> str:
        template = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        scripts = "\n".join(
            f'<script defer src="/ui/{feature}.js"></script>' for feature in self.ui_features
        )
        return template.replace(FEATURE_SCRIPTS, scripts)

    def _ui_path(self, feature: str) -> Path:
        package = importlib.import_module(self.features_package)
        for folder in package.__path__:
            candidate = Path(folder) / feature / "ui.js"
            if candidate.is_file():
                return candidate
        raise FileNotFoundError(f"{feature}/ui.js not found in {self.features_package}")

    # -- WSGI ----------------------------------------------------------------------------

    def wsgi(self, environ: WSGIEnvironment, start_response: StartResponse) -> Iterable[bytes]:
        method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        # The body is read and parsed before taking the lock: a client that stalls in the
        # middle of its request holds only its own thread.
        parsed = _parse(environ)
        if isinstance(parsed, Response):
            status, headers, data = _encode(parsed)
        else:
            # One request at a time: the single sqlite connection and its per-request
            # transaction stay serial even on the threaded server.
            with self._lock:
                resp = self.handle("GET" if method == "HEAD" else method, *parsed)
                status, headers, data = _encode(resp)
        start_response(status, headers)
        return [b""] if method == "HEAD" else [data]


# ---------------------------------------------------------------------------------------
# Helpers


# sqlite reports these for a UNIQUE or PRIMARY KEY clash (a race or a duplicate row): a 409.
# Every other constraint failure (NOT NULL, CHECK, a type) is a bug in the handler.
CONFLICT_ERRORS = ("SQLITE_CONSTRAINT_UNIQUE", "SQLITE_CONSTRAINT_PRIMARYKEY")


def _is_conflict(exc: Exception) -> bool:
    return isinstance(exc, sqlite3.IntegrityError) and exc.sqlite_errorname in CONFLICT_ERRORS


def _parse(
    environ: WSGIEnvironment,
) -> Response | tuple[str, object, dict[str, str], dict[str, str]]:
    """(path, body, query, headers) of a WSGI request, or the 400/413 answer for a bad body."""
    raw_length = str(environ.get("CONTENT_LENGTH") or "").strip() or "0"
    # ASCII digits only: rejects negatives (read(-1) would block) and the non-ASCII
    # digits that str.isdigit() accepts
    if not (raw_length.isascii() and raw_length.isdigit()):
        return Response(400, {"error": "bad Content-Length"})
    length = int(raw_length)
    if length > MAX_BODY:
        return Response(413, {"error": "request body too large"})
    try:
        raw = environ["wsgi.input"].read(length) if length else b""
    except OSError:  # the socket timed out or the client went away
        return Response(400, {"error": "request body incomplete"})
    if len(raw) < length:
        return Response(400, {"error": "request body incomplete"})
    try:
        body = json.loads(raw) if raw else None
    except (ValueError, RecursionError):  # RecursionError: a hostile, deeply nested body
        return Response(400, {"error": "request body is not valid JSON"})
    path = _utf8(str(environ.get("PATH_INFO", "/")))
    query = dict(parse_qsl(_utf8(str(environ.get("QUERY_STRING", "")))))
    headers: dict[str, str] = {}
    for key, value in environ.items():
        if key.startswith("HTTP_"):
            headers[key[5:].lower().replace("_", "-")] = str(value)
    if environ.get("CONTENT_TYPE"):
        headers["content-type"] = str(environ["CONTENT_TYPE"])
    return path, body, query, headers


def _encode(resp: Response) -> tuple[str, list[tuple[str, str]], bytes]:
    try:
        return encode_response(resp)
    except (TypeError, ValueError):  # a body json.dumps cannot encode
        traceback.print_exc()
        return encode_response(Response(500, {"error": "internal error"}))


def wrap_ui(feature: str, text: str) -> str:
    """A feature's ui.js as served (and as tools/uirun.js evaluates it): its own scope."""
    return f"(() => {{\n'use strict';\n{text}\n}})();\n//# sourceURL=/ui/{feature}.js\n"


def _static_response(data: bytes, content_type: str) -> Response:
    return Response(200, data, content_type, STATIC_HEADERS)


def _bearer(value: str | None) -> str | None:
    """The token of an 'Authorization: Bearer <token>' header, else None."""
    if not value:
        return None
    scheme, _, token = value.strip().partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token:
        return None
    return token


def encode_response(resp: Response) -> tuple[str, list[tuple[str, str]], bytes]:
    """The status line, headers and body bytes of `resp` as the WSGI app sends them.
    A body json.dumps cannot encode raises TypeError or ValueError."""
    if isinstance(resp.body, bytes):
        data = resp.body
        headers = [("Content-Type", resp.content_type)]
    else:
        data = json.dumps(resp.body).encode("utf-8")
        headers = [
            ("Content-Type", resp.content_type or JSON_TYPE),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
        ]
    extra = {name.lower() for name, _ in resp.headers}
    headers = [(n, v) for n, v in headers if n.lower() not in extra] + list(resp.headers)
    headers.append(("Content-Length", str(len(data))))
    try:
        reason = HTTPStatus(resp.status).phrase
    except ValueError:
        reason = "Unknown"
    return f"{resp.status} {reason}", headers, data


def _utf8(value: str) -> str:
    """PEP 3333 hands over the path and query as latin-1-decoded bytes; URLs are UTF-8."""
    try:
        return value.encode("latin-1").decode("utf-8", "replace")
    except UnicodeEncodeError:
        return value  # already decoded by a non-PEP 3333 caller


def create_app(
    db_path: str = ":memory:",
    *,
    clock: Clock | None = None,
    hash_iterations: int = 200_000,
    raise_errors: bool = False,
) -> App:
    """The app with every discovered feature and a database at db_path."""
    return App(
        discover(),
        connect(db_path, hash_iterations=hash_iterations),
        clock=clock,
        ui_features=discover_ui(),
        raise_errors=raise_errors,
    )
