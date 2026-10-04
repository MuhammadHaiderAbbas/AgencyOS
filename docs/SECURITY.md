# Security

- **Tenancy**: every query is scoped by `org_id` from the verified token (`project_for`, `artifact_for`). Live streams filter by org. Tests cover cross-tenant reads and writes.
- **Auth**: PBKDF2-SHA256 (390k rounds) and HS256 JWT. State-changing requests need the `Authorization` header. The HttpOnly SameSite=Lax cookie is accepted only for safe GETs (previews, downloads, SSE), which blocks CSRF. Login and signup are rate-limited.
- **Secrets**: provider keys are stored per organisation, Fernet-encrypted with a key derived from `AGENCYOS_SECRET_KEY`. They are masked in the API and never sent to the browser, agents' prompts, exports or clones.
- **Prompt injection (§89)**: user and external content is wrapped in `<requirements>` / `<answer>` / `<artifact>` tags and system prompts declare it data. Extraction accepts only whitelisted fields, and reviews can only make results stricter.
- **Sandboxing**: generated code and tests run through `services/sandbox.py`. In Docker mode: no network, read-only root, memory/CPU/pid limits, timeout. Without Docker: scrubbed env, rlimits, timeout. Third-party agents **require** Docker.
- **Generated sites**: strict CSP, no third-party scripts, parameterised SQL, request-size limits, constant-time admin token compare. The security agent blocks deployment on critical/high findings.
- **Files**: workspace and preview paths are resolved and confined. Path traversal is tested.
- **Audit**: signup, settings changes, agent enable/disable, imports, deletions.
