export type ReadinessStatus = "not_ready" | "needs_review" | "ready";

export type ReadinessSummary = {
  total_finding_count: number;
  finding_counts_by_severity: Record<string, number>;
  finding_counts_by_type: Record<string, number>;
  blocker_count: number;
  human_review_required: boolean;
  status: ReadinessStatus;
};

export type CsvProfile = {
  file_name: string;
  row_count: number;
  column_count: number;
  column_names: string[];
  data_types: Record<string, string>;
  missing_value_counts: Record<string, number>;
  duplicate_row_count: number;
};

export type InspectedFile = {
  file_name: string;
  relative_path: string;
  extension: string;
  size_bytes: number;
  csv_profile: CsvProfile | null;
};

export type InspectionFinding = {
  type: string;
  severity: string;
  file: string;
  affected_column: string | null;
  evidence: Record<string, string | number | string[]>;
  message: string;
};

export type DatasetInspection = {
  summary: {
    dataset_name: string;
    total_file_count: number;
    csv_file_count: number;
    total_size_bytes: number;
  };
  readiness: ReadinessSummary;
  files: InspectedFile[];
  findings: InspectionFinding[];
};

export type DatasetUploadResponse = {
  dataset_id: string;
  file_name: string;
  dataset_name: string;
  archive_size_bytes: number;
  archive_checksum_sha256: string;
  extracted_file_count: number;
  extracted_size_bytes: number;
  inspection_url: string;
};

export type AuditAction =
  | "upload"
  | "inspection"
  | "clarification_review"
  | "clarification_response"
  | "recommendation_generation"
  | "remediation_preview"
  | "remediation_apply"
  | "validation"
  | "package_generation"
  | "package_download";

export type AuditEvent = {
  timestamp: string;
  action: AuditAction;
  status: "success" | "failure";
  dataset_id: string;
  summary: string;
};

export type DatasetAuditTrail = {
  dataset_id: string;
  events: AuditEvent[];
};

export type FindingReference = {
  type: string;
  file: string;
  affected_column: string | null;
};

export type RemediationRecommendation = {
  related_finding: FindingReference;
  short_title: string;
  rationale: string;
  proposed_action: string;
  confidence: number;
  human_approval_required: boolean;
  assumptions: string[];
};

export type ClarificationStatus = "unanswered" | "answered" | "deferred";

export type ClarificationQuestion = {
  question_id: string;
  related_finding: FindingReference;
  question: string;
  why_this_matters: string;
  status: ClarificationStatus;
  answer: string | null;
  updated_at: string | null;
};

export type DatasetClarifications = {
  dataset_id: string;
  summary: {
    total_count: number;
    answered_count: number;
    deferred_count: number;
    unanswered_count: number;
  };
  questions: ClarificationQuestion[];
};

export type ClarificationActionResult =
  | { ok: true; data: DatasetClarifications }
  | { ok: false; message: string };

export type RecommendationActionState = {
  status: "idle" | "success" | "configuration_error" | "error";
  recommendations: RemediationRecommendation[];
  generation: number;
  message?: string;
};

export type RemediationAction = {
  related_finding: FindingReference;
  target_file: string;
  target_column: string | null;
  proposed_operation: string;
  can_apply_automatically: boolean;
  manual_review_reason: string | null;
  expected_result: string;
};

export type RemediationPreviewResponse = {
  actions: RemediationAction[];
};

export type RemediationActionResult = {
  action: RemediationAction;
  source_checksum_sha256: string;
  output_checksum_sha256: string | null;
  message: string;
};

export type FileChecksumRecord = {
  relative_path: string;
  source_checksum_sha256: string;
  output_checksum_sha256: string;
};

export type RemediationApplyResponse = {
  working_copy_directory: string;
  applied_actions: RemediationActionResult[];
  skipped_actions: RemediationActionResult[];
  failed_actions: RemediationActionResult[];
  file_checksums: FileChecksumRecord[];
};

export type FileChecksumVerification = {
  relative_path: string;
  expected_source_checksum_sha256: string | null;
  actual_source_checksum_sha256: string | null;
  source_checksum_verified: boolean;
  expected_output_checksum_sha256: string | null;
  actual_output_checksum_sha256: string | null;
  output_checksum_verified: boolean;
};

export type DatasetValidationResult = {
  resolved_findings: InspectionFinding[];
  remaining_findings: InspectionFinding[];
  checksum_verifications: FileChecksumVerification[];
  source_checksums_verified: boolean;
  output_checksums_verified: boolean;
  original_files_unchanged: boolean;
  readiness: ReadinessSummary;
};

export type PackageFileEntry = {
  relative_path: string;
  size_bytes: number;
  checksum_sha256: string;
};

export type PackageGenerationResult = {
  dataset_name: string;
  zip_file_name: string;
  zip_size_bytes: number;
  zip_checksum_sha256: string;
  download_url: string;
  files: PackageFileEntry[];
  readiness: ReadinessSummary;
};

export type WorkflowActionResult<T> =
  | { ok: true; data: T }
  | { ok: false; message: string; prerequisite: boolean };

export type InspectionResult =
  | { ok: true; data: DatasetInspection }
  | { ok: false; message: string };

const DEFAULT_BACKEND_URL = "http://localhost:8000";

export function getBackendUrl() {
  return (process.env.DATAQUAY_BACKEND_URL || DEFAULT_BACKEND_URL).replace(
    /\/$/,
    "",
  );
}

export async function getSampleDatasetInspection(): Promise<InspectionResult> {
  return getDatasetInspection("/api/inspect/sample-dataset");
}

export async function getUploadedDatasetInspection(
  datasetId: string,
): Promise<InspectionResult> {
  if (!isDatasetIdentifier(datasetId)) {
    return {
      ok: false,
      message:
        "The dataset identifier is invalid. Upload the dataset again to create a new workspace.",
    };
  }
  return getDatasetInspection(
    `/api/inspect/datasets/${encodeURIComponent(datasetId)}`,
  );
}

export function isDatasetUploadResponse(
  value: unknown,
): value is DatasetUploadResponse {
  return Boolean(
    isRecord(value) &&
      typeof value.dataset_id === "string" &&
      isDatasetIdentifier(value.dataset_id) &&
      typeof value.file_name === "string" &&
      typeof value.dataset_name === "string" &&
      typeof value.archive_size_bytes === "number" &&
      typeof value.archive_checksum_sha256 === "string" &&
      typeof value.extracted_file_count === "number" &&
      typeof value.extracted_size_bytes === "number" &&
      typeof value.inspection_url === "string",
  );
}

export function isDatasetAuditTrail(
  value: unknown,
): value is DatasetAuditTrail {
  return Boolean(
    isRecord(value) &&
      typeof value.dataset_id === "string" &&
      isDatasetIdentifier(value.dataset_id) &&
      Array.isArray(value.events) &&
      value.events.every(isAuditEvent),
  );
}

async function getDatasetInspection(path: string): Promise<InspectionResult> {
  const backendUrl = getBackendUrl();

  try {
    const response = await fetch(`${backendUrl}${path}`, {
      cache: "no-store",
      headers: { Accept: "application/json" },
    });

    if (!response.ok) {
      return {
        ok: false,
        message: `The inspection API returned HTTP ${response.status}. Confirm that the backend is healthy and try again.`,
      };
    }

    const payload: unknown = await response.json();
    if (!isDatasetInspection(payload)) {
      return {
        ok: false,
        message:
          "The inspection API returned an unexpected response. Check that the frontend and backend versions match.",
      };
    }

    return { ok: true, data: payload };
  } catch {
    return {
      ok: false,
      message:
        "DataQuay could not reach the inspection API. Confirm that the backend is running and the backend URL is correct.",
    };
  }
}

export function isDatasetIdentifier(value: string) {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(
    value,
  );
}

function isAuditEvent(value: unknown): value is AuditEvent {
  if (!isRecord(value)) return false;
  return (
    typeof value.timestamp === "string" &&
    auditActions.has(value.action as AuditAction) &&
    (value.status === "success" || value.status === "failure") &&
    typeof value.dataset_id === "string" &&
    isDatasetIdentifier(value.dataset_id) &&
    typeof value.summary === "string"
  );
}

const auditActions = new Set<AuditAction>([
  "upload",
  "inspection",
  "clarification_review",
  "clarification_response",
  "recommendation_generation",
  "remediation_preview",
  "remediation_apply",
  "validation",
  "package_generation",
  "package_download",
]);

export function isRecommendationResponse(
  value: unknown,
): value is { recommendations: RemediationRecommendation[] } {
  if (!value || typeof value !== "object") {
    return false;
  }

  const candidate = value as { recommendations?: unknown };
  return (
    Array.isArray(candidate.recommendations) &&
    candidate.recommendations.every(isRemediationRecommendation)
  );
}

export function isDatasetClarifications(
  value: unknown,
): value is DatasetClarifications {
  if (!isRecord(value) || !isRecord(value.summary)) return false;
  return (
    typeof value.dataset_id === "string" &&
    isDatasetIdentifier(value.dataset_id) &&
    typeof value.summary.total_count === "number" &&
    typeof value.summary.answered_count === "number" &&
    typeof value.summary.deferred_count === "number" &&
    typeof value.summary.unanswered_count === "number" &&
    Array.isArray(value.questions) &&
    value.questions.every(isClarificationQuestion)
  );
}

export function isRemediationPreviewResponse(
  value: unknown,
): value is RemediationPreviewResponse {
  if (!isRecord(value) || !Array.isArray(value.actions)) {
    return false;
  }
  return value.actions.every(isRemediationAction);
}

export function isRemediationApplyResponse(
  value: unknown,
): value is RemediationApplyResponse {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.working_copy_directory === "string" &&
    isActionResultArray(value.applied_actions) &&
    isActionResultArray(value.skipped_actions) &&
    isActionResultArray(value.failed_actions) &&
    Array.isArray(value.file_checksums) &&
    value.file_checksums.every(isFileChecksumRecord)
  );
}

export function isDatasetValidationResult(
  value: unknown,
): value is DatasetValidationResult {
  if (!isRecord(value)) {
    return false;
  }
  return (
    Array.isArray(value.resolved_findings) &&
    value.resolved_findings.every(isInspectionFinding) &&
    Array.isArray(value.remaining_findings) &&
    value.remaining_findings.every(isInspectionFinding) &&
    Array.isArray(value.checksum_verifications) &&
    value.checksum_verifications.every(isChecksumVerification) &&
    typeof value.source_checksums_verified === "boolean" &&
    typeof value.output_checksums_verified === "boolean" &&
    typeof value.original_files_unchanged === "boolean" &&
    isReadinessSummary(value.readiness)
  );
}

export function isPackageGenerationResult(
  value: unknown,
): value is PackageGenerationResult {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.dataset_name === "string" &&
    typeof value.zip_file_name === "string" &&
    typeof value.zip_size_bytes === "number" &&
    typeof value.zip_checksum_sha256 === "string" &&
    typeof value.download_url === "string" &&
    Array.isArray(value.files) &&
    value.files.every(isPackageFileEntry) &&
    isReadinessSummary(value.readiness)
  );
}

function isRemediationRecommendation(
  value: unknown,
): value is RemediationRecommendation {
  if (!value || typeof value !== "object") {
    return false;
  }

  const candidate = value as Partial<RemediationRecommendation>;
  const finding = candidate.related_finding;
  return Boolean(
    finding &&
      typeof finding.type === "string" &&
      typeof finding.file === "string" &&
      (typeof finding.affected_column === "string" ||
        finding.affected_column === null) &&
      typeof candidate.short_title === "string" &&
      typeof candidate.rationale === "string" &&
      typeof candidate.proposed_action === "string" &&
      typeof candidate.confidence === "number" &&
      typeof candidate.human_approval_required === "boolean" &&
      Array.isArray(candidate.assumptions) &&
      candidate.assumptions.every((assumption) => typeof assumption === "string"),
  );
}

function isClarificationQuestion(
  value: unknown,
): value is ClarificationQuestion {
  if (!isRecord(value)) return false;
  return (
    typeof value.question_id === "string" &&
    isFindingReference(value.related_finding) &&
    typeof value.question === "string" &&
    typeof value.why_this_matters === "string" &&
    (value.status === "unanswered" ||
      value.status === "answered" ||
      value.status === "deferred") &&
    (typeof value.answer === "string" || value.answer === null) &&
    (typeof value.updated_at === "string" || value.updated_at === null)
  );
}

function isRemediationAction(value: unknown): value is RemediationAction {
  if (!isRecord(value)) {
    return false;
  }
  return Boolean(
    isFindingReference(value.related_finding) &&
      typeof value.target_file === "string" &&
      (typeof value.target_column === "string" || value.target_column === null) &&
      typeof value.proposed_operation === "string" &&
      typeof value.can_apply_automatically === "boolean" &&
      (typeof value.manual_review_reason === "string" ||
        value.manual_review_reason === null) &&
      typeof value.expected_result === "string",
  );
}

function isActionResultArray(value: unknown): value is RemediationActionResult[] {
  return Array.isArray(value) && value.every(isRemediationActionResult);
}

function isRemediationActionResult(
  value: unknown,
): value is RemediationActionResult {
  if (!isRecord(value)) {
    return false;
  }
  return (
    isRemediationAction(value.action) &&
    typeof value.source_checksum_sha256 === "string" &&
    (typeof value.output_checksum_sha256 === "string" ||
      value.output_checksum_sha256 === null) &&
    typeof value.message === "string"
  );
}

function isFileChecksumRecord(value: unknown): value is FileChecksumRecord {
  return Boolean(
    isRecord(value) &&
      typeof value.relative_path === "string" &&
      typeof value.source_checksum_sha256 === "string" &&
      typeof value.output_checksum_sha256 === "string",
  );
}

function isChecksumVerification(
  value: unknown,
): value is FileChecksumVerification {
  return Boolean(
    isRecord(value) &&
      typeof value.relative_path === "string" &&
      typeof value.source_checksum_verified === "boolean" &&
      typeof value.output_checksum_verified === "boolean",
  );
}

function isPackageFileEntry(value: unknown): value is PackageFileEntry {
  return Boolean(
    isRecord(value) &&
      typeof value.relative_path === "string" &&
      typeof value.size_bytes === "number" &&
      typeof value.checksum_sha256 === "string",
  );
}

function isFindingReference(value: unknown): value is FindingReference {
  return Boolean(
    isRecord(value) &&
      typeof value.type === "string" &&
      typeof value.file === "string" &&
      (typeof value.affected_column === "string" ||
        value.affected_column === null),
  );
}

function isInspectionFinding(value: unknown): value is InspectionFinding {
  return Boolean(
    isRecord(value) &&
      typeof value.type === "string" &&
      typeof value.severity === "string" &&
      typeof value.file === "string" &&
      (typeof value.affected_column === "string" ||
        value.affected_column === null) &&
      isRecord(value.evidence) &&
      typeof value.message === "string",
  );
}

function isReadinessSummary(value: unknown): value is ReadinessSummary {
  return Boolean(
    isRecord(value) &&
      typeof value.total_finding_count === "number" &&
      typeof value.blocker_count === "number" &&
      typeof value.human_review_required === "boolean" &&
      ["not_ready", "needs_review", "ready"].includes(String(value.status)) &&
      isRecord(value.finding_counts_by_severity) &&
      isRecord(value.finding_counts_by_type),
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object");
}

function isDatasetInspection(value: unknown): value is DatasetInspection {
  if (!value || typeof value !== "object") {
    return false;
  }

  const candidate = value as Partial<DatasetInspection>;
  return Boolean(
    candidate.summary &&
      candidate.readiness &&
      Array.isArray(candidate.files) &&
      Array.isArray(candidate.findings),
  );
}
