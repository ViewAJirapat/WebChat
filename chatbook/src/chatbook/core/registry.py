"""Auto-discovery: every package in chatbook/features is a feature.

A backend feature is a folder with an __init__.py and a handler.py whose handlers carry
@route. A page feature is a folder with an __init__.py and a ui.js. Nothing is registered by
hand, so adding a feature never touches a shared file, and two features built in parallel
never conflict.
"""

import importlib
import importlib.util
import pkgutil
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from chatbook.core.http import Request, Response

Handler = Callable[[Request], Response]
_MARK = "__chatbook_routes__"
_UI_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


class RegistryError(Exception):
    pass


@dataclass(frozen=True)
class Route:
    method: str
    pattern: str  # e.g. "/api/users/{id}"
    handler: Handler
    feature: str
    public: bool = False  # True: no login needed


def route(method: str, pattern: str, *, public: bool = False) -> Callable[[Handler], Handler]:
    """Mark a handler for discovery: @route("GET", "/api/users/{id}"). Stackable."""

    def mark(handler: Handler) -> Handler:
        marks: list[tuple[str, str, bool]] = list(getattr(handler, _MARK, []))
        marks.append((method.upper(), pattern, public))
        setattr(handler, _MARK, marks)
        return handler

    return mark


def _segments(path: str) -> list[str]:
    return path.strip("/").split("/")


def _is_param(segment: str) -> bool:
    return segment.startswith("{") and segment.endswith("}")


def match(pattern: str, path: str) -> dict[str, str] | None:
    """Path parameters if `path` fits `pattern`, else None."""
    want, got = _segments(pattern), _segments(path)
    if len(want) != len(got):
        return None
    params: dict[str, str] = {}
    for w, g in zip(want, got, strict=True):
        if _is_param(w):
            if not g:
                return None
            params[w[1:-1]] = g
        elif w != g:
            return None
    return params


def specificity(pattern: str) -> tuple[int, ...]:
    """Sort key: fixed segments before {params}, so /items/new beats /items/{id}
    whichever feature folder sorts first."""
    return tuple(1 if _is_param(s) else 0 for s in _segments(pattern))


def _shape(pattern: str) -> str:
    return "/" + "/".join("{}" if _is_param(s) else s for s in _segments(pattern))


def ensure_unique(routes: list[Route]) -> None:
    """Two routes with the same method and shape fail loudly."""
    seen: dict[tuple[str, str], Route] = {}
    for r in routes:
        key = (r.method, _shape(r.pattern))
        if key in seen:
            other = seen[key]
            raise RegistryError(
                f"{r.method} {r.pattern} is defined by features {other.feature!r} and {r.feature!r}"
            )
        seen[key] = r


def _folders(package: str) -> list[Path]:
    pkg = importlib.import_module(package)
    return [child for folder in pkg.__path__ for child in sorted(Path(folder).iterdir())]


def discover(package: str = "chatbook.features") -> list[Route]:
    """Import <package>.<feature>.handler for every feature folder and collect its routes.
    Page folders (no handler.py) are skipped."""
    for child in _folders(package):
        if (child / "handler.py").is_file() and not (child / "__init__.py").is_file():
            raise RegistryError(f"feature folder {child.name!r} has no __init__.py")
    pkg = importlib.import_module(package)
    routes: list[Route] = []
    for info in sorted(pkgutil.iter_modules(pkg.__path__), key=lambda i: i.name):
        feature = f"{package}.{info.name}"
        name = f"{feature}.handler"
        if not info.ispkg or importlib.util.find_spec(name) is None:
            continue
        module = importlib.import_module(name)
        handlers = {id(obj): obj for obj in vars(module).values()}  # one entry per function
        for obj in handlers.values():
            marks = getattr(obj, _MARK, None)
            origin = getattr(obj, "__module__", "") or ""
            # Handlers may live in any module of the same feature and be imported here.
            if marks and callable(obj) and (origin == feature or origin.startswith(feature + ".")):
                routes += [
                    Route(method, pattern, obj, info.name, public)
                    for method, pattern, public in marks
                ]
    ensure_unique(routes)
    return routes


def discover_ui(package: str = "chatbook.features") -> list[str]:
    """Sorted names of the feature folders that contain a ui.js (pages and services)."""
    names: list[str] = []
    for child in _folders(package):
        if not (child / "ui.js").is_file():
            continue
        if not _UI_NAME.fullmatch(child.name):
            raise RegistryError(
                f"feature folder {child.name!r} has a ui.js but its name does not match "
                "^[a-z][a-z0-9_]*$"
            )
        if not (child / "__init__.py").is_file():
            raise RegistryError(f"feature folder {child.name!r} has no __init__.py")
        names.append(child.name)
    return sorted(set(names))
