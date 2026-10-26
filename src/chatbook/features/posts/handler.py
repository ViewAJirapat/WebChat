"""posts: new posts, the feed, one post, delete a post.

CONTRACT (keep this docstring; implement exactly this):
Notation: db = request.db, me = request.me.id.
post_json(db: Db, row: dict[str, Any], me: int) -> dict[str, Any]  (write it in this file) =
  {"id": row["id"], "author": user_json(require_user(db, row["author_id"])),
  "body": row["body"], "created_at": row["created_at"],
  "like_count": int(db.value("SELECT COUNT(*) FROM likes WHERE post_id = ?", row["id"])),
  "comment_count": int(db.value("SELECT COUNT(*) FROM comments WHERE post_id = ?", row["id"])),
  "liked": db.one("SELECT 1 FROM likes WHERE post_id = ? AND user_id = ?", row["id"], me)
           is not None}
POST /api/posts  body {"body"}
  text = body_str(request, "body", max_len=2000)
  pid = db.run("INSERT INTO posts (author_id, body, created_at) VALUES (?, ?, ?)",
               me, text, request.now)
  -> 201 {"post": post_json(db, visible_post(db, pid, me), me)}
GET /api/feed?limit=&before=
  limit = query_int(request, "limit", default=20, lo=1, hi=100)
  before = query_opt_int(request, "before"); cursor = before if before is not None else 2**62
  rows, more = db.page("SELECT * FROM posts WHERE id < ? AND (author_id = ? OR author_id IN"
      " (SELECT friend_id FROM friendships WHERE user_id = ?)) ORDER BY id DESC",
      cursor, me, me, limit=limit)
  -> 200 {"posts": [post_json(db, r, me) for r in rows], "has_more": more}
GET /api/posts/{id}
  pid = path_id(request); row = visible_post(db, pid, me)            (404)
  -> 200 {"post": post_json(db, row, me)}
DELETE /api/posts/{id}
  pid = path_id(request); row = visible_post(db, pid, me)            (404)
  row["author_id"] != me -> 403
  DELETE FROM likes WHERE post_id = ?; DELETE FROM comments WHERE post_id = ?;
  DELETE FROM posts WHERE id = ?  -> 200 {"deleted": pid}
Tables you may write: posts; likes and comments (delete only, when deleting a post).
"""

from chatbook.core.api import HTTPError, Request, Response, route


@route("POST", "/api/posts")
def create_post(request: Request) -> Response:
    raise HTTPError(501, "not implemented")


@route("GET", "/api/feed")
def get_feed(request: Request) -> Response:
    raise HTTPError(501, "not implemented")


@route("GET", "/api/posts/{id}")
def get_post(request: Request) -> Response:
    raise HTTPError(501, "not implemented")


@route("DELETE", "/api/posts/{id}")
def delete_post(request: Request) -> Response:
    raise HTTPError(501, "not implemented")
