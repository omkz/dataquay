from fastapi import APIRouter, HTTPException

from app.schemas import (
    AuditAction,
    AuditStatus,
    RecommendationDecisionRequest,
    RecommendationDecisionResponse,
    WorkspaceDetail,
    WorkspaceListResponse,
)
from app.services.audit_trail import append_audit_event
from app.services.dataset_workspace import DatasetNotFoundError
from app.services.dataset_workflow import resolve_dataset_workflow_workspace
from app.services.workflow_repository import (
    PersistenceError,
    get_workspace_detail,
    list_workspaces,
    save_human_decision,
)

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


@router.get("", response_model=WorkspaceListResponse)
def list_dataset_workspaces() -> WorkspaceListResponse:
    try:
        return list_workspaces()
    except PersistenceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/{dataset_id}", response_model=WorkspaceDetail)
def get_dataset_workspace(dataset_id: str) -> WorkspaceDetail:
    try:
        resolve_dataset_workflow_workspace(dataset_id)
        workspace = get_workspace_detail(dataset_id)
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PersistenceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if workspace is None:
        raise HTTPException(status_code=404, detail="Dataset workspace was not found.")
    return workspace


@router.put(
    "/{dataset_id}/decision",
    response_model=RecommendationDecisionResponse,
)
def update_recommendation_decision(
    dataset_id: str,
    request: RecommendationDecisionRequest,
) -> RecommendationDecisionResponse:
    try:
        workflow = resolve_dataset_workflow_workspace(dataset_id)
        decisions = save_human_decision(
            dataset_id,
            recommendation_key_value=request.recommendation_key,
            decision=request.decision,
        )
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PersistenceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    append_audit_event(
        workflow.workspace_directory,
        dataset_id=dataset_id,
        action=AuditAction.HUMAN_DECISION,
        status=AuditStatus.SUCCESS,
        summary=(
            f"A remediation recommendation was marked {request.decision.value}. "
            "The decision contains no raw dataset values."
        ),
    )
    return RecommendationDecisionResponse(decisions=decisions)
