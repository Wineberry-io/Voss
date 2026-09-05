from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional
from ._config import get_config
from .budget import current_budget
from .probable import ProbableValue
from .providers import get as get_provider
from .providers.base import ModelProvider

Compressor = Callable[[str, int, ModelProvider], Awaitable[str]]


async def _summarize_compress(text: str, target_tokens: int, provider: ModelProvider) -> str:
    """Default compression: ask the model to summarize down to target token count."""
    prompt = f"Summarize the following content to fit within {target_tokens} tokens, preserving key facts:\n\n{text}"
    cfg = get_config()
    resp = await provider.complete(
        messages=[{"role": "user", "content": prompt}],
        model=cfg.default_model,
        max_tokens=cfg.max_output_tokens,
    )
    return resp.text


@dataclass
class _Slot:
    content: str
    tokens: int
    compression: str = "summarize"


@dataclass
class ContextScope:
    token_budget: int
    model: Optional[str] = None
    provider: Optional[ModelProvider] = None
    compressor: Compressor = field(default=_summarize_compress)
    slots: list[_Slot] = field(default_factory=list)
    tokens_used: int = 0
    async_mode: bool = True

    @property
    def _model(self) -> str:
        return self.model or get_config().default_model

    @property
    def _provider(self) -> ModelProvider:
        return self.provider or get_provider(self._model)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def add(self, content: Any, *, compression: str = "summarize") -> str:
        text = content if isinstance(content, str) else str(content)
        tokens = self._provider.count_tokens(text=text, model=self._model)
        slot = _Slot(content=text, tokens=tokens, compression=compression)
        self.slots.append(slot)
        self.tokens_used += tokens
        await self._maybe_compress()
        return slot.content

    async def _maybe_compress(self) -> None:
        if self.tokens_used <= self.token_budget:
            return
        for slot in self.slots:
            if self.tokens_used <= self.token_budget:
                break
            if slot.compression != "summarize":
                continue
            target = max(slot.tokens // 2, 64)
            compressed = await self.compressor(slot.content, target, self._provider)
            new_tokens = self._provider.count_tokens(text=compressed, model=self._model)
            self.tokens_used += new_tokens - slot.tokens
            slot.content, slot.tokens = compressed, new_tokens

    def assemble(self) -> list[dict]:
        return [{"role": "user", "content": slot.content} for slot in self.slots]

    async def ask(self, prompt: str, *, return_type: Optional[type] = None) -> Any:
        messages = self.assemble() + [{"role": "user", "content": prompt}]
        response_format = None
        wants_probable = return_type is ProbableValue
        if return_type and not wants_probable and hasattr(return_type, "model_validate"):
            response_format = return_type
        resp = await self._provider.complete(
            messages=messages,
            model=self._model,
            response_format=response_format,
            max_tokens=get_config().max_output_tokens,
        )
        self.tokens_used += resp.completion_tokens
        bs = current_budget()
        if bs is not None:
            bs.add_usage(tokens=resp.total_tokens, cost=resp.cost_usd)
        if wants_probable:
            conf = 0.9 if resp.text.strip() else 0.0
            return ProbableValue(value=resp.text, confidence=conf)
        if response_format is not None:
            return resp.parsed
        return resp.text
