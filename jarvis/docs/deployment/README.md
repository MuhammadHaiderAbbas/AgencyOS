# JARVIS — Deployment

## Development

```bash
./scripts/dev-start.sh
# or
docker compose up --build   # needs postgres + redis
python -m apps.gateway.main --port 8000  # from jarvis/
```

Health: `GET http://localhost:8000/api/v1/health`

## Docker Production

```bash
docker build -t jarvis:latest .
docker run -p 8000:8000 -e JARVIS_SECRET_KEY=$(openssl rand -hex 32) -v jarvis_data:/data jarvis:latest
```

With compose: `docker compose up -d` (postgres, redis, gateway).

## Environment

- `JARVIS_DATABASE_URL` — prefer `postgresql+psycopg://jarvis:jarvis@postgres:5432/jarvis`
- `JARVIS_REDIS_URL` — `redis://redis:6379/0` or empty for in-process
- `JARVIS_SECRET_KEY` — 32+ random; generate via `openssl rand -hex 32`
- `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` — optional

## Migrations

Alembic (future): `alembic upgrade head` (Phase 2).

## Backup/Restore

- DB: `pg_dump` / `sqlite .dump`
- Data: `tar czf backup.tar.gz data/`

Never backup secrets plaintext.

## HTTPS

Terminate at Caddy/Traefik. Example Caddyfile:

```
jarvis.example.com {
  reverse_proxy gateway:8000
}
```
