Postgres Docker setup for DocTalk
================================

Overview
--------
This file documents how to run a local Docker-based PostgreSQL instance, preserve the existing Prisma workflow, and enable `pgvector` for future RAG work.

Files added or changed
- `docker-compose.yml` — launches `db` (Postgres) and `pgadmin` with persistent volumes and a healthcheck.
- `.env` — root environment file for runtime and database variables.
- `.env.example` — non-sensitive example environment variables.
- `data/initdb/enable_extensions.sql` — init script to enable `vector` extension on DB creation.
- `backend/prisma/schema.prisma` — added `shadowDatabaseUrl` to the datasource for safe migrations.

Quick start
-----------
1. Edit the root `.env` and fill credentials.

   ```powershell
   notepad .env
   ```

2. Start Docker services:

   ```bash
   docker compose up -d
   ```

3. Confirm Postgres is healthy:

   ```bash
   docker compose ps
   docker logs --follow <compose-project-name>_db_1
   ```

Prisma commands (migrations & generate)
--------------------------------------
You can run Prisma commands either from your host (install Node.js & Prisma CLI) or via a one-off Docker container.

From host (requires Node.js + npm):

```bash
# install prisma CLI if you haven't
npx prisma generate
npx prisma migrate dev --name init --preview-feature
npx prisma db push
```

Via Docker (no local Node.js required):

```bash
docker run --rm -it \
  -v "${PWD}:/workspace" \
  -w /workspace \
  -e DATABASE_URL="$DATABASE_URL" \
  node:18-bullseye \
  bash -lc "npm install -g prisma && prisma generate && prisma migrate deploy || true"
```

Notes on `DATABASE_URL` vs `DIRECT_URL` vs `SHADOW_DATABASE_URL`
- `DATABASE_URL`: main connection string used at runtime by Prisma and your app.
- `DIRECT_URL`: used by Prisma Migrate engine to connect directly when needed; keep equal to `DATABASE_URL` for local setups.
- `SHADOW_DATABASE_URL`: recommended for `prisma migrate` to create a temporary shadow DB so migrations are tested safely.

Resetting the database
----------------------
- To completely reset the DB data (destructive):

```bash
docker compose down -v
docker compose up -d
```

- Or to drop and recreate only the application database (using psql):

```bash
# replace values as appropriate
psql "${DATABASE_URL}" -c "DROP DATABASE IF EXISTS doctalk; CREATE DATABASE doctalk;"
```

Viewing logs
------------
- To tail Postgres logs:

```bash
docker compose logs -f db
```

- To access pgAdmin UI, open http://localhost:8080 and use credentials from your `.env`.

pgvector support and future RAG work
-----------------------------------
- The init script `data/initdb/enable_extensions.sql` attempts to `CREATE EXTENSION IF NOT EXISTS vector;` on first DB init.
- The `docker-compose.yml` uses the official `postgres:15` image. If your Postgres image doesn't ship `pgvector`, switch the `db` image to a pgvector-enabled image (for example, `ankane/pgvector` or another vendor image) in `docker-compose.yml`.
- Prisma does not require schema changes now; when adding RAG features, you'll add vector columns and appropriate Prisma types (via community providers / raw SQL) later.

Ensuring no hosted-SQL dependencies
-----------------------------------
- This change replaces any previously hosted Postgres usage with a local Docker Postgres. The backend Python codebase did not contain any runtime hosted-SQL client usage; a legacy SQL export file previously existed and has been removed to avoid confusion. The project now runs purely on PostgreSQL.

If you want, I can:
- Add a `Makefile` or `scripts/` helpers to run the Prisma Docker commands.
- Swap `postgres:15` to a confirmed `pgvector` image tag.
