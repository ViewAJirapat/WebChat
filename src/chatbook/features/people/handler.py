"""people: search people.

CONTRACT (keep this docstring; implement exactly this):
Notation: db = request.db, me = request.me.id.
GET /api/users?q=&limit=
  1. q = query_str(request, "q", max_len=50)
  2. limit = query_int(request, "limit", default=20, lo=1, hi=50)
  3. rows = db.all("SELECT * FROM users WHERE id != ? ORDER BY username", me)
  4. keep the rows where q.casefold() is in row["username"].casefold() or in
     row["display_name"].casefold()   (plain Python `in`, no SQL LIKE)
  5. keep the first `limit` rows
  -> 200 {"users": [{**user_json(row), "relationship": relationship(db, me, row["id"])} ...]}
Read-only.
"""

from chatbook.core.api import HTTPError, Request, Response, route


@route("GET", "/api/users")
def search_users(request: Request) -> Response:
    raise HTTPError(501, "not implemented")
