from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi.testclient import TestClient
import polars as pl
import pytest

from app.main import app
from app.schemas import RecommendationResponse

client = TestClient(app)

SAMPLE_DATASET_PATH = (
    Path(__file__).resolve().parents[2] / "sample-data" / "soil-study"
)
MISSING_DATASET_ID = "00000000-0000-4000-8000-000000000000"


def _sample_archive() -> bytes:
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(SAMPLE_DATASET_PATH.rglob("*")):
            if path.is_file():
                archive.writestr(
                    path.relative_to(SAMPLE_DATASET_PATH).as_posix(),
                    path.read_bytes(),
                )
    return output.getvalue()


def _upload_sample_dataset() -> dict[str, object]:
    response = client.post(
        "/api/datasets/upload",
        files={
            "file": ("uploaded-soil.zip", _sample_archive(), "application/zip")
        },
    )
    assert response.status_code == 201
    return response.json()


def _approved_recommendation(
    finding_type: str,
    file: str,
    column: str | None,
) -> dict[str, object]:
    return {
        "related_finding": {
            "type": finding_type,
            "file": file,
            "affected_column": column,
        },
        "short_title": "Approved safe recommendation",
        "rationale": "The deterministic finding can be remediated safely.",
        "proposed_action": "Apply the deterministic operation.",
        "confidence": 0.98,
        "human_approval_required": True,
    }


def _directory_contents(directory: Path) -> dict[Path, bytes]:
    return {
        path.relative_to(directory): path.read_bytes()
        for path in directory.rglob("*")
        if path.is_file()
    }


def test_uploaded_dataset_completes_workflow_without_changing_originals(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage_root = tmp_path / "datasets"
    monkeypatch.setenv("DATAQUAY_DATA_ROOT", str(storage_root))
    upload = _upload_sample_dataset()
    dataset_id = str(upload["dataset_id"])
    workspace = storage_root / dataset_id
    original_directory = workspace / "original"
    original_before = _directory_contents(original_directory)
    archive_before = (workspace / "archive" / "upload.zip").read_bytes()

    async def fake_recommendations(inspection):
        assert inspection.summary.dataset_name == "uploaded-soil"
        return RecommendationResponse(recommendations=[])

    monkeypatch.setattr(
        "app.routes.inspect.generate_recommendations",
        fake_recommendations,
    )
    recommendation_response = client.post(
        f"/api/inspect/datasets/{dataset_id}/recommendations"
    )
    assert recommendation_response.status_code == 200
    assert recommendation_response.json() == {"recommendations": []}

    approved_recommendations = [
        _approved_recommendation("duplicate_rows", "observations.csv", None),
        _approved_recommendation(
            "inconsistent_date_formats",
            "participants.csv",
            "joined_at",
        ),
        _approved_recommendation(
            "inconsistent_date_formats",
            "observations.csv",
            "recorded_at",
        ),
        _approved_recommendation(
            "missing_reference",
            "observations.csv",
            "participant_id",
        ),
    ]
    request = {"approved_recommendations": approved_recommendations}

    preview_response = client.post(
        f"/api/remediate/datasets/{dataset_id}/preview",
        json=request,
    )
    assert preview_response.status_code == 200
    assert len(preview_response.json()["actions"]) == 4
    assert sum(
        action["can_apply_automatically"]
        for action in preview_response.json()["actions"]
    ) == 3
    assert not (workspace / "working-copy").exists()

    apply_response = client.post(
        f"/api/remediate/datasets/{dataset_id}/apply",
        json=request,
    )
    assert apply_response.status_code == 200
    application = apply_response.json()
    assert application["working_copy_directory"] == str(
        (workspace / "working-copy").resolve()
    )
    assert len(application["applied_actions"]) == 3
    assert len(application["skipped_actions"]) == 1
    assert application["failed_actions"] == []
    remediated_observations = pl.read_csv(
        workspace / "working-copy" / "observations.csv"
    )
    assert remediated_observations.height == 3
    assert set(remediated_observations["recorded_at"].to_list()) == {
        "2026-02-01",
        "2026-02-02",
    }

    validation_response = client.post(f"/api/validate/datasets/{dataset_id}")
    assert validation_response.status_code == 200
    validation = validation_response.json()
    assert validation["source_checksums_verified"] is True
    assert validation["output_checksums_verified"] is True
    assert validation["original_files_unchanged"] is True
    assert len(validation["resolved_findings"]) == 4

    generation_response = client.post(f"/api/package/datasets/{dataset_id}")
    assert generation_response.status_code == 200
    package = generation_response.json()
    assert package["dataset_name"] == "uploaded-soil"
    assert package["download_url"] == (
        f"/api/package/datasets/{dataset_id}/download"
    )
    assert package["zip_file_name"] == "uploaded-soil.zip"

    download_response = client.get(package["download_url"])
    assert download_response.status_code == 200
    assert download_response.headers["content-type"] == "application/zip"
    with ZipFile(BytesIO(download_response.content)) as archive:
        assert "data/participants.csv" in archive.namelist()
        assert "validation-report.json" in archive.namelist()
        assert "provenance.json" in archive.namelist()

    repeated_apply_response = client.post(
        f"/api/remediate/datasets/{dataset_id}/apply",
        json=request,
    )
    assert repeated_apply_response.status_code == 200
    stale_download_response = client.get(package["download_url"])
    assert stale_download_response.status_code == 409
    assert "has not been generated yet" in stale_download_response.json()["detail"]

    audit_response = client.get(f"/api/audit/datasets/{dataset_id}")
    assert audit_response.status_code == 200
    events = audit_response.json()["events"]
    assert [(event["action"], event["status"]) for event in events] == [
        ("upload", "success"),
        ("recommendation_generation", "success"),
        ("remediation_preview", "success"),
        ("remediation_apply", "success"),
        ("validation", "success"),
        ("package_generation", "success"),
        ("package_download", "success"),
        ("remediation_apply", "success"),
        ("package_download", "failure"),
    ]
    audit_content = (workspace / "audit" / "events.jsonl").read_text()
    assert "alice@example.com" not in audit_content
    assert "P001" not in audit_content

    assert _directory_contents(original_directory) == original_before
    assert (workspace / "archive" / "upload.zip").read_bytes() == archive_before


def test_uploaded_workflow_reports_missing_prerequisites(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATAQUAY_DATA_ROOT", str(tmp_path / "datasets"))
    dataset_id = str(_upload_sample_dataset()["dataset_id"])

    validation_response = client.post(f"/api/validate/datasets/{dataset_id}")
    generation_response = client.post(f"/api/package/datasets/{dataset_id}")
    download_response = client.get(
        f"/api/package/datasets/{dataset_id}/download"
    )

    assert validation_response.status_code == 409
    assert "apply remediation first" in validation_response.json()["detail"]
    assert generation_response.status_code == 409
    assert "apply remediation first" in generation_response.json()["detail"]
    assert download_response.status_code == 409
    assert "has not been generated yet" in download_response.json()["detail"]
    audit_response = client.get(f"/api/audit/datasets/{dataset_id}")
    assert [(event["action"], event["status"]) for event in audit_response.json()["events"]] == [
        ("upload", "success"),
        ("validation", "failure"),
        ("package_generation", "failure"),
        ("package_download", "failure"),
    ]


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/api/inspect/datasets/{id}/recommendations"),
        ("post", "/api/remediate/datasets/{id}/preview"),
        ("post", "/api/remediate/datasets/{id}/apply"),
        ("post", "/api/validate/datasets/{id}"),
        ("post", "/api/package/datasets/{id}"),
        ("get", "/api/package/datasets/{id}/download"),
        ("get", "/api/audit/datasets/{id}"),
    ],
)
def test_uploaded_workflow_rejects_unknown_dataset_identifiers(
    method: str,
    path: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATAQUAY_DATA_ROOT", str(tmp_path / "datasets"))
    url = path.format(id=MISSING_DATASET_ID)
    request = {"approved_recommendations": []}

    response = (
        client.post(url, json=request)
        if method == "post" and "/remediate/" in url
        else client.request(method, url)
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Dataset workspace was not found."}
