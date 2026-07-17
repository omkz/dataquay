from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.agents.data_steward import AIConfigurationError, generate_recommendations
from app.schemas import CsvProfile, DatasetInspection, RecommendationResponse
from app.services.csv_profiler import profile_csv
from app.services.dataset_inspector import inspect_dataset
from app.services.dataset_workspace import (
    DatasetNotFoundError,
    inspect_dataset_workspace,
)

router = APIRouter(prefix="/api/inspect", tags=["inspection"])

SAMPLE_DATASET_PATH = (
    Path(__file__).resolve().parents[3] / "sample-data" / "soil-study"
)
SAMPLE_CSV_PATH = SAMPLE_DATASET_PATH / "participants.csv"


@router.get("/sample", response_model=CsvProfile)
def inspect_sample() -> CsvProfile:
    return profile_csv(SAMPLE_CSV_PATH)


@router.get("/sample-dataset", response_model=DatasetInspection)
def inspect_sample_dataset() -> DatasetInspection:
    return inspect_dataset(SAMPLE_DATASET_PATH)


@router.get("/datasets/{dataset_id}", response_model=DatasetInspection)
def inspect_uploaded_dataset(dataset_id: str) -> DatasetInspection:
    try:
        return inspect_dataset_workspace(dataset_id)
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/sample-dataset/recommendations",
    response_model=RecommendationResponse,
)
async def recommend_sample_dataset_remediation() -> RecommendationResponse:
    inspection = inspect_dataset(SAMPLE_DATASET_PATH)
    try:
        return await generate_recommendations(inspection)
    except AIConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post(
    "/datasets/{dataset_id}/recommendations",
    response_model=RecommendationResponse,
)
async def recommend_uploaded_dataset_remediation(
    dataset_id: str,
) -> RecommendationResponse:
    try:
        inspection = inspect_dataset_workspace(dataset_id)
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        return await generate_recommendations(inspection)
    except AIConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
