from pydantic import BaseModel, Field


# ── Auth ──────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    """Body for POST /api/v1/auth/login."""

    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class TokenResponse(BaseModel):
    """
    Returned by POST /api/v1/auth/login on success.

    `access_token` is a signed JWT the client must include in every
    subsequent request as:  Authorization: Bearer <access_token>
    """

    access_token: str
    token_type: str = "bearer"
    role: str


# ── Chat ──────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    """Body for POST /api/v1/chat."""

    query: str = Field(..., min_length=1, max_length=1000)
    session_id: str = Field(
        ...,
        description="Client-generated UUID that groups messages into a conversation.",
    )


class Source(BaseModel):
    """
    A single document chunk that contributed to the answer.
    Rendered as a citation in the Streamlit frontend.
    """

    source_file: str
    department: str
    section: str = ""


class ChatResponse(BaseModel):
    """
    Returned by POST /api/v1/chat (non-streaming fallback).

    The streaming endpoint uses SSE and does not use this model directly,
    but it is useful for tests and the /docs playground.
    """

    answer: str
    sources: list[Source] = []
    session_id: str


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    """Returned by GET /health."""

    status: str = "ok"


class ReadyResponse(BaseModel):
    """Returned by GET /ready — confirms Qdrant is reachable."""

    status: str
    qdrant: str
