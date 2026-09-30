from app.ai.providers.base import AIProvider, AIResponse
from app.ai.providers.openai_provider import OpenAIProvider
from app.core import runtime_config

# Model tiers a task can route to; anything else falls back to "primary".
_TASK_TO_TIER = {
    "classification": "fast",
    "ocr_cleanup": "fast",
    "extraction": "primary",
    "reasoning": "reasoning",
    "anomaly_explanation": "reasoning",
    "summarization": "primary",
    "chat": "primary",
}
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"


class AIProviderNotConfigured(RuntimeError):
    """Raised when a real AI call is attempted but no API key is set."""


def get_provider() -> AIProvider:
    """
    Built fresh on every call (cheap — just wraps a client) rather than
    cached, so a model change from the Settings page takes effect on the
    very next request.
    """
    cfg = runtime_config.get_config()
    api_key = runtime_config.get_api_key()
    if not api_key:
        provider_name = "NVIDIA" if cfg.ai_provider == "nvidia" else "OpenAI"
        raise AIProviderNotConfigured(
            f"No {provider_name} API key is configured. Add one in Settings before using AI features."
        )
    return OpenAIProvider(
        default_model=cfg.default_model,
        fast_model=cfg.fast_model,
        reasoning_model=cfg.reasoning_model,
        api_key=api_key,
        base_url=NVIDIA_BASE_URL if cfg.ai_provider == "nvidia" else None,
    )


async def run_task(task: str, system_prompt: str, user_prompt: str, json_mode: bool = True) -> AIResponse:
    """
    Single entry point business logic should call. `task` must be one of the
    keys in _TASK_TO_TIER (classification, extraction, reasoning,
    anomaly_explanation, summarization, chat, ocr_cleanup).
    """
    tier = _TASK_TO_TIER.get(task, "primary")
    provider = get_provider()
    return await provider.complete(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model_tier=tier,
        json_mode=json_mode,
    )
