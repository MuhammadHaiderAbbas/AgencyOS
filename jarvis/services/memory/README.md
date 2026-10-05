# JARVIS — Memory Model

## Three Tiers

| Tier | Lifetime | Example | Retrieval |
|---|---|---|---|
| Working | Current conversation | “The user just asked about calendar” | ContextEngine window (last N messages) |
| Episodic | Days–months | “Yesterday you asked to prepare quarterly report” | Semantic search + time filter |
| Semantic | Persistent | “User prefers dark UI, timezone UTC, US English” | Key-value + embedding search |

## Memory Record

```json
{
  "id": "uuid",
  "user_id": "uuid",
  "kind": "working|episodic|semantic",
  "content": "User prefers dark UI",
  "importance": 0.9,
  "confidence": 0.85,
  "source": "user|system|agent",
  "expires_at": null,
  "embedding": [0.12, ...],
  "created_at": "ISO8601"
}
```

Fields: `importance` (0-1), `confidence` (0-1), `source`, `expires_at`, `embedding` (pgvector 1536).

## Operations

- `create(user_id, kind, content, importance?, confidence?, expires_at?) → Memory`
- `update(id, patch) → Memory`
- `delete(id)` / `delete_all(user_id, kind?)`
- `search(user_id, query, kinds?, limit?, time_range?) → [{memory, score}]` (cosine via pgvector, fallback brute)
- `list(user_id, kind?, limit?, offset?) → {memories, total}`

## Policy

- Do NOT save everything. `MemoryPolicy` decides: user says “Remember this” → semantic with high importance; casual chat → working only.
- Sensitive info requires explicit consent (`allow_memory_sensitive` preference).
- Expiration: working auto-expires with conversation (session), episodic TTL configured (default 90 days), semantic persistent until deleted.
- Deduplication: on create, search similar >0.92 cosine → update importance instead of duplicate.

## Controls (User-facing)

- “Remember this”: `POST /memory {kind:semantic, content:...}`
- “Forget that”: `DELETE /memory/{id}` or `POST /memory/controls {action:forget, target:"dark UI"}`
- “Show what you remember”: `GET /memory` or search
- “Don’t remember this conversation”: flag conversation `ephemeral:true` → working only, no episodic write.
- “Delete my memories”: `POST /memory/controls {action:delete_all}`

## Integration

- `ContextEngine` loads: last 10 working + top-5 relevant episodic/semantic via `memory.search(current_intent)`.
- `Planner` uses memories to personalize steps.
- `InputManager` emits `MEMORY_CREATED` on store.

## Storage

Tables: `memories` + `memory_embeddings` (vector). In dev SQLite, embeddings stored as JSON blob and brute-forced; prod uses `vector(1536)` HNSW.
