"""comments: list, add and delete comments.

CONTRACT (keep this docstring; implement exactly this):
Notation: db = request.db, me = request.me.id.
K(row) = {"id": row["id"], "post_id": row["post_id"],
          "author": user_json(require_user(db, row["author_id"])), "body": row["body"],
          "created_at": row["created_at"]}
GET /api/posts/{id}/comments
  pid = path_id(request); visible_post(db, pid, me)                  (404)
  -> 200 {"comments": [K(r) for rows WHERE post_id = ? ORDER BY id]}
POST /api/posts/{id}/comments  body {"body"}
  pid = path_id(request); visible_post(db, pid, me)                  (404)
  text = body_str(request, "body", max_len=1000)
  cid = INSERT INTO comments (post_id, author_id, body, created_at)
  -> 201 {"comment": K(the new row)}
DELETE /api/comments/{id}
  cid = path_id(request); row = db.one("SELECT * FROM comments WHERE id = ?", cid)
  row is None -> 404
  post = visible_post(db, row["post_id"], me)                        (404)
  me is neither row["author_id"] nor post["author_id"] -> 403
  DELETE FROM comments WHERE id = ?  -> 200 {"deleted": cid}
Tables you may write: comments.
"""

from chatbook.core.api import HTTPError, Request, Response, route


@route("GET", "/api/posts/{id}/comments")
def list_comments(request: Request) -> Response:
    raise HTTPError(501, "not implemented")


@route("POST", "/api/posts/{id}/comments")
def add_comment(request: Request) -> Response:
    raise HTTPError(501, "not implemented")


@route("DELETE", "/api/comments/{id}")
def delete_comment(request: Request) -> Response:
    raise HTTPError(501, "not implemented")
