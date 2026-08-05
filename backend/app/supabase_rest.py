from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

import httpx

from .settings import Settings


class SupabaseRestError(RuntimeError):
    """Normalized Supabase Data API failure without exposing credentials."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code


@dataclass(frozen=True, slots=True)
class SupabaseRestClient:
    base_url: str
    api_key: str
    access_token: str
    timeout_seconds: float = 10.0

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        access_token: str,
    ) -> SupabaseRestClient:
        if settings.supabase_url is None or not settings.supabase_anon_key:
            raise RuntimeError("Supabase Data API is not configured")
        return cls(
            base_url=str(settings.supabase_url).rstrip("/"),
            api_key=settings.supabase_anon_key,
            access_token=access_token,
        )

    def request(
        self,
        method: str,
        resource: str,
        *,
        params: dict[str, str] | None = None,
        payload: dict[str, object] | list[dict[str, object]] | None = None,
        prefer: str | None = None,
    ) -> object:
        headers = {
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if prefer:
            headers["Prefer"] = prefer

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.request(
                    method,
                    f"{self.base_url}/rest/v1/{resource.lstrip('/')}",
                    params=params,
                    json=payload,
                    headers=headers,
                )
        except httpx.RequestError as error:
            raise SupabaseRestError(
                "Supabase Data API is unavailable",
                status_code=503,
            ) from error

        if response.status_code >= 400:
            message = "Supabase Data API request failed"
            code: str | None = None
            try:
                error_payload = cast(object, response.json())
            except ValueError:
                error_payload = None
            if isinstance(error_payload, dict):
                candidate_message = error_payload.get("message")
                candidate_code = error_payload.get("code")
                if isinstance(candidate_message, str) and candidate_message.strip():
                    message = candidate_message.strip()
                if isinstance(candidate_code, str) and candidate_code.strip():
                    code = candidate_code.strip()
            raise SupabaseRestError(
                message,
                status_code=response.status_code,
                code=code,
            )

        if not response.content:
            return None
        return cast(Any, response.json())
