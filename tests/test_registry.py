"""Route and page discovery (core/registry.py): shopapi's registry tests plus `public` and ui.js."""

import importlib
import sys
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from chatbook import create_app
from chatbook.core.http import Request, Response
from chatbook.core.registry import (
    RegistryError,
    Route,
    discover,
    discover_ui,
    ensure_unique,
    match,
    route,
    specificity,
)

Handler = Callable[[Request], Response]
UI_JS = "CB.page('x', {title: 'X', render: () => 'x'});\n"


def _ok(request: Request) -> Response:
    return Response(200, None)


def _returns(value: str) -> Handler:
    def handler(request: Request) -> Response:
        return Response(200, {"from": value})

    return handler


def _route(method: str, pattern: str, handler: Handler, feature: str) -> Route:
    return Route(method=method, pattern=pattern, handler=handler, feature=feature, public=True)


@pytest.fixture
def tmp_package(tmp_path: Path) -> Iterator[Callable[[str], Path]]:
    """Make importable throwaway packages under tmp_path (never inside the repo)."""
    names: list[str] = []
    sys.path.insert(0, str(tmp_path))

    def make(name: str) -> Path:
        pkg = tmp_path / name
        _write(pkg / "__init__.py")
        names.append(name)
        return pkg

    yield make
    sys.path.remove(str(tmp_path))
    for mod in [m for m in sys.modules if m.split(".")[0] in names]:
        del sys.modules[mod]
    importlib.invalidate_caches()


def _write(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    importlib.invalidate_caches()


def test_match_extracts_params() -> None:
    assert match("/api/users/{id}", "/api/users/7") == {"id": "7"}
    assert match("/api/users/{id}", "/api/users/") is None
    assert match("/api/users/{id}", "/api/users/7/x") is None
    assert match("/api/groups/{id}/members/me", "/api/groups/3/members/me") == {"id": "3"}
    assert match("/api/groups/{id}/members/me", "/api/groups/3/members/you") is None
    assert match("/api/health", "/api/health") == {}


def test_two_features_claiming_one_route_shape_fail_loudly() -> None:
    routes = [_route("GET", "/x/{a}", _ok, "one"), _route("GET", "/x/{b}", _ok, "two")]
    with pytest.raises(RegistryError, match=r"one.*two|two.*one"):
        ensure_unique(routes)


def test_same_shape_with_another_method_is_fine() -> None:
    ensure_unique([_route("GET", "/x/{a}", _ok, "one"), _route("DELETE", "/x/{b}", _ok, "two")])


def test_fixed_segments_sort_before_params() -> None:
    assert specificity("/api/groups/{id}/members/me") < specificity("/api/groups/{id}/members/{x}")
    assert specificity("/items/new") < specificity("/items/{id}")


def test_fixed_segments_win_over_params_whatever_the_feature_order() -> None:
    app = create_app()
    by_param = _route("GET", "/api/t/items/{id}", _returns("param"), "a_items")
    fixed = _route("GET", "/api/t/items/new", _returns("fixed"), "z_new")
    app.routes = sorted([*app.routes, by_param, fixed], key=lambda r: specificity(r.pattern))
    assert app.handle("GET", "/api/t/items/new").body == {"from": "fixed"}
    assert app.handle("GET", "/api/t/items/7").body == {"from": "param"}


def test_app_routes_are_sorted_by_specificity() -> None:
    keys = [specificity(r.pattern) for r in create_app().routes]
    assert keys == sorted(keys)


def test_route_marks_stack_with_their_public_flag() -> None:
    def handler(request: Request) -> Response:
        return Response(200, request.method)

    both = route("GET", "/a", public=True)(route("POST", "/a")(handler))
    assert both is handler
    marks = sorted(tuple(m) for m in vars(both)["__chatbook_routes__"])
    assert marks == [("GET", "/a", True), ("POST", "/a", False)]


def test_feature_folder_without_init_fails_loudly(tmp_package: Callable[[str], Path]) -> None:
    pkg = tmp_package("cbt_noinit")
    _write(pkg / "broken" / "handler.py")
    with pytest.raises(RegistryError, match="broken"):
        discover("cbt_noinit")


def test_discover_keeps_stacked_reexported_and_aliased_handlers(
    tmp_package: Callable[[str], Path],
) -> None:
    pkg = tmp_package("cbt_multi")
    _write(pkg / "multi" / "__init__.py")
    _write(
        pkg / "multi" / "impl.py",
        "from chatbook.core.api import Request, Response, route\n\n\n"
        '@route("GET", "/multi", public=True)\n'
        '@route("POST", "/multi")\n'
        "def both(request: Request) -> Response:\n"
        "    return Response(200, request.method)\n",
    )
    _write(pkg / "multi" / "handler.py", "from cbt_multi.multi.impl import both\n\nalias = both\n")
    found = sorted((r.method, r.pattern, r.feature, r.public) for r in discover("cbt_multi"))
    assert found == [("GET", "/multi", "multi", True), ("POST", "/multi", "multi", False)]


def test_page_folders_are_skipped_by_discover_and_listed_by_discover_ui(
    tmp_package: Callable[[str], Path],
) -> None:
    pkg = tmp_package("cbt_pages")
    for name in ["zeta_page", "alpha_page"]:
        _write(pkg / name / "__init__.py")
        _write(pkg / name / "ui.js", UI_JS)
    _write(pkg / "backend" / "__init__.py")
    _write(
        pkg / "backend" / "handler.py",
        "from chatbook.core.api import Request, Response, route\n\n\n"
        '@route("GET", "/backend")\n'
        "def get(request: Request) -> Response:\n"
        "    return Response(200, None)\n",
    )
    found = [(r.feature, r.method, r.pattern, r.public) for r in discover("cbt_pages")]
    assert found == [("backend", "GET", "/backend", False)]
    assert discover_ui("cbt_pages") == ["alpha_page", "zeta_page"]


def test_ui_folder_without_init_fails_loudly(tmp_package: Callable[[str], Path]) -> None:
    pkg = tmp_package("cbt_uinoinit")
    _write(pkg / "lonely" / "ui.js", UI_JS)
    with pytest.raises(RegistryError):
        discover_ui("cbt_uinoinit")


def test_ui_folder_with_a_bad_name_fails_loudly(tmp_package: Callable[[str], Path]) -> None:
    pkg = tmp_package("cbt_uibadname")
    _write(pkg / "BadPage" / "__init__.py")
    _write(pkg / "BadPage" / "ui.js", UI_JS)
    with pytest.raises(RegistryError):
        discover_ui("cbt_uibadname")
