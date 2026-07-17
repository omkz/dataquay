import { getBackendUrl } from "@/lib/dataquay";

const MAX_UPLOAD_SIZE_BYTES = 25 * 1024 * 1024;

export async function POST(request: Request) {
  try {
    const incomingForm = await request.formData();
    const file = incomingForm.get("file");
    if (!(file instanceof File)) {
      return Response.json(
        { detail: "Select a ZIP dataset before uploading." },
        { status: 400 },
      );
    }
    if (!file.name.toLowerCase().endsWith(".zip")) {
      return Response.json(
        { detail: "Only ZIP dataset uploads are supported." },
        { status: 415 },
      );
    }
    if (file.size > MAX_UPLOAD_SIZE_BYTES) {
      return Response.json(
        { detail: "ZIP uploads must not exceed 25 MB." },
        { status: 413 },
      );
    }

    const backendForm = new FormData();
    backendForm.append("file", file, file.name);
    const response = await fetch(`${getBackendUrl()}/api/datasets/upload`, {
      method: "POST",
      cache: "no-store",
      headers: { Accept: "application/json" },
      body: backendForm,
    });
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
          "DataQuay could not reach the upload service. Confirm that the backend is running and try again.",
      },
      { status: 502 },
    );
  }
}
