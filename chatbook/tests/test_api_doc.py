"""The worker docs (docs/api/*.md) match the code they describe (DESIGN 3.18).

A name is documented where a line starts with `name(` or `@name(` (a signature) or `Name:` (a
field list). Db counts as documented where its method signatures are. Every `name(params) -> ret`
line must have the parameter names, kinds and defaults of inspect.signature.
"""

import ast
import dataclasses
import inspect
import re
from pathlib import Path
from typing import Any

from chatbook.core import api
from chatbook.core.store import Db, connect

DOCS = Path(__file__).resolve().parents[1] / "docs" / "api"
DB_METHODS = ["one", "all", "value", "run", "page"]
EMPTY = inspect.Parameter.empty

# DESIGN 3.10, in this order: the whole public contract of chatbook.core.api
ALL = [
    "route",
    "Request",
    "Response",
    "HTTPError",
    "User",
    "Db",
    "body_str",
    "body_id",
    "body_ids",
    "path_id",
    "query_str",
    "query_int",
    "query_opt_int",
    "user_json",
    "get_user",
    "require_user",
    "create_user",
    "check_password",
    "new_session",
    "are_friends",
    "befriend",
    "unfriend",
    "relationship",
    "friend_ids",
    "visible_post",
    "can_see_post",
    "create_conversation",
    "find_direct",
    "require_member",
    "member_ids",
    "add_member",
    "remove_member",
    "post_message",
    "message_json",
    "mark_read",
    "unread_count",
    "conversation_json",
]
TABLE_LINE = re.compile(r"^([a-z_]+)\(([^()]*)\)")

SIGNATURE = re.compile(r"(?<![\w.])([A-Za-z_]\w*)\(([^()]*)\)\s*->")
STARTS = re.compile(r"^\s*@?([A-Za-z_]\w*)\s*[(:]")
DECORATOR = re.compile(r"^\s*@([A-Za-z_]\w*)\(([^()]*)\)")


def doc_files() -> dict[str, list[str]]:
    files = {p.name: p.read_text(encoding="utf-8").splitlines() for p in sorted(DOCS.glob("*.md"))}
    assert "base.md" in files
    return files


def signatures() -> list[tuple[str, int, str, str]]:
    """(file, line number, name, params) for every `name(params) -> ret` in the docs."""
    found = []
    for file, lines in doc_files().items():
        for number, line in enumerate(lines, 1):
            if line.lstrip().startswith(("def ", "class ")):
                continue  # the example handler is code, not reference
            for m in SIGNATURE.finditer(line):
                found.append((file, number, m.group(1), m.group(2)))
    return found


def documented_in(name: str) -> set[str]:
    where = set()
    for file, lines in doc_files().items():
        for line in lines:
            m = STARTS.match(line)
            if m and m.group(1) == name:
                where.add(file)
    if name == "Db":
        where |= {file for file, _, sig, _ in signatures() if sig in DB_METHODS}
    return where


Shape = list[tuple[str, inspect._ParameterKind, Any]]


def doc_shape(params: str) -> Shape:
    tree = ast.parse(f"def _f({params}): pass")
    fn = tree.body[0]
    assert isinstance(fn, ast.FunctionDef)
    a = fn.args
    shape: Shape = []
    positional: list[tuple[ast.arg, inspect._ParameterKind]]
    positional = [(x, inspect.Parameter.POSITIONAL_ONLY) for x in a.posonlyargs]
    positional += [(x, inspect.Parameter.POSITIONAL_OR_KEYWORD) for x in a.args]
    defaults: list[Any] = [EMPTY] * (len(positional) - len(a.defaults))
    defaults += [ast.literal_eval(d) for d in a.defaults]
    for (arg, kind), default in zip(positional, defaults, strict=True):
        shape.append((arg.arg, kind, default))
    if a.vararg:
        shape.append((a.vararg.arg, inspect.Parameter.VAR_POSITIONAL, EMPTY))
    for arg, kw_default in zip(a.kwonlyargs, a.kw_defaults, strict=True):
        value = EMPTY if kw_default is None else ast.literal_eval(kw_default)
        shape.append((arg.arg, inspect.Parameter.KEYWORD_ONLY, value))
    if a.kwarg:
        shape.append((a.kwarg.arg, inspect.Parameter.VAR_KEYWORD, EMPTY))
    return shape


def code_shape(obj: Any) -> Shape:
    params = list(inspect.signature(obj).parameters.values())
    if params and params[0].name == "self":
        params = params[1:]
    return [(p.name, p.kind, p.default) for p in params]


def typed(shape: Shape) -> list[tuple[str, inspect._ParameterKind, type, Any]]:
    return [(name, kind, type(default), default) for name, kind, default in shape]


def target(name: str) -> Any:
    if name in DB_METHODS:
        return getattr(Db, name)
    assert name in api.__all__, f"documented but not exported by chatbook.core.api: {name}"
    return getattr(api, name)


def test_the_public_contract_is_exact() -> None:
    assert api.__all__ == ALL


def test_every_export_exists() -> None:
    for name in api.__all__:
        assert hasattr(api, name), name


def test_documented_tables_match_the_schema() -> None:
    db = connect(":memory:")
    schema = {
        r["name"]: [c["name"] for c in db.all(f"PRAGMA table_info({r['name']})")]
        for r in db.all("SELECT name FROM sqlite_master WHERE type = 'table'")
        if r["name"] != "sqlite_sequence"
    }
    documented: set[str] = set()
    problems = []
    for file, lines in doc_files().items():
        for number, line in enumerate(lines, 1):
            m = TABLE_LINE.match(line)
            if not m or m.group(1) not in schema:
                continue
            columns = [c.strip() for c in m.group(2).split(",")]
            want = schema[m.group(1)]
            if columns != want:
                problems.append(f"{file}:{number}: {line.strip()} but the schema has {want}")
            documented.add(m.group(1))
    assert problems == []
    assert sorted(set(schema) - documented) == ["sessions"]  # sessions are frame-only


def test_every_export_is_documented_in_exactly_one_file() -> None:
    problems = []
    for name in api.__all__:
        where = documented_in(name)
        if len(where) != 1:
            problems.append(f"{name}: documented in {sorted(where) or 'no file'}")
    assert problems == []


def test_every_function_and_db_method_has_a_signature_line() -> None:
    names = {sig for _, _, sig, _ in signatures()}
    functions = [n for n in api.__all__ if inspect.isfunction(getattr(api, n)) and n != "route"]
    assert sorted(set(functions + DB_METHODS) - names) == []


def test_decorator_lines_match_the_code() -> None:
    checked = []
    for file, lines in doc_files().items():
        for number, line in enumerate(lines, 1):
            m = DECORATOR.match(line)
            if not m:
                continue
            try:
                doc = doc_shape(m.group(2))
            except SyntaxError:
                continue  # a usage example such as @route("PUT", "/api/notes/{id}")
            code = code_shape(target(m.group(1)))
            assert typed(doc) == typed(code), f"{file}:{number}: {line.strip()} but code has {code}"
            checked.append(m.group(1))
    assert "route" in checked


def test_documented_signatures_match_the_code() -> None:
    problems = []
    for file, number, name, params in signatures():
        try:
            doc = doc_shape(params)
        except SyntaxError:
            problems.append(f"{file}:{number}: {name}({params}) is not a parameter list")
            continue
        code = code_shape(target(name))
        if typed(doc) != typed(code):
            problems.append(f"{file}:{number}: {name}({params}) but the code has {code}")
    assert problems == []


def field_list(name: str) -> list[str]:
    for lines in doc_files().values():
        for line in lines:
            if line.startswith(name + ":"):
                text = re.split(r"\s{2,}|\(", line[len(name) + 1 :].strip())[0]
                return [f.strip() for f in text.split(",") if f.strip()]
    raise AssertionError(f"no '{name}:' line in docs/api")


def test_request_fields_match_the_dataclass() -> None:
    assert field_list("Request") == [f.name for f in dataclasses.fields(api.Request)]


def test_user_fields_match_the_dataclass() -> None:
    assert field_list("User") == [f.name for f in dataclasses.fields(api.User)]
