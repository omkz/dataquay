from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.schemas import (
    RemediationApplyResponse,
    RemediationPreviewRequest,
    RemediationPreviewResponse,
)
from app.services.dataset_inspector import inspect_dataset
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
