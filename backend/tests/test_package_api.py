from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from fastapi.testclient import TestClient
import pytest

from app.main import app

client = TestClient(app)


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


def test_package_generation_and_download_endpoints(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    working_copy = tmp_path / "working-copy"
    package_directory = tmp_path / "packages" / "soil-study"
    monkeypatch.setattr(
        "app.routes.remediate.SAMPLE_WORKING_COPY_PATH",
        working_copy,
    )
    monkeypatch.setattr(
        "app.routes.package.SAMPLE_WORKING_COPY_PATH",
        working_copy,
    )
    monkeypatch.setattr(
        "app.routes.package.SAMPLE_PACKAGE_PATH",
        package_directory,
    )
    apply_request = {
        "approved_recommendations": [
            _approved_recommendation(
                "duplicate_rows",
                "observations.csv",
                None,
            ),
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
        ]
    }
    apply_response = client.post(
        "/api/remediate/sample-dataset/apply",
        json=apply_request,
    )
    assert apply_response.status_code == 200

    generation_response = client.post("/api/package/sample-dataset")

    assert generation_response.status_code == 200
    package = generation_response.json()
    assert package["dataset_name"] == "soil-study"
    assert package["zip_file_name"] == "soil-study.zip"
    assert package["download_url"] == "/api/package/sample-dataset/download"
    assert len(package["files"]) == 10
    assert package["readiness"]["total_finding_count"] == 8

    download_response = client.get(package["download_url"])

    assert download_response.status_code == 200
    assert download_response.headers["content-type"] == "application/zip"
    assert "soil-study.zip" in download_response.headers["content-disposition"]
    with ZipFile(BytesIO(download_response.content)) as archive:
        assert "data/participants.csv" in archive.namelist()
        assert "validation-report.json" in archive.namelist()
        assert "provenance.json" in archive.namelist()


def test_package_endpoints_fail_clearly_before_remediation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.routes.package.SAMPLE_WORKING_COPY_PATH",
        tmp_path / "missing-working-copy",
    )
    monkeypatch.setattr(
        "app.routes.package.SAMPLE_PACKAGE_PATH",
        tmp_path / "missing-package",
    )

    generation_response = client.post("/api/package/sample-dataset")
    download_response = client.get("/api/package/sample-dataset/download")

    assert generation_response.status_code == 409
    assert "working copy does not exist" in generation_response.json()["detail"]
    assert download_response.status_code == 404
    assert download_response.json() == {
        "detail": "The sample dataset package has not been generated yet."
    }
