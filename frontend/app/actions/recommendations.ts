"use server";

import {
  getBackendApiError,
  isDatasetIdentifier,
  isRecommendationResponse,
  type RecommendationActionState,
} from "@/lib/dataquay";
import { authenticatedBackendFetch } from "@/lib/backend-fetch";

export async function generateRecommendations(
  previousState: RecommendationActionState,
  formData: FormData,
): Promise<RecommendationActionState> {
  const datasetIdValue = formData.get("dataset_id");
  const datasetId =
    typeof datasetIdValue === "string" && datasetIdValue
      ? datasetIdValue
      : undefined;
  if (datasetId && !isDatasetIdentifier(datasetId)) {
    return {
      status: "error",
      recommendations: [],
      generation: previousState.generation,
      message: "The uploaded dataset identifier is invalid. Upload it again to continue.",
    };
  }
  const recommendationPath = datasetId
    ? `/api/inspect/datasets/${encodeURIComponent(datasetId)}/recommendations`
    : "/api/inspect/sample-dataset/recommendations";

  try {
    const response = await authenticatedBackendFetch(recommendationPath, {
      method: "POST",
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
    const payload: unknown = await readJsonResponse(response);

    const backendError = getBackendApiError(payload);
    if (backendError?.code === "ai_not_configured") {
      return {
        status: "configuration_error",
        recommendations: [],
        generation: previousState.generation,
        message: backendError.message,
      };
    }

    if (
      backendError?.code === "database_not_configured" ||
      backendError?.code === "database_unavailable"
    ) {
      return {
        status: "database_error",
        recommendations: [],
        generation: previousState.generation,
        message: backendError.message,
      };
    }

    if (!response.ok) {
      return {
        status: "error",
        recommendations: [],
        generation: previousState.generation,
        message:
          backendError?.message ??
          `The recommendation service returned HTTP ${response.status}. Please try again.`,
      };
    }

    if (!isRecommendationResponse(payload)) {
      return {
        status: "error",
        recommendations: [],
        generation: previousState.generation,
        message:
          "The recommendation service returned an unexpected response. Check that the frontend and backend versions match.",
      };
    }

    return {
      status: "success",
      recommendations: payload.recommendations,
      generation: previousState.generation + 1,
    };
  } catch {
    return {
      status: "error",
      recommendations: [],
      generation: previousState.generation,
      message:
        "DataQuay could not reach the recommendation service. Confirm that the backend is running and try again.",
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
