from pathlib import Path

from fastapi.testclient import TestClient
import polars as pl
import pytest

from app.main import app

client = TestClient(app)

SAMPLE_DATASET_PATH = (
    Path(__file__).resolve().parents[2] / "sample-data" / "soil-study"
)


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
        "short_title": "Approved recommendation",
        "rationale": "The finding should be remediated.",
        "proposed_action": "Prepare the appropriate remediation.",
        "confidence": 0.9,
        "human_approval_required": True,
    }


def test_preview_endpoint_returns_actions_without_modifying_sample_files() -> None:
    original_files = {
        path.relative_to(SAMPLE_DATASET_PATH): path.read_bytes()
        for path in SAMPLE_DATASET_PATH.rglob("*")
        if path.is_file()
    }
    request = {
        "approved_recommendations": [
            _approved_recommendation(
                "duplicate_rows",
                "observations.csv",
                None,
            ),
            _approved_recommendation(
                "inconsistent_date_formats",
                "observations.csv",
                "recorded_at",
            ),
            _approved_recommendation(
                "suspicious_numeric_values",
                "observations.csv",
                "soil_moisture",
            ),
        ]
    }

    response = client.post("/api/remediate/sample-dataset/preview", json=request)

    assert response.status_code == 200
    actions = response.json()["actions"]
    assert len(actions) == 3
    assert actions[0] == {
        "related_finding": {
            "type": "duplicate_rows",
            "file": "observations.csv",
            "affected_column": None,
        },
        "target_file": "observations.csv",
        "target_column": None,
        "proposed_operation": "remove_exact_duplicate_rows",
        "can_apply_automatically": True,
        "manual_review_reason": None,
        "expected_result": (
            "Only one copy of each exact duplicate row remains in the target file."
        ),
    }
    assert actions[1]["proposed_operation"] == "normalize_recognized_date_formats"
    assert actions[1]["can_apply_automatically"] is True
    assert actions[2]["proposed_operation"] == "review_suspicious_numeric_values"
    assert actions[2]["can_apply_automatically"] is False
    assert actions[2]["manual_review_reason"]

    current_files = {
        path.relative_to(SAMPLE_DATASET_PATH): path.read_bytes()
        for path in SAMPLE_DATASET_PATH.rglob("*")
        if path.is_file()
    }
    assert current_files == original_files


def test_preview_endpoint_rejects_a_stale_or_unknown_finding_reference() -> None:
    request = {
        "approved_recommendations": [
            _approved_recommendation(
                "duplicate_rows",
                "unknown.csv",
                None,
            )
        ]
    }

    response = client.post("/api/remediate/sample-dataset/preview", json=request)

    assert response.status_code == 422
    assert "not present in the current inspection" in response.json()["detail"]


def test_apply_endpoint_applies_only_safe_actions_to_a_working_copy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    working_copy = tmp_path / "api-working-copy"
    monkeypatch.setattr(
        "app.routes.remediate.SAMPLE_WORKING_COPY_PATH",
        working_copy,
    )
    original_files = {
        path.relative_to(SAMPLE_DATASET_PATH): path.read_bytes()
        for path in SAMPLE_DATASET_PATH.rglob("*")
        if path.is_file()
    }
    request = {
        "approved_recommendations": [
            _approved_recommendation(
                "duplicate_rows",
                "observations.csv",
                None,
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
    }

    first_response = client.post(
        "/api/remediate/sample-dataset/apply",
        json=request,
    )

    assert first_response.status_code == 200
    result = first_response.json()
    assert result["working_copy_directory"] == str(working_copy.resolve())
    assert len(result["applied_actions"]) == 2
    assert len(result["skipped_actions"]) == 1
    assert result["failed_actions"] == []
    assert result["skipped_actions"][0]["action"]["proposed_operation"] == (
        "reconcile_missing_references"
    )
    assert len(result["applied_actions"][0]["source_checksum_sha256"]) == 64
    assert len(result["applied_actions"][0]["output_checksum_sha256"]) == 64

    output = pl.read_csv(working_copy / "observations.csv")
    assert output.height == 3
    assert set(output["recorded_at"].to_list()) == {
        "2026-02-01",
        "2026-02-02",
    }
    first_output_bytes = (working_copy / "observations.csv").read_bytes()

    second_response = client.post(
        "/api/remediate/sample-dataset/apply",
        json=request,
    )

    assert second_response.status_code == 200
    assert second_response.json() == result
    assert (working_copy / "observations.csv").read_bytes() == first_output_bytes
    assert {
        path.relative_to(SAMPLE_DATASET_PATH): path.read_bytes()
        for path in SAMPLE_DATASET_PATH.rglob("*")
        if path.is_file()
    } == original_files
