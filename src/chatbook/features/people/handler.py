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

from chatbook.core.api import (
    Request,
    Response,
    query_int,
    query_str,
    relationship,
    route,
    user_json,
)


@route("GET", "/api/users")
def search_users(request: Request) -> Response:
    q = query_str(request, "q", max_len=50)
    limit = query_int(request, "limit", default=20, lo=1, hi=50)

    rows = request.db.all("SELECT * FROM users WHERE id != ? ORDER BY username", request.me.id)

    filtered_rows = [
        row
        for row in rows
        if q.casefold() in row["username"].casefold()
        or q.casefold() in row["display_name"].casefold()
    ]

    limited_rows = filtered_rows[:limit]

    users = [
        {**user_json(row), "relationship": relationship(request.db, request.me.id, row["id"])}
        for row in limited_rows
    ]

    return Response(200, {"users": users})
