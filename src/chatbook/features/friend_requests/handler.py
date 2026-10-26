"""friend_requests: send and list friend requests.

CONTRACT (keep this docstring; implement exactly this):
Notation: db = request.db, me = request.me.id.
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
"""

from chatbook.core.api import HTTPError, Request, Response, route


@route("POST", "/api/friends/requests")
def send_request(request: Request) -> Response:
    raise HTTPError(501, "not implemented")


@route("GET", "/api/friends/requests")
def list_requests(request: Request) -> Response:
    raise HTTPError(501, "not implemented")
