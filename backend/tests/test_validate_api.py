from pathlib import Path

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


def test_validate_endpoint_returns_post_remediation_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    working_copy = tmp_path / "api-working-copy"
    monkeypatch.setattr(
        "app.routes.remediate.SAMPLE_WORKING_COPY_PATH",
        working_copy,
    )
    monkeypatch.setattr(
        "app.routes.validation.SAMPLE_WORKING_COPY_PATH",
        working_copy,
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

    response = client.post("/api/validate/sample-dataset")

    assert response.status_code == 200
    result = response.json()
    assert len(result["resolved_findings"]) == 4
    assert len(result["remaining_findings"]) == 8
    assert len(result["checksum_verifications"]) == 3
    assert result["source_checksums_verified"] is True
    assert result["output_checksums_verified"] is True
    assert result["original_files_unchanged"] is True
    assert result["readiness"]["total_finding_count"] == 8
    assert result["readiness"]["blocker_count"] == 2
    assert result["readiness"]["status"] == "not_ready"


def test_validate_endpoint_requires_remediation_to_be_applied(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.routes.validation.SAMPLE_WORKING_COPY_PATH",
        tmp_path / "missing-working-copy",
    )

    response = client.post("/api/validate/sample-dataset")

    assert response.status_code == 409
    assert response.json() == {
        "detail": (
            "The remediated working copy does not exist; apply remediation first."
        )
    }
