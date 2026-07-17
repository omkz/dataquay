from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.schemas import DatasetUploadResponse
from app.services.dataset_workspace import (
    DatasetUploadError,
    UnsafeArchiveError,
    UnsupportedUploadError,
    UploadTooLargeError,
    create_dataset_workspace,
)

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


@router.post(
    "/upload",
    response_model=DatasetUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_dataset(
    file: Annotated[UploadFile, File(description="ZIP research dataset")],
) -> DatasetUploadResponse:
    try:
        return await create_dataset_workspace(file)
    except UploadTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except UnsupportedUploadError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except UnsafeArchiveError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DatasetUploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        await file.close()
