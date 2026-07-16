# DataQuay — Product Requirements Document

## 1. Product Overview

DataQuay is an AI-assisted data stewardship platform that helps research teams prepare datasets for sharing, preservation, and repository publication.

It inspects uploaded datasets, identifies quality, metadata, documentation, privacy, and file-organization issues, then creates an evidence-based remediation plan for human review.

**Tagline:**
Turn messy research data into trusted, repository-ready datasets.

---

## 2. Problem

Research datasets are often submitted with:

* incomplete metadata;
* missing or unclear documentation;
* inconsistent file and column names;
* undocumented values or codes;
* data quality problems;
* potentially sensitive information;
* unclear relationships between files.

Researchers may understand the scientific context but not repository, metadata, privacy, or preservation requirements.

Data stewards must therefore inspect datasets manually, request clarification, recommend corrections, validate the results, and prepare the final package. This process is slow, repetitive, and difficult to standardize.

---

## 3. Target Users

### Primary User

**Research data stewards** working at universities, libraries, research institutes, or institutional repositories.

### Supporting Users

* researchers;
* research assistants;
* repository managers;
* research data office staff.

### Initial Market

University research teams working with small-to-medium structured datasets, particularly CSV, Excel, and JSON files.

---

## 4. Product Goals

DataQuay should:

1. Reduce repetitive dataset inspection work.
2. Detect important quality, metadata, privacy, and documentation issues.
3. Provide clear recommendations supported by evidence.
4. Keep humans in control of important decisions.
5. Produce validated and documented dataset packages.
6. Maintain a complete audit trail.
7. Support export and repository publishing.

---

## 5. Core User Flow

```text
Create workspace
→ Upload dataset
→ Inspect files
→ Review detected issues
→ Review remediation plan
→ Approve or reject actions
→ Apply approved changes
→ Validate dataset
→ Generate documentation
→ Export or publish
```

---

## 6. Core Features

### 6.1 Dataset Upload

Users can upload a folder or ZIP file containing:

* CSV;
* Excel;
* JSON;
* README or Markdown files;
* supporting documentation.

Original files must remain unchanged.

### 6.2 Dataset Inspection

The system should:

* discover and classify files;
* profile tabular data;
* identify schemas and data types;
* detect missing values and duplicates;
* detect inconsistent formats;
* identify relationships between files;
* calculate checksums.

### 6.3 Issue Detection

DataQuay should detect issues related to:

* data quality;
* missing metadata;
* incomplete documentation;
* inconsistent naming;
* unclear file structure;
* sensitive or personally identifiable information;
* unsupported or unstable file formats;
* file integrity.

### 6.4 Data Steward Agent

The AI agent should:

* interpret inspection results;
* explain why an issue matters;
* identify likely file relationships;
* propose remediation actions;
* generate clarification questions;
* draft metadata and documentation.

Every recommendation must include:

* issue;
* severity;
* confidence;
* evidence;
* affected files or columns;
* recommended action.

### 6.5 Human Review

Users must be able to:

* approve recommendations;
* reject recommendations;
* modify proposed actions;
* request clarification;
* accept documented risks;
* add notes.

DataQuay must not perform high-impact changes without approval.

### 6.6 Remediation

Approved actions may include:

* renaming files;
* restructuring folders;
* normalizing dates;
* standardizing missing values;
* masking approved sensitive fields;
* generating documentation;
* generating checksums and manifests.

Changes must be applied to a new working version, not the original files.

### 6.7 Validation

After remediation, DataQuay should rerun relevant checks and show:

* resolved issues;
* remaining issues;
* warnings;
* validation failures;
* readiness status;
* before-and-after comparison.

Possible readiness states:

```text
Not Ready
Needs Review
Conditionally Ready
Repository Ready
Published
```

### 6.8 Documentation Generation

DataQuay should generate editable drafts for:

* README;
* data dictionary;
* metadata manifest;
* file inventory;
* validation report;
* provenance record.

### 6.9 Export and Publishing

Users should be able to:

* download the final dataset package;
* publish an approved package to iRODS;
* verify uploaded checksums;
* review publishing status and errors.

### 6.10 Audit Trail

The system must record:

* uploads;
* detected issues;
* AI recommendations;
* user decisions;
* transformations;
* validation results;
* generated files;
* exports and publishing actions.

---

## 7. MVP Scope

### Included

* dataset workspaces;
* folder or ZIP upload;
* CSV, Excel, and JSON inspection;
* tabular profiling;
* metadata and documentation checks;
* probable sensitive-data detection;
* AI-assisted recommendations;
* human approval;
* remediation plan;
* README generation;
* data dictionary generation;
* validation;
* final package export;
* audit trail;
* basic iRODS publishing.

### Out of Scope

* medical imaging;
* genomic datasets;
* petabyte-scale processing;
* arbitrary scientific binary formats;
* fully autonomous publication;
* legal or regulatory compliance certification;
* scientific analysis;
* interpretation of research conclusions;
* automatic execution of uploaded code.

---

## 8. Success Metrics

DataQuay should measure:

* time from upload to first inspection result;
* reduction in manual review time;
* percentage of datasets reaching validated status;
* increase in metadata completeness;
* reduction in unresolved critical issues;
* percentage of recommendations accepted by data stewards;
* percentage of packages accepted by repositories without further corrections;
* number of unauthorized modifications or publications.

---

## 9. Key Risks

### Incorrect AI Recommendations

Mitigation:

* show evidence and confidence;
* require human approval;
* preserve original files;
* validate outcomes using deterministic rules.

### Sensitive Data Detection Errors

Mitigation:

* combine rule-based detection with AI analysis;
* require human review;
* never claim guaranteed privacy compliance.

### Missing Research Context

Mitigation:

* generate clarification questions;
* label assumptions and unknowns;
* block final readiness when critical information is missing.

### Different Institutional Requirements

Mitigation:

* separate universal checks from configurable institutional policies.

---

## 10. Product Principle

> Workflow controls the process, pipelines perform deterministic checks, AI handles ambiguity, and humans make final decisions.
