"use client";

import { useActionState, useEffect, useState } from "react";

import { generateRecommendations } from "@/app/actions/recommendations";
import { notifyDatasetAuditUpdated } from "@/app/components/AuditTimeline";
import { DATASET_CLARIFICATIONS_UPDATED_EVENT } from "@/app/components/ClarificationPanel";
import {
  RemediationWorkflow,
  type ValidationBaseline,
} from "@/app/components/RemediationWorkflow";
import { reportWorkflowProgress } from "@/app/components/WorkflowStepper";
import type {
  RecommendationActionState,
  RemediationRecommendation,
} from "@/lib/dataquay";

const initialState: RecommendationActionState = {
  status: "idle",
  recommendations: [],
  generation: 0,
};

type RecommendationDecision = "pending" | "approved" | "rejected";

export function RecommendationsPanel({
  datasetId,
  validationBaseline,
}: {
  datasetId?: string;
  validationBaseline: ValidationBaseline;
}) {
  const [state, formAction, pending] = useActionState(
    generateRecommendations,
    initialState,
  );
  const [clarificationsChanged, setClarificationsChanged] = useState(false);

  useEffect(() => {
    function handleClarificationUpdate(event: Event) {
      if (
        event instanceof CustomEvent &&
        event.detail?.datasetId === datasetId &&
        state.status === "success"
      ) {
        setClarificationsChanged(true);
      }
    }
    window.addEventListener(
      DATASET_CLARIFICATIONS_UPDATED_EVENT,
      handleClarificationUpdate,
    );
    return () =>
      window.removeEventListener(
        DATASET_CLARIFICATIONS_UPDATED_EVENT,
        handleClarificationUpdate,
      );
  }, [datasetId, state.status]);

  useEffect(() => {
    if (pending) {
      reportWorkflowProgress(
        datasetId,
        "recommendations",
        "active",
        "The Data Steward Agent is generating masked, proposal-only guidance.",
      );
      return;
    }
    if (state.status !== "idle") {
      notifyDatasetAuditUpdated(datasetId);
    }
    if (state.status === "success") {
      reportWorkflowProgress(
        datasetId,
        "clarifications",
        "complete",
        "Available clarification context was included; unresolved context must remain labelled as AI assumptions.",
      );
      reportWorkflowProgress(
        datasetId,
        "recommendations",
        "complete",
        "Recommendations are ready. Review each proposal and record a decision.",
      );
      if (state.recommendations.length === 0) {
        reportWorkflowProgress(
          datasetId,
          "review",
          "blocked",
          "No recommendations were returned. Generate again or review the deterministic findings manually.",
        );
      }
    } else if (
      state.status === "configuration_error" ||
      state.status === "error"
    ) {
      reportWorkflowProgress(
        datasetId,
        "recommendations",
        "blocked",
        state.message ?? "Recommendation generation must succeed before review.",
      );
    }
  }, [datasetId, pending, state]);

  return (
    <section className="content-section" aria-labelledby="recommendations-title">
      <div className="section-heading recommendation-heading">
        <div>
          <p className="section-kicker">Data Steward Agent</p>
          <h2 id="recommendations-title">Remediation recommendations</h2>
          <p className="section-description">
            Generate proposal-only guidance from the deterministic findings. No
            dataset files will be changed. Saved clarification answers are
            included as confirmed context for uploaded datasets.
          </p>
        </div>
        <form
          action={formAction}
          onSubmit={() => setClarificationsChanged(false)}
        >
          {datasetId ? (
            <input name="dataset_id" type="hidden" value={datasetId} />
          ) : null}
          <button
            className="generate-button"
            disabled={pending}
            type="submit"
          >
            {pending ? (
              <>
                <span className="button-spinner" aria-hidden="true" />
                Generating…
              </>
            ) : state.status === "success" && clarificationsChanged ? (
              "Refresh with clarifications"
            ) : state.status === "success" ? (
              "Generate again"
            ) : (
              "Generate recommendations"
            )}
          </button>
        </form>
      </div>

      {clarificationsChanged ? (
        <div className="recommendation-context-notice" role="status">
          Clarification context changed. Refresh recommendations to incorporate
          the latest confirmed answers and unresolved questions.
        </div>
      ) : null}

      <div aria-live="polite">
        {pending ? (
          <RecommendationLoading />
        ) : state.status === "idle" ? (
          <RecommendationIdle />
        ) : state.status === "configuration_error" ? (
          <RecommendationNotice
            kind="configuration"
            title="AI configuration required"
            message={state.message ?? "Configure the backend AI model to continue."}
          />
        ) : state.status === "error" ? (
          <RecommendationNotice
            kind="error"
            title="Recommendations unavailable"
            message={state.message ?? "The request could not be completed."}
          />
        ) : state.recommendations.length === 0 ? (
          <RecommendationEmpty />
        ) : (
          <RecommendationReview
            datasetId={datasetId}
            key={state.generation}
            recommendations={state.recommendations}
            validationBaseline={validationBaseline}
          />
        )}
      </div>
    </section>
  );
}

function RecommendationReview({
  recommendations,
  datasetId,
  validationBaseline,
}: {
  recommendations: RemediationRecommendation[];
  datasetId?: string;
  validationBaseline: ValidationBaseline;
}) {
  const [decisions, setDecisions] = useState<
    Record<string, RecommendationDecision>
  >({});
  const reviewedRecommendations = recommendations.map((recommendation, index) => {
    const id = getRecommendationId(recommendation, index);
    return {
      id,
      recommendation,
      decision: decisions[id] ?? "pending",
      index,
    };
  });
  const decisionCounts = reviewedRecommendations.reduce(
    (counts, item) => {
      counts[item.decision] += 1;
      return counts;
    },
    { pending: 0, approved: 0, rejected: 0 },
  );
  const approvedRecommendations = reviewedRecommendations.filter(
    (item) => item.decision === "approved",
  );

  useEffect(() => {
    if (decisionCounts.approved > 0) {
      reportWorkflowProgress(
        datasetId,
        "review",
        "complete",
        `${decisionCounts.approved} approved recommendation${decisionCounts.approved === 1 ? " is" : "s are"} ready for remediation preview.`,
      );
    } else if (decisionCounts.pending > 0) {
      reportWorkflowProgress(
        datasetId,
        "review",
        "active",
        `Review ${decisionCounts.pending} pending recommendation${decisionCounts.pending === 1 ? "" : "s"} and approve at least one to continue.`,
      );
    } else {
      reportWorkflowProgress(
        datasetId,
        "review",
        "blocked",
        "All recommendations are rejected. Approve one or generate a new set to continue.",
      );
    }
  }, [datasetId, decisionCounts.approved, decisionCounts.pending]);

  function updateDecision(id: string, decision: RecommendationDecision) {
    setDecisions((current) => ({ ...current, [id]: decision }));
  }

  return (
    <div className="recommendation-review">
      <ReviewSummary counts={decisionCounts} />

      <div className="recommendation-list">
        {reviewedRecommendations.map((item) => (
          <RecommendationCard
            decision={item.decision}
            index={item.index + 1}
            key={item.id}
            onDecision={(decision) => updateDecision(item.id, decision)}
            recommendation={item.recommendation}
          />
        ))}
      </div>

      <ApprovedRemediationPlan
        datasetId={datasetId}
        items={approvedRecommendations}
        validationBaseline={validationBaseline}
      />
    </div>
  );
}

function ReviewSummary({
  counts,
}: {
  counts: Record<RecommendationDecision, number>;
}) {
  return (
    <div className="review-summary" aria-label="Recommendation review summary">
      <div className="review-summary-heading">
        <div>
          <span>Review progress</span>
          <strong>Current decisions</strong>
        </div>
        <small>Kept on this page only</small>
      </div>
      <div className="review-counts">
        <ReviewCount decision="approved" count={counts.approved} />
        <ReviewCount decision="rejected" count={counts.rejected} />
        <ReviewCount decision="pending" count={counts.pending} />
      </div>
    </div>
  );
}

function ReviewCount({
  decision,
  count,
}: {
  decision: RecommendationDecision;
  count: number;
}) {
  return (
    <div className={`review-count review-count-${decision}`}>
      <span className="review-count-dot" aria-hidden="true" />
      <strong>{count}</strong>
      <span>{formatLabel(decision)}</span>
    </div>
  );
}

function RecommendationIdle() {
  return (
    <div className="recommendation-state recommendation-idle">
      <span className="recommendation-state-mark" aria-hidden="true">
        AI
      </span>
      <div>
        <strong>Recommendations are generated on demand.</strong>
        <p>
          The agent receives only the dataset summary, readiness result, and
          masked findings.
        </p>
      </div>
    </div>
  );
}

function RecommendationLoading() {
  return (
    <div className="recommendation-loading" aria-busy="true">
      <div>
        <span className="skeleton recommendation-skeleton-title" />
        <span className="skeleton recommendation-skeleton-copy" />
        <span className="skeleton recommendation-skeleton-copy short" />
      </div>
      <p>The Data Steward Agent is preparing structured proposals…</p>
    </div>
  );
}

function RecommendationEmpty() {
  return (
    <div className="recommendation-state">
      <span className="recommendation-state-mark empty" aria-hidden="true">
        0
      </span>
      <div>
        <strong>No recommendations were returned.</strong>
        <p>The deterministic findings remain available for manual review.</p>
      </div>
    </div>
  );
}

function RecommendationNotice({
  kind,
  title,
  message,
}: {
  kind: "configuration" | "error";
  title: string;
  message: string;
}) {
  return (
    <div className={`recommendation-state recommendation-${kind}`} role="alert">
      <span className="recommendation-state-mark" aria-hidden="true">
        {kind === "configuration" ? "CFG" : "!"}
      </span>
      <div>
        <strong>{title}</strong>
        <p>{message}</p>
      </div>
    </div>
  );
}

function RecommendationCard({
  recommendation,
  index,
  decision,
  onDecision,
}: {
  recommendation: RemediationRecommendation;
  index: number;
  decision: RecommendationDecision;
  onDecision: (decision: RecommendationDecision) => void;
}) {
  const confidence = Math.round(recommendation.confidence * 100);
  const finding = recommendation.related_finding;

  return (
    <article className="recommendation-card">
      <div className="recommendation-card-topline">
        <span className="recommendation-index">
          Recommendation {String(index).padStart(2, "0")}
        </span>
        <span
          className={`approval-badge ${
            recommendation.human_approval_required ? "required" : "not-required"
          }`}
        >
          {recommendation.human_approval_required
            ? "Human approval required"
            : "No approval required"}
        </span>
      </div>

      <h3>{recommendation.short_title}</h3>

      <div className="related-finding">
        <span>Related finding</span>
        <strong>{formatLabel(finding.type)}</strong>
        <code>
          {finding.file}
          {finding.affected_column ? ` / ${finding.affected_column}` : ""}
        </code>
      </div>

      <div className="recommendation-primary-action">
        <span>Proposed action</span>
        <p>{recommendation.proposed_action}</p>
      </div>

      <details className="recommendation-details">
        <summary>
          <span>View rationale and confidence</span>
          <small>{confidence}% confidence</small>
        </summary>
        <div className="recommendation-detail-body">
          <div className="recommendation-rationale">
            <span>Rationale</span>
            <p>{recommendation.rationale}</p>
          </div>
          <div className="recommendation-assumptions">
            <span>AI assumptions</span>
            {recommendation.assumptions.length > 0 ? (
              <ul>
                {recommendation.assumptions.map((assumption, assumptionIndex) => (
                  <li key={`${assumption}-${assumptionIndex}`}>{assumption}</li>
                ))}
              </ul>
            ) : (
              <p>No unresolved assumptions were declared for this proposal.</p>
            )}
          </div>
          <div className="confidence-row">
            <span>Confidence</span>
            <div
              className="confidence-track"
              role="progressbar"
              aria-label={`Recommendation confidence: ${confidence}%`}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={confidence}
            >
              <span style={{ width: `${confidence}%` }} />
            </div>
            <strong>{confidence}%</strong>
          </div>
        </div>
      </details>

      <div className="decision-row">
        <div className="current-decision">
          <span>Current decision</span>
          <strong className={`decision-label decision-${decision}`}>
            {formatLabel(decision)}
          </strong>
        </div>
        <div
          className="decision-actions"
          role="group"
          aria-label={`Review decision for ${recommendation.short_title}`}
        >
          {(["pending", "approved", "rejected"] as const).map((option) => (
            <button
              aria-pressed={decision === option}
              className={`decision-button decision-button-${option}`}
              key={option}
              onClick={() => onDecision(option)}
              type="button"
            >
              {formatLabel(option)}
            </button>
          ))}
        </div>
      </div>
    </article>
  );
}

function ApprovedRemediationPlan({
  items,
  datasetId,
  validationBaseline,
}: {
  items: Array<{
    id: string;
    recommendation: RemediationRecommendation;
    index: number;
  }>;
  datasetId?: string;
  validationBaseline: ValidationBaseline;
}) {
  return (
    <section className="approved-plan" aria-labelledby="approved-plan-title">
      <div className="approved-plan-heading">
        <div>
          <p className="section-kicker">Human-reviewed proposals</p>
          <h3 id="approved-plan-title">Approved remediation plan</h3>
        </div>
        <span>{items.length} approved</span>
      </div>

      {items.length === 0 ? (
        <div className="approved-plan-empty">
          No recommendations have been approved. Approving a proposal adds it
          here without applying any change to the dataset.
        </div>
      ) : (
        <div className="approved-plan-list">
          {items.map(({ id, recommendation, index }) => (
            <article className="approved-plan-item" key={id}>
              <span className="approved-plan-number">
                {String(index + 1).padStart(2, "0")}
              </span>
              <div>
                <h4>{recommendation.short_title}</h4>
                <p>{recommendation.proposed_action}</p>
                <code>
                  {recommendation.related_finding.file}
                  {recommendation.related_finding.affected_column
                    ? ` / ${recommendation.related_finding.affected_column}`
                    : ""}
                </code>
              </div>
            </article>
          ))}
        </div>
      )}

      <RemediationWorkflow
        approvedRecommendations={items.map((item) => item.recommendation)}
        datasetId={datasetId}
        key={items.map((item) => item.id).join("|") || "no-approvals"}
        validationBaseline={validationBaseline}
      />
    </section>
  );
}

function getRecommendationId(
  recommendation: RemediationRecommendation,
  index: number,
) {
  const finding = recommendation.related_finding;
  return [finding.type, finding.file, finding.affected_column ?? "file", index].join(
    "-",
  );
}

function formatLabel(value: string) {
  return value
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}
