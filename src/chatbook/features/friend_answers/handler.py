"""friend_answers: accept, decline or cancel a friend request.

CONTRACT (keep this docstring; implement exactly this):
Notation: db = request.db, me = request.me.id.
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
"""

from chatbook.core.api import HTTPError, Request, Response, route


@route("POST", "/api/friends/requests/{id}/accept")
def accept_request(request: Request) -> Response:
    raise HTTPError(501, "not implemented")


@route("POST", "/api/friends/requests/{id}/decline")
def decline_request(request: Request) -> Response:
    raise HTTPError(501, "not implemented")


@route("DELETE", "/api/friends/requests/{id}")
def cancel_request(request: Request) -> Response:
    raise HTTPError(501, "not implemented")
