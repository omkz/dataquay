from fastapi import APIRouter, HTTPException

from app.auth import WorkspaceOwner
from app.schemas import (
    AuditAction,
    AuditStatus,
    ClarificationUpdateRequest,
    DatasetClarifications,
)
from app.services.audit_trail import append_audit_event, commit_audited_mutation
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
    save_clarification_response,
    sync_clarifications,
)

router = APIRouter(prefix="/api/clarify", tags=["clarifications"])


@router.get("/datasets/{dataset_id}", response_model=DatasetClarifications)
def get_uploaded_dataset_clarifications(
    dataset_id: str,
    _owner: WorkspaceOwner,
) -> DatasetClarifications:
    try:
        workflow = resolve_dataset_workflow_workspace(dataset_id)
        inspection = inspect_dataset_workspace(dataset_id)
        generated = get_dataset_clarifications(
            workflow.workspace_directory,
            dataset_id=dataset_id,
            findings=inspection.findings,
            use_snapshot=False,
        )
        clarifications = sync_clarifications(generated)
        store_dataset_clarifications(workflow.workspace_directory, clarifications)
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ClarificationError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return clarifications


@router.put(
    "/datasets/{dataset_id}/questions/{question_id}",
    response_model=DatasetClarifications,
)
def update_uploaded_dataset_clarification(
    dataset_id: str,
    question_id: str,
    request: ClarificationUpdateRequest,
    _owner: WorkspaceOwner,
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
            use_snapshot=False,
        )
        synced = sync_clarifications(generated)
        store_dataset_clarifications(workflow.workspace_directory, synced)
        updated = update_dataset_clarification(
            workflow.workspace_directory,
            dataset_id=dataset_id,
            findings=inspection.findings,
            question_id=question_id,
            update=request,
            persist=False,
            use_snapshot=False,
        )
        updated_question = next(
            question
            for question in updated.questions
            if question.question_id == question_id
        )
    except ClarificationQuestionNotFoundError as exc:
        append_audit_event(
            workflow.workspace_directory,
            dataset_id=dataset_id,
            action=AuditAction.CLARIFICATION_RESPONSE,
            status=AuditStatus.FAILURE,
            summary="A clarification response was rejected because the question was not found.",
        )
        raise HTTPException(status_code=404, detail=str(exc)) from exc
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
    clarifications = commit_audited_mutation(
        workflow.workspace_directory,
        dataset_id=dataset_id,
        action=AuditAction.CLARIFICATION_RESPONSE,
        status=AuditStatus.SUCCESS,
        summary=(
            f"A clarification question was {status_label}. The response content "
            "was excluded from the audit trail."
        ),
        mutation=lambda session: save_clarification_response(
            dataset_id,
            question_id=question_id,
            status=updated_question.status,
            answer=updated_question.answer,
            session=session,
        ),
    )
    store_dataset_clarifications(workflow.workspace_directory, clarifications)
    return clarifications
