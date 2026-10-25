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


def test_node_missing_fails_with_the_install_hint(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    make_tree(root, {"good/__init__.py": '"""good."""\n', "good/ui.js": GOOD_UI})
    empty = tmp_path / "empty-path"
    empty.mkdir()
    code, out = check(root, env={**os.environ, "PATH": str(empty)})
    assert code == 1, out
    assert "install Node.js 24 and put it on PATH" in out
