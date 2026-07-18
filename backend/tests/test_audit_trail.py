from pathlib import Path
from uuid import UUID

import pytest

from app.database import session_scope
from app.models import DatasetRecord, Workspace
from app.schemas import AuditAction, AuditStatus
from app.services.audit_trail import append_audit_event, read_audit_trail


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

    monkeypatch.setattr(
        "app.services.audit_trail.os.open",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("mirror unavailable")),
    )
    event = append_audit_event(
        workspace,
        dataset_id=dataset_id,
        action=AuditAction.UPLOAD,
        status=AuditStatus.SUCCESS,
        summary="Archive accepted.",
    )

    assert not (workspace / "audit" / "events.jsonl").exists()
    assert read_audit_trail(workspace, dataset_id=dataset_id).events == [event]


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
