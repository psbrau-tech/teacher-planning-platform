from dataclasses import dataclass

from .settings import Settings


@dataclass(frozen=True, slots=True)
class RuntimeReadiness:
    environment: str
    public_base_url: str
    data_boundary: str
    supabase_configured: bool
    pilot_access_configured: bool
    privileged_runtime_credentials_absent: bool

    @property
    def core_ready(self) -> bool:
        return all(
            (
                self.supabase_configured,
                self.pilot_access_configured,
                self.privileged_runtime_credentials_absent,
            )
        )


def evaluate_runtime_readiness(settings: Settings) -> RuntimeReadiness:
    """Report required runtime configuration without exposing secret values.

    Database migration, staff provisioning, Google provider configuration, and
    future AI features are administered outside the running ECS task. Their
    credentials must not be injected until reviewed runtime code requires them.
    """
    return RuntimeReadiness(
        environment=settings.environment,
        public_base_url=str(settings.public_base_url),
        data_boundary=settings.data_boundary,
        supabase_configured=all(
            (
                settings.supabase_url,
                settings.supabase_anon_key,
            )
        ),
        pilot_access_configured=bool(settings.email_domains or settings.pilot_emails),
        privileged_runtime_credentials_absent=not any(
            (
                settings.supabase_service_role_key,
                settings.database_url,
                settings.openai_api_key,
                settings.google_oauth_client_id,
                settings.google_oauth_client_secret,
            )
        ),
    )
