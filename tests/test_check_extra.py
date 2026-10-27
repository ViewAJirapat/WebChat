"""The extra gate (tools/check_extra.py), run on small throwaway trees outside the repo."""

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

REPO = Path(__file__).resolve().parents[1]

GOOD_UI = """// a page; words like windowless, documents and styles are fine
CB.page('good', {title: 'Good', render: () => CB.el('p', {class: 'muted'}, 'Good')});
"""
SERVICE_UI = "CB.every(5000, async () => {});\n"
GOOD_PY = (
    '"""good: fine."""\n\n'
    "# CREATE in a comment is fine: only string literals are checked\n"
    'LABEL = "dropdown"\n'
)

# line number -> offending line; line 1 registers the page
BAD_UI_LINES = [
    "CB.page('bad', {title: 'Bad', render: () => 'x'});",
    "document.title = 'x';",
    "window.foo = 1;",
    "const g = globalThis;",
    "fetch('/api/x');",
    "const x = new XMLHttpRequest();",
    "node.innerHTML = '<b>';",
    "node.outerHTML = '';",
    "node.insertAdjacentHTML('beforeend', '');",
    "eval('1');",
    "const f = new Function('return 1');",
    "setTimeout(() => {}, 1);",
    "setInterval(() => {}, 1);",
    "localStorage.getItem('a');",
    "sessionStorage.getItem('a');",
    "node.addEventListener('click', () => {});",
    "node.classList.add('a');",
    "node.style.color = 'red';",
    "node.setAttribute('a', 'b');",
    "node.querySelector('p');",
    "node.getElementById('a');",
    "const m = require('fs');",
    "import('x');",
    "// window.comment = 1;",
]
HINTS = [
    "use CB.* only",
    "use CB.api",
    "build nodes with CB.el",
    "not allowed",
    "use the page's poll or CB.every",
    "the frame keeps the session",
    "use the onclick prop or CB.form",
    "use CB.el props (class, ...)",
    "keep references to the nodes you create",
    "no modules",
]
# the browser objects are fine outside feature pages (cb.js is the frame's own code)
CORE_JS = "document.title = 'x';\nwindow.CB = {};\nsetTimeout(() => {}, 1);\n"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def make_tree(root: Path, features: dict[str, str], snapshot: bool = True) -> None:
    """A minimal repo copy: the tool itself plus src/chatbook/features/<path> files, and an
    empty CONTRACT snapshot unless `snapshot` is False."""
    write(root / "tools" / "check_extra.py", (REPO / "tools" / "check_extra.py").read_text("utf-8"))
    if snapshot:
        write(root / "tools" / "contracts.json", '{"files": {}}\n')
    write(root / "src" / "chatbook" / "__init__.py", "")
    write(root / "src" / "chatbook" / "features" / "__init__.py", "")
    for rel, text in features.items():
        write(root / "src" / "chatbook" / "features" / rel, text)


def check(root: Path, env: dict[str, str] | None = None, *args: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "tools/check_extra.py", *args],
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        env=env,
    )
    return proc.returncode, proc.stdout + proc.stderr


def test_node_is_on_path() -> None:
    assert shutil.which("node"), "install Node.js 24 and put it on PATH"


def test_clean_tree_passes(tmp_path: Path) -> None:
    filler = "".join(f"X{i} = {i}\n" for i in range(179))
    make_tree(
        tmp_path,
        {
            "good/__init__.py": '"""good."""\n',
            "good/handler.py": GOOD_PY,
            "good/ui.js": GOOD_UI,
            "svc/__init__.py": '"""svc."""\n',
            "svc/ui.js": SERVICE_UI,
            "big/__init__.py": '"""big."""\n',
            "big/handler.py": '"""big: exactly 180 lines."""\n' + filler,
        },
    )
    write(tmp_path / "src" / "chatbook" / "core" / "static" / "cb.js", CORE_JS)
    big = tmp_path / "src" / "chatbook" / "features" / "big" / "handler.py"
    assert len(big.read_text(encoding="utf-8").splitlines()) == 180
    code, out = check(tmp_path)
    assert code == 0, out


def test_problems_are_reported_with_file_line_and_hint(tmp_path: Path) -> None:
    long_py = '"""long."""\n' + "".join(f"Y{i} = {i}\n" for i in range(180))
    make_tree(
        tmp_path,
        {
            "bad/__init__.py": '"""bad."""\n',
            "bad/ui.js": "\n".join(BAD_UI_LINES) + "\n",
            "nomark/__init__.py": '"""nomark."""\n',
            "nomark/ui.js": "const a = 1;\n",
            "broken/__init__.py": '"""broken."""\n',
            "broken/ui.js": "CB.page('broken', {title: 'B', render: () => (});\n",
            "long/__init__.py": '"""long."""\n',
            "long/handler.py": long_py,
            "longjs/__init__.py": '"""longjs."""\n',
            "longjs/ui.js": "CB.every(5000, async () => {});\n" + "// filler\n" * 180,
            "ddl/__init__.py": '"""ddl."""\n',
            "ddl/handler.py": (
                '"""ddl."""\n\n'
                'A = "create table x (a int)"\n'
                "B = 'pragma foreign_keys'\n"
                'C = "dropdown and dropped are other words"\n'
            ),
        },
    )
    write(tmp_path / "tools" / "helper.js", "const x = ;\n")
    write(tmp_path / "src" / "chatbook" / "core" / "static" / "cb.js", "function (\n")
    code, out = check(tmp_path)
    assert code == 1, out
    assert re.search(r"tools[/\\]helper\.js", out), out  # node --check covers tools/ too
    assert re.search(r"core[/\\]static[/\\]cb\.js", out), out  # and the frame's own js
    assert re.search(r"longjs[/\\]ui\.js", out), out  # the size limit covers .js too
    for number in range(2, len(BAD_UI_LINES) + 1):
        assert re.search(rf"bad[/\\]ui\.js:{number}:", out), f"line {number} not reported:\n{out}"
    assert not re.search(r"bad[/\\]ui\.js:1:", out), out
    for hint in HINTS:
        assert hint in out, f"hint {hint!r} missing:\n{out}"
    assert re.search(r"nomark[/\\]ui\.js", out), out  # neither CB.page( nor CB.every(
    assert re.search(r"broken[/\\]ui\.js", out), out  # node --check
    assert re.search(r"long[/\\]handler\.py", out), out
    assert "split or simplify" in out
    assert re.search(r"ddl[/\\]handler\.py:3:", out), out
    assert re.search(r"ddl[/\\]handler\.py:4:", out), out
    assert not re.search(r"ddl[/\\]handler\.py:5:", out), out
    assert "the schema belongs to the frame" in out


# Schema SQL: line number -> source line; every line below the docstring is a problem.
DDL_BAD = '''"""ddl."""

A = "drop table users"
B = "CREATE UNIQUE INDEX i ON t (a)"
C = "ATTACH 'x.db' AS y"
D = "create temp table t (a)"
E = "CREATE " "TABLE t (a)"
F = "ALTER " + "TABLE users ADD x"
'''
# English that only looks like schema words: docstrings and messages are fine.
DDL_FINE = '''"""groups: Create a group and DROP a member."""

from chatbook.core.api import HTTPError, Request, Response


class Note:
    """Create a note."""


def create_group(request: Request) -> Response:
    """Create a new group conversation."""
    if request.body is None:
        raise HTTPError(400, "cannot create a group alone")
    return Response(200, {"hint": "drop the title or alter it", "x": "dropdown"})
'''


def test_schema_sql_is_rejected_but_english_words_are_not(tmp_path: Path) -> None:
    make_tree(tmp_path, {"ddlbad/handler.py": DDL_BAD, "ddlfine/handler.py": DDL_FINE})
    code, out = check(tmp_path)
    assert code == 1, out
    for number in range(3, len(DDL_BAD.splitlines()) + 1):
        assert re.search(rf"ddlbad[/\\]handler\.py:{number}: ", out), f"line {number}:\n{out}"
    assert "ddlfine" not in out, out
    assert "the schema belongs to the frame" in out


# SQL built at run time, one way per file; the finding's split literal comes first.
SQL_BAD = {
    # SQL on a plain line, the value on an f" continuation line (adjacent literals)
    "split": 'def f(db, q):\n    return db.all(\n        "SELECT * FROM users"\n'
    "        f\" WHERE username LIKE '%{q}%'\"\n    )\n",
    "lower": 'def f(db, me):\n    return db.one(f"select * from users where id = {me}")\n',
    "triple": 'def f(db, me):\n    return db.one(f"""SELECT *\n'
    '    FROM users WHERE id = {me}""")\n',
    "rprefix": 'def f(db, me):\n    return db.one(rf"SELECT * FROM users WHERE id = {me}")\n',
    "upper": 'def f(db, me):\n    return db.one(F"SELECT * FROM users WHERE id = {me}")\n',
    "plus": 'def f(db, me):\n    return db.all("SELECT * FROM users WHERE id = " + str(me))\n',
    "percent": 'def f(db, me):\n    return db.all("SELECT * FROM users WHERE id = %d" % me)\n',
    "format": 'def f(db, me):\n    return db.all("SELECT * FROM users WHERE id = {}".format(me))\n',
    "variable": 'def f(db, me):\n    cond = f" AND id = {me}"\n'
    '    sql = "SELECT * FROM users WHERE 1 = 1" + cond\n    return db.all(sql)\n',
    "augmented": 'def f(db, me):\n    sql = "SELECT * FROM users"\n'
    '    sql += " WHERE id = " + str(me)\n    return db.all(sql)\n',
    "inlist": 'def f(db, ids):\n    marks = ", ".join("?" * len(ids))\n'
    '    return db.all("SELECT * FROM users WHERE id IN (" + marks + ")", *ids)\n',
}
# Placeholders only: adjacent literals, a constant, a choice of literals, messages.
SQL_FINE = '''"""posts: SELECT * FROM posts WHERE id = ? (the CONTRACT may quote SQL)."""

from typing import Any

FEED = "SELECT * FROM posts WHERE author_id = ? ORDER BY id DESC"


def feed(db: Any, me: int, before: int | None, pid: int) -> Any:
    rows = db.all(FEED, me)
    sql = "SELECT * FROM posts WHERE id < ?" if before else "SELECT * FROM posts WHERE 1 = ?"
    more = db.all(sql, before or 1)
    row = db.one(
        "SELECT * FROM posts WHERE id = ?"
        " AND author_id = ?",
        pid,
        me,
    )
    if row is None:
        raise ValueError(f"cannot delete post {pid}: select another one")
    return rows, more, db.page("SELECT * FROM posts ORDER BY id", limit=5), f"{me}:{pid}"
'''


def test_sql_built_at_run_time_is_rejected(tmp_path: Path) -> None:
    files = {f"sql_{name}/handler.py": text for name, text in SQL_BAD.items()}
    make_tree(tmp_path, files | {"sql_fine/handler.py": SQL_FINE})
    code, out = check(tmp_path)
    assert code == 1, out
    for name in SQL_BAD:
        pattern = rf"sql_{name}[/\\]handler\.py:\d+: .*\(fix: SQL must be one string literal"
        assert re.search(pattern, out), f"{name} not reported:\n{out}"
    assert "sql_fine" not in out, out


def test_node_missing_fails_with_the_install_hint(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    make_tree(root, {"good/__init__.py": '"""good."""\n', "good/ui.js": GOOD_UI})
    empty = tmp_path / "empty-path"
    empty.mkdir()
    code, out = check(root, env={**os.environ, "PATH": str(empty)})
    assert code == 1, out
    assert "install Node.js 24 and put it on PATH" in out


# CONTRACT blocks (section 3.17): one stub of each kind, split into its block and its code.
PY_BLOCK = '''"""demo: one route.

CONTRACT (keep this docstring; implement exactly this):
GET /api/demo
  -> 200 {"ok": true}
"""
'''
PY_CODE = """
from chatbook.core.api import HTTPError, Request, Response, route


@route("GET", "/api/demo")
def demo(request: Request) -> Response:
    raise HTTPError(501, "not implemented")
"""
JS_BLOCK = """// page_demo: a page.
// CONTRACT (keep this comment; implement exactly this):
// CB.page('demo', {title: 'Demo', render})
// render() -> CB.el('p', {}, 'Demo')
"""
JS_CODE = """CB.page('demo', {
  title: 'Demo',
  render: () => CB.el('p', {class: 'muted'}, 'Coming soon'),
});
"""
PY = "demo/handler.py"
JS = "page_demo/ui.js"
CONTRACT_HINT = "(fix: restore it verbatim at the top of the file, then put your code below it)"


def test_unchanged_stubs_and_code_below_the_contract_block_pass(tmp_path: Path) -> None:
    make_tree(tmp_path, {PY: PY_BLOCK + PY_CODE, JS: JS_BLOCK + JS_CODE}, snapshot=False)
    code, out = check(tmp_path, None, "--write-contracts")  # as staff make the snapshot
    assert code == 0 and "2 CONTRACT block(s)" in out, out
    assert check(tmp_path) == (0, "check_extra: ok\n")
    # a worker's code below the block, saved with CRLF line endings (and the JS with a BOM)
    below = {
        PY: PY_BLOCK
        + "# a comment\nimport re\n"
        + PY_CODE
        + "\n\ndef f() -> str:\n    return ''\n",
        JS: JS_BLOCK + "\n// a comment after a blank line\nconst A = 'a'; // note\n" + JS_CODE,
    }
    for rel, text in below.items():
        file = tmp_path / "src" / "chatbook" / "features" / rel
        bom = "\ufeff" if rel == JS else ""
        file.write_bytes((bom + text).replace("\n", "\r\n").encode("utf-8"))
    code, out = check(tmp_path)
    assert code == 0, out


# folder -> (stub file, the worker's text (None: deleted), reported line, message)
CONTRACT_BAD = {
    "py_deleted": ("handler.py", PY_CODE.lstrip("\n"), 1, "CONTRACT block missing or changed"),
    "py_edited": ("handler.py", PY_BLOCK.replace("200", "201") + PY_CODE, 5, "or changed"),
    "py_code_above": ("handler.py", "import re\n" + PY_BLOCK + PY_CODE, 1, "moved below"),
    "py_moved_down": ("handler.py", PY_CODE.lstrip("\n") + "\n" + PY_BLOCK, 1, "moved below"),
    "py_file_deleted": ("handler.py", None, 1, "file missing"),
    "js_deleted": ("ui.js", JS_CODE, 1, "CONTRACT block missing or changed"),
    "js_edited": ("ui.js", JS_BLOCK.replace("// render", "// x") + JS_CODE, 4, "or changed"),
    "js_code_above": ("ui.js", "const x = 1;\n" + JS_BLOCK + JS_CODE, 1, "moved below"),
    "js_extended": ("ui.js", JS_BLOCK + "// my note\n" + JS_CODE, 5, "comment line right after"),
}


def test_a_damaged_contract_block_fails_with_the_text_to_restore(tmp_path: Path) -> None:
    files: dict[str, str] = {}
    snapshot: dict[str, list[str]] = {}
    for folder, (name, text, _, _) in CONTRACT_BAD.items():
        block = PY_BLOCK if name == "handler.py" else JS_BLOCK
        snapshot[f"src/chatbook/features/{folder}/{name}"] = block.split("\n")[:-1]
        if text is not None:
            files[f"{folder}/{name}"] = text
    make_tree(tmp_path, files, snapshot=False)
    write(tmp_path / "tools" / "contracts.json", json.dumps({"files": snapshot}, indent=2))
    code, out = check(tmp_path)
    assert code == 1, out
    assert f"check_extra: {len(CONTRACT_BAD)} problem(s)" in out, out
    for folder, (name, _, line, message) in CONTRACT_BAD.items():
        path = f"src/chatbook/features/{folder}/{name}"
        found = re.search(rf"^{re.escape(path)}:{line}: [^\n]*{message}[^\n]*$", out, re.M)
        assert found, f"{folder}:\n{out}"
        block = PY_BLOCK if name == "handler.py" else JS_BLOCK
        if "moved" in message:
            assert found.group(0).endswith(CONTRACT_HINT) and "(it starts at line " in out
        elif "right after" in message:
            assert "put a blank line or code before your comments" in found.group(0)
        else:  # missing or changed: the exact text to restore follows
            assert found.group(0).endswith(CONTRACT_HINT), out
            shown = f"==== CONTRACT block of {path} ====\n{block}==== end of the CONTRACT block"
            assert shown in out, f"{folder}:\n{out}"


def test_missing_snapshot_fails(tmp_path: Path) -> None:
    make_tree(tmp_path, {PY: PY_BLOCK + PY_CODE}, snapshot=False)
    code, out = check(tmp_path)
    assert code == 1, out
    assert "tools/contracts.json: not found (fix: staff: run python tools/check_extra.py" in out


# --restore-contracts (the harness autofix step, 3.16 item 6): folder -> (stub file, the
# worker's text, the text after restoring; None: left exactly as it is).
PY_TOP = PY_CODE.lstrip("\n")  # the stub's code without the blank line after the block
FUTURE = "from __future__ import annotations\n"
RESTORED_0 = "restore-contracts: 0 CONTRACT block(s) restored\n"
RESTORE = {
    # the block deleted without a trace: put back on top, one blank line after it
    "py_deleted": ("handler.py", PY_TOP, PY_BLOCK + PY_CODE),
    "py_blank_first": ("handler.py", "\n\n" + PY_TOP, PY_BLOCK + PY_CODE),
    # the block replaced by a docstring of the worker's own: the block takes its place
    "py_own_docstring": ("handler.py", '"""Demo handlers."""\n' + PY_CODE, PY_BLOCK + PY_CODE),
    "py_comment_then_docstring": (
        "handler.py",
        "# my note\n'''Demo\nhandlers.'''  # trailing\n" + PY_CODE,
        PY_BLOCK + "\n# my note\n" + PY_CODE,
    ),
    # `from __future__` stays the first statement after the docstring
    "py_future": ("handler.py", FUTURE + PY_CODE, PY_BLOCK + "\n" + FUTURE + PY_CODE),
    "py_docstring_future": (
        "handler.py",
        '"""Demo.\n\nMore text.\n"""\n\n' + FUTURE + PY_CODE,
        PY_BLOCK + "\n" + FUTURE + PY_CODE,
    ),
    # code that does not compile still gets its block (the other gates report the code)
    "py_broken": ("handler.py", PY_TOP + "def broken(:\n", PY_BLOCK + PY_CODE + "def broken(:\n"),
    "js_deleted": ("ui.js", JS_CODE, JS_BLOCK + "\n" + JS_CODE),
    "js_own_comment": (
        "ui.js",
        "\n// my page\n\n" + JS_CODE,
        JS_BLOCK + "\n// my page\n\n" + JS_CODE,
    ),
    # a block that left a trace (its first line or the word CONTRACT) is edited or moved:
    # left alone for the gate, which shows the text to restore
    "py_ok": ("handler.py", PY_BLOCK + PY_CODE, None),
    "py_edited": ("handler.py", PY_BLOCK.replace("200", "201") + PY_CODE, None),
    "py_first_line_edited": ("handler.py", PY_BLOCK.replace("one route", "x") + PY_CODE, None),
    "py_only_first_line_left": ("handler.py", '"""demo: one route."""\n' + PY_CODE, None),
    "py_moved_down": ("handler.py", PY_TOP + "\n" + PY_BLOCK, None),
    "py_code_above": ("handler.py", "import re\n" + PY_BLOCK + PY_CODE, None),
    "py_noted": ("handler.py", "# the CONTRACT said so\n" + PY_CODE, None),
    # a string that opens the file but is not a statement of its own
    "py_shared_line": ("handler.py", '"""Demo."""; import re\n' + PY_CODE, None),
    "js_edited": ("ui.js", JS_BLOCK.replace("// render", "// x") + JS_CODE, None),
    "js_extended": ("ui.js", JS_BLOCK + "// my note\n" + JS_CODE, None),
    "js_code_above": ("ui.js", "const x = 1;\n" + JS_BLOCK + JS_CODE, None),
}


def contract_tree(root: Path, files: dict[str, tuple[str, str | None]]) -> dict[str, str]:
    """A tree whose snapshot lists each folder's stub file (folder -> (file name, text; None:
    deleted)); returns folder -> the stub's repo path."""
    paths = {
        folder: f"src/chatbook/features/{folder}/{name}" for folder, (name, _) in files.items()
    }
    snapshot = {
        paths[folder]: (PY_BLOCK if name == "handler.py" else JS_BLOCK).split("\n")[:-1]
        for folder, (name, _) in files.items()
    }
    make_tree(
        root,
        {f"{f}/{name}": text for f, (name, text) in files.items() if text is not None},
        snapshot=False,
    )
    write(root / "tools" / "contracts.json", json.dumps({"files": snapshot}, indent=2))
    return paths


def test_restore_puts_back_only_a_block_deleted_without_a_trace(tmp_path: Path) -> None:
    files: dict[str, tuple[str, str | None]] = {f: (n, t) for f, (n, t, _) in RESTORE.items()}
    extra: dict[str, tuple[str, str | None]] = {
        "py_not_utf8": ("handler.py", None),  # written as bytes below
        "py_file_deleted": ("handler.py", None),
    }
    paths = contract_tree(tmp_path, files | extra)
    feature = tmp_path / "src" / "chatbook" / "features"
    latin1 = b"# caf\xe9\n" + PY_TOP.encode()
    (feature / "py_not_utf8").mkdir()
    (feature / "py_not_utf8" / "handler.py").write_bytes(latin1)
    before = {f: (tmp_path / p).read_bytes() for f, p in paths.items() if f in RESTORE}
    code, out = check(tmp_path, None, "--restore-contracts")
    assert code == 0, out
    restored = [f for f, (_, _, after) in RESTORE.items() if after is not None]
    assert f"restore-contracts: {len(restored)} CONTRACT block(s) restored" in out, out
    for folder, (_, _, after) in RESTORE.items():
        path = paths[folder]
        text = (tmp_path / path).read_bytes().decode("utf-8")
        if after is None:
            assert text.encode() == before[folder], f"{folder} was changed:\n{text}"
            assert f"restored the CONTRACT block at the top of {path}" not in out, out
            assert (f"left {path}: " in out) == (folder != "py_ok"), f"{folder}:\n{out}"
        else:
            assert text == after, f"{folder}:\n{text}"
            assert f"restored the CONTRACT block at the top of {path}" in out, out
            if path.endswith(".py") and folder != "py_broken":
                compile(text, path, "exec", dont_inherit=True)
    assert "py_own_docstring/handler.py in place of the file's own 1-line docstring" in out, out
    assert f"left {paths['py_edited']}: part of its CONTRACT block is still there" in out, out
    assert f"left {paths['py_shared_line']}: the string that opens it is not a" in out, out
    assert (feature / "py_not_utf8" / "handler.py").read_bytes() == latin1
    assert f"left {paths['py_not_utf8']}: not UTF-8 text" in out, out
    assert f"left {paths['py_file_deleted']}: file missing" in out, out
    assert not (feature / "py_file_deleted").exists()  # a deleted file is not made up
    # idempotent: a second run changes nothing
    after_first = {f: (tmp_path / p).read_bytes() for f, p in paths.items() if f in RESTORE}
    code, again = check(tmp_path, None, "--restore-contracts")
    assert code == 0 and "restore-contracts: 0 CONTRACT block(s) restored" in again, again
    assert after_first == {f: (tmp_path / p).read_bytes() for f, p in paths.items() if f in RESTORE}
    # the gate passes every restored file and still reports every file left alone
    code, gate = check(tmp_path)
    assert code == 1, gate
    for folder, (_, _, after) in RESTORE.items():
        reported = re.search(rf"^{re.escape(paths[folder])}:\d+: [^\n]*CONTRACT", gate, re.M)
        assert bool(reported) == (after is None and folder != "py_ok"), f"{folder}:\n{gate}"
    # a file the gate cannot decode is reported, not a crash on its U+FFFD (cp874 console)
    assert f"{paths['py_not_utf8']}:1: CONTRACT block missing" in gate, gate
    assert gate.endswith(" problem(s)\n"), gate


def test_restore_keeps_line_endings_and_byte_order_mark(tmp_path: Path) -> None:
    worker = {"crlf": ("handler.py", PY_TOP), "bom_crlf": ("ui.js", JS_CODE)}
    paths = contract_tree(tmp_path, {f: (n, "x") for f, (n, _) in worker.items()})
    for folder, (_, text) in worker.items():
        bom = "\ufeff" if folder == "bom_crlf" else ""
        (tmp_path / paths[folder]).write_bytes((bom + text.replace("\n", "\r\n")).encode())
    code, out = check(tmp_path, None, "--restore-contracts")
    assert code == 0 and "2 CONTRACT block(s) restored" in out, out
    want = {
        "crlf": (PY_BLOCK + PY_CODE).replace("\n", "\r\n").encode(),
        "bom_crlf": ("\ufeff" + (JS_BLOCK + "\n" + JS_CODE).replace("\n", "\r\n")).encode(),
    }
    assert {f: (tmp_path / p).read_bytes() for f, p in paths.items()} == want
    assert check(tmp_path) == (0, "check_extra: ok\n")


def test_restore_then_ruff_passes_the_gates(tmp_path: Path) -> None:
    """The autofix order of harness/swarm.toml: --restore-contracts, then ruff's fixer and
    formatter, which fix the spacing below the block and never change the block itself."""
    files: dict[str, tuple[str, str | None]] = {
        "starts_with_def": ("handler.py", "def demo() -> int:\n    return 1\n"),
        "own_doc_future": ("handler.py", '"""Mine."""\n' + FUTURE + PY_CODE),
    }
    paths = contract_tree(tmp_path, files)
    write(tmp_path / "pyproject.toml", (REPO / "pyproject.toml").read_text(encoding="utf-8"))
    autofix = [
        ["tools/check_extra.py", "--restore-contracts"],
        ["-m", "ruff", "check", "--fix", "--exit-zero", "--quiet", "src"],
        ["-m", "ruff", "format", "--quiet", "src"],
    ]
    for args in autofix:
        subprocess.run([sys.executable, *args], cwd=str(tmp_path), timeout=120, check=True)
    assert check(tmp_path) == (0, "check_extra: ok\n")
    for args in (["check", "src"], ["format", "--check", "src"]):
        proc = subprocess.run(
            [sys.executable, "-m", "ruff", *args],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
    for path in paths.values():
        assert (tmp_path / path).read_text(encoding="utf-8").startswith(PY_BLOCK + "\n")


def test_restore_without_a_snapshot_or_with_odd_paths_changes_nothing(tmp_path: Path) -> None:
    make_tree(tmp_path, {PY: PY_TOP}, snapshot=False)
    code, out = check(tmp_path, None, "--restore-contracts")
    assert (code, out) == (0, "tools/contracts.json: not found (nothing restored)\n")
    odd = ["tools/check_extra.py", "src/chatbook/features/../../x.py", "src/chatbook/core/api.py"]
    block = PY_BLOCK.split("\n")[:-1]
    write(tmp_path / "tools" / "contracts.json", json.dumps({"files": dict.fromkeys(odd, block)}))
    tool = (tmp_path / "tools" / "check_extra.py").read_bytes()
    code, out = check(tmp_path, None, "--restore-contracts")
    assert code == 0 and out.endswith(RESTORED_0), out
    for path in odd:
        assert f"left {path}: not a features/<name>/handler.py or ui.js path" in out, out
    assert (tmp_path / "tools" / "check_extra.py").read_bytes() == tool
    assert not (tmp_path / "x.py").exists()


def load_tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_extra", REPO / "tools" / "check_extra.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


STALE = (
    "tools/contracts.json does not match the feature files. Staff who changed a CONTRACT "
    "block, added a stub or removed one: run `python tools/check_extra.py --write-contracts` "
    "and review `git diff tools/contracts.json`."
)
UNCOVERED = (
    "feature file(s) {paths} are not in tools/contracts.json. Workers: do not add a new "
    "handler.py or ui.js; delete it and write your code in the stub file your task names. "
    "Staff who added a stub: run `python tools/check_extra.py --write-contracts` and review "
    "`git diff tools/contracts.json`."
)


def test_contract_snapshot_matches_the_feature_files() -> None:
    """tools/contracts.json covers every feature file and is exactly what --write-contracts
    makes from them, so staff cannot forget to regenerate it. A file whose block a worker
    damaged is left to the check_extra gate, which shows the text to restore (one report,
    not two)."""
    tool = load_tool()
    snapshot = tool.load_contracts(REPO)
    features = REPO / "src" / "chatbook" / "features"
    files = [*features.glob("*/handler.py"), *features.glob("*/ui.js")]
    uncovered = sorted(
        p for p in (f.relative_to(REPO).as_posix() for f in files) if p not in snapshot
    )
    damaged = set()
    for path, block in snapshot.items():
        file = REPO / path
        text = file.read_text(encoding="utf-8") if file.is_file() else None
        if tool.check_contract(path, text, block):
            damaged.add(path)
    assert uncovered == [], UNCOVERED.format(paths=", ".join(uncovered))
    current = tool.collect_contracts(REPO)
    paths = (snapshot.keys() | current.keys()) - damaged
    stale = sorted(p for p in paths if snapshot.get(p) != current.get(p))
    assert stale == [], STALE
    text = (REPO / "tools" / "contracts.json").read_text(encoding="utf-8")
    assert text == tool.dump_contracts(snapshot), STALE
