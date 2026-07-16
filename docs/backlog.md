Berikut **MVP Product Backlog** yang bisa disimpan sebagai `docs/backlog.md`.

# DataQuay — MVP Product Backlog

## Backlog Conventions

### Priority

* **P0** — Required for the core MVP workflow
* **P1** — Important for a usable product
* **P2** — Useful after the core workflow is stable

### Status

```text
Planned
In Progress
Blocked
In Review
Done
```

---

# Epic 1 — Project Foundation

## DQ-001: Initialize Application Structure

**Priority:** P0
**Status:** Planned

Create the initial frontend, backend, worker, database, and local infrastructure structure.

### Acceptance Criteria

* Next.js frontend runs locally.
* FastAPI backend runs locally.
* PostgreSQL is available.
* MinIO or another S3-compatible storage service is available.
* Temporal server and worker can start.
* All services run through Docker Compose.
* Environment variables are documented in `.env.example`.

---

## DQ-002: Add Database Migrations

**Priority:** P0
**Status:** Planned

Configure SQLAlchemy and Alembic for database models and migrations.

### Acceptance Criteria

* Initial migration can be applied successfully.
* Migration rollback works.
* Database configuration is environment-based.
* Application startup does not create tables automatically.

---

## DQ-003: Implement Basic Authentication

**Priority:** P1
**Status:** Planned

Allow users to sign in and access their own workspaces.

### Acceptance Criteria

* Authenticated users can access the application.
* Unauthenticated users are redirected to sign in.
* API endpoints verify user identity.
* Workspace access is restricted to authorized users.

---

# Epic 2 — Dataset Workspaces

## DQ-010: Create Dataset Workspace

**Priority:** P0
**Status:** Planned

As a researcher, I want to create a workspace so that I can manage one dataset stewardship process.

### Acceptance Criteria

* User can provide a dataset name.
* User can provide a project description.
* User can select a research domain.
* Workspace is created with `draft` status.
* Workspace appears on the workspaces page.
* Workspace creation is recorded in the audit trail.

### Dependencies

* DQ-002
* DQ-003

---

## DQ-011: Display Workspace Overview

**Priority:** P0
**Status:** Planned

Display the current state of a dataset workspace.

### Acceptance Criteria

* Overview shows workflow status.
* Overview shows file count.
* Overview shows issue count by severity.
* Overview shows current readiness state.
* Overview shows recent activity.
* Empty states are displayed before a dataset is uploaded.

---

# Epic 3 — Dataset Upload and Storage

## DQ-020: Upload Dataset Package

**Priority:** P0
**Status:** Planned

As a researcher, I want to upload a ZIP package containing research files.

### Acceptance Criteria

* User can upload a ZIP file.
* Upload size and content type are validated.
* File is stored in object storage.
* Upload progress is visible.
* Original package checksum is generated.
* Original package remains immutable.
* Failed uploads show a retry option.

### Dependencies

* DQ-010

---

## DQ-021: Safely Extract Dataset Package

**Priority:** P0
**Status:** Planned

Extract the uploaded package in an isolated worker.

### Acceptance Criteria

* ZIP contents are extracted outside the API process.
* Path traversal attempts are rejected.
* Executable files are flagged or rejected.
* Corrupted archives produce a clear failure.
* Extraction does not modify the original archive.
* Workflow status is updated.

---

## DQ-022: Build File Inventory

**Priority:** P0
**Status:** Planned

Create a structured inventory of all extracted files.

### Acceptance Criteria

* Every file has a stored path, name, size, format, and checksum.
* Unsupported files are retained but marked uninspected.
* Duplicate checksums are detected.
* File inventory is visible in the UI.
* Folder hierarchy is preserved.

---

# Epic 4 — Inspection Pipeline

## DQ-030: Detect File Formats

**Priority:** P0
**Status:** Planned

Identify supported and unsupported file formats.

### Acceptance Criteria

* CSV, Excel, JSON, Markdown, and text files are recognized.
* File type detection does not rely only on the extension.
* Extension and detected-content conflicts create findings.
* Unsupported files do not stop the entire inspection.

---

## DQ-031: Profile Tabular Files

**Priority:** P0
**Status:** Planned

Generate profiles for supported tabular files.

### Acceptance Criteria

For each supported file, DataQuay records:

* row count;
* column count;
* inferred data types;
* missing-value counts;
* unique-value counts;
* duplicate row count;
* sample values;
* probable identifier columns.

Profiling errors must be isolated to the affected file.

---

## DQ-032: Detect Data-Quality Issues

**Priority:** P0
**Status:** Planned

Generate deterministic findings for common data-quality problems.

### Acceptance Criteria

The system detects:

* empty files;
* empty columns;
* duplicate rows;
* duplicate identifiers;
* inconsistent data types;
* malformed dates;
* inconsistent missing-value markers;
* leading and trailing whitespace.

Each finding includes severity, evidence, and affected resources.

---

## DQ-033: Check Documentation and Metadata

**Priority:** P0
**Status:** Planned

Check whether the dataset package contains sufficient documentation.

### Acceptance Criteria

The system checks for:

* README presence;
* data-dictionary presence;
* dataset title;
* dataset description;
* creator information;
* contact information;
* license or access statement;
* descriptions for discovered data files.

Missing requirements create findings.

---

## DQ-034: Scan Probable Sensitive Information

**Priority:** P0
**Status:** Planned

Detect probable sensitive or personally identifiable information.

### Acceptance Criteria

The system scans for:

* email addresses;
* phone numbers;
* IP addresses;
* personal identifiers;
* physical addresses;
* precise coordinates;
* probable names or sensitive free-text content.

Findings show only the minimum evidence necessary for review.

All privacy findings require human review.

---

# Epic 5 — Data Steward Agent

## DQ-040: Configure Structured AI Provider

**Priority:** P0
**Status:** Planned

Create a configurable AI service using PydanticAI.

### Acceptance Criteria

* Provider and model are configured through environment variables.
* Agent output is validated through Pydantic schemas.
* Invalid output can be retried.
* Provider, model, prompt version, and timestamp are recorded.
* Application logic does not hard-code one model name.

---

## DQ-041: Generate Steward Recommendations

**Priority:** P0
**Status:** Planned

Analyze inspection results and generate evidence-backed recommendations.

### Acceptance Criteria

Each recommendation includes:

* category;
* severity;
* confidence;
* explanation;
* evidence;
* affected resources;
* proposed action;
* approval requirement.

The agent must not modify files or approve recommendations.

---

## DQ-042: Generate Clarification Questions

**Priority:** P1
**Status:** Planned

Create questions when the dataset context is incomplete.

### Acceptance Criteria

* Questions reference a specific file, column, or issue.
* Researcher responses are stored.
* The affected finding can be re-evaluated.
* Assumptions remain visible until confirmed.

---

# Epic 6 — Issue Review and Approval

## DQ-050: Display Findings

**Priority:** P0
**Status:** Planned

Allow users to review deterministic, AI, and policy findings.

### Acceptance Criteria

Users can filter findings by:

* severity;
* category;
* file;
* source;
* status.

Each finding shows evidence and recommended action.

---

## DQ-051: Record Human Decisions

**Priority:** P0
**Status:** Planned

Allow data stewards to decide how findings should be handled.

### Acceptance Criteria

Users can:

* approve;
* modify;
* reject;
* accept risk;
* request clarification;
* add notes.

Every decision records the user, timestamp, affected recommendation, and optional explanation.

---

## DQ-052: Build Remediation Plan

**Priority:** P0
**Status:** Planned

Convert approved recommendations into executable remediation actions.

### Acceptance Criteria

* Only approved actions enter the remediation plan.
* Each action shows affected files and expected result.
* High-impact actions display a warning.
* Users can remove or modify actions before execution.
* Plan execution requires explicit confirmation.

---

# Epic 7 — Remediation Pipeline

## DQ-060: Create Working Dataset Version

**Priority:** P0
**Status:** Planned

Create a new dataset version before applying changes.

### Acceptance Criteria

* Original files remain immutable.
* Working files are stored separately.
* Working version references its source version.
* Version creation is recorded in the audit trail.

---

## DQ-061: Apply Approved Transformations

**Priority:** P0
**Status:** Planned

Execute supported remediation actions.

### Initial Actions

* rename files;
* reorganize folders;
* normalize dates;
* normalize missing-value markers;
* mask approved sensitive fields;
* generate checksums.

### Acceptance Criteria

* Only approved actions are executed.
* Each action records parameters and results.
* Failed actions do not silently pass.
* Individual failed actions can be retried.
* Input and output checksums are recorded.

---

# Epic 8 — Documentation Generation

## DQ-070: Generate README

**Priority:** P0
**Status:** Planned

Generate an editable README draft using dataset context and inspection results.

### Acceptance Criteria

README may include:

* dataset overview;
* creators;
* file structure;
* collection method;
* processing history;
* missing-value conventions;
* known limitations;
* access conditions;
* contact information.

AI-generated content is clearly labeled.

---

## DQ-071: Generate Data Dictionary

**Priority:** P0
**Status:** Planned

Generate an editable data dictionary for supported tabular files.

### Acceptance Criteria

The dictionary contains:

* file name;
* column name;
* inferred type;
* description;
* unit where known;
* allowed values where known;
* missing-value meaning;
* probable sensitivity.

Unknown descriptions are marked for review rather than invented.

---

## DQ-072: Generate Metadata Manifest

**Priority:** P1
**Status:** Planned

Generate a structured metadata document for the final package.

### Acceptance Criteria

* Metadata is editable.
* Required missing fields remain visible.
* Human-reviewed metadata is versioned.
* Metadata is included in final validation.

---

# Epic 9 — Validation

## DQ-080: Run Final Validation

**Priority:** P0
**Status:** Planned

Re-run applicable checks against the remediated dataset.

### Acceptance Criteria

Validation reports:

* resolved findings;
* unresolved findings;
* failed checks;
* warnings;
* privacy blockers;
* missing metadata;
* checksum failures;
* package-completeness status.

---

## DQ-081: Determine Readiness State

**Priority:** P0
**Status:** Planned

Assign an explainable readiness state.

### States

```text
Not Ready
Needs Review
Conditionally Ready
Repository Ready
Published
```

### Acceptance Criteria

* Open critical findings block repository readiness.
* Unresolved high-risk privacy findings block repository readiness.
* Missing required metadata blocks repository readiness.
* Readiness includes an explanation.
* Numerical scores never override blockers.

---

## DQ-082: Display Before-and-After Results

**Priority:** P1
**Status:** Planned

Show how the dataset changed after remediation.

### Acceptance Criteria

The UI compares:

* issue counts;
* metadata completeness;
* documentation completeness;
* privacy findings;
* validation status;
* readiness state.

---

# Epic 10 — Final Package

## DQ-090: Generate Repository-Ready Package

**Priority:** P0
**Status:** Planned

Create the final dataset package.

### Package Contents

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

### Acceptance Criteria

* Package contains the validated dataset version.
* File manifest matches package contents.
* Checksums are generated.
* Validation report is included.
* Provenance references source and working versions.
* Package generation requires human approval.

---

## DQ-091: Download Final Package

**Priority:** P0
**Status:** Planned

Allow authorized users to download the final ZIP package.

### Acceptance Criteria

* Download uses a secure signed URL.
* Downloaded package checksum can be verified.
* Download is recorded in the audit trail.

---

# Epic 11 — iRODS Publishing

## DQ-100: Configure iRODS Connection

**Priority:** P1
**Status:** Planned

Allow an administrator to configure an iRODS destination.

### Acceptance Criteria

* Credentials are encrypted.
* Connection can be tested.
* Connection errors are clearly reported.
* Raw credentials are never returned to the frontend.

---

## DQ-101: Publish Package to iRODS

**Priority:** P1
**Status:** Planned

Publish an approved final package to an iRODS collection.

### Acceptance Criteria

* User selects the target collection.
* Missing collections can be created.
* Package files are uploaded.
* Supported AVU metadata is attached.
* Uploaded checksums are verified.
* Partial failures are reported.
* Publication requires explicit approval.

---

# Epic 12 — Audit Trail

## DQ-110: Record Audit Events

**Priority:** P0
**Status:** Planned

Record important actions throughout the dataset lifecycle.

### Events Include

* workspace creation;
* uploads;
* inspection runs;
* generated findings;
* AI recommendations;
* human decisions;
* remediation actions;
* validation runs;
* document generation;
* package downloads;
* repository publishing;
* failures and retries.

---

## DQ-111: Display Audit Trail

**Priority:** P1
**Status:** Planned

Allow authorized users to review workspace history.

### Acceptance Criteria

Each event shows:

* actor;
* action;
* timestamp;
* affected resource;
* source type;
* relevant version references.

---

# Recommended Build Order

```text
1. Project Foundation
2. Dataset Workspaces
3. Upload and File Inventory
4. Inspection Pipeline
5. Data Steward Agent
6. Issue Review and Approval
7. Remediation Pipeline
8. Documentation Generation
9. Validation
10. Final Package Export
11. Audit Trail
12. iRODS Publishing
```

# MVP Completion Definition

The MVP is complete when a user can:

```text
Create workspace
→ Upload a research dataset
→ Inspect supported files
→ Review evidence-backed findings
→ Approve remediation
→ Apply changes to a working copy
→ Validate the result
→ Generate documentation
→ Download a repository-ready package
```

Basic iRODS publishing is the final MVP integration milestone after package download is stable.
