"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { DATASET_AUDIT_UPDATED_EVENT } from "@/app/components/AuditTimeline";
import {
  isDatasetAuditTrail,
  type AuditAction,
  type AuditEvent,
} from "@/lib/dataquay";

export type DemoWorkflowStep =
  | "recommendations"
  | "review"
  | "remediation"
  | "validation"
  | "package";
export type WorkflowProgressStep =
  | "upload"
  | "inspection"
  | DemoWorkflowStep;
export type DemoWorkflowStatus = "waiting" | "active" | "complete" | "blocked";

type ProgressSignal = {
  status: DemoWorkflowStatus;
  message?: string;
};

type StepDefinition = {
  key:
    WorkflowProgressStep;
  label: string;
  waitingMessage: string;
};

const WORKFLOW_PROGRESS_EVENT = "dataquay:workflow-progress";
const stepDefinitions: StepDefinition[] = [
  {
    key: "upload",
    label: "Upload",
    waitingMessage: "Select a ZIP dataset to begin.",
  },
  {
    key: "inspection",
    label: "Inspection",
    waitingMessage: "Wait for deterministic inspection to complete.",
  },
  {
    key: "recommendations",
    label: "Recommendations",
    waitingMessage: "Generate remediation recommendations when you are ready.",
  },
  {
    key: "review",
    label: "Human review",
    waitingMessage: "Review the proposals and approve at least one action.",
  },
  {
    key: "remediation",
    label: "Remediation",
    waitingMessage: "Preview the approved plan, then apply safe actions.",
  },
  {
    key: "validation",
    label: "Validation",
    waitingMessage: "Validate the working copy and checksum results.",
  },
  {
    key: "package",
    label: "Package download",
    waitingMessage: "Generate the final package, then download its ZIP.",
  },
];

export function WorkflowStepper({
  datasetId,
  stage = "dashboard",
}: {
  datasetId?: string;
  stage?: "upload" | "dashboard";
}) {
  const workflowId = datasetId ?? "sample";
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [signals, setSignals] = useState<
    Partial<Record<WorkflowProgressStep, ProgressSignal>>
  >({});
  const [syncing, setSyncing] = useState(Boolean(datasetId));

  const refreshAudit = useCallback(async () => {
    if (!datasetId) return;
    try {
      const response = await fetch(
        `/api/datasets/${encodeURIComponent(datasetId)}/audit`,
        { cache: "no-store" },
      );
      const payload: unknown = await response.json().catch(() => null);
      if (response.ok && isDatasetAuditTrail(payload)) {
        setAuditEvents(payload.events);
      }
    } finally {
      setSyncing(false);
    }
  }, [datasetId]);

  useEffect(() => {
    const initialSync = window.setTimeout(() => void refreshAudit(), 0);
    function handleAuditUpdate(event: Event) {
      if (
        event instanceof CustomEvent &&
        event.detail?.datasetId === datasetId
      ) {
        void refreshAudit();
      }
    }
    function handleProgress(event: Event) {
      if (
        !(event instanceof CustomEvent) ||
        event.detail?.workflowId !== workflowId
      ) {
        return;
      }
      const detail = event.detail as {
        step: WorkflowProgressStep;
        signal: ProgressSignal;
      };
      setSignals((current) => ({
        ...current,
        [detail.step]: detail.signal,
      }));
    }
    window.addEventListener(DATASET_AUDIT_UPDATED_EVENT, handleAuditUpdate);
    window.addEventListener(WORKFLOW_PROGRESS_EVENT, handleProgress);
    return () => {
      window.clearTimeout(initialSync);
      window.removeEventListener(DATASET_AUDIT_UPDATED_EVENT, handleAuditUpdate);
      window.removeEventListener(WORKFLOW_PROGRESS_EVENT, handleProgress);
    };
  }, [datasetId, refreshAudit, workflowId]);

  const steps = useMemo(() => {
    const reconstructed = reconstructProgress(auditEvents);
    return stepDefinitions.map((definition) => {
      if (definition.key === "upload") {
        return {
          ...definition,
          ...(signals.upload ?? {
            status: stage === "upload" ? "active" as const : "complete" as const,
          }),
        };
      }
      if (definition.key === "inspection") {
        return {
          ...definition,
          ...(signals.inspection ?? {
            status: stage === "dashboard" ? "complete" as const : "waiting" as const,
          }),
        };
      }
      const base = reconstructed[definition.key];
      const signal = signals[definition.key];
      return { ...definition, ...(signal ?? base) };
    });
  }, [auditEvents, signals, stage]);
  const nextStep = steps.find((step) => step.status !== "complete");

  return (
    <section
      className={`workflow-progress workflow-progress-${stage}`}
      aria-labelledby="workflow-progress-title"
    >
      <div className="workflow-progress-heading">
        <div>
          <p className="section-kicker">End-to-end workflow</p>
          <h2 id="workflow-progress-title">From archive to trusted package</h2>
        </div>
        {stage === "dashboard" ? (
          <div className="workflow-progress-actions">
            {syncing ? <span>Syncing history…</span> : null}
            <Link className="start-over-link" href="/">
              Start over
            </Link>
          </div>
        ) : null}
      </div>

      <ol className="workflow-progress-list">
        {steps.map((step, index) => (
          <li className={`progress-${step.status}`} key={step.key}>
            <span className="progress-number" aria-hidden="true">
              {step.status === "complete" ? "✓" : index + 1}
            </span>
            <span className="progress-label">{step.label}</span>
            <span className="progress-status">{statusLabels[step.status]}</span>
          </li>
        ))}
      </ol>

      <div
        className={`workflow-next-action ${
          nextStep?.status === "blocked" ? "is-blocked" : ""
        }`}
        aria-live="polite"
      >
        <div className="workflow-current-stage">
          <span>{nextStep ? "Current stage" : "Current status"}</span>
          <strong>{nextStep?.label ?? "Workflow complete"}</strong>
          {nextStep ? <small>{statusLabels[nextStep.status]}</small> : null}
        </div>
        <div className="workflow-recommended-action">
          <span>{nextStep ? "Next recommended action" : "What’s next"}</span>
          <strong>
            {nextStep
              ? nextStep.message ?? nextStep.waitingMessage
              : "The package was downloaded. Start over to inspect another dataset."}
          </strong>
        </div>
      </div>
    </section>
  );
}

export function reportWorkflowProgress(
  datasetId: string | undefined,
  step: WorkflowProgressStep,
  status: DemoWorkflowStatus,
  message?: string,
) {
  window.dispatchEvent(
    new CustomEvent(WORKFLOW_PROGRESS_EVENT, {
      detail: {
        workflowId: datasetId ?? "sample",
        step,
        signal: { status, message },
      },
    }),
  );
}

function reconstructProgress(
  events: AuditEvent[],
): Record<DemoWorkflowStep, ProgressSignal> {
  const progress: Record<DemoWorkflowStep, ProgressSignal> = {
    recommendations: { status: "waiting" },
    review: { status: "waiting" },
    remediation: { status: "waiting" },
    validation: { status: "waiting" },
    package: { status: "waiting" },
  };
  const recommendation = latestEvent(events, "recommendation_generation");
  if (recommendation) {
    progress.recommendations = eventSignal(
      recommendation.event,
      "Recommendations are ready. Review each proposal and record a decision.",
    );
  }

  const preview = latestEvent(events, "remediation_preview");
  const application = latestEvent(events, "remediation_apply");
  const remediation = laterEvent(preview, application);
  if (remediation) {
    progress.review = { status: "complete" };
    progress.remediation = eventSignal(
      remediation.event,
      remediation.event.action === "remediation_apply"
        ? "Safe actions were applied to the working copy. Run validation next."
        : "The preview is ready. Apply the approved safe actions next.",
      remediation.event.action === "remediation_apply" ? "complete" : "active",
    );
  }

  const validation = latestEvent(events, "validation");
  const validationIsCurrent = Boolean(
    validation && (!remediation || validation.index > remediation.index),
  );
  if (validation && validationIsCurrent) {
    progress.validation = eventSignal(
      validation.event,
      "Validation passed. Generate the final package next.",
    );
  }

  const generation = latestEvent(events, "package_generation");
  const download = latestEvent(events, "package_download");
  const packageEvent = laterEvent(generation, download);
  if (
    packageEvent &&
    validation &&
    validationIsCurrent &&
    packageEvent.index > validation.index
  ) {
    progress.package = eventSignal(
      packageEvent.event,
      packageEvent.event.action === "package_download"
        ? "The final ZIP was prepared for download."
        : "The final package is ready. Download the ZIP to finish.",
      packageEvent.event.action === "package_download" ? "complete" : "active",
    );
  }
  return progress;
}

function latestEvent(events: AuditEvent[], action: AuditAction) {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    if (events[index].action === action) return { event: events[index], index };
  }
  return undefined;
}

function laterEvent(
  left: ReturnType<typeof latestEvent>,
  right: ReturnType<typeof latestEvent>,
) {
  if (!left) return right;
  if (!right) return left;
  return left.index > right.index ? left : right;
}

function eventSignal(
  event: AuditEvent,
  successMessage: string,
  successStatus: DemoWorkflowStatus = "complete",
): ProgressSignal {
  return event.status === "success"
    ? { status: successStatus, message: successMessage }
    : { status: "blocked", message: event.summary };
}

const statusLabels: Record<DemoWorkflowStatus, string> = {
  waiting: "Waiting",
  active: "In progress",
  complete: "Complete",
  blocked: "Blocked",
};
