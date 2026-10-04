"""Concrete providers: Anthropic, OpenAI and a deterministic local Mock.

HTTP calls use `requests` directly so there is no hard dependency on vendor SDKs.
Keys are only ever read server-side.
"""
from __future__ import annotations

import requests

from .base import LLMError, LLMResponse, estimate_cost, rough_tokens


class AnthropicProvider:
    name = "anthropic"
    url = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key: str, timeout: float = 120):
        self.api_key = api_key
        self.timeout = timeout

    def complete(self, *, system, prompt, model, max_tokens=2000, json_mode=False) -> LLMResponse:
        if json_mode:
            system = system + "\n\nRespond with a single valid JSON value only. No prose, no code fences."
        try:
            r = requests.post(
                self.url,
                headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01",
                         "content-type": "application/json"},
                json={"model": model, "max_tokens": max_tokens, "system": system,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            raise LLMError(f"Anthropic request failed: {e.__class__.__name__}") from e
        if r.status_code != 200:
            raise LLMError(f"Anthropic HTTP {r.status_code}: {r.text[:300]}")
        data = r.json()
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        u = data.get("usage", {})
        tin, tout = int(u.get("input_tokens", 0)), int(u.get("output_tokens", 0))
        return LLMResponse(text, self.name, model, tin, tout, estimate_cost(model, tin, tout))


class OpenAIProvider:
    name = "openai"
    url = "https://api.openai.com/v1/chat/completions"

    def __init__(self, api_key: str, timeout: float = 120):
        self.api_key = api_key
        self.timeout = timeout

    def complete(self, *, system, prompt, model, max_tokens=2000, json_mode=False) -> LLMResponse:
        body = {"model": model, "max_tokens": max_tokens,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
            body["messages"][0]["content"] += "\n\nRespond with a single JSON object only."
        try:
            r = requests.post(self.url, headers={"Authorization": f"Bearer {self.api_key}"},
                              json=body, timeout=self.timeout)
        except requests.RequestException as e:
            raise LLMError(f"OpenAI request failed: {e.__class__.__name__}") from e
        if r.status_code != 200:
            raise LLMError(f"OpenAI HTTP {r.status_code}: {r.text[:300]}")
        data = r.json()
        text = data["choices"][0]["message"].get("content") or ""
        u = data.get("usage", {})
        tin, tout = int(u.get("prompt_tokens", 0)), int(u.get("completion_tokens", 0))
        return LLMResponse(text, self.name, model, tin, tout, estimate_cost(model, tin, tout))


class MockProvider:
    """Deterministic local provider.

    It does not pretend to be a language model: `complete` raises, which makes every
    agent use its deterministic, rule-based implementation instead. Executions are
    recorded with provider="mock" so the UI can show that no LLM was involved.
    """

    name = "mock"

    def complete(self, *, system, prompt, model, max_tokens=2000, json_mode=False) -> LLMResponse:
        raise LLMError("mock provider: use deterministic fallback")

    @staticmethod
    def usage_for(prompt: str, output: str) -> tuple[int, int]:
        return rough_tokens(prompt), rough_tokens(output)
