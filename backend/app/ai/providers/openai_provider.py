from openai import AsyncOpenAI

from app.ai.providers.base import AIProvider, AIResponse
from app.core.config import get_settings

settings = get_settings()


class OpenAIProvider(AIProvider):
    """
    Wraps the OpenAI SDK. Model *names* are never hard-coded elsewhere in the
    app — only the tier ("fast" / "primary" / "reasoning") is referenced.
    Tier -> model name mapping is passed in at construction time (from the
    runtime AI config, editable from the Settings page) rather than read
    directly from the environment, so a model change takes effect
    immediately without a restart.
    """

    def __init__(self, *, default_model: str | None = None, fast_model: str | None = None,
                 reasoning_model: str | None = None, api_key: str, base_url: str | None = None) -> None:
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        self._client = AsyncOpenAI(**client_kwargs)
        self._tier_to_model = {
            "fast": fast_model or settings.openai_fast_model,
            "primary": default_model or settings.openai_default_model,
            "reasoning": reasoning_model or settings.openai_reasoning_model,
        }

    async def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model_tier: str,
        json_mode: bool = False,
        temperature: float = 0.2,
    ) -> AIResponse:
        model = self._tier_to_model.get(model_tier, settings.openai_default_model)

        kwargs = {}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = await self._client.chat.completions.create(
            model=model,
            temperature=temperature,
            max_tokens=2048,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            **kwargs,
        )

        choice = response.choices[0].message.content or ""
        usage = response.usage

        return AIResponse(
            text=choice,
            model=model,
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
            raw=response,
        )
