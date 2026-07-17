"use server";

import {
  getBackendUrl,
  isDatasetValidationResult,
  isPackageGenerationResult,
  isRemediationApplyResponse,
  isRemediationPreviewResponse,
  type DatasetValidationResult,
  type PackageGenerationResult,
  type RemediationApplyResponse,
  type RemediationPreviewResponse,
  type RemediationRecommendation,
  type WorkflowActionResult,
} from "@/lib/dataquay";

export async function previewApprovedRemediation(
  approvedRecommendations: RemediationRecommendation[],
  datasetId?: string,
): Promise<WorkflowActionResult<RemediationPreviewResponse>> {
  if (approvedRecommendations.length === 0) {
    return prerequisiteError(
      "Approve at least one recommendation before previewing remediation.",
    );
  }
  return postWorkflowEndpoint(
    workflowPath(datasetId, "/api/remediate/sample-dataset/preview", "remediate", "preview"),
    { approved_recommendations: approvedRecommendations },
    isRemediationPreviewResponse,
    "remediation preview",
  );
}

export async function applyApprovedRemediation(
  approvedRecommendations: RemediationRecommendation[],
  datasetId?: string,
): Promise<WorkflowActionResult<RemediationApplyResponse>> {
  if (approvedRecommendations.length === 0) {
    return prerequisiteError(
      "Approve and preview at least one recommendation before applying remediation.",
    );
  }
  return postWorkflowEndpoint(
    workflowPath(datasetId, "/api/remediate/sample-dataset/apply", "remediate", "apply"),
    { approved_recommendations: approvedRecommendations },
    isRemediationApplyResponse,
    "remediation apply",
  );
}

export async function validateAppliedRemediation(datasetId?: string): Promise<
  WorkflowActionResult<DatasetValidationResult>
> {
  return postWorkflowEndpoint(
    workflowPath(datasetId, "/api/validate/sample-dataset", "validate"),
    undefined,
    isDatasetValidationResult,
    "validation",
  );
}

export async function generateFinalPackage(datasetId?: string): Promise<
  WorkflowActionResult<PackageGenerationResult>
> {
  return postWorkflowEndpoint(
    workflowPath(datasetId, "/api/package/sample-dataset", "package"),
    undefined,
    isPackageGenerationResult,
    "package generation",
  );
}

function workflowPath(
  datasetId: string | undefined,
  samplePath: string,
  resource: "remediate" | "validate" | "package",
  operation?: "preview" | "apply",
) {
  if (!datasetId) return samplePath;
  const base = `/api/${resource}/datasets/${encodeURIComponent(datasetId)}`;
  return operation ? `${base}/${operation}` : base;
}

async function postWorkflowEndpoint<T>(
  path: string,
  body: object | undefined,
  validator: (value: unknown) => value is T,
  label: string,
): Promise<WorkflowActionResult<T>> {
  try {
    const response = await fetch(`${getBackendUrl()}${path}`, {
      method: "POST",
      cache: "no-store",
      headers: {
        Accept: "application/json",
        ...(body ? { "Content-Type": "application/json" } : {}),
      },
      ...(body ? { body: JSON.stringify(body) } : {}),
    });
    const payload: unknown = await readJsonResponse(response);

    if (!response.ok) {
      return {
        ok: false,
        prerequisite: response.status === 404 || response.status === 409,
        message: extractBackendError(
          payload,
          `The ${label} service returned HTTP ${response.status}.`,
        ),
      };
    }
    if (!validator(payload)) {
      return {
        ok: false,
        prerequisite: false,
        message: `The ${label} service returned an unexpected response. Check that the frontend and backend versions match.`,
      };
    }
    return { ok: true, data: payload };
  } catch {
    return {
      ok: false,
      prerequisite: false,
      message: `DataQuay could not reach the ${label} service. Confirm that the backend is running and try again.`,
    };
  }
}

async function readJsonResponse(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function extractBackendError(payload: unknown, fallback: string) {
  if (
    payload &&
    typeof payload === "object" &&
    "detail" in payload &&
    typeof payload.detail === "string"
  ) {
    return payload.detail;
  }
  return fallback;
}

function prerequisiteError(message: string) {
  return { ok: false, prerequisite: true, message } as const;
}
