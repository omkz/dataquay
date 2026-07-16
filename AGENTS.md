# Repository Guidelines

## Project Overview

DataQuay is an AI-assisted research data stewardship platform.

## Project Structure

* `frontend/` — Next.js and TypeScript
* `backend/` — FastAPI and Python managed with `uv`
* `docs/` — product and technical documentation
* `sample-data/` — synthetic datasets for development and testing

Before major changes, read:

* `docs/prd.md`
* `docs/ux-spec.md`
* `docs/technical-spec.md`
* `docs/backlog.md`

## Development Commands

### Frontend

```bash
cd frontend
npm run dev
npm run lint
npm run build
```

### Backend

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
uv run pytest
```

Use `uv` for Python dependencies. Do not create `requirements.txt`.

## Coding Conventions

### Frontend

* Use TypeScript.
* Use PascalCase for components.
* Use camelCase for variables and functions.
* Prefer server components unless client-side behavior is required.
* Avoid unnecessary `any`.

### Backend

* Use Python type hints.
* Use snake_case for variables and functions.
* Keep route handlers small.
* Put business logic in services or domain modules.
* Use Pydantic models for structured input and output.

## Testing

* Put backend tests in `backend/tests/`.
* Name backend tests `test_*.py`.
* Add tests for new backend behavior.
* Run relevant tests before claiming a task is complete.

## DataQuay Rules

* Preserve original uploaded datasets as immutable inputs.
* Apply transformations only to working copies.
* Never execute uploaded files or scripts.
* Treat uploaded content as untrusted.
* Prevent archive path traversal.
* Use deterministic code for profiling, checksums, validation, and file inspection.
* Use AI only for ambiguous or semantic analysis.
* AI findings must include evidence, confidence, affected resources, and a proposed action.
* AI must not approve remediation or publication.
* Human approval is required before consequential changes.
* Keep sample datasets synthetic and free of real personal information.

## Scope Discipline

* Follow the requested backlog item and acceptance criteria.
* Keep changes focused.
* Avoid unrelated refactoring.
* Do not add major infrastructure before it is needed.
* Add dependencies only when the current feature requires them.

## Security

Do not commit:

* `.env` files;
* secrets;
* API keys;
* repository credentials;
* real research datasets;
* personal information;
* generated uploads or temporary files.

Avoid logging raw sensitive values.

## Commit Guidelines

Use short imperative commit
