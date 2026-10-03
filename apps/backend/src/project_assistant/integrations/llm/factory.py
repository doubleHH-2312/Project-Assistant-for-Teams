from project_assistant.core.config import Settings
from project_assistant.integrations.llm.provider import (
    LLMProvider,
    MockLLMProvider,
    OpenAICompatibleLLMProvider,
)


def build_llm_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "mock":
        return MockLLMProvider()
    assert settings.llm_api_key is not None
    assert settings.llm_model is not None
    return OpenAICompatibleLLMProvider(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key.get_secret_value(),
        model=settings.llm_model,
        output_mode=settings.llm_structured_output_mode,
        timeout_seconds=settings.llm_timeout_seconds,
        max_attempts=settings.llm_max_attempts,
    )
