# Deployment

## Running AgencyOS
- `docker build -t agencyos . && docker run -p 8000:8000 -e AGENCYOS_SECRET_KEY=… -v agencyos-data:/data agencyos`
- Put it behind HTTPS (Caddy/nginx). SSE needs proxy buffering off (`X-Accel-Buffering: no` is sent).
- Set `AGENCYOS_SECRET_KEY` explicitly in production. Changing it invalidates sessions and stored provider keys.
- To run third-party agents, mount the Docker socket into a **separate** worker host. Never do this on the API host.

## Deploying generated projects
Adapters live in `services/deploy.py`:
- `local`: copies the build to `data/deployments/<project>/releases/<id>`, flips `CURRENT`, health-checks it and serves it at `/sites/<project>/`. Rollback re-points `CURRENT`.
- `netlify`: zip deploy via API (`NETLIFY_AUTH_TOKEN`, `NETLIFY_SITE_ID`).
- Vercel, AWS, Azure, GCP, Render and Railway implement the same `DeploymentAdapter` interface (listed as "interface only").

Flow: build → tests → security scan → client acceptance → deploy authorisation → deploy → health check → URL.
The generated API (`source/api/server.py`) is deployed separately with `ADMIN_TOKEN` and `ALLOWED_ORIGIN` set, and `assets/config.js` points the site at it.
