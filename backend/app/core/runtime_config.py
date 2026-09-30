"""
Holds the AI provider/model configuration that can be changed at runtime
from the Settings page, without restarting the server. Seeded from
environment defaults on first boot, then persisted in the `system_settings`
table. An API key entered in the Settings page is held in process memory only
and is never persisted or returned by the API.
"""
from dataclasses import dataclass

from app.core.config import get_settings

settings = get_settings()
NVIDIA_DEFAULT_MODEL = "nvidia/nemotron-3.5-lightning-30b-a3b"
RETIRED_NVIDIA_MODELS = {"meta/llama-3.3-70b-instruct"}


@dataclass
class RuntimeAIConfig:
    ai_provider: str
    default_model: str
    fast_model: str
    reasoning_model: str


_config = RuntimeAIConfig(
    ai_provider=settings.ai_provider,
    default_model=settings.openai_default_model,
    fast_model=settings.openai_fast_model,
    reasoning_model=settings.openai_reasoning_model,
)
_api_key_override: str | None = None


def get_config() -> RuntimeAIConfig:
    return _config


def get_api_key() -> str:
    return _api_key_override or ""


def set_api_key(api_key: str | None) -> None:
    global _api_key_override
    _api_key_override = api_key


def migrate_retired_nvidia_models(row) -> bool:
    if row.ai_provider != "nvidia":
        return False

    changed = False
    for field in ("default_model", "fast_model", "reasoning_model"):
        if getattr(row, field) in RETIRED_NVIDIA_MODELS:
            setattr(row, field, NVIDIA_DEFAULT_MODEL)
            changed = True
    return changed


def update_config(*, ai_provider: str | None = None, default_model: str | None = None,
                   fast_model: str | None = None, reasoning_model: str | None = None) -> RuntimeAIConfig:
    global _config
    _config = RuntimeAIConfig(
        ai_provider=ai_provider if ai_provider is not None else _config.ai_provider,
        default_model=default_model if default_model is not None else _config.default_model,
        fast_model=fast_model if fast_model is not None else _config.fast_model,
        reasoning_model=reasoning_model if reasoning_model is not None else _config.reasoning_model,
    )
    return _config


def load_from_row(row) -> None:
    """Called once at startup with the persisted SystemSettings row, if any."""
    global _config
    _config = RuntimeAIConfig(
        ai_provider=row.ai_provider,
        default_model=row.default_model,
        fast_model=row.fast_model,
        reasoning_model=row.reasoning_model,
    )
