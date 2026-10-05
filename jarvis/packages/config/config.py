"""Centralized configuration — env vars with safe defaults."""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# load .env from jarvis root and cwd
for _p in [Path(__file__).resolve().parents[2] / ".env", Path(__file__).resolve().parents[3] / ".env", Path.cwd() / ".env", Path.cwd() / "jarvis" / ".env"]:
    if _p.exists():
        load_dotenv(_p, override=False)


def _bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    env: str
    data_dir: Path
    database_url: str
    redis_url: str | None
    secret_key: str
    frontend_dist: Path
    allow_signup: bool
    token_ttl_minutes: int
    host: str
    port: int
    log_level: str

    # LLM
    llm_provider: str
    anthropic_api_key: str | None
    openai_api_key: str | None
    anthropic_model_fast: str
    anthropic_model_strong: str
    openai_model_fast: str
    openai_model_strong: str
    ollama_url: str

    # features
    tavily_api_key: str | None
    allow_remote_access: bool
    max_tool_calls: int
    max_runtime_s: int
    otel_enabled: bool

    @property
    def is_dev(self) -> bool:
        return self.env == "development"


_settings: Settings | None = None


def _load_secret(data_dir: Path) -> str:
    env = os.getenv("JARVIS_SECRET_KEY")
    if env and len(env) >= 16:
        return env
    p = data_dir / ".secret_key"
    if p.exists():
        v = p.read_text().strip()
        if v:
            return v
    key = secrets.token_urlsafe(48)
    data_dir.mkdir(parents=True, exist_ok=True)
    try:
        p.write_text(key)
        p.chmod(0o600)
    except OSError:
        pass
    return key


def load_settings(**overrides) -> Settings:
    global _settings
    root = Path(__file__).resolve().parents[2]  # jarvis/ when file is jarvis/packages/config/config.py
    # when running from AgencyOS root, jarvis is subdir — validate root
    if not (root / ".env.example").exists():
        # fallback: find jarvis dir upward
        cand = Path.cwd() / "jarvis"
        if (cand / ".env.example").exists():
            root = cand
        else:
            for parent in Path(__file__).resolve().parents:
                if (parent / "jarvis" / ".env.example").exists():
                    root = parent / "jarvis"
                    break
                if (parent / ".env.example").exists() and (parent / "apps").exists():
                    root = parent
                    break
            # last fallback: use parents[3] (AgencyOS) if still not found
            if not (root / ".env.example").exists():
                alt = Path(__file__).resolve().parents[3]
                if (alt / ".env.example").exists():
                    root = alt

    data_dir = Path(overrides.pop("data_dir", None) or os.getenv("JARVIS_DATA_DIR") or root / "data")
    data_dir.mkdir(parents=True, exist_ok=True)

    db_url = os.getenv("JARVIS_DATABASE_URL") or f"sqlite:///{data_dir / 'jarvis.sqlite3'}"
    frontend = Path(os.getenv("JARVIS_FRONTEND_DIST") or root / "apps" / "web" / "dist")

    s = Settings(
        env=os.getenv("JARVIS_ENV", "development").lower(),
        data_dir=data_dir,
        database_url=db_url,
        redis_url=os.getenv("JARVIS_REDIS_URL") or None,
        secret_key=_load_secret(data_dir),
        frontend_dist=frontend,
        allow_signup=_bool("JARVIS_ALLOW_SIGNUP", True),
        token_ttl_minutes=int(os.getenv("JARVIS_TOKEN_TTL_MINUTES", "1440")),
        host=os.getenv("JARVIS_HOST", "0.0.0.0"),
        port=int(os.getenv("JARVIS_PORT", "8000")),
        log_level=os.getenv("JARVIS_LOG_LEVEL", "INFO").upper(),
        llm_provider=os.getenv("JARVIS_LLM_PROVIDER", "auto").lower(),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
        openai_api_key=os.getenv("OPENAI_API_KEY") or None,
        anthropic_model_fast=os.getenv("JARVIS_ANTHROPIC_MODEL_FAST", "claude-haiku-4-5"),
        anthropic_model_strong=os.getenv("JARVIS_ANTHROPIC_MODEL_STRONG", "claude-sonnet-4-5"),
        openai_model_fast=os.getenv("JARVIS_OPENAI_MODEL_FAST", "gpt-4o-mini"),
        openai_model_strong=os.getenv("JARVIS_OPENAI_MODEL_STRONG", "gpt-4o"),
        ollama_url=os.getenv("JARVIS_OLLAMA_URL", "http://localhost:11434"),
        tavily_api_key=os.getenv("TAVILY_API_KEY") or None,
        allow_remote_access=_bool("JARVIS_ALLOW_REMOTE_ACCESS", False),
        max_tool_calls=int(os.getenv("JARVIS_MAX_TOOL_CALLS", "20")),
        max_runtime_s=int(os.getenv("JARVIS_MAX_RUNTIME_S", "120")),
        otel_enabled=_bool("JARVIS_OTEL_ENABLED", False),
    )
    for k, v in overrides.items():
        setattr(s, k, v)
    _settings = s
    return s


def settings() -> Settings:
    if _settings is None:
        return load_settings()
    return _settings
