"""
Provider-agnostic interface every AI backend must implement.

Business logic (extraction, anomaly detection, chat, ...) should only ever
talk to `AIProvider`, never to a concrete SDK. That's what lets a new
provider (Anthropic, Google, a local model, ...) be dropped in later
without touching anything upstream.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class AIResponse:
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    raw: Optional[Any] = None


class AIProvider(ABC):
    @abstractmethod
    async def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model_tier: str,
        json_mode: bool = False,
        temperature: float = 0.2,
        max_tokens: int = 1950,
    ) -> AIResponse:
        """Run a single completion. `model_tier` is one of: fast | primary | reasoning."""
        raise NotImplementedError
