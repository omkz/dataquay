from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.schemas import (
    AuditAction,
    AuditStatus,
    RemediationApplyResponse,
    RemediationPreviewRequest,
    RemediationPreviewResponse,
)
from app.services.audit_trail import append_audit_event
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
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        inspection = inspect_dataset(workflow.source_directory)
        preview = preview_remediation_actions(
            request.approved_recommendations,
            inspection.findings,
        )
    except UnknownFindingReferenceError as exc:
        append_audit_event(
            workflow.workspace_directory,
            dataset_id=dataset_id,
            action=AuditAction.REMEDIATION_PREVIEW,
            status=AuditStatus.FAILURE,
            summary=(
                "Remediation preview was rejected because an approved proposal "
                "did not match a current finding."
            ),
        )
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:
        append_audit_event(
            workflow.workspace_directory,
            dataset_id=dataset_id,
            action=AuditAction.REMEDIATION_PREVIEW,
            status=AuditStatus.FAILURE,
            summary="Remediation preview failed before actions were classified.",
        )
        raise
    automatic_count = sum(
        action.can_apply_automatically for action in preview.actions
    )
    append_audit_event(
        workflow.workspace_directory,
        dataset_id=dataset_id,
        action=AuditAction.REMEDIATION_PREVIEW,
        status=AuditStatus.SUCCESS,
        summary=(
            f"Previewed {len(preview.actions)} approved actions: "
            f"{automatic_count} automatic and "
            f"{len(preview.actions) - automatic_count} manual."
        ),
    )
    return preview


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
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        result = apply_approved_remediation_actions(
            request.approved_recommendations,
            workflow.source_directory,
            workflow.working_copy_directory,
        )
        invalidate_generated_package(workflow)
    except UnknownFindingReferenceError as exc:
        append_audit_event(
            workflow.workspace_directory,
            dataset_id=dataset_id,
            action=AuditAction.REMEDIATION_APPLY,
            status=AuditStatus.FAILURE,
            summary=(
                "Remediation apply was rejected because an approved proposal "
                "did not match a current finding."
            ),
        )
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:
        append_audit_event(
            workflow.workspace_directory,
            dataset_id=dataset_id,
            action=AuditAction.REMEDIATION_APPLY,
            status=AuditStatus.FAILURE,
            summary="Remediation failed while preparing or updating the working copy.",
        )
        raise
    append_audit_event(
        workflow.workspace_directory,
        dataset_id=dataset_id,
        action=AuditAction.REMEDIATION_APPLY,
        status=AuditStatus.SUCCESS,
        summary=(
            f"Applied {len(result.applied_actions)} safe actions, skipped "
            f"{len(result.skipped_actions)}, and recorded "
            f"{len(result.failed_actions)} failed actions in the working copy."
        ),
    )
    return result
