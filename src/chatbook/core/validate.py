"""Input validation helpers. Each one raises HTTPError itself (400, or 404 for path ids)."""

import re
from typing import Any, TypeGuard

from chatbook.core.http import HTTPError, Request

_MAX_ID = 2**63 - 1  # the largest integer sqlite stores
_INT = re.compile(r"-?[0-9]{1,18}")
_UINT = re.compile(r"[0-9]{1,18}")


def _body(request: Request) -> dict[str, Any]:
    if not isinstance(request.body, dict):
        raise HTTPError(400, "request body must be a JSON object")
    return request.body


def _is_id(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool) and 0 < value <= _MAX_ID


def body_str(
    request: Request, name: str, *, min_len: int = 1, max_len: int = 1000, strip: bool = True
) -> str:
    """body[name] as a string of min_len..max_len characters (after strip() unless strip=False)."""
    value = _body(request).get(name)
    if not isinstance(value, str):
        raise HTTPError(400, f"{name} must be a string")
    if strip:
        value = value.strip()
    if not min_len <= len(value) <= max_len:
        raise HTTPError(400, f"{name} must be {min_len}-{max_len} characters")
    return value


def body_id(request: Request, name: str) -> int:
    """body[name] as a positive integer (a JSON number, not true/false)."""
    value = _body(request).get(name)
    if not _is_id(value):
        raise HTTPError(400, f"{name} must be a positive integer")
    return value


def body_ids(request: Request, name: str, *, max_items: int = 100) -> list[int]:
    """body[name] as a list of at most max_items positive integers; duplicates removed,
    first-seen order kept."""
    value = _body(request).get(name)
    if not isinstance(value, list) or len(value) > max_items:
        raise HTTPError(400, f"{name} must be a list of positive integers")
    ids: list[int] = []
    for item in value:
        if not _is_id(item):
            raise HTTPError(400, f"{name} must be a list of positive integers")
        if item not in ids:
            ids.append(item)
    return ids


def path_id(request: Request, name: str = "id") -> int:
    """The {name} path segment as a positive integer; HTTPError(404) otherwise."""
    raw = request.params.get(name, "")
    if not (1 <= len(raw) <= 18 and raw.isascii() and raw.isdigit()) or int(raw) <= 0:
        raise HTTPError(404, "not found")
    return int(raw)


def query_str(request: Request, name: str, *, max_len: int, min_len: int = 1) -> str:
    """The query parameter, stripped, of min_len..max_len characters."""
    value = request.query.get(name, "").strip()
    if not min_len <= len(value) <= max_len:
        raise HTTPError(400, f"{name} must be {min_len}-{max_len} characters")
    return value


def query_int(request: Request, name: str, *, default: int, lo: int, hi: int) -> int:
    """The query parameter as an integer in lo..hi; `default` when missing or empty."""
    raw = request.query.get(name, "")
    if raw == "":
        return default
    if not _INT.fullmatch(raw) or not lo <= int(raw) <= hi:
        raise HTTPError(400, f"{name} must be an integer between {lo} and {hi}")
    return int(raw)


def query_opt_int(request: Request, name: str) -> int | None:
    """The query parameter as a non-negative integer; None when missing or empty."""
    raw = request.query.get(name, "")
    if raw == "":
        return None
    if not _UINT.fullmatch(raw):
        raise HTTPError(400, f"{name} must be a non-negative integer")
    return int(raw)
