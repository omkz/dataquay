# DataQuay

DataQuay is an AI-assisted research data stewardship application that turns a
messy research dataset into a human-reviewed, validated, and documented ZIP
package with provenance and checksums.

The current MVP supports a complete authenticated local demo while keeping
source files immutable, deterministic checks in control, and consequential
changes subject to explicit human approval.

## Why DataQuay

Research datasets often arrive with missing documentation, inconsistent dates,
duplicate records, broken cross-file references, suspicious sentinel values,
and possible personal data. Reviewing those issues manually is slow and hard to
standardize.

DataQuay inventories and profiles the dataset, explains findings, collects
missing context, proposes remediation, validates the result, and produces an
auditable package without allowing AI to approve or apply changes by itself.

## Workflow

```text
Magic-link sign-in
  → Upload ZIP into an owned workspace
  → Inspect files and calculate deterministic findings
  → Answer or defer clarification questions
  → Generate structured AI recommendations
  → Approve or reject each recommendation
  → Preview and apply supported remediation to a working copy
  → Validate checksums, findings, and source immutability
  → Generate and download the final ZIP
  → Review the persisted audit trail
```

Persisted workspaces can be reopened after a new session. A synthetic demo
dataset is included in `sample-data/`.

## Safeguards

- Uploaded archives and extracted originals remain read-only. Remediation uses a
  separate working copy.
- ZIP extraction rejects unsafe paths, links, special files, encrypted entries,
  unsupported extensions, oversized archives, and suspicious compression.
- Inspection, profiling, checksums, remediation, validation, manifests, and ZIP
  generation use deterministic code paths.
- The Data Steward Agent receives structured findings and clarification state,
  not raw dataset rows.
- AI output is proposal-only. Every recommendation requires an explicit human
  decision before supported remediation can run.
- Package generation stops when integrity checks fail, and workflow actions are
  recorded in the audit trail.
- Workspace ownership is enforced without revealing whether another user's
  workspace exists.

## Architecture

```text
Browser
  → Next.js application, Auth.js, and server-side API proxy
      → short-lived signed internal identity token
          → FastAPI workflow API
              ├── PostgreSQL: users, sessions, workspaces, decisions, audit state
              ├── Local filesystem: archives, originals, working copies, packages
              └── PydanticAI: configurable Data Steward Agent provider/model
```

| Area | Implementation |
| --- | --- |
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS |
| Authentication | Auth.js 5, PostgreSQL adapter, Nodemailer magic links, JOSE |
| Backend | Python 3.14, FastAPI, Pydantic, SQLAlchemy, Alembic |
| Data processing | Polars and deterministic inspection/remediation services |
| AI | PydanticAI with a provider-qualified runtime model |
| Persistence | PostgreSQL metadata plus isolated local filesystem workspaces |
| Tests | Pytest coverage for authentication, migrations, persistence, and the full workflow |

Repository layout:

```text
dataquay/
├── frontend/       # Next.js UI, Auth.js, server actions, authenticated proxy
├── backend/        # FastAPI routes, services, models, migrations, and tests
├── docs/           # Product, UX, technical, and backlog documents
├── sample-data/    # Synthetic demo dataset
└── compose.yaml    # Local Mailpit service
```

## Authentication

Auth.js sends 15-minute magic links through the configured SMTP server and stores
database sessions in PostgreSQL. Next.js protects pages and API routes, then
signs a short-lived identity token for backend requests. FastAPI validates the
token before enforcing workspace ownership.

`AUTH_SECRET` and `DATAQUAY_INTERNAL_AUTH_SECRET` must be separate random values
of at least 32 bytes. The internal secret must match in the frontend and backend
and must never use a `NEXT_PUBLIC_` prefix.

Alembic is the only owner of the shared PostgreSQL schema.

## Local setup

Prerequisites: PostgreSQL, `uv`, Node.js/npm, and Docker for local Mailpit.

1. Copy the environment templates:

   ```bash
   cp backend/.env.example backend/.env.local
   cp frontend/.env.example frontend/.env.local
   ```

2. Configure the environment:

   - Point `DATAQUAY_DATABASE_URL` and `AUTH_DATABASE_URL` to the same database.
   - Generate independent `AUTH_SECRET` and `DATAQUAY_INTERNAL_AUTH_SECRET`
     values, and copy the internal secret to both services.
   - Configure `DATAQUAY_AI_MODEL` and the selected provider credential.
   - Keep the Mailpit SMTP defaults for local sign-in or provide another SMTP
     server and sender.

3. Start Mailpit and prepare the database:

   ```bash
   docker compose up -d mailpit

   cd backend
   uv sync
   uv run alembic upgrade head
   ```

4. Start FastAPI from `backend/`:

   ```bash
   uv run uvicorn app.main:app --reload --env-file .env.local
   ```

5. Start Next.js in another terminal:

   ```bash
   cd frontend
   npm ci
   npm run dev
   ```

Open `http://localhost:3000`, request a sign-in link, and retrieve it from
Mailpit at `http://localhost:8025`. The backend health endpoint is
`http://localhost:8000/health`.

Local environment files, provider keys, uploaded data, and generated packages
must not be committed.

## Verification

Run the release checks from a configured checkout:

```bash
cd backend
uv sync --frozen
uv run alembic current
uv run alembic check
uv run pytest

cd ../frontend
npm ci
npm run lint
npm run typecheck
npm run build
```

Release verification also exercises the authenticated workflow from upload
through package download, including migration state, ownership isolation,
immutable originals, remediation, validation, manifest checksums, and the final
audit event.

## Generated package

The deterministic ZIP contains the validated working dataset and generated
documentation:

```text
data/                      # Validated working-copy files
README.md                  # Dataset and validation summary
data-dictionary.csv        # CSV columns, inferred types, and missing counts
metadata.json              # Dataset, package, readiness, and finding summary
file-manifest.json         # File paths, sizes, and SHA-256 checksums
checksums.sha256           # Verifiable package-content checksums
validation-report.json     # Resolved findings and integrity results
provenance.json            # Applied, skipped, and failed actions with checksums
```

Entries are sorted and use a fixed timestamp so identical inputs and workflow
results produce deterministic package bytes.

## Current product scope

DataQuay currently focuses on a secure, auditable stewardship workflow for
CSV-centric research datasets and individually owned workspaces. The application
is designed so storage, execution, collaboration, and repository integrations can
evolve independently as the product grows.

- Deep profiling and automated transformations currently focus on CSV files,
  while other allowlisted formats are inventoried and packaged safely.
- Automatic remediation is intentionally conservative. Context-dependent issues
  remain under human review rather than being changed automatically.
- Dataset artifacts are stored in isolated local workspaces. Object storage,
  background processing, retries, and distributed execution are natural next
  steps for larger deployments.
- Workspaces currently have a single owner. Organizations, team roles, sharing,
  and administrative ownership workflows are planned collaboration capabilities.
- Repository-ready ZIP packages are supported today. Direct publishing to iRODS
  and other research repositories is part of the integration roadmap.
- Privacy findings support data-steward review and risk identification; they do
  not replace institutional, legal, or regulatory assessment.
- AI recommendations remain advisory. Evidence, uncertainty, explicit approval,
  and deterministic validation continue to be the authoritative controls.
- The frontend currently loads Geist from Google Fonts. Self-hosted assets can be
  introduced for offline, restricted-network, or institutional deployments.

## Built and verified with Codex and GPT-5.6

Codex with GPT-5.6 was used as a development and verification collaborator. It
helped translate the product backlog into scoped changes, inspect and edit the
repository, add tests, run migrations and release gates, and drive the complete
authenticated workflow to find integration defects.

The runtime Data Steward Agent is deliberately narrower than the coding agent:
it receives structured inspection context, proposes remediation, and never
approves changes, executes uploaded content, validates integrity, or publishes
data.

## Project documents

- [Product requirements](docs/prd.md)
- [UX specification](docs/ux-spec.md)
- [Technical specification](docs/technical-spec.md)
- [MVP backlog](docs/backlog.md)
