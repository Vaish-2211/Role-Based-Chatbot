"""
Unit tests for JWT token creation/decoding and password verification.

These tests run entirely in memory — no server, no database needed.
We override the settings with controlled values using monkeypatch so
the tests are hermetic (not affected by whatever is in your .env file).
"""

import time

import pytest
from jose import JWTError


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def patch_settings(monkeypatch):
    """
    Inject deterministic settings for every test in this module.

    autouse=True means this fixture runs automatically — you don't need
    to list it as a parameter in each test function.
    """
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-unit-tests")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("JWT_EXPIRE_MINUTES", "60")

    # Clear the lru_cache so pydantic-settings re-reads our patched env vars.
    from app.core.settings import get_settings
    get_settings.cache_clear()

    yield

    # Clean up after the test.
    get_settings.cache_clear()


# ── JWT Tests ─────────────────────────────────────────────────────────────────

def test_create_and_decode_token():
    """A freshly created token should decode to the same payload."""
    from app.auth.jwt_handler import create_access_token, decode_token

    token = create_access_token({"sub": "alice_finance", "role": "finance"})

    # Token must be a non-empty string
    assert isinstance(token, str)
    assert len(token) > 0

    payload = decode_token(token)
    assert payload["sub"] == "alice_finance"
    assert payload["role"] == "finance"
    assert "exp" in payload  # expiry claim must be present


def test_token_contains_all_roles():
    """Tokens can be created for every role without error."""
    from app.auth.jwt_handler import create_access_token, decode_token

    roles = ["c_level", "finance", "marketing", "hr", "engineering", "employee"]
    for role in roles:
        token = create_access_token({"sub": f"user_{role}", "role": role})
        payload = decode_token(token)
        assert payload["role"] == role


def test_tampered_token_raises():
    """Modifying the token payload must invalidate the signature."""
    from app.auth.jwt_handler import create_access_token, decode_token

    token = create_access_token({"sub": "eve_employee", "role": "employee"})

    # Tamper: flip the last character
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")

    with pytest.raises(JWTError):
        decode_token(tampered)


def test_wrong_secret_raises():
    """A token signed with a different key must be rejected."""
    from app.core.settings import get_settings
    from jose import jwt

    settings = get_settings()
    token = jwt.encode(
        {"sub": "attacker", "role": "c_level"},
        "wrong-secret",
        algorithm=settings.jwt_algorithm,
    )

    from app.auth.jwt_handler import decode_token
    with pytest.raises(JWTError):
        decode_token(token)


def test_expired_token_raises(monkeypatch):
    """An expired token (exp in the past) must be rejected."""
    from app.core.settings import get_settings
    from jose import jwt

    settings = get_settings()
    # exp = 1 second in the past
    expired_payload = {"sub": "alice_finance", "role": "finance", "exp": int(time.time()) - 1}
    token = jwt.encode(expired_payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    from app.auth.jwt_handler import decode_token
    with pytest.raises(JWTError):
        decode_token(token)


# ── Password Tests ─────────────────────────────────────────────────────────────

def test_authenticate_user_valid():
    """authenticate_user returns the user dict when credentials are correct."""
    from app.auth.dependencies import authenticate_user

    user = authenticate_user("alice_finance", "alice@123")
    assert user is not None
    assert user["username"] == "alice_finance"
    assert user["role"] == "finance"


def test_authenticate_user_wrong_password():
    """authenticate_user returns None for a wrong password."""
    from app.auth.dependencies import authenticate_user

    result = authenticate_user("alice_finance", "wrong_password")
    assert result is None


def test_authenticate_user_unknown_user():
    """authenticate_user returns None for a username that does not exist."""
    from app.auth.dependencies import authenticate_user

    result = authenticate_user("nonexistent_user", "any_password")
    assert result is None


def test_all_test_users_authenticate():
    """Every hardcoded test user can authenticate with their known password."""
    from app.auth.dependencies import authenticate_user

    credentials = [
        ("tony_sharma",   "tony@123"),
        ("alice_finance", "alice@123"),
        ("bob_marketing", "bob@123"),
        ("carol_hr",      "carol@123"),
        ("dave_eng",      "dave@123"),
        ("eve_employee",  "eve@123"),
    ]
    for username, password in credentials:
        user = authenticate_user(username, password)
        assert user is not None, f"authenticate_user failed for {username}"
