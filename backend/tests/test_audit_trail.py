from pathlib import Path

from app.schemas import AuditAction, AuditStatus
from app.services.audit_trail import append_audit_event, read_audit_trail


def test_audit_trail_appends_events_without_rewriting_prior_entries(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "dataset"
    dataset_id = "00000000-0000-4000-8000-000000000001"

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
