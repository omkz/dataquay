"use server";

import {
  isDatasetClarifications,
  isDatasetIdentifier,
  type ClarificationActionResult,
} from "@/lib/dataquay";
import { authenticatedBackendFetch } from "@/lib/backend-fetch";

export async function loadDatasetClarifications(
  datasetId: string,
): Promise<ClarificationActionResult> {
  return requestClarifications(
    datasetId,
    `/api/clarify/datasets/${encodeURIComponent(datasetId)}`,
    { method: "GET" },
  );
}

export async function updateDatasetClarification(
  datasetId: string,
  questionId: string,
  decision: "answer" | "defer",
  answer?: string,
): Promise<ClarificationActionResult> {
  if (!/^cq_[0-9a-f]{20}$/.test(questionId)) {
    return { ok: false, message: "The clarification question is invalid." };
  }
  return requestClarifications(
    datasetId,
    `/api/clarify/datasets/${encodeURIComponent(datasetId)}/questions/${encodeURIComponent(questionId)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        decision,
        answer: decision === "answer" ? answer : undefined,
      }),
    },
  );
}

async function requestClarifications(
  datasetId: string,
  path: string,
  init: RequestInit,
): Promise<ClarificationActionResult> {
  if (!isDatasetIdentifier(datasetId)) {
    return {
      ok: false,
      message: "The dataset identifier is invalid. Upload the dataset again.",
    };
  }

  try {
    const headers = new Headers(init.headers);
    headers.set("Accept", "application/json");
    const response = await authenticatedBackendFetch(path, {
      ...init,
      cache: "no-store",
      headers,
    });
    const payload: unknown = await response.json().catch(() => null);
    if (!response.ok) {
      return {
        ok: false,
        message: extractDetail(
          payload,
          `The clarification service returned HTTP ${response.status}.`,
        ),
      };
    }
    if (!isDatasetClarifications(payload)) {
      return {
        ok: false,
        message: "The clarification service returned an unexpected response.",
      };
    }
    return { ok: true, data: payload };
  } catch {
    return {
      ok: false,
      message:
        "DataQuay could not reach the clarification service. Confirm that the backend is running and try again.",
    };
  }
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
