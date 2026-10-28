"""The public contract: the only chatbook module features import (see docs/api/*.md)."""

from chatbook.core.chat import (
    add_member,
    conversation_json,
    create_conversation,
    find_direct,
    mark_read,
    member_ids,
    message_json,
    post_message,
    remove_member,
    require_member,
    unread_count,
)
from chatbook.core.http import HTTPError, Request, Response
from chatbook.core.registry import route
from chatbook.core.social import (
    are_friends,
    befriend,
    friend_ids,
    relationship,
    unfriend,
    visible_post,
)
from chatbook.core.store import Db
from chatbook.core.users import (
    User,
    check_password,
    create_user,
    get_user,
    new_session,
    require_user,
    user_json,
)
from chatbook.core.validate import (
    body_id,
    body_ids,
    body_str,
    path_id,
    query_int,
    query_opt_int,
    query_str,
)

__all__ = [
    "route",
    "Request",
    "Response",
    "HTTPError",
    "User",
    "Db",
    "body_str",
    "body_id",
    "body_ids",
    "path_id",
    "query_str",
    "query_int",
    "query_opt_int",
    "user_json",
    "get_user",
    "require_user",
    "create_user",
    "check_password",
    "new_session",
    "are_friends",
    "befriend",
    "unfriend",
    "relationship",
    "friend_ids",
    "visible_post",
    "create_conversation",
    "find_direct",
    "require_member",
    "member_ids",
    "add_member",
    "remove_member",
    "post_message",
    "message_json",
    "mark_read",
    "unread_count",
    "conversation_json",
]
