import "server-only";

import { authenticatedBackendFetch } from "@/lib/backend-fetch";
import {
  extractApiDetail,
  isDatasetIdentifier,
  isDatasetInspection,
  isRecord,
  isWorkspaceDetail,
  isWorkspaceSummary,
  type InspectionResult,
  type WorkspaceDetailResult,
  type WorkspaceListResult,
} from "@/lib/dataquay";

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

export async function getWorkspaceList(): Promise<WorkspaceListResult> {
  try {
    const response = await authenticatedBackendFetch("/api/workspaces", {
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
    const payload: unknown = await response.json().catch(() => null);
    if (!response.ok) {
      return {
        ok: false,
        message: extractApiDetail(
          payload,
          `Workspace history returned HTTP ${response.status}.`,
        ),
      };
    }
    if (!isRecord(payload) || !Array.isArray(payload.workspaces)) {
      return {
        ok: false,
        message: "Workspace history returned an unexpected response.",
      };
    }
    if (!payload.workspaces.every(isWorkspaceSummary)) {
      return { ok: false, message: "Workspace history contains invalid records." };
    }
    return { ok: true, data: payload.workspaces };
  } catch {
    return {
      ok: false,
      message:
        "Workspace history is unavailable. Confirm that the backend and PostgreSQL are running.",
    };
  }
}

export async function getWorkspaceDetail(
  datasetId: string,
): Promise<WorkspaceDetailResult> {
  if (!isDatasetIdentifier(datasetId)) {
    return { ok: false, message: "The dataset identifier is invalid." };
  }
  try {
    const response = await authenticatedBackendFetch(
      `/api/workspaces/${encodeURIComponent(datasetId)}`,
      { cache: "no-store", headers: { Accept: "application/json" } },
    );
    const payload: unknown = await response.json().catch(() => null);
    if (!response.ok) {
      return {
        ok: false,
        message: extractApiDetail(
          payload,
          `Workspace metadata returned HTTP ${response.status}.`,
        ),
      };
    }
    if (!isWorkspaceDetail(payload)) {
      return {
        ok: false,
        message: "Workspace metadata returned an unexpected response.",
      };
    }
    return { ok: true, data: payload };
  } catch {
    return {
      ok: false,
      message:
        "Persisted workflow state is unavailable. Confirm that the backend and PostgreSQL are running.",
    };
  }
}

async function getDatasetInspection(path: string): Promise<InspectionResult> {
  try {
    const response = await authenticatedBackendFetch(path, {
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
