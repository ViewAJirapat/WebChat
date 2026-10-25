"""The test kit used by every hidden test: an in-process HTTP Client with seeding helpers,
UI fixtures in the API shapes, and run_page() for the headless page runner.

Features never import this module (archlint); it drives features through the app only.
"""

import json
import os
import shutil
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NamedTuple, TypeVar, overload
from urllib.parse import parse_qsl, unquote

from chatbook.app import App, create_app, encode_response
from chatbook.core import chat, social, users
from chatbook.core.clock import FakeClock
from chatbook.core.store import Db

REPO = Path(__file__).resolve().parents[2]
START_MS = 1_700_000_000_000

ALICE = {"id": 1, "username": "alice", "display_name": "Alice Adams"}
BOB = {"id": 2, "username": "bob", "display_name": "Bob Brown"}
CAROL = {"id": 3, "username": "carol", "display_name": "Carol Chen"}
DAN = {"id": 4, "username": "dan", "display_name": "Dan Diaz"}
ERIN = {"id": 5, "username": "erin", "display_name": "Erin Evans"}
FRANK = {"id": 6, "username": "frank", "display_name": "Frank Fox"}

_T = TypeVar("_T")


class Account(NamedTuple):
    id: int
    username: str
    display_name: str
    token: str
    json: dict[str, Any]  # U


class _Headers(dict[str, str]):
    """Response headers: names stored lower-case, lookups ignore case."""

    def __getitem__(self, key: str) -> str:
        return super().__getitem__(key.lower())

    def __contains__(self, key: object) -> bool:
        return super().__contains__(key.lower() if isinstance(key, str) else key)

    @overload
    def get(self, key: str, default: None = None, /) -> str | None: ...
    @overload
    def get(self, key: str, default: str, /) -> str: ...
    @overload
    def get(self, key: str, default: _T, /) -> str | _T: ...
    def get(self, key: str, default: object = None, /) -> object:
        return super().get(key.lower(), default)


@dataclass
class Resp:
    status: int
    json: Any  # parsed JSON, or None for non-JSON responses
    text: str  # raw body text
    headers: dict[str, str]


class Client:
    """An app on a fresh in-memory database with a FakeClock; requests go straight to
    App.handle (no sockets). Seeding helpers write through core helpers and commit at once."""

    __test__ = False  # not a pytest test class

    app: App
    db: Db
    clock: FakeClock

    def __init__(self) -> None:
        self.clock = FakeClock()
        self.app = create_app(":memory:", clock=self.clock, hash_iterations=1, raise_errors=True)
        self.db = self.app.db

    @property
    def now(self) -> int:
        return self.clock.now_ms()

    def tick(self, ms: int = 1000) -> None:
        self.clock.advance(ms)

    @contextmanager
    def _tx(self) -> Iterator[None]:
        self.db._begin()
        try:
            yield
        except BaseException:
            self.db._rollback()
            raise
        self.db._commit()

    def user(
        self, username: str, display_name: str | None = None, password: str = "password1"
    ) -> Account:
        """A new user (display_name defaults to username.capitalize()) with a session."""
        name = display_name if display_name is not None else username.capitalize()
        with self._tx():
            u = users.create_user(self.db, username, password, name, self.now)
            token = users.new_session(self.db, u.id, self.now)
        return Account(u.id, u.username, u.display_name, token, users.user_json(u))

    # -- HTTP ----------------------------------------------------------------------------

    def request(
        self,
        method: str,
        path: str,
        body: object = None,
        *,
        user: Account | None = None,
        token: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> Resp:
        """Send a request as `user` (or with a raw `token`). `path` may carry '?query' and
        %-escapes. Bodies are round-tripped through JSON both ways, as on the wire."""
        raw_path, _, raw_query = path.partition("?")
        query = dict(parse_qsl(raw_query))
        sent_headers = {k.lower(): v for k, v in (headers or {}).items()}
        bearer = token if token is not None else (user.token if user is not None else None)
        if bearer is not None:
            sent_headers["authorization"] = f"Bearer {bearer}"
        sent_body = json.loads(json.dumps(body))
        resp = self.app.handle(method, unquote(raw_path), sent_body, query, sent_headers)
        _, header_list, data = encode_response(resp)  # as the WSGI app would send it
        out_headers = _Headers((name.lower(), value) for name, value in header_list)
        text = data.decode("utf-8")
        parsed = None if isinstance(resp.body, bytes) else json.loads(text)
        return Resp(resp.status, parsed, text, out_headers)

    def get(self, path: str, *, user: Account | None = None, token: str | None = None) -> Resp:
        return self.request("GET", path, user=user, token=token)

    def post(
        self,
        path: str,
        body: object = None,
        *,
        user: Account | None = None,
        token: str | None = None,
    ) -> Resp:
        return self.request("POST", path, body, user=user, token=token)

    def put(
        self,
        path: str,
        body: object = None,
        *,
        user: Account | None = None,
        token: str | None = None,
    ) -> Resp:
        return self.request("PUT", path, body, user=user, token=token)

    def delete(self, path: str, *, user: Account | None = None, token: str | None = None) -> Resp:
        return self.request("DELETE", path, user=user, token=token)

    # -- seeding through core helpers (each commits at once) -----------------------------

    def befriend(self, a: Account, b: Account) -> None:
        with self._tx():
            social.befriend(self.db, a.id, b.id, self.now)

    def unfriend(self, a: Account, b: Account) -> None:
        with self._tx():
            social.unfriend(self.db, a.id, b.id)

    def are_friends(self, a: Account, b: Account) -> bool:
        return social.are_friends(self.db, a.id, b.id)

    def friend_request(self, a: Account, b: Account) -> int:
        """A pending request a -> b; returns its id."""
        with self._tx():
            return self.db.run(
                "INSERT INTO friend_requests (from_id, to_id, created_at) VALUES (?, ?, ?)",
                a.id,
                b.id,
                self.now,
            )

    def dm(self, a: Account, b: Account) -> int:
        """The direct conversation of a and b (found or created); returns its id."""
        with self._tx():
            found = chat.find_direct(self.db, a.id, b.id)
            if found is not None:
                return found
            return chat.create_conversation(self.db, "direct", "", a.id, [b.id], self.now)

    def group(self, owner: Account, members: list[Account], title: str = "Group") -> int:
        with self._tx():
            ids = [m.id for m in members]
            return chat.create_conversation(self.db, "group", title, owner.id, ids, self.now)

    def leave(self, user: Account, cid: int) -> None:
        with self._tx():
            chat.remove_member(self.db, cid, user.id)

    def send(self, sender: Account, cid: int, body: str = "hello") -> int:
        """Post a message; returns its id."""
        with self._tx():
            return int(chat.post_message(self.db, cid, sender.id, body, self.now)["id"])

    def read(self, user: Account, cid: int) -> None:
        with self._tx():
            chat.mark_read(self.db, cid, user.id)

    def unread(self, user: Account, cid: int) -> int:
        return chat.unread_count(self.db, cid, user.id)

    def make_post(self, author: Account, body: str = "post") -> int:
        with self._tx():
            return self.db.run(
                "INSERT INTO posts (author_id, body, created_at) VALUES (?, ?, ?)",
                author.id,
                body,
                self.now,
            )

    def like(self, user: Account, pid: int) -> None:
        with self._tx():
            self.db.run(
                "INSERT OR IGNORE INTO likes (post_id, user_id, created_at) VALUES (?, ?, ?)",
                pid,
                user.id,
                self.now,
            )

    def comment(self, user: Account, pid: int, body: str = "nice") -> int:
        with self._tx():
            return self.db.run(
                "INSERT INTO comments (post_id, author_id, body, created_at) VALUES (?, ?, ?, ?)",
                pid,
                user.id,
                body,
                self.now,
            )

    def touch(self, user: Account) -> None:
        """last_seen_at = now."""
        with self._tx():
            users.touch(self.db, user.id, self.now)

    # -- inspection and expected values --------------------------------------------------

    def row(self, sql: str, *args: object) -> dict[str, Any] | None:
        return self.db.one(sql, *args)

    def rows(self, sql: str, *args: object) -> list[dict[str, Any]]:
        return self.db.all(sql, *args)

    def message(self, mid: int) -> dict[str, Any]:
        """M of message `mid`."""
        found = self.db.one("SELECT * FROM messages WHERE id = ?", mid)
        if found is None:
            raise AssertionError(f"no message with id {mid}")
        return chat.message_json(self.db, found)

    def conversation(self, cid: int, viewer: Account) -> dict[str, Any]:
        """C of conversation `cid` as `viewer` sees it."""
        return chat.conversation_json(self.db, cid, viewer.id)


# ---------------------------------------------------------------------------------------
# UI fixtures (plain dicts in the API shapes)


def fake_message(
    id: int,
    sender: dict[str, Any],
    body: str,
    *,
    conversation_id: int = 3,
    created_at: int = START_MS,
) -> dict[str, Any]:
    """M."""
    return {
        "id": id,
        "conversation_id": conversation_id,
        "sender": dict(sender),
        "body": body,
        "created_at": created_at,
    }


def fake_conversation(
    id: int,
    kind: str,
    title: str,
    members: list[dict[str, Any]],
    *,
    last_message: dict[str, Any] | None = None,
    unread: int = 0,
    updated_at: int = START_MS,
) -> dict[str, Any]:
    """C."""
    return {
        "id": id,
        "kind": kind,
        "title": title,
        "members": [dict(m) for m in members],
        "last_message": last_message,
        "unread": unread,
        "updated_at": updated_at,
    }


def fake_request(
    id: int, frm: dict[str, Any], to: dict[str, Any], created_at: int = START_MS
) -> dict[str, Any]:
    """R."""
    return {"id": id, "from": dict(frm), "to": dict(to), "created_at": created_at}


def fake_post(
    id: int,
    author: dict[str, Any],
    body: str,
    *,
    like_count: int = 0,
    comment_count: int = 0,
    liked: bool = False,
) -> dict[str, Any]:
    """Post."""
    return {
        "id": id,
        "author": dict(author),
        "body": body,
        "created_at": START_MS,
        "like_count": like_count,
        "comment_count": comment_count,
        "liked": liked,
    }


# ---------------------------------------------------------------------------------------
# The headless page runner (tools/uirun.js)


@dataclass
class UiResult:
    pages: list[dict[str, Any]]
    page: str | None
    title: str | None
    text: str
    classes: list[list[Any]]
    buttons: list[dict[str, Any]]
    forms: list[dict[str, Any]]
    calls: list[list[Any]]
    unmatched: list[list[Any]]
    nav: list[list[Any]]
    toasts: list[str]
    badges: dict[str, int]
    session: list[list[Any]]
    errors: list[str]

    @property
    def labels(self) -> list[str]:
        """The labels of the buttons, in tree order."""
        return [str(b.get("label")) for b in self.buttons]

    def count(self, method: str, path: str) -> int:
        """The number of calls with exactly this method and path (query included)."""
        return sum(1 for c in self.calls if c[0] == method and c[1] == path)


def run_page(
    feature: str,
    page: str | None = None,
    *,
    params: dict[str, str] | None = None,
    me: dict[str, Any] | None = ALICE,
    token: str = "t0",
    api: dict[str, Any] | None = None,
    steps: list[dict[str, Any]] | None = None,
    files: list[str] | None = None,
    load_all: bool = False,
) -> UiResult:
    """Run page `page` of src/chatbook/features/<feature>/ui.js (or of `files`) in
    tools/uirun.js with the real cb.js and mocked `api` answers, then apply `steps`.
    `page=None` only loads the files (services, page registry). `me=None` is logged out."""
    paths = files if files is not None else [f"src/chatbook/features/{feature}/ui.js"]
    scenario: dict[str, Any] = {
        "cb": str(REPO / "src" / "chatbook" / "core" / "static" / "cb.js"),
        "files": [str(_abs(p)) for p in paths],
        "me": me,
        "token": token if me is not None else None,
        "page": page,
        "params": dict(params or {}),
        "api": dict(api or {}),
        "steps": list(steps or []),
        "load_all": load_all,
    }
    data = run_scenario(scenario)
    return UiResult(
        pages=list(data.get("pages") or []),
        page=data.get("page"),
        title=data.get("title"),
        text=str(data.get("text") or ""),
        classes=list(data.get("classes") or []),
        buttons=list(data.get("buttons") or []),
        forms=list(data.get("forms") or []),
        calls=list(data.get("calls") or []),
        unmatched=list(data.get("unmatched") or []),
        nav=list(data.get("nav") or []),
        toasts=list(data.get("toasts") or []),
        badges=dict(data.get("badges") or {}),
        session=list(data.get("session") or []),
        errors=list(data.get("errors") or []),
    )


def run_scenario(scenario: dict[str, Any]) -> dict[str, Any]:
    """Run `node tools/uirun.js` with `scenario` on stdin (TZ=UTC, 60 s timeout) and return
    its JSON result. Node missing, a runner crash or a timeout raise AssertionError."""
    node = shutil.which("node")
    if node is None:
        raise AssertionError("node not found: install Node.js 24 and put it on PATH")
    env = dict(os.environ)
    env["TZ"] = "UTC"
    try:
        proc = subprocess.run(
            [node, str(REPO / "tools" / "uirun.js")],
            input=json.dumps(scenario),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise AssertionError(f"tools/uirun.js timed out after 60 s\n{exc.stderr!r}") from exc
    if proc.returncode != 0:
        raise AssertionError(f"tools/uirun.js crashed (exit {proc.returncode}):\n{proc.stderr}")
    try:
        result = json.loads(proc.stdout)
    except ValueError as exc:
        raise AssertionError(
            f"tools/uirun.js printed no JSON result:\n{proc.stdout}\n{proc.stderr}"
        ) from exc
    if not isinstance(result, dict):
        raise AssertionError(f"tools/uirun.js printed {type(result).__name__}, not an object")
    return result


def _abs(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else REPO / p
