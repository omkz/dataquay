"use client";

export default function ErrorPage({
  unstable_retry,
}: {
  error: Error & { digest?: string };
  unstable_retry: () => void;
}) {
  return (
    <main className="state-page">
      <div className="state-card error-card" role="alert">
        <span className="state-icon" aria-hidden="true">
          !
        </span>
        <p className="eyebrow">Unexpected error</p>
        <h1>The dataset overview could not be rendered.</h1>
        <p>Try the inspection again. No source files have been changed.</p>
        <button className="retry-link" type="button" onClick={unstable_retry}>
          Try again
        </button>
      </div>
    </main>
  );
}
