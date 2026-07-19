# DataQuay

DataQuay is an AI-assisted research data stewardship platform that helps research teams turn messy datasets into validated, documented, privacy-aware, and repository-ready packages.

## Status

Early development.

## Documentation

- [Product Requirements Document](docs/prd.md)
- [UX Specification](docs/ux-spec.md)
- [Technical Specification](docs/technical-spec.md)
- [MVP Backlog](docs/backlog.md)

## Project Structure

```text
dataquay/
├── frontend/
├── backend/
├── workers/
├── docs/
├── sample-data/
└── docker-compose.yml
```

## Environment Setup

Frontend and backend configuration are kept separate. Create local files from the
committed templates:

```bash
cp frontend/.env.example frontend/.env.local
cp backend/.env.example backend/.env.local
```

Next.js loads `frontend/.env.local` automatically. Start FastAPI with its local
environment file explicitly:

```bash
cd backend
uv run uvicorn app.main:app --reload --env-file .env.local
```

Generate two independent random secrets. Put one in `frontend/.env.local` as
`AUTH_SECRET`. Put the other in both service files as
`DATAQUAY_INTERNAL_AUTH_SECRET`; it signs short-lived server-to-server identity
tokens and must never use a `NEXT_PUBLIC_` prefix.

For local magic-link email, start Mailpit before signing in:

```bash
docker compose up -d mailpit
```

Mailpit accepts SMTP on `localhost:1025`; open its local inbox at
`http://localhost:8025`. Messages are captured locally and are not delivered to
real addresses.

Local `.env` files are ignored by Git. Never put real provider API keys in the
committed `.env.example` files.

PostgreSQL stores workspace and workflow metadata while archives, extracted
originals, working copies, and packages remain in local storage. After setting
`DATAQUAY_DATABASE_URL` in `backend/.env.local`, apply migrations before starting
the API:

```bash
cd backend
uv sync
uv run alembic upgrade head
```

To verify a rollback during development, run `uv run alembic downgrade base` and
then reapply `uv run alembic upgrade head`.

The same PostgreSQL database is configured in Next.js with
`AUTH_DATABASE_URL`. Alembic is the only migration system: Auth.js must not run
or generate schema migrations. Migration `0002` creates the magic-link users,
sessions, verification tokens, and nullable workspace ownership. Existing
unowned workspaces stay inaccessible until an explicit ownership migration is
designed.
