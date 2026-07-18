"use client";

import { useMemo, useState } from "react";

import type { InspectionFinding } from "@/lib/dataquay";

type FindingScope = "blockers" | "other" | "all";

const blockerSeverities = new Set(["critical", "high"]);
const severityOrder = ["critical", "high", "medium", "low", "informational"];

export function FindingsExplorer({
  findings,
}: {
  findings: InspectionFinding[];
}) {
  const blockerCount = findings.filter((finding) =>
    blockerSeverities.has(finding.severity),
  ).length;
  const otherCount = findings.length - blockerCount;
  const [scope, setScope] = useState<FindingScope>(
    blockerCount > 0 ? "blockers" : "all",
  );
  const [type, setType] = useState("all");

  const findingTypes = useMemo(
    () => [...new Set(findings.map((finding) => finding.type))].sort(),
    [findings],
  );
  const visibleFindings = useMemo(
    () =>
      findings
        .map((finding, originalIndex) => ({ finding, originalIndex }))
        .filter(({ finding }) => {
          const isBlocker = blockerSeverities.has(finding.severity);
          const matchesScope =
            scope === "all" ||
            (scope === "blockers" && isBlocker) ||
            (scope === "other" && !isBlocker);
          return matchesScope && (type === "all" || finding.type === type);
        })
        .sort(
          (left, right) =>
            severityRank(left.finding.severity) -
              severityRank(right.finding.severity) ||
            left.originalIndex - right.originalIndex,
        ),
    [findings, scope, type],
  );

  if (findings.length === 0) {
    return (
      <div className="empty-dashboard-state">
        No structured findings to review.
      </div>
    );
  }

  return (
    <div className="findings-explorer">
      <div className="finding-filters" aria-label="Filter findings">
        <div className="finding-scope" role="group" aria-label="Finding scope">
          <FilterButton
            active={scope === "blockers"}
            count={blockerCount}
            label="Blockers"
            onClick={() => setScope("blockers")}
            tone="blocker"
          />
          <FilterButton
            active={scope === "other"}
            count={otherCount}
            label="Other findings"
            onClick={() => setScope("other")}
          />
          <FilterButton
            active={scope === "all"}
            count={findings.length}
            label="All"
            onClick={() => setScope("all")}
          />
        </div>
        <label className="finding-type-filter">
          <span>Finding type</span>
          <select value={type} onChange={(event) => setType(event.target.value)}>
            <option value="all">All types</option>
            {findingTypes.map((findingType) => (
              <option key={findingType} value={findingType}>
                {formatLabel(findingType)}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="findings-list" aria-live="polite">
        {visibleFindings.length > 0 ? (
          visibleFindings.map(({ finding, originalIndex }, index) => (
            <FindingCard
              finding={finding}
              index={index + 1}
              key={`${finding.type}-${finding.file}-${finding.affected_column ?? "file"}-${originalIndex}`}
            />
          ))
        ) : (
          <div className="empty-dashboard-state compact">
            No findings match these filters.
          </div>
        )}
      </div>
    </div>
  );
}

function FilterButton({
  active,
  count,
  label,
  onClick,
  tone,
}: {
  active: boolean;
  count: number;
  label: string;
  onClick: () => void;
  tone?: "blocker";
}) {
  return (
    <button
      aria-pressed={active}
      className={`finding-filter-button ${tone ? `finding-filter-${tone}` : ""}`}
      onClick={onClick}
      type="button"
    >
      {label}
      <span>{count}</span>
    </button>
  );
}

function FindingCard({
  finding,
  index,
}: {
  finding: InspectionFinding;
  index: number;
}) {
  const evidenceEntries = Object.entries(finding.evidence);
  const isBlocker = blockerSeverities.has(finding.severity);

  return (
    <article className={`finding-card ${isBlocker ? "finding-card-blocker" : ""}`}>
      <div className="finding-number">{String(index).padStart(2, "0")}</div>
      <div className="finding-body">
        <div className="finding-header">
          <div className="finding-badges">
            <span className={`severity-badge severity-${finding.severity}`}>
              {formatLabel(finding.severity)}
            </span>
            <span className="finding-type">{formatLabel(finding.type)}</span>
          </div>
          <div className="finding-location">
            <span>{finding.file}</span>
            <span aria-hidden="true">/</span>
            <strong>{finding.affected_column ?? "Entire file"}</strong>
          </div>
        </div>
        <p className="finding-message">{finding.message}</p>
        {evidenceEntries.length > 0 ? (
          <details className="finding-evidence">
            <summary>
              <span>View detailed evidence</span>
              <small>
                {evidenceEntries.length} {evidenceEntries.length === 1 ? "field" : "fields"}
              </small>
            </summary>
            <dl className="evidence-grid">
              {evidenceEntries.map(([label, value]) => (
                <div key={label}>
                  <dt>{formatLabel(label)}</dt>
                  <dd>{formatEvidence(value)}</dd>
                </div>
              ))}
            </dl>
          </details>
        ) : null}
      </div>
    </article>
  );
}

function severityRank(severity: string) {
  const rank = severityOrder.indexOf(severity);
  return rank === -1 ? severityOrder.length : rank;
}

function formatEvidence(value: string | number | string[]) {
  if (Array.isArray(value)) {
    return (
      <span className="evidence-values">
        {value.map((item, index) => (
          <code key={`${item}-${index}`}>{item}</code>
        ))}
      </span>
    );
  }

  return typeof value === "number" ? value.toLocaleString() : value;
}

function formatLabel(value: string) {
  return value
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}
