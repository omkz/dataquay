import Link from "next/link";

import { DatasetUploadForm } from "@/app/components/DatasetUploadForm";
import { WorkflowStepper } from "@/app/components/WorkflowStepper";

export function UploadLanding() {
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
            This iteration uses an isolated local workspace without a database.
          </SafetyItem>
        </section>

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
