"""profiles: view and edit profiles.

CONTRACT (keep this docstring; implement exactly this):
Notation: db = request.db, me = request.me.id.
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
"""

from chatbook.core.api import (
    Request,
    Response,
    body_str,
    friend_ids,
    path_id,
    relationship,
    require_user,
    route,
)


@route("GET", "/api/users/{id}")
def get_profile(request: Request) -> Response:
    uid = path_id(request)
    row = require_user(request.db, uid)
    rel = relationship(request.db, request.me.id, row["id"])
    rid = None
    if rel == "request_sent":
        rid = request.db.value(
            "SELECT id FROM friend_requests WHERE from_id = ? AND to_id = ?",
            request.me.id,
            row["id"],
        )
    elif rel == "request_received":
        rid = request.db.value(
            "SELECT id FROM friend_requests WHERE from_id = ? AND to_id = ?",
            row["id"],
            request.me.id,
        )

    profile = {
        "id": row["id"],
        "username": row["username"],
        "display_name": row["display_name"],
        "bio": row["bio"],
        "joined_at": row["created_at"],
        "relationship": rel,
        "friend_count": len(friend_ids(request.db, row["id"])),
        "request_id": rid,
    }
    return Response(200, {"user": profile})


@route("PUT", "/api/profile")
def update_profile(request: Request) -> Response:
    display_name = body_str(request, "display_name", max_len=50)
    bio = body_str(request, "bio", min_len=0, max_len=300)
    request.db.run(
        "UPDATE users SET display_name = ?, bio = ? WHERE id = ?", display_name, bio, request.me.id
    )
    updated_row = require_user(request.db, request.me.id)
    rel = "self"
    rid = None
    friend_count = len(friend_ids(request.db, request.me.id))

    profile = {
        "id": updated_row["id"],
        "username": updated_row["username"],
        "display_name": updated_row["display_name"],
        "bio": updated_row["bio"],
        "joined_at": updated_row["created_at"],
        "relationship": rel,
        "friend_count": friend_count,
        "request_id": rid,
    }
    return Response(200, {"user": profile})
