from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.schemas import ClarificationUpdateRequest, RecommendationResponse
from app.services.clarifications import (
    ClarificationQuestionNotFoundError,
    get_dataset_clarifications,
    update_dataset_clarification,
)
from app.services.dataset_inspector import inspect_dataset

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
        files={"file": ("clarify.zip", _sample_archive(), "application/zip")},
    )
    assert response.status_code == 201
    return response.json()


def _directory_contents(directory: Path) -> dict[Path, bytes]:
    return {
        path.relative_to(directory): path.read_bytes()
        for path in directory.rglob("*")
        if path.is_file()
    }


def test_clarification_service_generates_stable_focused_questions_and_persists_answers(
    tmp_path: Path,
) -> None:
    inspection = inspect_dataset(SAMPLE_DATASET_PATH)
    dataset_id = "00000000-0000-4000-8000-000000000001"

    initial = get_dataset_clarifications(
        tmp_path,
        dataset_id=dataset_id,
        findings=inspection.findings,
    )

    assert {question.related_finding.type.value for question in initial.questions} == {
        "missing_values",
        "duplicate_identifier_values",
        "missing_reference",
        "suspicious_numeric_values",
        "probable_personal_data",
    }
    assert initial.summary.total_count == len(initial.questions)
    assert initial.summary.unanswered_count == len(initial.questions)
    assert initial.summary.answered_count == 0
    assert all(question.question_id.startswith("cq_") for question in initial.questions)
    assert all(question.why_this_matters for question in initial.questions)

    target = next(
        question
        for question in initial.questions
        if question.related_finding.type.value == "missing_values"
    )
    answered = update_dataset_clarification(
        tmp_path,
        dataset_id=dataset_id,
        findings=inspection.findings,
        question_id=target.question_id,
        update=ClarificationUpdateRequest(
            decision="answer",
            answer="Confirmed by alice@example.com: blanks mean not collected.",
        ),
    )
    answered_question = next(
        question for question in answered.questions if question.question_id == target.question_id
    )
    assert answered_question.status.value == "answered"
    assert answered_question.answer == "Confirmed by [masked-email]: blanks mean not collected."
    assert answered.summary.answered_count == 1

    reloaded = get_dataset_clarifications(
        tmp_path,
        dataset_id=dataset_id,
        findings=inspection.findings,
    )
    assert reloaded == answered
    stored = (tmp_path / "clarifications" / "questions.json").read_text()
    assert "alice@example.com" not in stored

    deferred_target = next(
        question
        for question in reloaded.questions
        if question.question_id != target.question_id
    )
    deferred = update_dataset_clarification(
        tmp_path,
        dataset_id=dataset_id,
        findings=inspection.findings,
        question_id=deferred_target.question_id,
        update=ClarificationUpdateRequest(decision="defer"),
    )
    assert deferred.summary.deferred_count == 1

    with pytest.raises(ClarificationQuestionNotFoundError):
        update_dataset_clarification(
            tmp_path,
            dataset_id=dataset_id,
            findings=inspection.findings,
            question_id="cq_unknown",
            update=ClarificationUpdateRequest(decision="defer"),
        )


def test_uploaded_clarification_api_preserves_originals_audits_activity_and_informs_ai(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage_root = tmp_path / "datasets"
    monkeypatch.setenv("DATAQUAY_DATA_ROOT", str(storage_root))
    upload = _upload_sample_dataset()
    dataset_id = str(upload["dataset_id"])
    workspace = storage_root / dataset_id
    originals_before = _directory_contents(workspace / "original")

    response = client.get(f"/api/clarify/datasets/{dataset_id}")
    assert response.status_code == 200
    clarifications = response.json()
    question = next(
        item
        for item in clarifications["questions"]
        if item["related_finding"]["type"] == "suspicious_numeric_values"
    )

    answer_response = client.put(
        f"/api/clarify/datasets/{dataset_id}/questions/{question['question_id']}",
        json={
            "decision": "answer",
            "answer": "The flagged value is a documented missing-data sentinel.",
        },
    )
    assert answer_response.status_code == 200
    assert answer_response.json()["summary"]["answered_count"] == 1

    deferred_question = next(
        item
        for item in answer_response.json()["questions"]
        if item["status"] == "unanswered"
    )
    defer_response = client.put(
        f"/api/clarify/datasets/{dataset_id}/questions/{deferred_question['question_id']}",
        json={"decision": "defer"},
    )
    assert defer_response.status_code == 200
    assert defer_response.json()["summary"]["deferred_count"] == 1

    async def fake_recommendations(inspection, *, clarifications):
        assert inspection.summary.dataset_name == "clarify"
        assert clarifications.summary.answered_count == 1
        confirmed = [item.answer for item in clarifications.questions if item.answer]
        assert confirmed == ["The flagged value is a documented missing-data sentinel."]
        return RecommendationResponse(recommendations=[])

    monkeypatch.setattr(
        "app.routes.inspect.generate_recommendations",
        fake_recommendations,
    )
    recommendation_response = client.post(
        f"/api/inspect/datasets/{dataset_id}/recommendations"
    )
    assert recommendation_response.status_code == 200

    audit_response = client.get(f"/api/audit/datasets/{dataset_id}")
    assert audit_response.status_code == 200
    actions = [event["action"] for event in audit_response.json()["events"]]
    assert actions == [
        "upload",
        "clarification_review",
        "clarification_response",
        "clarification_response",
        "recommendation_generation",
    ]
    audit_text = (workspace / "audit" / "events.jsonl").read_text()
    assert "documented missing-data sentinel" not in audit_text
    assert _directory_contents(workspace / "original") == originals_before
    assert not (workspace / "working-copy").exists()


@pytest.mark.parametrize(
    ("method", "path", "json"),
    [
        ("get", "/api/clarify/datasets/{id}", None),
        (
            "put",
            "/api/clarify/datasets/{id}/questions/cq_unknown",
            {"decision": "defer"},
        ),
    ],
)
def test_clarification_api_rejects_unknown_dataset_identifiers(
    method: str,
    path: str,
    json: dict[str, str] | None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATAQUAY_DATA_ROOT", str(tmp_path / "datasets"))
    response = client.request(method, path.format(id=MISSING_DATASET_ID), json=json)
    assert response.status_code == 404
    assert response.json() == {"detail": "Dataset workspace was not found."}
