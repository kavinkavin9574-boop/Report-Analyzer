from app.ai.providers.base import AIProvider, AIResponse
from app.ai.providers.openai_provider import OpenAIProvider
from app.core import runtime_config
from openai import APIConnectionError

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
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class AIProviderNotConfigured(RuntimeError):
    """Raised when a real AI call is attempted but no API key is set."""


class AIProviderConnectionError(RuntimeError):
    """Raised when the configured AI provider cannot be reached."""


def get_provider() -> AIProvider:
    """
    Built fresh on every call (cheap — just wraps a client) rather than
    cached, so a model change from the Settings page takes effect on the
    very next request.
    """
    cfg = runtime_config.get_config()
    api_key = runtime_config.get_api_key()
    if not api_key:
        provider_name = {
            "nvidia": "NVIDIA",
            "openrouter": "OpenRouter",
        }.get(cfg.ai_provider, "OpenAI")
        raise AIProviderNotConfigured(
            f"No {provider_name} API key is configured. Add one in Settings before using AI features."
        )
    return OpenAIProvider(
        default_model=cfg.default_model,
        fast_model=cfg.fast_model,
        reasoning_model=cfg.reasoning_model,
        api_key=api_key,
        base_url={
            "nvidia": NVIDIA_BASE_URL,
            "openrouter": OPENROUTER_BASE_URL,
        }.get(cfg.ai_provider),
    )


async def run_task(task: str, system_prompt: str, user_prompt: str, json_mode: bool = True) -> AIResponse:
    """
    Single entry point business logic should call. `task` must be one of the
    keys in _TASK_TO_TIER (classification, extraction, reasoning,
    anomaly_explanation, summarization, chat, ocr_cleanup).
    """
    tier = _TASK_TO_TIER.get(task, "primary")
    provider = get_provider()
    provider_name = runtime_config.get_config().ai_provider
    provider_label = {
        "openai": "OpenAI",
        "nvidia": "NVIDIA",
        "openrouter": "OpenRouter",
    }.get(provider_name, provider_name)
    provider_host = {
        "openai": "api.openai.com",
        "nvidia": "integrate.api.nvidia.com",
        "openrouter": "openrouter.ai",
    }.get(provider_name, "configured provider endpoint")

    try:
        return await provider.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model_tier=tier,
            json_mode=json_mode,
        )
    except APIConnectionError as exc:
        cause = exc.__cause__ or exc.__context__
        cause_detail = (
            f"Underlying error: {type(cause).__name__}: {cause}"
            if cause
            else "No lower-level network cause was provided."
        )
        raise AIProviderConnectionError(
            f"Could not connect to {provider_label} ({provider_host}) during task "
            f"'{task}'. Check backend outbound HTTPS access, proxy/firewall "
            f"settings, and provider availability. {cause_detail}"
        ) from exc
