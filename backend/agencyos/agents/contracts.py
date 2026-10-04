"""Agent contracts: the normalised shape every agent (built-in, imported, custom) has.

Separation of concerns:
  AgentDefinition  -> capability + contract metadata (registry)
  AgentAdapter     -> how an agent is executed (adapters.py)
  Orchestrator     -> when/why it runs (orchestration/engine.py)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class Permission(str, Enum):
    READ_PROJECT = "READ_PROJECT"
    READ_ARTIFACT = "READ_ARTIFACT"
    WRITE_ARTIFACT = "WRITE_ARTIFACT"
    WRITE_CODE = "WRITE_CODE"
    EXECUTE_CODE = "EXECUTE_CODE"
    RUN_TESTS = "RUN_TESTS"
    ACCESS_WEB = "ACCESS_WEB"
    ACCESS_GITHUB = "ACCESS_GITHUB"
    DEPLOY = "DEPLOY"
    SEND_EMAIL = "SEND_EMAIL"


class AgentContractSpec(BaseModel):
    inputs: list[str] = []
    task: str = ""
    constraints: list[str] = []
    tools: list[str] = []
    expected_output: list[str] = []
    quality_criteria: list[str] = []
    do_not: list[str] = []


class AgentDefinition(BaseModel):
    id: str
    name: str
    role: str | None = None
    description: str
    capabilities: list[str] = []
    industry: str | None = "general"
    category: str | None = None
    framework: str = "builtin"
    source: str = "builtin"  # builtin | github | catalogue | custom
    execution_mode: str = "in_process"  # in_process | sandbox | prompt | catalogue_only
    entrypoint: str | None = None
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    tools: list[str] = []
    permissions: list[Permission] = []
    dependencies: list[str] = []
    environment_requirements: list[str] = []
    required_credentials: list[str] = []
    supported_tasks: list[str] = []
    risk_level: str = "low"  # low | medium | high
    cost_estimate_usd: float = 0.0
    version: str = "1.0.0"
    license: str | None = None
    source_url: str | None = None
    commit_hash: str | None = None
    contract: AgentContractSpec = Field(default_factory=AgentContractSpec)
    system_instructions: str | None = None  # custom/prompt agents only
    model_tier: str = "strong"


@dataclass
class ArtifactOut:
    name: str
    type: str
    content: Any
    content_type: str = "application/json"  # or text/markdown, text/plain, application/yaml, text/x-sql
    note: str | None = None


@dataclass
class AgentContext:
    project: dict
    requirements: dict
    task: dict
    artifacts: dict[str, Any]           # name -> latest content (only the ones this task needs)
    memory: list[dict]                  # relevant project memory entries
    feedback: list[str]                 # review / QA / user feedback for revisions
    workspace: Path
    llm: Any                            # LLMClient
    permissions: set[str]
    params: dict = field(default_factory=dict)

    def require(self, perm: Permission) -> None:
        if perm.value not in self.permissions:
            raise PermissionError(f"agent lacks permission {perm.value}")


@dataclass
class AgentResult:
    status: str  # success | failed | needs_input
    summary: str
    artifacts: list[ArtifactOut] = field(default_factory=list)
    structured_output: dict = field(default_factory=dict)
    logs: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    confidence: float = 0.8
    question: str | None = None  # for needs_input: escalate to the user
    provider: str = "mock"
    model: str = "deterministic"


ROLE_PERMISSIONS: dict[str, list[Permission]] = {
    "project_manager": [Permission.READ_PROJECT, Permission.READ_ARTIFACT, Permission.WRITE_ARTIFACT],
    "business_analyst": [Permission.READ_PROJECT, Permission.WRITE_ARTIFACT],
    "researcher": [Permission.READ_PROJECT, Permission.WRITE_ARTIFACT, Permission.ACCESS_WEB],
    "ux_designer": [Permission.READ_PROJECT, Permission.READ_ARTIFACT, Permission.WRITE_ARTIFACT],
    "ui_designer": [Permission.READ_PROJECT, Permission.READ_ARTIFACT, Permission.WRITE_ARTIFACT],
    "architect": [Permission.READ_PROJECT, Permission.READ_ARTIFACT, Permission.WRITE_ARTIFACT],
    "content_writer": [Permission.READ_PROJECT, Permission.WRITE_ARTIFACT],
    "seo_specialist": [Permission.READ_PROJECT, Permission.READ_ARTIFACT, Permission.WRITE_ARTIFACT],
    "frontend_developer": [Permission.READ_PROJECT, Permission.READ_ARTIFACT, Permission.WRITE_CODE,
                           Permission.WRITE_ARTIFACT, Permission.RUN_TESTS],
    "backend_developer": [Permission.READ_PROJECT, Permission.READ_ARTIFACT, Permission.WRITE_CODE,
                          Permission.WRITE_ARTIFACT, Permission.RUN_TESTS],
    "database_engineer": [Permission.READ_PROJECT, Permission.READ_ARTIFACT, Permission.WRITE_ARTIFACT,
                          Permission.WRITE_CODE],
    "qa_engineer": [Permission.READ_PROJECT, Permission.READ_ARTIFACT, Permission.WRITE_ARTIFACT,
                    Permission.RUN_TESTS, Permission.EXECUTE_CODE],
    "security_engineer": [Permission.READ_PROJECT, Permission.READ_ARTIFACT, Permission.WRITE_ARTIFACT],
    "performance_engineer": [Permission.READ_PROJECT, Permission.READ_ARTIFACT, Permission.WRITE_ARTIFACT],
    "accessibility_specialist": [Permission.READ_PROJECT, Permission.READ_ARTIFACT, Permission.WRITE_ARTIFACT],
    "technical_writer": [Permission.READ_PROJECT, Permission.READ_ARTIFACT, Permission.WRITE_CODE,
                         Permission.WRITE_ARTIFACT],
    "devops_engineer": [Permission.READ_PROJECT, Permission.READ_ARTIFACT, Permission.WRITE_ARTIFACT,
                        Permission.DEPLOY],
    "reviewer": [Permission.READ_PROJECT, Permission.READ_ARTIFACT],
    "change_analyst": [Permission.READ_PROJECT, Permission.READ_ARTIFACT],
}
