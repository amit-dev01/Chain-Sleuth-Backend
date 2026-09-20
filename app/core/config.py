from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """
    Application configuration loaded from environment variables or a .env file.
    All fields are read at startup and validated by Pydantic.
    """

    # ── Blockchain ──────────────────────────────────────────────────────────────
    TRONGRID_KEY: str = ""           # TronGrid API key for TRON RPC access

    # ── Graph Database ──────────────────────────────────────────────────────────
    NEO4J_URI: str = "bolt://localhost:7687"   # Neo4j Bolt connection URI
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"

    # ── Cache / Queue ───────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── App Meta ────────────────────────────────────────────────────────────────
    APP_NAME: str = "ChainSleuth"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()
