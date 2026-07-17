from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.schemas import (
    RemediationApplyResponse,
    RemediationPreviewRequest,
    RemediationPreviewResponse,
)
from app.services.dataset_inspector import inspect_dataset
from app.services.dataset_workspace import DatasetNotFoundError
from app.services.dataset_workflow import (
    invalidate_generated_package,
    resolve_dataset_workflow_workspace,
)
from app.services.remediation_apply import apply_approved_remediation_actions
from app.services.remediation_preview import (
    UnknownFindingReferenceError,
    preview_remediation_actions,
)

router = APIRouter(prefix="/api/remediate", tags=["remediation"])

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
    "/sample-dataset/preview",
    response_model=RemediationPreviewResponse,
)
def preview_sample_dataset_remediation(
    request: RemediationPreviewRequest,
) -> RemediationPreviewResponse:
    inspection = inspect_dataset(SAMPLE_DATASET_PATH)
    try:
        return preview_remediation_actions(
            request.approved_recommendations,
            inspection.findings,
        )
    except UnknownFindingReferenceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/sample-dataset/apply",
    response_model=RemediationApplyResponse,
)
def apply_sample_dataset_remediation(
    request: RemediationPreviewRequest,
) -> RemediationApplyResponse:
    try:
        return apply_approved_remediation_actions(
            request.approved_recommendations,
            SAMPLE_DATASET_PATH,
            SAMPLE_WORKING_COPY_PATH,
        )
    except UnknownFindingReferenceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/datasets/{dataset_id}/preview",
    response_model=RemediationPreviewResponse,
)
def preview_uploaded_dataset_remediation(
    dataset_id: str,
    request: RemediationPreviewRequest,
) -> RemediationPreviewResponse:
    try:
        workflow = resolve_dataset_workflow_workspace(dataset_id)
        inspection = inspect_dataset(workflow.source_directory)
        return preview_remediation_actions(
            request.approved_recommendations,
            inspection.findings,
        )
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except UnknownFindingReferenceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/datasets/{dataset_id}/apply",
    response_model=RemediationApplyResponse,
)
def apply_uploaded_dataset_remediation(
    dataset_id: str,
    request: RemediationPreviewRequest,
) -> RemediationApplyResponse:
    try:
        workflow = resolve_dataset_workflow_workspace(dataset_id)
        result = apply_approved_remediation_actions(
            request.approved_recommendations,
            workflow.source_directory,
            workflow.working_copy_directory,
        )
        invalidate_generated_package(workflow)
        return result
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except UnknownFindingReferenceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
