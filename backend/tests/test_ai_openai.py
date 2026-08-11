from decimal import Decimal

import pytest

import app.ai_openai as ai_openai
from app.ai_openai import AiServiceError, estimate_cost_usd, request_structured_response
from app.settings import Settings


class FakeResponse:
    def __init__(self, status_code: int, payload: object) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> object:
        return self._payload


class FakeHttpClient:
    def __init__(self, responses: list[FakeResponse], captured: list[dict[str, object]]) -> None:
        self.responses = responses
        self.captured = captured

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def post(self, url, *, headers, json):
        self.captured.append({"url": url, "headers": headers, "json": json})
        return self.responses.pop(0)


def _settings() -> Settings:
    return Settings(
        openai_api_key="synthetic-key",
        openai_model="gpt-5.6-terra",
        openai_input_cost_per_million=Decimal("2.00"),
        openai_cached_input_cost_per_million=Decimal("0.20"),
        openai_cache_write_cost_per_million=Decimal("2.50"),
        openai_output_cost_per_million=Decimal("12.00"),
    )


def _success_payload() -> dict[str, object]:
    return {
        "id": "resp_synthetic_123",
        "model": "gpt-5.6-terra",
        "status": "completed",
        "output": [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": '{"learning_targets":"Explain leadership styles."}',
                    }
                ],
            }
        ],
        "usage": {
            "input_tokens": 1000,
            "output_tokens": 50,
            "input_tokens_details": {
                "cached_tokens": 200,
                "cache_write_tokens": 100,
            },
        },
    }


def test_cost_estimate_accounts_for_cached_and_cache_write_tokens() -> None:
    cost = estimate_cost_usd(
        input_tokens=1000,
        cached_tokens=200,
        cache_write_tokens=100,
        output_tokens=50,
        settings=_settings(),
    )

    assert cost == Decimal("0.002290")


def test_structured_request_uses_privacy_and_governance_controls(monkeypatch) -> None:
    captured: list[dict[str, object]] = []
    responses = [FakeResponse(200, _success_payload())]
    monkeypatch.setattr(
        ai_openai.httpx,
        "Client",
        lambda **kwargs: FakeHttpClient(responses, captured),
    )

    result = request_structured_response(
        settings=_settings(),
        teacher_subject="teacher-uuid-123",
        instructions="Return a teacher-reviewable planning draft.",
        context={
            "standards": [{"code": "U2C1L1", "text": "Leadership styles"}],
            "course_name": "Army JROTC LET 2",
        },
        schema_name="tpp_planning_suggestion",
        schema={
            "type": "object",
            "properties": {"learning_targets": {"type": "string"}},
            "required": ["learning_targets"],
            "additionalProperties": False,
        },
    )

    assert result.data == {"learning_targets": "Explain leadership styles."}
    assert result.usage.provider_response_id == "resp_synthetic_123"
    assert result.usage.estimated_cost_usd == Decimal("0.002290")
    request = captured[0]["json"]
    assert request["model"] == "gpt-5.6-terra"
    assert request["store"] is False
    assert request["reasoning"] == {"effort": "low", "context": "current_turn"}
    assert request["safety_identifier"].startswith("tpp_")
    assert "teacher-uuid-123" not in request["safety_identifier"]
    assert request["text"]["format"]["type"] == "json_schema"
    assert request["text"]["format"]["strict"] is True


def test_transient_rate_limit_retries_once(monkeypatch) -> None:
    captured: list[dict[str, object]] = []
    responses = [FakeResponse(429, {}), FakeResponse(200, _success_payload())]
    monkeypatch.setattr(
        ai_openai.httpx,
        "Client",
        lambda **kwargs: FakeHttpClient(responses, captured),
    )
    monkeypatch.setattr(ai_openai.time, "sleep", lambda seconds: None)

    result = request_structured_response(
        settings=_settings(),
        teacher_subject="teacher-uuid-123",
        instructions="Return structured data.",
        context={"course_name": "Army JROTC LET 2"},
        schema_name="test_schema",
        schema={
            "type": "object",
            "properties": {"learning_targets": {"type": "string"}},
            "required": ["learning_targets"],
            "additionalProperties": False,
        },
    )

    assert len(captured) == 2
    assert result.usage.retry_count == 1


def test_refusal_is_bounded_and_does_not_return_partial_text(monkeypatch) -> None:
    captured: list[dict[str, object]] = []
    responses = [
        FakeResponse(
            200,
            {
                "id": "resp_refusal",
                "model": "gpt-5.6-terra",
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "refusal", "refusal": "Cannot comply"}],
                    }
                ],
                "usage": {"input_tokens": 10, "output_tokens": 2},
            },
        )
    ]
    monkeypatch.setattr(
        ai_openai.httpx,
        "Client",
        lambda **kwargs: FakeHttpClient(responses, captured),
    )

    with pytest.raises(AiServiceError, match="could not provide a suggestion"):
        request_structured_response(
            settings=_settings(),
            teacher_subject="teacher-uuid-123",
            instructions="Return structured data.",
            context={"course_name": "Army JROTC LET 2"},
            schema_name="test_schema",
            schema={
                "type": "object",
                "properties": {"learning_targets": {"type": "string"}},
                "required": ["learning_targets"],
                "additionalProperties": False,
            },
        )


def test_missing_api_key_fails_before_network_call() -> None:
    settings = Settings(openai_api_key=None)

    with pytest.raises(AiServiceError, match="not configured"):
        request_structured_response(
            settings=settings,
            teacher_subject="teacher-uuid-123",
            instructions="Return structured data.",
            context={"course_name": "Army JROTC LET 2"},
            schema_name="test_schema",
            schema={
                "type": "object",
                "properties": {"learning_targets": {"type": "string"}},
                "required": ["learning_targets"],
                "additionalProperties": False,
            },
        )


def test_context_size_is_bounded_before_request() -> None:
    with pytest.raises(AiServiceError, match="context is too large"):
        request_structured_response(
            settings=_settings(),
            teacher_subject="teacher-uuid-123",
            instructions="Return structured data.",
            context={"text": "x" * (ai_openai.MAX_CONTEXT_CHARACTERS + 1)},
            schema_name="test_schema",
            schema={
                "type": "object",
                "properties": {"learning_targets": {"type": "string"}},
                "required": ["learning_targets"],
                "additionalProperties": False,
            },
        )
