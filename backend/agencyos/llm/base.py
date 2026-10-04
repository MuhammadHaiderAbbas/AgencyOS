"""LLM provider abstraction.

Agents never talk to a vendor SDK directly. They call `LLMClient.generate_json` /
`generate_text` with a task *tier* ("fast", "strong", "code"); the router picks the
provider and model. Swapping or adding a provider does not touch agent code.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0


class LLMError(Exception):
    pass


class LLMProvider(Protocol):
    name: str

    def complete(self, *, system: str, prompt: str, model: str, max_tokens: int = 2000,
                 json_mode: bool = False) -> LLMResponse: ...


# Indicative prices (USD per 1M tokens) used for *estimates* only. Real billing is the
# provider's invoice; the UI labels these numbers as estimates.
PRICE_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-sonnet-4-5": (3.0, 15.0),
    "claude-opus-4-1": (15.0, 75.0),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.5, 10.0),
}


def estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    pin, pout = PRICE_PER_MTOK.get(model, (3.0, 15.0))
    return round(tokens_in / 1e6 * pin + tokens_out / 1e6 * pout, 6)


def rough_tokens(text: str) -> int:
    return max(1, len(text) // 4)


_JSON_BLOCK = re.compile(r"\{.*\}|\[.*\]", re.S)


def extract_json(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?|```$", "", text).strip()
    try:
        return json.loads(text)
    except ValueError:
        m = _JSON_BLOCK.search(text)
        if not m:
            raise
        return json.loads(m.group(0))


@dataclass
class UsageRecord:
    provider: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    purpose: str


@dataclass
class LLMCallResult:
    value: Any
    provider: str
    model: str
    used_fallback: bool
    usage: list[UsageRecord] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


Validator = Callable[[Any], list[str]]
