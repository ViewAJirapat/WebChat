===== ? 4880
Report from writer "core"

All my files are written. Ruff, ruff format and `mypy --strict` pass on all of `src` (64 files, stubs included). There are no CR line endings and no non-ASCII bytes. The harness archlint, run with the DESIGN section 4 rules, finds no violations. The package imports, the threaded server answers over real HTTP, and `--demo` seeds an empty file DB. Discovery works on an empty features package.

The frame tests present right now (`tests/test_app.py`, `test_store.py`, `test_validate.py`, `test_registry.py`) give 132 passed, 4 failed. All 4 failures are static-file tests failing only because `core/static/` (cb.js, cb.css, start.js, index.html) is not written yet. That is the UI-runtime writer's part. I could not test `run_page` end to end because `tools/uirun.js` does not exist yet either.

**Files written** (all under `E:/Playground_Projects/05_ChatBook/chatbook`):

| File | Lines |
|---|---|
| `.gitattributes` | 1 |
| `.gitignore` | 8 |
| `pyproject.toml` | 23 |
| `src/chatbook/__init__.py` | 5 |
| `src/chatbook/__main__.py` | 66 |
| `src/chatbook/app.py` | 312 |
| `src/chatbook/testing.py` | 458 |
| `src/chatbook/py.typed` | 0 |
| `src/chatbook/features/__init__.py` | 1 |
| `src/chatbook/core/__init__.py` | 1 |
| `src/chatbook/core/clock.py` | 28 |
| `src/chatbook/core/store.py` | 99 |
| `src/chatbook/core/schema.sql` | 72 |
| `src/chatbook/core/http.py` | 50 |
| `src/chatbook/core/registry.py` | 143 |
| `src/chatbook/core/users.py` | 135 |
| `src/chatbook/core/social.py` | 68 |
| `src/chatbook/core/chat.py` | 222 |
| `src/chatbook/core/validate.py` | 93 |
| `src/chatbook/core/api.py` | 83 |
| `src/chatbook/core/demo.py` | 73 |

**Where DESIGN.md was ambiguous, and what I chose:**
1. **`App` constructor** (not specified): `App(routes=None, db=None, *, clock=None, ui_features=None, raise_errors=False, features_package="chatbook.features")`. Frame routes are always added unless an equal route is already passed. A missing `db` becomes an in-memory one.
2. **Import cycle between users.py and http.py:** users.py needs `HTTPError` and http.py needs `User`, so http.py uses `from __future__ import annotations` and imports `User`/`Db` under `TYPE_CHECKING`. As a result, `typing.get_type_hints(Request)` would fail; `dataclasses.fields(Request)` and `inspect.signature` work.
3. **`Route.public`** defaults to `False`, so 4-argument construction still works. Route marks are `(METHOD, pattern, public)` as specified.
4. **Static files** are read from disk on every request. An unknown static path returns a plain JSON 404 without the CSP headers.
5. **Index page:** the `<script defer ...>` tags are joined with `"\n"`.
6. **Writing the response:** the lock covers parsing and building the whole response. The finished body is returned as a list, so the actual socket write happens outside the lock.
7. **`touch`** runs inside the request transaction, so a request that ends in 4xx or 5xx rolls back `last_seen_at` too. This is the literal reading of steps 5 and 6.
8. **`body_id` / `body_ids`** also reject values above 2**63-1 (with 400), which would otherwise crash sqlite with a 500.
9. **`create_conversation`:** a group needs at least 2 members including the creator; there is no maximum.
10. **`conversation_json`:** `last_message` is the newest message by id, not `last_message_id`. A missing conversation raises 404. The viewer does not have to be a member.
11. **`message_json`:** if the sender's user row is missing, the sender is `{"id", "username": "", "display_name": "Unknown"}`.
12. **`run_page`:**
    - It sends `token: null` when `me` is None, so logged-out runs never call `/api/session` with a token.
    - It has an extra `load_all=False` keyword.
    - Relative `files` paths resolve against the repo root.
13. **`Client.request` response headers:** they are exactly what the WSGI app would send (lower-case names, lookups ignore case).
14. **Demo timestamps** start 2 hours before `now`. `seed()` does not open its own transaction; `__main__.seed_demo()` wraps it.

**For the integrator:**
- **Extra public helpers** not in DESIGN, used by the frame:
  - in `app.py`: `wrap_ui(feature, text)` (the exact IIFE wrapper), `encode_response(resp)`, `FRAME_ROUTES`, `STATIC_DIR` (tests can patch it).
  - in `testing.py`: `run_scenario(scenario)` and the constant `REPO`.
  - in `__main__.py`: `seed_demo(app)`.
- **What the UI writer must provide:**
  - `src/chatbook/core/static/{index.html, cb.js, cb.css, start.js}`, with `<!--FEATURE_SCRIPTS-->` in `index.html`.
  - `tools/uirun.js`, which must accept the stdin keys I send: `cb`, `files`, `me`, `token`, `page`, `params`, `api`, `steps`, `load_all`.
- **Caches left in the repo:** a `.ruff_cache` folder (gitignored) was created by ruff runs. My mypy cache went to the scratchpad. I removed the `__pycache__` folders I created.
- I ran no git commands.

===== ? 4733
Report from writer "stubs": all assigned files are written, and every check I could run passes.

**Checks run**
- ruff check and ruff format --check pass on the 30 `__init__.py` files, the 18 `handler.py` files and `tools/check_extra.py`.
- mypy passes on the features package against the real `chatbook.core.api`. `mypy --strict` passes on `tools/check_extra.py`.
- Every `.py` compiles and every `ui.js` passes `node --check`.
- `tools/check_extra.py` prints `check_extra: ok` on the repo now that all the frame files are present.
- All files are LF, ASCII, end with a newline and have no trailing whitespace.
- Once the other writers' tests appeared I ran them: `tests/test_check_extra.py`, `test_api_doc.py` and `test_route_map.py` pass (13 tests), and the full suite passes (231 in 5.9 s).
- The real `registry.discover()` finds 35 routes, matching the 3.17 route table (method, pattern, public flag, feature) and the stub function names.
- `uirun load_all` (inside `test_route_map`) matches the page table in 1.3.
- The doc signatures match `inspect.signature` of the real core functions.

**Files written** (line counts)
- **Feature `__init__.py`:** 30 files at `E:/Playground_Projects/05_ChatBook/chatbook/src/chatbook/features/<name>/__init__.py`, each a one-line docstring.
- **Backend stubs** (`handler.py`): accounts 29, people 21, friend_requests 34, friend_answers 35, friends 27, dm 22, groups 32, group_members 32, conversations 29, chat_send 29, chat_history 22, updates 20, profiles 36, posts 55, likes 36, comments 40, presence 18, suggestions 20.
- **UI stubs** (`ui.js`): page_login 27, page_inbox 25, page_friends 36, page_people 31, page_discover 27, page_feed 35, page_profile 36, page_chat 34, page_group_new 20, page_group 33, page_post 35, badges 10.
- Every CONTRACT block is 30 lines or fewer; the longest are posts and page_post at exactly 30.
- **Docs and rules:** `E:/Playground_Projects/05_ChatBook/chatbook/AGENTS.md` (38), `docs/ui.md` (82), `docs/api/base.md` (57), `docs/api/social.md` (18), `docs/api/chat.md` (31), `docs/api/posts.md` (13).
- **Gate:** `E:/Playground_Projects/05_ChatBook/chatbook/tools/check_extra.py` (193).

**Where DESIGN.md was ambiguous, and what I chose**
1. **`base.md` heading:** it is verbatim except one line, which now reads `## Database (request.db is a Db), ...`. I added it because the name `Db` appeared nowhere in the base.md text. `test_api_doc` already treats `Db` as documented through its method signatures, so this edit is not required and is safe to revert. `AGENTS.md` and `docs/ui.md` match DESIGN byte for byte.
2. **social, chat and posts docs:** DESIGN only summarises these, so I wrote them. Each exported name starts a line in exactly one file. I kept parentheses off signature lines after the `->`, and wrote no `request.db`, `route`, `Request` or `User` outside base.md.
3. **Docstring wording:** feature docstrings avoid the words create, drop, alter, pragma and attach, because the DDL gate scans docstrings too. So the first lines read "groups: start a group chat and rename it." and "posts: new posts, the feed, one post, delete a post."
4. **Extra CONTRACT lines:** backend CONTRACTs add "Notation: db = request.db, me = request.me.id." (accounts keeps its DESIGN text exactly). Read-only features say "Read-only."
5. **Condensed specs:** some specs needed trimming to fit 30 lines, with the same meaning.
   - updates: the friend-request count is pulled into a `requests = int(db.value(...))` line.
   - conversations: the `reads` query is split into a `rows = db.all(...)` line plus a list comprehension.
   - page_chat: two onsubmit lines are merged.
   - page_chat and page_group: the "Server answers" lines are shortened.
6. **UI stubs:** they follow the template exactly: title, nav and order (plus `public: true` on login) and a "Coming soon" render. `poll` and `load` appear only in the CONTRACT, for the worker to add.
7. **`check_extra.py` behaviour:**
   - It prints `path:line: problem (fix: hint)`, with a line or two of context after `node --check` errors, and exits 1 on any problem.
   - It takes an optional root argument (default: the current directory) and fails if there is no `src/chatbook`.
   - It reports "node missing" only when there are `.js` files to check.
   - The setTimeout hint is the plain text "use the page's poll or CB.every".
   - The DDL check also scans f-string and t-string text tokens.

**For the integrator**
- `src/chatbook/features/__init__.py` is not mine. Another writer created it and it exists.
- My ruff runs may have created `chatbook/.ruff_cache`, and `tests/__pycache__` now exists from a pytest run. Both are gitignored. I did not create or edit any other file and ran no git commands.

