# DataQuay — Technical Specification

## 1. Purpose

DataQuay is an AI-assisted research data stewardship platform that helps research teams inspect, improve, validate, and prepare datasets for export or repository publication.

The system combines deterministic data processing, AI-assisted analysis, human approval, and repository connectors.

---

## 2. Architecture

```text
Next.js Frontend
        ↓
FastAPI Backend
        ↓
PostgreSQL + Object Storage
        ↓
Workflow Orchestrator
        ├── Inspection Pipeline
        ├── Data Steward Agent
        ├── Remediation Pipeline
        ├── Validation Engine
        └── Repository Connectors
```

Original uploaded files must remain immutable. All approved changes are applied to a new dataset version.

---

## 3. Technology Stack

### Frontend

* Next.js
* TypeScript
* Tailwind CSS
* shadcn/ui
* TanStack Query

### Backend

* Python
* FastAPI
* Pydantic
* SQLAlchemy
* Alembic

### Infrastructure

* PostgreSQL
* S3-compatible object storage
* MinIO for local development
* Temporal for workflow orchestration
* Docker Compose

### Data Processing

* Polars
* PyArrow
* openpyxl
* Pandera

### AI Layer

* PydanticAI
* configurable model provider and model name
* structured Pydantic outputs

### Privacy Detection

* Microsoft Presidio
* regular expressions
* AI-assisted semantic analysis

### Repository Integration

* python-irodsclient
* generic connector interface for future repositories

---

## 4. Core Workflow

```text
Upload dataset
→ Inspect files
→ Generate findings and recommendations
→ Wait for human review
→ Apply approved remediation
→ Validate results
→ Generate final package
→ Download or publish
```

Long-running work must run through background workers rather than inside HTTP requests.

Temporal should manage:

* workflow state;
* retries;
* timeouts;
* human approval waits;
* failed-step recovery.

---

## 5. Inspection Pipeline

The inspection pipeline performs deterministic analysis.

Initial stages:

```text
Extract package
→ Build file inventory
→ Generate checksums
→ Detect formats
→ Profile tabular files
→ Check documentation
→ Scan privacy patterns
```

For supported tabular files, collect:

* row and column counts;
* inferred data types;
* missing values;
* duplicate rows;
* unique-value counts;
* sample values;
* possible identifiers;
* possible relationships between files.

---

## 6. Data Steward Agent

The Data Steward Agent interprets ambiguous findings and proposes actions.

Responsibilities:

* classify probable file roles;
* interpret unclear columns;
* explain why issues matter;
* identify likely file relationships;
* assess documentation clarity;
* identify semantic privacy risks;
* generate clarification questions;
* propose remediation;
* draft README and metadata.

Each recommendation must include:

```text
category
severity
confidence
explanation
evidence
affected resources
proposed action
approval requirement
```

The agent must not:

* modify files directly;
* approve its own recommendations;
* publish datasets;
* claim legal compliance;
* hide uncertainty.

The AI provider and model must be configurable rather than hard-coded.

---

## 7. Human Approval

Human approval is required before:

* modifying dataset values;
* removing rows or columns;
* masking sensitive information;
* excluding files;
* generating the final package;
* publishing to a repository.

Each decision must record:

* user;
* action;
* timestamp;
* affected recommendation;
* optional note.

---

## 8. Remediation Pipeline

Approved actions are applied to a working copy.

Initial supported actions:

* rename files;
* reorganize folders;
* normalize dates;
* normalize missing-value markers;
* mask approved sensitive fields;
* generate README;
* generate data dictionary;
* generate metadata manifest;
* generate checksums.

Every transformation must record its inputs, outputs, parameters, and execution result.

---

## 9. Validation Engine

Initial validation categories:

* file integrity;
* data quality;
* metadata;
* documentation;
* privacy;
* package completeness.

Finding sources:

```text
deterministic rule
AI analysis
institutional policy
human review
repository requirement
```

Severity levels:

```text
critical
high
medium
low
informational
```

A dataset cannot be marked repository-ready when:

* an unresolved critical issue exists;
* a high-risk privacy issue remains unresolved;
* required metadata is missing;
* checksum generation fails;
* validation fails;
* final human approval is missing.

Deterministic rules establish facts, AI interprets ambiguity, and humans make consequential decisions.

---

## 10. Final Package

The generated package may contain:

```text
data/
README.md
data-dictionary.csv
metadata.json
file-manifest.json
checksums.sha256
validation-report.json
provenance.json
```

Users must be able to download the package as a ZIP archive.

---

## 11. Repository Connectors

Publishing should use a generic connector interface.

Initial destinations:

* package download;
* iRODS.

The iRODS connector should support:

* authentication;
* collection creation;
* file upload;
* AVU metadata;
* checksum verification;
* publication error reporting.

Additional repository connectors can be added later without changing the core stewardship workflow.

---

## 12. Core Data Model

Initial entities:

```text
users
organizations
workspaces
workspace_members
dataset_versions
files
file_profiles
findings
recommendations
decisions
remediation_actions
validation_runs
generated_documents
repository_connections
publication_jobs
audit_events
```

Detailed columns and relationships should be finalized during implementation.

---

## 13. Security

DataQuay must:

* encrypt data in transit;
* protect repository credentials;
* isolate access by workspace;
* preserve immutable original files;
* avoid logging raw sensitive values;
* validate uploaded file types;
* never execute uploaded files;
* record important access and modification events;
* support secure file deletion.

---

## 14. MVP Scope

The initial implementation should support:

* dataset workspaces;
* ZIP upload;
* CSV, Excel, JSON, Markdown, and text inspection;
* deterministic profiling;
* privacy pattern scanning;
* structured AI recommendations;
* human approval;
* limited remediation;
* validation;
* README and data-dictionary generation;
* ZIP package export;
* basic iRODS publishing;
* audit trail.

The initial implementation does not require:

* Kubernetes;
* vector databases;
* unrestricted multi-agent workflows;
* multiple repository connectors;
* large-scale distributed processing;
* specialized scientific binary formats.

---

## 15. Technical Principles

> Workflow controls the lifecycle.

> Pipelines perform deterministic processing.

> AI handles ambiguity and proposes actions.

> Humans approve consequential decisions.

> Validation determines readiness.

> Repository connectors handle final delivery.
