# JARVIS — Agent Model

## Concept
Agents are specialized AI workers. Each has a system prompt, model tier, allowed tools, and execution limits. The Orchestrator dispatches plan steps to agents.

## Base Interface

```python
class AgentDefinition:
    id: str                 # e.g. "research"
    name: str               # "Research Agent"
    description: str
    allowed_tools: list[str]   # subset of registry; [] means no tools (pure reasoning)
    system_prompt: str
    model_tier: Literal["small","standard","advanced","vision","code","speech"]
    max_runtime_s: int = 120
    max_tool_calls: int = 20
    max_tokens: int = 8000
    enabled: bool = True

class AgentAdapter:
    async def run(self, execution: Execution, step: PlanStep, context: Context) -> AgentResult
```

## Built-in Agents (11 required)

| Agent | Tier | Tools | Purpose |
|---|---|---|---|
| GeneralAssistant | standard | all low-risk + search, files.read | General reasoning fallback |
| Research | advanced | browser.*, search.* | Web research, source cross-check |
| Computer | standard | computer.* , system.* | App launch, window mgmt |
| File | standard | files.* | Search/read/summarize documents |
| Developer | code | developer.*, files.*, system.* | Repo inspection, patch propose, test run |
| Communication | standard | email.*, messaging.* | Draft/reply/send (send needs approval) |
| Scheduling | small | calendar.*, reminders | Calendar/reminders, briefing |
| Automation | standard | automation.*, scheduler.* | Workflow execution |
| Vision | vision | vision.*, files.read | Image/screen analysis, OCR |
| System | small | system.* | Diagnostics, monitoring |
| Security | standard | security.*, audit | Permission enforcement, scanning |

## Execution Lifecycle

```
Queue Execution → Orchestrator picks agent → check permissions→ run
→ emit TOOL_STARTED per tool → collect results → verification →
→ if high-risk: approval gate → resume → final result or failure → audit
```

Metrics per execution: latency, tokens, cost, tool_calls, errors.

## Orchestrator Responsibilities

- Build context via `ContextEngine` (only inputs listed in step)
- Route to correct agent (first via plan assignment, fallback via intent)
- Enforce per-agent limits (`max_runtime_s`, `max_tool_calls`, etc.)
- Handle fallback: if primary agent fails, try alternate agent with same tools (bounded retry)
- Emit events: `AGENT_STARTED`, `AGENT_COMPLETED`, `AGENT_FAILED`

## Adding a New Agent

1. Add `AgentDefinition` to `services/agent/builtin.py`
2. Implement adapter if custom runtime (else default LLM-backed adapter)
3. Register tools it may use (already in registry)
4. Add benchmark scenario to `tests/agent/`

## Example — DeveloperAgent bounded execution
```python
dev = registry.get("developer")
execution = Execution(id="...", goal="Fix failing tests", steps=[...])
# Orchestrator ensures it cannot call email.send (not in allowed_tools) even if LLM hallucinates it
```
