# Backend reference 2: friends (import from chatbook.core.api)

## Helpers (db: the request's database)
are_friends(db, a, b) -> bool
befriend(db, a, b, now) -> None         a and b become friends, both directions; also deletes
                                        the pending requests between them, in either direction
unfriend(db, a, b) -> None              removes the friendship, both directions
relationship(db, me, other) -> str      one of "self", "friends", "request_sent",
                                        "request_received", "none"
    self: the same id; request_sent: me asked other; request_received: other asked me
friend_ids(db, user_id) -> list[int]    the ids of the user's friends, ascending

## Tables
friend_requests(id, from_id, to_id, created_at)   a pending request; UNIQUE (from_id, to_id)
friendships(user_id, friend_id, created_at)       one row per direction (a->b and b->a)

The friends of me: SELECT friend_id FROM friendships WHERE user_id = ?
Write friendships only through befriend and unfriend.
