from __future__ import annotations

import json
import time
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from hashlib import sha256
from typing import Any, cast

import httpx

from .settings import Settings

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
MAX_CONTEXT_CHARACTERS = 80_000
MAX_OUTPUT_TOKENS = 4_000
MAX_ATTEMPTS = 2
JsonObject = dict[str, Any]


class AiServiceError(RuntimeError):
    """Bounded AI-service failure safe to surface to a teacher."""


@dataclass(frozen=True, slots=True)
class AiUsage:
    model: str
    provider_response_id: str | None
    input_tokens: int
    cached_tokens: int
    cache_write_tokens: int
    output_tokens: int
    estimated_cost_usd: Decimal
    retry_count: int


@dataclass(frozen=True, slots=True)
class StructuredAiResult:
    data: JsonObject
    usage: AiUsage


def safety_identifier(subject: str) -> str:
    normalized = subject.strip()
    if not normalized:
        raise AiServiceError("AI request identity is unavailable")
    return f"tpp_{sha256(f'tpp-pilot:{normalized}'.encode()).hexdigest()[:32]}"


def estimate_cost_usd(
    *,
    input_tokens: int,
    cached_tokens: int,
    cache_write_tokens: int,
    output_tokens: int,
    settings: Settings,
) -> Decimal:
    for value in (input_tokens, cached_tokens, cache_write_tokens, output_tokens):
        if value < 0:
            raise AiServiceError("AI usage data is invalid")

    uncached_tokens = max(input_tokens - cached_tokens - cache_write_tokens, 0)
    total = (
        Decimal(uncached_tokens) * settings.openai_input_cost_per_million
        + Decimal(cached_tokens) * settings.openai_cached_input_cost_per_million
        + Decimal(cache_write_tokens) * settings.openai_cache_write_cost_per_million
        + Decimal(output_tokens) * settings.openai_output_cost_per_million
    ) / Decimal(1_000_000)
    return total.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def request_structured_response(
    *,
    settings: Settings,
    teacher_subject: str,
    instructions: str,
    context: JsonObject,
    schema_name: str,
    schema: JsonObject,
) -> StructuredAiResult:
    if not settings.openai_api_key:
        raise AiServiceError("AI planning assistance is not configured")

    serialized_context = json.dumps(
        context,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    if len(serialized_context) > MAX_CONTEXT_CHARACTERS:
        raise AiServiceError("AI planning context is too large")

    payload: JsonObject = {
        "model": settings.openai_model,
        "store": False,
        "reasoning": {
            "effort": settings.openai_reasoning_effort,
            "context": "current_turn",
        },
        "safety_identifier": safety_identifier(teacher_subject),
        "instructions": instructions,
        "input": serialized_context,
        "text": {
            "verbosity": "low",
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "strict": True,
                "schema": schema,
            },
        },
        "max_output_tokens": MAX_OUTPUT_TOKENS,
    }

    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    response_payload: JsonObject | None = None
    attempts = 0
    for attempt in range(MAX_ATTEMPTS):
        attempts = attempt + 1
        try:
            with httpx.Client(timeout=settings.openai_timeout_seconds) as client:
                response = client.post(OPENAI_RESPONSES_URL, headers=headers, json=payload)
        except httpx.HTTPError as error:
            if attempts < MAX_ATTEMPTS:
                time.sleep(0.25)
                continue
            raise AiServiceError("AI planning assistance is temporarily unavailable") from error

        if response.status_code in {408, 409, 429} or response.status_code >= 500:
            if attempts < MAX_ATTEMPTS:
                time.sleep(0.25)
                continue
            raise AiServiceError("AI planning assistance is temporarily unavailable")
        if response.status_code >= 400:
            raise AiServiceError("AI planning assistance request was rejected")

        try:
            raw = response.json()
        except ValueError as error:
            raise AiServiceError("AI planning assistance returned invalid data") from error
        if not isinstance(raw, dict):
            raise AiServiceError("AI planning assistance returned invalid data")
        response_payload = cast(JsonObject, raw)
        break

    if response_payload is None:
        raise AiServiceError("AI planning assistance is temporarily unavailable")

    data = _parse_structured_output(response_payload)
    usage = _parse_usage(response_payload, settings=settings, retry_count=attempts - 1)
    return StructuredAiResult(data=data, usage=usage)


def _parse_structured_output(payload: JsonObject) -> JsonObject:
    status = payload.get("status")
    if status not in {None, "completed"}:
        raise AiServiceError("AI planning assistance did not complete")

    output = payload.get("output")
    if not isinstance(output, list):
        raise AiServiceError("AI planning assistance returned no structured output")

    refusal_seen = False
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            part_type = part.get("type")
            if part_type == "refusal":
                refusal_seen = True
                continue
            if part_type != "output_text":
                continue
            text = part.get("text")
            if not isinstance(text, str) or not text.strip():
                continue
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError as error:
                raise AiServiceError(
                    "AI planning assistance returned invalid structured data"
                ) from error
            if not isinstance(parsed, dict):
                raise AiServiceError("AI planning assistance returned invalid structured data")
            return cast(JsonObject, parsed)

    if refusal_seen:
        raise AiServiceError("AI planning assistance could not provide a suggestion")
    raise AiServiceError("AI planning assistance returned no structured output")


def _usage_integer(record: JsonObject, key: str) -> int:
    value = record.get(key, 0)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise AiServiceError("AI usage data is invalid")
    return cast(int, value)


def _parse_usage(
    payload: JsonObject,
    *,
    settings: Settings,
    retry_count: int,
) -> AiUsage:
    raw_usage = payload.get("usage")
    if not isinstance(raw_usage, dict):
        raise AiServiceError("AI usage data is unavailable")
    usage = cast(JsonObject, raw_usage)

    input_tokens = _usage_integer(usage, "input_tokens")
    output_tokens = _usage_integer(usage, "output_tokens")
    raw_details = usage.get("input_tokens_details")
    details = cast(JsonObject, raw_details) if isinstance(raw_details, dict) else {}
    cached_tokens = _usage_integer(details, "cached_tokens")
    cache_write_tokens = _usage_integer(details, "cache_write_tokens")

    raw_id = payload.get("id")
    response_id = raw_id if isinstance(raw_id, str) and raw_id.strip() else None
    raw_model = payload.get("model")
    model = raw_model if isinstance(raw_model, str) and raw_model.strip() else settings.openai_model

    return AiUsage(
        model=model,
        provider_response_id=response_id,
        input_tokens=input_tokens,
        cached_tokens=cached_tokens,
        cache_write_tokens=cache_write_tokens,
        output_tokens=output_tokens,
        estimated_cost_usd=estimate_cost_usd(
            input_tokens=input_tokens,
            cached_tokens=cached_tokens,
            cache_write_tokens=cache_write_tokens,
            output_tokens=output_tokens,
            settings=settings,
        ),
        retry_count=retry_count,
    )
