from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.auth import WorkspaceOwner
from app.schemas import AuditAction, AuditStatus, DatasetValidationResult
from app.services.audit_trail import append_audit_event, commit_audited_mutation
from app.services.dataset_workspace import DatasetNotFoundError
from app.services.dataset_workflow import resolve_dataset_workflow_workspace
from app.services.remediation_validation import (
    ValidationUnavailableError,
    validate_remediated_dataset,
)
from app.services.workflow_repository import update_workspace_readiness

router = APIRouter(prefix="/api/validate", tags=["validation"])

SAMPLE_DATASET_PATH = (
    Path(__file__).resolve().parents[3] / "sample-data" / "soil-study"
)
SAMPLE_WORKING_COPY_PATH = (
    Path(__file__).resolve().parents[2]
    / ".dataquay"
    / "working-copies"
    / "soil-study"
)


@router.post(
    "/sample-dataset",
    response_model=DatasetValidationResult,
)
def validate_sample_dataset_remediation() -> DatasetValidationResult:
    try:
        return validate_remediated_dataset(
            SAMPLE_DATASET_PATH,
            SAMPLE_WORKING_COPY_PATH,
        )
    except ValidationUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/datasets/{dataset_id}",
    response_model=DatasetValidationResult,
)
def validate_uploaded_dataset_remediation(
    dataset_id: str,
    _owner: WorkspaceOwner,
) -> DatasetValidationResult:
    try:
        workflow = resolve_dataset_workflow_workspace(dataset_id)
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        validation = validate_remediated_dataset(
            workflow.source_directory,
            workflow.working_copy_directory,
        )
    except ValidationUnavailableError as exc:
        append_audit_event(
            workflow.workspace_directory,
            dataset_id=dataset_id,
            action=AuditAction.VALIDATION,
            status=AuditStatus.FAILURE,
            summary=(
                "Validation could not run because the working copy or checksum "
                "manifest was unavailable."
            ),
        )
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception:
        append_audit_event(
            workflow.workspace_directory,
            dataset_id=dataset_id,
            action=AuditAction.VALIDATION,
            status=AuditStatus.FAILURE,
            summary="Validation failed before checksum and finding results were available.",
        )
        raise
    commit_audited_mutation(
        workflow.workspace_directory,
        dataset_id=dataset_id,
        action=AuditAction.VALIDATION,
        status=AuditStatus.SUCCESS,
        summary=(
            f"Validation resolved {len(validation.resolved_findings)} findings, "
            f"left {len(validation.remaining_findings)} remaining, and reported "
            f"readiness as {validation.readiness.status.value}."
        ),
        mutation=lambda session: update_workspace_readiness(
            dataset_id,
            validation.readiness,
            session=session,
        ),
    )
    return validation
