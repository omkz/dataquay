# DataQuay — UX Specification

## 1. UX Objective

DataQuay should help researchers and data stewards prepare research datasets without requiring deep technical knowledge.

The interface must make three things clear:

1. What issues were found.
2. Why they matter.
3. What changes will be applied after approval.

AI-generated recommendations must be clearly labeled and supported by evidence.

---

## 2. Primary User Flow

```text
Create workspace
→ Upload dataset
→ Inspect files
→ Review issues
→ Approve remediation
→ Apply changes
→ Validate results
→ Review final package
→ Download or publish
```

---

## 3. Navigation

### Main Navigation

* Workspaces
* Repository Connections
* Settings

### Workspace Navigation

* Overview
* Files
* Issues
* Remediation
* Validation
* Package
* Audit Trail

---

## 4. Core Screens

### 4.1 Workspaces

Shows all dataset workspaces.

Each workspace displays:

* dataset name;
* owner;
* current workflow status;
* readiness state;
* unresolved critical issues;
* last activity.

Primary action:

**New Dataset**

---

### 4.2 New Dataset

Users provide:

* dataset name;
* project description;
* research domain;
* dataset owner;
* folder or ZIP file.

Primary action:

**Upload and Inspect**

Repository destination can be selected later.

---

### 4.3 Inspection Progress

Shows the progress of:

```text
File discovery
→ Data profiling
→ Documentation checks
→ Privacy scanning
→ Recommendation generation
```

Users should be able to leave the page while processing continues.

Failed stages must show a clear retry option.

---

### 4.4 Dataset Overview

Provides a summary of:

* file count and formats;
* issue count by severity;
* metadata completeness;
* documentation completeness;
* probable privacy risks;
* current readiness state.

Primary actions:

* **Review Issues**
* **View Files**

---

### 4.5 Files

Displays the dataset folder structure and file inventory.

For each file, show:

* name;
* format;
* probable role;
* size;
* checksum;
* inspection status;
* related issues.

For tabular files, users can view column profiles and sample values.

Original files must remain read-only.

---

### 4.6 Issues

Displays detected issues with filters for:

* severity;
* category;
* file;
* status.

Each issue must show:

* title;
* explanation;
* severity;
* confidence;
* affected resource;
* evidence;
* detection source;
* recommended action.

Detection sources:

```text
Deterministic Rule
AI Analysis
Institutional Policy
```

Available decisions:

* Approve
* Modify
* Reject
* Accept Risk
* Request Clarification

---

### 4.7 Remediation Plan

Shows all approved changes before execution.

Each action displays:

* source issue;
* planned change;
* affected files;
* risk level;
* approval status;
* expected result.

Primary action:

**Apply Approved Changes**

The interface must clearly state that changes are applied to a working copy and that original files remain unchanged.

---

### 4.8 Validation Results

Compares the original and remediated dataset.

Show:

* resolved issues;
* remaining issues;
* failed checks;
* warnings;
* publication blockers;
* readiness state.

Example:

```text
Before: Needs Review
After: Repository Ready
```

Primary actions:

* **Return to Issues**
* **Review Package**

---

### 4.9 Final Package

Displays the files included in the final package:

* validated data files;
* README;
* data dictionary;
* metadata manifest;
* checksums;
* validation report;
* provenance record.

Primary actions:

* **Download Package**
* **Publish to Repository**

---

### 4.10 Publish

Users choose a configured destination.

Initial options:

* Download
* iRODS

Before publishing, show:

* destination;
* target path;
* included files;
* unresolved warnings;
* approval status.

Primary action:

**Approve and Publish**

---

### 4.11 Audit Trail

Shows a chronological history of:

* uploads;
* detected issues;
* AI recommendations;
* human decisions;
* file transformations;
* validation runs;
* exports;
* publishing actions.

Each event should identify the actor, action, timestamp, and affected resource.

---

## 5. Important Interface States

Major screens must support:

* empty state;
* loading state;
* partial results;
* success state;
* recoverable failure;
* permission denied;
* approval required.

Long-running processes must not block navigation.

---

## 6. Trust and Safety Principles

DataQuay must:

* label AI-generated content;
* show evidence behind recommendations;
* separate findings from proposed actions;
* warn before high-impact changes;
* require approval before modifying data;
* preserve original files;
* show critical blockers separately from readiness scores;
* never publish automatically.

---

## 7. MVP Screen List

1. Workspaces
2. New Dataset
3. Inspection Progress
4. Dataset Overview
5. Files
6. Issues
7. Remediation Plan
8. Validation Results
9. Final Package
10. Publish
11. Audit Trail
