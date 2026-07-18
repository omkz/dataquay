from fastapi import APIRouter, HTTPException

from app.schemas import (
    AuditAction,
    AuditStatus,
    ClarificationUpdateRequest,
    DatasetClarifications,
)
from app.services.audit_trail import append_audit_event
from app.services.clarifications import (
    ClarificationError,
    ClarificationQuestionNotFoundError,
    get_dataset_clarifications,
    store_dataset_clarifications,
    update_dataset_clarification,
)
from app.services.dataset_workspace import (
    DatasetNotFoundError,
    inspect_dataset_workspace,
)
from app.services.dataset_workflow import resolve_dataset_workflow_workspace
from app.services.workflow_repository import (
    PersistenceError,
    save_clarification_response,
    sync_clarifications,
)

router = APIRouter(prefix="/api/clarify", tags=["clarifications"])


@router.get("/datasets/{dataset_id}", response_model=DatasetClarifications)
def get_uploaded_dataset_clarifications(dataset_id: str) -> DatasetClarifications:
    try:
        workflow = resolve_dataset_workflow_workspace(dataset_id)
        inspection = inspect_dataset_workspace(dataset_id)
        generated = get_dataset_clarifications(
            workflow.workspace_directory,
            dataset_id=dataset_id,
            findings=inspection.findings,
        )
        clarifications = sync_clarifications(generated)
        store_dataset_clarifications(workflow.workspace_directory, clarifications)
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ClarificationError, PersistenceError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    append_audit_event(
        workflow.workspace_directory,
        dataset_id=dataset_id,
        action=AuditAction.CLARIFICATION_REVIEW,
        status=AuditStatus.SUCCESS,
        summary=(
            f"Reviewed {clarifications.summary.total_count} clarification questions; "
            f"{clarifications.summary.answered_count} answered, "
            f"{clarifications.summary.deferred_count} deferred, and "
            f"{clarifications.summary.unanswered_count} unanswered."
        ),
    )
    return clarifications


@router.put(
    "/datasets/{dataset_id}/questions/{question_id}",
    response_model=DatasetClarifications,
)
def update_uploaded_dataset_clarification(
    dataset_id: str,
    question_id: str,
    request: ClarificationUpdateRequest,
) -> DatasetClarifications:
    try:
        workflow = resolve_dataset_workflow_workspace(dataset_id)
        inspection = inspect_dataset_workspace(dataset_id)
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        generated = get_dataset_clarifications(
            workflow.workspace_directory,
            dataset_id=dataset_id,
            findings=inspection.findings,
        )
        synced = sync_clarifications(generated)
        store_dataset_clarifications(workflow.workspace_directory, synced)
        updated = update_dataset_clarification(
            workflow.workspace_directory,
            dataset_id=dataset_id,
            findings=inspection.findings,
            question_id=question_id,
            update=request,
        )
        updated_question = next(
            question
            for question in updated.questions
            if question.question_id == question_id
        )
        clarifications = save_clarification_response(
            dataset_id,
            question_id=question_id,
            status=updated_question.status,
            answer=updated_question.answer,
        )
        store_dataset_clarifications(workflow.workspace_directory, clarifications)
    except ClarificationQuestionNotFoundError as exc:
        append_audit_event(
            workflow.workspace_directory,
            dataset_id=dataset_id,
            action=AuditAction.CLARIFICATION_RESPONSE,
            status=AuditStatus.FAILURE,
            summary="A clarification response was rejected because the question was not found.",
        )
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PersistenceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ClarificationError as exc:
        append_audit_event(
            workflow.workspace_directory,
            dataset_id=dataset_id,
            action=AuditAction.CLARIFICATION_RESPONSE,
            status=AuditStatus.FAILURE,
            summary="A clarification response could not be stored safely.",
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    status_label = "answered" if request.decision.value == "answer" else "deferred"
    append_audit_event(
        workflow.workspace_directory,
        dataset_id=dataset_id,
        action=AuditAction.CLARIFICATION_RESPONSE,
        status=AuditStatus.SUCCESS,
        summary=(
            f"A clarification question was {status_label}. The response content "
            "was excluded from the audit trail."
        ),
    )
    return clarifications
