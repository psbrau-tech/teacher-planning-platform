from decimal import Decimal
from functools import lru_cache
from typing import Literal

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from the environment or AWS-injected secrets."""

    model_config = SettingsConfigDict(
        env_prefix="TPP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "local"
    public_base_url: HttpUrl = HttpUrl("http://localhost:5173")
    data_boundary: str = "teacher-and-curriculum-only"

    supabase_url: HttpUrl | None = None
    supabase_anon_key: str | None = Field(default=None, repr=False)
    supabase_service_role_key: str | None = Field(default=None, repr=False)
    database_url: str | None = Field(default=None, repr=False)
    openai_api_key: str | None = Field(default=None, repr=False)
    openai_model: str = "gpt-5.6-terra"
    openai_reasoning_effort: Literal["none", "low", "medium", "high", "xhigh", "max"] = "low"
    openai_timeout_seconds: float = Field(default=45.0, gt=0, le=120)
    openai_input_cost_per_million: Decimal = Field(default=Decimal("2.00"), ge=0)
    openai_cached_input_cost_per_million: Decimal = Field(default=Decimal("0.20"), ge=0)
    openai_cache_write_cost_per_million: Decimal = Field(default=Decimal("2.50"), ge=0)
    openai_output_cost_per_million: Decimal = Field(default=Decimal("12.00"), ge=0)
    google_oauth_client_id: str | None = Field(default=None, repr=False)
    google_oauth_client_secret: str | None = Field(default=None, repr=False)

    allowed_email_domains: str = ""
    allowed_pilot_emails: str = ""

    @property
    def email_domains(self) -> frozenset[str]:
        return frozenset(
            value.strip().lower()
            for value in self.allowed_email_domains.split(",")
            if value.strip()
        )

    @property
    def pilot_emails(self) -> frozenset[str]:
        return frozenset(
            value.strip().lower()
            for value in self.allowed_pilot_emails.split(",")
            if value.strip()
        )

    def email_is_allowed(self, email: str) -> bool:
        normalized = email.strip().lower()
        if normalized in self.pilot_emails:
            return True
        if "@" not in normalized:
            return False
        return normalized.rsplit("@", maxsplit=1)[1] in self.email_domains


@lru_cache
def get_settings() -> Settings:
    return Settings()
