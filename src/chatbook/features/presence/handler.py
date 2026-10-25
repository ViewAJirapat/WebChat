"""presence: friends online.

CONTRACT (keep this docstring; implement exactly this):
Notation: db = request.db, me = request.me.id.
GET /api/friends/online
  rows = db.all("SELECT u.* FROM friendships f JOIN users u ON u.id = f.friend_id"
                " WHERE f.user_id = ? AND u.last_seen_at >= ?", me, request.now - 60000)
  sort by (row["display_name"].casefold(), row["id"])
  -> 200 {"online": [user_json(r) for r in rows]}
(The app sets last_seen_at = now on every logged-in request; 0 means never.) Read-only.
"""

from chatbook.core.api import HTTPError, Request, Response, route


@route("GET", "/api/friends/online")
def online_friends(request: Request) -> Response:
    raise HTTPError(501, "not implemented")
