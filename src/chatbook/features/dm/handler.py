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

from chatbook.core.api import (
    HTTPError,
    Request,
    Response,
    are_friends,
    body_id,
    conversation_json,
    create_conversation,
    find_direct,
    require_user,
    route,
)


@route("POST", "/api/dm")
def open_dm(request: Request) -> Response:
    # Step 1: other = body_id(request, "user_id")
    other = body_id(request, "user_id")

    # Step 2: other == me -> 400
    if other == request.me.id:
        raise HTTPError(400, "Cannot open a conversation with yourself")

    # Step 3: require_user(db, other) -> 404
    require_user(request.db, other)

    # Step 4: not are_friends(db, me, other) -> 403
    if not are_friends(request.db, request.me.id, other):
        raise HTTPError(403, "You are not friends with this user")

    # Step 5: cid = find_direct(db, me, other)
    cid = find_direct(request.db, request.me.id, other)
    if cid is None:
        # Step 5.1: cid = create_conversation(db, "direct", "", me, [other], request.now)
        cid = create_conversation(request.db, "direct", "", request.me.id, [other], request.now)
        status = 201
    else:
        status = 200

    # Step 6: return Response(status, {"conversation": conversation_json(db, cid, me)})
    return Response(status, {"conversation": conversation_json(request.db, cid, request.me.id)})
