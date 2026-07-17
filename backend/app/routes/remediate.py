from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.schemas import RemediationPreviewRequest, RemediationPreviewResponse
from app.services.dataset_inspector import inspect_dataset
from app.services.remediation_preview import (
    UnknownFindingReferenceError,
    preview_remediation_actions,
)

router = APIRouter(prefix="/api/remediate", tags=["remediation"])

SAMPLE_DATASET_PATH = (
    Path(__file__).resolve().parents[3] / "sample-data" / "soil-study"
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
