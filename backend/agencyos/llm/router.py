"""Model router + client used by agents.

Provider selection order:
  1. organisation preference (Settings page) and org-level encrypted keys
  2. AGENCYOS_LLM_PROVIDER + env keys
  3. 'auto': Anthropic if a key exists, else OpenAI, else the local mock.

Tier -> model mapping keeps cheap models for extraction/classification and strong
models for architecture/review work.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from ..config import settings
from ..db import db, new_id, now
from ..security import decrypt_secret
from .base import LLMCallResult, LLMError, UsageRecord, Validator, extract_json, rough_tokens
from .providers import AnthropicProvider, MockProvider, OpenAIProvider

log = logging.getLogger("agencyos.llm")

TIERS = ("fast", "strong", "code")


def org_secret(org_id: str | None, name: str) -> str | None:
    if not org_id:
        return None
    row = db().q1("SELECT ciphertext FROM org_secrets WHERE org_id = ? AND name = ?", (org_id, name))
    return decrypt_secret(row["ciphertext"]) if row else None


def resolve_provider(org_id: str | None) -> tuple[Any, dict[str, str]]:
    s = settings()
    pref = (org_secret(org_id, "LLM_PROVIDER") or s.llm_provider or "auto").lower()
    akey = org_secret(org_id, "ANTHROPIC_API_KEY") or s.anthropic_api_key
    okey = org_secret(org_id, "OPENAI_API_KEY") or s.openai_api_key
    if pref == "auto":
        pref = "anthropic" if akey else "openai" if okey else "mock"
    if pref == "anthropic" and akey:
        return AnthropicProvider(akey), {"fast": s.anthropic_model_fast, "strong": s.anthropic_model_strong,
                                         "code": s.anthropic_model_strong}
    if pref == "openai" and okey:
        return OpenAIProvider(okey), {"fast": s.openai_model_fast, "strong": s.openai_model_strong,
                                      "code": s.openai_model_strong}
    return MockProvider(), {"fast": "deterministic", "strong": "deterministic", "code": "deterministic"}


def provider_status(org_id: str | None) -> dict:
    p, models = resolve_provider(org_id)
    return {"provider": p.name, "models": models, "is_mock": p.name == "mock"}


class LLMClient:
    def __init__(self, org_id: str | None, project_id: str | None = None, execution_id: str | None = None):
        self.org_id = org_id
        self.project_id = project_id
        self.execution_id = execution_id
        self.provider, self.models = resolve_provider(org_id)
        self.usage: list[UsageRecord] = []

    @property
    def is_mock(self) -> bool:
        return self.provider.name == "mock"

    def _record(self, rec: UsageRecord) -> None:
        self.usage.append(rec)
        db().insert("llm_usage", {
            "id": new_id(), "org_id": self.org_id, "project_id": self.project_id,
            "execution_id": self.execution_id, "provider": rec.provider, "model": rec.model,
            "purpose": rec.purpose, "tokens_in": rec.tokens_in, "tokens_out": rec.tokens_out,
            "cost_usd": rec.cost_usd, "created_at": now(),
        })

    def generate_json(self, *, purpose: str, tier: str, system: str, prompt: str,
                      fallback: Callable[[], Any], validate: Validator | None = None,
                      max_tokens: int = 3000, retries: int = 1) -> LLMCallResult:
        """Ask the model for JSON, validate it, retry with corrections, else fall back.

        The fallback is the agent's deterministic implementation; it is used directly
        when the provider is the local mock.
        """
        notes: list[str] = []
        if not self.is_mock:
            model = self.models.get(tier, self.models["strong"])
            correction = ""
            for attempt in range(retries + 1):
                try:
                    resp = self.provider.complete(system=system, prompt=prompt + correction,
                                                  model=model, max_tokens=max_tokens, json_mode=True)
                    self._record(UsageRecord(resp.provider, resp.model, resp.tokens_in, resp.tokens_out,
                                             resp.cost_usd, purpose))
                    value = extract_json(resp.text)
                    errors = validate(value) if validate else []
                    if not errors:
                        return LLMCallResult(value, resp.provider, resp.model, False, list(self.usage), notes)
                    notes.append(f"attempt {attempt + 1}: output failed validation: {errors[:3]}")
                    correction = ("\n\nYour previous answer was invalid: " + "; ".join(errors[:5]) +
                                  ". Return corrected JSON only.")
                except (LLMError, ValueError) as e:
                    notes.append(f"attempt {attempt + 1}: {e}")
                    log.warning("LLM %s failed for %s: %s", self.provider.name, purpose, e)
            notes.append("fell back to deterministic implementation")
        value = fallback()
        tin, tout = rough_tokens(prompt), rough_tokens(str(value))
        self._record(UsageRecord("mock", "deterministic", tin, tout, 0.0, purpose))
        return LLMCallResult(value, "mock", "deterministic", True, list(self.usage), notes)

    def generate_text(self, *, purpose: str, tier: str, system: str, prompt: str,
                      fallback: Callable[[], str], max_tokens: int = 1500) -> LLMCallResult:
        if not self.is_mock:
            model = self.models.get(tier, self.models["strong"])
            try:
                resp = self.provider.complete(system=system, prompt=prompt, model=model, max_tokens=max_tokens)
                self._record(UsageRecord(resp.provider, resp.model, resp.tokens_in, resp.tokens_out,
                                         resp.cost_usd, purpose))
                if resp.text.strip():
                    return LLMCallResult(resp.text.strip(), resp.provider, resp.model, False, list(self.usage))
            except LLMError as e:
                log.warning("LLM text failed for %s: %s", purpose, e)
        value = fallback()
        self._record(UsageRecord("mock", "deterministic", rough_tokens(prompt), rough_tokens(value), 0.0, purpose))
        return LLMCallResult(value, "mock", "deterministic", True, list(self.usage))
