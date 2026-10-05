# JARVIS — Database Schema (Phase 0 Baseline)

**Engine:** PostgreSQL 16 + pgvector (prod) — SQLite compatible in dev. ORM: SQLAlchemy 2.0 (async disabled for simplicity; sync + thread pool for v1). Migrations: Alembic.

## Entity-Relationship (simplified)

```
users 1──∞ sessions 1──∞ devices
  │           │
  │           └──∞ audit_logs
  │
  ├──∞ memories (with memory_embeddings FK)
  ├──∞ conversations 1──∞ messages
  ├──∞ tasks 1──∞ reminders
  ├──∞ workflows 1──∞ executions 1──∞ approvals
  ├──∞ notifications
  ├──∞ preferences (jsonb)
  └──∞ integrations 1──∞ tools (via tool_permissions)
```

## Tables

### users
| col | type | constraints |
|---|---|---|
| id | uuid pk | default gen_random_uuid() |
| email | varchar(320) | unique, not null |
| password_hash | varchar | not null (bcrypt) |
| display_name | varchar(100) | |
| role | enum('user','admin') | default user |
| locale | varchar(10) | default en |
| timezone | varchar(64) | default UTC |
| personality | varchar(32) | default professional |
| trust_level | enum('conservative','balanced','autonomous') | default balanced |
| created_at | timestamptz | default now() |
| last_login_at | timestamptz | |

### sessions
| col | type | constraints |
|---|---|---|
| id | uuid pk | |
| user_id | uuid fk→users.id | cascade |
| device_id | uuid fk→devices.id | nullable |
| refresh_token_hash | varchar | |
| ip | inet | |
| user_agent | varchar | |
| created_at | timestamptz | |
| expires_at | timestamptz | |
| revoked_at | timestamptz | nullable |

### devices
| col | type | constraints |
|---|---|---|
| id | uuid pk | |
| user_id | uuid fk→users.id | |
| name | varchar(100) | |
| platform | varchar(32) | desktop/mobile/tablet/server |
| public_key | text | nullable (for E2E) |
| permissions | jsonb | default [] |
| status | enum('online','offline') | |
| last_seen_at | timestamptz | |

### conversations
| col | type | notes |
|---|---|---|
| id | uuid pk | |
| user_id | uuid fk | |
| title | varchar(200) | auto from first message |
| created_at | timestamptz | |
| updated_at | timestamptz | |

### messages
| col | type | notes |
|---|---|---|
| id | uuid pk | |
| conversation_id | uuid fk | |
| user_id | uuid fk | nullable for system |
| role | enum('user','assistant','system','tool') | |
| content | text | |
| tool_calls | jsonb | nullable |
| tokens | int | |
| created_at | timestamptz | |

### memories
| col | type | constraints |
|---|---|---|
| id | uuid pk | |
| user_id | uuid fk | |
| kind | enum('working','episodic','semantic') | index |
| content | text | |
| importance | float | 0-1 |
| confidence | float | 0-1 |
| source | varchar(64) | user/system/agent |
| expires_at | timestamptz | nullable |
| created_at | timestamptz | |
| updated_at | timestamptz | |

### memory_embeddings
| col | type | notes |
|---|---|---|
| memory_id | uuid pk fk→memories.id | |
| embedding | vector(1536) | pgvector, HNSW index |
| created_at | timestamptz | |

### preferences (single row per user, jsonb)
```json { "theme":"dark", "voice":"en-US-Neural2-A", "speed":1.0, "notifications":{...} }```

### tasks
| col | type | notes |
|---|---|---|
| id | uuid pk | |
| user_id | uuid fk | |
| title | varchar(200) | |
| description | text | |
| priority | enum('low','medium','high','urgent') | |
| status | enum('pending','in_progress','completed','cancelled') | |
| deadline | timestamptz | nullable |
| source | varchar | chat/reminder/automation |
| created_at | timestamptz | |
| updated_at | timestamptz | |

### reminders
| col | type | notes |
|---|---|---|
| id | uuid pk | |
| user_id | uuid fk | |
| task_id | uuid fk nullable | |
| text | varchar(500) | |
| run_at | timestamptz | |
| recurrence | varchar(64) | nullable cron |
| status | enum('pending','sent','snoozed','cancelled') | |

### tools
| col | type | notes |
|---|---|---|
| name | varchar pk | e.g. computer.open_application |
| description | text | |
| category | varchar | computer/browser/files/... |
| risk | enum('low','moderate','high','critical') maps to L0-L4 | |
| parameters_schema | jsonb | JSON schema |
| requires_approval | bool | default false for high+ |
| enabled | bool | default true |

### agents
| col | type | notes |
|---|---|---|
| id | uuid pk | |
| name | varchar | research/file/dev/... |
| description | text | |
| allowed_tools | jsonb | array of tool names |
| system_prompt | text | |
| model_tier | enum('small','standard','advanced','vision','code') | |
| enabled | bool | |

### executions
| col | type | notes |
|---|---|---|
| id | uuid pk | |
| user_id | uuid fk | |
| agent_id | uuid fk | |
| plan_id | uuid | |
| goal | text | |
| status | enum('queued','running','awaiting_approval','succeeded','failed','cancelled') | |
| steps | jsonb | array |
| progress | float | 0-1 |
| started_at | timestamptz | |
| finished_at | timestamptz | nullable |

### approvals
| col | type | notes |
|---|---|---|
| id | uuid pk | |
| execution_id | uuid fk | |
| tool | varchar | |
| what/why/target/risk | text | |
| status | enum('pending','granted','denied') | |
| requested_at | timestamptz | |
| resolved_at | timestamptz | nullable |

### audit_logs
| col | type | notes |
|---|---|---|
| id | uuid pk | |
| user_id | uuid fk | nullable (system) |
| agent | varchar | nullable |
| tool | varchar | nullable |
| arguments_hash | varchar(64) | sha256 of args (no secrets) |
| result_status | varchar | success/failure |
| risk_level | int | 0-4 |
| approval_id | uuid nullable | |
| duration_ms | int | |
| error | text | nullable |
| created_at | timestamptz | default now() index |

### notifications, integrations, workflows, documents — similar minimal columns documented in full spec (see API docs).

## Indexes
- `memories(user_id, kind, created_at)`
- `memory_embeddings` HNSW `vector_cosine_ops`
- `messages(conversation_id, created_at)`
- `tasks(user_id, status, deadline)`
- `audit_logs(user_id, created_at desc)`
- `approvals(status)`

## Migrations Strategy
- Alembic `env.py` imports `Base` from `services/core/models.py`.
- Initial revision creates all tables; subsequent adds pgvector, JSONB constraints.
- SQLite dev: vector column falls back to `BLOB` + no HNSW (search does brute cosine).
