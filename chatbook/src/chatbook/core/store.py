"""The database: a thin wrapper over one sqlite3 connection with plain-dict rows.

The connection is in autocommit mode; the App opens one transaction per request
(_begin/_commit/_rollback). Features never commit.
"""

import functools
import sqlite3
import weakref
from collections.abc import Sequence
from pathlib import Path
from typing import Any

Row = dict[str, Any]


def _dict_row(cursor: sqlite3.Cursor, row: tuple[Any, ...]) -> Row:
    return {col[0]: value for col, value in zip(cursor.description, row, strict=True)}


def _params(args: tuple[object, ...]) -> Sequence[object]:
    """db.one(sql, a, b) == db.one(sql, (a, b)) == db.one(sql, [a, b])."""
    if len(args) == 1 and isinstance(args[0], tuple | list):
        return tuple(args[0])
    return args


class Db:
    """Query helpers. Always use ? placeholders, never build SQL from values."""

    hash_iterations: int

    def __init__(self, conn: sqlite3.Connection, *, hash_iterations: int = 200_000) -> None:
        self._conn = conn
        self.hash_iterations = hash_iterations
        # Closes the connection when the Db is collected (no ResourceWarning on 3.13+).
        self._finalizer = weakref.finalize(self, conn.close)

    def _execute(self, sql: str, args: tuple[object, ...]) -> sqlite3.Cursor:
        return self._conn.execute(sql, _params(args))

    def one(self, sql: str, *args: object) -> Row | None:
        """The first row, or None."""
        return self._execute(sql, args).fetchone()

    def all(self, sql: str, *args: object) -> list[Row]:
        """All rows."""
        return list(self._execute(sql, args).fetchall())

    def value(self, sql: str, *args: object) -> Any:
        """The first column of the first row, or None."""
        cursor = self._conn.cursor()
        cursor.row_factory = None  # plain tuples: duplicate column names cannot collide
        row = cursor.execute(sql, _params(args)).fetchone()
        return None if row is None else row[0]

    def run(self, sql: str, *args: object) -> int:
        """INSERT: the new row id (0 if none); any other statement: the number of rows changed."""
        cursor = self._execute(sql, args)
        if sql.lstrip()[:6].upper() == "INSERT":
            return cursor.lastrowid or 0
        return cursor.rowcount

    def page(self, sql: str, *args: object, limit: int) -> tuple[list[Row], bool]:
        """Up to `limit` rows and whether more exist. Adds LIMIT itself (the SQL has none)."""
        params = [*_params(args), limit + 1]
        rows = list(self._conn.execute(sql + " LIMIT ?", params).fetchall())
        return rows[:limit], len(rows) > limit

    # Frame only: the App wraps every request in one transaction.
    def _begin(self) -> None:
        self._conn.execute("BEGIN IMMEDIATE")

    def _commit(self) -> None:
        if self._conn.in_transaction:
            self._conn.execute("COMMIT")

    def _rollback(self) -> None:
        if self._conn.in_transaction:
            self._conn.execute("ROLLBACK")

    def close(self) -> None:
        self._finalizer()


@functools.cache
def _schema() -> str:
    return Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")


def connect(path: str, *, hash_iterations: int = 200_000) -> Db:
    """Open (and create if needed) the database at `path` (":memory:" for a private one)."""
    conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
    conn.row_factory = _dict_row
    db = Db(conn, hash_iterations=hash_iterations)
    if path not in ("", ":memory:"):
        conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_schema())
    return db
