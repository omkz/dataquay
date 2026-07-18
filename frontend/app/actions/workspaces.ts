"use server";

import {
  getBackendUrl,
  isDatasetIdentifier,
  type RecommendationDecision,
  type RecommendationDecisionResult,
} from "@/lib/dataquay";

export async function saveRecommendationDecision(
  datasetId: string,
  recommendationKey: string,
  decision: RecommendationDecision,
): Promise<RecommendationDecisionResult> {
  if (!isDatasetIdentifier(datasetId)) {
    return { ok: false, message: "The dataset identifier is invalid." };
  }
  if (!recommendationKey || recommendationKey.length > 180) {
    return { ok: false, message: "The recommendation identifier is invalid." };
  }

  try {
    const response = await fetch(
      `${getBackendUrl()}/api/workspaces/${encodeURIComponent(datasetId)}/decision`,
      {
        method: "PUT",
        cache: "no-store",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ recommendation_key: recommendationKey, decision }),
      },
    );
    const payload: unknown = await response.json().catch(() => null);
    if (!response.ok) {
      return {
        ok: false,
        message: extractDetail(
          payload,
          `Saving the review decision returned HTTP ${response.status}.`,
        ),
      };
    }
    if (!isDecisionResponse(payload)) {
      return { ok: false, message: "The decision API returned an unexpected response." };
    }
    return { ok: true, decisions: payload.decisions };
  } catch {
    return {
      ok: false,
      message: "The review decision could not be saved. Confirm that the backend and PostgreSQL are running.",
    };
  }
}

function isDecisionResponse(
  value: unknown,
): value is { decisions: Record<string, RecommendationDecision> } {
  if (!value || typeof value !== "object" || !("decisions" in value)) return false;
  const decisions = value.decisions;
  return Boolean(
    decisions &&
      typeof decisions === "object" &&
      Object.values(decisions).every(
        (decision) =>
          decision === "pending" || decision === "approved" || decision === "rejected",
      ),
  );
}

function extractDetail(payload: unknown, fallback: string) {
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
