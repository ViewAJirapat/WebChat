"""dm: open a direct conversation with a friend.

CONTRACT (keep this docstring; implement exactly this):
Notation: db = request.db, me = request.me.id.
POST /api/dm  body {"user_id"}  checks in this order:
  1. other = body_id(request, "user_id")
  2. other == me -> 400
  3. require_user(db, other)                                   (404)
  4. not are_friends(db, me, other) -> 403
  5. cid = find_direct(db, me, other)
     found -> status 200; else cid = create_conversation(db, "direct", "", me, [other],
     request.now) and status 201
  -> status {"conversation": conversation_json(db, cid, me)}
Tables you may write: conversations and members only through create_conversation.
"""

from chatbook.core.api import HTTPError, Request, Response, route


@route("POST", "/api/dm")
def open_dm(request: Request) -> Response:
    raise HTTPError(501, "not implemented")
