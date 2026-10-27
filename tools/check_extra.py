"""Extra gate: JS syntax and banned browser habits, file-size limits, in feature Python code no
schema SQL and no SQL built at run time (f-strings, +, %, .format), and every feature file
that has a CONTRACT block on the frame still begins with exactly that block.

Run from the repo root:  python tools/check_extra.py [root]
Prints `path:line: problem (fix: hint)` for every problem and exits 1 if there is any.
Standard library only.

The CONTRACT blocks are kept in tools/contracts.json (protected, like all of tools/). Staff
who change a stub's CONTRACT block or add a stub regenerate it from the feature files with
  python tools/check_extra.py --write-contracts [root]
and review `git diff tools/contracts.json` before committing.
"""

from __future__ import annotations

import ast
import io
import json
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
DDL_HINT = (
    "the schema belongs to the frame: no CREATE/ALTER/DROP TABLE, PRAGMA or ATTACH in feature "
    "code; if this text is not SQL, reword it"
)
SQL_HINT = "SQL must be one string literal with ? placeholders; pass the values as arguments"
CALL_HINT = "a page calls CB.page(name, {...}); a service calls CB.every(ms, fn)"
CONTRACTS = "tools/contracts.json"
CONTRACT_HINT = "restore it verbatim at the top of the file, then put your code below it"
EXTENDED_HINT = "leave the CONTRACT block as it is; put a blank line or code before your comments"
REGEN_HINT = "staff: run python tools/check_extra.py --write-contracts on the frame"
CONTRACTS_ABOUT = (
    "The CONTRACT block each feature file must begin with, one string per line. Checked by "
    "tools/check_extra.py; made by `python tools/check_extra.py --write-contracts`. "
    "Do not edit by hand."
)

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
# Schema statements only: "Create a new post" or "could not drop it" are fine.
DDL_SQL = re.compile(
    r"\b(?:CREATE|ALTER|DROP)\s+(?:(?:TEMP|TEMPORARY|UNIQUE|VIRTUAL)\s+)*"
    r"(?:TABLE|INDEX|VIEW|TRIGGER)\b"
    r"|\bPRAGMA\b"
    r"|\b(?:ATTACH|DETACH)\s+DATABASE\b|\bATTACH\s+\S+\s+AS\s+\w",
    re.IGNORECASE,
)
# Text that reads as SQL (a statement or a clause), any case: "cannot delete it" is not.
SQL_SHAPE = re.compile(
    r"\bSELECT\b.*\bFROM\b|\b(?:INSERT|REPLACE)\b.*\bINTO\b|\bUPDATE\b.*\bSET\b"
    r"|\bDELETE\b.*\bFROM\b|\bWHERE\b|\bORDER\s+BY\b|\bVALUES\s*\(",
    re.IGNORECASE | re.DOTALL,
)
DB_METHODS = ("one", "all", "value", "run", "page")


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


def _parse_python(path: str, text: str) -> ast.Module | str:
    try:
        return ast.parse(text)
    except (SyntaxError, ValueError) as exc:
        return problem(path, 1, f"cannot parse the Python file: {exc}", "fix the syntax")


def _docstrings(tree: ast.Module) -> set[int]:
    """ids of the docstring nodes (module, class, function): prose, never SQL."""
    out: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            first = node.body[0] if node.body else None
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                if isinstance(first.value.value, str):
                    out.add(id(first.value))
    return out


def _pieces(node: ast.expr) -> list[str] | None:
    """The literal text of a string built with f-strings, + or %, a value in between counting
    as one space; None if `node` is not such an expression."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.JoinedStr):
        return [v.value if isinstance(v, ast.Constant) else " " for v in node.values]
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
        left, right = _pieces(node.left), _pieces(node.right)
        if left is None and right is None:
            return None
        return (left or [" "]) + (right or [" "])
    return None


def _built(node: ast.AST) -> str | None:
    """The literal text of a string built at run time (f-string, +, %, or .format/.join on a
    literal), else None. A plain literal is not built."""
    if isinstance(node, ast.JoinedStr):
        return "".join(_pieces(node) or [])
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
        parts = _pieces(node)
        if parts is not None and any(p.strip() for p in parts):
            return "".join(parts)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in ("format", "join")
        and isinstance(node.func.value, ast.Constant)
        and isinstance(node.func.value.value, str)
    ):
        inner = [
            c.value
            for arg in node.args
            for c in ast.walk(arg)
            if isinstance(c, ast.Constant) and isinstance(c.value, str)
        ]
        return " ".join([node.func.value.value, *inner])
    return None


def check_ddl(path: str, text: str) -> list[str]:
    """No string in feature Python code names a schema statement (docstrings excepted)."""
    tree = _parse_python(path, text)
    if isinstance(tree, str):
        return [tree]
    skip = _docstrings(tree)
    found: dict[tuple[int, str], None] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in skip:
                continue
            value: str | None = node.value
        else:
            value = _built(node) if isinstance(node, ast.BinOp) else None
        if value is None:
            continue
        for match in DDL_SQL.finditer(value):
            start = getattr(node, "lineno", 1)
            end = getattr(node, "end_lineno", None) or start
            line = min(start + value.count("\n", 0, match.start()), end)
            found[(line, match.group(0).split()[0])] = None
    return [
        problem(path, line, f"string contains schema SQL {word!r}", DDL_HINT)
        for line, word in sorted(found)
    ]


def _sql_ok(node: ast.expr) -> bool:
    """A string literal, a variable, or a choice between them."""
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str)
    if isinstance(node, ast.Name):
        return True
    if isinstance(node, ast.IfExp):
        return _sql_ok(node.body) and _sql_ok(node.orelse)
    return False


def _names(node: ast.expr) -> set[str]:
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, ast.IfExp):
        return _names(node.body) | _names(node.orelse)
    return set()


def _assignments(tree: ast.Module) -> list[tuple[str, ast.expr | None, int]]:
    """(name, value, line) for every assignment; value None when it is not a plain `=`."""
    out: list[tuple[str, ast.expr | None, int]] = []

    def bind(target: ast.expr, value: ast.expr | None, line: int) -> None:
        if isinstance(target, ast.Name):
            out.append((target.id, value, line))
        elif isinstance(target, (ast.Tuple, ast.List)):
            same = isinstance(value, (ast.Tuple, ast.List)) and len(value.elts) == len(target.elts)
            values = value.elts if same and value is not None else [None] * len(target.elts)
            for t, v in zip(target.elts, values, strict=True):
                bind(t, v, line)
        elif isinstance(target, ast.Starred):
            bind(target.value, None, line)

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                bind(target, node.value, node.lineno)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            bind(node.target, node.value, node.lineno)
        elif isinstance(node, ast.NamedExpr):
            bind(node.target, node.value, node.lineno)
        elif isinstance(node, ast.AugAssign):
            bind(node.target, None, node.lineno)
    return out


def check_sql(path: str, text: str) -> list[str]:
    """SQL in feature Python code is one literal with ? placeholders, never built at run time:
    (a) the first argument of .one/.all/.value/.run/.page is a string literal or a variable;
    (b) no f-string, +, % or .format/.join on a literal builds text that reads as SQL;
    (c) a variable passed as that first argument is only ever assigned string literals."""
    tree = _parse_python(path, text)
    if isinstance(tree, str):
        return [tree]
    found: dict[tuple[int, str], None] = {}
    sql_names: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in DB_METHODS
            and node.args
        ):
            first = node.args[0]
            if _sql_ok(first):
                sql_names |= _names(first)
            else:
                message = f"the SQL passed to .{node.func.attr}() is built at run time"
                found[(node.lineno, message)] = None
        built = _built(node)
        if built is not None and SQL_SHAPE.search(built):
            line = getattr(node, "lineno", 1)
            found[(line, "SQL text is built from pieces (f-string, +, % or .format)")] = None
    assignments = _assignments(tree)
    grown = True
    while grown:  # sql = BASE makes BASE an SQL variable too
        grown = False
        for name, value, _ in assignments:
            if name in sql_names and value is not None and _sql_ok(value):
                new = _names(value) - sql_names
                if new:
                    sql_names |= new
                    grown = True
    for name, value, line in assignments:
        if name in sql_names and (value is None or not _sql_ok(value)):
            found[(line, f"the SQL variable {name!r} is assigned a built string")] = None
    return [problem(path, line, message, SQL_HINT) for line, message in sorted(found)]


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


def _normalise(text: str) -> str:
    """Line endings become \\n and a leading byte-order mark goes: the only differences a
    CONTRACT block may have from its snapshot."""
    return text.replace("\r\n", "\n").replace("\r", "\n").removeprefix("\ufeff")


def contract_block(path: str, text: str) -> str | None:
    """The CONTRACT block a feature file begins with, each line ending in \\n, or None.
    handler.py: the docstring that opens line 1 (only its first token is read, so code
    below it may even be broken). ui.js: the leading lines that start with //. Either way
    the block must contain the word CONTRACT."""
    text = _normalise(text)
    lines = text.split("\n")
    count = 0
    if path.endswith(".py"):
        try:
            first = next(tokenize.generate_tokens(io.StringIO(text).readline))
        except (tokenize.TokenError, SyntaxError, StopIteration):
            return None
        if first.type == tokenize.STRING and first.start == (1, 0):
            count = first.end[0]
    else:
        while count < len(lines) and lines[count].startswith("//"):
            count += 1
    block = "".join(line + "\n" for line in lines[:count])
    return block if "CONTRACT" in block else None


def check_contract(path: str, text: str | None, block: str) -> list[str]:
    """The file begins with exactly `block` (line endings and a byte-order mark aside). In a
    .js file the next line must not be another // line: the leading comment block is the
    CONTRACT block and nothing more. `text` is None when the file is missing."""
    body = "" if text is None else _normalise(text)
    if body.startswith(block):
        if path.endswith(".js") and body[len(block) :].startswith("//"):
            line = block.count("\n") + 1
            message = "a // comment line right after the CONTRACT block extends it"
            return [problem(path, line, message, EXTENDED_HINT)]
        return []
    moved = body.find("\n" + block)
    if moved >= 0:
        line = body.count("\n", 0, moved + 1) + 1
        message = f"CONTRACT block moved below other code (it starts at line {line})"
        return [problem(path, 1, message, CONTRACT_HINT)]
    want = block.split("\n")[:-1]
    have = body.split("\n")
    last = len(want) - 1  # all lines equal: the file ends right after the block's last line
    first = next((i for i, w in enumerate(want) if i >= len(have) or have[i] != w), last)
    differs = first < len(have) and have[first] != want[first]
    found = repr(have[first]) if differs else "missing (the file ends there)"
    message = "file missing" if text is None else "CONTRACT block missing or changed"
    lines = [
        problem(path, first + 1, message, CONTRACT_HINT),
        f"    line {first + 1} must be {want[first]!r} but is {found}",
        f"    the file must begin with these {len(want)} lines, exactly as shown:",
        f"==== CONTRACT block of {path} ====",
        *want,
        "==== end of the CONTRACT block: your code goes below it ====",
    ]
    return ["\n".join(lines)]


def load_contracts(root: Path) -> dict[str, str]:
    """path -> CONTRACT block, from tools/contracts.json; ValueError when it is unusable."""
    file = root / CONTRACTS
    if not file.is_file():
        raise ValueError("not found")
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot read it: {exc}") from exc
    files = data.get("files") if isinstance(data, dict) else None
    if not isinstance(files, dict) or not all(
        isinstance(lines, list) and lines and all(isinstance(s, str) for s in lines)
        for lines in files.values()
    ):
        raise ValueError('expected {"files": {"<path>": ["<line>", ...]}}')
    return {path: "".join(s + "\n" for s in lines) for path, lines in files.items()}


def dump_contracts(blocks: dict[str, str]) -> str:
    """The text of tools/contracts.json for these blocks (stable, ASCII, one line per item)."""
    files = {path: blocks[path].split("\n")[:-1] for path in sorted(blocks)}
    return json.dumps({"about": CONTRACTS_ABOUT, "files": files}, indent=2) + "\n"


def collect_contracts(root: Path) -> dict[str, str]:
    """path -> CONTRACT block of every features/*/handler.py and features/*/ui.js that
    begins with one."""
    features = root / "src" / "chatbook" / "features"
    out: dict[str, str] = {}
    for file in [*features.glob("*/handler.py"), *features.glob("*/ui.js")]:
        rel = _rel(root, file)
        block = contract_block(rel, _read(file))
        if block is not None:
            out[rel] = block
    return dict(sorted(out.items()))


def check_contracts(root: Path) -> list[str]:
    """Every file listed in tools/contracts.json begins with its CONTRACT block."""
    try:
        blocks = load_contracts(root)
    except ValueError as exc:
        return [f"{CONTRACTS}: {exc} (fix: {REGEN_HINT})"]
    out: list[str] = []
    for path, block in sorted(blocks.items()):
        file = root / path
        out.extend(check_contract(path, _read(file) if file.is_file() else None, block))
    return out


def write_contracts(root: Path) -> str:
    """Staff only: regenerate tools/contracts.json from the feature files; returns a report
    of what changed (review it: a damaged block must be restored, not recorded)."""
    try:
        old = load_contracts(root)
    except ValueError:
        old = {}
    new = collect_contracts(root)
    (root / CONTRACTS).write_text(dump_contracts(new), encoding="utf-8", newline="\n")
    changed = {p for p in new.keys() & old.keys() if new[p] != old[p]}
    report = [f"wrote {CONTRACTS}: {len(new)} CONTRACT block(s)"]
    report += [f"  added    {p}" for p in sorted(new.keys() - old.keys())]
    report += [f"  changed  {p}" for p in sorted(changed)]
    report += [f"  REMOVED  {p}" for p in sorted(old.keys() - new.keys())]
    return "\n".join(report)


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
                out.extend(check_sql(_rel(root, file), text))
    out.extend(check_contracts(root))  # last: feedback keeps the tail of long output
    return out


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    write = args[:1] == ["--write-contracts"]
    args = args[1:] if write else args
    root = Path(args[0]) if args else Path.cwd()
    if write:
        if not (root / "src" / "chatbook" / "features").is_dir():
            print(f"{root.as_posix()}: no src/chatbook/features here (fix: run from the repo root)")
            return 1
        print(write_contracts(root.resolve()))
        return 0
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
