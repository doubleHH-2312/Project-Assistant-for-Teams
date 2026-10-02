from dataclasses import dataclass
from typing import Any, Protocol

import httpx


@dataclass(frozen=True, slots=True)
class LLMResult:
    content: dict[str, Any]
    provider: str
    metadata: dict[str, Any]


class LLMProvider(Protocol):
    async def generate(
        self, template: dict[str, Any], evidence: list[dict[str, Any]]
    ) -> LLMResult: ...


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


class InternalLLMProvider:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float = 20,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    async def generate(
        self, template: dict[str, Any], evidence: list[dict[str, Any]]
    ) -> LLMResult:
        payload = {
            "model": self.model,
            "system": (
                "Generate a weekly project report using only supplied evidence. "
                "Preserve identifiers and return JSON matching the supplied schema."
            ),
            "template": template,
            "evidence": evidence,
        }
        last_error: httpx.HTTPError | None = None
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            for attempt in range(2):
                try:
                    response = await client.post(
                        f"{self.base_url}/generate",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        json=payload,
                    )
                    response.raise_for_status()
                    body = response.json()
                    return LLMResult(
                        content=body["content"],
                        provider="internal",
                        metadata={"model": self.model, "attempt": attempt + 1},
                    )
                except (httpx.TimeoutException, httpx.TransportError) as error:
                    last_error = error
        assert last_error is not None
        raise last_error

