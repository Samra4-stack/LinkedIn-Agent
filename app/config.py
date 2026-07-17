"""
app/config.py
─────────────
Central configuration module using Pydantic Settings.
Loads all environment variables from .env file.
Single source of truth for all app configuration.
"""

from __future__ import annotations

from functools import lru_cache
from typing import List, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ─── Application ─────────────────────────────────────────
    app_name: str = Field(default="LinkedIn AI Agent")
    app_env: Literal["development", "staging", "production"] = Field(default="development")
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8000)
    app_base_url: str = Field(default="")
    debug: bool = Field(default=True)
    secret_key: str = Field(default="change-this-in-production")

    # ─── Database ─────────────────────────────────────────────
    database_url: str = Field(default="sqlite:////app/data/linkedin_agent.db")

    # ─── AI Providers ─────────────────────────────────────────
    # Supported: "groq" | "gemini" | "openai"
    ai_provider: Literal["openai", "gemini", "groq"] = Field(default="groq")

    # Groq (OpenAI-compatible, free tier available)
    groq_api_key: str = Field(default="")
    groq_model: str = Field(default="llama-3.3-70b-specdec")
    groq_base_url: str = Field(default="https://api.groq.com/openai/v1")

    # OpenAI (also used as fallback key field for Groq via OPENAI_API_KEY)
    openai_api_key: str = Field(default="")
    openai_model: str = Field(default="gpt-4o")
    openai_max_tokens: int = Field(default=1500)
    openai_temperature: float = Field(default=0.8)

    # Google Gemini
    gemini_api_key: str = Field(default="")
    gemini_model: str = Field(default="gemini-1.5-pro")

    # ─── Image Providers ─────────────────────────────────────
    # Note: "dalle" requires OpenAI key — removed from default when using Groq/Gemini
    image_provider_priority: str = Field(default="pixabay,pexels,unsplash")
    
    # ─── Notifications ───────────────────────────────────────
    smtp_server: str = Field(default="smtp.gmail.com")
    smtp_port: int = Field(default=465)
    smtp_user: str = Field(default="")
    smtp_password: str = Field(default="")
    notification_email: str = Field(default="")
    unsplash_api_key: str = Field(default="")
    pexels_api_key: str = Field(default="")
    pixabay_api_key: str = Field(default="")
    dalle_image_size: str = Field(default="1024x1024")
    dalle_image_quality: str = Field(default="hd")
    dalle_image_style: str = Field(default="vivid")

    # ─── LinkedIn ─────────────────────────────────────────────
    linkedin_client_id: str = Field(default="")
    linkedin_client_secret: str = Field(default="")
    linkedin_access_token: str = Field(default="")
    linkedin_redirect_uri: str = Field(default="http://localhost:8000/auth/linkedin/callback")
    linkedin_person_urn: str = Field(default="")

    # ─── Scheduler ───────────────────────────────────────────
    scheduler_hour: int = Field(default=9)
    scheduler_minute: int = Field(default=0)
    scheduler_timezone: str = Field(default="Asia/Karachi")

    # ─── Email / SMTP (optional daily report) ────────────────
    smtp_host: str = Field(default="smtp.gmail.com")
    report_recipient: str = Field(default="")

    # ─── Content ─────────────────────────────────────────────
    default_topics: str = Field(
        default="Artificial Intelligence,Data Analytics,Python,Machine Learning,Power BI,"
        "Cloud Computing,Career Advice,Productivity,Tech News,Software Engineering"
    )
    post_language: str = Field(default="English")
    max_hashtags: int = Field(default=10)
    post_min_length: int = Field(default=500)
    post_max_length: int = Field(default=2500)

    # ─── Memory ──────────────────────────────────────────────
    memory_file_path: str = Field(default="./data/memory.json")
    max_history_days: int = Field(default=365)

    # ─── Logging ─────────────────────────────────────────────
    log_level: str = Field(default="INFO")
    log_file_path: str = Field(default="./logs/agent.log")
    log_rotation: str = Field(default="10 MB")
    log_retention: str = Field(default="30 days")

    # ─── Rate Limiting ────────────────────────────────────────
    rate_limit_requests: int = Field(default=100)
    rate_limit_window_seconds: int = Field(default=60)

    # ─── CORS ────────────────────────────────────────────────
    cors_origins: str = Field(default="http://localhost:3000,http://localhost:8000")

    # ─── Computed Properties ─────────────────────────────────
    @property
    def topics_list(self) -> List[str]:
        """Return default topics as a list."""
        return [t.strip() for t in self.default_topics.split(",") if t.strip()]

    @property
    def image_providers_list(self) -> List[str]:
        """Return image provider priority as a list."""
        return [p.strip() for p in self.image_provider_priority.split(",") if p.strip()]

    @property
    def cors_origins_list(self) -> List[str]:
        """Return CORS origins as a list."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def effective_groq_key(self) -> str:
        """
        Return the Groq API key.
        Supports both GROQ_API_KEY and OPENAI_API_KEY (Groq uses OpenAI-compatible format).
        If the OPENAI_API_KEY starts with 'gsk_' it is a Groq key.
        """
        if self.groq_api_key:
            return self.groq_api_key
        if self.openai_api_key and self.openai_api_key.startswith("gsk_"):
            return self.openai_api_key
        return ""

    @property
    def effective_groq_model(self) -> str:
        """Return the Groq model name, falling back to openai_model if groq_model matches."""
        # If user set openai_model to a Groq model name, use that
        if self.openai_model and self.openai_model != "gpt-4o":
            return self.openai_model
        return self.groq_model

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        # Supabase gives postgres:// — SQLAlchemy needs postgresql://
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql://", 1)
        return v

    @field_validator("scheduler_hour")
    @classmethod
    def validate_hour(cls, v: int) -> int:
        if not 0 <= v <= 23:
            raise ValueError("scheduler_hour must be between 0 and 23")
        return v

    @field_validator("scheduler_minute")
    @classmethod
    def validate_minute(cls, v: int) -> int:
        if not 0 <= v <= 59:
            raise ValueError("scheduler_minute must be between 0 and 59")
        return v

    @field_validator("openai_temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        if not 0.0 <= v <= 2.0:
            raise ValueError("openai_temperature must be between 0.0 and 2.0")
        return v


@lru_cache()
def get_settings() -> Settings:
    """
    Return cached Settings instance.
    Use this as a FastAPI dependency: Depends(get_settings)
    """
    return Settings()


# Module-level singleton for use outside FastAPI dependency injection
settings = get_settings()
