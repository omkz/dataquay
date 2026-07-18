from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi.testclient import TestClient
import pytest

from app.database import get_engine
from app.main import app
from app.schemas import RecommendationResponse

client = TestClient(app)
SAMPLE_DATASET_PATH = (
    Path(__file__).resolve().parents[2] / "sample-data" / "soil-study"
)


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


def test_workspace_can_be_listed_and_reopened_with_persisted_review_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage_root = tmp_path / "datasets"
    monkeypatch.setenv("DATAQUAY_DATA_ROOT", str(storage_root))
    upload_response = client.post(
        "/api/datasets/upload",
        files={"file": ("persistent-soil.zip", _sample_archive(), "application/zip")},
    )
    assert upload_response.status_code == 201
    dataset_id = upload_response.json()["dataset_id"]

    inspection_response = client.get(f"/api/inspect/datasets/{dataset_id}")
    assert inspection_response.status_code == 200
    clarification_response = client.get(f"/api/clarify/datasets/{dataset_id}")
    question = clarification_response.json()["questions"][0]
    answer_response = client.put(
        f"/api/clarify/datasets/{dataset_id}/questions/{question['question_id']}",
        json={"decision": "answer", "answer": "Confirmed research context."},
    )
    assert answer_response.status_code == 200

    async def fake_recommendations(inspection, *, clarifications):
        assert clarifications.summary.answered_count == 1
        return RecommendationResponse.model_validate(
            {
                "recommendations": [
                    {
                        "related_finding": {
                            "type": "missing_values",
                            "file": "participants.csv",
                            "affected_column": "email",
                        },
                        "short_title": "Document expected missingness",
                        "rationale": "Human context confirms the value is expected.",
                        "proposed_action": "Document the missing-value convention.",
                        "confidence": 0.92,
                        "human_approval_required": True,
                        "assumptions": [],
                    }
                ]
            }
        )

    monkeypatch.setattr(
        "app.routes.inspect.generate_recommendations",
        fake_recommendations,
    )
    generated = client.post(f"/api/inspect/datasets/{dataset_id}/recommendations")
    assert generated.status_code == 200

    detail = client.get(f"/api/workspaces/{dataset_id}")
    assert detail.status_code == 200
    recommendation = detail.json()["recommendations"][0]
    key = "recommendation-0"
    assert detail.json()["decisions"] == {key: "pending"}
    assert recommendation["short_title"] == "Document expected missingness"

    decision = client.put(
        f"/api/workspaces/{dataset_id}/decision",
        json={"recommendation_key": key, "decision": "approved"},
    )
    assert decision.status_code == 200
    assert decision.json()["decisions"][key] == "approved"

    # Read-only inspection and clarification refreshes must not move a reviewed
    # workflow backwards when the dashboard is reopened.
    assert client.get(f"/api/inspect/datasets/{dataset_id}").status_code == 200
    assert client.get(f"/api/clarify/datasets/{dataset_id}").status_code == 200
    assert client.get(f"/api/workspaces/{dataset_id}").json()["workflow_status"] == (
        "in_review"
    )

    # Remove compatibility mirrors to prove PostgreSQL/SQLAlchemy state is enough
    # to restore clarification, recommendation, decision, and audit metadata.
    workspace = storage_root / dataset_id
    (workspace / "clarifications" / "questions.json").unlink()
    (workspace / "audit" / "events.jsonl").unlink()
    get_engine().dispose()

    reopened = TestClient(app).get(f"/api/workspaces/{dataset_id}")
    assert reopened.status_code == 200
    assert reopened.json()["workflow_status"] == "in_review"
    assert reopened.json()["decisions"] == {key: "approved"}
    assert reopened.json()["recommendations"][0]["proposed_action"] == (
        "Document the missing-value convention."
    )
    restored_clarifications = client.get(f"/api/clarify/datasets/{dataset_id}")
    restored_question = next(
        item
        for item in restored_clarifications.json()["questions"]
        if item["question_id"] == question["question_id"]
    )
    assert restored_question["status"] == "answered"
    assert restored_question["answer"] == "Confirmed research context."
    audit = client.get(f"/api/audit/datasets/{dataset_id}")
    assert any(event["action"] == "human_decision" for event in audit.json()["events"])

    listed = client.get("/api/workspaces")
    assert listed.status_code == 200
    assert listed.json()["workspaces"][0]["dataset_id"] == dataset_id
    assert listed.json()["workspaces"][0]["file_count"] == 3

    assert (workspace / "archive" / "upload.zip").is_file()
    assert (workspace / "original" / "participants.csv").is_file()


def test_read_only_requests_do_not_change_workspace_or_audit_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage_root = tmp_path / "datasets"
    monkeypatch.setenv("DATAQUAY_DATA_ROOT", str(storage_root))
    upload = client.post(
        "/api/datasets/upload",
        files={"file": ("read-only.zip", _sample_archive(), "application/zip")},
    )
    assert upload.status_code == 201
    dataset_id = upload.json()["dataset_id"]
    before_workspace = client.get(f"/api/workspaces/{dataset_id}").json()
    before_audit = client.get(f"/api/audit/datasets/{dataset_id}").json()

    assert client.get(f"/api/inspect/datasets/{dataset_id}").status_code == 200
    assert client.get(f"/api/clarify/datasets/{dataset_id}").status_code == 200
    assert client.get("/api/workspaces").status_code == 200
    assert client.get(f"/api/workspaces/{dataset_id}").status_code == 200
    assert client.get(f"/api/audit/datasets/{dataset_id}").status_code == 200
    assert client.get(f"/api/package/datasets/{dataset_id}/download").status_code == 409

    after_workspace = client.get(f"/api/workspaces/{dataset_id}").json()
    after_audit = client.get(f"/api/audit/datasets/{dataset_id}").json()
    assert after_workspace["workflow_status"] == before_workspace["workflow_status"]
    assert after_workspace["current_stage"] == before_workspace["current_stage"]
    assert after_workspace["updated_at"] == before_workspace["updated_at"]
    assert after_audit == before_audit
