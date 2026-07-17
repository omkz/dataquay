from pathlib import Path

from fastapi.testclient import TestClient

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
