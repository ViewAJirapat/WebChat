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

from typing import Any

from chatbook.core.api import (
    Db,
    HTTPError,
    Request,
    Response,
    are_friends,
    befriend,
    body_id,
    require_user,
    route,
    user_json,
)


def request_json(db: Db, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "from": user_json(require_user(db, row["from_id"])),
        "to": user_json(require_user(db, row["to_id"])),
        "created_at": row["created_at"],
    }


@route("POST", "/api/friends/requests")
def send_request(request: Request) -> Response:
    other = body_id(request, "user_id")
    if other == request.me.id:
        raise HTTPError(400, "Cannot send a friend request to yourself")

    require_user(request.db, other)

    if are_friends(request.db, request.me.id, other):
        raise HTTPError(409, "You are already friends with this user")

    existing_request = request.db.one(
        "SELECT id FROM friend_requests WHERE from_id = ? AND to_id = ?", request.me.id, other
    )
    if existing_request is not None:
        raise HTTPError(409, "You have already sent a friend request to this user")

    reverse_request = request.db.one(
        "SELECT id FROM friend_requests WHERE from_id = ? AND to_id = ?", other, request.me.id
    )
    if reverse_request is not None:
        befriend(request.db, request.me.id, other, request.now)
        return Response(
            200, {"status": "friends", "friend": user_json(require_user(request.db, other))}
        )

    rid = request.db.run(
        "INSERT INTO friend_requests (from_id, to_id, created_at) VALUES (?, ?, ?)",
        request.me.id,
        other,
        request.now,
    )
    return Response(
        201,
        {
            "status": "pending",
            "request": request_json(
                request.db,
                {"id": rid, "from_id": request.me.id, "to_id": other, "created_at": request.now},
            ),
        },
    )


@route("GET", "/api/friends/requests")
def list_requests(request: Request) -> Response:
    incoming = request.db.all(
        "SELECT * FROM friend_requests WHERE to_id = ? ORDER BY id DESC", request.me.id
    )
    outgoing = request.db.all(
        "SELECT * FROM friend_requests WHERE from_id = ? ORDER BY id DESC", request.me.id
    )
    return Response(
        200,
        {
            "incoming": [request_json(request.db, r) for r in incoming],
            "outgoing": [request_json(request.db, r) for r in outgoing],
        },
    )
