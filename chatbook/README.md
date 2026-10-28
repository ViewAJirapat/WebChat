# ChatBook

A small Facebook-like chat web app: a single-page browser UI in plain JavaScript talking to a
JSON API written with the Python standard library and sqlite3. The frame (everything outside
the feature folders) is written by staff; each feature in `src/chatbook/features/` is built by
a local LLM worker through the swarm harness.

- Design (single source of truth): `../DESIGN.md`. Progress log: `../PROGRESS.md`.
- Worker rules: `AGENTS.md`. Worker references: `docs/api/*.md` (backend), `docs/ui.md` (pages).
- Harness config and tasks: `../harness/` (`swarm.toml`, `tasks/`).

## Run

Python 3.12+ and Node.js 24 (the UI runner and the JS gate need `node` on PATH).

```
PYTHONPATH=src python -m chatbook           # http://127.0.0.1:8000
PYTHONPATH=src python -m chatbook --demo    # seeds demo users on an empty database
```

Environment: `PORT` (default 8000), `HOST` (default 127.0.0.1), `CHATBOOK_DB` (default
`chatbook.db` in the current directory). Demo logins: `alice`, `bob`, `carol`, `dave`, password
`password1` (local demo only).

## Test

The gates every task must pass, run from this folder (dev tools: pytest, ruff, mypy):

```
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest -q -p no:cacheprovider tests
python tools/check_extra.py
```

Plus the import rules: `swarm -t chatbook archlint` (see `../harness/swarm.toml`).

`check_extra.py` also checks that each feature file still begins with its CONTRACT block, as
recorded in `tools/contracts.json`. Staff who change a stub's CONTRACT block or add a stub
regenerate that file, review its diff and commit it with the stub:

```
python tools/check_extra.py --write-contracts
git diff tools/contracts.json
```

## Layout

- `src/chatbook/app.py`: dispatch, auth, one transaction per request, static files, WSGI.
- `src/chatbook/core/`: storage, users, social and chat rules, routing, validation, and the
  browser runtime (`core/static/cb.js`). `core/api.py` is the only module features import.
- `src/chatbook/features/<name>/`: one feature per folder, `handler.py` (routes) or `ui.js`
  (a page), discovered at startup.
- `src/chatbook/testing.py`: the test kit for hidden tests (`Client`, `run_page`).
- `tools/uirun.js`: headless page runner (real `cb.js`, fake DOM). `tools/check_extra.py`: the
  JS, file-size, SQL and CONTRACT-block gate. `tools/contracts.json`: the CONTRACT block each
  feature file must begin with (generated, see above).
