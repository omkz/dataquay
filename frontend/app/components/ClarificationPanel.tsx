"use client";

import { useCallback, useEffect, useState, useTransition } from "react";

import {
  loadDatasetClarifications,
  updateDatasetClarification,
} from "@/app/actions/clarifications";
import { notifyDatasetAuditUpdated } from "@/app/components/AuditTimeline";
import { reportWorkflowProgress } from "@/app/components/WorkflowStepper";
import type {
  ClarificationQuestion,
  DatasetClarifications,
} from "@/lib/dataquay";

export const DATASET_CLARIFICATIONS_UPDATED_EVENT =
  "dataquay:clarifications-updated";

type ClarificationState =
  | { status: "loading" }
  | { status: "success"; data: DatasetClarifications }
  | { status: "error"; message: string };

export function ClarificationPanel({ datasetId }: { datasetId: string }) {
  const [state, setState] = useState<ClarificationState>({ status: "loading" });
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [activeQuestion, setActiveQuestion] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  const loadClarifications = useCallback(async () => {
    setState({ status: "loading" });
    const result = await loadDatasetClarifications(datasetId);
    if (!result.ok) {
      setState({ status: "error", message: result.message });
      return;
    }
    setState({ status: "success", data: result.data });
    setDrafts(buildDrafts(result.data));
    reportClarificationProgress(datasetId, result.data);
    notifyDatasetAuditUpdated(datasetId);
  }, [datasetId]);

  useEffect(() => {
    const initialLoad = window.setTimeout(() => void loadClarifications(), 0);
    return () => window.clearTimeout(initialLoad);
  }, [loadClarifications]);

  function updateQuestion(
    question: ClarificationQuestion,
    decision: "answer" | "defer",
  ) {
    const answer = drafts[question.question_id]?.trim() ?? "";
    if (decision === "answer" && !answer) {
      setNotice("Enter a focused research-context answer before saving it.");
      return;
    }
    setActiveQuestion(question.question_id);
    setNotice(null);
    startTransition(async () => {
      const result = await updateDatasetClarification(
        datasetId,
        question.question_id,
        decision,
        answer,
      );
      setActiveQuestion(null);
      if (!result.ok) {
        setNotice(result.message);
        return;
      }
      setState({ status: "success", data: result.data });
      setDrafts(buildDrafts(result.data));
      reportClarificationProgress(datasetId, result.data);
      setNotice(
        decision === "answer"
          ? "Confirmed information saved. Refresh recommendations to use it."
          : "Question deferred. AI must continue treating this context as unknown.",
      );
      notifyDatasetAuditUpdated(datasetId);
      window.dispatchEvent(
        new CustomEvent(DATASET_CLARIFICATIONS_UPDATED_EVENT, {
          detail: { datasetId },
        }),
      );
    });
  }

  return (
    <section
      className="content-section section-anchor"
      id="clarifications"
      aria-labelledby="clarification-title"
    >
      <div className="section-heading clarification-heading">
        <div>
          <p className="section-kicker">Research context</p>
          <h2 id="clarification-title">Clarification questions</h2>
          <p className="section-description">
            Resolve ambiguity before asking AI for updated proposals. Responses
            inform recommendations only and never authorize dataset changes.
          </p>
        </div>
        {state.status === "success" ? (
          <span className="section-meta">
            {state.data.summary.unanswered_count} unanswered
          </span>
        ) : null}
      </div>

      {state.status === "loading" ? (
        <ClarificationLoading />
      ) : state.status === "error" ? (
        <div className="clarification-state error" role="alert">
          <strong>Clarification questions unavailable</strong>
          <p>{state.message}</p>
          <button onClick={() => void loadClarifications()} type="button">
            Try again
          </button>
        </div>
      ) : state.data.questions.length === 0 ? (
        <div className="clarification-state">
          <strong>No research-context questions are required</strong>
          <p>The current findings do not match an ambiguous finding category.</p>
        </div>
      ) : (
        <div className="clarification-workspace">
          <ClarificationSummary clarifications={state.data} />
          {notice ? (
            <div className="clarification-notice" aria-live="polite">
              {notice}
            </div>
          ) : null}
          <div className="clarification-list">
            {state.data.questions.map((question, index) => (
              <ClarificationCard
                draft={drafts[question.question_id] ?? ""}
                index={index + 1}
                isPending={
                  isPending && activeQuestion === question.question_id
                }
                key={`${question.question_id}-${question.status}`}
                onAnswer={() => updateQuestion(question, "answer")}
                onDefer={() => updateQuestion(question, "defer")}
                onDraftChange={(value) =>
                  setDrafts((current) => ({
                    ...current,
                    [question.question_id]: value,
                  }))
                }
                question={question}
              />
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function ClarificationSummary({
  clarifications,
}: {
  clarifications: DatasetClarifications;
}) {
  const { summary } = clarifications;
  return (
    <div className="clarification-summary" aria-label="Clarification status">
      <ClarificationCount
        count={summary.answered_count}
        detail="Saved human answers"
        label="Confirmed information"
        status="answered"
      />
      <ClarificationCount
        count={summary.unanswered_count}
        detail="Still unknown"
        label="Unanswered questions"
        status="unanswered"
      />
      <ClarificationCount
        count={summary.deferred_count}
        detail="Intentionally unresolved"
        label="Deferred questions"
        status="deferred"
      />
      <div className="clarification-assumption-key">
        <span>AI assumptions</span>
        <p>
          Any proposal that relies on unanswered or deferred context must label
          that dependency as an AI assumption.
        </p>
      </div>
    </div>
  );
}

function ClarificationCount({
  count,
  detail,
  label,
  status,
}: {
  count: number;
  detail: string;
  label: string;
  status: "answered" | "unanswered" | "deferred";
}) {
  return (
    <div className={`clarification-count clarification-count-${status}`}>
      <span className="clarification-count-dot" aria-hidden="true" />
      <div>
        <strong>{count}</strong>
        <span>{label}</span>
        <small>{detail}</small>
      </div>
    </div>
  );
}

function ClarificationCard({
  draft,
  index,
  isPending,
  onAnswer,
  onDefer,
  onDraftChange,
  question,
}: {
  draft: string;
  index: number;
  isPending: boolean;
  onAnswer: () => void;
  onDefer: () => void;
  onDraftChange: (value: string) => void;
  question: ClarificationQuestion;
}) {
  return (
    <details
      className={`clarification-card clarification-${question.status}`}
      open={question.status === "unanswered"}
    >
      <summary className="clarification-card-summary">
        <span className="clarification-card-topline">
          <span>Question {String(index).padStart(2, "0")}</span>
          <strong>{statusLabels[question.status]}</strong>
        </span>
        <span className="clarification-question-text">{question.question}</span>
        <span className="clarification-location">
          <span>{formatLabel(question.related_finding.type)}</span>
          <code>
            {question.related_finding.file}
            {question.related_finding.affected_column
              ? ` / ${question.related_finding.affected_column}`
              : ""}
          </code>
        </span>
      </summary>
      <div className="clarification-card-content">
        <details className="clarification-why">
          <summary>Why this context is needed</summary>
          <p>{question.why_this_matters}</p>
        </details>

        {question.status === "answered" && question.answer ? (
          <div className="confirmed-information">
            <span>Confirmed information</span>
            <p>{question.answer}</p>
          </div>
        ) : question.status === "deferred" ? (
          <div className="deferred-information">
            Deferred by the reviewer. This remains unknown until answered.
          </div>
        ) : null}

        <label className="clarification-answer">
        <span>
          {question.status === "answered" ? "Update answer" : "Your answer"}
        </span>
        <textarea
          disabled={isPending}
          maxLength={2000}
          onChange={(event) => onDraftChange(event.target.value)}
          placeholder="Add research context, coding conventions, or an approved handling decision. Do not paste raw rows or personal data."
          rows={3}
          value={draft}
        />
        </label>
        <div className="clarification-actions">
        <button
          className="clarification-answer-button"
          disabled={isPending}
          onClick={onAnswer}
          type="button"
        >
          {isPending ? "Saving…" : "Save as confirmed"}
        </button>
        <button
          className="clarification-defer-button"
          disabled={isPending || question.status === "deferred"}
          onClick={onDefer}
          type="button"
        >
          {question.status === "deferred" ? "Deferred" : "Defer question"}
        </button>
        </div>
      </div>
    </details>
  );
}

function ClarificationLoading() {
  return (
    <div className="clarification-loading" aria-busy="true">
      <span className="skeleton" />
      <span className="skeleton" />
      <span className="skeleton" />
    </div>
  );
}

function buildDrafts(clarifications: DatasetClarifications) {
  return Object.fromEntries(
    clarifications.questions.map((question) => [
      question.question_id,
      question.answer ?? "",
    ]),
  );
}

function formatLabel(value: string) {
  return value
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function reportClarificationProgress(
  datasetId: string,
  clarifications: DatasetClarifications,
) {
  const unresolved = clarifications.summary.unanswered_count;
  reportWorkflowProgress(
    datasetId,
    "clarifications",
    unresolved === 0 ? "complete" : "active",
    unresolved === 0
      ? "All clarification questions are answered or deferred. Generate recommendations next."
      : `${unresolved} clarification question${unresolved === 1 ? " remains" : "s remain"} unanswered. Answer, defer, or continue with explicit AI assumptions.`,
  );
}

const statusLabels = {
  answered: "Confirmed",
  unanswered: "Unanswered",
  deferred: "Deferred",
} as const;
