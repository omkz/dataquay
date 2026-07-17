from pathlib import Path

from fastapi import APIRouter

from app.schemas import CsvProfile
from app.services.csv_profiler import profile_csv

router = APIRouter(prefix="/api/inspect", tags=["inspection"])

SAMPLE_CSV_PATH = (
    Path(__file__).resolve().parents[3]
    / "sample-data"
    / "soil-study"
    / "participants.csv"
)


@router.get("/sample", response_model=CsvProfile)
def inspect_sample() -> CsvProfile:
    return profile_csv(SAMPLE_CSV_PATH)
