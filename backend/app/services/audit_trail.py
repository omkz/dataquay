from datetime import datetime, timezone
import os
from pathlib import Path
import re

from pydantic import ValidationError

from app.schemas import AuditAction, AuditEvent, AuditStatus, DatasetAuditTrail
from app.services.workflow_repository import (
    PersistenceError,
    persist_audit_event,
    read_persisted_audit_trail,
)

AUDIT_DIRECTORY_NAME = "audit"
AUDIT_FILE_NAME = "events.jsonl"
EMAIL_IN_TEXT_PATTERN = re.compile(
    r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+"
    r"(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+"
)


class AuditTrailError(RuntimeError):
    """Raised when a dataset audit trail cannot be stored or read safely."""


def append_audit_event(
    workspace_directory: str | Path,
    *,
    dataset_id: str,
    action: AuditAction,
    status: AuditStatus,
    summary: str,
) -> AuditEvent:
    """Append one constrained event without reading or rewriting prior events."""
    workspace = Path(workspace_directory).resolve()
    audit_directory = workspace / AUDIT_DIRECTORY_NAME
    audit_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    event = AuditEvent(
        timestamp=datetime.now(timezone.utc),
        action=action,
        status=status,
        dataset_id=dataset_id,
        summary=_safe_summary(summary),
    )
    try:
        persist_audit_event(event)
    except PersistenceError as exc:
        raise AuditTrailError("The dataset audit event could not be persisted.") from exc
    payload = (event.model_dump_json() + "\n").encode("utf-8")
    audit_path = audit_directory / AUDIT_FILE_NAME

    try:
        descriptor = os.open(
            audit_path,
            os.O_APPEND | os.O_CREAT | os.O_WRONLY,
            0o600,
        )
        try:
            view = memoryview(payload)
            while view:
                written = os.write(descriptor, view)
                if written == 0:
                    raise OSError("Audit event append made no progress.")
                view = view[written:]
        finally:
            os.close(descriptor)
    except OSError as exc:
        raise AuditTrailError("The dataset audit event could not be stored.") from exc
    return event


def read_audit_trail(
    workspace_directory: str | Path,
    *,
    dataset_id: str,
) -> DatasetAuditTrail:
    try:
        persisted = read_persisted_audit_trail(dataset_id)
    except PersistenceError as exc:
        raise AuditTrailError("The persisted audit trail is unavailable.") from exc
    if persisted is not None:
        return persisted
    audit_path = (
        Path(workspace_directory).resolve()
        / AUDIT_DIRECTORY_NAME
        / AUDIT_FILE_NAME
    )
    if not audit_path.exists():
        return DatasetAuditTrail(dataset_id=dataset_id, events=[])

    try:
        lines = audit_path.read_text(encoding="utf-8").splitlines()
        events = [
            AuditEvent.model_validate_json(line)
            for line in lines
            if line.strip()
        ]
    except (OSError, ValidationError) as exc:
        raise AuditTrailError("The dataset audit trail is unavailable or invalid.") from exc
    if any(event.dataset_id != dataset_id for event in events):
        raise AuditTrailError("The dataset audit trail does not match the workspace.")
    return DatasetAuditTrail(dataset_id=dataset_id, events=events)


def _safe_summary(summary: str) -> str:
    normalized = " ".join(summary.split())
    masked = EMAIL_IN_TEXT_PATTERN.sub("[masked-email]", normalized)
    return (masked[:500] or "Workflow event recorded.")
