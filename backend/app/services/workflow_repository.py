from collections.abc import Callable
from datetime import datetime, timezone
from typing import TypeVar
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api_errors import DatabaseUnavailableError
from app.database import session_scope
from app.models import (
    AuditEventRecord,
    ClarificationRecord,
    DatasetRecord,
    HumanDecision,
    RecommendationBatch,
    RecommendationRecord,
    Workspace,
)
from app.schemas import (
    AuditAction,
    AuditEvent,
    AuditStatus,
    ClarificationQuestion,
    ClarificationStatus,
    ClarificationSummary,
    DatasetAuditTrail,
    DatasetClarifications,
    DatasetUploadResponse,
    FindingReference,
    ReadinessSummary,
    RecommendationDecision,
    RecommendationResponse,
    RemediationRecommendation,
    WorkspaceDetail,
    WorkspaceListResponse,
    WorkspaceSummary,
)


class PersistenceError(DatabaseUnavailableError):
    """Raised when PostgreSQL workflow metadata cannot be read or stored."""


T = TypeVar("T")


def _run_persisted(
    operation: Callable[[Session], T],
    *,
    session: Session | None,
    error_message: str,
) -> T:
    try:
        if session is not None:
            return operation(session)
        with session_scope() as managed_session:
            return operation(managed_session)
    except PersistenceError:
        raise
    except SQLAlchemyError as exc:
        raise PersistenceError(error_message) from exc


def create_workspace_record(
    upload: DatasetUploadResponse,
    *,
    storage_path: str,
    owner_id: int,
) -> None:
    workspace_id = UUID(upload.dataset_id)
    try:
        with session_scope() as session:
            workspace = Workspace(
                id=workspace_id,
                name=upload.dataset_name,
                owner_id=owner_id,
                workflow_status="uploaded",
                current_stage="inspection",
            )
            session.add(workspace)
            # There is intentionally no ORM relationship between these records.
            # Flush the parent first so PostgreSQL can enforce the foreign key;
            # both inserts remain inside this transaction and roll back together.
            session.flush()
            session.add(
                DatasetRecord(
                    id=workspace_id,
                    workspace_id=workspace_id,
                    original_file_name=upload.file_name,
                    archive_size_bytes=upload.archive_size_bytes,
                    archive_checksum_sha256=upload.archive_checksum_sha256,
                    extracted_file_count=upload.extracted_file_count,
                    extracted_size_bytes=upload.extracted_size_bytes,
                    storage_path=storage_path,
                )
            )
    except SQLAlchemyError as exc:
        raise PersistenceError(
            "The dataset workspace metadata could not be persisted. "
            "Confirm that PostgreSQL is available and migrations are current."
        ) from exc


def delete_workspace_record(dataset_id: str) -> None:
    try:
        workspace_id = UUID(dataset_id)
    except ValueError:
        return
    try:
        with session_scope() as session:
            workspace = session.get(Workspace, workspace_id)
            if workspace is not None:
                session.delete(workspace)
    except SQLAlchemyError as exc:
        raise PersistenceError("Workspace metadata cleanup failed.") from exc


def list_workspaces(owner_id: int) -> WorkspaceListResponse:
    try:
        with session_scope() as session:
            rows = session.execute(
                select(Workspace, DatasetRecord)
                .join(DatasetRecord, DatasetRecord.workspace_id == Workspace.id)
                .where(Workspace.owner_id == owner_id)
                .order_by(Workspace.updated_at.desc())
            ).all()
            return WorkspaceListResponse(
                workspaces=[_workspace_summary(workspace, dataset) for workspace, dataset in rows]
            )
    except SQLAlchemyError as exc:
        raise PersistenceError(
            "Workspace metadata is unavailable. Confirm that PostgreSQL is running "
            "and apply the latest Alembic migration."
        ) from exc


def get_workspace_detail(dataset_id: str, owner_id: int) -> WorkspaceDetail | None:
    workspace_id = _parse_workspace_id(dataset_id)
    if workspace_id is None:
        return None
    try:
        with session_scope() as session:
            row = session.execute(
                select(Workspace, DatasetRecord)
                .join(DatasetRecord, DatasetRecord.workspace_id == Workspace.id)
                .where(
                    Workspace.id == workspace_id,
                    Workspace.owner_id == owner_id,
                )
            ).one_or_none()
            if row is None:
                return None
            workspace, dataset = row
            batch = _latest_batch(session, workspace_id)
            recommendations: list[RemediationRecommendation] = []
            decisions: dict[str, RecommendationDecision] = {}
            if batch is not None:
                records = session.scalars(
                    select(RecommendationRecord)
                    .where(RecommendationRecord.batch_id == batch.id)
                    .order_by(RecommendationRecord.ordinal)
                ).all()
                recommendations = [_recommendation_from_record(record) for record in records]
                decision_rows = session.scalars(
                    select(HumanDecision).where(HumanDecision.batch_id == batch.id)
                ).all()
                decisions = {
                    decision.recommendation_key: RecommendationDecision(decision.decision)
                    for decision in decision_rows
                }
            summary = _workspace_summary(workspace, dataset)
            return WorkspaceDetail(
                **summary.model_dump(),
                recommendations_generated=batch is not None,
                recommendations=recommendations,
                decisions=decisions,
            )
    except SQLAlchemyError as exc:
        raise PersistenceError("Workspace metadata could not be loaded.") from exc


def workspace_is_owned_by(dataset_id: str, owner_id: int) -> bool:
    workspace_id = _parse_workspace_id(dataset_id)
    if workspace_id is None:
        return False
    try:
        with session_scope() as session:
            return session.scalar(
                select(Workspace.id).where(
                    Workspace.id == workspace_id,
                    Workspace.owner_id == owner_id,
                )
            ) is not None
    except SQLAlchemyError as exc:
        raise PersistenceError("Workspace ownership could not be verified.") from exc


def update_workspace_readiness(
    dataset_id: str,
    readiness: ReadinessSummary,
    *,
    session: Session | None = None,
) -> None:
    workspace_id = _parse_workspace_id(dataset_id)
    if workspace_id is None:
        return

    def update(db: Session) -> None:
        workspace = db.get(Workspace, workspace_id)
        if workspace is None:
            return
        workspace.readiness_status = readiness.status.value
        workspace.updated_at = datetime.now(timezone.utc)

    _run_persisted(
        update,
        session=session,
        error_message="Workspace readiness could not be persisted.",
    )


def sync_clarifications(
    clarifications: DatasetClarifications,
) -> DatasetClarifications:
    workspace_id = _parse_workspace_id(clarifications.dataset_id)
    if workspace_id is None:
        raise PersistenceError("Dataset workspace metadata was not found.")
    try:
        with session_scope() as session:
            if session.get(Workspace, workspace_id) is None:
                raise PersistenceError("Dataset workspace metadata was not found.")
            current_ids = {question.question_id for question in clarifications.questions}
            existing = {
                record.question_id: record
                for record in session.scalars(
                    select(ClarificationRecord).where(
                        ClarificationRecord.workspace_id == workspace_id
                    )
                ).all()
            }
            for question in clarifications.questions:
                record = existing.get(question.question_id)
                if record is None:
                    record = ClarificationRecord(
                        workspace_id=workspace_id,
                        question_id=question.question_id,
                        finding_type=question.related_finding.type.value,
                        file_name=question.related_finding.file,
                        affected_column=question.related_finding.affected_column,
                        question=question.question,
                        why_this_matters=question.why_this_matters,
                        status=question.status.value,
                        answer=question.answer,
                    )
                    session.add(record)
                else:
                    record.finding_type = question.related_finding.type.value
                    record.file_name = question.related_finding.file
                    record.affected_column = question.related_finding.affected_column
                    record.question = question.question
                    record.why_this_matters = question.why_this_matters
            for stale_id, record in existing.items():
                if stale_id not in current_ids:
                    session.delete(record)
            session.flush()
            records = session.scalars(
                select(ClarificationRecord)
                .where(ClarificationRecord.workspace_id == workspace_id)
                .order_by(ClarificationRecord.question_id)
            ).all()
            return _clarifications_from_records(clarifications.dataset_id, records)
    except PersistenceError:
        raise
    except SQLAlchemyError as exc:
        raise PersistenceError("Clarification metadata could not be persisted.") from exc


def save_clarification_response(
    dataset_id: str,
    *,
    question_id: str,
    status: ClarificationStatus,
    answer: str | None,
    session: Session | None = None,
) -> DatasetClarifications:
    workspace_id = _parse_workspace_id(dataset_id)
    if workspace_id is None:
        raise PersistenceError("Dataset workspace metadata was not found.")

    def save(db: Session) -> DatasetClarifications:
        record = db.get(ClarificationRecord, (workspace_id, question_id))
        if record is None:
            raise LookupError("Clarification question was not found for this dataset.")
        record.status = status.value
        record.answer = answer
        record.updated_at = datetime.now(timezone.utc)
        db.flush()
        records = db.scalars(
            select(ClarificationRecord)
            .where(ClarificationRecord.workspace_id == workspace_id)
            .order_by(ClarificationRecord.question_id)
        ).all()
        return _clarifications_from_records(dataset_id, records)

    return _run_persisted(
        save,
        session=session,
        error_message="Clarification response could not be persisted.",
    )


def save_recommendation_batch(
    dataset_id: str,
    response: RecommendationResponse,
    *,
    session: Session | None = None,
) -> None:
    workspace_id = _required_workspace_id(dataset_id)

    def save(db: Session) -> None:
        workspace = db.scalar(
            select(Workspace).where(Workspace.id == workspace_id).with_for_update()
        )
        if workspace is None:
            raise LookupError("Dataset workspace metadata was not found.")
        generation = db.scalar(
            select(func.coalesce(func.max(RecommendationBatch.generation), 0)).where(
                RecommendationBatch.workspace_id == workspace_id
            )
        )
        batch = RecommendationBatch(
            id=uuid4(),
            workspace_id=workspace_id,
            generation=int(generation or 0) + 1,
        )
        db.add(batch)
        db.flush()
        for index, recommendation in enumerate(response.recommendations):
            key = recommendation_key(index)
            db.add(
                RecommendationRecord(
                    id=uuid4(),
                    batch_id=batch.id,
                    recommendation_key=key,
                    ordinal=index,
                    finding_type=recommendation.related_finding.type.value,
                    file_name=recommendation.related_finding.file,
                    affected_column=recommendation.related_finding.affected_column,
                    short_title=recommendation.short_title,
                    rationale=recommendation.rationale,
                    proposed_action=recommendation.proposed_action,
                    confidence=recommendation.confidence,
                    human_approval_required=recommendation.human_approval_required,
                    assumptions=recommendation.assumptions,
                )
            )
            db.add(
                HumanDecision(
                    id=uuid4(),
                    workspace_id=workspace_id,
                    batch_id=batch.id,
                    recommendation_key=key,
                    decision=RecommendationDecision.PENDING.value,
                )
            )
        workspace.workflow_status = "recommendations_ready"
        workspace.current_stage = "review"
        workspace.updated_at = datetime.now(timezone.utc)

    _run_persisted(
        save,
        session=session,
        error_message="Generated recommendations could not be persisted.",
    )


def save_human_decision(
    dataset_id: str,
    *,
    recommendation_key_value: str,
    decision: RecommendationDecision,
    session: Session | None = None,
) -> dict[str, RecommendationDecision]:
    workspace_id = _required_workspace_id(dataset_id)

    def save(db: Session) -> dict[str, RecommendationDecision]:
        batch = _latest_batch(db, workspace_id)
        if batch is None:
            raise LookupError("No persisted recommendations are available for review.")
        record = db.scalar(
            select(HumanDecision).where(
                HumanDecision.batch_id == batch.id,
                HumanDecision.recommendation_key == recommendation_key_value,
            )
        )
        if record is None:
            raise LookupError("Recommendation was not found in the current generation.")
        record.decision = decision.value
        record.updated_at = datetime.now(timezone.utc)
        workspace = db.get(Workspace, workspace_id)
        if workspace is not None:
            workspace.workflow_status = "in_review"
            workspace.current_stage = "review"
            workspace.updated_at = datetime.now(timezone.utc)
        db.flush()
        rows = db.scalars(
            select(HumanDecision).where(HumanDecision.batch_id == batch.id)
        ).all()
        return {
            row.recommendation_key: RecommendationDecision(row.decision)
            for row in rows
        }

    return _run_persisted(
        save,
        session=session,
        error_message="The human decision could not be persisted.",
    )


def persist_audit_event(
    event: AuditEvent,
    *,
    session: Session | None = None,
) -> None:
    workspace_id = _parse_workspace_id(event.dataset_id)
    if workspace_id is None:
        raise PersistenceError("Dataset workspace metadata was not found.")

    def save(db: Session) -> None:
        workspace = db.get(Workspace, workspace_id)
        if workspace is None:
            raise PersistenceError("Dataset workspace metadata was not found.")
        db.add(
            AuditEventRecord(
                workspace_id=workspace_id,
                timestamp=event.timestamp,
                action=event.action.value,
                status=event.status.value,
                summary=event.summary,
            )
        )
        _apply_workflow_event(workspace, event.action, event.status)
        workspace.updated_at = event.timestamp
        db.flush()

    _run_persisted(
        save,
        session=session,
        error_message="The audit event could not be persisted.",
    )


def read_persisted_audit_trail(dataset_id: str) -> DatasetAuditTrail:
    workspace_id = _parse_workspace_id(dataset_id)
    if workspace_id is None:
        raise PersistenceError("Dataset workspace metadata was not found.")
    try:
        with session_scope() as session:
            if session.get(Workspace, workspace_id) is None:
                raise PersistenceError("Dataset workspace metadata was not found.")
            rows = session.scalars(
                select(AuditEventRecord)
                .where(AuditEventRecord.workspace_id == workspace_id)
                .order_by(AuditEventRecord.id)
            ).all()
            return DatasetAuditTrail(
                dataset_id=dataset_id,
                events=[
                    AuditEvent(
                        timestamp=(
                            row.timestamp
                            if row.timestamp.tzinfo is not None
                            else row.timestamp.replace(tzinfo=timezone.utc)
                        ),
                        action=AuditAction(row.action),
                        status=AuditStatus(row.status),
                        dataset_id=dataset_id,
                        summary=row.summary,
                    )
                    for row in rows
                ],
            )
    except PersistenceError:
        raise
    except SQLAlchemyError as exc:
        raise PersistenceError("The persisted audit trail could not be loaded.") from exc


def recommendation_key(index: int) -> str:
    return f"recommendation-{index}"


def _latest_batch(session, workspace_id: UUID) -> RecommendationBatch | None:
    return session.scalar(
        select(RecommendationBatch)
        .where(RecommendationBatch.workspace_id == workspace_id)
        .order_by(RecommendationBatch.generation.desc())
        .limit(1)
    )


def _workspace_summary(
    workspace: Workspace,
    dataset: DatasetRecord,
) -> WorkspaceSummary:
    return WorkspaceSummary(
        dataset_id=str(dataset.id),
        dataset_name=workspace.name,
        original_file_name=dataset.original_file_name,
        file_count=dataset.extracted_file_count,
        archive_size_bytes=dataset.archive_size_bytes,
        workflow_status=workspace.workflow_status,
        current_stage=workspace.current_stage,
        readiness_status=workspace.readiness_status,
        created_at=workspace.created_at,
        updated_at=workspace.updated_at,
    )


def _recommendation_from_record(
    record: RecommendationRecord,
) -> RemediationRecommendation:
    return RemediationRecommendation(
        related_finding=FindingReference(
            type=record.finding_type,
            file=record.file_name,
            affected_column=record.affected_column,
        ),
        short_title=record.short_title,
        rationale=record.rationale,
        proposed_action=record.proposed_action,
        confidence=record.confidence,
        human_approval_required=record.human_approval_required,
        assumptions=list(record.assumptions or []),
    )


def _clarifications_from_records(
    dataset_id: str,
    records: list[ClarificationRecord],
) -> DatasetClarifications:
    questions = [
        ClarificationQuestion(
            question_id=record.question_id,
            related_finding=FindingReference(
                type=record.finding_type,
                file=record.file_name,
                affected_column=record.affected_column,
            ),
            question=record.question,
            why_this_matters=record.why_this_matters,
            status=ClarificationStatus(record.status),
            answer=record.answer,
            updated_at=record.updated_at,
        )
        for record in records
    ]
    return DatasetClarifications(
        dataset_id=dataset_id,
        summary=ClarificationSummary(
            total_count=len(questions),
            answered_count=sum(q.status == ClarificationStatus.ANSWERED for q in questions),
            deferred_count=sum(q.status == ClarificationStatus.DEFERRED for q in questions),
            unanswered_count=sum(q.status == ClarificationStatus.UNANSWERED for q in questions),
        ),
        questions=questions,
    )


def _apply_workflow_event(
    workspace: Workspace,
    action: AuditAction,
    status: AuditStatus,
) -> None:
    stage_by_action = {
        AuditAction.UPLOAD: ("uploaded", "inspection"),
        AuditAction.INSPECTION: ("inspected", "clarifications"),
        AuditAction.CLARIFICATION_REVIEW: ("clarifying", "clarifications"),
        AuditAction.CLARIFICATION_RESPONSE: ("clarifying", "clarifications"),
        AuditAction.RECOMMENDATION_GENERATION: ("recommendations_ready", "review"),
        AuditAction.HUMAN_DECISION: ("in_review", "review"),
        AuditAction.REMEDIATION_PREVIEW: ("in_review", "remediation"),
        AuditAction.REMEDIATION_APPLY: ("remediated", "validation"),
        AuditAction.VALIDATION: ("validated", "package"),
        AuditAction.PACKAGE_GENERATION: ("package_ready", "package"),
        AuditAction.PACKAGE_DOWNLOAD: ("completed", "package"),
    }
    workflow_status, stage = stage_by_action[action]
    if status == AuditStatus.FAILURE:
        workspace.workflow_status = "blocked"
        workspace.current_stage = stage
        return

    non_regressing_actions = {
        AuditAction.UPLOAD,
        AuditAction.INSPECTION,
        AuditAction.CLARIFICATION_REVIEW,
    }
    if action in non_regressing_actions and _workflow_rank(
        workspace.workflow_status
    ) > _workflow_rank(workflow_status):
        return
    workspace.workflow_status = workflow_status
    workspace.current_stage = stage


def _workflow_rank(status: str) -> int:
    order = [
        "uploaded",
        "inspected",
        "clarifying",
        "recommendations_ready",
        "in_review",
        "remediated",
        "validated",
        "package_ready",
        "completed",
    ]
    try:
        return order.index(status)
    except ValueError:
        return -1


def _parse_workspace_id(dataset_id: str) -> UUID | None:
    try:
        parsed = UUID(dataset_id)
    except ValueError:
        return None
    return parsed if str(parsed) == dataset_id else None


def _required_workspace_id(dataset_id: str) -> UUID:
    workspace_id = _parse_workspace_id(dataset_id)
    if workspace_id is None:
        raise LookupError("Dataset workspace metadata was not found.")
    return workspace_id
