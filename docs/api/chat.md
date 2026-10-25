# Backend reference 3: conversations and messages (import from chatbook.core.api)

## Shapes (always built by the helpers below, never by hand)
U = {"id", "username", "display_name"}
M = {"id", "conversation_id", "sender": U, "body", "created_at"}
C = {"id", "kind": "direct" | "group", "title", "members": [U sorted by id],
     "last_message": M or None, "unread": int, "updated_at": int}
  title: direct = the other member's display_name; group = the stored title
  updated_at: the last message's created_at, else the conversation's created_at

## Helpers (db: the request's database)
create_conversation(db, kind, title, creator_id, member_ids, now) -> int
    the new id; members = the creator + member_ids; kind "direct" takes title "" and exactly
    one other member
find_direct(db, a, b) -> int | None                       the direct conversation of a and b
require_member(db, conversation_id, user_id) -> dict      the conversations row; 404 if missing
                                                          or the user is not a member
member_ids(db, conversation_id) -> list[int]              ascending
add_member(db, conversation_id, user_id, now) -> None     old messages are not unread for them
remove_member(db, conversation_id, user_id) -> None
post_message(db, conversation_id, sender_id, body, now) -> dict    inserts; returns M
message_json(db, row) -> dict                             M from a messages row
mark_read(db, conversation_id, user_id) -> int            marks all read; the new last_read_id
unread_count(db, conversation_id, user_id) -> int         others' messages after last_read_id
conversation_json(db, conversation_id, viewer_id) -> dict    C as seen by viewer_id

## Tables
conversations(id, kind, title, direct_key, created_by, created_at, last_message_id)
members(conversation_id, user_id, joined_at, last_read_id)
messages(id, conversation_id, sender_id, body, created_at)
Write messages, last_message_id and last_read_id only through the helpers above.
