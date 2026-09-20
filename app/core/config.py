from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """
    Application configuration loaded from environment variables or a .env file.
    All fields are read at startup and validated by Pydantic.
    """

    # ── Blockchain ──────────────────────────────────────────────────────────────
    TRONGRID_KEY: str = ""           # TronGrid API key for TRON RPC access

    # ── AI / LLM ────────────────────────────────────────────────────────────────
    GEMINI_API_KEY: str = ""         # Google Gemini API key (google-genai SDK)
    GEMINI_MODEL: str = "gemini-3.6-flash"  # Verified working model on Google GenAI SDK

    # ── Graph Database ──────────────────────────────────────────────────────────
    NEO4J_URI: str = "bolt://localhost:7687"   # Neo4j Bolt/Aura connection URI
    NEO4J_USER: str = "neo4j"
    NEO4J_USERNAME: str = ""                   # Fallback / alias for Aura credentials
    NEO4J_PASSWORD: str = "password"
    NEO4J_DATABASE: str = ""                   # Leave empty for server default

    # ── Cache / Queue ───────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    UPSTASH_REDIS_REST_URL: str = ""           # Optional: auto-converts to rediss:// URI
    UPSTASH_REDIS_REST_TOKEN: str = ""         # Optional: Upstash access token / password

    # ── App Meta ────────────────────────────────────────────────────────────────
    APP_NAME: str = "ChainSleuth"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    CORS_ORIGINS: str = ""           # Comma-separated extra allowed origins (e.g. https://chainsleuth.onrender.com)

    @property
    def neo4j_user(self) -> str:
        """Returns the configured username, prioritizing NEO4J_USERNAME if present."""
        return self.NEO4J_USERNAME or self.NEO4J_USER or "neo4j"

    @property
    def redis_url(self) -> str:
        """Returns standard rediss:// connection URI, auto-constructed if Upstash REST credentials provided."""
        if self.UPSTASH_REDIS_REST_URL and self.UPSTASH_REDIS_REST_TOKEN:
            host = self.UPSTASH_REDIS_REST_URL.replace("https://", "").replace("http://", "").rstrip("/")
            return f"rediss://default:{self.UPSTASH_REDIS_REST_TOKEN}@{host}:6379"
        return self.REDIS_URL

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()
