# Rules for ChatBook workers

A harness gives you one task, checks it with gates and hidden tests, and commits it only if
everything passes. The task names the one feature folder you may change.

## Your file
- The feature folder `src/chatbook/features/<name>/` and its stub file already exist. Edit the
  stub. Keep its `@route(...)` lines and function names, or its `CB.page(...)` name, nav and
  order, exactly as they are.
- Keep the CONTRACT block at the top of the file. Implement exactly what it and the task say:
  routes, JSON keys, status codes, the order of checks, list order, texts and labels.
- Keep the file under 120 lines. Add no files unless the task asks.

## Python (handler.py)
- Import only from `chatbook.core.api` (docs/api/*.md), `typing` and `re`. Never import
  another feature, sqlite3, time, datetime or os.
- Database: `request.db.one/all/value/run/page(sql, *args)` with `?` placeholders. Never build
  SQL with f-strings or `+`. Never commit: the app does it.
- `request.now` is the time (int ms). `request.me` is the logged-in user (already checked).
- Validate input only with body_str, body_id, body_ids, path_id, query_str, query_int,
  query_opt_int. They raise 400/404 themselves.
- Errors: `raise HTTPError(status, "message")`. Success: `return Response(status, {...})`.
- Build users, messages and conversations with user_json, message_json and conversation_json.
- mypy --strict: annotate every function; use `dict[str, Any]` for JSON dicts; wrap DB values
  with int(...) or str(...) where a typed value is needed.

## JavaScript (ui.js)
- Plain JavaScript. Use only `CB.*` (docs/ui.md) and JS built-ins. The gate rejects document,
  window, fetch, innerHTML, setTimeout, setInterval, classList, style, addEventListener,
  import and require.
- A page is `CB.page(name, {title, nav, order, load, render, poll})`: `load` fetches with
  `CB.api`, `render` returns nodes built with `CB.el` and `CB.form`.
- After a change (send, accept, like) call `CB.refresh()` or `CB.go(...)`.
- `CB.api` shows errors itself: no try/catch.

## Don't
- Don't edit anything outside your feature folder; the harness reverts it.
- No `# type: ignore`, `# noqa`, skip or xfail markers. No dependencies. No git commands.
