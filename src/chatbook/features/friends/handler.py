"""friends: list friends and unfriend.

CONTRACT (keep this docstring; implement exactly this):
Notation: db = request.db, me = request.me.id.
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
"""

from chatbook.core.api import HTTPError, Request, Response, route


@route("GET", "/api/friends")
def list_friends(request: Request) -> Response:
    raise HTTPError(501, "not implemented")


@route("DELETE", "/api/friends/{id}")
def remove_friend(request: Request) -> Response:
    raise HTTPError(501, "not implemented")
