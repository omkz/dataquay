from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.exc import SQLAlchemyError

from app.database import session_scope
from app.models import AuditEventRecord, ClarificationRecord, DatasetRecord, Workspace
from app.schemas import AuditAction, AuditStatus, ClarificationStatus
from app.services.audit_trail import (
    AuditTrailError,
    append_audit_event,
    commit_audited_mutation,
    read_audit_trail,
)
from app.services.workflow_repository import save_clarification_response


def test_audit_trail_appends_events_without_rewriting_prior_entries(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "dataset"
    dataset_id = "00000000-0000-4000-8000-000000000001"
    _persist_workspace(dataset_id, workspace)

    first = append_audit_event(
        workspace,
        dataset_id=dataset_id,
        action=AuditAction.UPLOAD,
        status=AuditStatus.SUCCESS,
        summary="Archive accepted.\nContact alice@example.com was masked.",
    )
    audit_path = workspace / "audit" / "events.jsonl"
    first_bytes = audit_path.read_bytes()
    second = append_audit_event(
        workspace,
        dataset_id=dataset_id,
        action=AuditAction.INSPECTION,
        status=AuditStatus.FAILURE,
        summary="Inspection did not complete.",
    )

    stored_bytes = audit_path.read_bytes()
    assert stored_bytes.startswith(first_bytes)
    assert stored_bytes.count(b"\n") == 2
    trail = read_audit_trail(workspace, dataset_id=dataset_id)
    assert trail.dataset_id == dataset_id
    assert trail.events == [first, second]
    assert trail.events[0].summary == (
        "Archive accepted. Contact [masked-email] was masked."
    )
    assert "alice@example.com" not in audit_path.read_text()
    assert all(event.timestamp.tzinfo is not None for event in trail.events)


def test_jsonl_failure_does_not_lose_postgresql_audit_event(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "dataset"
    dataset_id = "00000000-0000-4000-8000-000000000002"
    _persist_workspace(dataset_id, workspace)
    question_id = _persist_clarification(dataset_id)

    monkeypatch.setattr(
        "app.services.audit_trail.os.open",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("mirror unavailable")),
    )
    result = commit_audited_mutation(
        workspace,
        dataset_id=dataset_id,
        action=AuditAction.CLARIFICATION_RESPONSE,
        status=AuditStatus.SUCCESS,
        summary="Clarification answered without exposing its content.",
        mutation=lambda session: save_clarification_response(
            dataset_id,
            question_id=question_id,
            status=ClarificationStatus.ANSWERED,
            answer="Confirmed context.",
            session=session,
        ),
    )

    assert result.summary.answered_count == 1
    assert not (workspace / "audit" / "events.jsonl").exists()
    trail = read_audit_trail(workspace, dataset_id=dataset_id)
    assert [item.action for item in trail.events] == [
        AuditAction.CLARIFICATION_RESPONSE
    ]
    with session_scope() as session:
        clarification = session.get(
            ClarificationRecord,
            (UUID(dataset_id), question_id),
        )
        assert clarification is not None
        assert clarification.status == ClarificationStatus.ANSWERED.value


def test_audited_mutation_commits_workflow_change_event_and_jsonl(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "dataset"
    dataset_id = "00000000-0000-4000-8000-000000000004"
    _persist_workspace(dataset_id, workspace)
    question_id = _persist_clarification(dataset_id)

    result = commit_audited_mutation(
        workspace,
        dataset_id=dataset_id,
        action=AuditAction.CLARIFICATION_RESPONSE,
        status=AuditStatus.SUCCESS,
        summary="Clarification answered without exposing its content.",
        mutation=lambda session: save_clarification_response(
            dataset_id,
            question_id=question_id,
            status=ClarificationStatus.ANSWERED,
            answer="Confirmed context.",
            session=session,
        ),
    )

    assert result.summary.answered_count == 1
    assert (workspace / "audit" / "events.jsonl").read_text().count("\n") == 1
    with session_scope() as session:
        clarification = session.get(
            ClarificationRecord,
            (UUID(dataset_id), question_id),
        )
        assert clarification is not None
        assert clarification.status == ClarificationStatus.ANSWERED.value
        assert session.scalar(select(func.count()).select_from(AuditEventRecord)) == 1
        workspace_record = session.get(Workspace, UUID(dataset_id))
        assert workspace_record is not None
        assert workspace_record.workflow_status == "clarifying"


def test_audit_insert_failure_rolls_back_clarification_mutation(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "dataset"
    dataset_id = "00000000-0000-4000-8000-000000000003"
    _persist_workspace(dataset_id, workspace)
    question_id = _persist_clarification(dataset_id)

    def fail_audit_insert(*_args) -> None:
        raise SQLAlchemyError("forced audit failure")

    event.listen(AuditEventRecord, "before_insert", fail_audit_insert)
    try:
        with pytest.raises(AuditTrailError):
            commit_audited_mutation(
                workspace,
                dataset_id=dataset_id,
                action=AuditAction.CLARIFICATION_RESPONSE,
                status=AuditStatus.SUCCESS,
                summary="Clarification answered.",
                mutation=lambda session: save_clarification_response(
                    dataset_id,
                    question_id=question_id,
                    status=ClarificationStatus.ANSWERED,
                    answer="Must roll back.",
                    session=session,
                ),
            )
    finally:
        event.remove(AuditEventRecord, "before_insert", fail_audit_insert)

    with session_scope() as session:
        clarification = session.get(
            ClarificationRecord,
            (UUID(dataset_id), question_id),
        )
        assert clarification is not None
        assert clarification.status == ClarificationStatus.UNANSWERED.value
        assert clarification.answer is None
        assert session.scalar(select(func.count()).select_from(AuditEventRecord)) == 0
        workspace_record = session.get(Workspace, UUID(dataset_id))
        assert workspace_record is not None
        assert workspace_record.workflow_status == "uploaded"
    assert not (workspace / "audit" / "events.jsonl").exists()


def test_mutation_failure_does_not_commit_an_audit_event(tmp_path: Path) -> None:
    workspace = tmp_path / "dataset"
    dataset_id = "00000000-0000-4000-8000-000000000005"
    _persist_workspace(dataset_id, workspace)

    def fail_mutation(_session) -> None:
        raise SQLAlchemyError("forced mutation failure")

    with pytest.raises(AuditTrailError):
        commit_audited_mutation(
            workspace,
            dataset_id=dataset_id,
            action=AuditAction.VALIDATION,
            status=AuditStatus.SUCCESS,
            summary="Validation completed.",
            mutation=fail_mutation,
        )

    with session_scope() as session:
        assert session.scalar(select(func.count()).select_from(AuditEventRecord)) == 0
        workspace_record = session.get(Workspace, UUID(dataset_id))
        assert workspace_record is not None
        assert workspace_record.workflow_status == "uploaded"
    assert not (workspace / "audit" / "events.jsonl").exists()


def _persist_workspace(dataset_id: str, workspace: Path) -> None:
    workspace_id = UUID(dataset_id)
    with session_scope() as session:
        session.add(
            Workspace(
                id=workspace_id,
                name="audit-test",
                workflow_status="uploaded",
                current_stage="inspection",
            )
        )
        session.flush()
        session.add(
            DatasetRecord(
                id=workspace_id,
                workspace_id=workspace_id,
                original_file_name="audit-test.zip",
                archive_size_bytes=1,
                archive_checksum_sha256="0" * 64,
                extracted_file_count=1,
                extracted_size_bytes=1,
                storage_path=str(workspace),
            )
        )


def _persist_clarification(dataset_id: str) -> str:
    question_id = "cq_00000000000000000000"
    with session_scope() as session:
        session.add(
            ClarificationRecord(
                workspace_id=UUID(dataset_id),
                question_id=question_id,
                finding_type="missing_values",
                file_name="participants.csv",
                affected_column="email",
                question="Is this missing value expected?",
                why_this_matters="Research context is required.",
                status=ClarificationStatus.UNANSWERED.value,
                answer=None,
            )
        )
    return question_id
