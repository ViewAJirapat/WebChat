"""Serve the app: `python -m chatbook [--demo]`.

Environment: PORT (default 8000), HOST (default 127.0.0.1), CHATBOOK_DB (default chatbook.db
in the current directory).
"""

import argparse
import os
import socketserver
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

from chatbook.app import App, create_app
from chatbook.core import demo


class ThreadingWSGIServer(socketserver.ThreadingMixIn, WSGIServer):
    """One thread per connection, so idle (preconnect) sockets cannot stall the server.
    The App's lock still runs one request at a time."""

    daemon_threads = True


class RequestHandler(WSGIRequestHandler):
    """Drops a connection that stays silent for `timeout` seconds, so a stuck client does not
    keep its thread forever. A silent socket is closed quietly (no traceback); a body that
    stops arriving ends that request with a 400 (App.wsgi)."""

    timeout = 30

    def handle(self) -> None:
        try:
            super().handle()
        except TimeoutError:
            self.close_connection = True


def seed_demo(app: App) -> bool:
    """Seed the demo data if the users table is empty; True if it seeded."""
    if app.db.value("SELECT COUNT(*) FROM users"):
        return False
    app.db._begin()
    try:
        demo.seed(app.db, app.clock.now_ms())
    except BaseException:
        app.db._rollback()
        raise
    app.db._commit()
    return True


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m chatbook", description=__doc__)
    parser.add_argument("--demo", action="store_true", help="seed demo users on an empty DB")
    args = parser.parse_args(argv)
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    db_path = os.environ.get("CHATBOOK_DB", "chatbook.db")
    app = create_app(db_path)
    if args.demo:
        if seed_demo(app):
            print("demo: seeded; log in as (username / password):")
            for username, name in demo.DEMO_USERS:
                print(f"  {username} / {demo.DEMO_PASSWORD}   ({name})")
        else:
            print("demo: the database already has users; nothing seeded")
    with make_server(
        host, port, app.wsgi, server_class=ThreadingWSGIServer, handler_class=RequestHandler
    ) as server:
        for r in app.routes:
            print(f"{r.method:<6} {r.pattern:<40} {r.feature}")
        for feature in app.ui_features:
            print(f"ui     /ui/{feature}.js")
        print(f"database {db_path}")
        # flush: when stdout is a pipe or a file (a tool runs the server), show this at once
        print(f"chatbook on http://{host}:{port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("stopped")


if __name__ == "__main__":
    main()
