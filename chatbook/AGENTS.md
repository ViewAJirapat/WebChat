# Rules for ChatBook workers

A harness gives you one task, checks it with gates and hidden tests, and commits it only if
everything passes. The task names the one feature folder you may change.

## Your file
- The feature folder `src/chatbook/features/<name>/` and its stub file already exist. Edit the
  stub. Keep its `@route(...)` lines and function names, or its `CB.page(...)` name, nav and
  order, exactly as they are.
- The file must still begin with its CONTRACT block, unchanged; your code goes below it.
- Implement exactly what the CONTRACT and the task say: routes, JSON keys, status codes, the
  order of checks, list order, texts and labels.
- Keep the file under 120 lines. Add no files unless the task asks.

## Python (handler.py)
- Import only from `chatbook.core.api` (docs/api/*.md), `typing` and `re`. Never import
  another feature, sqlite3, time, datetime or os.
- Database: `request.db.one/all/value/run/page(sql, *args)` with `?` placeholders. The SQL is
  one string literal (adjacent literals are fine); never build it with f-strings, `+`, `%` or
  `.format`. Never commit: the app does it.
- Never write schema SQL (CREATE/ALTER/DROP TABLE, PRAGMA, ATTACH): the schema is the frame's.
- `request.now` is the time (int ms). `request.me` is the logged-in user (already checked).
- Validate input only with body_str, body_id, body_ids, path_id, query_str, query_int,
  query_opt_int. They raise 400/404 themselves.
- Errors: `raise HTTPError(status, "message")`. Success: `return Response(status, {...})`.
- Build users, messages and conversations with user_json, message_json and conversation_json.
- mypy --strict: annotate every function (a helper takes `db: Db` and a row as
  `dict[str, Any]`); use `dict[str, Any]` for JSON dicts; wrap DB values with int(...) or
  str(...) where a typed value is needed. db.one and get_user return `dict | None`: check
  `if row is None: raise HTTPError(404, ...)` before passing the row to a typed helper.

## JavaScript (ui.js)
- Plain JavaScript. Use only `CB.*` (docs/ui.md) and JS built-ins. The gate rejects document,
  window, fetch, innerHTML, setTimeout, setInterval, classList, style, addEventListener,
  import and require.
- Leave a blank line after the CONTRACT comment: a `//` line right below it fails the gate.
- A page is `CB.page(name, {title, nav, order, load, render, poll})`: `load` fetches with
  `CB.api`, `render` returns nodes built with `CB.el` and `CB.form`.
- After a change (send, accept, like) call `CB.refresh()` or `CB.go(...)`.
- `CB.api` shows errors itself: no try/catch.

## Don't
- Don't edit anything outside your feature folder; the harness reverts it.
- No `# type: ignore`, `# noqa`, `# ruff: noqa`, `# mypy: ...`, `# fmt: off`, skip or xfail
  markers. No dependencies. No git commands.
