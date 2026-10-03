import json

import httpx
import pytest

from project_assistant.integrations.llm.provider import (
    LLMProviderError,
    OpenAICompatibleLLMProvider,
)

SCHEMA = {
    "type": "object",
    "required": ["completed"],
    "properties": {"completed": {"type": "array", "items": {"type": "string"}}},
    "additionalProperties": False,
}
EVIDENCE = [
    {"id": "daily-1", "workSummary": "Implemented API", "status": "DONE"},
    {"id": "daily-2", "workSummary": "Reviewed UI", "status": "DONE"},
]


def success_response(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        request=request,
        json={
            "id": "chatcmpl-test",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(
                            {"completed": ["Implemented API", "Reviewed UI"]}
                        ),
                    }
                }
            ],
            "usage": {"prompt_tokens": 42, "completion_tokens": 12},
        },
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "expected_response_type"),
    [
        ("json_schema", "json_schema"),
        ("json_object", "json_object"),
        ("prompt", None),
    ],
)
async def test_openai_compatible_request_contract_and_output_modes(
    mode: str, expected_response_type: str | None
) -> None:
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return success_response(request)

    provider = OpenAICompatibleLLMProvider(
        base_url="https://llm.company.example/openai/v1/",
        api_key="test-secret-key",
        model="company-report-model",
        output_mode=mode,  # type: ignore[arg-type]
        timeout_seconds=3,
        max_attempts=2,
        transport=httpx.MockTransport(handle),
    )

    result = await provider.generate(SCHEMA, EVIDENCE)

    assert len(requests) == 1
    request = requests[0]
    payload = json.loads(request.content)
    assert str(request.url) == "https://llm.company.example/openai/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer test-secret-key"
    assert payload["model"] == "company-report-model"
    assert "only supplied evidence" in payload["messages"][0]["content"]
    assert json.loads(payload["messages"][1]["content"])["evidence"] == EVIDENCE
    if expected_response_type is None:
        assert "response_format" not in payload
    else:
        assert payload["response_format"]["type"] == expected_response_type
    if mode == "json_schema":
        assert payload["response_format"]["json_schema"]["schema"] == SCHEMA
    assert result.content == {"completed": ["Implemented API", "Reviewed UI"]}
    assert result.provider == "openai_compatible"
    assert result.metadata == {
        "model": "company-report-model",
        "attempt": 1,
        "outputMode": mode,
        "responseId": "chatcmpl-test",
        "usage": {"prompt_tokens": 42, "completion_tokens": 12},
    }
    assert "test-secret-key" not in str(result.metadata)


@pytest.mark.asyncio
@pytest.mark.parametrize("first_status", [429, 500, 503])
async def test_retries_retryable_http_statuses(first_status: int) -> None:
    attempts = 0

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(first_status, request=request, json={"error": "retry"})
        return success_response(request)

    provider = OpenAICompatibleLLMProvider(
        "https://api.openai.com/v1",
        "test-key",
        "gpt-test",
        "json_schema",
        3,
        2,
        transport=httpx.MockTransport(handle),
    )

    result = await provider.generate(SCHEMA, EVIDENCE)

    assert attempts == 2
    assert result.metadata["attempt"] == 2


@pytest.mark.asyncio
async def test_retries_transport_timeout_only_up_to_max_attempts() -> None:
    attempts = 0

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ReadTimeout("timed out", request=request)

    provider = OpenAICompatibleLLMProvider(
        "https://api.openai.com/v1",
        "test-key",
        "gpt-test",
        "json_object",
        1,
        3,
        transport=httpx.MockTransport(handle),
    )

    with pytest.raises(LLMProviderError) as failure:
        await provider.generate(SCHEMA, EVIDENCE)

    assert attempts == 3
    assert failure.value.code == "LLM_UNAVAILABLE"


@pytest.mark.asyncio
async def test_does_not_retry_non_retryable_4xx() -> None:
    attempts = 0

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(400, request=request, json={"error": "bad request"})

    provider = OpenAICompatibleLLMProvider(
        "https://api.openai.com/v1",
        "test-key",
        "gpt-test",
        "prompt",
        3,
        3,
        transport=httpx.MockTransport(handle),
    )

    with pytest.raises(LLMProviderError) as failure:
        await provider.generate(SCHEMA, EVIDENCE)

    assert attempts == 1
    assert failure.value.code == "LLM_REQUEST_REJECTED"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        {"choices": []},
        {"choices": [{"message": {"content": "not-json"}}]},
        {"choices": [{"message": {"content": "[]"}}]},
    ],
)
async def test_rejects_malformed_response_content(body: dict[str, object]) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, json=body)

    provider = OpenAICompatibleLLMProvider(
        "https://api.openai.com/v1",
        "test-key",
        "gpt-test",
        "json_schema",
        3,
        1,
        transport=httpx.MockTransport(handle),
    )

    with pytest.raises(LLMProviderError) as failure:
        await provider.generate(SCHEMA, EVIDENCE)

    assert failure.value.code == "LLM_RESPONSE_INVALID"
