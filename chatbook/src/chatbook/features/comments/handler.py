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
  cid = db.run("INSERT INTO comments (post_id, author_id, body, created_at)"
               " VALUES (?, ?, ?, ?)", pid, me, text, request.now)
  -> 201 {"comment": K({"id": cid, "post_id": pid, "author_id": me, "body": text,
                        "created_at": request.now})}
DELETE /api/comments/{id}
  cid = path_id(request); row = db.one("SELECT * FROM comments WHERE id = ?", cid)
  row is None -> 404
  post = visible_post(db, row["post_id"], me)                        (404)
  me is neither row["author_id"] nor post["author_id"] -> 403
  DELETE FROM comments WHERE id = ?  -> 200 {"deleted": cid}
Tables you may write: comments.
"""

from typing import Any

from chatbook.core.api import (
    Db,
    HTTPError,
    Request,
    Response,
    body_str,
    path_id,
    require_user,
    route,
    user_json,
    visible_post,
)


def comment_json(db: Db, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "post_id": row["post_id"],
        "author": user_json(require_user(db, row["author_id"])),
        "body": row["body"],
        "created_at": row["created_at"],
    }


@route("GET", "/api/posts/{id}/comments")
def list_comments(request: Request) -> Response:
    pid = path_id(request)
    visible_post(request.db, pid, request.me.id)
    rows = request.db.all("SELECT * FROM comments WHERE post_id = ? ORDER BY id", pid)
    comments = [comment_json(request.db, r) for r in rows]
    return Response(200, {"comments": comments})


@route("POST", "/api/posts/{id}/comments")
def add_comment(request: Request) -> Response:
    pid = path_id(request)
    visible_post(request.db, pid, request.me.id)
    text = body_str(request, "body", max_len=1000)
    cid = request.db.run(
        "INSERT INTO comments (post_id, author_id, body, created_at) VALUES (?, ?, ?, ?)",
        pid,
        request.me.id,
        text,
        request.now,
    )
    comment = {
        "id": cid,
        "post_id": pid,
        "author_id": request.me.id,
        "body": text,
        "created_at": request.now,
    }
    return Response(201, {"comment": comment_json(request.db, comment)})


@route("DELETE", "/api/comments/{id}")
def delete_comment(request: Request) -> Response:
    cid = path_id(request)
    row = request.db.one("SELECT * FROM comments WHERE id = ?", cid)
    if row is None:
        raise HTTPError(404, "comment not found")
    post = visible_post(request.db, row["post_id"], request.me.id)
    if request.me.id != row["author_id"] and request.me.id != post["author_id"]:
        raise HTTPError(403, "forbidden")
    request.db.run("DELETE FROM comments WHERE id = ?", cid)
    return Response(200, {"deleted": cid})
