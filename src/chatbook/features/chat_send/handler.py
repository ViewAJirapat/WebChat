"""chat_send: send a message and mark a conversation read.

CONTRACT (keep this docstring; implement exactly this):
Notation: db = request.db, me = request.me.id.
POST /api/conversations/{id}/messages  body {"body"}  checks in this order:
  1. cid = path_id(request); conv = require_member(db, cid, me)      (404)
  2. text = body_str(request, "body", max_len=2000)
  3. if conv["kind"] == "direct": other = the id in member_ids(db, cid) that is not me;
     not are_friends(db, me, other) -> 403
  -> 201 {"message": post_message(db, cid, me, text, request.now)}
POST /api/conversations/{id}/read   (no body)
  1. cid = path_id(request); require_member(db, cid, me)              (404)
  2. last = mark_read(db, cid, me)
  -> 200 {"conversation_id": cid, "last_read_id": last, "unread": unread_count(db, cid, me)}
Tables you may write: messages, conversations.last_message_id and members.last_read_id only
through post_message and mark_read.
"""

from chatbook.core.api import HTTPError, Request, Response, route


@route("POST", "/api/conversations/{id}/messages")
def send_message(request: Request) -> Response:
    raise HTTPError(501, "not implemented")


@route("POST", "/api/conversations/{id}/read")
def read_conversation(request: Request) -> Response:
    raise HTTPError(501, "not implemented")
