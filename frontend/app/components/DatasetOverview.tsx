import Link from "next/link";

import { RecommendationsPanel } from "@/app/components/RecommendationsPanel";
import type {
  DatasetInspection,
  InspectionFinding,
  InspectedFile,
  ReadinessStatus,
} from "@/lib/dataquay";

const readinessLabels: Record<ReadinessStatus, string> = {
  not_ready: "Not ready",
  needs_review: "Needs review",
  ready: "Ready",
};

const severityOrder = ["critical", "high", "medium", "low", "informational"];

export function DatasetOverview({
  inspection,
}: {
  inspection: DatasetInspection;
}) {
  const { summary, readiness, files, findings } = inspection;
  const nonCsvFileCount = summary.total_file_count - summary.csv_file_count;
  const severityEntries = Object.entries(readiness.finding_counts_by_severity).sort(
    ([left], [right]) =>
      severityOrder.indexOf(left) - severityOrder.indexOf(right),
  );

  return (
    <div className="app-shell">
      <header className="site-header">
        <Link className="brand" href="/" aria-label="DataQuay dataset overview">
          <span className="brand-mark" aria-hidden="true">
            DQ
          </span>
          <span>
            <strong>DataQuay</strong>
            <small>Research data stewardship</small>
          </span>
        </Link>
        <span className="environment-pill">Sample dataset</span>
      </header>

      <main className="overview-main">
        <section className="overview-heading" aria-labelledby="dataset-title">
          <div>
            <p className="eyebrow">Dataset inspection</p>
            <h1 id="dataset-title">{formatLabel(summary.dataset_name)}</h1>
            <p className="heading-copy">
              Deterministic inspection results for the complete sample dataset.
              Original source files remain unchanged.
            </p>
          </div>
          <div className="dataset-path">
            <span>Dataset</span>
            <code>{summary.dataset_name}</code>
          </div>
        </section>

        <section className="readiness-panel" aria-labelledby="readiness-title">
          <div className="readiness-copy">
            <p className="section-kicker">Readiness</p>
            <div className="readiness-title-row">
              <span
                className={`status-indicator status-${readiness.status}`}
                aria-hidden="true"
              />
              <h2 id="readiness-title">
                {readinessLabels[readiness.status]}
              </h2>
            </div>
            <p>
              {readiness.human_review_required
                ? "Human review is required before this dataset can progress."
                : "No current findings require human review."}
            </p>
          </div>
          <div className="readiness-metrics">
            <Metric
              value={readiness.blocker_count}
              label="Publication blockers"
              emphasis={readiness.blocker_count > 0}
            />
            <Metric
              value={readiness.total_finding_count}
              label="Total findings"
            />
          </div>
        </section>

        <section className="summary-grid" aria-label="Dataset summary">
          <SummaryCard
            label="Files inventoried"
            value={summary.total_file_count}
            detail="Across the sample directory"
          />
          <SummaryCard
            label="CSV profiles"
            value={summary.csv_file_count}
            detail={`${nonCsvFileCount} non-CSV ${pluralize("file", nonCsvFileCount)}`}
          />
          <SummaryCard
            label="Dataset size"
            value={formatBytes(summary.total_size_bytes)}
            detail="Original files, read only"
          />
        </section>

        <section className="content-section" aria-labelledby="severity-title">
          <div className="section-heading">
            <div>
              <p className="section-kicker">Risk distribution</p>
              <h2 id="severity-title">Findings by severity</h2>
            </div>
            <span className="section-meta">
              {readiness.total_finding_count} total
            </span>
          </div>
          <div className="severity-grid">
            {severityEntries.map(([severity, count]) => (
              <div className="severity-card" key={severity}>
                <span className={`severity-dot severity-${severity}`} />
                <div>
                  <strong>{count}</strong>
                  <span>{formatLabel(severity)}</span>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="content-section" aria-labelledby="files-title">
          <div className="section-heading">
            <div>
              <p className="section-kicker">Inventory</p>
              <h2 id="files-title">Dataset files</h2>
            </div>
            <span className="section-meta">{files.length} files</span>
          </div>
          <div className="table-frame">
            <table>
              <thead>
                <tr>
                  <th scope="col">File</th>
                  <th scope="col">Format</th>
                  <th scope="col">Size</th>
                  <th scope="col">Inspection</th>
                </tr>
              </thead>
              <tbody>
                {files.map((file) => (
                  <FileRow file={file} key={file.relative_path} />
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="content-section" aria-labelledby="findings-title">
          <div className="section-heading">
            <div>
              <p className="section-kicker">Evidence</p>
              <h2 id="findings-title">Structured findings</h2>
            </div>
            <span className="section-meta">Deterministic rules</span>
          </div>
          <div className="findings-list">
            {findings.map((finding, index) => (
              <FindingCard
                finding={finding}
                index={index + 1}
                key={`${finding.type}-${finding.file}-${finding.affected_column ?? "file"}`}
              />
            ))}
          </div>
        </section>

        <RecommendationsPanel />
      </main>

      <footer className="site-footer">
        <span>DataQuay deterministic inspection</span>
        <span>Sample data · Read only</span>
      </footer>
    </div>
  );
}

function Metric({
  value,
  label,
  emphasis = false,
}: {
  value: number;
  label: string;
  emphasis?: boolean;
}) {
  return (
    <div className={`metric ${emphasis ? "metric-emphasis" : ""}`}>
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function SummaryCard({
  label,
  value,
  detail,
}: {
  label: string;
  value: number | string;
  detail: string;
}) {
  return (
    <div className="summary-card">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  );
}

function FileRow({ file }: { file: InspectedFile }) {
  return (
    <tr>
      <td>
        <div className="file-name">
          <span className="file-icon" aria-hidden="true">
            {file.extension === ".csv" ? "CSV" : "DOC"}
          </span>
          <span>
            <strong>{file.file_name}</strong>
            <small>{file.relative_path}</small>
          </span>
        </div>
      </td>
      <td>
        <span className="format-pill">
          {file.extension.replace(".", "").toUpperCase() || "FILE"}
        </span>
      </td>
      <td>{formatBytes(file.size_bytes)}</td>
      <td>
        {file.csv_profile ? (
          <span className="profile-summary">
            <strong>{file.csv_profile.row_count}</strong> rows ·{" "}
            <strong>{file.csv_profile.column_count}</strong> columns
          </span>
        ) : (
          <span className="inventory-only">Inventory only</span>
        )}
      </td>
    </tr>
  );
}

function FindingCard({
  finding,
  index,
}: {
  finding: InspectionFinding;
  index: number;
}) {
  return (
    <article className="finding-card">
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
        <dl className="evidence-grid">
          {Object.entries(finding.evidence).map(([label, value]) => (
            <div key={label}>
              <dt>{formatLabel(label)}</dt>
              <dd>{formatEvidence(value)}</dd>
            </div>
          ))}
        </dl>
      </div>
    </article>
  );
}

function formatEvidence(value: string | number | string[]) {
  if (Array.isArray(value)) {
    return (
      <span className="evidence-values">
        {value.map((item) => (
          <code key={item}>{item}</code>
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

function formatBytes(bytes: number) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  return `${(bytes / 1024).toFixed(1)} KB`;
}

function pluralize(word: string, count: number) {
  return count === 1 ? word : `${word}s`;
}
