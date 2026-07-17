import { getBackendUrl } from "@/lib/dataquay";

export async function GET() {
  try {
    const response = await fetch(
      `${getBackendUrl()}/api/package/sample-dataset/download`,
      { cache: "no-store", headers: { Accept: "application/zip" } },
    );

    if (!response.ok || !response.body) {
      const detail = await readErrorDetail(response);
      return Response.json(
        {
          detail:
            detail ??
            "The package download is unavailable. Generate the package first.",
        },
        { status: response.status || 502 },
      );
    }

    return new Response(response.body, {
      status: 200,
      headers: {
        "Content-Type": response.headers.get("content-type") ?? "application/zip",
        "Content-Disposition":
          response.headers.get("content-disposition") ??
          'attachment; filename="soil-study.zip"',
        ...(response.headers.get("content-length")
          ? { "Content-Length": response.headers.get("content-length")! }
          : {}),
      },
    });
  } catch {
    return Response.json(
      {
        detail:
          "DataQuay could not reach the package download service. Confirm that the backend is running and try again.",
      },
      { status: 502 },
    );
  }
}

async function readErrorDetail(response: Response): Promise<string | null> {
  try {
    const payload: unknown = await response.json();
    if (
      payload &&
      typeof payload === "object" &&
      "detail" in payload &&
      typeof payload.detail === "string"
    ) {
      return payload.detail;
    }
  } catch {
    return null;
  }
  return null;
}
