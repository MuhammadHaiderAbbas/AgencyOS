"""Runtime configuration. Everything comes from environment variables (see .env.example)."""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path


def _bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    data_dir: Path
    database_path: Path
    secret_key: str
    llm_provider: str  # auto | mock | anthropic | openai
    anthropic_api_key: str | None
    openai_api_key: str | None
    anthropic_model_fast: str
    anthropic_model_strong: str
    openai_model_fast: str
    openai_model_strong: str
    agent_repo_path: Path | None
    agent_repo_url: str
    enable_external_agents: bool
    step_delay: float
    max_task_retries: int
    max_revisions: int
    max_project_executions: int
    max_project_budget_usd: float
    access_token_ttl_minutes: int
    frontend_dist: Path
    allow_signup: bool
    # ---- Monetization & earning ----
    stripe_secret_key: str | None
    stripe_publishable_key: str | None
    stripe_webhook_secret: str | None
    stripe_price_pro: str | None
    stripe_price_business: str | None
    base_url: str
    # ---- Email ----
    smtp_host: str | None
    smtp_port: int
    smtp_user: str | None
    smtp_password: str | None
    smtp_from: str | None
    smtp_use_tls: bool
    # ---- GitHub ----
    github_token: str | None
    github_client_id: str | None
    github_client_secret: str | None
    extra: dict = field(default_factory=dict)

    @property
    def workspaces_dir(self) -> Path:
        return self.data_dir / "workspaces"

    @property
    def deployments_dir(self) -> Path:
        return self.data_dir / "deployments"


_settings: Settings | None = None


def _load_secret(data_dir: Path) -> str:
    env = os.getenv("AGENCYOS_SECRET_KEY")
    if env:
        return env
    # Local development convenience: generate once and persist (never committed; data/ is git-ignored).
    p = data_dir / ".secret_key"
    if p.exists():
        return p.read_text().strip()
    key = secrets.token_urlsafe(48)
    p.write_text(key)
    try:
        p.chmod(0o600)
    except OSError:
        pass
    return key


def load_settings(**overrides) -> Settings:
    global _settings
    root = Path(__file__).resolve().parents[2]
    data_dir = Path(overrides.pop("data_dir", None) or os.getenv("AGENCYOS_DATA_DIR") or root / "data")
    data_dir.mkdir(parents=True, exist_ok=True)
    repo = os.getenv("AGENCYOS_AGENT_REPO_PATH")
    s = Settings(
        data_dir=data_dir,
        database_path=Path(os.getenv("AGENCYOS_DATABASE_PATH") or data_dir / "agencyos.sqlite3"),
        secret_key=_load_secret(data_dir),
        llm_provider=os.getenv("AGENCYOS_LLM_PROVIDER", "auto").lower(),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
        openai_api_key=os.getenv("OPENAI_API_KEY") or None,
        anthropic_model_fast=os.getenv("AGENCYOS_ANTHROPIC_MODEL_FAST", "claude-haiku-4-5"),
        anthropic_model_strong=os.getenv("AGENCYOS_ANTHROPIC_MODEL_STRONG", "claude-sonnet-4-5"),
        openai_model_fast=os.getenv("AGENCYOS_OPENAI_MODEL_FAST", "gpt-4o-mini"),
        openai_model_strong=os.getenv("AGENCYOS_OPENAI_MODEL_STRONG", "gpt-4o"),
        agent_repo_path=Path(repo) if repo else None,
        agent_repo_url=os.getenv(
            "AGENCYOS_AGENT_REPO_URL", "https://github.com/ashishpatel26/500-AI-Agents-Projects"
        ),
        enable_external_agents=_bool("AGENCYOS_ENABLE_EXTERNAL_AGENTS", False),
        step_delay=float(os.getenv("AGENCYOS_STEP_DELAY", "0.6")),
        max_task_retries=int(os.getenv("AGENCYOS_MAX_TASK_RETRIES", "2")),
        max_revisions=int(os.getenv("AGENCYOS_MAX_REVISIONS", "3")),
        max_project_executions=int(os.getenv("AGENCYOS_MAX_PROJECT_EXECUTIONS", "400")),
        max_project_budget_usd=float(os.getenv("AGENCYOS_MAX_PROJECT_BUDGET_USD", "25")),
        access_token_ttl_minutes=int(os.getenv("AGENCYOS_TOKEN_TTL_MINUTES", "1440")),
        frontend_dist=Path(os.getenv("AGENCYOS_FRONTEND_DIST") or root / "frontend" / "dist"),
        allow_signup=_bool("AGENCYOS_ALLOW_SIGNUP", True),
        stripe_secret_key=os.getenv("STRIPE_SECRET_KEY") or None,
        stripe_publishable_key=os.getenv("STRIPE_PUBLISHABLE_KEY") or None,
        stripe_webhook_secret=os.getenv("STRIPE_WEBHOOK_SECRET") or None,
        stripe_price_pro=os.getenv("STRIPE_PRICE_PRO") or None,
        stripe_price_business=os.getenv("STRIPE_PRICE_BUSINESS") or None,
        base_url=(os.getenv("AGENCYOS_BASE_URL") or os.getenv("BASE_URL") or "http://localhost:8000").rstrip("/"),
        smtp_host=os.getenv("SMTP_HOST") or os.getenv("EMAIL_SMTP_HOST") or None,
        smtp_port=int(os.getenv("SMTP_PORT") or os.getenv("EMAIL_SMTP_PORT") or 587),
        smtp_user=os.getenv("SMTP_USER") or os.getenv("EMAIL_SMTP_USER") or None,
        smtp_password=os.getenv("SMTP_PASSWORD") or os.getenv("EMAIL_SMTP_PASSWORD") or None,
        smtp_from=os.getenv("SMTP_FROM") or os.getenv("EMAIL_FROM") or None,
        smtp_use_tls=_bool("SMTP_USE_TLS", True),
        github_token=os.getenv("GITHUB_TOKEN") or None,
        github_client_id=os.getenv("GITHUB_CLIENT_ID") or None,
        github_client_secret=os.getenv("GITHUB_CLIENT_SECRET") or None,
    )
    for k, v in overrides.items():
        setattr(s, k, v)
    s.workspaces_dir.mkdir(parents=True, exist_ok=True)
    s.deployments_dir.mkdir(parents=True, exist_ok=True)
    _settings = s
    return s


def settings() -> Settings:
    if _settings is None:
        return load_settings()
    return _settings
