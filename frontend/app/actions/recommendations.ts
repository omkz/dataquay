"use server";

import {
  getBackendUrl,
  isRecommendationResponse,
  type RecommendationActionState,
} from "@/lib/dataquay";

export async function generateRecommendations(
  previousState: RecommendationActionState,
  formData: FormData,
): Promise<RecommendationActionState> {
  void formData;

  try {
    const response = await fetch(
      `${getBackendUrl()}/api/inspect/sample-dataset/recommendations`,
      {
        method: "POST",
        cache: "no-store",
        headers: { Accept: "application/json" },
      },
    );
    const payload: unknown = await readJsonResponse(response);

    if (response.status === 503) {
      return {
        status: "configuration_error",
        recommendations: [],
        generation: previousState.generation,
        message:
          "AI recommendations are not configured. Set DATAQUAY_AI_MODEL and the provider API key in the backend environment, then try again.",
      };
    }

    if (!response.ok) {
      return {
        status: "error",
        recommendations: [],
        generation: previousState.generation,
        message: `The recommendation service returned HTTP ${response.status}. Please try again.`,
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
