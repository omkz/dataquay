export default function Loading() {
  return (
    <main className="state-page" aria-live="polite" aria-busy="true">
      <div className="loading-shell">
        <div className="loading-heading">
          <span className="skeleton skeleton-label" />
          <span className="skeleton skeleton-title" />
          <span className="skeleton skeleton-copy" />
        </div>
        <div className="skeleton skeleton-panel" />
        <div className="loading-grid">
          <span className="skeleton skeleton-card" />
          <span className="skeleton skeleton-card" />
          <span className="skeleton skeleton-card" />
        </div>
        <p className="loading-message">Inspecting the sample dataset…</p>
      </div>
    </main>
  );
}
