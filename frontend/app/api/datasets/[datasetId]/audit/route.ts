import {
  getBackendUrl,
  isDatasetIdentifier,
} from "@/lib/dataquay";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ datasetId: string }> },
) {
  const { datasetId } = await params;
  if (!isDatasetIdentifier(datasetId)) {
    return Response.json(
      { detail: "The uploaded dataset identifier is invalid." },
      { status: 404 },
    );
  }

  try {
    const response = await fetch(
      `${getBackendUrl()}/api/audit/datasets/${encodeURIComponent(datasetId)}`,
      { cache: "no-store", headers: { Accept: "application/json" } },
    );
    return new Response(await response.text(), {
      status: response.status,
      headers: {
        "Content-Type": response.headers.get("content-type") ?? "application/json",
      },
    });
  } catch {
    return Response.json(
      {
        detail:
          "DataQuay could not reach the audit service. Confirm that the backend is running and try again.",
      },
      { status: 502 },
    );
  }
}
