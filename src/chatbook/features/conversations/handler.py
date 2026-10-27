"""conversations: the inbox list and one conversation.

CONTRACT (keep this docstring; implement exactly this):
Notation: db = request.db, me = request.me.id.
GET /api/conversations
  rows = db.all("SELECT conversation_id FROM members WHERE user_id = ?", me)
  items = [conversation_json(db, r["conversation_id"], me) for r in rows]
  items.sort(key=lambda c: (c["updated_at"], c["id"]), reverse=True)
  -> 200 {"conversations": items}
GET /api/conversations/{id}
  cid = path_id(request); require_member(db, cid, me)                 (404)
  rows = db.all("SELECT user_id, last_read_id FROM members WHERE conversation_id = ?"
                " ORDER BY user_id", cid)
  reads = [{"user_id": r["user_id"], "last_read_id": r["last_read_id"]} for r in rows]
  -> 200 {"conversation": conversation_json(db, cid, me), "reads": reads}
Read-only.
"""

from chatbook.core.api import Request, Response, conversation_json, path_id, require_member, route


@route("GET", "/api/conversations")
def list_conversations(request: Request) -> Response:
    rows = request.db.all("SELECT conversation_id FROM members WHERE user_id = ?", request.me.id)
    items = [conversation_json(request.db, r["conversation_id"], request.me.id) for r in rows]
    items.sort(key=lambda c: (c["updated_at"], c["id"]), reverse=True)
    return Response(200, {"conversations": items})


@route("GET", "/api/conversations/{id}")
def get_conversation(request: Request) -> Response:
    cid = path_id(request)
    require_member(request.db, cid, request.me.id)
    rows = request.db.all(
        "SELECT user_id, last_read_id FROM members WHERE conversation_id = ? ORDER BY user_id", cid
    )
    reads = [{"user_id": r["user_id"], "last_read_id": r["last_read_id"]} for r in rows]
    return Response(
        200, {"conversation": conversation_json(request.db, cid, request.me.id), "reads": reads}
    )
