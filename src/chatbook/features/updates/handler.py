"""updates: badge counts.

CONTRACT (keep this docstring; implement exactly this):
Notation: db = request.db, me = request.me.id.
GET /api/updates
  rows = db.all("SELECT conversation_id FROM members WHERE user_id = ?", me)
  counts = [unread_count(db, r["conversation_id"], me) for r in rows]
  requests = int(db.value("SELECT COUNT(*) FROM friend_requests WHERE to_id = ?", me))
  -> 200 {"unread_total": sum(counts),
          "unread_conversations": the number of counts that are > 0,
          "friend_requests": requests}
Read-only.
"""

from chatbook.core.api import HTTPError, Request, Response, route


@route("GET", "/api/updates")
def get_updates(request: Request) -> Response:
    raise HTTPError(501, "not implemented")
