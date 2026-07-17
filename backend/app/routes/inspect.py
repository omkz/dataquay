from pathlib import Path

from fastapi import APIRouter

from app.schemas import CsvProfile, DatasetInspection
from app.services.csv_profiler import profile_csv
from app.services.dataset_inspector import inspect_dataset

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
