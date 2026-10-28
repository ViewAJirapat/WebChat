# ChatBook: final blueprint (DESIGN.md)

This file is the single source of truth for the staff who (1) write the frame and (2) write each
task. Where it gives code, names or strings, use them exactly. Where it says "staff detail", the
staff choose the implementation, but the stated behaviour still holds.

- Product repo: `E:/Playground_Projects/05_ChatBook/chatbook` (new git repo, package `chatbook`).
- Oracle clone: `E:/Playground_Projects/05_ChatBook/chatbook-oracle` (a throwaway clone of the
  product repo, used only by `swarm validate` and dry-run integrations).
- Harness config and tasks: `E:/Playground_Projects/05_ChatBook/harness/` (`swarm.toml`,
  `tasks/<id>/`, `.worktrees/`, `runs/`).
- The harness repo `E:/Playground_Projects/04_AgentSwarm` is never modified. Every command is
  `uv run --project E:/Playground_Projects/04_AgentSwarm swarm -c E:/Playground_Projects/05_ChatBook/harness/swarm.toml -t <target> <cmd>`
  (written `swarm -t <target> <cmd>` below).
- Owner's ground rule (PROGRESS.md): the frame, hidden tests and reference patches are staff work;
  **feature code comes only from the local LLM through the harness**.

---

## 0. Decisions: where this design comes from

The base is the **feasibility** design (best scored by all three judges): core-owned users,
sessions and schema; cross-feature domain helpers in the frame; validators that raise their own
errors; an injectable clock; `features/<name>/ui.js` page discovery; a test `Client`; staff
stubs for every feature. Grafts and fixes:

| # | Change | Source | Why |
|---|---|---|---|
| 1 | `validate` and dry-run `integrate` run only on a **separate target `chatbook-oracle`** pointing at a throwaway clone. The real target integrates **explicit worker branch lists** only. | parallel; all judges (fatal flaw) | Run ids are `<task>--<engine>--<stamp>` and `integrate` keeps the last one in sorted order, so `oracle` beats `local-14b-arch` and would ship the staff patch. Verified in `swarm/runner.py:new_run_id` and `swarm/dispatch.py:integrate`. |
| 2 | Each stub carries a **CONTRACT block** (docstring or comment) with routes, check order, status codes and JSON keys. | worker-fit, harness judges | In Aider 0.86.2 architect mode the editor pass gets only the architect's plan plus the files (`architect_coder.py`: `editor_coder.run(with_message=content)` with empty history). `prompt.md` never reaches the editor. |
| 3 | **Declarative pages**: `CB.page(name, {load, render, poll})`; the frame re-runs load and render on `poll` and on `CB.refresh()`, and keeps typed field text across re-renders. | product; worker-fit | Removes hand-written async state (dedupe, lastId, "load older" bookkeeping). The chat page drops from ~95-130 to ~65 lines. |
| 4 | The **headless UI runner executes the real `cb.js`** against a small fake DOM; banned DOM habits are caught by a lint gate with fix hints. | product (fidelity); worker-fit (loud errors) | One engine for browser and tests; failures are specific (`file:line` + hint), never silent no-ops. |
| 5 | Every served `ui.js` is wrapped in `(() => { 'use strict'; ... })();`, in the browser and in the runner. A frame test loads all ui.js files into one context. | product; harness, product judges (fatal flaw) | Top-level names in two pages can no longer collide. |
| 6 | `.gitattributes` `* text=auto eol=lf` is the first file committed in both repos; patches written with `git diff --output=`. | parallel, product; harness judge (fatal flaw) | This PC has `core.autocrlf=true` (system gitconfig); CRLF worktrees break `git apply` of stub-modifying patches. |
| 7 | Frame built-ins `GET /api/health`, `GET /api/session`, `DELETE /api/session`; `python -m chatbook --demo` seed. | product | The shell resolves "me" and logs out before any worker task lands; fast browser smoke tests. |
| 8 | `Db` methods accept a single tuple or list of params as well as varargs. | product; worker-fit judge | qwen writes `db.one(sql, (rid,))` out of sqlite3 habit. |
| 9 | Threaded server (`ThreadingMixIn`, daemon threads, 30 s socket timeout) **plus one global lock around each request's dispatch** (the body is read before the lock is taken). | product + harness judge; frame review | Chrome preconnect sockets and clients that stall mid-body cannot stall the server, and the single sqlite connection and per-request transaction stay serial. |
| 10 | A UNIQUE / PRIMARY KEY `sqlite3.IntegrityError` maps to 409 with rollback; other constraint failures (NOT NULL, CHECK) are unexpected errors (500, or raised under `raise_errors`). `tests/test_api_doc.py` checks the worker docs against `inspect.signature`. `tests/test_route_map.py` asserts the exact route and page tables. | parallel; harness judge; frame review | Safety net for races without hiding handler bugs from workers, no drift between docs and code, decorator edits caught by the gate. |
| 11 | Worker docs split by domain (`docs/api/base.md` + one domain file per task; `docs/ui.md` for pages). | worker-fit judge | Aider sends `--read` files to both the architect and the editor call: keep AGENTS.md + references under ~2k tokens. |
| 12 | Full demo protected list restored (`ruff.toml`, `.ruff.toml`, `setup.cfg`, `pytest.ini`, `mypy.ini`, ...), plus `package.json`. | harness judge | No-slash patterns protect any path component; a nested `ruff.toml` inside a feature folder would otherwise be in scope. |
| 13 | Only ASCII in every string a hidden test asserts (`'...'` not an ellipsis; no emoji). `CB.short(text, n)` does truncation in the frame. | worker-fit judge | The architect plan normalises characters; the editor copies the plan. |
| 14 | MVP first: W1-W3 (22 tasks) give a usable chat; feed, presence, suggestions are a stretch phase (W4-W5). `/api/updates` slimmed to what the badges use. Calibration wave W1 includes one UI task. | product judge; parallel | Protect the critical path; no task spends effort on unused semantics. |
| 15 | **Profiles become worker tasks** (API + page); the style example lives in `docs/` instead of a staff-written feature. | owner's ground rule | Feature code only from the local LLM. |
| 16 | mypy `python_version = "3.12"`, `warn_return_any = false`; JSON builders return `dict[str, Any]`. | harness judge; own check | Gates run on Python 3.14; `dict[str, object]` values cannot be compared or sorted under mypy. |
| 17 | Hidden-test fixtures use values that differ from the prompt examples; acceptance file names are unique (`test_cbNN_<name>.py`). | product | Discourages hard-coding under `acceptance_feedback = "full"`. |
| 18 | The UI runner reads its scenario from stdin; test helpers never write into the worktree. Helper classes are not named `Test*`. | harness judge | Files written in the worktree would be reverted by the guard and pollute feedback. |
| 19 | Friends-only DMs and group adds, consistent in every UI entry point ("Message" shown only for friends). | feasibility; product judge | No dead-end 403s in the UI. |
| 20 | Fallback engines limited to what is installed: `qwen2.5-coder:14b`, `:7b` (16k context). `qwen3-coder:30b` is **not pulled** on this PC (18 GB; ask the owner before downloading; 16 GB RAM makes it doubtful). The `claude` CLI is signed out. | own check (`ollama list`) | The fallback ladder must be real. |
| 21 | **CONTRACT-preservation gate**: `tools/check_extra.py` fails any feature file that no longer begins with its CONTRACT block exactly as the frame has it (line endings aside), and prints the block to restore. The blocks live in a protected snapshot `tools/contracts.json`, generated from the stubs with `check_extra.py --write-contracts` (3.16 item 6). An autofix step, `check_extra.py --restore-contracts`, puts back a block deleted without a trace, since the printed block can be clipped when another stage also fails (section 4). | Wave 1 review (`wf_f84d1397-1dc`); its verifier | The cb-05 (friends) worker deleted its CONTRACT docstring; behaviour was right and every hidden test passed, so no gate caught it. The editor pass sees only the CONTRACT (row 2), so a retry on that file would run blind, and the in-repo spec is lost for later tasks and reviews. |

---

## 1. Product overview and UI flows

ChatBook is a small Facebook-like web app: a single-page browser UI (plain JavaScript) talking to
a JSON API (Python standard library, sqlite3). The browser polls for new data; there is no
websocket.

### 1.1 What a user can do (MVP = waves 1-3)

1. **Register / log in** on the public `login` page. After login the app opens **Chats**.
2. **Find people**: the People page, or the search box in the top bar (Enter opens
   `people` with `q`). Each result shows a relationship button: Add friend / Requested (disabled) /
   Respond / Message.
3. **Friend requests**: the Friends page lists incoming requests (Accept, Decline), sent requests
   (Cancel) and friends (Message, Unfriend). Sending a request to someone who already asked you
   makes you friends immediately.
4. **Profiles**: click any name to open `profile`. Own profile: edit display name and bio. Other
   profiles: Add friend / Cancel request / Accept / Message + Unfriend, by relationship.
5. **1:1 chat** with a friend ("Message" anywhere opens or creates the direct conversation).
6. **Group chat**: Chats > "New group" (name + friend checkboxes). In a group chat, "Group
   settings" opens rename, members, add a friend, leave.
7. **Chat page**: history (newest 50, "Show older" adds 50), composer, polling every 2 s, marks
   the conversation read when it has unread messages, shows "Seen" when another member has read
   your last message.
8. **Unread state**: the Chats list shows unread counts per conversation; the top bar shows badges
   (Chats: unread messages, Friends: pending requests) refreshed every 5 s, and the tab title gets
   an `(n) ` prefix.

### 1.2 Stretch (waves 4-5)

Feed (posts by you and your friends, like/unlike, comments, delete own post), single post page with
comments, Discover page (friends online in the last 60 s; people you may know by mutual friends).

### 1.3 Page map

| Page | Title | Nav label (order) | Opened from | Feature folder |
|---|---|---|---|---|
| `login` | Welcome | - (public) | logged-out start, logout | `page_login` |
| `inbox` | Chats | Chats (10) | home after login | `page_inbox` |
| `friends` | Friends | Friends (20) | nav, "Respond" | `page_friends` |
| `people` | People | People (30) | nav, top-bar search | `page_people` |
| `discover` | Discover | Discover (35) | nav (stretch) | `page_discover` |
| `feed` | Feed | Feed (40) | nav (stretch) | `page_feed` |
| `profile` | Profile | Profile (50) | nav (own), any name link (`{id}`) | `page_profile` |
| `chat` | Chat | - | inbox item, Message buttons (`{id, limit?}`) | `page_chat` |
| `group_new` | New group | - | inbox "New group" | `page_group_new` |
| `group` | Group settings | - | chat "Group settings" (`{id}`) | `page_group` |
| `post` | Post | - | feed "Comments (n)" (`{id}`) | `page_post` |
| (service) | - | - | runs every 5 s while logged in | `badges` |

URL form: `#/<page>?<k>=<v>&...` (e.g. `#/chat?id=3`). Page params are always strings.

### 1.4 Look

Facebook-like (frame CSS): blue top bar `#1877f2` with the "chatbook" logo, search box, nav links
with red badges, the user's name (opens own profile) and "Log out"; light grey page background
`#f0f2f5`; white rounded cards; chat bubbles (`.msg`, own messages `.msg.mine` right-aligned and
blue); responsive down to 360 px width.

---

## 2. Repository layout (`chatbook/`)

```
chatbook/
  .gitattributes            * text=auto eol=lf        (first commit)
  .gitignore                __pycache__/ .mypy_cache/ .ruff_cache/ .pytest_cache/ *.db *.db-wal *.db-shm .aider*
  AGENTS.md                 worker rules (section 5)
  README.md                 how to run, test, and where the design lives
  pyproject.toml
  docs/
    api/base.md             backend reference: routing, Request, Db, validation, users, example
    api/social.md           friendships and requests
    api/chat.md             conversations and messages
    api/posts.md            posts, likes, comments
    ui.md                   the CB browser toolkit
  tools/
    check_extra.py          JS syntax + bans, file-size limits, no schema SQL and only
                            constant SQL (no f-string/+/%/.format) in feature Python,
                            every feature file still begins with its CONTRACT block;
                            --restore-contracts (autofix) puts a deleted block back
    contracts.json          the CONTRACT block of each feature file (generated: 3.16 item 6)
    uirun.js                headless page runner (real cb.js + fake DOM), scenario on stdin
  tests/                    frame tests (protected; run as a gate on every task)
    fixtures/sample_page.js
    test_*.py
  src/chatbook/
    __init__.py             exports App, create_app
    __main__.py             python -m chatbook [--demo]
    app.py                  dispatch, auth, transactions, static/UI serving, WSGI
    testing.py              Client, run_page, UI fixtures (used by every hidden test)
    py.typed
    core/
      __init__.py
      api.py                the public contract: the only chatbook module features import
      http.py               Request, Response, HTTPError
      registry.py           route discovery, ui.js discovery
      store.py              Db wrapper, connect()
      schema.sql            the whole schema (frame-owned)
      clock.py              SystemClock, FakeClock
      validate.py           body_*/path_id/query_* helpers
      users.py              users, passwords, sessions
      social.py             friendship rules, visible_post
      chat.py               conversations, members, messages, JSON builders
      demo.py               --demo seed
      static/index.html     shell template
      static/cb.js          the CB toolkit + router (browser and runner)
      static/start.js       calls CB.start()
      static/cb.css
    features/
      __init__.py
      <30 feature folders, each scaffolded by the staff with a stub> (section 3.17)
```

`pyproject.toml`:

```toml
[project]
name = "chatbook"
version = "0.1.0"
description = "A Facebook-like chat app built by local LLM workers through the swarm harness."
requires-python = ">=3.12"
dependencies = []

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]

[tool.mypy]
strict = true
mypy_path = "src"
python_version = "3.12"
warn_return_any = false
```

Do not add `filterwarnings = error` (hidden tests run with this pyproject via `-c`).

---

## 3. The frame

The frame is everything except the bodies of the 30 feature stubs. Staff write it, prove it
(frame tests green, every task validated), commit it on `main`, and it is then protected.
Target size: ~4.5k lines including tests, stubs, CSS and JS.

### 3.1 Conventions every module follows

- **Ids** are integers from `AUTOINCREMENT` (1, 2, 3 ... on a fresh DB). **Time** is integer
  milliseconds since the epoch, from `request.now` (never `time` in features).
- **Status codes**: 200 OK, 201 created, 400 validation, 401 not logged in (frame only),
  403 forbidden, 404 not found / not a member / not visible (existence is not leaked),
  405 wrong method (frame), 409 conflict, 413 body too large (frame), 500 internal (frame).
- **Errors** are always `{"error": "<message>"}`. Hidden tests check status codes and the exact
  success JSON, never error message text.
- **Shared JSON shapes** (built only by frame helpers, so all features agree):

| Name | Shape | Built by |
|---|---|---|
| U | `{"id", "username", "display_name"}` | `user_json` |
| M | `{"id", "conversation_id", "sender": U, "body", "created_at"}` | `message_json`, `post_message` |
| C | `{"id", "kind": "direct"|"group", "title", "members": [U sorted by id], "last_message": M|null, "unread": int, "updated_at": int}` | `conversation_json` |
| R | `{"id", "from": U, "to": U, "created_at"}` | friend_requests feature (spec) |
| P | `{"id", "username", "display_name", "bio", "joined_at", "relationship", "friend_count", "request_id": int|null}` | profiles feature (spec) |
| Post | `{"id", "author": U, "body", "created_at", "like_count", "comment_count", "liked": bool}` | posts feature (spec) |
| K | `{"id", "post_id", "author": U, "body", "created_at"}` | comments feature (spec) |

- `title` of a direct conversation = the other member's `display_name` ("Unknown" if none);
  of a group = the stored title. `updated_at` = the last message's `created_at`, else the
  conversation's `created_at`.
- Lists are wrapped in objects (`{"users": [...]}`). Ordering is always fully specified, ties
  broken by id.

### 3.2 `core/clock.py`

```python
class Clock(Protocol):
    def now_ms(self) -> int: ...

class SystemClock:            # int(time.time() * 1000)
    def now_ms(self) -> int: ...

class FakeClock:
    def __init__(self, start_ms: int = 1_700_000_000_000) -> None: ...
    def now_ms(self) -> int: ...          # fixed until advance()
    def advance(self, ms: int) -> None: ...
```

### 3.3 `core/store.py` and `core/schema.sql`

```python
Row = dict[str, Any]

class Db:
    hash_iterations: int        # set by create_app (200_000 production, 1 in Client)
    def one(self, sql: str, *args: object) -> Row | None
    def all(self, sql: str, *args: object) -> list[Row]
    def value(self, sql: str, *args: object) -> Any          # first column of first row, or None
    def run(self, sql: str, *args: object) -> int            # INSERT...: lastrowid; else rowcount
    def page(self, sql: str, *args: object, limit: int) -> tuple[list[Row], bool]
    # frame only (underscored, not in docs): _begin(), _commit(), _rollback(), close()

def connect(path: str, *, hash_iterations: int = 200_000) -> Db
```

- Params: `db.one(sql, a, b)` and `db.one(sql, (a, b))` / `db.one(sql, [a, b])` are equivalent:
  if exactly one arg is a tuple or list it is the parameter sequence.
- `run`: if the statement starts with `INSERT` (case-insensitive, after whitespace) it returns
  `cursor.lastrowid` (0 if None), otherwise `cursor.rowcount`. Docs note that after an ignored
  `INSERT OR IGNORE` the value is meaningless.
- `page`: executes `sql + " LIMIT ?"` with `limit + 1`; returns `(rows[:limit], len(rows) > limit)`.
  The SQL must not contain LIMIT.
- Rows are plain dicts (row factory). Connection: `sqlite3.connect(path, isolation_level=None,
  check_same_thread=False)` (autocommit; the App issues `BEGIN IMMEDIATE`/`COMMIT`/`ROLLBACK`).
  File databases use `PRAGMA journal_mode=WAL`. `connect` runs `schema.sql` (all
  `CREATE ... IF NOT EXISTS`). Close through `weakref.finalize` so Python 3.13+ prints no
  `ResourceWarning` into worker feedback.
- No foreign-key constraints (features delete dependent rows themselves; spec says when).

`schema.sql` (complete, frozen; a later change is a staff frame commit between waves):

```sql
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL,
  bio TEXT NOT NULL DEFAULT '',
  password_hash TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  last_seen_at INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,          -- sha256 hex of the bearer token
  user_id INTEGER NOT NULL,
  created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS friend_requests (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  from_id INTEGER NOT NULL,
  to_id INTEGER NOT NULL,
  created_at INTEGER NOT NULL,
  UNIQUE (from_id, to_id)
);
CREATE TABLE IF NOT EXISTS friendships (   -- one row per direction
  user_id INTEGER NOT NULL,
  friend_id INTEGER NOT NULL,
  created_at INTEGER NOT NULL,
  PRIMARY KEY (user_id, friend_id)
);
CREATE TABLE IF NOT EXISTS conversations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL CHECK (kind IN ('direct', 'group')),
  title TEXT NOT NULL DEFAULT '',
  direct_key TEXT UNIQUE,                -- 'minid:maxid' for direct, NULL for group
  created_by INTEGER NOT NULL,
  created_at INTEGER NOT NULL,
  last_message_id INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS members (
  conversation_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  joined_at INTEGER NOT NULL,
  last_read_id INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (conversation_id, user_id)
);
CREATE INDEX IF NOT EXISTS members_user ON members (user_id);
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  conversation_id INTEGER NOT NULL,
  sender_id INTEGER NOT NULL,
  body TEXT NOT NULL,
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS messages_conv ON messages (conversation_id, id);
CREATE TABLE IF NOT EXISTS posts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  author_id INTEGER NOT NULL,
  body TEXT NOT NULL,
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS posts_author ON posts (author_id, id);
CREATE TABLE IF NOT EXISTS likes (
  post_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  created_at INTEGER NOT NULL,
  PRIMARY KEY (post_id, user_id)
);
CREATE TABLE IF NOT EXISTS comments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  post_id INTEGER NOT NULL,
  author_id INTEGER NOT NULL,
  body TEXT NOT NULL,
  created_at INTEGER NOT NULL
);
```

Table ownership (stated again in each task prompt; `testing.py` and `demo.py` may write anything):

| Table | Written by |
|---|---|
| users, sessions | core helpers only; `profiles` updates `display_name`, `bio` |
| friend_requests | `friend_requests` inserts; `friend_answers` deletes; `core.befriend` deletes |
| friendships | core only (`befriend`, `unfriend`) |
| conversations, members, messages | core helpers; `groups` updates `title` |
| posts, likes, comments | `posts` (insert/delete posts, delete their likes and comments), `likes`, `comments` |

Any feature may read any table.

### 3.4 `core/users.py`

```python
@dataclass(frozen=True)
class User:
    id: int
    username: str
    display_name: str

def user_json(u: User | Mapping[str, Any]) -> dict[str, Any]        # U
def get_user(db: Db, user_id: int) -> Row | None                    # full users row
def require_user(db: Db, user_id: int) -> Row                       # 404 "user not found"
def create_user(db: Db, username: str, password: str, display_name: str, now: int) -> User
    # stores username exactly as given (the accounts feature lower-cases it);
    # existing username -> HTTPError(409, "username taken"); hash with db.hash_iterations
def check_password(db: Db, username: str, password: str) -> User | None
    # exact username match; verify with hmac.compare_digest; a dummy hash runs for unknown users
def new_session(db: Db, user_id: int, now: int) -> str              # secrets.token_urlsafe(32)
# frame only (not exported by api.py):
def end_session(db: Db, token: str | None) -> None
def user_for_token(db: Db, token: str | None) -> User | None
def touch(db: Db, user_id: int, now: int) -> None                   # last_seen_at = now
def hash_password(password: str, iterations: int) -> str
    # 'pbkdf2_sha256$<iterations>$<salt hex>$<hash hex>', salt = secrets.token_bytes(16)
def verify_password(password: str, stored: str) -> bool             # iterations read from stored
```

### 3.5 `core/social.py`

```python
def are_friends(db: Db, a: int, b: int) -> bool
def befriend(db: Db, a: int, b: int, now: int) -> None
    # INSERT OR IGNORE both directions; DELETE friend_requests between a and b in either direction
def unfriend(db: Db, a: int, b: int) -> None                        # delete both directions
def relationship(db: Db, me: int, other: int) -> str
    # 'self' if me == other; 'friends'; 'request_sent' (row me->other); 'request_received'
    # (row other->me); else 'none'
def friend_ids(db: Db, user_id: int) -> list[int]                   # ascending
def visible_post(db: Db, post_id: int, viewer_id: int) -> Row
    # the posts row; 404 "post not found" unless the author is the viewer or a friend of the viewer
```

### 3.6 `core/chat.py`

```python
def create_conversation(db: Db, kind: str, title: str, creator_id: int,
                        member_ids: list[int], now: int) -> int
    # members = creator + member_ids (deduplicated, creator not repeated), last_read_id 0;
    # kind 'direct' requires exactly 2 members and sets direct_key 'min:max' and title '';
    # a bad kind or member count raises ValueError (programming error, not a 4xx)
def find_direct(db: Db, a: int, b: int) -> int | None
def require_member(db: Db, conversation_id: int, user_id: int) -> Row
    # the conversations row; 404 "conversation not found" if missing or the user is not a member
def member_ids(db: Db, conversation_id: int) -> list[int]          # ascending
def add_member(db: Db, conversation_id: int, user_id: int, now: int) -> None
    # INSERT OR IGNORE; last_read_id = the conversation's last_message_id (no old unread)
def remove_member(db: Db, conversation_id: int, user_id: int) -> None
def post_message(db: Db, conversation_id: int, sender_id: int, body: str, now: int) -> dict[str, Any]
    # inserts; sets conversations.last_message_id and the sender's last_read_id; returns M
def message_json(db: Db, row: Mapping[str, Any]) -> dict[str, Any]          # M from a messages row
def mark_read(db: Db, conversation_id: int, user_id: int) -> int
    # last_read_id = max(last_read_id, last_message_id); returns the new value
def unread_count(db: Db, conversation_id: int, user_id: int) -> int
    # messages with id > the user's last_read_id and sender_id != user; 0 if not a member
def conversation_json(db: Db, conversation_id: int, viewer_id: int) -> dict[str, Any]   # C
```

### 3.7 `core/validate.py`

All raise `HTTPError` themselves. Messages are fixed (not tested, but keep them).

| Function | Accepts | Error |
|---|---|---|
| `body_str(request, name, *, min_len=1, max_len=1000, strip=True) -> str` | body is a dict and `body[name]` is a str that encodes as UTF-8 (a lone surrogate such as `"\ud800"` does not; sqlite could not store it) and whose length after the optional `strip()` is within `min_len..max_len` | 400 `request body must be a JSON object` / `<name> must be a string` / `<name> must be <min>-<max> characters` |
| `body_id(request, name) -> int` | an `int`, not `bool`, `> 0` | 400 `<name> must be a positive integer` (also for a non-dict body: `request body must be a JSON object`) |
| `body_ids(request, name, *, max_items=100) -> list[int]` | a list of at most `max_items` ints (not bool) `> 0`; duplicates removed, first-seen order kept | 400 `<name> must be a list of positive integers` |
| `path_id(request, name="id") -> int` | `request.params[name]` is 1-18 ASCII digits and `> 0` | 404 `not found` |
| `query_str(request, name, *, max_len, min_len=1) -> str` | `request.query.get(name, "").strip()` has length within range | 400 `<name> must be <min>-<max> characters` |
| `query_int(request, name, *, default, lo, hi) -> int` | missing/empty -> `default`; else matches `-?[0-9]{1,18}` and `lo <= n <= hi` | 400 `<name> must be an integer between <lo> and <hi>` |
| `query_opt_int(request, name) -> int \| None` | missing/empty -> None; else matches `[0-9]{1,18}` | 400 `<name> must be a non-negative integer` |

The query dict comes from `parse_qsl` (blank values dropped, so `?q=` counts as missing; for a
repeated key the last value wins).

### 3.8 `core/http.py`

```python
@dataclass(frozen=True)
class Request:
    method: str
    path: str
    params: dict[str, str]          # {name} path segments
    query: dict[str, str]
    body: object                    # parsed JSON or None
    headers: dict[str, str]         # lower-case names
    user: User | None               # resolved by the App from the bearer token
    token: str | None
    db: Db
    now: int                        # ms, from the App's clock, fixed for the request
    @property
    def me(self) -> User: ...       # HTTPError(401, "login required") if user is None

JSON_TYPE = "application/json; charset=utf-8"

@dataclass(frozen=True)
class Response:
    status: int
    body: object = None             # JSON-serializable (features); bytes for frame static files
    content_type: str = JSON_TYPE
    headers: tuple[tuple[str, str], ...] = ()

class HTTPError(Exception):
    def __init__(self, status: int, message: str) -> None: ...   # .status, .message
```

### 3.9 `core/registry.py`

shopapi's registry with three additions: the `public` flag, ui.js discovery and frame routes.

```python
Handler = Callable[[Request], Response]
def route(method: str, pattern: str, *, public: bool = False) -> Callable[[Handler], Handler]
@dataclass(frozen=True)
class Route:
    method: str; pattern: str; handler: Handler; feature: str; public: bool
def discover(package: str = "chatbook.features") -> list[Route]
def discover_ui(package: str = "chatbook.features") -> list[str]
    # sorted names of feature folders containing ui.js; such a folder without __init__.py,
    # or a name not matching ^[a-z][a-z0-9_]*$, raises RegistryError
def match(pattern: str, path: str) -> dict[str, str] | None
def specificity(pattern: str) -> tuple[int, ...]
def ensure_unique(routes: list[Route]) -> None      # same (method, shape) twice -> RegistryError
class RegistryError(Exception): ...
```

Marks attribute: `__chatbook_routes__` holding `(METHOD, pattern, public)` tuples. Folders with
only `__init__.py` + `ui.js` (pages) are skipped by `discover()` (no `handler.py`).

### 3.10 `core/api.py` (the public contract)

Short: the import lines and `__all__`, with a one-line docstring pointing to `docs/api/*.md`.
It is the only `chatbook` module features may import (archlint).

```python
__all__ = [
    "route", "Request", "Response", "HTTPError", "User", "Db",
    "body_str", "body_id", "body_ids", "path_id", "query_str", "query_int", "query_opt_int",
    "user_json", "get_user", "require_user", "create_user", "check_password", "new_session",
    "are_friends", "befriend", "unfriend", "relationship", "friend_ids", "visible_post",
    "create_conversation", "find_direct", "require_member", "member_ids", "add_member",
    "remove_member", "post_message", "message_json", "mark_read", "unread_count",
    "conversation_json",
]
```

### 3.11 `app.py`

```python
def create_app(db_path: str = ":memory:", *, clock: Clock | None = None,
               hash_iterations: int = 200_000, raise_errors: bool = False) -> App

class App:
    routes: list[Route]             # discovered + frame routes, sorted by specificity
    ui_features: list[str]          # discover_ui()
    db: Db
    clock: Clock
    raise_errors: bool              # Client sets True: unexpected exceptions propagate
    def handle(self, method: str, path: str, body: object = None,
               query: dict[str, str] | None = None,
               headers: dict[str, str] | None = None) -> Response
    def wsgi(self, environ: WSGIEnvironment, start_response: StartResponse) -> Iterable[bytes]
```

Frame routes (feature name `core`, part of `routes` and of `ensure_unique`):

| Route | Auth | Response |
|---|---|---|
| `GET /api/health` | public | 200 `{"status": "ok"}` |
| `GET /api/session` | login | 200 `{"user": U}` |
| `DELETE /api/session` | login | `end_session(token)`; 200 `{"ok": true}` |

`App.handle` steps, in order:

1. `method = method.upper()`.
2. **Static** (path not starting with `/api/`): `GET /` -> generated index page;
   `GET /static/<name>` for `name` in {`cb.js`, `cb.css`, `start.js`}; `GET /ui/<feature>.js`
   for `feature` in `ui_features`, served wrapped as
   `(() => {\n'use strict';\n<file text>\n})();\n//# sourceURL=/ui/<feature>.js\n`. Anything
   else (any method) -> 404 `{"error": "not found"}`. Static responses carry
   `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'`,
   `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store`,
   and types `text/html`, `text/javascript`, `text/css` (all `; charset=utf-8`). The index page
   is `static/index.html` with `<!--FEATURE_SCRIPTS-->` replaced by one
   `<script defer src="/ui/<feature>.js"></script>` per ui feature in sorted order.
3. **API match**: first route (specificity order) whose pattern matches and method equals.
   No match but the path matches other methods -> 405 `{"error": "method not allowed",
   "allow": [sorted methods]}`; no match at all -> 404 `{"error": "not found"}`.
4. **Auth**: `authorization` header `Bearer <token>` -> `user_for_token`; unknown token = anonymous.
   Non-public route and no user -> 401 `{"error": "login required"}` (handler not called).
5. **Transaction**: `db._begin()` (`BEGIN IMMEDIATE`); if logged in, `touch(user.id, now)`;
   build `Request(..., now=clock.now_ms())`; call the handler.
6. Outcome: a `Response` with status < 400 -> `_commit()`; a `Response` with status >= 400 ->
   `_rollback()`; `HTTPError` -> rollback, `Response(status, {"error": message})`;
   a UNIQUE / PRIMARY KEY `sqlite3.IntegrityError` (`sqlite_errorname`
   `SQLITE_CONSTRAINT_UNIQUE` or `SQLITE_CONSTRAINT_PRIMARYKEY`) -> rollback, 409
   `{"error": "conflict"}`; other constraint failures (NOT NULL, CHECK, ...) are handler bugs and
   take the unexpected-error path below; a non-`Response` return value -> treated as an exception
   (`TypeError("handler must return Response")`); any other exception -> rollback, then re-raise
   if `raise_errors`, else 500 `{"error": "internal error"}` with the traceback printed to stderr.

`App.wsgi`: reads and parses the request first (the checks below; a 400/413 answer needs no
lock), then holds **one `threading.Lock` around dispatch, transaction, handler and encoding**, so
the threaded server never runs two requests at once and a client that stalls mid-body holds only
its own thread. As in shopapi:
- `HEAD` is handled as `GET` with an empty body;
- `CONTENT_LENGTH` must be ASCII digits (whitespace stripped), else 400 `bad Content-Length`;
  more than 65536 bytes -> 413 `{"error": "request body too large"}`;
- fewer body bytes than `CONTENT_LENGTH` (the client went away) or a socket error while reading
  -> 400 `{"error": "request body incomplete"}`;
- a non-empty body that is not JSON (including one nested too deeply for `json.loads`, which
  raises `RecursionError`) -> 400 `{"error": "request body is not valid JSON"}`;
- `PATH_INFO` and `QUERY_STRING` re-decoded latin-1 -> UTF-8; query via `parse_qsl`;
- headers from `HTTP_*` keys plus `CONTENT_TYPE`, lower-cased, `_` -> `-`;
- JSON responses: `Content-Type: application/json; charset=utf-8`, `Cache-Control: no-store`,
  `X-Content-Type-Options: nosniff`, `Content-Length`.

### 3.12 `__main__.py` and `core/demo.py`

`python -m chatbook [--demo]`:
- env `PORT` (default 8000), `HOST` (default `127.0.0.1`), `CHATBOOK_DB` (default `chatbook.db`
  in the current directory);
- server: `class ThreadingWSGIServer(socketserver.ThreadingMixIn, WSGIServer)` with
  `daemon_threads = True`, and `class RequestHandler(WSGIRequestHandler)` with `timeout = 30`
  whose `handle()` closes a connection that timed out without a traceback;
  `make_server(host, port, app.wsgi, server_class=ThreadingWSGIServer, handler_class=RequestHandler)`;
- prints every route (`METHOD pattern feature`), every ui feature and the URL;
- `--demo`: if the `users` table is empty, `demo.seed(app.db, now)` and print the demo logins.

`demo.seed(db: Db, now: int) -> None` uses core helpers plus plain inserts into posts, likes and
comments (core-owned tables), so it works whatever features are merged:
- users `alice` "Alice Adams", `bob` "Bob Brown", `carol` "Carol Chen", `dave` "Dave Diaz",
  password `password1` (local demo only; printed at startup);
- friendships alice-bob, alice-carol, bob-carol; pending request dave -> alice;
- a direct conversation alice-bob with 3 messages; group "Weekend trip" (alice, bob, carol)
  with 2 messages;
- 2 posts (alice, bob), one like, one comment.

### 3.13 The UI runtime (`core/static/`)

**`index.html`**: doctype, `lang="en"`, charset and viewport metas, `<title>ChatBook</title>`,
`<link rel="stylesheet" href="/static/cb.css">`, `<script defer src="/static/cb.js"></script>`,
`<!--FEATURE_SCRIPTS-->`, `<script defer src="/static/start.js"></script>`; body:
`<header id="cb-header"></header><main id="cb-main"></main><div id="cb-toasts"></div>`.
No inline script or style (CSP).

**`cb.js`** defines `window.CB` (in the browser) or the runner's global `CB`. Structure: one
platform-independent core that talks to a **host** object (DOM factory, storage, HTTP, timers,
hash location, clock, event hook). The browser host uses `document`, `fetch`, `localStorage`,
`setInterval`, `location.hash`; `tools/uirun.js` supplies a fake host. The same core code runs in
both, so the runner tests the real engine.

Worker-facing API (exactly what `docs/ui.md` documents; nothing else is public):

| Function | Behaviour |
|---|---|
| `CB.page(name, spec)` | Registers a page. `spec = {title, nav?, order? (default 100), public? (default false), load?, render, poll?}`. `load(params)` may be async and returns data (default `{}`); `render(data, params)` returns a child (node, string, number, array, null). Duplicate name -> throws `Error('page "<name>" registered twice')`. |
| `CB.api(method, path, body?)` | `fetch` with JSON body (none if `body` is undefined), `Authorization: Bearer <token>` when logged in. 2xx -> parsed JSON. Error -> `CB.toast(error message or 'Request failed (<status>)')` and throws an `ApiError(status, message)`. A 401 **while logged in** also runs `CB.logout()`. |
| `CB.el(tag, props?, ...children)` | Creates an element. Props: `class`, `testid` (-> `data-testid`), `title`, `type`, `value`, `placeholder`, `disabled`, `checked`, `name`, `onclick`. Any other prop -> throws `Error('CB.el: unknown prop "<p>"; allowed: ...')`. Tags `script`, `style`, `iframe`, `object`, `embed`, `link`, `meta` throw; tag `form` throws `Error('CB.el: tag "form" is not allowed; use CB.form')` (a hand-built form would reload the page on submit and put its fields in the URL). Children: strings/numbers become text nodes (never HTML), arrays are flattened, `null`/`undefined`/`false` skipped. `onclick` may be async; a rejected `ApiError` is swallowed (already toasted), any other error is logged as an uncaught error. |
| `CB.form({fields, submit, reset?, onsubmit})` | Builds a form. `fields: [{name, label, type?, value?, options?}]`, `type` in `text` (default), `password`, `textarea`, `select`, `checkboxes`; `options: [{value, label}]` (strings). Values passed to `onsubmit`: strings; `checkboxes` -> array of checked values (strings). While `onsubmit` runs the submit button is disabled. On success with `reset: true`, text/password/textarea fields are cleared. Errors handled as for `onclick`. |
| `CB.go(name, params?)` | Navigates to `#/<name>?<params>`; every param value is converted with `String()`. |
| `CB.refresh()` | Re-runs `load` + `render` of the current page (one at a time; a refresh requested during a refresh runs once afterwards). |
| `CB.every(ms, fn)` | Registers a global job: runs `fn` once right after login (or at start if already logged in) and then every `ms` while logged in; stopped by logout. For page-less services, called at the top level of a file. |
| `CB.me` | Getter: the logged-in user U, or null. |
| `CB.login(token, user)` | Stores the token, sets `me`, starts `every` jobs, goes to `inbox`. |
| `CB.logout()` | Best-effort `DELETE /api/session`, clears token and `me`, stops jobs, goes to `login`. |
| `CB.reloadMe()` | `GET /api/session` and updates `me` and the header. |
| `CB.avatar(user)` | A `span.avatar` with initials (`aria-hidden="true"`), colour picked from the id. |
| `CB.userLink(user)` | A clickable `a.user-link` showing `display_name`; click -> `CB.go('profile', {id: user.id})`. |
| `CB.time(ms)` | `'HH:MM'` if today, else `'D Mon'` (host clock, local time zone). Never asserted in tests. |
| `CB.plural(n, word)` | `'1 friend'`, `'3 friends'` (adds `s` unless n === 1). |
| `CB.short(text, n)` | `text` if its length <= n, else `text.slice(0, n) + '...'`. |
| `CB.toast(text)` | Shows a message for 4 s. |
| `CB.badge(page, n)` | Sets the nav badge of `page` (hidden when n <= 0). The tab title is prefixed with `(<sum of badges>) ` when the sum > 0. |
| `CB.qs(obj)` | `'?a=1&b=x'` with `encodeURIComponent`, keys in insertion order, skipping null/undefined/''; `''` when nothing remains. |

Internal behaviour (frame-owned, documented in `docs/ui.md` only where workers need it):
- **Router**: hash `#/<page>?<query>`; empty hash -> `inbox` when logged in, else `login`.
  Logged out + non-public page -> replace with `login`. Logged in + `login` -> `inbox`. Unknown
  page -> a "Page not found" card. Each navigation cancels the previous page's poll timer.
- **Render cycle**: show "Loading..." only on first load; `data = await load(params)`;
  `child = render(data, params)`; mount. Before replacing the mounted tree, record the value of
  every named form field whose value differs from its initial value (key: form index + field
  name), plus the focused field and its selection; after mounting, restore them where the field
  still exists. Elements with class `messages` are scrolled to the bottom on first render and on
  re-render if they were at the bottom. Load and render run on every poll and refresh, but when
  the data (as JSON) and `CB.me` equal those of the mounted render and the new tree has the same
  fingerprint as the mounted one (tags, attributes, text, `disabled`, option and checkbox values;
  not typed text, ticked boxes or the selected option), nothing is mounted: a click in progress,
  the text selection and the focus survive an unchanged poll. A tree the page's own code changed
  after mounting (e.g. `button.disabled = true`) differs, so it is mounted again.
- **Load errors**: on the first load of a page, `ApiError` -> a card "Could not load this page."
  with a "Retry" button (`CB.refresh`); other errors -> the same card and an uncaught-error
  record. A failed poll or refresh of a page already shown keeps the page and its typed text
  (the `ApiError` toast, or the error record, is the only sign). A render error always shows
  the card.
- **Poll**: `spec.poll` ms timer while the page is shown; skipped while the tab is hidden or a
  refresh is in flight.
- **Header**: logo, search input (Enter -> `CB.go('people', {q: value.trim()})` when non-empty),
  nav links for pages with `nav` sorted by `order` then name, each with a badge span, the user's
  name (`CB.go('profile')`), "Log out". Hidden when logged out.
- **Start** (`start.js` calls `CB.start()`): read the token from storage key `cb.token`; if present
  `GET /api/session` (401 -> clear); start jobs if logged in; route the current hash.
- **Host events** (no-ops in the browser, recorded by the runner): `go`, `toast`, `badge`,
  `login`, `logout`, `error`.

**`cb.css`** defines (at least): body background `#f0f2f5`, system font; header bar `#1877f2`
white text; `.stack` (column, 12 px gap), `.row` (row, centred, gap, wrap), `.item` (list row,
white, padding, rounded, hover), `.item.unread` (bold), `.card` (white, rounded, shadow, padding),
`.muted` (grey), `.badge` (red pill), `.messages` (scrollable column, max-height 60vh), `.msg`
(bubble, light grey), `.msg.mine` (right, `#1877f2`, white text), `.danger` (red button),
`.narrow` (max-width 420 px, centred), `.avatar` (32 px circle), `.user-link`, buttons, inputs,
toasts, responsive below 600 px. Every class named in `docs/ui.md` must exist.

### 3.14 `tools/uirun.js` (headless page runner)

`node tools/uirun.js` reads one JSON scenario from **stdin** and prints one JSON result on stdout
(exit 0), or prints a stack trace on stderr (exit 1) for a runner crash. It creates a Node `vm`
context whose globals are only the JS built-ins plus `__CB_HOST__` (fake host), evaluates
`cb.js`, then each feature file wrapped exactly as the server wraps it. The context has no
`document`, `window`, `fetch`, timers or `require`.

**Fake DOM**: elements with `tagName`, attributes, children, parent, `append`, `replaceChildren`,
`remove`, `textContent` (get/set), `value`, `checked`, `disabled`, `focus`, `scrollTop`/
`scrollHeight` (numbers), `setAttribute`/`getAttribute`/`getAttributeNames` and listener
storage, all that `cb.js` needs internally (staff detail). Feature code's allowed node operations
are listed in `docs/ui.md`; the lint gate rejects the rest before tests run. Where page code could
rely on more than Chrome gives, the fake is as strict as Chrome: `appendChild` takes only nodes
(a string throws Chrome's `TypeError`; `append` turns strings into text), `childNodes` is a live
NodeList view (`length`, `item`, `[i]`, iteration, `forEach`, `entries`/`keys`/`values`) and
`children` a live HTMLCollection view (no `forEach`), neither with Array methods (`map`,
`filter`), and setting a select's `value` to a value no option has selects nothing (`''`), while
a value set before any option exists leaves the first option inserted later selected. A submit
of a form that no listener prevents (the browser would reload the page) is recorded in `errors`.

**Fake host**: time starts at `1_700_000_000_000` and only moves with `tick`; timers fire only on
`tick`; storage is in memory; `fetch` answers from the scenario's `api` table.

Scenario (all keys optional except `files`):

```json
{
  "cb": "<abs path of cb.js>",
  "files": ["<abs path of a ui.js>", "..."],
  "me": {"id": 1, "username": "alice", "display_name": "Alice Adams"},
  "token": "t0",
  "page": "chat",
  "params": {"id": "3"},
  "api": {
    "GET /api/conversations/3": {"conversation": {}},
    "GET /api/conversations/3/messages?limit=50": [{"messages": [], "has_more": false}, {"messages": [], "has_more": false}],
    "POST /api/conversations/3/read": {"$status": 404, "error": "conversation not found"}
  },
  "steps": [
    {"click": "Send"}, {"click": "Accept", "nth": 1}, {"click_id": "accept-4"},
    {"fill": "Send", "values": {"body": "draft"}},
    {"submit": "Send", "values": {"body": "hello"}},
    {"tick": 2000},
    {"go": "chat", "params": {"id": "3"}}
  ],
  "load_all": false
}
```

- **API matching**: key `"METHOD /path?query"` exactly as requested first, then
  `"METHOD /path"` without the query. A value is a JSON body answered with 200, or
  `{"$status": n, "error": "..."}` answered with that status, or a **list** of those consumed in
  order (the last one repeats). Unknown keys answer 404 `{"error": "not found"}` and are recorded
  in `unmatched`.
- **Start**: if `me` is set, `CB.me` is set without calling `/api/session` and `every` jobs run
  once. If `page` is set, it is opened with `params` (not recorded in `nav`). `page: null` loads
  the files only (services, page registry).
- **Steps** (after each, the runner drains all pending promises):
  - `click`: among clickable elements (every `button`, every element with `onclick`) pick those
    whose collapsed text equals the label, else those containing it; `nth` (default 0) chooses in
    tree order. No match, or a disabled button -> a `scenario:` entry in `errors`.
  - `click_id`: the clickable element with that `data-testid`.
  - `fill` / `submit`: the form whose submit button label equals the value; `values` sets fields by
    name (string; list of option values for `checkboxes`); an unknown field name or option ->
    `scenario:` error. `submit` then submits as the browser would.
  - `tick`: advances the clock by `ms`; every timer that is due runs once.
  - `go`: `CB.go(page, params)`.
- **`load_all: true`**: evaluate all `files`, report `pages` (with the file that registered each)
  and `errors`, nothing else.

Result:

```json
{
  "pages": [{"name": "chat", "title": "Chat", "nav": null, "order": 100, "public": false, "file": "page_chat"}],
  "page": "chat",
  "title": "Chat",
  "text": "Ski trip Alice Adams, Erin Evans Erin Evans: hi there 14:05 ...",
  "classes": [["stack", "..."], ["msg", "Erin Evans: hi there 14:05"]],
  "buttons": [{"label": "Send", "disabled": false, "testid": null}],
  "forms": [{"submit": "Send", "fields": ["body"], "types": {"body": "text"}, "options": {}, "values": {"body": ""}}],
  "calls": [["GET", "/api/conversations/3", null]],
  "unmatched": [],
  "nav": [["group", {"id": "3"}]],
  "toasts": [],
  "badges": {"inbox": 3},
  "session": [["login", "tok", {"id": 1}], ["logout"]],
  "errors": []
}
```

- `text`: the mounted page only (not header, toasts). Text nodes concatenated in tree order;
  every element except the inline formatting tags `b`, `strong`, `i`, `em`, `code` adds a space
  before and after; elements with `aria-hidden="true"` (avatars) are skipped; whitespace runs
  collapse to one space; trimmed. So `CB.el('b', {}, 'Bob'), ': ', 'hi'` reads `Bob: hi`, and
  a `small` time next to a `span` badge reads `14:05 2`.
- `classes`: `[class attribute, collapsed text]` for every element in the page that has a class,
  in tree order (e.g. `["badge", "2"]`, `["msg mine", "Alice Adams: hello 14:05"]`,
  `["item unread", "..."]`).
- `buttons`: every `button` in the page, in tree order.
- `calls`: `[method, path_with_query, body_or_null]` in order.
- `nav`: every `CB.go` after start, params as strings.
- `errors`: uncaught non-API errors (message), plus `scenario:` problems. Every UI test asserts
  `errors == []`.

### 3.15 `testing.py` (the one door for hidden tests)

Protected; outside `core` (it imports `app`); features may not import it (archlint).

```python
ALICE = {"id": 1, "username": "alice", "display_name": "Alice Adams"}
BOB   = {"id": 2, "username": "bob", "display_name": "Bob Brown"}
CAROL = {"id": 3, "username": "carol", "display_name": "Carol Chen"}
DAN   = {"id": 4, "username": "dan", "display_name": "Dan Diaz"}
ERIN  = {"id": 5, "username": "erin", "display_name": "Erin Evans"}
FRANK = {"id": 6, "username": "frank", "display_name": "Frank Fox"}

class Account(NamedTuple):
    id: int; username: str; display_name: str; token: str
    json: dict[str, Any]            # U

@dataclass
class Resp:
    status: int
    json: Any                       # parsed JSON, or None for non-JSON responses
    text: str                       # raw body text
    headers: dict[str, str]

class Client:
    __test__ = False
    def __init__(self) -> None
        # create_app(":memory:", clock=FakeClock(), hash_iterations=1, raise_errors=True)
    app: App; db: Db; clock: FakeClock
    @property
    def now(self) -> int
    def tick(self, ms: int = 1000) -> None
    def user(self, username: str, display_name: str | None = None,
             password: str = "password1") -> Account
        # create_user (display_name defaults to username.capitalize()) + new_session
    def request(self, method: str, path: str, body: object = None, *,
                user: Account | None = None, token: str | None = None,
                headers: dict[str, str] | None = None) -> Resp
        # path may contain '?query' (parse_qsl) and %-escapes (unquoted); the body is round-tripped
        # through json.dumps/json.loads (int dict keys become strings); App.handle with a real
        # 'authorization: Bearer <token>' header; the response body is round-tripped too, so a
        # non-serializable body raises in the test; unexpected handler exceptions propagate
    def get(self, path, *, user=None, token=None) -> Resp
    def post(self, path, body=None, *, user=None, token=None) -> Resp
    def put(self, path, body=None, *, user=None, token=None) -> Resp
    def delete(self, path, *, user=None, token=None) -> Resp
    # seeding through core helpers (each commits at once)
    def befriend(self, a: Account, b: Account) -> None
    def unfriend(self, a: Account, b: Account) -> None
    def are_friends(self, a: Account, b: Account) -> bool
    def friend_request(self, a: Account, b: Account) -> int        # pending row a -> b, its id
    def dm(self, a: Account, b: Account) -> int                    # find or create direct
    def group(self, owner: Account, members: list[Account], title: str = "Group") -> int
    def leave(self, user: Account, cid: int) -> None
    def send(self, sender: Account, cid: int, body: str = "hello") -> int   # message id
    def read(self, user: Account, cid: int) -> None                # mark_read
    def unread(self, user: Account, cid: int) -> int
    def make_post(self, author: Account, body: str = "post") -> int
    def like(self, user: Account, pid: int) -> None
    def comment(self, user: Account, pid: int, body: str = "nice") -> int
    def touch(self, user: Account) -> None                         # last_seen_at = now
    # inspection and expected values
    def row(self, sql: str, *args: object) -> dict[str, Any] | None
    def rows(self, sql: str, *args: object) -> list[dict[str, Any]]
    def message(self, mid: int) -> dict[str, Any]                  # M
    def conversation(self, cid: int, viewer: Account) -> dict[str, Any]   # C

# UI fixtures (plain dicts in the API shapes)
def fake_message(id: int, sender: dict, body: str, *, conversation_id: int = 3,
                 created_at: int = 1_700_000_000_000) -> dict
def fake_conversation(id: int, kind: str, title: str, members: list[dict], *,
                      last_message: dict | None = None, unread: int = 0,
                      updated_at: int = 1_700_000_000_000) -> dict
def fake_request(id: int, frm: dict, to: dict, created_at: int = 1_700_000_000_000) -> dict
def fake_post(id: int, author: dict, body: str, *, like_count: int = 0,
              comment_count: int = 0, liked: bool = False) -> dict

@dataclass
class UiResult:
    pages: list[dict]; page: str | None; title: str | None; text: str; classes: list[list]
    buttons: list[dict]; forms: list[dict]; calls: list[list]; unmatched: list[list]
    nav: list[list]; toasts: list[str]; badges: dict[str, int]; session: list[list]
    errors: list[str]
    @property
    def labels(self) -> list[str]                  # button labels
    def count(self, method: str, path: str) -> int  # calls with exactly this method and path

def run_page(feature: str, page: str | None = None, *, params: dict[str, str] | None = None,
             me: dict[str, Any] | None = ALICE, token: str = "t0",
             api: dict[str, Any] | None = None, steps: list[dict[str, Any]] | None = None,
             files: list[str] | None = None) -> UiResult
    # files default: [<repo>/src/chatbook/features/<feature>/ui.js]; <repo> =
    # Path(__file__).resolve().parents[2]; runs `node <repo>/tools/uirun.js` with the scenario on
    # stdin, env TZ=UTC, timeout 60 s; node missing or a runner crash -> AssertionError with stderr
```

### 3.16 `tools/check_extra.py` (gate)

Run as `{python} tools/check_extra.py` from the repo root; standard library only; exits 1 on any
problem, printing `path:line: problem` and a fix hint for each (characters the console code
page lacks are printed as backslash escapes, so a worker's non-ASCII text cannot crash the
report). Two more modes, for item 6: `--write-contracts` (staff) and `--restore-contracts`
(harness autofix).

1. `node --check` on every `.js` under `src/chatbook` and `tools` (node missing -> fail with
   "install Node.js 24 and put it on PATH").
2. For each `src/chatbook/features/*/ui.js`, these regexes on each line (comment lines starting
   with `//` included, since they rarely matter) with hints:

   | Pattern | Hint |
   |---|---|
   | `\bdocument\s*\.`, `\bwindow\s*\.`, `\bglobalThis\b` | use CB.* only |
   | `\bfetch\s*\(`, `XMLHttpRequest` | use CB.api |
   | `\.innerHTML\b`, `\.outerHTML\b`, `insertAdjacentHTML` | build nodes with CB.el |
   | `\beval\s*\(`, `\bnew\s+Function\b` | not allowed |
   | `\bsetTimeout\s*\(`, `\bsetInterval\s*\(` | use the page's `poll` or CB.every |
   | `\blocalStorage\b`, `\bsessionStorage\b` | the frame keeps the session |
   | `\.addEventListener\s*\(` | use the onclick prop or CB.form |
   | `\.classList\b`, `\.style\b`, `\.setAttribute\s*\(` | use CB.el props (class, ...) |
   | `\.querySelector`, `\.getElementById\s*\(` | keep references to the nodes you create |
   | `^\s*import\b`, `\bimport\s*\(`, `\brequire\s*\(` | no modules: the file is a plain script |

   Also: the file must contain `CB.page(` or `CB.every(`.
3. Every file under `src/chatbook/features/` (`.py` and `.js`) has at most 180 lines ("split or
   simplify: whole-file edits of long files get truncated").
4. In `src/chatbook/features/**/*.py` (via `ast`; docstrings of modules, classes and functions
   are skipped, adjacent literals are one string, `+` chains of literals are joined), no string
   names a schema statement, any case: `(CREATE|ALTER|DROP) [TEMP|TEMPORARY|UNIQUE|VIRTUAL]
   (TABLE|INDEX|VIEW|TRIGGER)`, `PRAGMA`, `ATTACH|DETACH DATABASE`, `ATTACH <x> AS <name>`. Hint:
   "the schema belongs to the frame: no CREATE/ALTER/DROP TABLE, PRAGMA or ATTACH in feature
   code; if this text is not SQL, reword it". English such as "Create a new post" or "could not
   drop it" passes.
5. In the same files, SQL is one constant string (hint "SQL must be one string literal with ?
   placeholders; pass the values as arguments"): (a) the first argument of any `.one/.all/.value/
   .run/.page(...)` call is a string literal, a variable, or `a if c else b` of those; (b) no
   f-string, `+`/`%` with a literal, or `.format`/`.join` on a literal builds text that reads as
   SQL (`SELECT ... FROM`, `INSERT|REPLACE ... INTO`, `UPDATE ... SET`, `DELETE ... FROM`,
   `WHERE`, `ORDER BY`, `VALUES (`, any case); (c) a variable passed as that first argument is
   only ever assigned such values in the file (no `+=`). This complements the line-based
   `forbidden_added` patterns (section 4), which miss split literals and other forms.
6. **CONTRACT blocks stay in place** (added after Wave 1, see 0 row 21). Every file listed in
   `tools/contracts.json` (each `features/*/handler.py` and `features/*/ui.js` that has a
   CONTRACT block on the frame: the docstring that opens line 1 of a `handler.py`, the leading
   `//` lines of a `ui.js`) must still **begin with exactly that block**, compared after
   normalising line endings (and dropping a byte-order mark). In a `ui.js` the line after the
   block must not be another `//` line: the leading comment block is the CONTRACT and nothing
   more (a blank line or code may follow, then any comments). Code of any kind below the block
   passes. Reports, printed after all other problems (the harness keeps the head and mostly the
   tail of long gate output):
   - `path:N: CONTRACT block missing or changed (fix: restore it verbatim at the top of the
     file, then put your code below it)`, N = the first line that differs, then the expected
     and found line and the whole block to restore between `====` lines (workers cannot see the
     snapshot, and the architect needs the verbatim text to put back);
   - `path:1: CONTRACT block moved below other code (it starts at line N)` (same hint);
   - `path:N: a // comment line right after the CONTRACT block extends it (fix: leave the
     CONTRACT block as it is; put a blank line or code before your comments)`;
   - `path:1: file missing` (a listed file was deleted; same hint and block);
   - `tools/contracts.json: not found` or unreadable (staff hint: regenerate it).

   **Snapshot.** `tools/contracts.json` = `{"about": ..., "files": {"<path>": ["<line>", ...]}}`,
   ASCII, one JSON string per block line so `git diff` shows block changes line by line. It is
   under `tools/**`, so the guard reverts any worker edit. The check needs no git, no ref name
   and no network: it behaves the same in a harness worktree, on an integration branch and in
   the oracle clone. (Rejected: comparing against `git show <base>:<path>` needs a ref the gate
   does not know and differs between run, integrate and validate; hashes instead of text
   could not show the worker what to restore; embedding ~44 KB of blocks in the tool hides
   block changes in a code diff.)

   **Restore (autofix).** The harness feedback budget (`feedback_chars` 3000) is split between
   the failing stages, so when another stage fails in the same iteration the printed block can
   be clipped (page_chat's is 2.3k characters) and the worker could not put it back. So the
   first autofix step (section 4) is `{python} tools/check_extra.py --restore-contracts`: for
   each snapshot entry whose file exists, is UTF-8 and does not begin with its block, and holds
   **no trace** of the block (neither the block's first line, without `//` or quotes, nor the
   word `CONTRACT` anywhere in the file), it puts the block back at the top. Any trace means an
   edited or moved block: the file is left byte for byte as it is and the gate reports it. (Not
   "any block line occurs": blocks hold pseudo-code such as `uid = path_id(request)` that
   workers copy into code verbatim; the Wave 1 cb-05 file had it, and that test would have
   blocked the restore. Not "the first line only": a worker who rewrote just the summary line
   would get a second, unedited block above the edited one.)
   - `handler.py`: the block is the module docstring. If the file opens with a docstring of its
     own (a string statement alone on its lines; comments before it are kept), the block takes
     its place: kept below the block, that docstring would become a plain string before the
     imports, which ruff rejects (E402, not auto-fixable) for a reason the worker cannot see.
     A docstring holds no behaviour, so nothing is lost. Either way a `from __future__` import
     stays the first statement after the docstring. A file that opens with a string that is
     not a statement of its own (`"""x"""; import re`) is left alone; so is one whose code
     compiles before and would not after (a safety net; `compile` only, nothing runs). Code
     that does not compile still gets its block (the other gates report the code).
   - `ui.js`: block, one blank line, then the file without its leading blank lines.
   - Line endings follow the file's first line ending; a byte-order mark stays first.
   - Writes only existing `src/chatbook/features/<name>/(handler.py|ui.js)` paths, whatever the
     snapshot lists; never recreates a deleted file (the gate reports `file missing`); prints
     a line for each file it restored or left with its block not in place (and why), then
     `restore-contracts: N CONTRACT block(s) restored` (to the run's `autofix.log`);
     idempotent; always exits 0.

   **Staff:** after changing a stub's CONTRACT block, adding a stub or removing one (8.1
   steps 1, 4 and 6), run `python tools/check_extra.py --write-contracts` (it prints the added,
   changed and REMOVED paths), check `git diff tools/contracts.json` (every line must match a
   stub you changed, added or removed on purpose; any other change, a REMOVED path above all,
   means a damaged feature file, not a new contract: restore the file instead) and commit the
   snapshot with the stub. `tests/test_check_extra.py` fails if a feature file is missing from
   the snapshot (its message tells workers not to add `handler.py`/`ui.js` files and staff to
   regenerate after adding a stub) or the snapshot is not exactly what `--write-contracts`
   makes; the gate itself fails if a block was edited, or a stub removed, without
   regenerating.

### 3.17 Feature stubs and the route/page tables

The frame commit contains all 30 feature folders. Backend folders: `__init__.py` (one-line
docstring) + `handler.py`. UI folders: `__init__.py` + `ui.js`.

Backend stub template (the CONTRACT is the task's spec, condensed; lines <= 100 chars):

```python
"""accounts: register and log in.

CONTRACT (keep this docstring; implement exactly this):
POST /api/auth/register (public) body {"username", "password", "display_name"}
  ...steps copied from the task spec...
"""

from chatbook.core.api import HTTPError, Request, Response, route


@route("POST", "/api/auth/register", public=True)
def register(request: Request) -> Response:
    raise HTTPError(501, "not implemented")
```

Import only names the stub uses (ruff F401 must pass on base). UI stub template:

```js
// page_inbox: the conversation list (home page).
// CONTRACT (keep this comment; implement exactly this):
// ...the task spec, condensed...
CB.page('inbox', {
  title: 'Chats',
  nav: 'Chats',
  order: 10,
  render: () => CB.el('p', {class: 'muted'}, 'Coming soon'),
});
```

The `badges` stub is `CB.every(5000, async () => {});` under its CONTRACT comment. Stubs keep base
green and make every hidden suite fail on base (501 / "Coming soon" / no calls). A CONTRACT block
is at most 30 lines; stub + implementation stays under 120 lines. Workers keep the block
unchanged at the top of the file and write below it; check_extra enforces this against
`tools/contracts.json` (3.16 item 6), which staff regenerate whenever a block changes, a stub
is added or a stub is removed; a block a worker deleted outright is put back by the autofix
step `--restore-contracts`.

Route table (asserted exactly by `tests/test_route_map.py`: method, pattern, public, feature):

| Method | Pattern | Public | Feature | Task |
|---|---|---|---|---|
| GET | `/api/health` | yes | core | frame |
| GET | `/api/session` | | core | frame |
| DELETE | `/api/session` | | core | frame |
| POST | `/api/auth/register` | yes | accounts | cb-01 |
| POST | `/api/auth/login` | yes | accounts | cb-01 |
| GET | `/api/users` | | people | cb-02 |
| POST | `/api/friends/requests` | | friend_requests | cb-03 |
| GET | `/api/friends/requests` | | friend_requests | cb-03 |
| POST | `/api/friends/requests/{id}/accept` | | friend_answers | cb-04 |
| POST | `/api/friends/requests/{id}/decline` | | friend_answers | cb-04 |
| DELETE | `/api/friends/requests/{id}` | | friend_answers | cb-04 |
| GET | `/api/friends` | | friends | cb-05 |
| DELETE | `/api/friends/{id}` | | friends | cb-05 |
| POST | `/api/dm` | | dm | cb-07 |
| POST | `/api/groups` | | groups | cb-08 |
| PUT | `/api/groups/{id}` | | groups | cb-08 |
| POST | `/api/groups/{id}/members` | | group_members | cb-09 |
| DELETE | `/api/groups/{id}/members/me` | | group_members | cb-09 |
| GET | `/api/conversations` | | conversations | cb-10 |
| GET | `/api/conversations/{id}` | | conversations | cb-10 |
| POST | `/api/conversations/{id}/messages` | | chat_send | cb-11 |
| POST | `/api/conversations/{id}/read` | | chat_send | cb-11 |
| GET | `/api/conversations/{id}/messages` | | chat_history | cb-12 |
| GET | `/api/updates` | | updates | cb-13 |
| GET | `/api/users/{id}` | | profiles | cb-14 |
| PUT | `/api/profile` | | profiles | cb-14 |
| POST | `/api/posts` | | posts | cb-23 |
| GET | `/api/feed` | | posts | cb-23 |
| GET | `/api/posts/{id}` | | posts | cb-23 |
| DELETE | `/api/posts/{id}` | | posts | cb-23 |
| POST | `/api/posts/{id}/like` | | likes | cb-24 |
| DELETE | `/api/posts/{id}/like` | | likes | cb-24 |
| GET | `/api/posts/{id}/likes` | | likes | cb-24 |
| GET | `/api/posts/{id}/comments` | | comments | cb-25 |
| POST | `/api/posts/{id}/comments` | | comments | cb-25 |
| DELETE | `/api/comments/{id}` | | comments | cb-25 |
| GET | `/api/friends/online` | | presence | cb-26 |
| GET | `/api/friends/suggestions` | | suggestions | cb-27 |

Page table (asserted exactly from `uirun` `load_all`: name, nav, order, public, file): see 1.3,
with `order` 100 for pages without nav, and `badges` registering no page.

Stub function names (keep them in the stubs; a later rename is harmless but discouraged):
accounts `register`, `login`; people `search_users`; friend_requests `send_request`,
`list_requests`; friend_answers `accept_request`, `decline_request`, `cancel_request`; friends
`list_friends`, `remove_friend`; dm `open_dm`; groups `create_group`, `rename_group`;
group_members `add_member_route`, `leave_group`; conversations `list_conversations`,
`get_conversation`; chat_send `send_message`, `read_conversation`; chat_history `list_messages`;
updates `get_updates`; profiles `get_profile`, `update_profile`; posts `create_post`, `get_feed`,
`get_post`, `delete_post`; likes `like_post`, `unlike_post`, `list_likes`; comments
`list_comments`, `add_comment`, `delete_comment`; presence `online_friends`; suggestions
`friend_suggestions`. (`add_member_route` avoids shadowing the imported `add_member`.)

### 3.18 Worker documentation (`docs/`, protected, passed read-only per task)

`tests/test_api_doc.py` checks that every name in `api.__all__` is documented in exactly one
`docs/api/*.md` file, that each documented signature line (`name(params) -> ret`) has the same
parameter names, kinds (`*` marks keyword-only) and defaults as `inspect.signature`, and that the
Request fields listed equal the dataclass fields. Keep each file compact.

**`docs/api/base.md`** (~75 lines, ~950 tokens), content:

```
# Backend reference 1: basics (import everything from chatbook.core.api)

Notation in task specs: db = request.db, me = request.me.id.

## Routing
@route(method, pattern, *, public=False)   keep the stub's decorators exactly as they are
Request: method, path, params, query, body, headers, user, token, db, now
  params: {name} path segments (str); query: dict of str; body: parsed JSON or None
  now: int milliseconds; me: the logged-in User (login is already checked unless public)
Response(status, body)        body must be JSON-serializable (dict, list, str, int, bool, None)
HTTPError(status, message)    raise it; the app answers {"error": message}
The app commits after your handler returns a status < 400 and rolls back otherwise.

## Database (request.db), always ? placeholders, never f-strings or + for SQL
Db: the type of request.db (import it from chatbook.core.api to annotate helpers: db: Db)
one(sql, *args) -> dict | None          first row
all(sql, *args) -> list[dict]           all rows
value(sql, *args) -> Any                first column of the first row, or None
run(sql, *args) -> int                  INSERT: the new id; UPDATE/DELETE: rows changed
page(sql, *args, limit) -> (rows, has_more)   adds LIMIT itself (your SQL has none)
A single tuple works too: db.one("SELECT * FROM users WHERE id = ?", (uid,))
Values from rows are Any: wrap with int(...) / str(...) where a typed value is needed.

## Validation (each raises the error itself)
body_str(request, name, *, min_len=1, max_len=1000, strip=True) -> str           400
body_id(request, name) -> int                    positive int, not bool          400
body_ids(request, name, *, max_items=100) -> list[int]   duplicates removed      400
path_id(request, name="id") -> int               bad or missing id               404
query_str(request, name, *, max_len, min_len=1) -> str      stripped             400
query_int(request, name, *, default, lo, hi) -> int         missing -> default   400
query_opt_int(request, name) -> int | None                  missing -> None      400

## Users
User: id, username, display_name          (request.me is a User)
user_json(u) -> dict                       {"id", "username", "display_name"} from a User or a row
get_user(db, user_id) -> dict | None       the full users row
require_user(db, user_id) -> dict          404 if missing
create_user(db, username, password, display_name, now) -> User     409 if the username is taken
check_password(db, username, password) -> User | None
new_session(db, user_id, now) -> str       a new login token

## Tables
users(id, username, display_name, bio, password_hash, created_at, last_seen_at)

## Example handler (style to copy)
from typing import Any
from chatbook.core.api import HTTPError, Request, Response, body_str, path_id, route

@route("PUT", "/api/notes/{id}")
def edit_note(request: Request) -> Response:
    note_id = path_id(request)
    row = request.db.one("SELECT * FROM notes WHERE id = ?", note_id)
    if row is None or row["owner_id"] != request.me.id:
        raise HTTPError(404, "note not found")
    text = body_str(request, "text", max_len=500)
    request.db.run("UPDATE notes SET text = ? WHERE id = ?", text, note_id)
    note: dict[str, Any] = {"id": note_id, "text": text}
    return Response(200, {"note": note})
```

**`docs/api/social.md`** (~20 lines): `are_friends(db, a, b) -> bool`, `befriend(db, a, b, now)
-> None` (both directions; deletes pending requests between them), `unfriend(db, a, b) -> None`,
`relationship(db, me, other) -> str` (the five values), `friend_ids(db, user_id) -> list[int]`;
tables `friend_requests(id, from_id, to_id, created_at)` (UNIQUE from_id, to_id) and
`friendships(user_id, friend_id, created_at)` (one row per direction).

**`docs/api/chat.md`** (~30 lines): every `core/chat.py` function with one-line meaning (3.6),
shapes M and C, tables `conversations(id, kind, title, direct_key, created_by, created_at,
last_message_id)`, `members(conversation_id, user_id, joined_at, last_read_id)`,
`messages(id, conversation_id, sender_id, body, created_at)`.

**`docs/api/posts.md`** (~15 lines): `visible_post(db, post_id, viewer_id) -> dict` (404 unless
author is the viewer or a friend); tables `posts(id, author_id, body, created_at)`,
`likes(post_id, user_id, created_at)` (PK post_id, user_id), `comments(id, post_id, author_id,
body, created_at)`; plus `friendships` for feed queries.

**`docs/ui.md`** (~90 lines, ~1.1k tokens), content:

```
# Browser pages: the CB toolkit

A page is one file src/chatbook/features/<name>/ui.js, loaded after cb.js in its own function
scope. Use only CB.* and plain JavaScript (no modules, no browser objects).

## A page
CB.page('people', {
  title: 'People',            // browser tab title
  nav: 'People',              // top-bar label; leave out for pages opened by links
  order: 30,                  // top-bar position
  load: async (params) => {   // optional: fetch data with CB.api and return it
    return await CB.api('GET', '/api/users' + CB.qs({q: params.q}));
  },
  render: (data, params) => CB.el('div', {class: 'stack'}, ...),   // return the page
  poll: 3000,                 // optional: run load + render again every 3000 ms
});
params: the URL parameters of the page, always strings ({} when none).
The app runs load, then render, and shows the result. CB.refresh() runs both again.
Text typed into form fields survives refresh and poll.

## Nodes
CB.el(tag, props, ...children) -> node
  props: class, testid, title, type, value, placeholder, disabled, checked, name, onclick
  children: strings, numbers, nodes, arrays of them; null is skipped. Text is shown as text.
  onclick may be async: onclick: async () => { await CB.api(...); CB.refresh(); }
After creating a node you may only use: node.append(...), node.replaceChildren(...),
node.textContent = '...', node.disabled = true/false. To change the page, call CB.refresh().

CB.form({fields, submit, reset, onsubmit}) -> form node   (every form; CB.el('form') throws)
  fields: [{name, label, type, value, options}]
    type: 'text' (default), 'password', 'textarea', 'select', 'checkboxes'
    options (select, checkboxes): [{value: '2', label: 'Bob'}]   values are strings
    value: initial text (text, password, textarea) or selected value (select)
  submit: the button label; reset: true clears the text fields after a successful onsubmit
  onsubmit: async (values) => { ... }   values.name is a string; checkboxes give a string array

## Server
await CB.api(method, path, body) -> the JSON answer. An error answer is shown to the user and
stops your function; the app handles it, so never write try/catch. 401 logs the user out.
CB.qs({q: 'bo', limit: 20}) -> '?q=bo&limit=20' (empty values are skipped)

## Navigation and session
CB.go(name, params)  opens a page: CB.go('chat', {id: 5}) gives params {id: '5'}
CB.refresh()         CB.me (the logged-in user: {id, username, display_name})
CB.login(token, user) stores the session and opens 'inbox'    CB.logout()    CB.reloadMe()
CB.every(ms, fn)     runs fn now and every ms while logged in; call it at the top of the file

## Helpers
CB.avatar(user) -> node          CB.userLink(user) -> node (click opens the profile)
CB.time(ms) -> '14:05'           CB.plural(3, 'friend') -> '3 friends'
CB.short(text, 60) -> the first 60 characters + '...' when longer
CB.toast(text)                   CB.badge(pageName, n)  (n <= 0 hides it)

## CSS classes
stack (column with gaps), row (side by side), item (list row), unread, card, muted, badge,
messages (chat list), msg (bubble), mine (my bubble), danger (red button), narrow (thin column)

## Rejected by the gate
document, window, globalThis, fetch, XMLHttpRequest, innerHTML, outerHTML,
insertAdjacentHTML, eval, new Function, setTimeout, setInterval, localStorage, sessionStorage,
addEventListener, classList, style, setAttribute, querySelector, getElementById, import, require

## Example
CB.page('notes', {
  title: 'Notes', nav: 'Notes', order: 60,
  load: () => CB.api('GET', '/api/notes'),
  render: (data) => CB.el('div', {class: 'stack'},
    CB.el('h2', {}, 'Notes (' + data.notes.length + ')'),
    data.notes.length
      ? data.notes.map((n) => CB.el('div', {class: 'item'},
          CB.el('span', {}, n.text),
          CB.el('button', {testid: 'del-' + n.id, onclick: async () => {
            await CB.api('DELETE', '/api/notes/' + n.id);
            CB.refresh();
          }}, 'Delete')))
      : CB.el('p', {class: 'muted'}, 'No notes yet'),
    CB.form({fields: [{name: 'text', label: 'New note'}], submit: 'Add', reset: true,
      onsubmit: async (v) => {
        await CB.api('POST', '/api/notes', {text: v.text});
        CB.refresh();
      }})),
});
```

### 3.19 Frame tests (`tests/`, protected, a gate on every task, < 15 s total)

Rule: **frame tests never depend on a stub's behaviour** (stubs get implemented) and never on a
feature implementation, except the staff end-to-end flow tests added after a wave is merged.

- `test_registry.py`: shopapi's registry tests ported (+ `public`, ui discovery errors).
- `test_app.py`: 401/404/405/413/400, HEAD, JSON headers, transaction commit/rollback (a test
  feature module registered via a temporary package or by building `App` with explicit routes),
  `HTTPError` rollback, UNIQUE / PRIMARY KEY `IntegrityError` -> 409, NOT NULL / CHECK failures
  -> 500 or raised, 500 vs `raise_errors`, deeply nested / short / lone-surrogate bodies -> 400,
  `/api/session` GET/DELETE, `/api/health`, static files + CSP headers, ui.js IIFE wrapping,
  unknown static -> 404, threaded server lock (two requests serialised), a client stalled mid-body
  does not block others, silent and stalled sockets dropped after the handler timeout.
- `test_store.py` (tuple/list params, run/page semantics), `test_validate.py` (every row of 3.7),
  `test_users.py`, `test_social.py`, `test_chat.py` (every function and shape of 3.4-3.6).
- `test_testing.py`: every `Client` helper and `run_page` against `tests/fixtures/sample_page.js`.
- `test_ui_runtime.py`: the sample page through `run_page`: load/render, poll on tick, refresh,
  form reset, field-text preservation across a poll, `ApiError` toast and no error record,
  401-while-logged-in logout, 401-while-logged-out no logout, `CB.go` string params, `every`
  jobs, unknown `CB.el` prop -> error, duplicate page -> error, click/click_id/fill/submit/
  unmatched semantics, IIFE isolation (two files declaring the same top-level `const`), an
  unchanged poll keeps the mounted tree while a page-mutated tree is mounted again, a failed poll
  keeps the page and its typed text, `CB.el('form')` refused, an unprevented submit recorded,
  fake-DOM strictness (`appendChild` of a string, `childNodes.map`, `children.forEach`, select
  values).
- `test_route_map.py`: `create_app().routes` equals the route table exactly; `uirun load_all` over
  every `features/*/ui.js` has no errors and equals the page table exactly.
- `test_api_doc.py` (3.18), `test_check_extra.py` (the tool on small fixture strings, including
  schema SQL vs English words and every way of building SQL at run time; and the CONTRACT
  check of 3.16 item 6 on a stub of each kind: unchanged stubs pass, code and comments below
  the block pass, with LF or CRLF; a deleted, edited, moved-below-code or `//`-extended block
  and a deleted file each fail with the line, message and the block to restore; a missing
  snapshot fails; `--write-contracts` makes the snapshot; `--restore-contracts` puts back a
  deleted block (blank lines first, a worker's own docstring replaced, `from __future__`
  kept first, comments above kept, a ui.js with its own comments, code that does not compile)
  and leaves byte for byte every block with a trace (edited, first line edited, only the first
  line left, moved, code above, `//`-extended, the word CONTRACT in a comment), a string
  sharing its line, a non-UTF-8 file and a deleted file; it keeps CRLF and a byte-order mark,
  is idempotent, writes nothing for a missing snapshot or a path outside
  `features/<name>/(handler.py|ui.js)`, and after it the gate passes the restored files and
  still reports the others; restore then ruff `check --fix` and `format` (the autofix order)
  leave files that pass both ruff gates and check_extra with the block untouched; and on the
  repo itself `tools/contracts.json` lists every `features/*/handler.py` and `ui.js` (else the
  message tells workers not to add such files) and equals what `--write-contracts` would
  write, so staff cannot forget to regenerate it. A file whose block
  a worker damaged is left out of that last comparison because the gate already reports it
  with the text to restore: one report instead of two, which would halve the worker's
  feedback budget; gate + test together still pin the snapshot exactly), `test_demo.py`
  (`seed` on an empty DB through core only).
- Added by staff after waves: `test_flow_social.py` (after W1: register, login, search, request,
  accept, unfriend over HTTP), `test_flow_chat.py` (after W2: dm, group, send, history, read,
  updates), `test_flow_feed.py` (after W4).

---

## 4. Harness configuration: `harness/swarm.toml`

Relative paths resolve against the harness folder. Two targets share one task folder: the real
target `chatbook` (workers, explicit integrations) and `chatbook-oracle` (validate and dry-run
integrations only, on the clone). The engines are copied from the harness `swarm.toml` with
`model_settings` as an absolute path. One deliberate change: `--map-tokens 0` instead of 1024 on
every engine (8k context; every task names its stub and docs; the editor pass uses no map
anyway). A repo map would not help: the engine passes every protected path, `core/` and `docs/`
included, to aider as `--aiderignore`, so a map could only list the sibling feature stubs (which
invites cross-feature imports that archlint rejects), never the API. There is no map engine.

`forbidden_added` also blocks the file-level suppressions (`# ruff: noqa`, `# flake8: noqa`,
`# mypy: ...`, `# fmt: off|skip`, any-case `# NOQA`) that would switch a gate off for a whole
file, and its SQL f-string patterns match upper-case keywords only (case-insensitive ones
blocked English messages such as f"Select a {x}"; harness `3254599`); check_extra (3.16, item 5)
is the full check for SQL built at run time.

`autofix` runs after every agent attempt, before the guard and the gates, and the harness
ignores its exit codes (the gates decide). Its first step is
`{python} tools/check_extra.py --restore-contracts` (3.16 item 6, "Restore"), **before** the
ruff steps: ruff's fixer and formatter then fix the spacing below a restored block (one blank
line after the docstring is not enough before a `def`; ruff format wants two) and never change
the block itself (it comes from frame stubs that pass both ruff gates, a module docstring is
formatted the same whatever follows, and nothing precedes it). Run last, a restore would leave
that spacing to `ruff format --check`, a failure the worker cannot explain because it never
sees autofix. `tests/test_check_extra.py` runs this order. Because autofix runs before the
guard, it runs the worktree's `tools/check_extra.py` and snapshot even if a worker edited them
(aider cannot see `tools/**`, and the guard reverts them right after): that is no new power,
since the gates already execute worker code on the host (`sandbox = "none"`), and the gate
that decides runs the reverted tool. The worker's prompt lists the autofix commands.

```toml
# ChatBook harness config. 04_AgentSwarm is never modified; run every command as
#   uv run --project E:/Playground_Projects/04_AgentSwarm swarm \
#     -c E:/Playground_Projects/05_ChatBook/harness/swarm.toml -t <target> <cmd>
#
# NEVER run `validate` or `-e oracle` on target "chatbook": integrate would pick the oracle
# branches (run ids sort by engine name). Validate only on "chatbook-oracle".

[defaults]
target = "chatbook"
engine = "local-14b-arch"
max_iterations = 4
agent_timeout = 900
verify_timeout = 300
feedback_chars = 3000          # 8k-context model: keep retries small
acceptance_feedback = "full"
baseline_check = true
worktrees_dir = ".worktrees"   # harness/.worktrees/<target>/<run-id>
runs_dir = "runs"              # harness/runs/<run-id>

# ---------------------------------------------------------------------------
[targets.chatbook]
repo = "../chatbook"
base = "main"
tasks = "tasks"
rules_file = "AGENTS.md"
pythonpath = ["src"]
import_check = "chatbook"
sandbox = "none"               # gates need node on the host; the docker image has none
verify = [
  ["{python}", "-m", "ruff", "check", "."],
  ["{python}", "-m", "ruff", "format", "--check", "."],
  ["{python}", "-m", "mypy", "src"],
  ["{python}", "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"],
  ["{python}", "tools/check_extra.py"],
]
autofix = [                    # exit codes ignored; restore first, then ruff (see above)
  ["{python}", "tools/check_extra.py", "--restore-contracts"],
  ["{python}", "-m", "ruff", "check", "--fix", "--exit-zero", "--quiet", "."],
  ["{python}", "-m", "ruff", "format", "--quiet", "."],
]
protected = [
  "tests/**", "conftest.py", "pyproject.toml", "setup.cfg", "setup.py", "tox.ini",
  "pytest.ini", "mypy.ini", ".mypy.ini", "ruff.toml", ".ruff.toml", "sitecustomize.py",
  "usercustomize.py", "AGENTS.md", "CLAUDE.md", ".claude", ".git*", ".aider*",
  "package.json", "tools/**", "docs/**", "README.md",
  "src/chatbook/*.py", "src/chatbook/py.typed", "src/chatbook/app/**",
  "src/chatbook/__main__/**", "src/chatbook/testing/**", "src/chatbook/core/**",
  "src/chatbook/features/__init__.py",
]
context_files = []             # each task lists its own read-only references in `files`
forbidden_added = [
  '#\s*type:\s*ignore',
  '(?i)#\s*noqa',
  '(?i)#\s*(ruff|flake8)\s*:\s*noqa',
  '(?i)#\s*mypy\s*:',
  '(?i)#\s*(fmt|yapf)\s*:\s*(off|skip|disable)',
  '#\s*pragma:\s*no\s*cover',
  'pytest\.(mark\.)?(skip|xfail|importorskip)',
  'unittest\.skip',
  'collect_ignore',
  # Upper-case keywords only: check_extra's AST check (item 5) catches lower-case and split SQL,
  # and case-insensitive patterns here would block English messages such as f"Select a {x}".
  '(?<![\w])f"[^"\n]*\b(SELECT|INSERT|UPDATE|DELETE)\b',
  '''(?<![\w])f'[^'\n]*\b(SELECT|INSERT|UPDATE|DELETE)\b''',
]

[targets.chatbook.architecture]
root = "src"
packages = ["chatbook"]
independent = ["chatbook.features.*"]

[[targets.chatbook.architecture.forbid]]
from = "chatbook.core.**"
to = ["chatbook.features.**", "chatbook.app", "chatbook.__main__", "chatbook.testing"]
fix = "core is the stable base: it must not know the features, the app or the test kit."

[[targets.chatbook.architecture.forbid]]
from = "chatbook.features.**"
to = "chatbook.**"
allow = ["chatbook.core.api", "chatbook.features.**"]
fix = "Import only chatbook.core.api (see docs/api/*.md) and modules in your own feature folder."

[[targets.chatbook.architecture.forbid]]
from = "chatbook.features.**"
to = ["sqlite3.**", "time", "datetime.**", "os.**", "sys", "subprocess", "socket",
      "threading", "multiprocessing.**", "asyncio.**", "importlib.**", "urllib.**",
      "http.**", "wsgiref.**", "shutil", "pathlib", "pickle", "random", "secrets", "hashlib"]
fix = "Use request.db, request.now and the chatbook.core.api helpers instead."

[[targets.chatbook.architecture.forbid]]
from = "chatbook.testing"
to = "chatbook.features.**"
fix = "The test kit drives features through the app, never by import."

# ---------------------------------------------------------------------------
# Identical except `repo`: a throwaway clone used ONLY for validate and dry-run integrate.
[targets.chatbook-oracle]
repo = "../chatbook-oracle"
# ... every other key and the four [[...architecture.forbid]] tables copied verbatim from
# [targets.chatbook] (TOML has no anchors; keep the two blocks identical, diff them after edits).

# ---------------------------------------------------------------------------
[engines.local-14b-arch]           # default worker: qwen2.5-coder:14b, architect mode
kind = "aider"
model = "ollama_chat/qwen2.5-coder:14b"
env = { OLLAMA_API_BASE = "http://127.0.0.1:11434" }
model_settings = "E:/Playground_Projects/04_AgentSwarm/config/aider.model.settings.yml"
extra_args = ["--map-tokens", "0", "--architect"]

[engines.local-14b]                # fallback: one pass, whole-file edits
kind = "aider"
model = "ollama_chat/qwen2.5-coder:14b"
env = { OLLAMA_API_BASE = "http://127.0.0.1:11434" }
model_settings = "E:/Playground_Projects/04_AgentSwarm/config/aider.model.settings.yml"
extra_args = ["--map-tokens", "0"]

[engines.local-7b-arch]            # fallback: 16k context (num_ctx) for prompts that overflow
kind = "aider"
model = "ollama_chat/qwen2.5-coder:7b"
env = { OLLAMA_API_BASE = "http://127.0.0.1:11434" }
model_settings = "E:/Playground_Projects/04_AgentSwarm/config/aider.model.settings.yml"
extra_args = ["--map-tokens", "0", "--architect"]

[engines.local-7b]
kind = "aider"
model = "ollama_chat/qwen2.5-coder:7b"
env = { OLLAMA_API_BASE = "http://127.0.0.1:11434" }
model_settings = "E:/Playground_Projects/04_AgentSwarm/config/aider.model.settings.yml"
extra_args = ["--map-tokens", "0"]

# Only if the owner pulls qwen3-coder:30b (18 GB download; doubtful with 16 GB RAM):
# [engines.local-30b-arch]
# kind = "aider"
# model = "ollama_chat/qwen3-coder:30b"
# env = { OLLAMA_API_BASE = "http://127.0.0.1:11434" }
# model_settings = "E:/Playground_Projects/04_AgentSwarm/config/aider.model.settings.yml"
# extra_args = ["--map-tokens", "0", "--architect"]

[engines.oracle]
kind = "oracle"
```

The harness folder is its own git repo (versions task specs, hidden tests and patches):
`harness/.gitattributes` = `* text=auto eol=lf`; `harness/.gitignore` = `.worktrees/` and `runs/`.

---

## 5. `AGENTS.md` (product repo, verbatim; ~45 lines, ~600 tokens)

```markdown
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
```

---

## 6. Tasks

### 6.1 How a task is built (staff checklist)

Folder `harness/tasks/cb-NN-<name>/`:

1. **`task.toml`**:

   ```toml
   title = "<Feature>: <what it does>"
   type = "feat"
   files = [
     "src/chatbook/features/<name>/<handler.py | ui.js>",   # in scope -> editable (--file)
     "docs/api/base.md",                                     # backend; protected -> --read
     "docs/api/<domain>.md",                                 # backend, when the spec needs it
     # UI tasks instead: "docs/ui.md"
   ]
   scope = ["src/chatbook/features/<name>/**"]
   prompt = """
   Implement the feature `<name>` in `src/chatbook/features/<name>/<file>`. The file is a stub:
   keep its CONTRACT block and its <@route lines and function names | CB.page name, nav and
   order>, and replace the stub body with the implementation below.
   Reference: <docs/api/base.md and docs/api/<domain>.md | docs/ui.md> (read-only).
   Notation: db = request.db, me = request.me.id.

   <the task's Spec, verbatim from 6.3>

   Tables you may write: <...>.   (backend only)
   JSON keys, status codes, list order and quoted texts must match exactly; error message
   texts are not tested.
   """
   ```

   Prompt size: at most ~700 words. It is followed by the harness boilerplate (~650 tokens).

2. **The stub** in the frame commit (3.17): its CONTRACT block is the Spec condensed to <= 30
   lines, so the editor pass sees it even though it never sees `prompt.md`. If you change a
   block (or add or remove a stub), regenerate `tools/contracts.json` with
   `python tools/check_extra.py --write-contracts` and commit both (3.16 item 6).

3. **`acceptance/test_cbNN_<name>.py`**: imports only `pytest`, `importlib`, `re` and
   `chatbook.testing`. Rules:
   - API tests: `c = Client()` per test; state only through `Client` seeding helpers (or
     `c.db.run` for columns without a helper, such as `bio`); assertions on status, exact success
     JSON (built from `Account.json`, `c.now`, `c.message`, `c.conversation`) and side effects via
     `c.row`/`c.rows`/`c.are_friends`/`c.unread`. One error condition per request. Never call
     another feature's endpoint (frame routes like `/api/session` are fine).
   - UI tests: `run_page(...)` with mocked `api`; every test asserts `res.errors == []` and,
     where relevant, `res.unmatched == []` first. Assert only strings the spec quotes.
   - Fixture values differ from the prompt's examples (other names, ids, texts).
   - Last test: `importlib.import_module("chatbook.features.<name>.handler")` (backend) or
     `assert "<page>" in [p["name"] for p in run_page(...).pages]` (UI).
   - Every suite fails on the stub base (501 / "Coming soon" / no calls).

4. **`solution.patch`**: the staff implementation of the stub (only files in the task's folder),
   produced in a scratch worktree of `main` with
   `git -C <scratch> diff --output=<abs path>/solution.patch main -- src/chatbook/features/<name>`
   (git writes the file itself: LF, no PowerShell re-encoding). It must pass the gates and the
   hidden tests; `swarm -t chatbook-oracle validate cb-NN` proves it.

### 6.2 Complete example: cb-01

`task.toml`:

```toml
title = "Accounts: register and log in"
type = "feat"
files = ["src/chatbook/features/accounts/handler.py", "docs/api/base.md"]
scope = ["src/chatbook/features/accounts/**"]
prompt = """
Implement the feature `accounts` in `src/chatbook/features/accounts/handler.py`. The file is a
stub: keep its CONTRACT docstring, its two @route lines and the function names `register` and
`login`, and replace each `raise HTTPError(501, ...)` with the implementation below.
Reference: docs/api/base.md (read-only). Notation: db = request.db.

POST /api/auth/register  (public)  body {"username", "password", "display_name"}
  1. username = body_str(request, "username", max_len=20).lower()
     if not re.fullmatch(r"[a-z0-9_]{3,20}", username): 400
  2. password = body_str(request, "password", min_len=8, max_len=128, strip=False)
  3. display_name = body_str(request, "display_name", max_len=50)
  4. user = create_user(db, username, password, display_name, request.now)   (raises 409 itself)
  5. token = new_session(db, user.id, request.now)
  -> 201 {"token": token, "user": user_json(user)}

POST /api/auth/login  (public)  body {"username", "password"}
  1. username = body_str(request, "username", max_len=50).lower()
  2. password = body_str(request, "password", max_len=128, strip=False)
  3. user = check_password(db, username, password); None -> 401
  -> 200 {"token": new_session(db, user.id, request.now), "user": user_json(user)}

Tables you may write: users and sessions, only through create_user and new_session.
JSON keys and status codes must match exactly; error message texts are not tested.
"""
```

Stub `src/chatbook/features/accounts/handler.py` (frame commit):

```python
"""accounts: register and log in.

CONTRACT (keep this docstring; implement exactly this):
POST /api/auth/register (public) body {"username", "password", "display_name"}
  1. username = body_str(request, "username", max_len=20).lower()
     re.fullmatch(r"[a-z0-9_]{3,20}", username) fails -> 400
  2. password = body_str(request, "password", min_len=8, max_len=128, strip=False)
  3. display_name = body_str(request, "display_name", max_len=50)
  4. user = create_user(request.db, username, password, display_name, request.now)  (409)
  5. token = new_session(request.db, user.id, request.now)
  -> 201 {"token": token, "user": user_json(user)}
POST /api/auth/login (public) body {"username", "password"}
  1. username = body_str(request, "username", max_len=50).lower()
  2. password = body_str(request, "password", max_len=128, strip=False)
  3. user = check_password(request.db, username, password); None -> 401
  -> 200 {"token": new_session(request.db, user.id, request.now), "user": user_json(user)}
"""

from chatbook.core.api import HTTPError, Request, Response, route


@route("POST", "/api/auth/register", public=True)
def register(request: Request) -> Response:
    raise HTTPError(501, "not implemented")


@route("POST", "/api/auth/login", public=True)
def login(request: Request) -> Response:
    raise HTTPError(501, "not implemented")
```

`acceptance/test_cb01_accounts.py`:

```python
import importlib
from typing import Any

import pytest

from chatbook.testing import Client

GOOD = {"username": "mia_7", "password": "longpass1", "display_name": "Mia M"}


def test_register_creates_user_and_working_token() -> None:
    c = Client()
    r = c.post("/api/auth/register",
               {"username": "  Mia_7 ", "password": "longpass1", "display_name": " Mia M "})
    assert r.status == 201
    assert set(r.json) == {"token", "user"}
    assert r.json["user"] == {"id": 1, "username": "mia_7", "display_name": "Mia M"}
    me = c.get("/api/session", token=r.json["token"])
    assert (me.status, me.json) == (200, {"user": r.json["user"]})


def test_username_taken_ignores_case() -> None:
    c = Client()
    c.user("mia_7")
    assert c.post("/api/auth/register", GOOD | {"username": "MIA_7"}).status == 409


@pytest.mark.parametrize("change", [
    {"username": "ab"}, {"username": "a b c"}, {"username": "x" * 21}, {"username": 123},
    {"username": "bad-name"}, {"password": "x" * 7}, {"password": 12345678},
    {"display_name": "   "}, {"display_name": "y" * 51},
])
def test_register_rejects_bad_fields(change: dict[str, Any]) -> None:
    assert Client().post("/api/auth/register", GOOD | change).status == 400


@pytest.mark.parametrize("missing", ["username", "password", "display_name"])
def test_register_rejects_missing_field(missing: str) -> None:
    body = {k: v for k, v in GOOD.items() if k != missing}
    assert Client().post("/api/auth/register", body).status == 400


def test_register_rejects_non_object_body() -> None:
    assert Client().post("/api/auth/register", ["mia_7"]).status == 400


def test_login_returns_new_token() -> None:
    c = Client()
    noah = c.user("noah", "Noah N", password="secret-pass")
    r = c.post("/api/auth/login", {"username": " NOAH ", "password": "secret-pass"})
    assert r.status == 200
    assert r.json["user"] == noah.json
    assert r.json["token"] != noah.token
    assert c.get("/api/session", token=r.json["token"]).status == 200


def test_login_failures_are_401() -> None:
    c = Client()
    c.user("noah", password="secret-pass")
    assert c.post("/api/auth/login", {"username": "noah", "password": "wrong-pass"}).status == 401
    assert c.post("/api/auth/login", {"username": "ghost", "password": "secret-pass"}).status == 401


def test_password_is_not_stripped() -> None:
    c = Client()
    c.post("/api/auth/register", GOOD | {"password": " spaced pass "})
    assert c.post("/api/auth/login", {"username": "mia_7", "password": "spaced pass"}).status == 401
    assert c.post("/api/auth/login",
                  {"username": "mia_7", "password": " spaced pass "}).status == 200


def test_lives_in_its_own_feature_folder() -> None:
    importlib.import_module("chatbook.features.accounts.handler")
```

### 6.3 Complete UI example: excerpt of cb-18 (page_chat) hidden tests

```python
from typing import Any

from chatbook.testing import ALICE, ERIN, FRANK, fake_conversation, fake_message, run_page

GROUP = fake_conversation(3, "group", "Ski trip", [ALICE, ERIN, FRANK], unread=2)
M10 = fake_message(10, ERIN, "hi there")
M11 = fake_message(11, ALICE, "on my way")
M12 = fake_message(12, ALICE, "hello")
READS = [{"user_id": 1, "last_read_id": 11}, {"user_id": 5, "last_read_id": 11},
         {"user_id": 6, "last_read_id": 0}]


def api(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "GET /api/conversations/3": [{"conversation": GROUP, "reads": READS},
                                     {"conversation": GROUP | {"unread": 0}, "reads": READS}],
        "GET /api/conversations/3/messages?limit=50": [
            {"messages": [M10, M11], "has_more": True},
            {"messages": [M10, M11, M12], "has_more": True}],
        "POST /api/conversations/3/read": {"conversation_id": 3, "last_read_id": 11, "unread": 0},
        "POST /api/conversations/3/messages": {"message": M12},
    }
    return base | over


def test_loads_thread_then_marks_read() -> None:
    res = run_page("page_chat", "chat", params={"id": "3"}, api=api())
    assert res.errors == [] and res.unmatched == []
    assert res.calls[:3] == [
        ["GET", "/api/conversations/3", None],
        ["GET", "/api/conversations/3/messages?limit=50", None],
        ["POST", "/api/conversations/3/read", None],
    ]
    assert "Ski trip" in res.text and "Erin Evans: hi there" in res.text
    assert "Alice Adams, Erin Evans, Frank Fox" in res.text
    assert {"Group settings", "Show older", "Send"} <= set(res.labels)
    assert "Seen" in res.text           # Erin read up to 11 = my last message


def test_send_trims_and_refreshes() -> None:
    res = run_page("page_chat", "chat", params={"id": "3"}, api=api(),
                   steps=[{"submit": "Send", "values": {"body": "  hello "}}])
    assert res.errors == []
    assert ["POST", "/api/conversations/3/messages", {"body": "hello"}] in res.calls
    assert res.count("GET", "/api/conversations/3/messages?limit=50") == 2
    assert "Alice Adams: hello" in res.text
```

### 6.4 Sizing rules (worker limits)

- One feature folder per task; the worker edits one file (stub) of at most ~120 lines including
  the CONTRACT block (gate limit 180).
- Prompt <= ~700 words; references per task: AGENTS.md (~600 tokens) + docs (~1.1-1.4k tokens).
  Architect call input ~3.5-4.5k tokens; editor call input ~4k + whole-file output <= ~1.6k.
- Specs give: exact route and decorator, check order with status codes, the frame helper for each
  step, SQL text where a join, filter or ordering is involved, exact JSON keys, list order, quoted
  UI texts and labels (ASCII only), and the testid of every repeated control.

### 6.5 Task list

Notation in every spec: `db = request.db`, `me = request.me.id`. "->" is the success response.
Each task: scope `["src/chatbook/features/<folder>/**"]`; files = the stub + the listed docs.

| Wave | Tasks | Theme | Gate to next wave |
|---|---|---|---|
| W1 calibration | cb-01..cb-06 | accounts, people search, friend requests, friends, login page | >= 4/6 pass, token budget measured |
| W2 | cb-07..cb-16 | chat API, groups, updates, profiles API, people and friends pages | merged, flow test added |
| W3 (MVP done) | cb-17..cb-22 | inbox, chat, new group, group settings, profile page, badges | **MVP smoke test passes** |
| W4 stretch | cb-23..cb-27 | posts/feed, likes, comments, presence, suggestions | merged |
| W5 stretch | cb-28..cb-30 | feed page, post page, discover page | merged, final smoke |

Every task's hidden tests depend only on the frame (Client seeding or mocked API), so any order
is valid for the harness; the waves are calibration, product checkpoints and merge batches.

---

#### Wave 1

**cb-01 accounts: register and log in** (S, ~45 lines; folder `accounts`; docs `base.md`)
Spec and tests: section 6.2.

**cb-02 people: search people** (S, ~30; `people`; `base.md`, `social.md`)

```
GET /api/users?q=&limit=
  1. q = query_str(request, "q", max_len=50)
  2. limit = query_int(request, "limit", default=20, lo=1, hi=50)
  3. rows = db.all("SELECT * FROM users WHERE id != ? ORDER BY username", me)
  4. keep the rows where q.casefold() is in row["username"].casefold() or in
     row["display_name"].casefold()   (plain Python `in`, no SQL LIKE)
  5. keep the first `limit` rows
  -> 200 {"users": [{**user_json(row), "relationship": relationship(db, me, row["id"])} ...]}
```

Hidden tests: users `alice`("Alice Smith"), `bob`("Bobby"), `alfred`("Al Fred"), `zed`("Zed
Hale"), `maya`("Valerie"); `c.befriend(bob, alfred)`, `c.friend_request(alice, bob)`. As bob,
`q=AL` -> `[alfred (friends), alice (request_received), maya (none)]` exactly (username order;
maya matches by display name only; bob excluded). As alfred, `q=al` excludes alfred. `limit=1` ->
only alfred. User `pct` ("Pct 100%"): `q=%25` -> only pct (literal `%`). 400 for: q missing,
`q=%20%20`, 51-char q, `limit=0`, `limit=51`, `limit=abc`. Import check.

**cb-03 friend_requests: send and list** (M, ~65; `friend_requests`; `base.md`, `social.md`)

```
R(row) = {"id": row["id"], "from": user_json(require_user(db, row["from_id"])),
          "to": user_json(require_user(db, row["to_id"])), "created_at": row["created_at"]}
POST /api/friends/requests  body {"user_id"}  checks in this order:
  1. other = body_id(request, "user_id")
  2. other == me -> 400
  3. require_user(db, other)                                              (404)
  4. are_friends(db, me, other) -> 409
  5. a friend_requests row with from_id=me, to_id=other exists -> 409
  6. a row with from_id=other, to_id=me exists: befriend(db, me, other, request.now)
     -> 200 {"status": "friends", "friend": user_json(require_user(db, other))}
  7. rid = db.run("INSERT INTO friend_requests (from_id, to_id, created_at) VALUES (?, ?, ?)",
                  me, other, request.now)
     -> 201 {"status": "pending",
             "request": R({"id": rid, "from_id": me, "to_id": other, "created_at": request.now})}
GET /api/friends/requests
  -> 200 {"incoming": [R(row) for rows WHERE to_id = me ORDER BY id DESC],
          "outgoing": [R(row) for rows WHERE from_id = me ORDER BY id DESC]}
Tables you may write: friend_requests (insert); friendships only through befriend.
```

Hidden tests: users a, b, d, e. a->b: 201 `{"status": "pending", "request": {"id": 1, "from":
a.json, "to": b.json, "created_at": c.now}}`, row present. Repeat -> 409. After `c.befriend(a,
d)`, a->d -> 409. Self -> 400; `999` -> 404; `"x"`, `true`, `0`, missing -> 400. Auto-accept:
`c.friend_request(e, a)` then a->e: 200 `{"status": "friends", "friend": e.json}`,
`c.are_friends(a, e)`, `c.rows("SELECT * FROM friend_requests WHERE from_id = ?", e.id) == []`.
Listing: seed `c.friend_request(b, a)`, `c.tick()`, `c.friend_request(d, a)`, `c.tick()`,
`c.friend_request(a, e)`: as a, `incoming` = [R(d->a), R(b->a)] (id desc), `outgoing` = [R(a->e)];
a user with nothing gets `{"incoming": [], "outgoing": []}`.

**cb-04 friend_answers: accept, decline, cancel** (S, ~40; `friend_answers`; `base.md`, `social.md`)

```
In every route: rid = path_id(request)
               row = db.one("SELECT * FROM friend_requests WHERE id = ?", rid)
POST /api/friends/requests/{id}/accept
  row is None or row["to_id"] != me -> 404
  befriend(db, row["from_id"], me, request.now)        (this also deletes the request)
  -> 200 {"friend": user_json(require_user(db, row["from_id"]))}
POST /api/friends/requests/{id}/decline
  row is None or row["to_id"] != me -> 404
  db.run("DELETE FROM friend_requests WHERE id = ?", rid)  -> 200 {"declined": rid}
DELETE /api/friends/requests/{id}
  row is None or row["from_id"] != me -> 404
  db.run("DELETE FROM friend_requests WHERE id = ?", rid)  -> 200 {"cancelled": rid}
Tables you may write: friend_requests (delete); friendships only through befriend.
```

Hidden tests: `rid = c.friend_request(f, g)` (names differ from the prompt). g accepts: 200
`{"friend": f.json}`, `c.are_friends(f, g)`, the row is gone. Sender accepts -> 404; sender
declines -> 404; recipient cancels -> 404. Sender cancels: 200 `{"cancelled": rid}`, row gone.
Recipient declines: 200 `{"declined": rid}`, row gone, not friends. Unknown `999` and `abc` ->
404 on all three routes. Already-answered id -> 404.

**cb-05 friends: list and unfriend** (S, ~30; `friends`; `base.md`, `social.md`)

```
GET /api/friends
  rows = db.all("SELECT u.* FROM friendships f JOIN users u ON u.id = f.friend_id"
                " WHERE f.user_id = ?", me)        (adjacent string literals, not +)
  sort rows by (row["display_name"].casefold(), row["id"])
  -> 200 {"friends": [user_json(r) for r in rows]}
DELETE /api/friends/{id}
  uid = path_id(request)
  not are_friends(db, me, uid) -> 404
  unfriend(db, me, uid)  -> 200 {"removed": uid}
Tables you may write: friendships only through unfriend.
```

Hidden tests: a befriends `bob`("bob"), `ann1`("Ann"), `ann2`("ann") created in that order ->
list `[ann1, ann2, bob]` (case-insensitive, ties by id); a lonely user -> `[]`. DELETE bob: 200
`{"removed": bob.id}`, `c.are_friends(a, bob)` false both ways, bob's list no longer has a. Second
DELETE -> 404; `999`, `x` -> 404; a non-friend id -> 404.

**cb-06 page_login: login and register page** (S, ~30; `page_login`; `ui.md`)

```
CB.page('login', {title: 'Welcome', public: true, render})      no nav, no load
render() -> CB.el('div', {class: 'stack narrow'}, these four, in this order:
  CB.el('h2', {}, 'Log in')
  CB.form({fields: [{name: 'username', label: 'Username'},
                    {name: 'password', label: 'Password', type: 'password'}],
           submit: 'Log in',
           onsubmit: async (v) => {
             const r = await CB.api('POST', '/api/auth/login',
                                    {username: v.username, password: v.password});
             CB.login(r.token, r.user); }})
  CB.el('h2', {}, 'Create account')
  CB.form({fields: [{name: 'username', label: 'Username'},
                    {name: 'display_name', label: 'Display name'},
                    {name: 'password', label: 'Password', type: 'password'}],
           submit: 'Create account',
           onsubmit: async (v) => {
             const r = await CB.api('POST', '/api/auth/register',
                 {username: v.username, password: v.password, display_name: v.display_name});
             CB.login(r.token, r.user); }}))
Server answers: {token, user}. No try/catch.
```

Hidden tests (`me=None`): page `login` registered with `public` true and `nav` null; `forms ==
[{"submit": "Log in", "fields": ["username", "password"], ...}, {"submit": "Create account",
"fields": ["username", "display_name", "password"], ...}]` and both password types are
`password`; text contains "Log in" and "Create account". Submit "Log in" with `{"username":
"carol", "password": "pw-123456"}` against mocked `{"token": "tok-L", "user": CAROL}`: `calls ==
[["POST", "/api/auth/login", {"username": "carol", "password": "pw-123456"}]]`, `session ==
[["login", "tok-L", CAROL]]`, `nav == [["inbox", {}]]`. Submit "Create account" likewise (exact
body with `display_name`). Mocked `{"$status": 401, "error": "wrong username or password"}`:
`session == []`, `toasts == ["wrong username or password"]`, `errors == []`.

---

#### Wave 2

**cb-07 dm: open a direct conversation** (S, ~30; `dm`; `base.md`, `social.md`, `chat.md`)

```
POST /api/dm  body {"user_id"}  checks in this order:
  1. other = body_id(request, "user_id")
  2. other == me -> 400
  3. require_user(db, other)                                   (404)
  4. not are_friends(db, me, other) -> 403
  5. cid = find_direct(db, me, other)
     found -> status 200; else cid = create_conversation(db, "direct", "", me, [other],
     request.now) and status 201
  -> status {"conversation": conversation_json(db, cid, me)}
Tables you may write: conversations and members only through create_conversation.
```

Hidden tests: `a = c.user("gina")`, `b = c.user("hank", "Hank Hill")`, stranger x;
`c.befriend(a, b)`. First POST: 201 `{"conversation": {"id": 1, "kind": "direct", "title": "Hank
Hill", "members": [a.json, b.json], "last_message": None, "unread": 0, "updated_at": c.now}}`.
Second: 200, same id; b->a: 200, same id, title "Gina". One conversations row. x -> 403; `999`
-> 404; self, `"2"`, missing -> 400.

**cb-08 groups: create and rename** (M, ~50; `groups`; `base.md`, `social.md`, `chat.md`)

```
POST /api/groups  body {"title", "member_ids"}  checks in this order:
  1. title = body_str(request, "title", max_len=50)
  2. ids = [i for i in body_ids(request, "member_ids") if i != me]
  3. not ids -> 400;  len(ids) > 49 -> 400
  4. for each id in ids, in order: require_user(db, id) (404); not are_friends(db, me, id) -> 403
  5. cid = create_conversation(db, "group", title, me, ids, request.now)
  -> 201 {"conversation": conversation_json(db, cid, me)}
PUT /api/groups/{id}  body {"title"}
  1. cid = path_id(request); conv = require_member(db, cid, me)      (404)
  2. conv["kind"] != "group" -> 400
  3. title = body_str(request, "title", max_len=50)
  4. db.run("UPDATE conversations SET title = ? WHERE id = ?", title, cid)
  -> 200 {"conversation": conversation_json(db, cid, me)}
Tables you may write: conversations.title; conversations and members only through
create_conversation.
```

Hidden tests: a friends with b and d; stranger x. Create `{"title": " Ski ", "member_ids": [d.id,
b.id, a.id, b.id]}`: 201, `members == [a.json, b.json, d.json]`, title "Ski", `last_message`
None. `[]`, `[a.id]`, `"x"`, `[true]` -> 400; `[x.id]` -> 403; `[999]` -> 404; 51-char title ->
400. Rename: `g = c.group(a, [b], "Old")`; b PUTs `{"title": "New"}` -> 200, title "New" (row
check); x -> 404; `abc` -> 404; renaming `c.dm(a, b)` -> 400; empty title -> 400.

**cb-09 group_members: add and leave** (S, ~45; `group_members`; `base.md`, `social.md`, `chat.md`)

```
POST /api/groups/{id}/members  body {"user_id"}  checks in this order:
  1. cid = path_id(request); conv = require_member(db, cid, me)      (404)
  2. conv["kind"] != "group" -> 400
  3. uid = body_id(request, "user_id")
  4. require_user(db, uid)                                            (404)
  5. uid in member_ids(db, cid) -> 409
  6. not are_friends(db, me, uid) -> 403
  7. add_member(db, cid, uid, request.now)
  -> 200 {"conversation": conversation_json(db, cid, me)}
DELETE /api/groups/{id}/members/me
  1. cid = path_id(request); conv = require_member(db, cid, me)      (404)
  2. conv["kind"] != "group" -> 400
  3. remove_member(db, cid, me)
  -> 200 {"left": cid}
Tables you may write: members only through add_member and remove_member.
```

Hidden tests: `g = c.group(a, [b])`, `c.send(b, g, "old")`, `c.befriend(a, d)`. Add d: 200,
members `[a, b, d]`, `c.unread(d, g) == 0`. Add d again -> 409; stranger -> 403; `999` -> 404;
outsider adding -> 404; add to `c.dm(a, b)` -> 400; `{"user_id": "x"}` -> 400. b leaves: 200
`{"left": g}`, b not in `c.rows("SELECT user_id FROM members WHERE conversation_id = ?", g)`;
b leaves again -> 404; leave a dm -> 400.

**cb-10 conversations: inbox list and detail** (S, ~30; `conversations`; `base.md`, `chat.md`)

```
GET /api/conversations
  rows = db.all("SELECT conversation_id FROM members WHERE user_id = ?", me)
  items = [conversation_json(db, r["conversation_id"], me) for r in rows]
  items.sort(key=lambda c: (c["updated_at"], c["id"]), reverse=True)
  -> 200 {"conversations": items}
GET /api/conversations/{id}
  cid = path_id(request); require_member(db, cid, me)                 (404)
  reads = [{"user_id": r["user_id"], "last_read_id": r["last_read_id"]} for r in db.all(
      "SELECT user_id, last_read_id FROM members WHERE conversation_id = ? ORDER BY user_id", cid)]
  -> 200 {"conversation": conversation_json(db, cid, me), "reads": reads}
Read-only.
```

Hidden tests: `d1 = c.dm(a, b)`; `c.tick()`; `g = c.group(a, [b, e], "Trip")`; `c.tick()`;
`m = c.send(b, d1, "yo")`. a's list `== [c.conversation(d1, a), c.conversation(g, a)]`
(d1 first: newer activity; `unread` 1, last body "yo"); e's list `[g]`; a lonely user `[]`.
Ties: two conversations created without a tick sort by id desc. Detail: `m2 = c.send(a, d1,
"hi")`; as b: `reads == [{"user_id": a.id, "last_read_id": m2}, {"user_id": b.id,
"last_read_id": m}]` and `conversation == c.conversation(d1, b)`. Outsider, `999`, `abc` -> 404.

**cb-11 chat_send: send a message and mark read** (S, ~35; `chat_send`; `base.md`, `social.md`, `chat.md`)

```
POST /api/conversations/{id}/messages  body {"body"}  checks in this order:
  1. cid = path_id(request); conv = require_member(db, cid, me)      (404)
  2. text = body_str(request, "body", max_len=2000)
  3. if conv["kind"] == "direct": other = the id in member_ids(db, cid) that is not me;
     not are_friends(db, me, other) -> 403
  -> 201 {"message": post_message(db, cid, me, text, request.now)}
POST /api/conversations/{id}/read   (no body)
  1. cid = path_id(request); require_member(db, cid, me)              (404)
  2. last = mark_read(db, cid, me)
  -> 200 {"conversation_id": cid, "last_read_id": last, "unread": unread_count(db, cid, me)}
Tables you may write: messages, conversations.last_message_id and members.last_read_id only
through post_message and mark_read.
```

Hidden tests: `c.befriend(a, b)`, `cid = c.dm(a, b)`. a sends `"  hi  "`: 201 `{"message": {"id":
1, "conversation_id": cid, "sender": a.json, "body": "hi", "created_at": c.now}}`;
`c.unread(b, cid) == 1`; `c.unread(a, cid) == 0`. 400 for `""`, `"   "`, 2001 chars, `5`, missing
body. Outsider -> 404; `abc` -> 404. After `c.unfriend(a, b)`: dm send -> 403, but a group with
the same two still accepts (201). Read: b gets three messages from a; b POSTs read -> 200
`{"conversation_id": cid, "last_read_id": <last id>, "unread": 0}`; read on an empty conversation
-> `last_read_id` 0.

**cb-12 chat_history: message history** (S, ~25; `chat_history`; `base.md`, `chat.md`)

```
GET /api/conversations/{id}/messages?limit=&before=
  1. cid = path_id(request); require_member(db, cid, me)              (404)
  2. limit = query_int(request, "limit", default=50, lo=1, hi=200)
  3. before = query_opt_int(request, "before")
     cursor = before if before is not None else 2**62
  4. rows, more = db.page("SELECT * FROM messages WHERE conversation_id = ? AND id < ?"
                          " ORDER BY id DESC", cid, cursor, limit=limit)
  5. rows.reverse()                      (oldest first)
  -> 200 {"messages": [message_json(db, r) for r in rows], "has_more": more}
Read-only.
```

Hidden tests: `cid = c.dm(a, b)`, five `c.send` alternating senders (ids in `ids`), plus messages
in another conversation interleaved. Default: all five ascending (each `== c.message(id)`),
`has_more` False. `limit=2`: `ids[3:]`, True. `before=ids[2]`: `ids[:2]`, False.
`before=ids[3]&limit=1`: `[ids[2]]`, True. `before=0`: `[]`. 400: `limit=0`, `limit=201`,
`limit=x`, `before=x`, `before=-1`. Outsider -> 404.

**cb-13 updates: badge counts** (S, ~20; `updates`; `base.md`, `chat.md`)

```
GET /api/updates
  rows = db.all("SELECT conversation_id FROM members WHERE user_id = ?", me)
  counts = [unread_count(db, r["conversation_id"], me) for r in rows]
  -> 200 {"unread_total": sum(counts),
          "unread_conversations": the number of counts that are > 0,
          "friend_requests": int(db.value("SELECT COUNT(*) FROM friend_requests WHERE to_id = ?", me))}
Read-only.
```

Hidden tests: a in `d1 = c.dm(a, b)` and `g = c.group(b, [a, e])`; `c.send(b, d1)` twice,
`c.send(e, g)` once; outsider conversation `c.dm(e, f)` with messages; `c.friend_request(x, a)`,
`c.friend_request(y, a)`, `c.friend_request(a, z)`. a gets `{"unread_total": 3,
"unread_conversations": 2, "friend_requests": 2}`. After `c.read(a, d1)`: `{1, 1, 2}`. After
`c.leave(a, g)`: unread 0. a's own messages never count. A fresh user: all zero.

**cb-14 profiles: view and edit** (M, ~50; `profiles`; `base.md`, `social.md`)

```
P(row) = {"id": row["id"], "username": row["username"], "display_name": row["display_name"],
          "bio": row["bio"], "joined_at": row["created_at"],
          "relationship": rel, "friend_count": len(friend_ids(db, row["id"])),
          "request_id": rid}
  where rel = relationship(db, me, row["id"]) and rid =
    db.value("SELECT id FROM friend_requests WHERE from_id = ? AND to_id = ?", me, row["id"])
      if rel == "request_sent";
    db.value("SELECT id FROM friend_requests WHERE from_id = ? AND to_id = ?", row["id"], me)
      if rel == "request_received";
    else None
GET /api/users/{id}
  uid = path_id(request); row = require_user(db, uid)                (404)
  -> 200 {"user": P(row)}
PUT /api/profile  body {"display_name", "bio"}
  1. display_name = body_str(request, "display_name", max_len=50)
  2. bio = body_str(request, "bio", min_len=0, max_len=300)
  3. db.run("UPDATE users SET display_name = ?, bio = ? WHERE id = ?", display_name, bio, me)
  -> 200 {"user": P(require_user(db, me))}
Tables you may write: users.display_name and users.bio.
```

Hidden tests: `ann = c.user("ann", "Ann Lee")`, bio set with `c.db.run`; as b (stranger):
`{"user": {"id": ann.id, "username": "ann", "display_name": "Ann Lee", "bio": "hello",
"joined_at": <ann's created_at>, "relationship": "none", "friend_count": 0, "request_id":
None}}`. `rid = c.friend_request(b, ann)`: as b `request_sent`/rid; as ann viewing b
`request_received`/rid. Friends -> `friends`, `friend_count` 1, `request_id` None. Self ->
`self`. `999`, `x` -> 404. PUT `{"display_name": "  Ann L ", "bio": " hi "}` -> 200, P of ann
with "Ann L"/"hi" and `relationship` "self"; persisted (row). `bio: ""` allowed. 400: display
`""`, 51 chars, bio 301 chars, bio `5`, bio missing, list body.

**cb-15 page_people: people search page** (M, ~50; `page_people`; `ui.md`)

```
CB.page('people', {title: 'People', nav: 'People', order: 30, load, render})
load(params): q = (params.q || '').trim()
  if q === '' -> return {q: '', users: null}
  r = await CB.api('GET', '/api/users' + CB.qs({q}));  return {q, users: r.users}
render(d) -> CB.el('div', {class: 'stack'},
  CB.form({fields: [{name: 'q', label: 'Search people', value: d.q}], submit: 'Search',
           onsubmit: (v) => CB.go('people', {q: v.q.trim()})}),
  d.users === null      -> CB.el('p', {class: 'muted'}, 'Search by name or username')
  d.users.length === 0  -> CB.el('p', {class: 'muted'}, 'No people found')
  otherwise             -> d.users.map(row))
row(u) = CB.el('div', {class: 'item'}, CB.avatar(u), CB.userLink(u),
                CB.el('span', {class: 'muted'}, '@' + u.username), action(u))
action(u) by u.relationship:
  'none'             -> CB.el('button', {testid: 'add-' + u.id, onclick: async () => {
                          await CB.api('POST', '/api/friends/requests', {user_id: u.id});
                          CB.toast('Request sent'); CB.refresh(); }}, 'Add friend')
  'request_sent'     -> CB.el('button', {disabled: true}, 'Requested')
  'request_received' -> CB.el('button', {onclick: () => CB.go('friends')}, 'Respond')
  'friends'          -> CB.el('button', {testid: 'message-' + u.id, onclick: async () => {
                          const r = await CB.api('POST', '/api/dm', {user_id: u.id});
                          CB.go('chat', {id: r.conversation.id}); }}, 'Message')
Server answers: GET /api/users -> {users: [{id, username, display_name, relationship}]};
POST /api/dm -> {conversation: {id, ...}}.
```

Hidden tests (fixtures: four users ids 5-8 named differently from the prompt, one per
relationship; `q` "jo"): no params -> `calls == []`, text "Search by name or username", one form
`Search` with field `q`. Submit `{"q": "  jo "}` -> `nav == [["people", {"q": "jo"}]]` and then
`["GET", "/api/users?q=jo", None]` is called. With `params={"q": "jo"}`: first call that GET;
text contains `@<username>` and display names; labels include "Add friend", "Requested"
(disabled), "Respond", "Message". `click_id add-5` -> POST `{"user_id": 5}`, `toasts ==
["Request sent"]`, the GET counted twice. Click "Respond" -> `nav == [["friends", {}]]`.
`click_id message-8` with mocked `{"conversation": {"id": 12, ...}}` -> `nav == [["chat",
{"id": "12"}]]`. Empty result -> "No people found".

**cb-16 page_friends: friends page** (M, ~60; `page_friends`; `ui.md`)

```
CB.page('friends', {title: 'Friends', nav: 'Friends', order: 20, load, render})
load(): req = await CB.api('GET', '/api/friends/requests')
        fr = await CB.api('GET', '/api/friends');  return {req, friends: fr.friends}
render(d) -> CB.el('div', {class: 'stack'}, in this order:
  CB.el('h2', {}, 'Friend requests'),
  d.req.incoming.length ? d.req.incoming.map(incoming) : CB.el('p', {class: 'muted'}, 'No requests'),
  CB.el('h2', {}, 'Sent requests'),
  d.req.outgoing.length ? d.req.outgoing.map(outgoing) : CB.el('p', {class: 'muted'}, 'No sent requests'),
  CB.el('h2', {}, 'Friends (' + d.friends.length + ')'),
  d.friends.length ? d.friends.map(friend) : CB.el('p', {class: 'muted'}, 'No friends yet'))
incoming(r) = item: CB.avatar(r.from), CB.userLink(r.from),
  button testid 'accept-' + r.id 'Accept':
    await CB.api('POST', '/api/friends/requests/' + r.id + '/accept'); CB.refresh()
  button testid 'decline-' + r.id 'Decline':
    await CB.api('POST', '/api/friends/requests/' + r.id + '/decline'); CB.refresh()
outgoing(r) = item: CB.avatar(r.to), CB.userLink(r.to),
  button testid 'cancel-' + r.id 'Cancel':
    await CB.api('DELETE', '/api/friends/requests/' + r.id); CB.refresh()
friend(f) = item: CB.avatar(f), CB.userLink(f),
  button testid 'message-' + f.id 'Message':
    const r = await CB.api('POST', '/api/dm', {user_id: f.id}); CB.go('chat', {id: r.conversation.id})
  button testid 'unfriend-' + f.id 'Unfriend':
    await CB.api('DELETE', '/api/friends/' + f.id); CB.refresh()
("item" = CB.el('div', {class: 'item'}, ...).)
Server answers: GET /api/friends/requests -> {incoming: [R], outgoing: [R]} with
R = {id, from: U, to: U, created_at}; GET /api/friends -> {friends: [U]}.
```

Hidden tests: mocked incoming `fake_request(7, ERIN, ALICE)`, outgoing `fake_request(8, ALICE,
FRANK)`, friends `[CAROL]`: text contains "Erin Evans", "Frank Fox", "Carol Chen", "Friends (1)",
"Friend requests", "Sent requests". `click_id accept-7` -> `["POST",
"/api/friends/requests/7/accept", None]`, `count("GET", "/api/friends") == 2`. `decline-7`,
`cancel-8` (DELETE), `unfriend-3` (DELETE `/api/friends/3`) each followed by a reload.
`message-3` with mocked dm id 21 -> POST `{"user_id": 3}`, `nav == [["chat", {"id": "21"}]]`.
All empty -> "No requests", "No sent requests", "No friends yet", "Friends (0)".

---

#### Wave 3 (MVP complete)

**cb-17 page_inbox: conversation list** (S, ~35; `page_inbox`; `ui.md`)

```
CB.page('inbox', {title: 'Chats', nav: 'Chats', order: 10, poll: 3000, load, render})
load(): return await CB.api('GET', '/api/conversations')
render(d) -> CB.el('div', {class: 'stack'},
  CB.el('div', {class: 'row'}, CB.el('h2', {}, 'Chats'),
        CB.el('button', {onclick: () => CB.go('group_new')}, 'New group')),
  d.conversations.length ? d.conversations.map(item)
                         : CB.el('p', {class: 'muted'}, 'No conversations yet'))
item(c) = CB.el('div', {class: c.unread > 0 ? 'item unread' : 'item', testid: 'conv-' + c.id,
                        onclick: () => CB.go('chat', {id: c.id})},
  CB.el('b', {}, c.title),
  CB.el('div', {class: 'muted'}, c.last_message
      ? c.last_message.sender.display_name + ': ' + CB.short(c.last_message.body, 60)
      : 'No messages yet'),
  CB.el('small', {class: 'muted'}, CB.time(c.updated_at)),
  c.unread > 0 ? CB.el('span', {class: 'badge'}, String(c.unread)) : null)
Server answer: {conversations: [C]}, C = {id, kind, title, members, last_message: M | null,
unread, updated_at}, M = {id, conversation_id, sender: U, body, created_at}.
```

Hidden tests: mocked `[fake_conversation(4, "direct", "Erin Evans", [ALICE, ERIN],
last_message=fake_message(9, ERIN, <70-char ASCII body>, conversation_id=4), unread=2),
fake_conversation(7, "group", "Ski trip", [ALICE, ERIN, FRANK])]`: text contains "Erin Evans: " +
body[:60] + "...", not body[:61]; "No messages yet"; `["badge", "2"] in res.classes` and the
first item's class is `item unread`, the second's `item`. Click "New
group" -> `[["group_new", {}]]`; `click_id conv-7` -> `[["chat", {"id": "7"}]]`. `tick 3000` ->
`count("GET", "/api/conversations") == 2`. Empty -> "No conversations yet".

**cb-18 page_chat: the chat thread** (M, ~60; `page_chat`; `ui.md`)

```
CB.page('chat', {title: 'Chat', poll: 2000, load, render})          no nav
load(params):
  const limit = Number(params.limit || 50)
  const d = await CB.api('GET', '/api/conversations/' + params.id)        // {conversation, reads}
  const h = await CB.api('GET', '/api/conversations/' + params.id + '/messages' + CB.qs({limit}))
  if (d.conversation.unread > 0) await CB.api('POST', '/api/conversations/' + params.id + '/read')
  return {conv: d.conversation, reads: d.reads, messages: h.messages, hasMore: h.has_more, limit}
render(d, params) -> CB.el('div', {class: 'stack'}, in this order:
  CB.el('div', {class: 'row'}, CB.el('h2', {}, d.conv.title),
        d.conv.kind === 'group'
          ? CB.el('button', {onclick: () => CB.go('group', {id: params.id})}, 'Group settings')
          : null),
  CB.el('div', {class: 'muted'}, d.conv.members.map((m) => m.display_name).join(', ')),
  d.hasMore ? CB.el('button', {onclick: () => CB.go('chat', {id: params.id, limit: d.limit + 50})},
                    'Show older') : null,
  CB.el('div', {class: 'messages'},
        d.messages.length ? d.messages.map(row) : CB.el('p', {class: 'muted'}, 'Say hi!')),
  seen(d) ? CB.el('div', {class: 'muted'}, 'Seen') : null,
  CB.form({fields: [{name: 'body', label: 'Write a message'}], submit: 'Send', reset: true,
           onsubmit: async (v) => {
             const text = v.body.trim();
             if (text === '') return;
             await CB.api('POST', '/api/conversations/' + params.id + '/messages', {body: text});
             CB.refresh(); }}))
row(m) = CB.el('div', {class: m.sender.id === CB.me.id ? 'msg mine' : 'msg'}, CB.avatar(m.sender),
  CB.el('b', {}, m.sender.display_name), ': ', m.body, ' ',
  CB.el('small', {class: 'muted'}, CB.time(m.created_at)))
seen(d): mine = the messages whose sender.id === CB.me.id; none -> false; last = id of the last
  of them; true when some r in d.reads has r.user_id !== CB.me.id and r.last_read_id >= last
Server answers: GET /api/conversations/{id} -> {conversation: C, reads: [{user_id,
last_read_id}]}; GET .../messages -> {messages: [M], has_more}; POST .../messages ->
{message: M}; POST .../read -> {conversation_id, last_read_id, unread}.
```

Hidden tests: section 6.3 plus: `tick 2000` -> messages GET called again and no second read POST
(second conversation answer has `unread` 0); click "Show older" -> `nav == [["chat", {"id": "3",
"limit": "100"}]]` and `GET /api/conversations/3/messages?limit=100` is then called; click "Group
settings" -> `[["group", {"id": "3"}]]`; submit `{"body": "   "}` -> no POST to messages; a
direct conversation with no messages and `has_more` false -> "Say hi!", no "Group settings", no
"Show older", no "Seen"; reads where others are below my last id -> no "Seen".

**cb-19 page_group_new: create a group** (S, ~25; `page_group_new`; `ui.md`)

```
CB.page('group_new', {title: 'New group', load, render})            no nav
load(): return await CB.api('GET', '/api/friends')                   // {friends: [U]}
render(d) -> d.friends.length === 0
  ? CB.el('p', {class: 'muted'}, 'Add friends first')
  : CB.form({fields: [
        {name: 'title', label: 'Group name'},
        {name: 'members', label: 'Members', type: 'checkboxes',
         options: d.friends.map((f) => ({value: String(f.id), label: f.display_name}))}],
      submit: 'Create group',
      onsubmit: async (v) => {
        const r = await CB.api('POST', '/api/groups',
                               {title: v.title, member_ids: v.members.map(Number)});
        CB.go('chat', {id: r.conversation.id}); }})
Server answer of POST /api/groups: {conversation: C}.
```

Hidden tests: friends `[ERIN, FRANK]` (ids 5, 6): one form "Create group", fields `["title",
"members"]`, `types["members"] == "checkboxes"`, options `["5", "6"]`. Submit `{"title": "Ski",
"members": ["5", "6"]}` with mocked `{"conversation": {"id": 9, ...}}` -> `["POST", "/api/groups",
{"title": "Ski", "member_ids": [5, 6]}]`, `nav == [["chat", {"id": "9"}]]`. No friends -> text
"Add friends first", `forms == []`.

**cb-20 page_group: group settings** (M, ~55; `page_group`; `ui.md`)

```
CB.page('group', {title: 'Group settings', load, render})           no nav
load(params):
  const c = (await CB.api('GET', '/api/conversations/' + params.id)).conversation
  if (c.kind !== 'group') return {c, friends: []}
  const f = await CB.api('GET', '/api/friends');  return {c, friends: f.friends}
render(d, params) -> d.c.kind !== 'group' ? CB.el('p', {class: 'muted'}, 'Not a group')
 : CB.el('div', {class: 'stack'}, in this order:
  CB.el('div', {class: 'row'}, CB.el('h2', {}, d.c.title),
        CB.el('button', {onclick: () => CB.go('chat', {id: params.id})}, 'Back to chat')),
  CB.form({fields: [{name: 'title', label: 'Group name', value: d.c.title}], submit: 'Rename',
           onsubmit: async (v) => {
             await CB.api('PUT', '/api/groups/' + params.id, {title: v.title});
             CB.toast('Renamed'); CB.refresh(); }}),
  CB.el('h3', {}, 'Members (' + d.c.members.length + ')'),
  d.c.members.map((m) => CB.el('div', {class: 'item'}, CB.avatar(m), CB.userLink(m))),
  candidates.length ? CB.form({fields: [{name: 'user_id', label: 'Add a friend', type: 'select',
        options: candidates.map((f) => ({value: String(f.id), label: f.display_name}))}],
      submit: 'Add',
      onsubmit: async (v) => {
        await CB.api('POST', '/api/groups/' + params.id + '/members', {user_id: Number(v.user_id)});
        CB.refresh(); }}) : null,
  CB.el('button', {class: 'danger', onclick: async () => {
      await CB.api('DELETE', '/api/groups/' + params.id + '/members/me');
      CB.go('inbox'); }}, 'Leave group'))
candidates = d.friends that are not in d.c.members (compare ids)
```

Hidden tests: group "Ski trip" with members `[ALICE, ERIN]`, friends `[ERIN, FRANK, CAROL]`: text
"Ski trip", "Members (2)"; forms "Rename" (`values["title"] == "Ski trip"`) and "Add" (options
`["6", "3"]`). Submit "Rename" `{"title": "Alps"}` -> PUT `{"title": "Alps"}`, `toasts ==
["Renamed"]`, conversation GET twice. Submit "Add" `{"user_id": "6"}` -> POST `{"user_id": 6}`.
Click "Leave group" -> DELETE `/api/groups/3/members/me`, `nav == [["inbox", {}]]`. Click "Back to
chat" -> `[["chat", {"id": "3"}]]`. All friends already members -> no "Add" form. A direct
conversation -> "Not a group" and no `/api/friends` call.

**cb-21 page_profile: profile page** (M, ~60; `page_profile`; `ui.md`)

```
CB.page('profile', {title: 'Profile', nav: 'Profile', order: 50, load, render})
load(params): return (await CB.api('GET', '/api/users/' + (params.id || CB.me.id))).user
render(u) -> CB.el('div', {class: 'stack'},
  CB.el('div', {class: 'row'}, CB.avatar(u), CB.el('h2', {}, u.display_name)),
  CB.el('div', {class: 'muted'}, '@' + u.username),
  CB.el('p', {}, u.bio || 'No bio yet'),
  CB.el('div', {class: 'muted'}, CB.plural(u.friend_count, 'friend')),
  actions(u))
actions(u) by u.relationship:
  'self'             -> CB.form({fields: [
                          {name: 'display_name', label: 'Display name', value: u.display_name},
                          {name: 'bio', label: 'Bio', type: 'textarea', value: u.bio}],
                        submit: 'Save profile',
                        onsubmit: async (v) => {
                          await CB.api('PUT', '/api/profile', {display_name: v.display_name, bio: v.bio});
                          CB.toast('Profile saved'); await CB.reloadMe(); CB.refresh(); }})
  'none'             -> button 'Add friend': await CB.api('POST', '/api/friends/requests',
                        {user_id: u.id}); CB.refresh()
  'request_sent'     -> button 'Cancel request': await CB.api('DELETE',
                        '/api/friends/requests/' + u.request_id); CB.refresh()
  'request_received' -> button 'Accept': await CB.api('POST', '/api/friends/requests/' +
                        u.request_id + '/accept'); CB.refresh()
  'friends'          -> CB.el('div', {class: 'row'},
                          button 'Message': const r = await CB.api('POST', '/api/dm', {user_id: u.id});
                                            CB.go('chat', {id: r.conversation.id})
                          button 'Unfriend': await CB.api('DELETE', '/api/friends/' + u.id); CB.refresh())
Server answer: {user: {id, username, display_name, bio, joined_at, relationship, friend_count,
request_id}}.
```

Hidden tests (profile of ERIN id 5 unless noted): `params={"id": "5"}` -> first call `GET
/api/users/5`; text "Erin Evans", "@erin", "No bio yet" (bio ""), "1 friend" / "3 friends".
`none` -> click "Add friend" -> POST `{"user_id": 5}` and the GET twice. `request_sent` (rid 9)
-> "Cancel request" -> DELETE `/api/friends/requests/9`. `request_received` -> "Accept" -> POST
`/api/friends/requests/9/accept`. `friends` -> "Message" -> POST `/api/dm` `{"user_id": 5}`,
nav chat; "Unfriend" -> DELETE `/api/friends/5`. No params, `me=ALICE` -> `GET /api/users/1`;
`self` -> form "Save profile" with values prefilled; submit -> PUT `{"display_name": ...,
"bio": ...}`, `toasts == ["Profile saved"]`, `GET /api/session` called.

**cb-22 badges: nav badge service** (S, ~10; `badges`; `ui.md`)

```
No page. At the top level of the file:
CB.every(5000, async () => {
  const u = await CB.api('GET', '/api/updates');
  CB.badge('inbox', u.unread_total);
  CB.badge('friends', u.friend_requests);
});
Server answer: {unread_total, unread_conversations, friend_requests}.
```

Hidden tests: `run_page("badges", None, api={"GET /api/updates": {"unread_total": 4,
"unread_conversations": 2, "friend_requests": 1}}, steps=[{"tick": 5000}])` -> `pages == []`,
`count("GET", "/api/updates") == 2`, `badges == {"inbox": 4, "friends": 1}`, `errors == []`.
With `me=None` -> no calls.

---

#### Wave 4 (stretch API)

**cb-23 posts: create, feed, read, delete** (M, ~65; `posts`; `base.md`, `posts.md`)

```
post_json(db: Db, row: dict[str, Any], me: int) -> dict[str, Any]  (write it in this file) =
  {"id": row["id"], "author": user_json(require_user(db, row["author_id"])),
  "body": row["body"], "created_at": row["created_at"],
  "like_count": int(db.value("SELECT COUNT(*) FROM likes WHERE post_id = ?", row["id"])),
  "comment_count": int(db.value("SELECT COUNT(*) FROM comments WHERE post_id = ?", row["id"])),
  "liked": db.one("SELECT 1 FROM likes WHERE post_id = ? AND user_id = ?", row["id"], me) is not None}
POST /api/posts  body {"body"}
  text = body_str(request, "body", max_len=2000)
  pid = db.run("INSERT INTO posts (author_id, body, created_at) VALUES (?, ?, ?)", me, text, request.now)
  -> 201 {"post": post_json(db, visible_post(db, pid, me), me)}
GET /api/feed?limit=&before=
  limit = query_int(request, "limit", default=20, lo=1, hi=100)
  before = query_opt_int(request, "before"); cursor = before if before is not None else 2**62
  rows, more = db.page("SELECT * FROM posts WHERE id < ? AND (author_id = ? OR author_id IN"
      " (SELECT friend_id FROM friendships WHERE user_id = ?)) ORDER BY id DESC",
      cursor, me, me, limit=limit)
  -> 200 {"posts": [post_json(db, r, me) for r in rows], "has_more": more}
GET /api/posts/{id}
  pid = path_id(request); row = visible_post(db, pid, me)            (404)
  -> 200 {"post": post_json(db, row, me)}
DELETE /api/posts/{id}
  pid = path_id(request); row = visible_post(db, pid, me)            (404)
  row["author_id"] != me -> 403
  DELETE FROM likes WHERE post_id = ?; DELETE FROM comments WHERE post_id = ?;
  DELETE FROM posts WHERE id = ?
  -> 200 {"deleted": pid}
Tables you may write: posts; likes and comments (delete only, when deleting a post).
```

Hidden tests: `c.befriend(a, b)`, stranger x; `pa = c.make_post(a)`, tick, `pb = c.make_post(b)`,
tick, `px = c.make_post(x)`; `c.like(b, pa)`, `c.comment(b, pa)`. a's feed: `[post pb, post pa]`
with exact shapes (pa: `like_count` 1, `comment_count` 1, `liked` False; as b, `liked` True),
`has_more` False, no px. `limit=1` -> `[pb]`, True; `before=pb` -> `[pa]`. Create `" hi "` ->
201, body "hi", counts 0. 400: empty body, 2001 chars, `limit=0`, `limit=101`. GET px as a ->
404. DELETE pa by b -> 403; by a -> 200 and `c.rows` shows no likes/comments for pa; DELETE px
by a -> 404.

**cb-24 likes: like, unlike, likers** (S, ~35; `likes`; `base.md`, `posts.md`)

```
In every route: pid = path_id(request); visible_post(db, pid, me)    (404)
  n = int(db.value("SELECT COUNT(*) FROM likes WHERE post_id = ?", pid)) after the change
POST /api/posts/{id}/like
  db.run("INSERT OR IGNORE INTO likes (post_id, user_id, created_at) VALUES (?, ?, ?)",
         pid, me, request.now)
  -> 200 {"post_id": pid, "like_count": n, "liked": True}
DELETE /api/posts/{id}/like
  db.run("DELETE FROM likes WHERE post_id = ? AND user_id = ?", pid, me)
  -> 200 {"post_id": pid, "like_count": n, "liked": False}
GET /api/posts/{id}/likes
  rows = db.all("SELECT u.* FROM likes l JOIN users u ON u.id = l.user_id"
                " WHERE l.post_id = ? ORDER BY l.created_at, u.id", pid)
  -> 200 {"users": [user_json(r) for r in rows]}
Tables you may write: likes.
```

Hidden tests: `pid = c.make_post(b)`, `c.befriend(a, b)`, `c.befriend(b, d)`. a likes twice ->
`like_count` 1 both times; b (author) likes -> 2; a unlikes twice -> 1 both times, `liked` False.
Likers: `c.like(d, p2)`, tick, `c.like(a, p2)` -> `[d.json, a.json]`. Stranger -> 404 on all;
`999`, `x` -> 404.

**cb-25 comments: list, add, delete** (M, ~50; `comments`; `base.md`, `posts.md`)

```
K(row) = {"id": row["id"], "post_id": row["post_id"],
          "author": user_json(require_user(db, row["author_id"])), "body": row["body"],
          "created_at": row["created_at"]}
GET /api/posts/{id}/comments
  pid = path_id(request); visible_post(db, pid, me)                  (404)
  -> 200 {"comments": [K(r) for rows WHERE post_id = ? ORDER BY id]}
POST /api/posts/{id}/comments  body {"body"}
  pid = path_id(request); visible_post(db, pid, me)                  (404)
  text = body_str(request, "body", max_len=1000)
  cid = db.run("INSERT INTO comments (post_id, author_id, body, created_at)"
               " VALUES (?, ?, ?, ?)", pid, me, text, request.now)
  -> 201 {"comment": K({"id": cid, "post_id": pid, "author_id": me, "body": text,
                        "created_at": request.now})}
DELETE /api/comments/{id}
  cid = path_id(request); row = db.one("SELECT * FROM comments WHERE id = ?", cid)
  row is None -> 404
  post = visible_post(db, row["post_id"], me)                        (404)
  me is neither row["author_id"] nor post["author_id"] -> 403
  DELETE FROM comments WHERE id = ?  -> 200 {"deleted": cid}
Tables you may write: comments.
```

Hidden tests: `c.befriend(a, b)`, `c.befriend(b, d)`, `c.befriend(a, d)`; `pid = c.make_post(b)`.
a comments `"  nice "` -> 201 body "nice", exact K. List ordered by id with author objects.
Stranger -> 404 (GET, POST); `999` -> 404. Deletes: d cannot delete a's comment (403); a can;
b (post author) can delete d's comment; unknown comment `999` -> 404; `c.rows` confirm. 400:
empty, 1001 chars.

**cb-26 presence: friends online** (S, ~20; `presence`; `base.md`, `social.md`)

```
GET /api/friends/online
  rows = db.all("SELECT u.* FROM friendships f JOIN users u ON u.id = f.friend_id"
                " WHERE f.user_id = ? AND u.last_seen_at >= ?", me, request.now - 60000)
  sort by (row["display_name"].casefold(), row["id"])
  -> 200 {"online": [user_json(r) for r in rows]}
(The app sets last_seen_at = now on every logged-in request; 0 means never.) Read-only.
```

Hidden tests: a friends with b ("Zoe") and d ("Bea"); x not a friend. `c.touch(b)`, `c.touch(x)`,
`c.tick(30000)`, `c.touch(d)` -> a gets `[d, b]` (display order), no x. `c.tick(31000)` -> `[d]`;
`c.tick(60000)` -> `[]`. A lonely user -> `[]`.

**cb-27 suggestions: people you may know** (S, ~30; `suggestions`; `base.md`, `social.md`)

```
GET /api/friends/suggestions
  rows = db.all("SELECT f2.friend_id AS id, COUNT(*) AS mutual FROM friendships f1"
                " JOIN friendships f2 ON f2.user_id = f1.friend_id"
                " WHERE f1.user_id = ? AND f2.friend_id != ? GROUP BY f2.friend_id", me, me)
  keep rows where relationship(db, me, row["id"]) == "none"
  sort by (-mutual, username of that user); keep the first 10
  -> 200 {"suggestions": [{**user_json(require_user(db, r["id"])), "mutual": int(r["mutual"])}]}
Read-only.
```

Hidden tests: graph a-b, a-d, b-e, d-e, b-f, b-g, plus `c.friend_request(a, g)` -> `[e (mutual
2), f (mutual 1)]` (g pending, friends and a excluded). Twelve friends-of-friends with one mutual
-> 10, sorted by username. A lonely user -> `[]`.

---

#### Wave 5 (stretch UI)

**cb-28 page_feed: feed page** (M, ~60; `page_feed`; `ui.md`)

```
CB.page('feed', {title: 'Feed', nav: 'Feed', order: 40, poll: 15000, load, render})
load(params): return await CB.api('GET', '/api/feed' + CB.qs({limit: Number(params.limit || 20)}))
render(d, params) -> CB.el('div', {class: 'stack'},
  CB.form({fields: [{name: 'body', label: 'What is on your mind?', type: 'textarea'}],
           submit: 'Post', reset: true,
           onsubmit: async (v) => {
             const text = v.body.trim();
             if (text === '') return;
             await CB.api('POST', '/api/posts', {body: text});
             CB.refresh(); }}),
  d.posts.length ? d.posts.map(card) : CB.el('p', {class: 'muted'}, 'No posts yet'),
  d.has_more ? CB.el('button', {onclick: () => CB.go('feed',
      {limit: Number(params.limit || 20) + 20})}, 'Show more') : null)
card(p) = CB.el('div', {class: 'card'},
  CB.el('div', {class: 'row'}, CB.avatar(p.author), CB.userLink(p.author),
        CB.el('small', {class: 'muted'}, CB.time(p.created_at))),
  CB.el('p', {}, p.body),
  CB.el('div', {class: 'row'},
    CB.el('button', {testid: 'like-' + p.id, onclick: async () => {
        await CB.api(p.liked ? 'DELETE' : 'POST', '/api/posts/' + p.id + '/like');
        CB.refresh(); }}, (p.liked ? 'Unlike' : 'Like') + ' (' + p.like_count + ')'),
    CB.el('button', {testid: 'comments-' + p.id, onclick: () => CB.go('post', {id: p.id})},
          'Comments (' + p.comment_count + ')'),
    p.author.id === CB.me.id ? CB.el('button', {testid: 'delete-' + p.id, onclick: async () => {
        await CB.api('DELETE', '/api/posts/' + p.id); CB.refresh(); }}, 'Delete') : null))
Server answer: {posts: [Post], has_more}, Post = {id, author: U, body, created_at, like_count,
comment_count, liked}.
```

Hidden tests: posts `fake_post(11, ALICE, "mine", like_count=1, liked=True)`,
`fake_post(10, ERIN, "theirs", comment_count=3)`, `has_more` True: first call `GET
/api/feed?limit=20`; labels include "Unlike (1)", "Like (0)", "Comments (3)"; exactly one
"Delete" (`delete-11`). `click_id like-10` -> `["POST", "/api/posts/10/like", None]` and the feed
GET twice; `like-11` -> DELETE. `comments-10` -> `[["post", {"id": "10"}]]`. Submit "Post"
`{"body": " hi "}` -> POST `{"body": "hi"}`; blank -> no POST. Click "Show more" ->
`[["feed", {"limit": "40"}]]`. Empty -> "No posts yet". `tick 15000` -> feed GET again.

**cb-29 page_post: one post with comments** (M, ~60; `page_post`; `ui.md`)

```
CB.page('post', {title: 'Post', load, render})                       no nav
load(params):
  const a = await CB.api('GET', '/api/posts/' + params.id)
  const b = await CB.api('GET', '/api/posts/' + params.id + '/comments')
  return {post: a.post, comments: b.comments}
render(d, params) -> CB.el('div', {class: 'stack'}, in this order:
  CB.el('button', {onclick: () => CB.go('feed')}, 'Back to feed'),
  CB.el('div', {class: 'card'},
    CB.el('div', {class: 'row'}, CB.avatar(d.post.author), CB.userLink(d.post.author),
          CB.el('small', {class: 'muted'}, CB.time(d.post.created_at))),
    CB.el('p', {}, d.post.body),
    CB.el('button', {testid: 'like-' + d.post.id, onclick: async () => {
        await CB.api(d.post.liked ? 'DELETE' : 'POST', '/api/posts/' + d.post.id + '/like');
        CB.refresh(); }}, (d.post.liked ? 'Unlike' : 'Like') + ' (' + d.post.like_count + ')')),
  CB.el('h3', {}, 'Comments (' + d.comments.length + ')'),
  d.comments.length ? d.comments.map(comment) : CB.el('p', {class: 'muted'}, 'No comments yet'),
  CB.form({fields: [{name: 'body', label: 'Write a comment'}], submit: 'Comment', reset: true,
           onsubmit: async (v) => {
             const text = v.body.trim();
             if (text === '') return;
             await CB.api('POST', '/api/posts/' + params.id + '/comments', {body: text});
             CB.refresh(); }}))
comment(k)  (defined inside render, so it can read d)
  = CB.el('div', {class: 'item'}, CB.avatar(k.author), CB.userLink(k.author),
  CB.el('span', {}, k.body), CB.el('small', {class: 'muted'}, CB.time(k.created_at)),
  k.author.id === CB.me.id || d.post.author.id === CB.me.id
    ? CB.el('button', {testid: 'delete-' + k.id, onclick: async () => {
        await CB.api('DELETE', '/api/comments/' + k.id); CB.refresh(); }}, 'Delete')
    : null)
Server answers: {post: Post}; {comments: [K]}, K = {id, post_id, author: U, body, created_at}.
```

Hidden tests: post 5 by ERIN, comments by ALICE (id 1) and FRANK (id 2): text "Comments (2)",
both bodies; "Delete" once (`delete-1`). `click_id delete-1` -> DELETE `/api/comments/1`, reload.
Submit "Comment" `{"body": " yo "}` -> POST `{"body": "yo"}`; blank -> none. Post by ALICE ->
"Delete" twice. Like toggling as in the feed. Empty -> "No comments yet". "Back to feed" ->
`[["feed", {}]]`.

**cb-30 page_discover: online friends and suggestions** (S, ~45; `page_discover`; `ui.md`)

```
CB.page('discover', {title: 'Discover', nav: 'Discover', order: 35, poll: 15000, load, render})
load(): const on = await CB.api('GET', '/api/friends/online')
        const sg = await CB.api('GET', '/api/friends/suggestions')
        return {online: on.online, suggestions: sg.suggestions}
render(d) -> CB.el('div', {class: 'stack'}, in this order:
  CB.el('h2', {}, 'Online now'),
  d.online.length ? d.online.map((u) => CB.el('div', {class: 'item'}, CB.avatar(u), CB.userLink(u),
      CB.el('button', {testid: 'message-' + u.id, onclick: async () => {
          const r = await CB.api('POST', '/api/dm', {user_id: u.id});
          CB.go('chat', {id: r.conversation.id}); }}, 'Message')))
    : CB.el('p', {class: 'muted'}, 'Nobody is online'),
  CB.el('h2', {}, 'People you may know'),
  d.suggestions.length ? d.suggestions.map((s) => CB.el('div', {class: 'item'}, CB.avatar(s),
      CB.userLink(s), CB.el('span', {class: 'muted'}, CB.plural(s.mutual, 'mutual friend')),
      CB.el('button', {testid: 'add-' + s.id, onclick: async () => {
          await CB.api('POST', '/api/friends/requests', {user_id: s.id});
          CB.toast('Request sent'); CB.refresh(); }}, 'Add friend')))
    : CB.el('p', {class: 'muted'}, 'No suggestions'))
Server answers: {online: [U]}; {suggestions: [U + mutual]}.
```

Hidden tests: online `[ERIN]`, suggestions `[FRANK + mutual 2, CAROL + mutual 1]`: text "Erin
Evans", "2 mutual friends", "1 mutual friend". `click_id add-6` -> POST `{"user_id": 6}`,
`toasts == ["Request sent"]`, suggestions GET twice. `click_id message-5` -> nav chat with the
mocked id. `tick 15000` -> both GETs again. Both empty -> "Nobody is online", "No suggestions".

---

## 7. Procedures

### 7.1 Phase A: frame, tasks, proof (staff, before any worker runs)

1. `git init -b main` in `chatbook`; first commit: `.gitattributes` (`* text=auto eol=lf`) and
   `.gitignore`. Then the frame (section 3) with all 30 stubs, docs, AGENTS.md, tests.
2. Gates locally (from `chatbook`, harness interpreter
   `E:/Playground_Projects/04_AgentSwarm/.venv/Scripts/python.exe`, written `py`):
   `py -m ruff check .`, `py -m ruff format --check .`, `py -m mypy src`,
   `py -m pytest -q -p no:cacheprovider tests`, `py tools/check_extra.py`, and
   `swarm -t chatbook archlint`.
3. Browser check of the frame (staff, Claude Browser tools): `python -m chatbook --demo` with a
   temporary `CHATBOOK_DB`, plus the sample page loaded through a temporary feature folder that
   is not committed: login redirect, nav order and badges, form submit and reset, typed text kept
   across a poll, `.messages` stays at the bottom, error toast, logout, tab title prefix, CSP
   clean console. Repeat in the mock (frame tests) so both agree.
4. `harness/`: `git init -b main`, `.gitattributes`, `.gitignore`, `swarm.toml` (section 4), and
   the MVP tasks cb-01..cb-22 (stretch tasks cb-23..cb-30 may follow after the MVP milestone;
   their stubs are already in the frame).
5. `git clone E:/Playground_Projects/05_ChatBook/chatbook E:/Playground_Projects/05_ChatBook/chatbook-oracle`.
6. `swarm -t chatbook-oracle validate` -> every task passes (base green, hidden tests red,
   reference passes).
7. `swarm -t chatbook-oracle integrate` (no branch list: only oracle branches exist in the clone)
   -> all merge, all gates and all hidden tests pass together: the reference product.
8. Browser smoke of the reference product (checkout `integration/<stamp>` in the clone, run with
   `--demo`, script 7.3). Then `git -C chatbook-oracle checkout main` and
   `swarm -t chatbook-oracle clean --branches`, in this order: `clean` cannot delete the
   integration branch while the clone has it checked out.
9. Update `PROGRESS.md`.

### 7.2 Each wave (chief)

1. **Refresh the oracle clone** to the current `main`:
   `git -C ../chatbook-oracle pull --ff-only`, `swarm -t chatbook-oracle clean --branches`,
   `swarm -t chatbook-oracle validate <wave ids>` (catches any drift since Phase A).
2. **Run**: `swarm -t chatbook run <wave ids> -j 1` (engine default `local-14b-arch`; one GPU).
3. **Triage** failures with the ladder in 8.1; rerun as needed.
4. **Integrate explicitly**: list worker branches
   (`git -C chatbook branch --list "agent/*--local-*"`), then
   `swarm -t chatbook integrate <this wave's passing branches> <all earlier accepted branches>`.
   Earlier branches merge as no-ops and their hidden tests run again (regression suite).
5. **Check provenance**: every merged commit body says `Automated change by swarm engine
   local-...`; none says `oracle`:
   `git -C chatbook log --format=%b main..integration/<stamp>`.
6. **Advance main**: `git -C chatbook merge --ff-only integration/<stamp>` (on `main`;
   integrate never advances it). Keep the `agent/*` branches on the real target until the project
   ends (they are the regression list); `swarm -t chatbook clean` without `--branches` removes
   kept worktrees once inspected.
7. **Smoke test** (7.3) for W2+ and **staff flow test** (3.19) committed to `main`.
8. **Update PROGRESS.md** (owner's rule: before and after long runs).

W1 extra: read `Tokens: N sent` for both the architect and the editor call in
`runs/<id>/iter-1/aider.chat.md` (or `aider.llm.txt`). Targets: architect input < 5.5k, editor
input + output < 7k. If over: shorten the CONTRACT block, trim the docs passed, lower
`feedback_chars` to 2500. If W1 passes fewer than 4 of 6, stop and fix the prompt/stub style or
the docs before W2 (re-validate after every change).

### 7.3 Browser smoke script (after each UI wave and at the end)

```powershell
cd E:/Playground_Projects/05_ChatBook/chatbook
$env:PYTHONPATH = 'src'; $env:CHATBOOK_DB = "$env:TEMP\chatbook-smoke.db"
E:/Playground_Projects/04_AgentSwarm/.venv/Scripts/python.exe -m chatbook --demo
```

Open `http://127.0.0.1:8000` in two browser profiles (or one normal and one private window),
as `alice` and `bob` (password `password1`). Check: register a new user; search "car" from the top
bar; send a request and accept it in the other window; Friends page counts; open a DM from People
and from a profile; send messages both ways and see them arrive within ~2 s; the Chats badge and
`(n)` title rise and clear after opening the chat; "Seen" appears; create a group, rename it, add
a friend, leave; "Show older" with 60+ messages (seed via repeated sends); edit own profile;
log out. The chief may drive this with the Claude Browser tools. The smoke DB lives in `%TEMP%`.

---

## 8. Failure plan and risks

### 8.1 When a task fails 4/4

1. **Read** `runs/<id>/iter-*/feedback.md`, `diff.patch`, `aider.chat.md`. Classify:
   - truncated or partial file -> the file or prompt is too big: shrink the CONTRACT/prompt, or
     split (step 4);
   - wrong names, keys, status or order -> the spec is ambiguous: sharpen the prompt **and** the
     stub's CONTRACT (staff commit to `main`, with `tools/contracts.json` regenerated by
     `python tools/check_extra.py --write-contracts`), quote the exact line (SQL, JSON literal,
     label);
   - "CONTRACT block missing or changed" / "moved" / "extends it" in the check_extra output ->
     the worker edited or moved its CONTRACT (a block deleted outright is put back by autofix:
     `iter-*/autofix.log` says "restored", or "left ..." and why not); the gate prints the
     block, so rerun first;
   - the same wrong code repeated (stuck warning) -> put the exact expected code line in the spec;
   - only mypy/ruff -> add the precise typing hint (`rows: list[dict[str, Any]]`, `int(...)`);
   - frame/mock friction (the worker expected reasonable CB/API behaviour) -> fix the frame or docs
     between waves, re-run frame tests, re-validate all pending tasks.
2. **Rerun once unchanged** (sampling varies): `swarm -t chatbook run cb-NN`.
3. **Re-spec and rerun** (after `swarm -t chatbook-oracle validate cb-NN`).
4. **Split** (staff frame commit between waves): backend -> move some routes into a new feature
   folder with its own stub, task and route-map entry (e.g. friend_requests: send / list), and
   regenerate `tools/contracts.json` (`--write-contracts`: one "added", one "changed");
   UI -> move a part into a later task that reopens the folder, whose `solution.patch` is written
   against the merged code at that time and whose acceptance folder also carries the original
   task's test file (so the original behaviour stays tested).
5. **Other engines**: `-e local-14b` (no architect: the single pass sees the prompt directly,
   useful when the plan loses details), then `-e local-7b-arch` (16k context, when the prompt
   overflows). `deepseek-coder-v2:16b` is not used (ignores instructions, measured).
6. **Owner decision**: for stretch tasks, drop the feature (remove its stub and nav entry in a
   frame commit, regenerating `tools/contracts.json` with `--write-contracts`: that stub's path
   is reported REMOVED, the one REMOVED staff expect; otherwise the gate fails with "file
   missing"). For MVP tasks, ask the owner: pull `qwen3-coder:30b` (18 GB; ask first),
   sign in the `claude` CLI for a cloud engine, or allow staff-written feature code. The ground
   rule forbids the last without consent.

MVP rule: W1-W3 must all be merged and smoke-tested before any stretch task runs.

### 8.2 Risks

| Risk | Mitigation |
|---|---|
| 8k context overflows (prompt + AGENTS + docs + file + plan + whole-file reply), on retries especially | Per-task docs split, AGENTS ~600 tokens, `--map-tokens 0`, `feedback_chars` 3000, files <= 120 lines, prompts <= 700 words, W1 measurement with a hard go/no-go. |
| The editor pass never sees `prompt.md` | CONTRACT block in every stub; docs passed as `--read` reach both passes; check_extra fails a file that no longer begins with its CONTRACT block and prints the block to restore, and an autofix step puts back a block deleted outright (3.16 item 6; added after Wave 1, where the cb-05 worker deleted its docstring with every test green). |
| Whole-file truncation | Gate limit 180 lines; specs sized 10-65 lines of logic; split rule. |
| The 14B resubmits the same wrong code | Harness stuck warning; specs quote SQL/JSON/labels; rerun; `local-14b` single pass. |
| Mock vs browser drift | The runner executes the real `cb.js`; only the DOM/host is fake, and as strict as Chrome where pages could rely on more (`appendChild` of strings, Array methods on `childNodes`/`children`, select values, unprevented submits; 3.14); lint rejects DOM habits; staff browser check of the sample page; chief smoke per wave. |
| The frame is a single point of failure | Frame tests for every documented behaviour, `test_api_doc`, `test_route_map`; frame frozen after Phase A; changes only between waves with re-validation of pending tasks. |
| Oracle branches merged as worker code | Separate oracle target and clone; explicit integrate lists; provenance check before ff-merge; never `validate` or `-e oracle` on `chatbook`. |
| CRLF breaks patches | `.gitattributes` first in both repos; patches via `git diff --output`. |
| JS name collisions between pages | IIFE wrapping (server and runner); load-all frame test. |
| Schema frozen | Designed for all 30 features up front; any change is a backward-compatible staff commit between waves. |
| Shape drift between API and UI (UI tests use mocks) | Shared shapes built by frame helpers (U, M, C); UI specs list the fields they read; flow tests and smoke tests at runtime. |
| Security | Login required by default (`public=True` to opt out); `require_member`/`visible_post` in the frame; CB.el text nodes + lint + CSP (no inline script/style); `CB.el('form')` refused; SQL f-string guard + check_extra's constant-SQL check + `?` placeholders; `body_str` rejects lone surrogates; tokens stored hashed; UNIQUE/PK IntegrityError -> 409; review diffs at integrate. The guard and archlint stop accidents, not a determined adversary. |
| Concurrency | Threaded server (30 s socket timeout) with one global lock around each request's dispatch (bodies are read before it); App-owned transactions; no shared-connection joins. |
| `acceptance_feedback = "full"` invites hard-coding | Fixtures differ from prompt examples; several fixture values per behaviour; diffs reviewed. |
| Node missing or sandbox switched to docker | `sandbox = "none"`; check_extra fails loudly without node; the docker image (harness repo) has no node and must not be modified. |
| Time-dependent flakiness | FakeClock in Client and the runner; `CB.time` never asserted. |
| mypy strict on Any rows / object dicts | `warn_return_any = false`, builders return `dict[str, Any]`, AGENTS tip. |
| GPU time | 30 tasks x ~2 attempts x 2-4 min = ~3-5 h of GPU time plus gates (~20-30 s per attempt). |
| Windows path length | Short task ids; worktree paths stay under ~190 characters. |

---

## 9. Open questions and the defaults this design takes

| Question | Default |
|---|---|
| DMs and group adds only between friends? | Yes (403 otherwise; UI shows "Message" only for friends). |
| Minimum group size | Creator + at least 1 other member. |
| Stretch waves (feed, presence, suggestions, discover) | In scope after the MVP milestone; droppable per task. |
| Bind address | `127.0.0.1`; `HOST=0.0.0.0` opts into LAN use (the owner decides). |
| Escalation beyond local 14B/7B | Only with the owner's consent (30B download, claude CLI sign-in, or staff code). |
| `acceptance_feedback` | `full` (product build, not a benchmark). |
| Repo map | `--map-tokens 0` on every engine: with `core/` and `docs/` aiderignored (protected), a map could only show sibling feature stubs. |
| Staff flow tests in `tests/` after waves | Yes (they become gates that protect merged features). |
| Harness folder versioned | Yes, its own git repo with LF. |
| Demo accounts with password `password1` | Local `--demo` only, printed at startup. |
