import Link from "next/link";

import { DatasetOverview } from "@/app/components/DatasetOverview";
import { UploadLanding } from "@/app/components/UploadLanding";
import {
  getSampleDatasetInspection,
  getUploadedDatasetInspection,
} from "@/lib/dataquay";

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<{
    dataset?: string | string[];
    demo?: string | string[];
  }>;
}) {
  const query = await searchParams;
  const datasetId = typeof query.dataset === "string" ? query.dataset : null;
  const demo = query.demo === "sample";

  if (!datasetId && !demo) {
    return <UploadLanding />;
  }

  const result = datasetId
    ? await getUploadedDatasetInspection(datasetId)
    : await getSampleDatasetInspection();

  if (!result.ok) {
    return (
      <InspectionError
        message={result.message}
        retryHref={datasetId ? `/?dataset=${encodeURIComponent(datasetId)}` : "/?demo=sample"}
        target={datasetId ? "uploaded dataset" : "sample demo dataset"}
      />
    );
  }

  return (
    <DatasetOverview
      datasetId={datasetId ?? undefined}
      inspection={result.data}
      mode={datasetId ? "uploaded" : "sample"}
    />
  );
}

function InspectionError({
  message,
  retryHref,
  target,
}: {
  message: string;
  retryHref: string;
  target: string;
}) {
  return (
    <main className="state-page">
      <div className="state-card error-card" role="alert">
        <span className="state-icon" aria-hidden="true">
          !
        </span>
        <p className="eyebrow">Inspection unavailable</p>
        <h1>We could not load the {target}.</h1>
        <p>{message}</p>
        <Link className="retry-link" href={retryHref}>
          Try again
        </Link>
        <Link className="state-secondary-link" href="/">
          Return to upload
        </Link>
      </div>
    </main>
  );
}
