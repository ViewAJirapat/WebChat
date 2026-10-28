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
