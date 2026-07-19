from fastapi import APIRouter, HTTPException

from app.auth import WorkspaceOwner
from app.schemas import DatasetAuditTrail
from app.services.audit_trail import read_audit_trail
from app.services.dataset_workspace import DatasetNotFoundError
from app.services.dataset_workflow import resolve_dataset_workflow_workspace

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get(
    "/datasets/{dataset_id}",
    response_model=DatasetAuditTrail,
)
def get_dataset_audit_trail(
    dataset_id: str,
    _owner: WorkspaceOwner,
) -> DatasetAuditTrail:
    try:
        workflow = resolve_dataset_workflow_workspace(dataset_id)
        return read_audit_trail(
            workflow.workspace_directory,
            dataset_id=dataset_id,
        )
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
