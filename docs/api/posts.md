# Backend reference 4: posts, likes, comments (import from chatbook.core.api)

## Helper (db: the request's database)
visible_post(db, post_id, viewer_id) -> dict
    the posts row; 404 unless its author is the viewer or a friend of the viewer
can_see_post(db, post_id, viewer_id) -> bool
    True if the post exists and its author is the viewer or a friend of the viewer;
    never raises. A post is hidden from me when this is False (e.g. after an unfriend)

## Tables
posts(id, author_id, body, created_at)
likes(post_id, user_id, created_at)                one row per (post_id, user_id)
comments(id, post_id, author_id, body, created_at)
friendships(user_id, friend_id, created_at)        one row per direction, for feed queries:
    the friends of me are SELECT friend_id FROM friendships WHERE user_id = ?
No foreign keys: deleting a post means deleting its likes and comments first.
