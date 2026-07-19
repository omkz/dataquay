from fastapi import APIRouter, HTTPException

from app.auth import CurrentUser, WorkspaceOwner
from app.schemas import (
    AuditAction,
    AuditStatus,
    RecommendationDecisionRequest,
    RecommendationDecisionResponse,
    WorkspaceDetail,
    WorkspaceListResponse,
)
from app.services.audit_trail import commit_audited_mutation
from app.services.dataset_workspace import DatasetNotFoundError
from app.services.dataset_workflow import resolve_dataset_workflow_workspace
from app.services.workflow_repository import (
    get_workspace_detail,
    list_workspaces,
    save_human_decision,
)

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


@router.get("", response_model=WorkspaceListResponse)
def list_dataset_workspaces(user: CurrentUser) -> WorkspaceListResponse:
    return list_workspaces(user.user_id)


@router.get("/{dataset_id}", response_model=WorkspaceDetail)
def get_dataset_workspace(
    dataset_id: str,
    owner: WorkspaceOwner,
) -> WorkspaceDetail:
    try:
        resolve_dataset_workflow_workspace(dataset_id)
        workspace = get_workspace_detail(dataset_id, owner.user_id)
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
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
    _owner: WorkspaceOwner,
) -> RecommendationDecisionResponse:
    try:
        workflow = resolve_dataset_workflow_workspace(dataset_id)
        decisions = commit_audited_mutation(
            workflow.workspace_directory,
            dataset_id=dataset_id,
            action=AuditAction.HUMAN_DECISION,
            status=AuditStatus.SUCCESS,
            summary=(
                f"A remediation recommendation was marked {request.decision.value}. "
                "The decision contains no raw dataset values."
            ),
            mutation=lambda session: save_human_decision(
                dataset_id,
                recommendation_key_value=request.recommendation_key,
                decision=request.decision,
                session=session,
            ),
        )
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return RecommendationDecisionResponse(decisions=decisions)
