"""Centralised, environment-driven configuration (12-factor).

All settings are read from environment variables / `.env`.
Validation happens at startup — the app fails fast on bad config.
"""

from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_JWT_SECRET = "dev-only-insecure-secret-change-me"


class Settings(BaseSettings):
    """Application settings. Extend per-step (auth, Redis, AI in later steps)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="Krushi Seva API")
    version: str = Field(default="0.1.0")
    environment: str = Field(default="development")
    log_level: str = Field(default="info")

    backend_host: str = Field(default="127.0.0.1")
    backend_port: int = Field(default=8000)

    api_v1_prefix: str = Field(default="/api/v1")

    # Comma-separated list, e.g. "http://localhost:3000,https://krushi.example.com"
    cors_origins: str = Field(default="http://localhost:3000")

    # ── Database (Step 2: PostgreSQL via psycopg, sync engine) ──
    # Placeholder default only — real deployments MUST set DATABASE_URL.
    database_url: str = Field(
        default="postgresql+psycopg://postgres:password@localhost:5432/krushi_seva"
    )
    database_pool_size: int = Field(default=10, ge=1)
    database_max_overflow: int = Field(default=20, ge=0)
    # Fail fast if the DB is unreachable (seconds). Keeps /health/db honest.
    database_connect_timeout: int = Field(default=5, ge=1)

    # ── Auth (Step 3: passwordless mobile-OTP + JWT) ──
    # Production MUST set a long random JWT_SECRET_KEY (validated below).
    jwt_secret_key: str = Field(default=_DEV_JWT_SECRET)
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=30, ge=1)
    refresh_token_expire_days: int = Field(default=30, ge=1)

    # OTP policy (service-level rate limiting, see auth module).
    otp_length: int = Field(default=6, ge=4, le=8)
    otp_expire_minutes: int = Field(default=10, ge=1)
    otp_max_attempts: int = Field(default=5, ge=1)
    otp_resend_cooldown_seconds: int = Field(default=60, ge=0)
    otp_max_sends_per_hour: int = Field(default=5, ge=1)

    # DEV-ONLY: when True (and NOT production), send-otp responses include the
    # OTP as `dev_otp` so frontend/tests work without an SMS provider.
    # NEVER enable in production — responses omit it there regardless.
    auth_dev_otp_enabled: bool = Field(default=True)

    # ── Weather (Step 7: provider abstraction + DB cache) ──
    weather_provider: str = Field(default="open-meteo")
    weather_api_key: str = Field(default="")
    weather_api_base_url: str = Field(default="https://api.open-meteo.com")
    weather_timeout_seconds: int = Field(default=10, ge=1, le=60)
    weather_current_ttl_minutes: int = Field(default=30, ge=1)
    weather_forecast_ttl_hours: int = Field(default=6, ge=1)

    # ── Market prices (Step 8: provider abstraction + DB cache) ──
    market_provider: str = Field(default="disabled")
    market_api_key: str = Field(default="")
    market_api_base_url: str = Field(default="")
    market_timeout_seconds: int = Field(default=10, ge=1, le=60)
    market_cache_ttl_minutes: int = Field(default=360, ge=1)

    # ── AI / RAG (Step 9: mock-first, keys NEVER in code/frontend/logs) ──
    ai_provider: str = Field(default="mock")
    ai_api_key: str = Field(default="")
    ai_model: str = Field(default="mock-model")
    ai_api_base_url: str = Field(default="")
    ai_timeout_seconds: int = Field(default=30, ge=1, le=300)
    ai_embedding_provider: str = Field(default="mock")
    ai_embedding_model: str = Field(default="mock-embed")
    ai_embedding_dim: int = Field(default=1536, ge=1)
    rag_top_k: int = Field(default=4, ge=1, le=20)
    rag_min_similarity: float = Field(default=0.15, ge=0.0, le=1.0)
    rag_max_context_chunks: int = Field(default=4, ge=1, le=20)
    rag_max_context_chars: int = Field(default=12000, ge=1000)
    rag_candidate_limit: int = Field(default=500, ge=10)
    ai_max_message_length: int = Field(default=2000, ge=100)
    ai_max_messages_per_hour: int = Field(default=30, ge=1)
    ai_max_history_messages: int = Field(default=20, ge=1, le=100)

    # ── Vision / crop image analysis (Step 10: mock-first, keys never exposed)
    vision_provider: str = Field(default="mock")
    vision_api_key: str = Field(default="")
    vision_model: str = Field(default="mock-vision")
    vision_api_base_url: str = Field(default="")
    vision_timeout_seconds: int = Field(default=60, ge=1, le=300)
    vision_max_images: int = Field(default=3, ge=1, le=5)
    vision_max_file_mb: int = Field(default=8, ge=1, le=50)
    vision_max_dimension: int = Field(default=4096, ge=256)
    vision_min_dimension: int = Field(default=200, ge=16)
    vision_max_analyses_per_hour: int = Field(default=10, ge=1)
    vision_storage_dir: str = Field(default="storage/crop_images")

    # ── Soil reports (Step 11: reuses vision storage abstraction, separate root)
    soil_report_max_mb: int = Field(default=10, ge=1, le=50)
    soil_storage_dir: str = Field(default="storage/soil_reports")
    health_storage_dir: str = Field(default="storage/health_photos")
    store_storage_dir: str = Field(default="storage/store_images")

    # ── Store commerce (Step 14: NO payment gateway in this step) ──
    order_delivery_charge: str = Field(default="0.00")
    cart_max_qty_per_item: int = Field(default=100, ge=1)
    cart_max_items: int = Field(default=50, ge=1)

    # ── Payments (Step 15: mock-first, keys NEVER in code/frontend/logs) ──
    # Providers: "mock" (deterministic dev/test, labelled) or "disabled".
    # Production REFUSES mock at startup (fail-fast, like AI/vision guards).
    payment_provider: str = Field(default="mock")
    payment_api_key: str = Field(default="")
    payment_api_secret: str = Field(default="")
    payment_api_base_url: str = Field(default="")
    payment_timeout_seconds: int = Field(default=10, ge=1, le=60)
    payment_webhook_secret: str = Field(default="")
    # Mock provider auto-approves when True (dev/test labelling only).
    payment_mock_approve: bool = Field(default=True)
    payment_currency: str = Field(default="INR")
    # ONLY bypass for unsigned webhooks: accepted only when environment !=
    # production AND payment_provider == mock AND this flag is True.
    # Default False (fail closed everywhere).
    payment_allow_unsigned_mock_webhook: bool = Field(default=False)

    # ── Khata ledger (Step 15: immutable entries, balance computed on read) ──
    khata_enabled: bool = Field(default=True)
    # Max allowed outstanding in paise (0 = no credit allowed). Surfaced in
    # the summary as `over_limit`; checkout itself never blocks on it.
    khata_credit_limit: int = Field(default=0, ge=0)

    # ── Inventory (Step 16: staff-gated stock management) ──
    # Comma-separated staff mobiles, e.g. "9876543210,9876543211".
    # Empty = no staff → all inventory write endpoints return 403.
    store_staff_mobiles: str = Field(default="")

    # ── POS counter billing (Step 18: staff discount cap) ──
    # Max discount (paise) a plain store_staff cashier may grant on one bill
    # (₹200 conservative cap). store_manager/admin are unlimited but the
    # discount may never exceed the subtotal. Plain staff above the cap get
    # 403 POS_DISCOUNT_LIMIT.
    pos_staff_max_discount_paise: int = Field(default=20000, ge=0)

    @field_validator("environment")
    @classmethod
    def _validate_environment(cls, value: str) -> str:
        allowed = {"development", "staging", "production", "test"}
        if value not in allowed:
            raise ValueError(f"ENVIRONMENT must be one of {sorted(allowed)}")
        return value

    @field_validator("jwt_secret_key")
    @classmethod
    def _validate_jwt_secret(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters")
        return value

    @field_validator("weather_provider")
    @classmethod
    def _validate_weather_provider(cls, value: str) -> str:
        allowed = {"open-meteo", "disabled"}
        if value not in allowed:
            raise ValueError(f"WEATHER_PROVIDER must be one of {sorted(allowed)}")
        return value

    @field_validator("market_provider")
    @classmethod
    def _validate_market_provider(cls, value: str) -> str:
        allowed = {"disabled"}
        if value not in allowed:
            raise ValueError(f"MARKET_PROVIDER must be one of {sorted(allowed)}")
        return value

    @field_validator("ai_provider", "ai_embedding_provider")
    @classmethod
    def _validate_ai_providers(cls, value: str) -> str:
        allowed = {"mock", "disabled"}
        if value not in allowed:
            raise ValueError(f"AI providers must be one of {sorted(allowed)}")
        return value

    @field_validator("vision_provider")
    @classmethod
    def _validate_vision_provider(cls, value: str) -> str:
        allowed = {"mock", "disabled"}
        if value not in allowed:
            raise ValueError(f"VISION_PROVIDER must be one of {sorted(allowed)}")
        return value

    @field_validator("payment_provider")
    @classmethod
    def _validate_payment_provider(cls, value: str) -> str:
        allowed = {"mock", "disabled"}
        if value not in allowed:
            raise ValueError(f"PAYMENT_PROVIDER must be one of {sorted(allowed)}")
        return value

    @model_validator(mode="after")
    def _validate_production(self) -> "Settings":
        """Fail fast on unsafe production configuration."""
        if self.environment == "production":
            if self.jwt_secret_key == _DEV_JWT_SECRET:
                raise ValueError(
                    "Production requires a unique JWT_SECRET_KEY "
                    "(default dev secret is not allowed)."
                )
            if self.auth_dev_otp_enabled:
                raise ValueError("Production requires AUTH_DEV_OTP_ENABLED=false.")
            if self.ai_provider == "mock" or self.ai_embedding_provider == "mock":
                raise ValueError(
                    "Production requires real AI providers "
                    "(mock AI must never serve farmers)."
                )
            if self.vision_provider == "mock":
                raise ValueError(
                    "Production requires a real vision provider "
                    "(mock vision must never serve farmers)."
                )
            if self.payment_provider == "mock":
                raise ValueError(
                    "Production requires a real payment provider "
                    "(mock payments must never serve farmers)."
                )
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse CORS_ORIGINS into a clean list."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance (override in tests via dependency)."""
    return Settings()
