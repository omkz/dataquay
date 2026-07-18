import Link from "next/link";

import { DatasetUploadForm } from "@/app/components/DatasetUploadForm";
import { WorkflowStepper } from "@/app/components/WorkflowStepper";
import type { WorkspaceListResult, WorkspaceSummary } from "@/lib/dataquay";

export function UploadLanding({
  workspaceResult,
}: {
  workspaceResult: WorkspaceListResult;
}) {
  return (
    <div className="app-shell upload-shell">
      <header className="site-header">
        <Link className="brand" href="/" aria-label="DataQuay upload">
          <span className="brand-mark" aria-hidden="true">DQ</span>
          <span>
            <strong>DataQuay</strong>
            <small>Research data stewardship</small>
          </span>
        </Link>
        <span className="environment-pill">Local workspace</span>
      </header>

      <main className="upload-main">
        <WorkflowStepper stage="upload" />
        <section className="upload-hero" aria-labelledby="upload-title">
          <div className="upload-hero-copy">
            <p className="eyebrow">New dataset</p>
            <h1 id="upload-title">Inspect a research dataset</h1>
            <p>
              Upload a ZIP archive to create an isolated, read-only original
              workspace and run deterministic inspection.
            </p>
          </div>
          <div className="upload-card">
            <div className="upload-card-heading">
              <span>01</span>
              <div>
                <h2>Select dataset archive</h2>
                <p>CSV and common research documentation formats are supported.</p>
              </div>
            </div>
            <DatasetUploadForm />
          </div>
        </section>

        <section className="upload-safety" aria-label="Upload safeguards">
          <SafetyItem mark="LOCK" title="Originals preserved">
            The archive and extracted files remain unchanged.
          </SafetyItem>
          <SafetyItem mark="SCAN" title="Archive validated">
            Unsafe paths, executable content, and oversized files are rejected.
          </SafetyItem>
          <SafetyItem mark="LOCAL" title="Stored locally">
            Dataset files stay local; PostgreSQL stores workflow metadata only.
          </SafetyItem>
        </section>

        <WorkspaceHistory result={workspaceResult} />

        <section className="demo-option">
          <div>
            <p className="section-kicker">Demo option</p>
            <h2>Explore without uploading</h2>
            <p>Open the synthetic soil-study dataset and its complete stewardship workflow.</p>
          </div>
          <Link className="demo-link" href="/?demo=sample">
            Open demo dataset
          </Link>
        </section>
      </main>

      <footer className="site-footer">
        <span>DataQuay deterministic inspection</span>
        <span>Local storage · No authentication</span>
      </footer>
    </div>
  );
}

function WorkspaceHistory({ result }: { result: WorkspaceListResult }) {
  return (
    <section className="workspace-history" aria-labelledby="workspace-history-title">
      <div className="workspace-history-heading">
        <div>
          <p className="section-kicker">Saved workspaces</p>
          <h2 id="workspace-history-title">Continue an unfinished workflow</h2>
          <p>Workflow metadata and review decisions survive application restarts.</p>
        </div>
        {result.ok ? <span>{result.data.length} saved</span> : null}
      </div>

      {!result.ok ? (
        <div className="workspace-history-error" role="status">
          <strong>Saved workspaces are unavailable.</strong>
          <p>{result.message}</p>
        </div>
      ) : result.data.length === 0 ? (
        <div className="workspace-history-empty">
          No uploaded workspaces yet. Upload a ZIP archive to create the first one.
        </div>
      ) : (
        <div className="workspace-list">
          {result.data.map((workspace) => (
            <WorkspaceCard key={workspace.dataset_id} workspace={workspace} />
          ))}
        </div>
      )}
    </section>
  );
}

function WorkspaceCard({ workspace }: { workspace: WorkspaceSummary }) {
  return (
    <Link
      className="workspace-card"
      href={`/?dataset=${encodeURIComponent(workspace.dataset_id)}`}
    >
      <div>
        <span className="workspace-status">{formatLabel(workspace.workflow_status)}</span>
        <h3>{formatLabel(workspace.dataset_name)}</h3>
        <p>{workspace.original_file_name}</p>
      </div>
      <dl>
        <div>
          <dt>Next stage</dt>
          <dd>{formatLabel(workspace.current_stage)}</dd>
        </div>
        <div>
          <dt>Files</dt>
          <dd>{workspace.file_count}</dd>
        </div>
        <div>
          <dt>Updated</dt>
          <dd>{formatTimestamp(workspace.updated_at)}</dd>
        </div>
      </dl>
      <span className="workspace-open">Reopen workflow →</span>
    </Link>
  );
}

function formatTimestamp(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(date);
}

function formatLabel(value: string) {
  return value
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function SafetyItem({
  mark,
  title,
  children,
}: {
  mark: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="safety-item">
      <span>{mark}</span>
      <div>
        <strong>{title}</strong>
        <p>{children}</p>
      </div>
    </div>
  );
}
