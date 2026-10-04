# Orchestration

## Lifecycle
`DISCOVERY → REQUIREMENTS → (approve) → PLANNING → (start) → RESEARCH/DESIGN/ARCHITECTURE/DEVELOPMENT/QA/SECURITY_REVIEW → USER_ACCEPTANCE → READY_TO_DEPLOY → DEPLOYING → COMPLETED`, plus `BLOCKED` and `CANCELLED`. The project status is **derived** from the task graph and pending approvals in `Orchestrator.refresh_project`. It is never set to "look busy".

## Task graph
`planner.TEMPLATE` lists every possible task with phase, role, kind, inputs, outputs and dependencies. `create_plan` keeps only tasks whose role is in the team (`teams.build_team`) and drops dependencies on missing tasks. It then checks the graph is acyclic. Kinds:
- `work`: produces artifacts. Reviewed.
- `check`: QA / a11y / performance / security. The report decides pass or fail.
- `fix`: bug-fix tasks created by failed checks.
- `approval`: human gates (design, acceptance, deploy, decision).
- `deploy`: runs the deployment adapter plus a health check.

Statuses: `BACKLOG READY IN_PROGRESS BLOCKED REVIEW REVISION_REQUIRED APPROVED COMPLETED FAILED`.

## Per-task execution (`run_task`)
1. `registry.select_agent(role)` picks the best enabled, healthy agent (score = success rate, review pass rate, cost, latency).
2. `build_context` assembles the minimal context.
3. The adapter runs the agent. Exceptions and permission errors become failed results.
4. Execution row: tokens, cost, provider/model, tools, logs, errors and duration go to the registry metrics and project cost.
5. Artifacts are saved as **new versions**, mirrored into the workspace, and `git commit -m "agent(<role>): …"` runs.
6. **Review**: `review.review()` checks each artifact against its contract. On failure: `REVISION_REQUIRED` with feedback, then re-run. After `MAX_REVISIONS` it escalates.
7. **Failure**: retry up to `MAX_TASK_RETRIES`, then an alternate compatible agent, then escalation (a decision approval for the user).

## QA bug loop (§57)
A failing check creates `fix_<check>_<owner>_<n>` tasks for the owning role (frontend/backend/ui/content). It adds a rebuild task when a design or content role was the owner, makes the check depend on the fixes and re-queues it. The loop is bounded by `MAX_REVISIONS`, then escalates. The frontend fixer applies deterministic remediations (alt text, labels, broken links, headings, meta, overflow, focus, touch targets). With an LLM, more fixers can be added behind the same issue codes.

## Gates (§26, §81)
- Requirements: before any plan exists.
- Design & architecture: developers cannot start (`db_schema`, `frontend` depend on it).
- Acceptance: after QA, a11y, perf, security, docs and the deploy plan all pass.
- Deploy: explicit authorisation. Nothing deploys without it.
- Decision: escalations ("accept with known issues" or "let the team try again").

## Change requests (§31–34)
Chat text → `changes.analyze` (feature add/remove, colour/style, copy/layout words) gives affected tasks, downstream tasks, agents, estimated time and cost, plus contradictions with explicit earlier choices. The user confirms, then `apply_change`:
- writes a new requirements version
- stores memory (`avoid_color:gold`, `style`)
- extends the plan for new scope (e.g. booking added to a brochure site gets architect, DB and backend tasks)
- resets affected and downstream tasks with the request as feedback
- supersedes pending approvals

The UI designer and reviewer read memory, so rejected colours never return.

## Guards (§90)
Max retries, max revisions, max executions per project, max budget per project, DAG cycle check, one active advance per project (no ping-pong), and restart recovery (mid-flight tasks re-queued, never lost).
