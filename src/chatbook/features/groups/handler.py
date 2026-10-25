"""groups: start a group chat and rename it.

CONTRACT (keep this docstring; implement exactly this):
Notation: db = request.db, me = request.me.id.
POST /api/groups  body {"title", "member_ids"}  checks in this order:
  1. title = body_str(request, "title", max_len=50)
  2. ids = [i for i in body_ids(request, "member_ids") if i != me]
  3. not ids -> 400;  len(ids) > 49 -> 400
  4. for each id in ids, in order: require_user(db, id) (404); not are_friends(db, me, id) -> 403
  5. cid = create_conversation(db, "group", title, me, ids, request.now)
  -> 201 {"conversation": conversation_json(db, cid, me)}
PUT /api/groups/{id}  body {"title"}
  1. cid = path_id(request); conv = require_member(db, cid, me)      (404)
  2. conv["kind"] != "group" -> 400
  3. title = body_str(request, "title", max_len=50)
  4. db.run("UPDATE conversations SET title = ? WHERE id = ?", title, cid)
  -> 200 {"conversation": conversation_json(db, cid, me)}
Tables you may write: conversations.title; conversations and members only through
create_conversation.
"""

from chatbook.core.api import HTTPError, Request, Response, route


@route("POST", "/api/groups")
def create_group(request: Request) -> Response:
    raise HTTPError(501, "not implemented")


@route("PUT", "/api/groups/{id}")
def rename_group(request: Request) -> Response:
    raise HTTPError(501, "not implemented")
