import Link from "next/link";

import { AuditTimeline } from "@/app/components/AuditTimeline";
import { ClarificationPanel } from "@/app/components/ClarificationPanel";
import { FindingsExplorer } from "@/app/components/FindingsExplorer";
import { RecommendationsPanel } from "@/app/components/RecommendationsPanel";
import { SectionNavigator } from "@/app/components/SectionNavigator";
import { WorkflowStepper } from "@/app/components/WorkflowStepper";
import type {
  DatasetInspection,
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
  mode,
  datasetId,
}: {
  inspection: DatasetInspection;
  mode: "sample" | "uploaded";
  datasetId?: string;
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
        <div className="header-actions">
          <Link className="header-link" href="/">Start over</Link>
          <span className="environment-pill">
            {mode === "sample" ? "Sample demo" : "Uploaded dataset"}
          </span>
        </div>
      </header>

      <main className="overview-main">
        <section className="overview-heading" aria-labelledby="dataset-title">
          <div>
            <p className="eyebrow">Dataset inspection</p>
            <h1 id="dataset-title">{formatLabel(summary.dataset_name)}</h1>
            <p className="heading-copy">
              Deterministic inspection results for the complete {mode === "sample" ? "sample dataset" : "uploaded dataset"}.
              Original source files remain unchanged.
            </p>
          </div>
          <div className="dataset-path">
            <span>{datasetId ? "Dataset ID" : "Dataset"}</span>
            <code>{datasetId ?? summary.dataset_name}</code>
          </div>
        </section>

        <WorkflowStepper datasetId={datasetId} />
        <SectionNavigator uploaded={Boolean(datasetId)} />

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
            detail={mode === "sample" ? "Across the sample directory" : "Across extracted originals"}
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

        <section className="content-section secondary-section" aria-labelledby="severity-title">
          <details>
            <summary className="section-heading">
              <div>
                <p className="section-kicker">Risk distribution</p>
                <h2 id="severity-title">Findings by severity</h2>
              </div>
              <span className="section-meta">
                {readiness.total_finding_count} total · Expand
              </span>
            </summary>
            <div className="secondary-section-content severity-grid">
            {severityEntries.length > 0 ? (
              severityEntries.map(([severity, count]) => (
                <div className="severity-card" key={severity}>
                  <span className={`severity-dot severity-${severity}`} />
                  <div>
                    <strong>{count}</strong>
                    <span>{formatLabel(severity)}</span>
                  </div>
                </div>
              ))
            ) : (
              <div className="empty-dashboard-state">
                No findings were detected in this dataset.
              </div>
            )}
            </div>
          </details>
        </section>

        <section className="content-section secondary-section" aria-labelledby="files-title">
          <details>
            <summary className="section-heading">
              <div>
                <p className="section-kicker">Inventory</p>
                <h2 id="files-title">Dataset files</h2>
              </div>
              <span className="section-meta">{files.length} files · Expand</span>
            </summary>
            <div className="secondary-section-content table-frame">
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
          </details>
        </section>

        <section className="content-section section-anchor" id="findings" aria-labelledby="findings-title">
          <div className="section-heading">
            <div>
              <p className="section-kicker">Evidence</p>
              <h2 id="findings-title">Structured findings</h2>
            </div>
            <span className="section-meta">Deterministic rules</span>
          </div>
          <FindingsExplorer findings={findings} />
        </section>

        {datasetId ? <ClarificationPanel datasetId={datasetId} /> : null}

        <RecommendationsPanel
          datasetId={datasetId}
          validationBaseline={{
            blockerCount: readiness.blocker_count,
            readinessStatus: readiness.status,
            totalFindingCount: readiness.total_finding_count,
          }}
        />
        {datasetId ? <AuditTimeline datasetId={datasetId} /> : null}
      </main>

      <footer className="site-footer">
        <span>DataQuay deterministic inspection</span>
        <span>{mode === "sample" ? "Sample demo" : "Uploaded originals"} · Read only</span>
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
