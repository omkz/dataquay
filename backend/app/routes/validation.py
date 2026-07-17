from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.schemas import DatasetValidationResult
from app.services.dataset_workspace import DatasetNotFoundError
from app.services.dataset_workflow import resolve_dataset_workflow_workspace
from app.services.remediation_validation import (
    ValidationUnavailableError,
    validate_remediated_dataset,
)

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
) -> DatasetValidationResult:
    try:
        workflow = resolve_dataset_workflow_workspace(dataset_id)
        return validate_remediated_dataset(
            workflow.source_directory,
            workflow.working_copy_directory,
        )
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValidationUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
