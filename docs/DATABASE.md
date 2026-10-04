# Database

Schema is in `backend/agencyos/db.py` (created on startup). Main tables:

| Table | Purpose |
|---|---|
| users, organizations, memberships | accounts, workspaces, roles (owner/admin/manager/developer/viewer) |
| projects | status, progress, cost, demo flag, archive |
| requirement_versions, interview_state | versioned specs; interview progress |
| chat_messages | conversation with structured `meta` (questions, plan, approvals, change requests) |
| tasks, task_dependencies | the DAG |
| agents, agent_metrics | registry + routing data |
| agent_executions, llm_usage | trace, tokens, cost per call |
| artifacts, artifact_versions, reviews | versioned deliverables and review verdicts |
| approvals | gates and decisions |
| project_events | activity feed / event log |
| project_memory | preferences, decisions, pending changes |
| deployments | releases and logs |
| notifications, org_secrets, audit_logs | — |

Foreign keys cascade on project or organisation deletion. Indexes cover project/org lookups and the event stream.
