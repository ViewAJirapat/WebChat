"""Request and response types shared by the app and every feature."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # users.py imports HTTPError from here, so User is imported for typing only
    from chatbook.core.store import Db
    from chatbook.core.users import User

JSON_TYPE = "application/json; charset=utf-8"


class HTTPError(Exception):
    """Raise from a handler to answer with an error status and {"error": message}."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass(frozen=True)
class Request:
    method: str
    path: str
    params: dict[str, str]  # {name} path segments
    query: dict[str, str]
    body: object  # parsed JSON or None
    headers: dict[str, str]  # lower-case names
    user: User | None  # resolved by the App from the bearer token
    token: str | None
    db: Db
    now: int  # ms, from the App's clock, fixed for the request

    @property
    def me(self) -> User:
        """The logged-in user; HTTPError(401) if the request is anonymous."""
        if self.user is None:
            raise HTTPError(401, "login required")
        return self.user


@dataclass(frozen=True)
class Response:
    status: int
    body: object = None  # JSON-serializable (features); bytes for frame static files
    content_type: str = JSON_TYPE
    headers: tuple[tuple[str, str], ...] = ()
