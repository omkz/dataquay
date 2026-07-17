export type ReadinessStatus = "not_ready" | "needs_review" | "ready";

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
  readiness: {
    total_finding_count: number;
    finding_counts_by_severity: Record<string, number>;
    finding_counts_by_type: Record<string, number>;
    blocker_count: number;
    human_review_required: boolean;
    status: ReadinessStatus;
  };
  files: InspectedFile[];
  findings: InspectionFinding[];
};

export type RemediationRecommendation = {
  related_finding: {
    type: string;
    file: string;
    affected_column: string | null;
  };
  short_title: string;
  rationale: string;
  proposed_action: string;
  confidence: number;
  human_approval_required: boolean;
};

export type RecommendationActionState = {
  status: "idle" | "success" | "configuration_error" | "error";
  recommendations: RemediationRecommendation[];
  generation: number;
  message?: string;
};

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
  const backendUrl = getBackendUrl();

  try {
    const response = await fetch(`${backendUrl}/api/inspect/sample-dataset`, {
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
      typeof candidate.human_approval_required === "boolean",
  );
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
