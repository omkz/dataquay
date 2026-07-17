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
): Promise<WorkflowActionResult<RemediationPreviewResponse>> {
  if (approvedRecommendations.length === 0) {
    return prerequisiteError(
      "Approve at least one recommendation before previewing remediation.",
    );
  }
  return postWorkflowEndpoint(
    "/api/remediate/sample-dataset/preview",
    { approved_recommendations: approvedRecommendations },
    isRemediationPreviewResponse,
    "remediation preview",
  );
}

export async function applyApprovedRemediation(
  approvedRecommendations: RemediationRecommendation[],
): Promise<WorkflowActionResult<RemediationApplyResponse>> {
  if (approvedRecommendations.length === 0) {
    return prerequisiteError(
      "Approve and preview at least one recommendation before applying remediation.",
    );
  }
  return postWorkflowEndpoint(
    "/api/remediate/sample-dataset/apply",
    { approved_recommendations: approvedRecommendations },
    isRemediationApplyResponse,
    "remediation apply",
  );
}

export async function validateAppliedRemediation(): Promise<
  WorkflowActionResult<DatasetValidationResult>
> {
  return postWorkflowEndpoint(
    "/api/validate/sample-dataset",
    undefined,
    isDatasetValidationResult,
    "validation",
  );
}

export async function generateFinalPackage(): Promise<
  WorkflowActionResult<PackageGenerationResult>
> {
  return postWorkflowEndpoint(
    "/api/package/sample-dataset",
    undefined,
    isPackageGenerationResult,
    "package generation",
  );
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
