"""group_members: add a member to a group or leave it.

CONTRACT (keep this docstring; implement exactly this):
Notation: db = request.db, me = request.me.id.
POST /api/groups/{id}/members  body {"user_id"}  checks in this order:
  1. cid = path_id(request); conv = require_member(db, cid, me)      (404)
  2. conv["kind"] != "group" -> 400
  3. uid = body_id(request, "user_id")
  4. require_user(db, uid)                                            (404)
  5. uid in member_ids(db, cid) -> 409
  6. not are_friends(db, me, uid) -> 403
  7. add_member(db, cid, uid, request.now)
  -> 200 {"conversation": conversation_json(db, cid, me)}
DELETE /api/groups/{id}/members/me
  1. cid = path_id(request); conv = require_member(db, cid, me)      (404)
  2. conv["kind"] != "group" -> 400
  3. remove_member(db, cid, me)
  -> 200 {"left": cid}
Tables you may write: members only through add_member and remove_member.
"""

from chatbook.core.api import HTTPError, Request, Response, route


@route("POST", "/api/groups/{id}/members")
def add_member_route(request: Request) -> Response:
    raise HTTPError(501, "not implemented")


@route("DELETE", "/api/groups/{id}/members/me")
def leave_group(request: Request) -> Response:
    raise HTTPError(501, "not implemented")
