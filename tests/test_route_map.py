"""The exact route and page tables (DESIGN 3.17). A change here is a staff frame commit."""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from chatbook import create_app
from chatbook.core.registry import discover_ui

REPO = Path(__file__).resolve().parents[1]
FEATURES = REPO / "src" / "chatbook" / "features"

# (method, pattern, public, feature)
ROUTES = [
    ("GET", "/api/health", True, "core"),
    ("GET", "/api/session", False, "core"),
    ("DELETE", "/api/session", False, "core"),
    ("POST", "/api/auth/register", True, "accounts"),
    ("POST", "/api/auth/login", True, "accounts"),
    ("GET", "/api/users", False, "people"),
    ("POST", "/api/friends/requests", False, "friend_requests"),
    ("GET", "/api/friends/requests", False, "friend_requests"),
    ("POST", "/api/friends/requests/{id}/accept", False, "friend_answers"),
    ("POST", "/api/friends/requests/{id}/decline", False, "friend_answers"),
    ("DELETE", "/api/friends/requests/{id}", False, "friend_answers"),
    ("GET", "/api/friends", False, "friends"),
    ("DELETE", "/api/friends/{id}", False, "friends"),
    ("POST", "/api/dm", False, "dm"),
    ("POST", "/api/groups", False, "groups"),
    ("PUT", "/api/groups/{id}", False, "groups"),
    ("POST", "/api/groups/{id}/members", False, "group_members"),
    ("DELETE", "/api/groups/{id}/members/me", False, "group_members"),
    ("GET", "/api/conversations", False, "conversations"),
    ("GET", "/api/conversations/{id}", False, "conversations"),
    ("POST", "/api/conversations/{id}/messages", False, "chat_send"),
    ("POST", "/api/conversations/{id}/read", False, "chat_send"),
    ("GET", "/api/conversations/{id}/messages", False, "chat_history"),
    ("GET", "/api/updates", False, "updates"),
    ("GET", "/api/users/{id}", False, "profiles"),
    ("PUT", "/api/profile", False, "profiles"),
    ("POST", "/api/posts", False, "posts"),
    ("GET", "/api/feed", False, "posts"),
    ("GET", "/api/posts/{id}", False, "posts"),
    ("DELETE", "/api/posts/{id}", False, "posts"),
    ("POST", "/api/posts/{id}/like", False, "likes"),
    ("DELETE", "/api/posts/{id}/like", False, "likes"),
    ("GET", "/api/posts/{id}/likes", False, "likes"),
    ("GET", "/api/posts/{id}/comments", False, "comments"),
    ("POST", "/api/posts/{id}/comments", False, "comments"),
    ("DELETE", "/api/comments/{id}", False, "comments"),
    ("GET", "/api/friends/online", False, "presence"),
    ("GET", "/api/friends/suggestions", False, "suggestions"),
]

# (name, nav, order, public, file)
PAGES = [
    ("login", None, 100, True, "page_login"),
    ("inbox", "Chats", 10, False, "page_inbox"),
    ("friends", "Friends", 20, False, "page_friends"),
    ("people", "People", 30, False, "page_people"),
    ("discover", "Discover", 35, False, "page_discover"),
    ("feed", "Feed", 40, False, "page_feed"),
    ("profile", "Profile", 50, False, "page_profile"),
    ("chat", None, 100, False, "page_chat"),
    ("group_new", None, 100, False, "page_group_new"),
    ("group", None, 100, False, "page_group"),
    ("post", None, 100, False, "page_post"),
]

UI_FEATURES = sorted([page[4] for page in PAGES] + ["badges"])


def test_route_table_is_exact() -> None:
    routes = create_app().routes
    found = [(r.method, r.pattern, r.public, r.feature) for r in routes]
    assert len(found) == len(set(found)), "a route is registered twice"
    assert sorted(found) == sorted(ROUTES)


def test_ui_features_are_exact() -> None:
    assert discover_ui() == UI_FEATURES
    assert create_app().ui_features == UI_FEATURES
    assert sorted(p.parent.name for p in FEATURES.glob("*/ui.js")) == UI_FEATURES


def load_all() -> dict[str, Any]:
    """Every features/*/ui.js evaluated together in one runner context (uirun load_all)."""
    node = shutil.which("node")
    assert node, "install Node.js 24 and put it on PATH"
    scenario = {
        "cb": str(REPO / "src" / "chatbook" / "core" / "static" / "cb.js"),
        "files": [str(p) for p in sorted(FEATURES.glob("*/ui.js"))],
        "load_all": True,
    }
    proc = subprocess.run(
        [node, str(REPO / "tools" / "uirun.js")],
        input=json.dumps(scenario),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        env={**os.environ, "TZ": "UTC"},
        cwd=str(REPO),
    )
    assert proc.returncode == 0, proc.stderr
    result: dict[str, Any] = json.loads(proc.stdout)
    return result


def test_all_ui_files_load_together_without_errors() -> None:
    result = load_all()
    assert result["errors"] == []
    assert sorted(result) == ["errors", "pages"]  # load_all reports nothing else
    pages = [(p["name"], p["nav"], p["order"], p["public"], p["file"]) for p in result["pages"]]
    assert len(pages) == len({p[0] for p in pages}), "a page name is registered twice"
    assert sorted(pages, key=lambda p: p[0]) == sorted(PAGES, key=lambda p: p[0])
