"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { isDatasetUploadResponse } from "@/lib/dataquay";

const MAX_UPLOAD_SIZE_BYTES = 25 * 1024 * 1024;

type UploadState =
  | { status: "idle" }
  | { status: "uploading"; progress: number }
  | { status: "inspecting" }
  | { status: "error"; message: string };

export function DatasetUploadForm() {
  const router = useRouter();
  const requestRef = useRef<XMLHttpRequest | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [state, setState] = useState<UploadState>({ status: "idle" });
  const busy = state.status === "uploading" || state.status === "inspecting";

  useEffect(() => {
    return () => requestRef.current?.abort();
  }, []);

  function selectFile(selectedFile: File | null) {
    if (!selectedFile) {
      setFile(null);
      setState({ status: "idle" });
      return;
    }
    const validationError = validateFile(selectedFile);
    if (validationError) {
      setFile(null);
      setState({ status: "error", message: validationError });
      return;
    }
    setFile(selectedFile);
    setState({ status: "idle" });
  }

  function uploadDataset() {
    if (!file || busy) return;
    const request = new XMLHttpRequest();
    requestRef.current = request;
    setState({ status: "uploading", progress: 0 });
    request.open("POST", "/api/datasets/upload");
    request.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) {
        setState({
          status: "uploading",
          progress: Math.min(99, Math.round((event.loaded / event.total) * 100)),
        });
      }
    });
    request.addEventListener("load", () => {
      requestRef.current = null;
      const payload = parseJson(request.responseText);
      if (request.status === 201 && isDatasetUploadResponse(payload)) {
        setState({ status: "inspecting" });
        router.push(`/?dataset=${encodeURIComponent(payload.dataset_id)}`);
        return;
      }
      setState({
        status: "error",
        message: getUploadError(
          payload,
          `The upload service returned HTTP ${request.status}.`,
        ),
      });
    });
    request.addEventListener("error", () => {
      requestRef.current = null;
      setState({
        status: "error",
        message:
          "The upload could not be completed. Check the backend connection and try again.",
      });
    });
    request.addEventListener("abort", () => {
      requestRef.current = null;
    });

    const formData = new FormData();
    formData.append("file", file, file.name);
    request.send(formData);
  }

  return (
    <div className="upload-form">
      <label className={`upload-picker ${busy ? "disabled" : ""}`}>
        <input
          accept=".zip,application/zip,application/x-zip-compressed"
          disabled={busy}
          onChange={(event) => selectFile(event.target.files?.[0] ?? null)}
          type="file"
        />
        <span className="upload-picker-mark" aria-hidden="true">ZIP</span>
        <span className="upload-picker-copy">
          <strong>{file ? file.name : "Choose a dataset ZIP"}</strong>
          <small>
            {file
              ? `${formatBytes(file.size)} selected`
              : "Maximum archive size 25 MB"}
          </small>
        </span>
        <span className="upload-browse">Browse</span>
      </label>

      {state.status === "uploading" ? (
        <div className="upload-progress" aria-live="polite">
          <div>
            <strong>Uploading archive</strong>
            <span>{state.progress}%</span>
          </div>
          <div
            className="upload-progress-track"
            role="progressbar"
            aria-label="Dataset upload progress"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={state.progress}
          >
            <span style={{ width: `${state.progress}%` }} />
          </div>
          <p>The backend will validate and extract the ZIP after transfer.</p>
        </div>
      ) : state.status === "inspecting" ? (
        <div className="upload-progress upload-inspecting" aria-live="polite">
          <div>
            <strong>Upload complete</strong>
            <span className="button-spinner" aria-hidden="true" />
          </div>
          <p>Opening the isolated workspace and inspecting the dataset…</p>
        </div>
      ) : state.status === "error" ? (
        <div className="upload-error" role="alert">
          <strong>Upload unavailable</strong>
          <p>{state.message}</p>
        </div>
      ) : null}

      <button
        className="upload-submit"
        disabled={!file || busy}
        onClick={uploadDataset}
        type="button"
      >
        {state.status === "uploading"
          ? "Uploading…"
          : state.status === "inspecting"
            ? "Inspecting…"
            : "Upload and inspect"}
      </button>
    </div>
  );
}

function validateFile(file: File) {
  if (!file.name.toLowerCase().endsWith(".zip")) {
    return "Select a ZIP archive containing the research dataset.";
  }
  if (file.size === 0) {
    return "The selected ZIP file is empty.";
  }
  if (file.size > MAX_UPLOAD_SIZE_BYTES) {
    return "The selected ZIP exceeds the 25 MB upload limit.";
  }
  return null;
}

function parseJson(value: string): unknown {
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}

function getUploadError(payload: unknown, fallback: string) {
  if (
    payload &&
    typeof payload === "object" &&
    "detail" in payload &&
    typeof payload.detail === "string"
  ) {
    return payload.detail;
  }
  return fallback;
}

function formatBytes(bytes: number) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
