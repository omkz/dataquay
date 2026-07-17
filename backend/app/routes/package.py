from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.schemas import PackageGenerationResult
from app.services.package_generator import (
    PackageGenerationError,
    generate_dataset_package,
    get_package_zip_path,
)

router = APIRouter(prefix="/api/package", tags=["package"])

SAMPLE_DATASET_PATH = (
    Path(__file__).resolve().parents[3] / "sample-data" / "soil-study"
)
SAMPLE_WORKING_COPY_PATH = (
    Path(__file__).resolve().parents[2]
    / ".dataquay"
    / "working-copies"
    / "soil-study"
)
SAMPLE_PACKAGE_PATH = (
    Path(__file__).resolve().parents[2]
    / ".dataquay"
    / "packages"
    / "soil-study"
)


@router.post(
    "/sample-dataset",
    response_model=PackageGenerationResult,
)
def generate_sample_dataset_package() -> PackageGenerationResult:
    try:
        return generate_dataset_package(
            SAMPLE_DATASET_PATH,
            SAMPLE_WORKING_COPY_PATH,
            SAMPLE_PACKAGE_PATH,
        )
    except PackageGenerationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/sample-dataset/download", response_class=FileResponse)
def download_sample_dataset_package() -> FileResponse:
    zip_path = get_package_zip_path(SAMPLE_PACKAGE_PATH)
    if not zip_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="The sample dataset package has not been generated yet.",
        )
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=zip_path.name,
    )
