import json
from dataclasses import dataclass
from typing import Any, Literal, Protocol

import httpx

StructuredOutputMode = Literal["json_schema", "json_object", "prompt"]


@dataclass(frozen=True, slots=True)
class LLMResult:
    content: dict[str, Any]
    provider: str
    metadata: dict[str, Any]


class LLMProvider(Protocol):
    async def generate(
        self, template: dict[str, Any], evidence: list[dict[str, Any]]
    ) -> LLMResult: ...


class LLMProviderError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class MockLLMProvider:
    """Deterministic transformer that only copies supplied evidence."""

    async def generate(
        self, template: dict[str, Any], evidence: list[dict[str, Any]]
    ) -> LLMResult:
        content: dict[str, list[str]] = {
            "completed": [],
            "in_progress": [],
            "blockers": [],
            "next_week": [],
            "support_required": [],
        }
        for item in evidence:
            if "content" in item:
                source = item["content"]
                for key in content:
                    values = source.get(key, []) if isinstance(source, dict) else []
                    content[key].extend(str(value) for value in values)
                continue
            work_item = str(item.get("workItemId", "unknown"))
            summary = str(item.get("workSummary", ""))
            entry = f"{work_item}: {summary}"
            status = item.get("status")
            if status == "DONE":
                content["completed"].append(entry)
            elif status == "BLOCKED":
                blocker = str(item.get("effectiveBlocker") or summary)
                content["blockers"].append(f"{work_item}: {blocker}")
                content["support_required"].append(f"{work_item}: {blocker}")
            else:
                content["in_progress"].append(entry)
            next_action = item.get("nextAction")
            if next_action:
                content["next_week"].append(f"{work_item}: {next_action}")
        for key, values in content.items():
            content[key] = list(dict.fromkeys(values))
        return LLMResult(
            content=content,
            provider="mock",
            metadata={"mode": "mock", "evidenceCount": len(evidence)},
        )


class OpenAICompatibleLLMProvider:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        output_mode: StructuredOutputMode,
        timeout_seconds: float,
        max_attempts: int,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not base_url.strip() or not api_key or not model.strip():
            raise ValueError("Base URL, API key, and model are required")
        if timeout_seconds <= 0:
            raise ValueError("LLM timeout must be greater than zero")
        if max_attempts < 1:
            raise ValueError("LLM max attempts must be at least one")
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self.model = model
        self.output_mode = output_mode
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts
        self._transport = transport

    def __repr__(self) -> str:
        return (
            "OpenAICompatibleLLMProvider("
            f"base_url={self.base_url!r}, model={self.model!r}, "
            f"output_mode={self.output_mode!r})"
        )

    async def generate(
        self, template: dict[str, Any], evidence: list[dict[str, Any]]
    ) -> LLMResult:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Generate a weekly project report using only supplied evidence. "
                        "Never invent project facts. Preserve evidence identifiers and "
                        "return only a JSON object matching this JSON Schema: "
                        f"{json.dumps(template, ensure_ascii=False, separators=(',', ':'))}"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {"evidence": evidence},
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                },
            ],
        }
        if self.output_mode == "json_schema":
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "weekly_report",
                    "strict": True,
                    "schema": template,
                },
            }
        elif self.output_mode == "json_object":
            payload["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            transport=self._transport,
        ) as client:
            for attempt in range(1, self.max_attempts + 1):
                try:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self._api_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
                except (httpx.TimeoutException, httpx.TransportError) as error:
                    if attempt < self.max_attempts:
                        continue
                    raise LLMProviderError(
                        "LLM_UNAVAILABLE", "The LLM endpoint is unavailable"
                    ) from error
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt < self.max_attempts:
                        continue
                    raise LLMProviderError(
                        "LLM_UNAVAILABLE", "The LLM endpoint is unavailable"
                    )
                if response.status_code >= 400:
                    raise LLMProviderError(
                        "LLM_REQUEST_REJECTED", "The LLM endpoint rejected the request"
                    )
                return self._parse_response(response, attempt)
        raise LLMProviderError("LLM_UNAVAILABLE", "The LLM endpoint is unavailable")

    def _parse_response(self, response: httpx.Response, attempt: int) -> LLMResult:
        try:
            body = response.json()
            content_value = body["choices"][0]["message"]["content"]
            content = (
                json.loads(content_value)
                if isinstance(content_value, str)
                else content_value
            )
            if not isinstance(content, dict):
                raise TypeError("LLM content must be a JSON object")
        except (ValueError, TypeError, KeyError, IndexError) as error:
            raise LLMProviderError(
                "LLM_RESPONSE_INVALID", "The LLM returned an invalid response"
            ) from error
        metadata: dict[str, Any] = {
            "model": self.model,
            "attempt": attempt,
            "outputMode": self.output_mode,
        }
        if isinstance(body.get("id"), str):
            metadata["responseId"] = body["id"]
        if isinstance(body.get("usage"), dict):
            metadata["usage"] = body["usage"]
        return LLMResult(
            content=content,
            provider="openai_compatible",
            metadata=metadata,
        )
