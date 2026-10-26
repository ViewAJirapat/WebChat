"""The extra gate (tools/check_extra.py), run on small throwaway trees outside the repo."""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

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


def make_tree(root: Path, features: dict[str, str]) -> None:
    """A minimal repo copy: the tool itself plus src/chatbook/features/<path> files."""
    write(root / "tools" / "check_extra.py", (REPO / "tools" / "check_extra.py").read_text("utf-8"))
    write(root / "src" / "chatbook" / "__init__.py", "")
    write(root / "src" / "chatbook" / "features" / "__init__.py", "")
    for rel, text in features.items():
        write(root / "src" / "chatbook" / "features" / rel, text)


def check(root: Path, env: dict[str, str] | None = None) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "tools/check_extra.py"],
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
