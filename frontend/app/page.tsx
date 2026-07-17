import Link from "next/link";
import { connection } from "next/server";

import { DatasetOverview } from "@/app/components/DatasetOverview";
import { getSampleDatasetInspection } from "@/lib/dataquay";

export default async function Home() {
  await connection();
  const result = await getSampleDatasetInspection();

  if (!result.ok) {
    return <InspectionError message={result.message} />;
  }

  return <DatasetOverview inspection={result.data} />;
}

function InspectionError({ message }: { message: string }) {
  return (
    <main className="state-page">
      <div className="state-card error-card" role="alert">
        <span className="state-icon" aria-hidden="true">
          !
        </span>
        <p className="eyebrow">Inspection unavailable</p>
        <h1>We could not load the sample dataset.</h1>
        <p>{message}</p>
        <Link className="retry-link" href="/">
          Try again
        </Link>
      </div>
    </main>
  );
}
