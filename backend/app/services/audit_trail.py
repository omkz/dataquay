from collections.abc import Callable
from datetime import datetime, timezone
import os
from pathlib import Path
import re
from typing import TypeVar

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import session_scope
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


class AuditTrailError(PersistenceError):
    """Raised when a dataset audit trail cannot be stored or read safely."""


T = TypeVar("T")


def commit_audited_mutation(
    workspace_directory: str | Path,
    *,
    dataset_id: str,
    action: AuditAction,
    status: AuditStatus,
    summary: str,
    mutation: Callable[[Session], T],
) -> T:
    """Commit a database mutation and audit event, then mirror the event."""
    result, event = _commit_audited(
        dataset_id=dataset_id,
        action=action,
        status=status,
        summary=summary,
        mutation=mutation,
    )
    _mirror_audit_event(workspace_directory, event)
    return result


def append_audit_event(
    workspace_directory: str | Path,
    *,
    dataset_id: str,
    action: AuditAction,
    status: AuditStatus,
    summary: str,
) -> AuditEvent:
    """Commit one workflow event, then append its best-effort JSONL mirror."""
    _, event = _commit_audited(
        dataset_id=dataset_id,
        action=action,
        status=status,
        summary=summary,
        mutation=lambda _session: None,
    )
    _mirror_audit_event(workspace_directory, event)
    return event


def _commit_audited(
    *,
    dataset_id: str,
    action: AuditAction,
    status: AuditStatus,
    summary: str,
    mutation: Callable[[Session], T],
) -> tuple[T, AuditEvent]:
    event = AuditEvent(
        timestamp=datetime.now(timezone.utc),
        action=action,
        status=status,
        dataset_id=dataset_id,
        summary=_safe_summary(summary),
    )
    try:
        with session_scope() as session:
            result = mutation(session)
            persist_audit_event(event, session=session)
    except PersistenceError as exc:
        raise AuditTrailError(
            "The workflow mutation and audit event could not be persisted."
        ) from exc
    except SQLAlchemyError as exc:
        raise AuditTrailError(
            "The workflow mutation and audit event could not be persisted."
        ) from exc
    return result, event


def _mirror_audit_event(
    workspace_directory: str | Path,
    event: AuditEvent,
) -> None:
    workspace = Path(workspace_directory).resolve()
    audit_directory = workspace / AUDIT_DIRECTORY_NAME
    payload = (event.model_dump_json() + "\n").encode("utf-8")
    audit_path = audit_directory / AUDIT_FILE_NAME

    try:
        audit_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
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
    except OSError:
        # PostgreSQL is authoritative. The JSONL copy is operationally useful,
        # but a mirror failure must not roll back a committed workflow event.
        pass


def read_audit_trail(
    workspace_directory: str | Path,
    *,
    dataset_id: str,
) -> DatasetAuditTrail:
    try:
        return read_persisted_audit_trail(dataset_id)
    except PersistenceError as exc:
        raise AuditTrailError("The persisted audit trail is unavailable.") from exc


def _safe_summary(summary: str) -> str:
    normalized = " ".join(summary.split())
    masked = EMAIL_IN_TEXT_PATTERN.sub("[masked-email]", normalized)
    return (masked[:500] or "Workflow event recorded.")
