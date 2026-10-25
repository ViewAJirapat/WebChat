"""likes: like, unlike and list likers.

CONTRACT (keep this docstring; implement exactly this):
Notation: db = request.db, me = request.me.id.
In every route: pid = path_id(request); visible_post(db, pid, me)    (404)
  n = int(db.value("SELECT COUNT(*) FROM likes WHERE post_id = ?", pid)) after the change
POST /api/posts/{id}/like
  db.run("INSERT OR IGNORE INTO likes (post_id, user_id, created_at) VALUES (?, ?, ?)",
         pid, me, request.now)
  -> 200 {"post_id": pid, "like_count": n, "liked": True}
DELETE /api/posts/{id}/like
  db.run("DELETE FROM likes WHERE post_id = ? AND user_id = ?", pid, me)
  -> 200 {"post_id": pid, "like_count": n, "liked": False}
GET /api/posts/{id}/likes
  rows = db.all("SELECT u.* FROM likes l JOIN users u ON u.id = l.user_id"
                " WHERE l.post_id = ? ORDER BY l.created_at, u.id", pid)
  -> 200 {"users": [user_json(r) for r in rows]}
Tables you may write: likes.
"""

from chatbook.core.api import HTTPError, Request, Response, route


@route("POST", "/api/posts/{id}/like")
def like_post(request: Request) -> Response:
    raise HTTPError(501, "not implemented")


@route("DELETE", "/api/posts/{id}/like")
def unlike_post(request: Request) -> Response:
    raise HTTPError(501, "not implemented")


@route("GET", "/api/posts/{id}/likes")
def list_likes(request: Request) -> Response:
    raise HTTPError(501, "not implemented")
