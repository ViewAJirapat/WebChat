"""Extra gate: JS syntax and banned browser habits, file-size limits, no schema SQL in features.

Run from the repo root:  python tools/check_extra.py [root]
Prints `path:line: problem (fix: hint)` for every problem and exits 1 if there is any.
Standard library only.
"""

from __future__ import annotations

import io
import re
import shutil
import subprocess
import sys
import tokenize
from pathlib import Path

MAX_LINES = 180
SIZE_HINT = "split or simplify: whole-file edits of long files get truncated"
NODE_HINT = "install Node.js 24 and put it on PATH"
SYNTAX_HINT = "fix the JavaScript syntax at that line"
DDL_HINT = "the schema belongs to the frame"
CALL_HINT = "a page calls CB.page(name, {...}); a service calls CB.every(ms, fn)"

_BAN_GROUPS: list[tuple[list[str], str]] = [
    ([r"\bdocument\s*\.", r"\bwindow\s*\.", r"\bglobalThis\b"], "use CB.* only"),
    ([r"\bfetch\s*\(", r"XMLHttpRequest"], "use CB.api"),
    ([r"\.innerHTML\b", r"\.outerHTML\b", r"insertAdjacentHTML"], "build nodes with CB.el"),
    ([r"\beval\s*\(", r"\bnew\s+Function\b"], "not allowed"),
    ([r"\bsetTimeout\s*\(", r"\bsetInterval\s*\("], "use the page's poll or CB.every"),
    ([r"\blocalStorage\b", r"\bsessionStorage\b"], "the frame keeps the session"),
    ([r"\.addEventListener\s*\("], "use the onclick prop or CB.form"),
    ([r"\.classList\b", r"\.style\b", r"\.setAttribute\s*\("], "use CB.el props (class, ...)"),
    ([r"\.querySelector", r"\.getElementById\s*\("], "keep references to the nodes you create"),
    (
        [r"^\s*import\b", r"\bimport\s*\(", r"\brequire\s*\("],
        "no modules: the file is a plain script",
    ),
]
JS_BANS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(pattern), hint) for patterns, hint in _BAN_GROUPS for pattern in patterns
]
DDL_WORD = re.compile(r"\b(CREATE|ALTER|DROP|PRAGMA|ATTACH)\b", re.IGNORECASE)


def _string_token_types() -> set[int]:
    types = {tokenize.STRING}
    for name in ("FSTRING_MIDDLE", "TSTRING_MIDDLE"):
        value = getattr(tokenize, name, None)
        if isinstance(value, int):
            types.add(value)
    return types


STRING_TOKENS = _string_token_types()


def problem(path: str, line: int, text: str, hint: str) -> str:
    return f"{path}:{line}: {text} (fix: {hint})"


def check_js_bans(path: str, text: str) -> list[str]:
    """Banned browser habits in a feature ui.js (comment lines included)."""
    out: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        for pattern, hint in JS_BANS:
            found = pattern.search(line)
            if found:
                used = found.group(0).strip()
                out.append(problem(path, number, f"banned {used!r}", hint))
    if "CB.page(" not in text and "CB.every(" not in text:
        out.append(problem(path, 1, "no CB.page( or CB.every( call", CALL_HINT))
    return out


def check_size(path: str, text: str) -> list[str]:
    """At most MAX_LINES lines per feature file."""
    count = len(text.splitlines())
    if count <= MAX_LINES:
        return []
    message = f"file has {count} lines, the limit is {MAX_LINES}"
    return [problem(path, MAX_LINES + 1, message, SIZE_HINT)]


def check_ddl(path: str, text: str) -> list[str]:
    """No string literal in feature Python code names a schema statement."""
    out: list[str] = []
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, SyntaxError) as exc:
        return [problem(path, 1, f"cannot read the Python tokens: {exc}", "fix the syntax")]
    for token in tokens:
        if token.type not in STRING_TOKENS:
            continue
        for found in DDL_WORD.finditer(token.string):
            line = token.start[0] + token.string.count("\n", 0, found.start())
            word = found.group(0)
            out.append(problem(path, line, f"string literal contains {word!r}", DDL_HINT))
    return out


def _node_error(path: str, stderr: str) -> str:
    lines = stderr.splitlines()
    number = 1
    if lines:
        head = re.search(r":(\d+)\s*$", lines[0])
        if head:
            number = int(head.group(1))
    message = next(
        (s.strip() for s in lines if re.match(r"\s*\w*Error\b", s)),
        lines[-1].strip() if lines else "node --check failed",
    )
    detail = [f"    {s}" for s in lines[1:3] if s.strip()]
    return "\n".join([problem(path, number, message, SYNTAX_HINT), *detail])


def check_node(root: Path, files: list[Path]) -> list[str]:
    """`node --check` on every file; node missing is a problem of its own."""
    if not files:
        return []
    node = shutil.which("node")
    if node is None:
        return ["node: not found (fix: " + NODE_HINT + ")"]
    out: list[str] = []
    for file in files:
        rel = _rel(root, file)
        try:
            done = subprocess.run(
                [node, "--check", str(file)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            out.append(problem(rel, 1, f"node --check did not run: {exc}", NODE_HINT))
            continue
        if done.returncode != 0:
            out.append(_node_error(rel, done.stderr))
    return out


def _rel(root: Path, file: Path) -> str:
    try:
        return file.relative_to(root).as_posix()
    except ValueError:
        return file.as_posix()


def _read(file: Path) -> str:
    return file.read_text(encoding="utf-8", errors="replace")


def run(root: Path) -> list[str]:
    """All problems under the repo root, in a stable order."""
    package = root / "src" / "chatbook"
    if not package.is_dir():
        return [f"{root.as_posix()}: no src/chatbook here (fix: run from the repo root)"]
    features = package / "features"
    js_files = sorted(
        f for base in (package, root / "tools") if base.is_dir() for f in base.rglob("*.js")
    )
    out = check_node(root, [f for f in js_files if f.is_file()])
    if features.is_dir():
        for ui in sorted(features.glob("*/ui.js")):
            out.extend(check_js_bans(_rel(root, ui), _read(ui)))
        for file in sorted(features.rglob("*")):
            if not file.is_file() or file.suffix not in (".py", ".js"):
                continue
            text = _read(file)
            out.extend(check_size(_rel(root, file), text))
            if file.suffix == ".py":
                out.extend(check_ddl(_rel(root, file), text))
    return out


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    root = Path(args[0]) if args else Path.cwd()
    problems = run(root.resolve())
    for line in problems:
        print(line)
    if problems:
        print(f"check_extra: {len(problems)} problem(s)")
        return 1
    print("check_extra: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
