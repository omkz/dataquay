"use client";

import { useActionState } from "react";

import { generateRecommendations } from "@/app/actions/recommendations";
import type {
  RecommendationActionState,
  RemediationRecommendation,
} from "@/lib/dataquay";

const initialState: RecommendationActionState = {
  status: "idle",
  recommendations: [],
};

export function RecommendationsPanel() {
  const [state, formAction, pending] = useActionState(
    generateRecommendations,
    initialState,
  );

  return (
    <section className="content-section" aria-labelledby="recommendations-title">
      <div className="section-heading recommendation-heading">
        <div>
          <p className="section-kicker">Data Steward Agent</p>
          <h2 id="recommendations-title">Remediation recommendations</h2>
          <p className="section-description">
            Generate proposal-only guidance from the deterministic findings. No
            dataset files will be changed.
          </p>
        </div>
        <form action={formAction}>
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
            ) : state.status === "success" ? (
              "Generate again"
            ) : (
              "Generate recommendations"
            )}
          </button>
        </form>
      </div>

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
          <div className="recommendation-list">
            {state.recommendations.map((recommendation, index) => (
              <RecommendationCard
                key={`${recommendation.related_finding.type}-${recommendation.related_finding.file}-${index}`}
                recommendation={recommendation}
                index={index + 1}
              />
            ))}
          </div>
        )}
      </div>
    </section>
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
}: {
  recommendation: RemediationRecommendation;
  index: number;
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

      <div className="recommendation-copy-grid">
        <div>
          <span>Rationale</span>
          <p>{recommendation.rationale}</p>
        </div>
        <div className="proposed-action">
          <span>Proposed action</span>
          <p>{recommendation.proposed_action}</p>
        </div>
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
    </article>
  );
}

function formatLabel(value: string) {
  return value
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}
