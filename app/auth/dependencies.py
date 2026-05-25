import json
from pathlib import Path

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from app.auth.jwt_handler import decode_token

# ── Load user store once at module import ─────────────────────────────────────
# Path is resolved relative to this file so it works regardless of where
# the server is launched from.
_USERS_FILE = Path(__file__).parent / "users.json"
_USERS: dict = json.loads(_USERS_FILE.read_text())

# HTTPBearer extracts the token from "Authorization: Bearer <token>" header.
# auto_error=False lets us return a custom 401 instead of FastAPI's default.
_bearer_scheme = HTTPBearer(auto_error=False)

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired token",
    headers={"WWW-Authenticate": "Bearer"},
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain-text password against a bcrypt hash.

    bcrypt.checkpw() re-hashes the plain password using the same salt
    embedded in the stored hash, then compares in constant time
    (preventing timing attacks).
    """
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


def authenticate_user(username: str, password: str) -> dict | None:
    """
    Validate username + password against the user store.

    Returns the user record dict on success, None if credentials are wrong.
    This is called by the /auth/login route.
    """
    user = _USERS.get(username)
    if user is None:
        return None
    if not verify_password(password, user["hashed_password"]):
        return None
    return {"username": username, "role": user["role"]}


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict:
    """
    FastAPI dependency — validates the JWT and returns the current user.

    Inject this into any route that requires authentication:
        @router.get("/protected")
        async def protected(user: dict = Depends(get_current_user)):
            return {"hello": user["username"]}

    Flow:
      1. HTTPBearer extracts the token from the Authorization header.
      2. decode_token() verifies signature + expiry.
      3. We confirm the username still exists in our user store.
      4. Return {"username": ..., "role": ...} to the route handler.

    Any failure raises HTTP 401.
    """
    if credentials is None:
        raise _CREDENTIALS_EXCEPTION

    try:
        payload = decode_token(credentials.credentials)
        username: str = payload.get("sub", "")
        role: str = payload.get("role", "")
    except JWTError:
        raise _CREDENTIALS_EXCEPTION

    if not username or username not in _USERS:
        raise _CREDENTIALS_EXCEPTION

    return {"username": username, "role": role}
