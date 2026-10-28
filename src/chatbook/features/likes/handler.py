"""likes: like, unlike and list likers.

CONTRACT (keep this docstring; implement exactly this):
Notation: db = request.db, me = request.me.id (the code below writes request.db and request.me.id).
n = int(db.value("SELECT COUNT(*) FROM likes WHERE post_id = ?", pid)) after the change
POST /api/posts/{id}/like
  pid = path_id(request); visible_post(db, pid, me)                  (404)
  db.run("INSERT OR IGNORE INTO likes (post_id, user_id, created_at) VALUES (?, ?, ?)",
         pid, me, request.now)
  -> 200 {"post_id": pid, "like_count": n, "liked": True}
DELETE /api/posts/{id}/like   (me may remove its own like even from a post me can't see)
  pid = path_id(request)                                             (404)
  gone = db.run("DELETE FROM likes WHERE post_id = ? AND user_id = ?", pid, me)
  if not can_see_post(db, pid, me):      (post missing, or author neither me nor a friend)
    gone == 0 -> raise HTTPError(404, "post not found")    (exactly the 404 of visible_post)
    -> 200 {"post_id": pid, "liked": False}                (no like_count: a hidden post)
  -> 200 {"post_id": pid, "like_count": n, "liked": False}
GET /api/posts/{id}/likes
  pid = path_id(request); visible_post(db, pid, me)                  (404)
  rows = db.all("SELECT u.* FROM likes l JOIN users u ON u.id = l.user_id"
                " WHERE l.post_id = ? ORDER BY l.created_at, u.id", pid)
  -> 200 {"users": [user_json(r) for r in rows]}
Tables you may write: likes.
"""

from chatbook.core.api import (
    HTTPError,
    Request,
    Response,
    can_see_post,
    path_id,
    route,
    user_json,
    visible_post,
)


@route("POST", "/api/posts/{id}/like")
def like_post(request: Request) -> Response:
    pid = path_id(request)
    visible_post(request.db, pid, request.me.id)
    request.db.run(
        "INSERT OR IGNORE INTO likes (post_id, user_id, created_at) VALUES (?, ?, ?)",
        pid,
        request.me.id,
        request.now,
    )
    n = int(request.db.value("SELECT COUNT(*) FROM likes WHERE post_id = ?", pid))
    return Response(200, {"post_id": pid, "like_count": n, "liked": True})


@route("DELETE", "/api/posts/{id}/like")
def unlike_post(request: Request) -> Response:
    pid = path_id(request)
    gone = request.db.run("DELETE FROM likes WHERE post_id = ? AND user_id = ?", pid, request.me.id)
    if not can_see_post(request.db, pid, request.me.id):
        if gone == 0:
            raise HTTPError(404, "post not found")
        return Response(200, {"post_id": pid, "liked": False})
    n = int(request.db.value("SELECT COUNT(*) FROM likes WHERE post_id = ?", pid))
    return Response(200, {"post_id": pid, "like_count": n, "liked": False})


@route("GET", "/api/posts/{id}/likes")
def list_likes(request: Request) -> Response:
    pid = path_id(request)
    visible_post(request.db, pid, request.me.id)
    rows = request.db.all(
        "SELECT u.* FROM likes l JOIN users u ON u.id = l.user_id "
        "WHERE l.post_id = ? ORDER BY l.created_at, u.id",
        pid,
    )
    users = [user_json(r) for r in rows]
    return Response(200, {"users": users})
