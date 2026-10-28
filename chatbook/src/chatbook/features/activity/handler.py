"""activity: my comments and likes on posts I can no longer see.

CONTRACT (keep this docstring; implement exactly this):
Notation: db = request.db, me = request.me.id (write both as the function's first lines).
Hidden post: its author is neither me nor a friend of me (e.g. after an unfriend).
GET /api/activity/hidden                                                       (read-only)
  cs = db.all("SELECT c.id, c.post_id, c.body, c.created_at, p.author_id AS post_author_id"
              " FROM comments c JOIN posts p ON p.id = c.post_id"
              " WHERE c.author_id = ? AND p.author_id != ? AND p.author_id NOT IN"
              " (SELECT friend_id FROM friendships WHERE user_id = ?)"
              " ORDER BY c.id DESC LIMIT 100", me, me, me)
  ls = db.all("SELECT l.post_id, l.created_at, p.author_id AS post_author_id"
              " FROM likes l JOIN posts p ON p.id = l.post_id"
              " WHERE l.user_id = ? AND p.author_id != ? AND p.author_id NOT IN"
              " (SELECT friend_id FROM friendships WHERE user_id = ?)"
              " ORDER BY l.created_at DESC, l.post_id DESC LIMIT 100", me, me, me)
  -> 200 {"comments": [{"id": r["id"], "post_id": r["post_id"],
                        "post_author": user_json(require_user(db, r["post_author_id"])),
                        "body": r["body"], "created_at": r["created_at"]} for r in cs],
          "likes": [{"post_id": r["post_id"],
                     "post_author": user_json(require_user(db, r["post_author_id"])),
                     "created_at": r["created_at"]} for r in ls]}
Only my own comments and likes; never the post's body, its counts or other users' rows.
"""

from chatbook.core.api import Request, Response, require_user, route, user_json


@route("GET", "/api/activity/hidden")
def hidden_activity(request: Request) -> Response:
    db = request.db
    me = request.me.id

    cs = db.all(
        "SELECT c.id, c.post_id, c.body, c.created_at, p.author_id AS post_author_id"
        " FROM comments c JOIN posts p ON p.id = c.post_id"
        " WHERE c.author_id = ? AND p.author_id != ? AND p.author_id NOT IN"
        " (SELECT friend_id FROM friendships WHERE user_id = ?)"
        " ORDER BY c.id DESC LIMIT 100",
        me,
        me,
        me,
    )

    ls = db.all(
        "SELECT l.post_id, l.created_at, p.author_id AS post_author_id"
        " FROM likes l JOIN posts p ON p.id = l.post_id"
        " WHERE l.user_id = ? AND p.author_id != ? AND p.author_id NOT IN"
        " (SELECT friend_id FROM friendships WHERE user_id = ?)"
        " ORDER BY l.created_at DESC, l.post_id DESC LIMIT 100",
        me,
        me,
        me,
    )

    comments = [
        {
            "id": r["id"],
            "post_id": r["post_id"],
            "post_author": user_json(require_user(db, r["post_author_id"])),
            "body": r["body"],
            "created_at": r["created_at"],
        }
        for r in cs
    ]

    likes = [
        {
            "post_id": r["post_id"],
            "post_author": user_json(require_user(db, r["post_author_id"])),
            "created_at": r["created_at"],
        }
        for r in ls
    ]

    return Response(200, {"comments": comments, "likes": likes})
