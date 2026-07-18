"use client";

import { useState, useTransition } from "react";

import {
  applyApprovedRemediation,
  generateFinalPackage,
  previewApprovedRemediation,
  validateAppliedRemediation,
} from "@/app/actions/remediation-workflow";
import { notifyDatasetAuditUpdated } from "@/app/components/AuditTimeline";
import type {
  DatasetValidationResult,
  InspectionFinding,
  PackageGenerationResult,
  RemediationAction,
  RemediationActionResult,
  RemediationApplyResponse,
  RemediationPreviewResponse,
  RemediationRecommendation,
} from "@/lib/dataquay";

type WorkflowStep = "preview" | "apply" | "validate" | "package";
type StepState<T> =
  | { status: "idle" }
  | { status: "success"; data: T }
  | { status: "error"; message: string; prerequisite: boolean };

const idleState = { status: "idle" } as const;

export function RemediationWorkflow({
  approvedRecommendations,
  datasetId,
}: {
  approvedRecommendations: RemediationRecommendation[];
  datasetId?: string;
}) {
  const [preview, setPreview] = useState<StepState<RemediationPreviewResponse>>(
    idleState,
  );
  const [application, setApplication] = useState<
    StepState<RemediationApplyResponse>
  >(idleState);
  const [validation, setValidation] = useState<
    StepState<DatasetValidationResult>
  >(idleState);
  const [packageResult, setPackageResult] = useState<
    StepState<PackageGenerationResult>
  >(idleState);
  const [activeStep, setActiveStep] = useState<WorkflowStep | null>(null);
  const [isPending, startTransition] = useTransition();

  const hasApprovals = approvedRecommendations.length > 0;
  const previewComplete = preview.status === "success";
  const applyComplete = application.status === "success";
  const validationComplete = validation.status === "success";
  const validationPassed =
    validationComplete &&
    validation.data.source_checksums_verified &&
    validation.data.output_checksums_verified &&
    validation.data.original_files_unchanged;

  function runPreview() {
    setApplication(idleState);
    setValidation(idleState);
    setPackageResult(idleState);
    setActiveStep("preview");
    startTransition(async () => {
      const result = await previewApprovedRemediation(
        approvedRecommendations,
        datasetId,
      );
      setPreview(
        result.ok
          ? { status: "success", data: result.data }
          : {
              status: "error",
              message: result.message,
              prerequisite: result.prerequisite,
            },
      );
      notifyDatasetAuditUpdated(datasetId);
      setActiveStep(null);
    });
  }

  function runApply() {
    setValidation(idleState);
    setPackageResult(idleState);
    setActiveStep("apply");
    startTransition(async () => {
      const result = await applyApprovedRemediation(
        approvedRecommendations,
        datasetId,
      );
      setApplication(
        result.ok
          ? { status: "success", data: result.data }
          : {
              status: "error",
              message: result.message,
              prerequisite: result.prerequisite,
            },
      );
      notifyDatasetAuditUpdated(datasetId);
      setActiveStep(null);
    });
  }

  function runValidation() {
    setPackageResult(idleState);
    setActiveStep("validate");
    startTransition(async () => {
      const result = await validateAppliedRemediation(datasetId);
      setValidation(
        result.ok
          ? { status: "success", data: result.data }
          : {
              status: "error",
              message: result.message,
              prerequisite: result.prerequisite,
            },
      );
      notifyDatasetAuditUpdated(datasetId);
      setActiveStep(null);
    });
  }

  function runPackageGeneration() {
    setActiveStep("package");
    startTransition(async () => {
      const result = await generateFinalPackage(datasetId);
      setPackageResult(
        result.ok
          ? { status: "success", data: result.data }
          : {
              status: "error",
              message: result.message,
              prerequisite: result.prerequisite,
            },
      );
      notifyDatasetAuditUpdated(datasetId);
      setActiveStep(null);
    });
  }

  return (
    <section className="workflow-panel" aria-labelledby="workflow-title">
      <div className="workflow-heading">
        <div>
          <p className="section-kicker">Controlled execution</p>
          <h3 id="workflow-title">
            {datasetId ? "Uploaded dataset workflow" : "Sample dataset workflow"}
          </h3>
          <p>
            Each stage runs only when you select it. Safe changes are applied to
            a separate working copy; original files remain unchanged.
          </p>
        </div>
        <span>{approvedRecommendations.length} approved</span>
      </div>

      <div className="workflow-steps" aria-live="polite">
        <WorkflowStepCard
          number={1}
          title="Preview remediation"
          description="Classify approved proposals as automatic or manual before creating a working copy."
          state={preview.status}
          action={
            <WorkflowButton
              disabled={!hasApprovals || isPending}
              label={previewComplete ? "Refresh preview" : "Preview approved actions"}
              loading={isPending && activeStep === "preview"}
              onClick={runPreview}
            />
          }
          prerequisite={
            hasApprovals
              ? undefined
              : "Approve at least one recommendation to begin."
          }
        >
          {preview.status === "error" ? (
            <WorkflowError state={preview} />
          ) : preview.status === "success" ? (
            <PreviewResult preview={preview.data} />
          ) : null}
        </WorkflowStepCard>

        <WorkflowStepCard
          number={2}
          title="Apply safe actions"
          description="Create a fresh working copy and apply only deterministic actions marked safe."
          state={application.status}
          action={
            <WorkflowButton
              disabled={!previewComplete || isPending}
              label={applyComplete ? "Apply again" : "Apply safe actions"}
              loading={isPending && activeStep === "apply"}
              onClick={runApply}
            />
          }
          prerequisite={
            previewComplete ? undefined : "Complete remediation preview first."
          }
        >
          {application.status === "error" ? (
            <WorkflowError state={application} />
          ) : application.status === "success" ? (
            <ApplicationResult application={application.data} />
          ) : null}
        </WorkflowStepCard>

        <WorkflowStepCard
          number={3}
          title="Validate working copy"
          description="Reinspect the output, compare findings, and verify source and output checksums."
          state={validation.status}
          action={
            <WorkflowButton
              disabled={!applyComplete || isPending}
              label={validationComplete ? "Validate again" : "Run validation"}
              loading={isPending && activeStep === "validate"}
              onClick={runValidation}
            />
          }
          prerequisite={
            applyComplete ? undefined : "Apply the approved safe actions first."
          }
        >
          {validation.status === "error" ? (
            <WorkflowError state={validation} />
          ) : validation.status === "success" ? (
            <ValidationResult validation={validation.data} />
          ) : null}
        </WorkflowStepCard>

        <WorkflowStepCard
          number={4}
          title="Generate final package"
          description="Build documentation, metadata, manifests, checksums, validation report, provenance, and ZIP."
          state={packageResult.status}
          action={
            <WorkflowButton
              disabled={!validationPassed || isPending}
              label={
                packageResult.status === "success"
                  ? "Generate package again"
                  : "Generate package"
              }
              loading={isPending && activeStep === "package"}
              onClick={runPackageGeneration}
            />
          }
          prerequisite={
            validationPassed
              ? undefined
              : validationComplete
                ? "Checksum validation must pass before packaging."
                : "Run validation successfully before packaging."
          }
        >
          {packageResult.status === "error" ? (
            <WorkflowError state={packageResult} />
          ) : packageResult.status === "success" ? (
            <PackageResult
              datasetId={datasetId}
              packageResult={packageResult.data}
            />
          ) : null}
        </WorkflowStepCard>
      </div>
    </section>
  );
}

function WorkflowStepCard({
  number,
  title,
  description,
  state,
  action,
  prerequisite,
  children,
}: {
  number: number;
  title: string;
  description: string;
  state: "idle" | "success" | "error";
  action: React.ReactNode;
  prerequisite?: string;
  children: React.ReactNode;
}) {
  return (
    <article className={`workflow-step workflow-step-${state}`}>
      <div className="workflow-step-header">
        <span className="workflow-step-number">{number}</span>
        <div>
          <h4>{title}</h4>
          <p>{description}</p>
        </div>
        <span className={`workflow-step-status status-${state}`}>
          {state === "success" ? "Complete" : state === "error" ? "Attention" : "Waiting"}
        </span>
      </div>
      <div className="workflow-step-action">
        {prerequisite ? <p>{prerequisite}</p> : <span />}
        {action}
      </div>
      {children ? <div className="workflow-step-result">{children}</div> : null}
    </article>
  );
}

function WorkflowButton({
  disabled,
  label,
  loading,
  onClick,
}: {
  disabled: boolean;
  label: string;
  loading: boolean;
  onClick: () => void;
}) {
  return (
    <button
      className="workflow-button"
      disabled={disabled}
      onClick={onClick}
      type="button"
    >
      {loading ? (
        <>
          <span className="button-spinner" aria-hidden="true" />
          Working…
        </>
      ) : (
        label
      )}
    </button>
  );
}

function WorkflowError({
  state,
}: {
  state: { status: "error"; message: string; prerequisite: boolean };
}) {
  return (
    <div className="workflow-error" role="alert">
      <strong>{state.prerequisite ? "Prerequisite required" : "Stage failed"}</strong>
      <p>{state.message}</p>
    </div>
  );
}

function PreviewResult({ preview }: { preview: RemediationPreviewResponse }) {
  const automatic = preview.actions.filter(
    (action) => action.can_apply_automatically,
  );
  const manual = preview.actions.filter(
    (action) => !action.can_apply_automatically,
  );
  return (
    <div className="workflow-result-stack">
      <div className="workflow-result-summary">
        <ResultMetric label="Safe to apply" value={automatic.length} tone="success" />
        <ResultMetric label="Manual review" value={manual.length} tone="warning" />
      </div>
      <ActionPreviewList actions={preview.actions} />
    </div>
  );
}

function ActionPreviewList({ actions }: { actions: RemediationAction[] }) {
  return (
    <div className="workflow-compact-list">
      {actions.map((action, index) => (
        <div className="workflow-compact-item" key={actionKey(action, index)}>
          <span
            className={`outcome-dot ${
              action.can_apply_automatically ? "applied" : "skipped"
            }`}
          />
          <div>
            <strong>{formatLabel(action.proposed_operation)}</strong>
            <p>
              {action.target_file}
              {action.target_column ? ` / ${action.target_column}` : ""}
            </p>
          </div>
          <small>
            {action.can_apply_automatically ? "Automatic" : "Manual"}
          </small>
        </div>
      ))}
    </div>
  );
}

function ApplicationResult({
  application,
}: {
  application: RemediationApplyResponse;
}) {
  return (
    <div className="workflow-result-stack">
      <div className="workflow-result-summary">
        <ResultMetric
          label="Applied"
          value={application.applied_actions.length}
          tone="success"
        />
        <ResultMetric
          label="Skipped"
          value={application.skipped_actions.length}
          tone="warning"
        />
        <ResultMetric
          label="Failed"
          value={application.failed_actions.length}
          tone="error"
        />
      </div>
      <OutcomeGroup
        title="Applied actions"
        empty="No safe actions were applied."
        items={application.applied_actions}
        tone="applied"
      />
      <OutcomeGroup
        title="Skipped actions"
        empty="No actions required manual handling."
        items={application.skipped_actions}
        tone="skipped"
      />
      {application.failed_actions.length > 0 ? (
        <OutcomeGroup
          title="Failed actions"
          empty=""
          items={application.failed_actions}
          tone="failed"
        />
      ) : null}
    </div>
  );
}

function OutcomeGroup({
  title,
  empty,
  items,
  tone,
}: {
  title: string;
  empty: string;
  items: RemediationActionResult[];
  tone: "applied" | "skipped" | "failed";
}) {
  return (
    <div className="outcome-group">
      <h5>{title}</h5>
      {items.length === 0 ? (
        <p className="outcome-empty">{empty}</p>
      ) : (
        <div className="workflow-compact-list">
          {items.map((item, index) => (
            <div
              className="workflow-compact-item"
              key={actionKey(item.action, index)}
            >
              <span className={`outcome-dot ${tone}`} />
              <div>
                <strong>{formatLabel(item.action.proposed_operation)}</strong>
                <p>{item.message}</p>
              </div>
              <code title={item.output_checksum_sha256 ?? "No output checksum"}>
                {shortChecksum(item.output_checksum_sha256)}
              </code>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ValidationResult({
  validation,
}: {
  validation: DatasetValidationResult;
}) {
  const checksumsPassed =
    validation.source_checksums_verified &&
    validation.output_checksums_verified &&
    validation.original_files_unchanged;
  return (
    <div className="workflow-result-stack">
      <div className="workflow-result-summary">
        <ResultMetric
          label="Resolved issues"
          value={validation.resolved_findings.length}
          tone="success"
        />
        <ResultMetric
          label="Remaining issues"
          value={validation.remaining_findings.length}
          tone="warning"
        />
        <ResultMetric
          label="Blockers"
          value={validation.readiness.blocker_count}
          tone={validation.readiness.blocker_count > 0 ? "error" : "success"}
        />
      </div>
      <div className={`checksum-banner ${checksumsPassed ? "passed" : "failed"}`}>
        <strong>
          {checksumsPassed ? "Checksum verification passed" : "Checksum verification failed"}
        </strong>
        <span>
          Original files {validation.original_files_unchanged ? "unchanged" : "changed"}
          {" · "}Readiness {formatLabel(validation.readiness.status)}
        </span>
      </div>
      <FindingOutcomeGroup
        title="Resolved issues"
        findings={validation.resolved_findings}
        empty="No findings were resolved by the applied safe actions."
        tone="resolved"
      />
      <FindingOutcomeGroup
        title="Remaining issues"
        findings={validation.remaining_findings}
        empty="No findings remain."
        tone="remaining"
      />
    </div>
  );
}

function FindingOutcomeGroup({
  title,
  findings,
  empty,
  tone,
}: {
  title: string;
  findings: InspectionFinding[];
  empty: string;
  tone: "resolved" | "remaining";
}) {
  return (
    <div className="outcome-group">
      <h5>{title}</h5>
      {findings.length === 0 ? (
        <p className="outcome-empty">{empty}</p>
      ) : (
        <div className="finding-outcome-list">
          {findings.map((finding, index) => (
            <div
              className={`finding-outcome finding-outcome-${tone}`}
              key={`${finding.type}-${finding.file}-${finding.affected_column ?? "file"}-${index}`}
            >
              <div>
                <strong>{formatLabel(finding.type)}</strong>
                <code>
                  {finding.file}
                  {finding.affected_column ? ` / ${finding.affected_column}` : ""}
                </code>
              </div>
              <p>{finding.message}</p>
              <span>{formatLabel(finding.severity)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function PackageResult({
  packageResult,
  datasetId,
}: {
  packageResult: PackageGenerationResult;
  datasetId?: string;
}) {
  const [downloadState, setDownloadState] = useState<
    { status: "idle" | "pending" | "error"; message?: string }
  >({ status: "idle" });

  async function downloadPackage() {
    setDownloadState({ status: "pending" });
    try {
      const downloadPath = datasetId
        ? `/api/datasets/${encodeURIComponent(datasetId)}/package`
        : "/api/sample-package";
      const response = await fetch(downloadPath, { cache: "no-store" });
      notifyDatasetAuditUpdated(datasetId);
      if (!response.ok) {
        const payload: unknown = await response.json().catch(() => null);
        const detail =
          payload &&
          typeof payload === "object" &&
          "detail" in payload &&
          typeof payload.detail === "string"
            ? payload.detail
            : `The package download returned HTTP ${response.status}.`;
        setDownloadState({ status: "error", message: detail });
        return;
      }

      const objectUrl = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = packageResult.zip_file_name;
      link.click();
      URL.revokeObjectURL(objectUrl);
      setDownloadState({ status: "idle" });
    } catch {
      setDownloadState({
        status: "error",
        message:
          "The ZIP could not be downloaded. Confirm that the backend is running and try again.",
      });
    }
  }

  return (
    <div className="package-result-wrap">
      <div className="package-result">
        <div>
          <span className="package-mark" aria-hidden="true">ZIP</span>
          <div>
            <strong>{packageResult.zip_file_name}</strong>
            <p>
              {packageResult.files.length} files · {formatBytes(packageResult.zip_size_bytes)}
            </p>
            <code title={packageResult.zip_checksum_sha256}>
              SHA-256 {shortChecksum(packageResult.zip_checksum_sha256)}
            </code>
          </div>
        </div>
        <button
          className="download-button"
          disabled={downloadState.status === "pending"}
          onClick={downloadPackage}
          type="button"
        >
          {downloadState.status === "pending" ? "Preparing download…" : "Download ZIP"}
        </button>
      </div>
      {downloadState.status === "error" ? (
        <div className="workflow-error" role="alert">
          <strong>Download failed</strong>
          <p>{downloadState.message}</p>
        </div>
      ) : null}
    </div>
  );
}

function ResultMetric({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "success" | "warning" | "error";
}) {
  return (
    <div className={`workflow-metric workflow-metric-${tone}`}>
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function actionKey(action: RemediationAction, index: number) {
  return `${action.proposed_operation}-${action.target_file}-${action.target_column ?? "file"}-${index}`;
}

function shortChecksum(checksum: string | null) {
  return checksum ? `${checksum.slice(0, 8)}…${checksum.slice(-6)}` : "No checksum";
}

function formatLabel(value: string) {
  return value
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
