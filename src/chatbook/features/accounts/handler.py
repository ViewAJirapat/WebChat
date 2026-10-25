"""accounts: register and log in.

CONTRACT (keep this docstring; implement exactly this):
POST /api/auth/register (public) body {"username", "password", "display_name"}
  1. username = body_str(request, "username", max_len=20).lower()
     re.fullmatch(r"[a-z0-9_]{3,20}", username) fails -> 400
  2. password = body_str(request, "password", min_len=8, max_len=128, strip=False)
  3. display_name = body_str(request, "display_name", max_len=50)
  4. user = create_user(request.db, username, password, display_name, request.now)  (409)
  5. token = new_session(request.db, user.id, request.now)
  -> 201 {"token": token, "user": user_json(user)}
POST /api/auth/login (public) body {"username", "password"}
  1. username = body_str(request, "username", max_len=50).lower()
  2. password = body_str(request, "password", max_len=128, strip=False)
  3. user = check_password(request.db, username, password); None -> 401
  -> 200 {"token": new_session(request.db, user.id, request.now), "user": user_json(user)}
"""

from chatbook.core.api import HTTPError, Request, Response, route


@route("POST", "/api/auth/register", public=True)
def register(request: Request) -> Response:
    raise HTTPError(501, "not implemented")


@route("POST", "/api/auth/login", public=True)
def login(request: Request) -> Response:
    raise HTTPError(501, "not implemented")
