"""suggestions: people you may know.

CONTRACT (keep this docstring; implement exactly this):
Notation: db = request.db, me = request.me.id.
GET /api/friends/suggestions
  rows = db.all("SELECT f2.friend_id AS id, COUNT(*) AS mutual FROM friendships f1"
                " JOIN friendships f2 ON f2.user_id = f1.friend_id"
                " WHERE f1.user_id = ? AND f2.friend_id != ? GROUP BY f2.friend_id", me, me)
  keep rows where relationship(db, me, row["id"]) == "none"
  sort by (-mutual, username of that user); keep the first 10
  -> 200 {"suggestions": [{**user_json(require_user(db, r["id"])), "mutual": int(r["mutual"])}]}
Read-only.
"""

from chatbook.core.api import HTTPError, Request, Response, route


@route("GET", "/api/friends/suggestions")
def friend_suggestions(request: Request) -> Response:
    raise HTTPError(501, "not implemented")
