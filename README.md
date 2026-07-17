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

Local `.env` files are ignored by Git. Never put real provider API keys in the
committed `.env.example` files.
