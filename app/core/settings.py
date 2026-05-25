from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central configuration object.

    pydantic-settings automatically reads values from:
      1. Environment variables (highest priority)
      2. A .env file in the working directory
      3. The field default (lowest priority)

    Any field without a default that is missing from the environment will
    raise a ValidationError at startup — catching misconfiguration early.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,   # GROQ_API_KEY and groq_api_key both work
        extra="ignore",         # silently ignore unknown env vars
    )

    # ── LLM ───────────────────────────────────────────────────────────────────
    groq_api_key: str

    # ── Vector Database ───────────────────────────────────────────────────────
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "finsolve_docs"

    # ── Authentication ────────────────────────────────────────────────────────
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # ── LangSmith Monitoring ──────────────────────────────────────────────────
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "finsolve-rag"

    # ── App ───────────────────────────────────────────────────────────────────
    backend_url: str = "http://localhost:8000"
    log_level: str = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the cached Settings singleton.

    The @lru_cache decorator ensures the .env file is parsed exactly once,
    no matter how many times get_settings() is called across the app.

    Usage:
        from app.core.settings import get_settings
        settings = get_settings()
        print(settings.groq_api_key)
    """
    return Settings()
