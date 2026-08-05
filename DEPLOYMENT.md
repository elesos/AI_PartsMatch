# Production deployment

Production is defined by the root `docker-compose.yml`; it does not read `.env` or `env_file`.
Bootstrap-only credentials are mounted from gitignored files under `.secrets/`. Runtime business
settings (public origins, exact CORS allowlist, storage routing, support contacts and AI tuning) are
idempotently loaded into `sys_configs` from `api/deploy/sys_configs.production.json`.

Host bindings:

- API: `127.0.0.1:8880` → `match-api.elesos.cc`
- Customer frontend: `127.0.0.1:8881` → `match.elesos.cc`
- Admin frontend: `127.0.0.1:8882` → `match-admin.elesos.cc`
- MinIO S3/console: `127.0.0.1:8890` / `127.0.0.1:8891` (local administration only)
- PostgreSQL and Redis have no host-published ports.

The API startup order is Alembic upgrade, production `sys_configs`, initial administrator bootstrap,
idempotent catalogue seed, then Uvicorn. Uploaded content is served through the HTTPS API origin at
`/api/v1/files/content/...`; the MinIO bucket itself remains private.
