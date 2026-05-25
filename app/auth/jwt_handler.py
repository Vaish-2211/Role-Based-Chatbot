from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.core.settings import get_settings

settings = get_settings()


def create_access_token(data: dict) -> str:
    """
    Create a signed JWT access token.

    `data` must include at minimum:
        {"sub": "<username>", "role": "<role>"}

    The token also embeds an `exp` (expiry) claim calculated from
    JWT_EXPIRE_MINUTES in settings.

    How it works:
      - We copy `data` to avoid mutating the caller's dict.
      - We add `exp` as a UTC timestamp.
      - `jwt.encode()` serialises the payload, signs it with our
        secret key using HS256, and returns a compact string.

    Example:
        token = create_access_token({"sub": "alice_finance", "role": "finance"})
        # → "eyJhbG..."
    """
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload["exp"] = expire

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str) -> dict:
    """
    Decode and validate a JWT access token.

    Returns the decoded payload dict on success.
    Raises JWTError if:
      - The signature is invalid (tampered token)
      - The token has expired (exp claim is in the past)
      - The token is malformed

    The caller (FastAPI dependency) is responsible for catching JWTError
    and converting it to an HTTP 401 response.

    Example:
        payload = decode_token("eyJhbG...")
        username = payload["sub"]   # → "alice_finance"
        role     = payload["role"]  # → "finance"
    """
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
