from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.auth import WorkspaceOwner
from app.schemas import AuditAction, AuditStatus, PackageGenerationResult
from app.services.audit_trail import append_audit_event
from app.services.dataset_workspace import DatasetNotFoundError
from app.services.dataset_workflow import resolve_dataset_workflow_workspace
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


@router.post(
    "/datasets/{dataset_id}",
    response_model=PackageGenerationResult,
)
def generate_uploaded_dataset_package(
    dataset_id: str,
    _owner: WorkspaceOwner,
) -> PackageGenerationResult:
    try:
        workflow = resolve_dataset_workflow_workspace(dataset_id)
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        package = generate_dataset_package(
            workflow.source_directory,
            workflow.working_copy_directory,
            workflow.package_directory,
            dataset_name=workflow.dataset_name,
            download_url=workflow.package_download_url,
        )
    except PackageGenerationError as exc:
        append_audit_event(
            workflow.workspace_directory,
            dataset_id=dataset_id,
            action=AuditAction.PACKAGE_GENERATION,
            status=AuditStatus.FAILURE,
            summary=(
                "Package generation stopped because workflow prerequisites or "
                "checksum verification were incomplete."
            ),
        )
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception:
        append_audit_event(
            workflow.workspace_directory,
            dataset_id=dataset_id,
            action=AuditAction.PACKAGE_GENERATION,
            status=AuditStatus.FAILURE,
            summary="Package generation failed before a downloadable ZIP was created.",
        )
        raise
    append_audit_event(
        workflow.workspace_directory,
        dataset_id=dataset_id,
        action=AuditAction.PACKAGE_GENERATION,
        status=AuditStatus.SUCCESS,
        summary=(
            f"Generated a validated package containing {len(package.files)} files "
            f"and a {package.zip_size_bytes}-byte ZIP."
        ),
    )
    return package


@router.get("/datasets/{dataset_id}/download", response_class=FileResponse)
def download_uploaded_dataset_package(
    dataset_id: str,
    _owner: WorkspaceOwner,
) -> FileResponse:
    try:
        workflow = resolve_dataset_workflow_workspace(dataset_id)
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    zip_path = get_package_zip_path(workflow.package_directory)
    if not zip_path.is_file():
        raise HTTPException(
            status_code=409,
            detail=(
                "The dataset package has not been generated yet; complete "
                "remediation and validation before downloading."
            ),
        )
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=zip_path.name,
    )
