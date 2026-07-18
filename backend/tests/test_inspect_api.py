from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.api_errors import AIServiceError
from app.schemas import RecommendationResponse


client = TestClient(app)


def test_inspect_sample_returns_participants_csv_profile() -> None:
    response = client.get("/api/inspect/sample")

    assert response.status_code == 200
    assert response.json() == {
        "file_name": "participants.csv",
        "row_count": 4,
        "column_count": 5,
        "column_names": [
            "participant_id",
            "name",
            "email",
            "age",
            "joined_at",
        ],
        "data_types": {
            "participant_id": "String",
            "name": "String",
            "email": "String",
            "age": "Int64",
            "joined_at": "String",
        },
        "missing_value_counts": {
            "participant_id": 0,
            "name": 0,
            "email": 1,
            "age": 1,
            "joined_at": 0,
        },
        "duplicate_row_count": 0,
    }


def test_inspect_sample_dataset_returns_inventory_and_csv_profiles() -> None:
    response = client.get("/api/inspect/sample-dataset")

    assert response.status_code == 200
    inspection = response.json()
    assert inspection["summary"] == {
        "dataset_name": "soil-study",
        "total_file_count": 3,
        "csv_file_count": 2,
        "total_size_bytes": 506,
    }
    assert inspection["readiness"] == {
        "total_finding_count": 12,
        "finding_counts_by_severity": {"high": 3, "medium": 9},
        "finding_counts_by_type": {
            "duplicate_identifier_values": 2,
            "duplicate_rows": 1,
            "inconsistent_date_formats": 2,
            "missing_reference": 1,
            "missing_values": 2,
            "probable_personal_data": 2,
            "suspicious_numeric_values": 2,
        },
        "blocker_count": 3,
        "human_review_required": True,
        "status": "not_ready",
    }

    files = {file["relative_path"]: file for file in inspection["files"]}
    assert set(files) == {"README.md", "observations.csv", "participants.csv"}

    assert files["README.md"] == {
        "file_name": "README.md",
        "relative_path": "README.md",
        "extension": ".md",
        "size_bytes": 153,
        "csv_profile": None,
    }

    observations = files["observations.csv"]
    assert observations["file_name"] == "observations.csv"
    assert observations["extension"] == ".csv"
    assert observations["size_bytes"] == 159
    assert observations["csv_profile"] == {
        "file_name": "observations.csv",
        "row_count": 4,
        "column_count": 4,
        "column_names": [
            "observation_id",
            "participant_id",
            "soil_moisture",
            "recorded_at",
        ],
        "data_types": {
            "observation_id": "String",
            "participant_id": "String",
            "soil_moisture": "Float64",
            "recorded_at": "String",
        },
        "missing_value_counts": {
            "observation_id": 0,
            "participant_id": 0,
            "soil_moisture": 0,
            "recorded_at": 0,
        },
        "duplicate_row_count": 1,
    }

    participants = files["participants.csv"]
    assert participants["file_name"] == "participants.csv"
    assert participants["extension"] == ".csv"
    assert participants["size_bytes"] == 194
    assert participants["csv_profile"]["row_count"] == 4
    assert participants["csv_profile"]["duplicate_row_count"] == 0

    findings = {
        (finding["type"], finding["file"], finding["affected_column"]): finding
        for finding in inspection["findings"]
    }
    assert len(findings) == 12

    assert findings[("missing_values", "participants.csv", "email")] == {
        "type": "missing_values",
        "severity": "medium",
        "file": "participants.csv",
        "affected_column": "email",
        "evidence": {"missing_count": 1},
        "message": "Column 'email' contains 1 missing value.",
    }
    assert findings[("missing_values", "participants.csv", "age")][
        "evidence"
    ] == {"missing_count": 1}
    assert findings[("duplicate_rows", "observations.csv", None)]["evidence"] == {
        "duplicate_row_count": 1
    }
    assert findings[
        ("duplicate_identifier_values", "participants.csv", "participant_id")
    ]["evidence"] == {
        "duplicate_count": 1,
        "duplicate_values": ["P002"],
    }
    assert findings[
        ("duplicate_identifier_values", "observations.csv", "observation_id")
    ]["evidence"] == {
        "duplicate_count": 1,
        "duplicate_values": ["O003"],
    }
    assert findings[("missing_reference", "observations.csv", "participant_id")][
        "evidence"
    ] == {
        "referenced_file": "participants.csv",
        "missing_values": ["P999"],
        "reference_count": 2,
    }
    assert findings[
        ("inconsistent_date_formats", "participants.csv", "joined_at")
    ]["evidence"] == {
        "detected_formats": ["YYYY-MM-DD", "DD/MM/YYYY", "Month D YYYY"],
        "triggering_values": [
            "2026-01-15 (YYYY-MM-DD)",
            "15/01/2026 (DD/MM/YYYY)",
            "January 16 2026 (Month D YYYY)",
        ],
    }
    assert findings[
        ("inconsistent_date_formats", "observations.csv", "recorded_at")
    ]["evidence"] == {
        "detected_formats": ["YYYY-MM-DD", "DD/MM/YYYY"],
        "triggering_values": [
            "2026-02-01 (YYYY-MM-DD)",
            "2026-02-02 (YYYY-MM-DD)",
            "01/02/2026 (DD/MM/YYYY)",
        ],
    }
    assert findings[
        ("suspicious_numeric_values", "participants.csv", "age")
    ]["evidence"] == {
        "suspicious_values": ["9999"],
        "occurrence_count": 1,
        "reason": "matches a common placeholder or invalid sentinel value",
    }
    assert findings[
        ("suspicious_numeric_values", "observations.csv", "soil_moisture")
    ]["evidence"] == {
        "suspicious_values": ["-99"],
        "occurrence_count": 1,
        "reason": "matches a common placeholder or invalid sentinel value",
    }
    assert findings[("probable_personal_data", "participants.csv", "name")][
        "evidence"
    ] == {
        "category": "person_name",
        "occurrence_count": 4,
        "detection_methods": ["column_name"],
        "masked_evidence": ["A****", "B**", "C******"],
    }
    assert findings[("probable_personal_data", "participants.csv", "email")][
        "evidence"
    ] == {
        "category": "email_address",
        "occurrence_count": 3,
        "detection_methods": ["column_name", "pattern_match"],
        "masked_evidence": ["a****@e******.com", "b**@e******.com"],
    }
    response_body = response.text
    assert "alice@example.com" not in response_body
    assert "bob@example.com" not in response_body


def test_recommendations_endpoint_returns_structured_agent_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_generate_recommendations(inspection: object) -> RecommendationResponse:
        assert getattr(inspection, "summary").dataset_name == "soil-study"
        return RecommendationResponse.model_validate(
            {
                "recommendations": [
                    {
                        "related_finding": {
                            "type": "duplicate_rows",
                            "file": "observations.csv",
                            "affected_column": None,
                        },
                        "short_title": "Review duplicate observation",
                        "rationale": "A duplicate row can distort analysis.",
                        "proposed_action": "Verify the row before removing a copy.",
                        "confidence": 0.95,
                        "human_approval_required": True,
                    }
                ]
            }
        )

    monkeypatch.setattr(
        "app.routes.inspect.generate_recommendations",
        fake_generate_recommendations,
    )

    response = client.post("/api/inspect/sample-dataset/recommendations")

    assert response.status_code == 200
    assert response.json()["recommendations"][0] == {
        "related_finding": {
            "type": "duplicate_rows",
            "file": "observations.csv",
            "affected_column": None,
        },
        "short_title": "Review duplicate observation",
        "rationale": "A duplicate row can distort analysis.",
        "proposed_action": "Verify the row before removing a copy.",
        "confidence": 0.95,
        "human_approval_required": True,
        "assumptions": [],
    }


def test_recommendations_endpoint_reports_missing_ai_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATAQUAY_AI_MODEL", raising=False)

    response = client.post("/api/inspect/sample-dataset/recommendations")

    assert response.status_code == 503
    assert response.json() == {
        "code": "ai_not_configured",
        "detail": (
            "DATAQUAY_AI_MODEL is not configured; set it to a "
            "PydanticAI provider-qualified model name."
        )
    }


def test_recommendations_endpoint_reports_ai_provider_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail_generation(_inspection):
        raise AIServiceError("The configured AI provider is temporarily unavailable.")

    monkeypatch.setattr(
        "app.routes.inspect.generate_recommendations",
        fail_generation,
    )

    response = client.post("/api/inspect/sample-dataset/recommendations")

    assert response.status_code == 503
    assert response.json() == {
        "code": "ai_service_unavailable",
        "detail": "The configured AI provider is temporarily unavailable.",
    }
