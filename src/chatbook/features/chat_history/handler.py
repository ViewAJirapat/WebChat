"""chat_history: message history.

CONTRACT (keep this docstring; implement exactly this):
Notation: db = request.db, me = request.me.id.
GET /api/conversations/{id}/messages?limit=&before=
  1. cid = path_id(request); require_member(db, cid, me)              (404)
  2. limit = query_int(request, "limit", default=50, lo=1, hi=200)
  3. before = query_opt_int(request, "before")
     cursor = before if before is not None else 2**62
  4. rows, more = db.page("SELECT * FROM messages WHERE conversation_id = ? AND id < ?"
                          " ORDER BY id DESC", cid, cursor, limit=limit)
  5. rows.reverse()                      (oldest first)
  -> 200 {"messages": [message_json(db, r) for r in rows], "has_more": more}
Read-only.
"""

from chatbook.core.api import HTTPError, Request, Response, route


@route("GET", "/api/conversations/{id}/messages")
def list_messages(request: Request) -> Response:
    raise HTTPError(501, "not implemented")
