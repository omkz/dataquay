"use client";

import { useCallback, useEffect, useState } from "react";

import {
  isDatasetAuditTrail,
  type AuditAction,
  type DatasetAuditTrail,
} from "@/lib/dataquay";

export const DATASET_AUDIT_UPDATED_EVENT = "dataquay:audit-updated";

type TimelineState =
  | { status: "loading" }
  | { status: "success"; trail: DatasetAuditTrail }
  | { status: "error"; message: string };

export function AuditTimeline({ datasetId }: { datasetId: string }) {
  const [state, setState] = useState<TimelineState>({ status: "loading" });
  const [refreshing, setRefreshing] = useState(false);

  const loadAudit = useCallback(async (background = false) => {
    if (background) setRefreshing(true);
    else setState({ status: "loading" });
    try {
      const response = await fetch(
        `/api/datasets/${encodeURIComponent(datasetId)}/audit`,
        { cache: "no-store" },
      );
      const payload: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        setState({
          status: "error",
          message: extractError(
            payload,
            `The audit service returned HTTP ${response.status}.`,
          ),
        });
      } else if (!isDatasetAuditTrail(payload)) {
        setState({
          status: "error",
          message: "The audit service returned an unexpected response.",
        });
      } else {
        setState({ status: "success", trail: payload });
      }
    } catch {
      setState({
        status: "error",
        message:
          "The audit trail could not be loaded. Confirm that the backend is running and try again.",
      });
    } finally {
      setRefreshing(false);
    }
  }, [datasetId]);

  useEffect(() => {
    const initialLoad = window.setTimeout(() => void loadAudit(), 0);
    function handleAuditUpdate(event: Event) {
      if (
        event instanceof CustomEvent &&
        event.detail?.datasetId === datasetId
      ) {
        void loadAudit(true);
      }
    }
    window.addEventListener(DATASET_AUDIT_UPDATED_EVENT, handleAuditUpdate);
    return () => {
      window.clearTimeout(initialLoad);
      window.removeEventListener(DATASET_AUDIT_UPDATED_EVENT, handleAuditUpdate);
    };
  }, [datasetId, loadAudit]);

  return (
    <section className="content-section" aria-labelledby="audit-title">
      <div className="section-heading audit-heading">
        <div>
          <p className="section-kicker">Append-only history</p>
          <h2 id="audit-title">Dataset audit trail</h2>
          <p className="section-description">
            Safe workflow summaries only. Raw rows, secrets, and unmasked
            personal data are never included.
          </p>
        </div>
        <button
          className="audit-refresh"
          disabled={refreshing || state.status === "loading"}
          onClick={() => void loadAudit(true)}
          type="button"
        >
          {refreshing ? "Refreshing…" : "Refresh timeline"}
        </button>
      </div>

      <div aria-live="polite">
        {state.status === "loading" ? (
          <AuditLoading />
        ) : state.status === "error" ? (
          <div className="audit-state audit-error" role="alert">
            <strong>Audit trail unavailable</strong>
            <p>{state.message}</p>
          </div>
        ) : state.trail.events.length === 0 ? (
          <div className="audit-state">
            <strong>No audit events yet</strong>
            <p>Workflow activity will appear here as it occurs.</p>
          </div>
        ) : (
          <ol className="audit-timeline">
            {[...state.trail.events].reverse().map((event, index) => (
              <li key={`${event.timestamp}-${event.action}-${index}`}>
                <span
                  className={`audit-marker audit-marker-${event.status}`}
                  aria-hidden="true"
                />
                <div className="audit-event">
                  <div className="audit-event-topline">
                    <strong>{actionLabels[event.action]}</strong>
                    <span className={`audit-status audit-status-${event.status}`}>
                      {event.status}
                    </span>
                  </div>
                  <p>{event.summary}</p>
                  <time dateTime={event.timestamp}>
                    {formatTimestamp(event.timestamp)}
                  </time>
                </div>
              </li>
            ))}
          </ol>
        )}
      </div>
    </section>
  );
}

export function notifyDatasetAuditUpdated(datasetId?: string) {
  if (!datasetId) return;
  window.dispatchEvent(
    new CustomEvent(DATASET_AUDIT_UPDATED_EVENT, { detail: { datasetId } }),
  );
}

function AuditLoading() {
  return (
    <div className="audit-loading" aria-busy="true">
      <span className="skeleton" />
      <span className="skeleton" />
      <span className="skeleton" />
    </div>
  );
}

function extractError(payload: unknown, fallback: string) {
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

function formatTimestamp(timestamp: string) {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return timestamp;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

const actionLabels: Record<AuditAction, string> = {
  upload: "Dataset upload",
  inspection: "Dataset inspection",
  clarification_review: "Clarification review",
  clarification_response: "Clarification response",
  recommendation_generation: "Recommendation generation",
  remediation_preview: "Remediation preview",
  remediation_apply: "Remediation apply",
  validation: "Working-copy validation",
  package_generation: "Package generation",
  package_download: "Package download",
};
