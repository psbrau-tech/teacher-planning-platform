from dataclasses import dataclass

from .settings import Settings


@dataclass(frozen=True, slots=True)
class RuntimeReadiness:
    environment: str
    public_base_url: str
    data_boundary: str
    supabase_configured: bool
    database_configured: bool
    google_sso_configured: bool
    openai_configured: bool
    pilot_access_configured: bool

    @property
    def core_ready(self) -> bool:
        return all(
            (
                self.supabase_configured,
                self.database_configured,
                self.google_sso_configured,
                self.pilot_access_configured,
            )
        )


def evaluate_runtime_readiness(settings: Settings) -> RuntimeReadiness:
    """Report configuration presence without exposing secret values."""
    return RuntimeReadiness(
        environment=settings.environment,
        public_base_url=str(settings.public_base_url),
        data_boundary=settings.data_boundary,
        supabase_configured=all(
            (
                settings.supabase_url,
                settings.supabase_anon_key,
                settings.supabase_service_role_key,
            )
        ),
        database_configured=bool(settings.database_url),
        google_sso_configured=all(
            (
                settings.google_oauth_client_id,
                settings.google_oauth_client_secret,
            )
        ),
        openai_configured=bool(settings.openai_api_key),
        pilot_access_configured=bool(settings.email_domains or settings.pilot_emails),
    )
